import json
from unittest.mock import Mock
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from assistant.benchmark import benchmark, grade_sql, suites
from assistant.budgets import BudgetExceeded, RequestBudget
from assistant.diagnostics import SyntheticSuite
from assistant.evaluation import evaluate
from assistant.generation import run_workflow
from assistant.plan_intent import explicit_constraints, validate_plan_intent, PlanIntentError
from assistant.plans import AnalysisPlan
from assistant.scheduling import QuotaScheduler, ScheduledModel, prepare_call


def args(metric='net_revenue_cents', **changes):
    return {'metric':metric,'grain':'item','dimensions':[],'filters':{},'date_range':None,**changes}


def call(plan):
    return AIMessage(content='',tool_calls=[{'name':'execute_analysis_plan','args':plan,'id':'p'}])


def provider(*replies):
    model=Mock(model_name='scripted')
    model.bind_tools.return_value.invoke.side_effect=list(replies)
    return model


@pytest.fixture
def owned():
    with SyntheticSuite() as suite:
        yield suite


def test_successful_plan_never_calls_summary_provider(retail):
    model=provider(call(args('customers',grain='customer')),RuntimeError('429 on unnecessary summary'))
    report=run_workflow(model,retail,[{'role':'user','content':'How many customers?'}])
    assert report.outcome=='answered' and '12 [q1:r0:c0]' in report.answer
    assert report.answer_validation['method']=='canonical_plan'
    assert report.answer_validation['displayed_verified'] and not report.answer_validation['model_verified']
    assert model.bind_tools.return_value.invoke.call_count==1


def test_evaluator_does_not_count_deterministic_answer_as_model_summary(retail):
    case=suites()['development'][0]
    model=provider(call(args('customers',grain='customer')))
    report=evaluate(retail,model,[case])
    assert report['cases'][0]['passed'] and report['cases'][0]['answer_passed']
    assert report['quality_metrics']['answer_faithfulness']=={'passed':1,'total':1}
    assert report['quality_metrics']['model_answer_faithfulness']=={'passed':0,'total':0}


def test_h05_redundant_group_rejected_before_execution_and_repaired(retail,monkeypatch):
    case=next(c for c in suites()['heldout'] if c['id']=='H05')
    correct=args(filters={'region':'South'},date_range=['2026-03-01','2026-04-01'])
    model=provider(call({**correct,'dimensions':['region']}),call(correct))
    original=retail.query;executed=[]
    def observe(sql,**kwargs):
        executed.append(sql)
        return original(sql,**kwargs)
    monkeypatch.setattr(retail,'query',observe)
    report=run_workflow(model,retail,[{'role':'user','content':case['question']}])
    assert report.outcome=='answered' and len(executed)==1
    assert report.attempts[0]['execution']=='not_run'
    assert report.attempts[0]['intent_fields']==['dimensions']
    assert report.result['columns']==['net_revenue_cents']
    assert report.trace['retries']==1
    assert model.bind_tools.return_value.invoke.call_count==2


@pytest.mark.parametrize('change,field',[
    ({'metric':'gross_sales_cents'},'metric'),({'filters':{'region':'North'}},'filters'),
    ({'date_range':['2026-04-01','2026-05-01']},'date_range'),({'dimensions':['region']},'dimensions'),
])
def test_h05_checks_metric_region_dates_and_shape_separately(change,field):
    question=next(c for c in suites()['heldout'] if c['id']=='H05')['question']
    value=args(filters={'region':'South'},date_range=['2026-03-01','2026-04-01'])
    with pytest.raises(PlanIntentError) as exc:
        validate_plan_intent(AnalysisPlan.parse({**value,**change}),question)
    assert field in exc.value.expected


def test_explicit_grouping_remains_valid():
    value=AnalysisPlan.parse(args(dimensions=['region'],filters={'region':'South'},date_range=['2026-03-01','2026-04-01']))
    validate_plan_intent(value,'Show March 2026 net revenue by region for South.')


def test_h05_plan_matches_all_instances_including_empty_region(owned):
    case=next(c for c in suites()['heldout'] if c['id']=='H05')
    plan=AnalysisPlan.parse(args(filters={'region':'South'},date_range=['2026-03-01','2026-04-01']))
    assert all(r['passed'] for r in grade_sql(plan.compile(),owned.services,case))
    assert owned.services['zero_sales'].query(plan.compile())['rows']==[[None]]


