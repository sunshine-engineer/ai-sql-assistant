from contextlib import nullcontext
from unittest.mock import Mock
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from assistant.chat import reset_for_database, context_messages
from assistant.generation import answer_question
from assistant.presentation import submit_turn
from assistant.validation import UnsafeSQL


def test_reset_and_bounded_context():
    state = {}
    reset_for_database(state, ['sqlite', 'a'])
    state['messages'] += [{'role': 'user', 'content': 'x' * 5000}] * 20
    assert len(context_messages(state['messages'])) == 8
    assert len(context_messages(state['messages'])[0]['content']) == 2000
    reset_for_database(state, ['sqlite', 'a'])
    assert len(state['messages']) == 21
    reset_for_database(state, ['sqlite', 'b'])
    assert len(state['messages']) == 1
    state['messages'].append({'role': 'user', 'content': 'hello'})
    reset_for_database(state, ['sqlite', 'b'], clear=True)
    assert len(state['messages']) == 1


def tool_reply(sql='SELECT COUNT(*) FROM students', name='query_database'):
    return AIMessage(content='', tool_calls=[{'name': name, 'args': {'sql': sql}, 'id': 'call1'}])


def test_followup_context_and_controlled_execution():
    model = Mock()
    bound = model.bind_tools.return_value
    bound.invoke.side_effect = [tool_reply(), AIMessage(content='Three students.')]
    service = Mock(dialect='sqlite', description='students')
    service.query.return_value = {'rows': [[3]]}
    messages = [{'role': 'user', 'content': 'Count students'},
                {'role': 'assistant', 'content': 'Three'},
                {'role': 'user', 'content': 'How many scored above 80?'}]
    assert answer_question(model, service, messages) == 'Three students.'
    service.query.assert_called_once_with('SELECT COUNT(*) FROM students')
    history = bound.invoke.call_args.args[0]
    assert any(isinstance(m, HumanMessage) and m.content == 'Count students' for m in history)
    assert any(isinstance(m, ToolMessage) and m.tool_call_id == 'call1' for m in history)


def test_invalid_query_is_returned_as_policy_error():
    model = Mock()
    model.bind_tools.return_value.invoke.side_effect = [tool_reply('DELETE FROM students'), AIMessage(content='Cannot modify.')]
    service = Mock(dialect='sqlite', description='students')
    service.query.side_effect = UnsafeSQL('internal details')
    answer_question(model, service, [])
    history = model.bind_tools.return_value.invoke.call_args.args[0]
    tool = next(m for m in history if isinstance(m, ToolMessage))
    assert 'rejected' in tool.content
    assert 'internal details' not in tool.content


def test_query_budget():
    model = Mock()
    model.bind_tools.return_value.invoke.side_effect = [tool_reply()] * 5
    service = Mock(dialect='sqlite', description='students')
    assert 'budget' in answer_question(model, service, [])
    assert service.query.call_count == 4


def test_unknown_tool_cannot_execute():
    model = Mock()
    model.bind_tools.return_value.invoke.side_effect = [tool_reply(name='sql_db_query'), AIMessage(content='Done')]
    service = Mock(dialect='sqlite', description='students')
    answer_question(model, service, [])
    service.query.assert_not_called()


def test_turn_stored_and_rendered_once(monkeypatch):
    monkeypatch.setattr('assistant.presentation.answer_question', lambda *a: 'Answer')
    st = Mock()
    st.chat_message.side_effect = lambda *a: nullcontext()
    st.spinner.side_effect = lambda *a: nullcontext()
    messages = []
    submit_turn(st, Mock(), Mock(), messages, 'Create a summary')
    assert messages == [{'role': 'user', 'content': 'Create a summary'},
                        {'role': 'assistant', 'content': 'Answer'}]
    assert [call.args[0] for call in st.write.call_args_list] == ['Create a summary', 'Answer']


def test_errors_do_not_leak_secrets(monkeypatch):
    def fail(*args):
        raise RuntimeError('password=secret')
    monkeypatch.setattr('assistant.presentation.answer_question', fail)
    st = Mock()
    st.chat_message.side_effect = lambda *a: nullcontext()
    st.spinner.side_effect = lambda *a: nullcontext()
    messages = []
    submit_turn(st, Mock(), Mock(), messages, 'hello')
    assert 'secret' not in messages[-1]['content']


def test_real_sqlite_through_model_tool_boundary(tmp_path):
    import sqlite3
    from assistant.connections import open_engine
    from assistant.execution import QueryService
    path = tmp_path / 'student.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE students (marks INTEGER)')
        db.executemany('INSERT INTO students VALUES (?)', [(90,), (80,)])
    engine = open_engine('sqlite', path=path)
    try:
        service = QueryService(engine)
        model = Mock()
        model.bind_tools.return_value.invoke.side_effect = [
            tool_reply('DELETE FROM students'),
            tool_reply('SELECT COUNT(*) FROM students'),
            AIMessage(content='Two students; no changes made.'),
        ]
        assert answer_question(model, service, []) == 'Two students; no changes made.'
        history = model.bind_tools.return_value.invoke.call_args.args[0]
        results = [m.content for m in history if isinstance(m, ToolMessage)]
        assert 'rejected' in results[0]
        assert '"rows": [[2]]' in results[1]
        assert service.query('SELECT COUNT(*) FROM students')['rows'] == [[2]]
    finally:
        engine.dispose()
