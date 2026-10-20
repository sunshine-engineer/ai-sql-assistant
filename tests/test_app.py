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
