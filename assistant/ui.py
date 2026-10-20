"""Streamlit composition: collect settings, manage the chat, render responses."""
import streamlit as st

from .chat import reset_for_database
from .config import AppConfig, DEFAULT_DATABASE, DEFAULT_MODEL
from .presentation import submit_turn
from .runtime import application_session


def read_sidebar() -> AppConfig:
    kind = st.sidebar.radio('Database', ['sqlite', 'mysql', 'postgres'])
    settings = {}
    schema = None
    if kind == 'sqlite':
        settings['path'] = str(DEFAULT_DATABASE)
    else:
        settings['host'] = st.sidebar.text_input('Host')
        settings['port'] = st.sidebar.text_input(
            'Port', value='5432' if kind == 'postgres' else '3306',
        )
        settings['user'] = st.sidebar.text_input('Read-only username')
        settings['password'] = st.sidebar.text_input('Database password', type='password')
        settings['database'] = st.sidebar.text_input('Database name')
        if kind == 'postgres':
            schema = st.sidebar.text_input('Approved schema', value='genai')
        st.sidebar.caption('Use a dedicated SELECT-only account, never the data-loading account.')
    config = AppConfig(kind=kind, settings=settings, schema=schema)
    reset_for_database(
        st.session_state, config.database_identity,
        clear=st.sidebar.button('Clear message history'),
    )
    config.api_key = st.sidebar.text_input('Groq API Key', type='password')
    config.model_name = st.sidebar.text_input('Groq model', value=DEFAULT_MODEL)
    return config


def render_history(messages):
    for message in messages:
        with st.chat_message(message['role']):
            st.write(message['content'])


def main():
    st.set_page_config(page_title='AI SQL Assistant', page_icon='🤖', layout='wide')
    st.title('🤖 AI SQL Assistant')
    st.caption('Ask questions about approved tables. Responses appear after processing.')
    config = read_sidebar()
    if not config.ready:
        st.info('Provide an API key and complete connection settings.')
        st.stop()
    try:
        with application_session(config) as (service, model):
            names = sorted({name for _, name in service.allowed})
            st.sidebar.caption('Approved tables: ' + ', '.join(names))
            render_history(st.session_state.messages)
            question = st.chat_input('Ask about the database', max_chars=2000)
            if question:
                submit_turn(st, model, service, st.session_state.messages, question)
    except Exception:
        st.error('Connection setup failed. Check the database, driver, schema and model settings.')
