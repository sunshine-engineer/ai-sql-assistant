import json
import sqlite3
from unittest.mock import Mock
import pytest
from langchain_core.messages import AIMessage
from assistant.plans import AnalysisPlan
from assistant.budgets import RequestBudget, BudgetExceeded, provider_error
from assistant.catalog import select_catalog
from assistant.instances import build_instance, INSTANCES
from assistant.connections import open_engine
from assistant.demo import TABLES
from assistant.execution import QueryService
from assistant.benchmark import grade_sql, suites, benchmark
from assistant.generation import run_workflow
from assistant.telemetry import record, aggregate
from assistant.validation import UnsafeSQL


def plan(metric='gross_sales_cents', **kwargs):
    return AnalysisPlan.parse({'metric':metric,'grain':'item','dimensions':[], 'filters':{}, 'date_range':None, **kwargs})


@pytest.fixture
def instances(tmp_path):
    services={}
    for name in INSTANCES:
        engine=open_engine('sqlite',path=build_instance(tmp_path,name))
        service=QueryService(engine,tables=TABLES)
        service.retail=True
        services[name]=service
    yield services
    for service in services.values():
        service.engine.dispose()


def test_constant_answer_rejected_across_instances(instances):
    case=suites()['heldout'][0]
    outcomes=grade_sql('SELECT 12 AS customers', instances,case)
    assert [i['passed'] for i in outcomes]==[True,False,False]
    assert all(i['passed'] for i in grade_sql('SELECT COUNT(*) FROM customers',instances,case))


@pytest.mark.parametrize('metric,oracle',[
 ('gross_sales_cents',"SELECT COALESCE(SUM(i.quantity*i.unit_price_cents),0) FROM order_items i JOIN orders o ON o.order_id=i.order_id WHERE o.status='completed'"),
 ('refund_cents','SELECT COALESCE(SUM(amount_cents),0) FROM refunds'),
 ('orders',"SELECT COUNT(*) FROM orders WHERE status='completed'"),
 ('units',"SELECT COALESCE(SUM(i.quantity),0) FROM order_items i JOIN orders o ON o.order_id=i.order_id WHERE o.status='completed'"),
])
def test_canonical_metrics_match_independent_normalized_oracles(instances,metric,oracle):
    grain='order' if metric=='orders' else 'item'
    for service in instances.values():
        assert service.query(plan(metric,grain=grain).compile())['rows']==service.query(oracle)['rows']


def test_zero_denominator_and_null_regions(instances):
    zero=instances['zero_sales']
    assert zero.query(plan('refund_rate').compile())['rows']==[[None]]
    assert zero.query(plan(dimensions=['region']).compile())['rows']==[[None,0]]


def test_refund_fanout_cannot_bypass_controlled_execution(instances):
    sql="SELECT SUM(i.quantity*i.unit_price_cents) FROM order_items i JOIN orders o ON o.order_id=i.order_id LEFT JOIN refunds r ON r.item_id=i.item_id WHERE o.status='completed'"
    for service in instances.values():
        with pytest.raises(UnsafeSQL):service.query(sql)


@pytest.mark.parametrize('changes',[
 {'metric':'invented'}, {'grain':'customer'}, {'dimensions':['customer_name']},
 {'filters':{'region':['North','South']}}, {'date_range':['2026-04-02','2026-04-01']},
 {'date_range':['2025-01-01','2026-04-01']}, {'metric':[]}, {'dimensions':['region','region']},
])
def test_invalid_plans(changes):
    with pytest.raises((ValueError,TypeError)):plan(**changes)


def test_filter_literals_cannot_inject_sql(retail):
    result=retail.query(plan(filters={'region':"North' OR 1=1 --"}).compile())
    assert result['rows']==[[None]]


def test_plan_tool_uses_canonical_sql_and_references(retail):
    model=Mock(model_name='test')
    model.bind_tools.return_value.invoke.side_effect=[
      AIMessage(content='',tool_calls=[{'name':'execute_analysis_plan','args':{'metric':'customers','grain':'customer','dimensions':[],'filters':{},'date_range':None},'id':'p1'}]),
      AIMessage(content=json.dumps({'facts':[{'result_id':'q1','row':0,'column':0,'value':12}]}))]
    report=run_workflow(model,retail,[{'role':'user','content':'How many customers?'}])
    assert report.outcome=='answered' and report.answer_validation['model_verified']
    assert report.attempts[0]['plan']['grain']=='customer'
    assert 'COUNT(*)' in report.attempts[0]['sql']


