"""Render one turn and persist each message once."""
from time import perf_counter
from .generation import answer_question


def submit_turn(st, model, service, messages, question):
    messages.append({'role': 'user', 'content': question})
    with st.chat_message('user'):
        st.write(question)
    with st.chat_message('assistant'):
        started = perf_counter()
        try:
            with st.spinner('Querying the database...'):
                answer = answer_question(model, service, messages)
        except Exception:
            answer = 'Unable to complete this request. Check the connection and model settings, then retry.'
        messages.append({'role': 'assistant', 'content': answer})
        st.write(answer)
        st.metric('Response Time', f'{perf_counter() - started:.2f}s')
