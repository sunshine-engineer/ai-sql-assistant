"""Analytics contracts use real deterministic data and a scripted provider."""
import json
import sqlite3
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage

from assistant.business import preflight
from assistant.charts import chart_data
from assistant.connections import open_engine
from assistant.demo import build_demo, TABLES
from assistant.evaluation import load_cases, evaluate, same_results
from assistant.execution import QueryService
from assistant.generation import run_workflow
from assistant.tracing import query_fingerprint, model_identifier



def call(sql, assumptions=None):
    return AIMessage(content='', tool_calls=[{'id': 'q1', 'name': 'query_database',
                     'args': {'sql': sql, 'assumptions': assumptions or ['USD cents']}}])


def provider(*replies):
    model = Mock(model_name='fixture/provider')
    model.bind_tools.return_value.invoke.side_effect = list(replies)
    return model


@pytest.mark.parametrize('case', load_cases(), ids=lambda c: c['id'])
def test_frozen_reference_cases(retail, case):
    result = evaluate(retail, cases=[case])
    assert result['mode'] == 'reference_fixture'
    assert result['cases'][0]['passed'], case['question']


def test_fixture_invariants_and_reproducibility(tmp_path):
    first, second = build_demo(tmp_path/'a.db'), build_demo(tmp_path/'b.db')
    with sqlite3.connect(first) as a, sqlite3.connect(second) as b:
        assert list(a.iterdump()) == list(b.iterdump())
        assert a.execute('PRAGMA foreign_key_check').fetchall() == []
        assert a.execute('SELECT COUNT(*) FROM orders').fetchone()[0] == 144
        assert a.execute('SELECT COUNT(*) FROM order_items').fetchone()[0] == 288
        gross, refund, net = a.execute('SELECT SUM(gross_sales_cents),SUM(refund_cents),SUM(net_revenue_cents) FROM sales_facts').fetchone()
        assert gross - refund == net
        assert refund == a.execute('SELECT SUM(amount_cents) FROM refunds').fetchone()[0]
        assert a.execute("SELECT SUM(gross_sales_cents) FROM sales_facts WHERE status='cancelled'").fetchone()[0] == 0
        assert a.execute('SELECT COUNT(*) FROM sales_facts WHERE region IS NULL').fetchone()[0] > 0
        a.execute("UPDATE customers SET customer_name='preserved' WHERE customer_id=1")
        a.commit()
    build_demo(first)
    with sqlite3.connect(first) as a:
        assert a.execute('SELECT customer_name FROM customers WHERE customer_id=1').fetchone()[0] == 'preserved'


def test_result_grading_uses_rows_not_sql_or_aliases():
    case = {'rows': [[1, 2.0], [1, 2.0]], 'columns': ['a', 'b'], 'ordered': False}
    assert same_results({'rows': [[1, 2.000000001], [1, 2.0]], 'columns': ['x','y']}, case)
    assert not same_results({'rows': [[1, 2.0]], 'columns': ['x','y']}, case)
    assert not same_results({'rows': [[1, 2.0], [1, 2.0]], 'columns': ['x','y'], 'truncated': True}, case)
    assert not same_results({'rows': [['1', 2.0], [1, 2.0]], 'columns': ['x','y']}, case)


def test_live_evaluation_detects_wrong_executed_results(retail):
    case = load_cases()[0]
    good = evaluate(retail, provider(call(case['gold_sql']), AIMessage(content=json.dumps({'facts':[{'result_id':'q1','row':0,'column':0,'value':12}]}))), [case])
    bad = evaluate(retail, provider(call('SELECT 99 AS customers'), AIMessage(content=json.dumps({'facts':[{'result_id':'q1','row':0,'column':0,'value':12}]}))), [case])
    assert good['mode'] == 'live_model' and good['cases'][0]['passed']
    assert not bad['cases'][0]['passed']  # Correct prose cannot hide a wrong executed result.


def test_repair_is_bounded_and_inspectable(retail):
    model = provider(call('SELECT nonexistent FROM sales_facts'),
                     call('SELECT SUM(net_revenue_cents) AS net FROM sales_facts'),
                     AIMessage(content='See the executed total.'))
    report = run_workflow(model, retail, [{'role':'user','content':'Show total net revenue.'}])
    assert report.outcome == 'answered'
    assert report.trace['retries'] == 1
    assert report.attempts[0]['error'] == 'unknown_column'
    assert report.attempts[1]['tables'] == ['sales_facts']
    assert report.attempts[1]['validation'] == 'passed'
    stages = [s['stage'] for s in report.trace['stages']]
    assert stages[0] == 'understand' and stages[-1] == 'summarize'
    assert 'validate' in stages and 'execute' in stages
    never_works = provider(*[call('SELECT nonexistent FROM sales_facts')]*5)
    failed = run_workflow(never_works, retail, [{'role':'user','content':'Show total net revenue.'}])
    assert failed.outcome == 'failed'
    assert len(failed.attempts) == 3 and failed.trace['retries'] == 2


def test_policy_failure_never_retries_or_modifies_data(retail):
    report = run_workflow(provider(call('DELETE FROM orders')), retail,
                          [{'role':'user','content':'Show all completed orders.'}])
    assert report.outcome == 'refused'
    assert report.attempts[0]['execution'] == 'not_run'
    assert report.trace['retries'] == 0
    assert retail.query('SELECT COUNT(*) FROM orders')['rows'] == [[144]]