def test_budget_prevents_model_call_and_post_deadline_execution(retail):
    model=Mock()
    report=run_workflow(model,retail,[{'role':'user','content':'Count customers'}],budget=RequestBudget(tokens=10))
    assert report.outcome=='budget_exhausted'
    model.bind_tools.return_value.invoke.assert_not_called()
    assert report.trace['model_calls']==[]
    clock=[0]
    budget=RequestBudget(seconds=1,clock=lambda:clock[0])
    def late(*a,**kw):
        clock[0]=2
        return AIMessage(content='',tool_calls=[{'name':'query_database','args':{'sql':'SELECT 1'},'id':'late'}])
    model.bind_tools.return_value.invoke.side_effect=late
    report=run_workflow(model,retail,[{'role':'user','content':'Count customers'}],budget=budget)
    assert report.outcome=='budget_exhausted' and report.attempts==[]


def test_missing_usage_charges_reservation():
    budget=RequestBudget(tokens=10000)
    kwargs,reserved=budget.admit([],[])
    assert kwargs['max_tokens']<=1500 and kwargs['timeout']<=20
    budget.charge(AIMessage(content='x'),reserved)
    assert budget.spent==reserved


@pytest.mark.parametrize('status,expected',[(429,'rate_limit'),(401,'authentication'),(403,'authentication'),(404,'model_or_request'),(500,'provider_unavailable')])
def test_provider_error_classes(status,expected):
    exc=RuntimeError('private exception with secret')
    exc.status_code=status
    assert provider_error(exc)==expected


def test_large_catalog_selection_is_bounded_and_not_authorization():
    catalog={f'noise_{i}':[{'name':'unrelated','type':'TEXT'}] for i in range(500)}
    catalog['customers']=[{'name':'customer_id','type':'INTEGER'}]
    catalog['orders']=[{'name':'customer_id','type':'INTEGER'},{'name':'order_date','type':'TEXT'}]
    selected=select_catalog(catalog,'Count customers with orders')
    assert {'customers','orders'}<=set(selected)
    assert len(selected)<=8 and len(json.dumps(selected).encode())<=12000
    assert not select_catalog(catalog,'xyzzy')


def test_telemetry_allowlist_and_aggregation(tmp_path):
    path=tmp_path/'ops.db'
    trace={'outcome':'failed','duration_ms':5,'token_usage':{'total_tokens':9},'token_usage_complete':True,
           'model_calls':[{'error_category':'rate_limit','secret':'should-not-store'}],
           'sql':'private-sql','prompt':'secret-question','retries':1,'tool_calls':[]}
    record(path,trace);record(path,trace)
    result=aggregate(path)
    assert result['requests']==2 and result['provider_errors']=={'rate_limit':2}
    assert result['measured_tokens']==18
    assert b'should-not-store' not in path.read_bytes() and b'secret-question' not in path.read_bytes()


def test_same_sql_reused_across_instances_in_scripted_benchmark(instances):
    model=Mock(model_name='scripted')
    model.bind_tools.return_value.invoke.side_effect=[
      AIMessage(content='',tool_calls=[{'name':'query_database','args':{'sql':'SELECT 12 AS customers'},'id':'q'}]),
      AIMessage(content=json.dumps({'facts':[{'result_id':'q1','row':0,'column':0,'value':12}]}))]
    model.invoke.return_value=AIMessage(content='{"sql":"SELECT COUNT(*) FROM customers"}')
    report=benchmark(model,instances,[suites()['heldout'][0]],repeats=1)
    assert report['summary']['workflow']['sql_suite_passed']==0
    assert report['summary']['one_shot']['sql_suite_passed']==1
    assert 'SELECT 12' not in json.dumps(report)


def test_reviewer_policy_blocks_real_database_configuration(monkeypatch):
    from assistant.config import AppConfig, DEFAULT_DATABASE
    from assistant.deployment import enforce_deployment
    monkeypatch.setenv('ASSISTANT_DEPLOYMENT','reviewer')
    enforce_deployment(AppConfig('sqlite',{'path':str(DEFAULT_DATABASE)}))
    with pytest.raises(PermissionError):enforce_deployment(AppConfig('postgres',{'host':'private'}))
    with pytest.raises(PermissionError):enforce_deployment(AppConfig('sqlite',{'path':'/tmp/private.db'}))


