"""Streamlit composition: collect settings, manage the chat, render responses."""
import os
import streamlit as st

from .chat import reset_for_database
from .config import AppConfig, DEFAULT_DATABASE, DEFAULT_MODEL
from .presentation import submit_turn, render_report
from .business import CONTRACT
from .runtime import application_session
from .budgets import BudgetExceeded


def read_sidebar() -> AppConfig:
    if os.environ.get('ASSISTANT_DEPLOYMENT') == 'hosted':
        from .access import hosted_config
        if not getattr(st.user, 'is_logged_in', False):
            st.sidebar.button('Sign in', on_click=st.login)
            st.info('Sign in to access your approved database views.')
            st.stop()
        try:
            principal = {**dict(st.user), 'is_logged_in':True}
            grants = st.secrets.to_dict().get('database_access', {})
            config = hosted_config(principal, grants, st.secrets['provider']['api_key'],
                                   st.secrets['provider'].get('model', DEFAULT_MODEL))
        except (KeyError, PermissionError):
            st.error('No current approved database access is configured for this identity.')
            st.sidebar.button('Sign out', on_click=st.logout)
            st.stop()
        reset_for_database(st.session_state, config.database_identity,
                           clear=st.sidebar.button('Clear message history'))
        st.sidebar.button('Sign out', on_click=st.logout)
        return config
    reviewer = os.environ.get('ASSISTANT_DEPLOYMENT') == 'reviewer'
    kind = st.sidebar.radio('Database', ['sqlite'] if reviewer else ['sqlite', 'mysql', 'postgres'])
    if reviewer:
        st.sidebar.caption('Reviewer mode: bundled synthetic data only.')
    settings = {}
    schema = None
    if kind == 'sqlite':
        dataset = st.sidebar.selectbox('Demo dataset', ['Retail analytics', 'Legacy students'])
        path = DEFAULT_DATABASE if dataset == 'Retail analytics' else DEFAULT_DATABASE.parent.parent / 'student.db'
        settings['path'] = str(path)
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
        tls_ca = st.sidebar.text_input('Trusted CA certificate path (optional for local use)')
        if tls_ca:
            settings['tls_ca'] = tls_ca
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
    for index, message in enumerate(messages):
        with st.chat_message(message['role']):
            st.write(message['content'])
            if message.get('report'):
                render_report(st, message['report'], key=str(index+1))


def main():
    st.set_page_config(page_title='AI SQL Assistant', page_icon='🤖', layout='wide')
    st.title('🤖 AI SQL Assistant')
    st.caption('Ask questions about approved tables. Responses appear after processing.')
    workspace = st.sidebar.selectbox('Workspace', ['Chat', 'Evaluation', 'Plan demo', 'Benchmarks'])
    if workspace == 'Benchmarks':
        from .benchmark_ui import render_benchmarks
        render_benchmarks(st)
        return
    if workspace == 'Plan demo':
        from .demo_ui import render_demo
        render_demo()
        return
    if workspace == 'Evaluation':
        from .evaluation_ui import render_evaluation
        render_evaluation(st)
        return
    config = read_sidebar()
    if not config.ready:
        st.info('Provide an API key and complete connection settings.')
        st.stop()
    try:
        with application_session(config) as (service, model):
            names = sorted({name for _, name in service.allowed})
            st.sidebar.caption('Approved tables: ' + ', '.join(names))
            if service.retail:
                st.sidebar.caption('Synthetic data: January–April 2026; reporting as of May 1, 2026.')
                with st.sidebar.expander('Business definitions'):
                    st.json(CONTRACT)
            render_history(st.session_state.messages)
            question = st.chat_input('Ask about the database', max_chars=2000)
            if question:
                st.session_state['analysis_context'] = submit_turn(
                    st, model, service, st.session_state.messages, question,
                    context=st.session_state.get('analysis_context'),
                )
    except BudgetExceeded:
        st.warning('Request time budget reached during setup. Select a smaller approved schema and retry.')
    except Exception:
        st.error('Connection setup failed. Check the database, driver, schema and model settings.')