def test_r28_zero_refund_categories_have_explicit_semantics(owned):
    case=next(c for c in suites()['development'] if c['id']=='R28')
    assert 'even when refunds are zero' in case['question']
    result=owned.services['zero_sales'].query(case['gold_sql'])
    assert result['rows']==[['Accessories',0],['Hardware',0],['Software',0]]
    plan=AnalysisPlan.parse(args('refund_cents',dimensions=['category']))
    assert all(r['passed'] for r in grade_sql(plan.compile(),owned.services,case))


def test_r09_requires_the_label_it_grades(owned):
    case=next(c for c in suites()['development'] if c['id']=='R09')
    assert "'Unknown'" in case['question'] and 'alphabetically' in case['question']
    assert all(r['passed'] for r in grade_sql(case['gold_sql'],owned.services,case))


def test_r13_output_contract_names_the_projection_and_order(owned):
    case=next(c for c in suites()['development'] if c['id']=='R13')
    assert 'Return only product_name, ordered alphabetically' in case['question']
    sql='SELECT p.product_name FROM products p WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.product_id=p.product_id) ORDER BY p.product_name'
    assert all(r['passed'] for r in grade_sql(sql,owned.services,case))
    extra=sql.replace('SELECT p.product_name FROM','SELECT p.product_id, p.product_name FROM')
    assert all(r['mismatch']=='shape' for r in grade_sql(extra,owned.services,case))


def test_h05_redundant_group_is_a_cross_instance_shape_regression(owned):
    case=next(c for c in suites()['heldout'] if c['id']=='H05')
    wrong=AnalysisPlan.parse(args(dimensions=['region'],filters={'region':'South'},date_range=['2026-03-01','2026-04-01']))
    assert all(r['mismatch']=='shape' for r in grade_sql(wrong.compile(),owned.services,case))


def test_provider_connection_classification_keeps_private_error_text_out():
    import httpx
    from groq import APIConnectionError, APITimeoutError
    from assistant.budgets import provider_error
    request=httpx.Request('POST','https://example.invalid/private-path')
    assert provider_error(APIConnectionError(message='private diagnostic',request=request))=='provider_connection'
    assert provider_error(APITimeoutError(request=request))=='provider_timeout'
    assert provider_error(ConnectionError('private diagnostic'))=='provider_connection'


def test_benchmark_stops_after_three_provider_failures_and_keeps_partial_evidence(owned):
    model=provider(ConnectionError('private outage'),ConnectionError('private outage'))
    model.invoke.side_effect=ConnectionError('private outage')
    report=benchmark(model,owned.services,[suites()['heldout'][0]],repeats=4)
    assert len(report['rows'])==3
    assert report['completion']=={'planned_attempts':8,'recorded_attempts':3,'not_attempted':5,
                                 'stop_reason':'consecutive_provider_failures'}
    assert report['case_contract_version']=='retail-questions-v3/reserved-questions-v2'
    assert model.invoke.call_count+model.bind_tools.return_value.invoke.call_count==3
    assert 'private outage' not in json.dumps(report)


def test_h08_approved_exists_now_executes_on_every_instance(owned):
    case=next(c for c in suites()['heldout'] if c['id']=='H08')
    assert all(r['passed'] for r in grade_sql(case['gold_sql'],owned.services,case))
    for service in owned.services.values():
        assert service.query(case['gold_sql'])['rows']==[[1]]


def test_h04_canonical_ratio_keeps_cancelled_refunds_and_zero_denominator(owned):
    case=next(c for c in suites()['heldout'] if c['id']=='H04')
    canonical=AnalysisPlan.parse(args('refund_rate')).compile()
    assert all(r['passed'] for r in grade_sql(canonical,owned.services,case))
    wrong="SELECT SUM(refund_cents)*1.0/NULLIF(SUM(gross_sales_cents),0) FROM sales_facts WHERE status='completed'"
    assert [r['passed'] for r in grade_sql(wrong,owned.services,case)]==[True,False,True]
    assert owned.services['zero_sales'].query(canonical)['rows']==[[None]]


def test_h04_raw_sql_must_replan_before_execution(retail,monkeypatch):
    sql='SELECT 1 AS refund_rate'
    model=provider(AIMessage(content='',tool_calls=[{'name':'query_database','args':{'sql':sql},'id':'sql'}]),call(args('refund_rate')))
    real=retail.query;queries=[]
    def observe(sql,**kwargs):queries.append(sql);return real(sql,**kwargs)
    monkeypatch.setattr(retail,'query',observe)
    question=next(c for c in suites()['heldout'] if c['id']=='H04')['question']
    report=run_workflow(model,retail,[{'role':'user','content':question}])
    assert report.outcome=='answered' and len(queries)==1 and queries[0]!=sql
    assert report.attempts[0]['error']=='canonical_plan_required'
    assert report.trace['retries']==1


