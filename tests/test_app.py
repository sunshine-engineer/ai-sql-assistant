from unittest.mock import Mock
from streamlit.testing.v1 import AppTest
from langchain_core.messages import AIMessage


def test_start_without_credentials():
    app = AppTest.from_file('app.py').run()
    assert not app.exception
    assert 'Provide an API key' in app.info[0].value


def test_chat_and_database_reset(monkeypatch):
    model = Mock()
    model.bind_tools.return_value.invoke.return_value = AIMessage(content='Summary of students')
    monkeypatch.setattr('langchain_groq.ChatGroq', lambda **kwargs: model)
    app = AppTest.from_file('app.py').run()
    app.sidebar.text_input[0].set_value('offline-test-key').run()
    assert not app.exception
    app.chat_input[0].set_value('Create a summary of students').run()
    assert not app.exception
    messages = app.session_state['messages']
    assert sum(m['role'] == 'user' for m in messages) == 1
    assert len(app.chat_message) == 3  # greeting, question, answer
    app.sidebar.radio[0].set_value('postgres').run()
    assert not app.exception
    assert len(app.session_state['messages']) == 1


def test_evaluation_dashboard_runs_offline_without_api_key():
    app = AppTest.from_file('app.py').run()
    app.sidebar.selectbox[0].set_value('Evaluation').run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 50
    app.button[0].click().run()
    assert not app.exception
    report = app.session_state['evaluation_report']
    assert report['mode'] == 'reference_fixture'
    assert len(report['cases']) == 50 and all(row['passed'] for row in report['cases'])


def test_inspection_and_contextual_comparison_in_streamlit(monkeypatch):
    sql = "SELECT SUM(net_revenue_cents) AS net_cents FROM sales_facts WHERE order_date >= '2026-04-01' AND order_date < '2026-05-01' AND region='North'"
    model = Mock(model_name='fixture/provider')
    model.bind_tools.return_value.invoke.side_effect = [
        AIMessage(content='', tool_calls=[{'name':'query_database', 'args':{'sql':sql,'assumptions':['Net revenue, USD cents.']},'id':'demo1'}]),
        AIMessage(content='See the executed net revenue total.'),
    ]
    monkeypatch.setattr('langchain_groq.ChatGroq', lambda **kwargs: model)
    app = AppTest.from_file('app.py').run()
    app.sidebar.text_input[0].set_value('offline-test-key').run()
    app.chat_input[0].set_value('Show April 2026 net revenue for North.').run()
    assert not app.exception
    assert any('LIMIT 201' in block.value for block in app.code)
    assert len(app.dataframe[-1].value) == 1
    app.chat_input[0].set_value('Compare that with last month.').run()
    assert not app.exception
    comparison = app.dataframe[-1].value
    assert comparison['period'].tolist() == ['2026-03','2026-04']
    assert model.bind_tools.return_value.invoke.call_count == 2
    assert "region = 'North'" in app.session_state['analysis_context']['sql']
    app.sidebar.radio[0].set_value('postgres').run()
    assert app.session_state['analysis_context'] == {}


def test_duplicate_result_columns_are_inspectable(monkeypatch):
    model = Mock(model_name='fixture/provider')
    model.bind_tools.return_value.invoke.side_effect = [
        AIMessage(content='', tool_calls=[{'name':'query_database','args':{'sql':'SELECT 1 AS value, 2 AS value'},'id':'duplicate'}]),
        AIMessage(content='See both values.'),
    ]
    monkeypatch.setattr('langchain_groq.ChatGroq', lambda **kwargs: model)
    app = AppTest.from_file('app.py').run()
    app.sidebar.text_input[0].set_value('offline-test-key').run()
    app.chat_input[0].set_value('Show both values.').run()
    assert not app.exception and not app.error
    assert app.dataframe[-1].value.columns.tolist() == ['value', 'value (2)']
    assert app.dataframe[-1].value.values.tolist() == [[1,2]]


def test_false_answer_and_changed_followup_in_streamlit(monkeypatch):
    model = Mock(model_name='fixture/provider')
    model.bind_tools.return_value.invoke.side_effect = [
        AIMessage(content='', tool_calls=[{'name':'query_database', 'args':{'sql':'SELECT COUNT(*) AS customers FROM customers'}, 'id':'count'}]),
        AIMessage(content='999 customers'),
    ]
    monkeypatch.setattr('langchain_groq.ChatGroq', lambda **kwargs: model)
    app = AppTest.from_file('app.py').run()
    app.sidebar.text_input[0].set_value('offline-test-key').run()
    app.chat_input[0].set_value('How many customers are there?').run()
    assert not app.exception
    answer = app.session_state['messages'][-1]['content']
    assert '999' not in answer and '12 [q1:r0:c0]' in answer
    assert any('Model answer rejected' in warning.value for warning in app.warning)
    app.chat_input[0].set_value('Compare that with last month, but use South instead of North').run()
    assert not app.exception
    assert 'additional instructions' in app.session_state['messages'][-1]['content']
    assert model.bind_tools.return_value.invoke.call_count == 2


def test_key_free_plan_demo_and_comparison():
    app=AppTest.from_file('app.py').run()
    app.sidebar.selectbox[0].set_value('Plan demo').run()
    assert not app.exception
    assert 'No model calls' in app.info[0].value
    app.button[0].click().run()
    assert not app.exception
    report=app.session_state['plan_demo_report']
    assert report['attempts'][0]['plan']['metric']=='net_revenue_cents'
    assert report['answer_validation']['displayed_verified']
    assert report['trace']['model_calls']==[]
    app.button[1].click().run()
    assert not app.exception
    report=app.session_state['plan_demo_report']
    assert report['comparison']['rows'][0][0]=='2026-03'
    assert report['comparison']['rows'][1][0]=='2026-04'


def test_hosted_chat_requires_login(monkeypatch):
    monkeypatch.setenv('ASSISTANT_DEPLOYMENT','hosted')
    app=AppTest.from_file('app.py').run()
    assert not app.exception
    assert any(button.label=='Sign in' for button in app.sidebar.button)
    assert any('Sign in' in info.value for info in app.info)
    assert not app.chat_input


def test_frozen_live_benchmark_dashboard_without_credentials():
    app=AppTest.from_file('app.py').run()
    app.sidebar.selectbox[0].set_value('Benchmarks').run()
    assert not app.exception
    assert any('quota-constrained' in warning.value for warning in app.warning)
    assert not app.text_input
    assert len(app.dataframe)>=2


def test_canonical_chat_finishes_without_second_model_call(monkeypatch):
    model=Mock(model_name='fixture/provider')
    model.bind_tools.return_value.invoke.side_effect=[
        AIMessage(content='',tool_calls=[{'name':'execute_analysis_plan','args':{
            'metric':'net_revenue_cents','grain':'item','dimensions':[],
            'filters':{'region':'South'},'date_range':['2026-03-01','2026-04-01']},'id':'plan'}]),
        RuntimeError('unnecessary summarizer would fail'),
    ]
    monkeypatch.setattr('langchain_groq.ChatGroq',lambda **kwargs:model)
    app=AppTest.from_file('app.py').run()
    app.sidebar.text_input[0].set_value('offline-test-key').run()
    app.chat_input[0].set_value('Give March 2026 net revenue in cents for South.').run()
    assert not app.exception
    assert app.dataframe[-1].value.columns.tolist()==['net_revenue_cents']
    report=app.session_state['messages'][-1]['report']
    assert report['answer_validation']['method']=='canonical_plan'
    assert model.bind_tools.return_value.invoke.call_count==1
