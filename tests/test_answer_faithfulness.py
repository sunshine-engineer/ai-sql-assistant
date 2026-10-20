"""Numeric claims must identify an actual cell; correct SQL alone is insufficient."""
from decimal import Decimal
import json
from unittest.mock import Mock
import pytest
from langchain_core.messages import AIMessage

from assistant.answers import assess_answer
from assistant.evaluation import evaluate, load_cases
from assistant.generation import run_workflow


def answer(value=12, result_id='q1', row=0, column=0):
    return json.dumps({'facts':[{'result_id':result_id,'row':row,'column':column,'value':value}]})


def provider(sql, content):
    model = Mock(model_name='scripted/provider')
    model.bind_tools.return_value.invoke.side_effect = [
        AIMessage(content='',tool_calls=[{'name':'query_database','args':{'sql':sql},'id':'one'}]),
        AIMessage(content=content),
    ]
    return model


@pytest.fixture
def count_result():
    return {'result_id':'q1','columns':['customers'],'rows':[[12]],'truncated':False}


@pytest.mark.parametrize('candidate', [
    'There are 999 customers in the database.', answer(999),
])
def test_correct_sql_with_contradictory_answer_fails_separate_quality_grade(retail, candidate):
    case = load_cases()[0]
    model = provider(case['gold_sql'], candidate)
    evaluation = evaluate(retail, model, [case])
    row = evaluation['cases'][0]
    assert row['query_passed'] is True
    assert row['answer_passed'] is False
    assert row['displayed_answer_passed'] is True
    assert row['passed'] is False and row['error'] == 'answer_not_faithful'
    assert evaluation['quality_metrics']['query_results'] == {'passed':1,'total':1}
    assert evaluation['quality_metrics']['model_answer_faithfulness'] == {'passed':0,'total':1}
    report = run_workflow(provider(case['gold_sql'], candidate), retail, [{'role':'user','content':case['question']}])
    assert '999' not in report.answer and '12 [q1:r0:c0]' in report.answer
    assert report.facts == [{'result_id':'q1','row':0,'column':0,'value':12}]
    assert '999' not in json.dumps(report.trace)


def test_correct_structured_answer_passes_sql_and_faithfulness(retail):
    case = load_cases()[0]
    report = evaluate(retail, provider(case['gold_sql'],answer()), [case])
    row = report['cases'][0]
    assert row['query_passed'] and row['answer_passed'] and row['passed']
    assert report['quality_metrics']['model_answer_faithfulness'] == {'passed':1,'total':1}


def test_answer_can_be_faithful_to_wrong_sql_but_case_still_fails(retail):
    report = evaluate(retail, provider('SELECT 99 AS customers',answer(99)), [load_cases()[0]])
    row = report['cases'][0]
    assert row['query_passed'] is False and row['answer_passed'] is True
    assert row['passed'] is False


def test_reference_mode_does_not_invent_answer_scores(retail):
    report = evaluate(retail, cases=[load_cases()[0]])
    assert report['quality_metrics']['query_results'] == {'passed':1,'total':1}
    assert report['quality_metrics']['model_answer_faithfulness'] == {'passed':0,'total':0}
    assert report['cases'][0]['answer_passed'] is None


@pytest.mark.parametrize('candidate', [
    answer(12,result_id='q0'), answer(12,row=-1), answer(12,column=-1),
    answer(12,row=1), answer(12,column=1), answer(12,row=True), answer(True),
    answer('12 customers'), answer(12.000001), '{"facts":[]}',
    json.dumps({'facts':[],'summary':'999 customers'}),
    json.dumps({'facts':[{'result_id':'q1','row':0,'column':0,'value':12}],'summary':'999 customers'}),
    '{"facts":[],"facts":[]}', '{"facts":[{"result_id":"q1","row":0,"column":0,"value":NaN}]}',
    '```json\n'+answer()+'\n```', '12',
])
def test_bad_answer_contract_falls_back_to_evidence(count_result, candidate):
    assessment = assess_answer(candidate, count_result)
    assert assessment.status == 'rejected'
    assert not assessment.model_verified and assessment.displayed_verified
    assert assessment.facts[0]['value'] == 12


def test_stale_results_cannot_support_final_answer(count_result):
    current = {**count_result, 'result_id':'q2'}
    assessment = assess_answer(answer(result_id='q1'),current)
    assert assessment.reason == 'wrong_result_reference'
    assert assessment.facts[0]['result_id'] == 'q2'


@pytest.mark.parametrize('value,claimed', [(None,None),(0,0),(-12,-12),(0.25,0.25), (Decimal('123.45'),'123.45')])
def test_null_zero_negative_and_decimal_cells_are_distinct(value, claimed):
    result = {'result_id':'q1','columns':['value'],'rows':[[value]],'truncated':False}
    assert assess_answer(answer(claimed),result).model_verified


def test_empty_results_do_not_become_zero_and_partial_data_is_labeled(count_result):
    empty = {**count_result,'rows':[]}
    result = assess_answer('{"facts":[]}',empty)
    assert result.model_verified and 'no rows' in result.answer
    assert not assess_answer(answer(0),empty).model_verified
    partial = assess_answer(answer(),{**count_result,'truncated':True})
    assert 'partial result' in partial.answer and 'complete totals' in partial.answer


def test_result_text_cannot_inject_markdown_images():
    text = '![image](https://example.invalid/private)'
    result = {'result_id':'q1','columns':['label'],'rows':[[text]],'truncated':False}
    assessment = assess_answer(answer(text),result)
    assert assessment.model_verified
    assert '![' not in assessment.answer
    assert '\\!' in assessment.answer