def test_growth_canonical_plan_matches_r30_on_all_instances(owned):
    case=next(c for c in suites()['development'] if c['id']=='R30')
    plan=AnalysisPlan.parse(args('net_revenue_growth_ratio',date_range=['2026-04-01','2026-05-01']))
    validate_plan_intent(plan,case['question'])
    assert all(r['passed'] for r in grade_sql(plan.compile(),owned.services,case))
    assert owned.services['zero_sales'].query(plan.compile())['rows']==[[None]]


@pytest.mark.parametrize('change',[
 {'date_range':None},{'date_range':['2026-01-01','2026-02-01']},
 {'date_range':['2026-03-01','2026-05-01']},{'dimensions':['month']},{'filters':{'month':'2026-04'}},
])
def test_growth_rejects_unsupported_grain_or_period_shapes(change):
    with pytest.raises(ValueError):AnalysisPlan.parse({**args('net_revenue_growth_ratio',date_range=['2026-04-01','2026-05-01']),**change})


class Clock:
    def __init__(self):self.now=0;self.sleeps=[]
    def __call__(self):return self.now
    def sleep(self,seconds):self.sleeps.append(seconds);self.now+=seconds


def test_quota_wait_longer_than_http_timeout_stays_within_request_budget():
    clock=Clock()
    scheduler=QuotaScheduler(requests_per_minute=1,clock=clock,sleeper=clock.sleep)
    scheduler.acquire(100,RequestBudget(seconds=120,clock=clock))
    model=Mock(model_name='fake')
    model.invoke.return_value=AIMessage(content='{"sql":"SELECT 1"}')
    wrapped=ScheduledModel(model,scheduler=scheduler)
    budget=RequestBudget(seconds=120,clock=clock)
    kwargs,reserved=prepare_call(wrapped,budget,[HumanMessage(content='count')],[])
    assert clock.now==60 and kwargs['timeout']==20
    wrapped.invoke([],**kwargs)
    assert model.invoke.call_count==1 and budget.remaining_seconds()==60


def test_quota_denial_does_not_sleep_or_invoke_past_budget():
    clock=Clock();scheduler=QuotaScheduler(requests_per_minute=1,clock=clock,sleeper=clock.sleep)
    scheduler.acquire(100,RequestBudget(seconds=120,clock=clock))
    model=Mock();wrapped=ScheduledModel(model,scheduler=scheduler)
    with pytest.raises(BudgetExceeded):prepare_call(wrapped,RequestBudget(seconds=10,clock=clock),[],[])
    assert clock.sleeps==[] and model.invoke.call_count==0


def test_token_accounting_releases_overreservation_and_shares_bindings():
    clock=Clock();scheduler=QuotaScheduler(tokens_per_minute=6000,clock=clock,sleeper=clock.sleep)
    model=Mock(model_name='fake')
    reply=AIMessage(content='ok',usage_metadata={'input_tokens':10,'output_tokens':10,'total_tokens':20})
    model.invoke.return_value=reply;model.bind_tools.return_value.invoke.return_value=reply
    wrapped=ScheduledModel(model,scheduler=scheduler);bound=wrapped.bind_tools([])
    assert bound.scheduler is scheduler
    for target in (wrapped,bound):
        kwargs,_=prepare_call(target,RequestBudget(seconds=120,clock=clock),[],[])
        target.invoke([],**kwargs)
    assert sum(t.tokens for t in scheduler.tickets)==40 and clock.now==0


def test_429_cooldown_uses_retry_after_without_retrying_same_request():
    clock=Clock();scheduler=QuotaScheduler(clock=clock,sleeper=clock.sleep)
    model=Mock(model_name='fake');exc=RuntimeError('private provider error')
    exc.status_code=429;exc.response=Mock(headers={'retry-after':'35'})
    model.invoke.side_effect=exc;wrapped=ScheduledModel(model,scheduler=scheduler)
    kwargs,_=prepare_call(wrapped,RequestBudget(seconds=120,clock=clock),[],[])
    with pytest.raises(RuntimeError):wrapped.invoke([],**kwargs)
    assert model.invoke.call_count==1 and scheduler.cooldown==35
    with pytest.raises(BudgetExceeded):prepare_call(wrapped,RequestBudget(seconds=10,clock=clock),[],[])
    assert model.invoke.call_count==1