def test_hosted_identity_and_user_scope_fail_closed(monkeypatch):
    from assistant.access import hosted_config
    from assistant.deployment import enforce_deployment
    principal={'is_logged_in':True,'email_verified':True,'email':'analyst@example.test','exp':4102444800}
    grant={'kind':'postgres','schema':'reporting','provider_approved':True,
           'columns':{'approved_sales':['month','net_cents']},
           'connection':{'host':'db.example.test','tls_ca':'/trusted/root.crt'}}
    grants={principal['email']:grant}
    config=hosted_config(principal,grants,'private-provider-key','test/model')
    assert config.approved_columns==grant['columns'] and config.hosted
    assert principal['email'] not in repr(config)
    monkeypatch.setenv('ASSISTANT_DEPLOYMENT','hosted')
    enforce_deployment(config)
    for changes in ({'is_logged_in':False},{'email_verified':False},{'email':'other@example.test'},{'exp':0}):
        with pytest.raises(PermissionError):hosted_config({**principal,**changes},grants,'key','model')
    for changes in ({'provider_approved':False},{'columns':{}},{'connection':{'host':'db'}}):
        with pytest.raises(PermissionError):hosted_config(principal,{principal['email']:{**grant,**changes}},'key','model')


def test_restricted_view_projection_hides_metadata_and_blocks_bypasses(tmp_path):
    path=tmp_path/'views.db'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE raw_data(month TEXT, net_cents INT, private_email TEXT); '
                         "INSERT INTO raw_data VALUES ('2026-04',12,'private@example.test'); "
                         'CREATE VIEW approved_sales AS SELECT * FROM raw_data;')
    engine=open_engine('sqlite',path=path)
    try:
        service=QueryService(engine,tables=['approved_sales'],approved_columns={'approved_sales':['month','net_cents']})
        assert 'private_email' not in service.describe('sales')
        assert service.query('SELECT SUM(net_cents) FROM approved_sales')['rows']==[[12]]
        for sql in ('SELECT * FROM approved_sales','SELECT private_email FROM approved_sales',
                    'SELECT net_cents FROM approved_sales WHERE private_email IS NOT NULL',
                    'SELECT COUNT(*) FROM raw_data',
                    'SELECT s.private_email FROM approved_sales s',
                    'SELECT net_cents FROM (SELECT private_email AS net_cents FROM approved_sales) x'):
            with pytest.raises(UnsafeSQL):service.query(sql)
    finally:engine.dispose()


@pytest.mark.parametrize('kind,options',[('postgres',{'sslmode':'verify-full','sslrootcert':'CA'}),
                                       ('mysql',{'ssl_ca':'CA','ssl_verify_cert':True,'ssl_verify_identity':True})])
def test_verified_tls_settings(monkeypatch,tmp_path,kind,options):
    from assistant.connections import open_engine
    ca=tmp_path/'ca.pem';ca.write_text('test-ca')
    factory=Mock()
    monkeypatch.setattr('assistant.connections.create_engine',factory)
    open_engine(kind,host='db.example.test',port=5432,user='readonly',password='secret',database='reports',tls_ca=str(ca))
    args=factory.call_args.kwargs['connect_args']
    for key,value in options.items():assert args[key]==(str(ca) if value=='CA' else value)


def test_provider_question_redaction():
    from assistant.access import provider_question
    assert 'private@example.test' not in provider_question('Find private@example.test')
    assert 'gsk_abcdef' not in provider_question('key gsk_abcdef')


def test_exists_is_read_only_but_nested_unsafe_functions_rejected(retail):
    sql='SELECT COUNT(*) FROM products p WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.product_id=p.product_id)'
    assert retail.query(sql)['rows']==[[1]]
    with pytest.raises(UnsafeSQL):retail.query("SELECT EXISTS (SELECT pg_read_file('/secret'))")


def test_canonical_empty_sum_preserves_null(retail):
    assert retail.query(plan(filters={'region':'absent'}).compile())['rows']==[[None]]


def test_reference_execution_failure_has_distinct_category(instances):
    outcomes=grade_sql('SELECT 1',instances,{'gold_sql':'SELECT secret FROM nonexistent'})
    assert all(row['error']=='reference_execution_failed' for row in outcomes)


@pytest.mark.parametrize('dialect',['sqlite','postgres','mysql'])
@pytest.mark.parametrize('metric',['gross_sales_cents','net_revenue_cents','refund_cents','refund_rate','units','orders','customers'])
def test_compiled_plan_validates_in_every_supported_dialect(metric,dialect):
    from assistant.validation import validate_sql
    from assistant.plans import METRICS
    candidate=plan(metric,grain=METRICS[metric][0],dimensions=['region'],filters={'region':'South'})
    assert validate_sql(candidate.compile(dialect),dialect,{('',t) for t in TABLES})