def test_month_followup_preserves_metric_and_region(retail):
    sql = "SELECT SUM(net_revenue_cents) AS net FROM sales_facts WHERE order_date >= '2026-04-01' AND order_date < '2026-05-01' AND region='North' AND category='Hardware'"
    first = run_workflow(provider(call(sql), AIMessage(content='Done')), retail,
                         [{'role':'user','content':'Show April 2026 North Hardware net revenue.'}])
    unused = Mock()
    followup = run_workflow(unused, retail, [{'role':'user','content':'Compare that with last month.'}], context=first.context)
    assert followup.outcome == 'answered'
    unused.bind_tools.assert_not_called()  # No new model interpretation can lose filters.
    for attempt in followup.attempts[:2]:
        assert "region = 'North'" in attempt['sql'] and "category = 'Hardware'" in attempt['sql']
        assert 'SUM(net_revenue_cents)' in attempt['sql']
    march = retail.query(sql.replace('2026-04-01','2026-03-01').replace('2026-05-01','2026-04-01'))['rows'][0][0]
    assert followup.result['rows'] == [['2026-03', march], ['2026-04', first.result['rows'][0][0]]]
    assert chart_data(followup.result)['kind'] == 'line'


def test_followup_requires_unambiguous_month(retail):
    result = run_workflow(Mock(), retail, [{'role':'user','content':'Compare that with last month.'}], context={'sql':'SELECT SUM(net_revenue_cents) FROM sales_facts'})
    assert result.outcome == 'clarify'
    result = run_workflow(Mock(), retail, [{'role':'user','content':'Compare that with last month.'}], context={'sql':"SELECT SUM(net_revenue_cents) FROM sales_facts WHERE order_date >= '2026-01-01' AND order_date < '2026-02-01'"})
    assert result.outcome == 'unsupported'


def test_trace_contains_no_prompts_sql_results_or_secret_values(retail):
    secret = 'private@example.com'
    reply = AIMessage(content=secret, usage_metadata={'input_tokens': 20, 'output_tokens': 5, 'total_tokens':25})
    model = provider(call(f"SELECT '{secret}' AS value"), reply)
    report = run_workflow(model, retail, [{'role':'user','content':secret}])
    trace = json.dumps(report.trace)
    assert secret not in trace and 'SELECT' not in trace and 'assumptions' not in trace
    assert report.trace['token_usage'] == {'input_tokens':20,'output_tokens':5,'total_tokens':25}
    assert len(report.trace['model_calls']) == 2
    assert report.trace['token_usage_complete'] is False  # Only the final scripted reply reported usage.
    assert query_fingerprint("SELECT 'Alice'",'sqlite') == query_fingerprint("SELECT 'Bob'",'sqlite')
    assert model_identifier(Mock(model_name='gsk_secret-token')) == '[redacted]'


def test_missing_usage_and_provider_errors_are_explicit(retail):
    model = provider()
    model.bind_tools.return_value.invoke.side_effect = RuntimeError('secret-api-key')
    report = run_workflow(model, retail, [{'role':'user','content':'Show gross sales.'}])
    assert report.outcome == 'failed' and report.trace['token_usage'] is None
    assert 'secret-api-key' not in json.dumps(report.trace)
    assert report.trace['model_calls'][0]['outcome'] == 'failed'


@pytest.mark.parametrize('question', ['Show the drop in net revenue in March 2026.', 'Create a summary of gross sales.'])
def test_business_filter_does_not_restore_keyword_false_positives(question):
    assert preflight(question) is None


def test_chart_never_invents_aggregations_or_values():
    result = {'columns':['category','net_cents'],'rows':[['A',10],['B',20]]}
    chart = chart_data(result)
    assert chart['frame']['net_cents'].tolist() == [10,20]
    assert chart_data({'columns':['category','net_cents'],'rows':[['A',10],['A',20]]}) is None
    assert chart_data({'columns':['net_cents'],'rows':[[10]]}) is None



def test_timeout_is_terminal_without_model_repair(retail):
    retail.timeout_ms = 0
    model = provider(call('SELECT SUM(a.quantity + b.quantity) FROM sales_facts a CROSS JOIN sales_facts b'))
    report = run_workflow(model, retail, [{'role':'user','content':'Show completed order totals.'}])
    assert report.outcome == 'failed'
    assert report.attempts[0]['error'] == 'timeout'
    assert report.trace['retries'] == 0
    assert model.bind_tools.return_value.invoke.call_count == 1


def test_decimal_chart_values_keep_original_units():
    from decimal import Decimal
    result = {'columns':['month','net_cents'],'rows':[['2026-03',Decimal('123.25')],['2026-04',Decimal('144.75')]]}
    chart = chart_data(result)
    assert chart['kind'] == 'line'
    assert chart['frame']['net_cents'].tolist() == [123.25,144.75]


def test_month_comparison_does_not_fabricate_a_third_execution(retail):
    sql = "SELECT 'label' AS period, SUM(net_revenue_cents) AS net FROM sales_facts WHERE order_date >= '2026-04-01' AND order_date < '2026-05-01'"
    report = run_workflow(Mock(), retail, [{'role':'user','content':'Compare that with last month.'}], context={'sql':sql})
    assert len(report.attempts) == len(report.trace['tool_calls']) == 2
    assert report.result['columns'] == ['_period','period','net']
    assert report.result['rows'][0][0] == '2026-03'


def test_conditional_analytics_still_validate_all_branches(retail):
    from assistant.validation import UnsafeSQL
    result = retail.query("SELECT SUM(CASE WHEN status='completed' THEN quantity ELSE 0 END) AS units FROM sales_facts")
    expected = retail.query("SELECT SUM(quantity) AS units FROM sales_facts WHERE status='completed'")
    assert result['rows'] == expected['rows']
    with pytest.raises(UnsafeSQL):
        retail.query("SELECT CASE WHEN 1=1 THEN 1 ELSE load_extension('bad') END")