def test_token_window_blocks_a_second_large_reservation():
    clock=Clock();scheduler=QuotaScheduler(tokens_per_minute=100,clock=clock,sleeper=clock.sleep)
    scheduler.acquire(70,RequestBudget(seconds=120,clock=clock))
    scheduler.acquire(70,RequestBudget(seconds=120,clock=clock))
    assert clock.now==60


def test_missing_usage_keeps_reservation_and_oversize_requests_are_denied():
    scheduler=QuotaScheduler(tokens_per_minute=100)
    ticket=scheduler.acquire(80,RequestBudget())
    scheduler.complete(ticket,AIMessage(content='no usage'))
    assert ticket.tokens==80
    with pytest.raises(BudgetExceeded):scheduler.acquire(101,RequestBudget())


def test_failure_layers_and_invalid_oracle_are_distinct(owned):
    services=owned.services;case=next(c for c in suites()['heldout'] if c['id']=='H05')
    assert all(r['error']=='policy_rejection' for r in grade_sql('DELETE FROM customers',services,case))
    assert all(r['error']=='database_error' for r in grade_sql('SELECT nonexistent FROM customers',services,case))
    assert all(r['error']=='result_mismatch' for r in grade_sql('SELECT 999',services,case))
    bad={**case,'gold_sql':'SELECT nonexistent FROM customers'}
    model=Mock()
    report=benchmark(model,services,[bad],repeats=1)
    assert all(r['outcome']=='invalid_reference' for r in report['rows'])
    assert report['summary']['workflow']['invalid_references']==1
    model.bind_tools.assert_not_called();model.invoke.assert_not_called()


def test_diagnostics_require_owned_active_services_and_known_cases(owned,retail):
    case=suites()['heldout'][0]
    with owned.capture(owned.services) as capture:
        model=provider(call(args('customers',grain='customer')))
        model.invoke.return_value=AIMessage(content='{"sql":"SELECT COUNT(*) FROM customers"}')
        report=benchmark(model,owned.services,[case],1,diagnostics=capture)
        assert report['summary']['workflow']['passed']==1
        assert capture.export()['rows'][0]['attempts'][0]['plan']['metric']=='customers'
        assert 'SELECT' not in json.dumps(report)
        with pytest.raises(PermissionError):benchmark(model,{'base':retail},[case],1,diagnostics=capture)
        with pytest.raises(PermissionError):benchmark(model,owned.services,[{**case,'question':'private user question'}],1,diagnostics=capture)
    owned.close()
    with pytest.raises(PermissionError):capture.export()


def test_multiple_plan_calls_are_all_executed_before_model_summary(retail,monkeypatch):
    first=call(args('customers',grain='customer'))
    second={**first.tool_calls[0],'id':'second'}
    model=provider(AIMessage(content='',tool_calls=[first.tool_calls[0],second]),
        AIMessage(content=json.dumps({'facts':[{'result_id':'q2','row':0,'column':0,'value':12}]})))
    report=run_workflow(model,retail,[{'role':'user','content':'Run two customer counts'}])
    assert len(report.attempts)==2 and report.answer_validation['model_verified']
    assert model.bind_tools.return_value.invoke.call_count==2


def test_truncated_canonical_result_remains_explicitly_partial(retail):
    retail.max_rows=1
    model=provider(call(args(dimensions=['category'])))
    report=run_workflow(model,retail,[{'role':'user','content':'Show net revenue by category'}])
    assert report.outcome=='answered' and report.result['truncated']
    assert 'partial result' in report.answer
    assert model.bind_tools.return_value.invoke.call_count==1


def test_diagnostic_ownership_cannot_be_forged_by_retail_marker(owned,retail):
    retail.retail=True
    with pytest.raises(PermissionError):
        with owned.capture({'base':retail,'skewed':retail,'zero_sales':retail}):pass
    original=owned.services['base'].engine
    try:
        owned.services['base'].engine=retail.engine
        with pytest.raises(PermissionError):owned.authorize(owned.services)
    finally:owned.services['base'].engine=original


def test_growth_compiles_safely_for_every_dialect():
    from assistant.validation import validate_sql
    from assistant.demo import TABLES
    plan=AnalysisPlan.parse(args('net_revenue_growth_ratio',date_range=['2026-04-01','2026-05-01']))
    for dialect in ('sqlite','postgres','mysql'):
        assert validate_sql(plan.compile(dialect),dialect,{('',t) for t in TABLES})