def test_post_database_deadline_stops_summarization(retail,monkeypatch):
    clock=[0]
    budget=RequestBudget(seconds=1,clock=lambda:clock[0])
    real_query=retail.query
    def late_query(*args,**kwargs):
        result=real_query(*args,**kwargs);clock[0]=2;return result
    monkeypatch.setattr(retail,'query',late_query)
    model=Mock()
    model.bind_tools.return_value.invoke.return_value=AIMessage(content='',tool_calls=[{'name':'query_database','args':{'sql':'SELECT 1'},'id':'q'}])
    report=run_workflow(model,retail,[{'role':'user','content':'Show one value'}],budget=budget)
    assert report.outcome=='budget_exhausted'
    assert model.bind_tools.return_value.invoke.call_count==1


def test_real_large_catalog_does_not_fill_prompt(tmp_path):
    path=tmp_path/'catalog.db'
    with sqlite3.connect(path) as db:
        for i in range(500):db.execute(f'CREATE TABLE noise_{i}(unrelated TEXT)')
        db.execute('CREATE TABLE customers(customer_id INT)')
        db.execute('CREATE TABLE orders(customer_id INT, order_date TEXT)')
    engine=open_engine('sqlite',path=path)
    try:
        service=QueryService(engine)
        selected=json.loads(service.describe('Count customers with orders'))
        assert {'customers','orders'}<=set(selected)
        assert len(selected)<=8 and len(json.dumps(selected).encode())<=12000
        # Metadata selection cannot expand or revoke application authorization.
        assert service.query('SELECT COUNT(*) FROM noise_1')['rows']==[[0]]
    finally:engine.dispose()


def test_net_revenue_oracle_and_zero_targets(instances):
    for name,service in instances.items():
        gross=service.query("SELECT SUM(i.quantity*i.unit_price_cents) FROM order_items i JOIN orders o ON o.order_id=i.order_id WHERE o.status='completed'")['rows'][0][0]
        refunds=service.query('SELECT COALESCE(SUM(amount_cents),0) FROM refunds')['rows'][0][0]
        assert service.query(plan('net_revenue_cents').compile())['rows']==[[gross-refunds]]
        if name!='base':
            assert service.query('SELECT COUNT(*) FROM targets WHERE target_cents=0')['rows'][0][0]>0


@pytest.mark.parametrize('status,expected',[(429,'rate_limit'),(401,'authentication'),(None,'provider_timeout')])
def test_baseline_provider_failures_preserve_sanitized_trace(retail,status,expected):
    from assistant.benchmark import one_shot
    model=Mock(model_name='test/model')
    exc=TimeoutError('secret-message') if status is None else RuntimeError('secret-message')
    if status is not None:exc.status_code=status
    model.invoke.side_effect=exc
    result=one_shot(model,retail,'Count all customers')
    assert result['error']==expected and result['outcome']=='failed'
    assert result['trace']['model_calls'][0]['error_category']==expected
    assert 'secret-message' not in json.dumps(result)


def test_schema_discovery_stops_at_request_deadline(monkeypatch):
    clock=[0]
    budget=RequestBudget(seconds=1,clock=lambda:clock[0])
    inspector=Mock()
    inspector.get_table_names.return_value=['first','second']
    inspector.get_view_names.return_value=[]
    def slow_columns(*a,**kw):
        clock[0]=2
        return [{'name':'value','type':'INTEGER'}]
    inspector.get_columns.side_effect=slow_columns
    monkeypatch.setattr('assistant.execution.inspect',lambda engine:inspector)
    engine=Mock();engine.dialect.name='sqlite'
    with pytest.raises(BudgetExceeded):QueryService(engine,budget=budget)
    assert inspector.get_columns.call_count==1


def test_workflow_inherits_setup_budget(retail):
    clock=[0]
    retail.request_budget=RequestBudget(seconds=1,clock=lambda:clock[0])
    clock[0]=2
    model=Mock()
    report=run_workflow(model,retail,[{'role':'user','content':'Count all customers'}])
    assert report.outcome=='budget_exhausted'
    assert report.trace['request_elapsed_ms']==2000
    model.bind_tools.return_value.invoke.assert_not_called()
