"""Streamlit entry point. Run with: streamlit run app.py."""
from pathlib import Path
import streamlit as st
from langchain_groq import ChatGroq
from assistant.chat import reset_for_database
from assistant.connections import open_engine
from assistant.execution import QueryService
from assistant.presentation import submit_turn

st.set_page_config(page_title='AI SQL Assistant', page_icon='🤖', layout='wide')
st.title('🤖 AI SQL Assistant')
st.caption('Ask questions about approved tables. Responses appear after processing.')
kind = st.sidebar.radio('Database', ['sqlite', 'mysql', 'postgres'])
settings = {}
schema = None
if kind == 'sqlite':
    settings['path'] = str(Path(__file__).parent / 'student.db')
else:
    settings['host'] = st.sidebar.text_input('Host')
    settings['port'] = st.sidebar.text_input('Port', value='5432' if kind == 'postgres' else '3306')
    settings['user'] = st.sidebar.text_input('Read-only username')
    settings['password'] = st.sidebar.text_input('Database password', type='password')
    settings['database'] = st.sidebar.text_input('Database name')
    if kind == 'postgres':
        schema = st.sidebar.text_input('Approved schema', value='genai')
    st.sidebar.caption('Use a dedicated SELECT-only account, never the data-loading account.')
reset_for_database(st.session_state, [kind, settings, schema],
                   clear=st.sidebar.button('Clear message history'))
key = st.sidebar.text_input('Groq API Key', type='password')
model_name = st.sidebar.text_input('Groq model', value='qwen/qwen3.6-27b')
if not key or any(not value for value in settings.values()):
    st.info('Provide an API key and complete connection settings.')
    st.stop()
engine = None
try:
    engine = open_engine(kind, **settings)
    service = QueryService(engine, schema=schema)
    st.sidebar.caption('Approved tables: ' + ', '.join(sorted({name for _, name in service.allowed})))
    model = ChatGroq(api_key=key, model=model_name, temperature=0,
                     streaming=False, timeout=20, max_retries=0, max_tokens=1500)
    for message in st.session_state.messages:
        with st.chat_message(message['role']):
            st.write(message['content'])
    question = st.chat_input('Ask about the database', max_chars=2000)
    if question:
        submit_turn(st, model, service, st.session_state.messages, question)
except Exception:
    st.error('Connection setup failed. Check the database, driver, schema and model settings.')
finally:
    if engine is not None:
        engine.dispose()
