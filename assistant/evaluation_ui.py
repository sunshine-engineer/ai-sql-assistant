"""Evaluation dashboard distinguishes fixture checks from actual model runs."""
import json
import pandas as pd
from .config import AppConfig, DEFAULT_DATABASE, DEFAULT_MODEL
from .connections import open_engine
from .demo import build_demo, TABLES
from .evaluation import evaluate, load_cases
from .execution import QueryService
from .runtime import application_session


def render_evaluation(st):
    st.subheader('Retail evaluation: 50 curated cases')
    st.write('Reference checks validate frozen expected results and deterministic controls. Live runs separately measure generated-query results and result-referenced answer facts. Unrestricted prose and remote database model quality are not graded.')
    cases = load_cases()
    st.dataframe(pd.DataFrame([{k: c[k] for k in ['id', 'category', 'question', 'expected_outcome']} for c in cases]), hide_index=True)
    mode = st.radio('Evaluation mode', ['Reference fixture checks (offline)', 'Live Groq model'])
    key = st.sidebar.text_input('Evaluation Groq API Key', type='password')
    model = st.sidebar.text_input('Evaluation model', value=DEFAULT_MODEL)
    count = st.number_input('Cases per run', min_value=1, max_value=50, value=5 if mode == 'Live Groq model' else 50)
    offset = st.number_input('Starting case index (zero based)', min_value=0, max_value=49, value=0)
    st.caption('Live runs consume provider quota. Use small batches on a free tier; failures and unavailable token usage remain explicit.')
    if st.button('Run evaluation'):
        if mode == 'Live Groq model' and not key:
            st.error('Provide a Groq API key for a live run.')
        else:
            selected = cases[offset:offset+count]
            with st.spinner('Evaluating selected cases...'):
                if mode == 'Live Groq model':
                    config = AppConfig('sqlite', {'path': str(DEFAULT_DATABASE)}, api_key=key, model_name=model)
                    try:
                        with application_session(config) as (service, llm):
                            report = evaluate(service, model=llm, cases=selected)
                    except Exception:
                        st.error('Evaluation setup failed. Check provider settings.')
                        return
                else:
                    build_demo(DEFAULT_DATABASE)
                    engine = open_engine('sqlite', path=DEFAULT_DATABASE)
                    try:
                        report = evaluate(QueryService(engine, tables=TABLES), cases=selected)
                    finally:
                        engine.dispose()
            st.session_state['evaluation_report'] = report
    report = st.session_state.get('evaluation_report')
    if report:
        st.info('Mode: ' + report['mode'] + '. Results below describe only this selected batch.')
        for kind, metric in report['metrics'].items():
            label = 'End-to-end answers' if report['mode'] == 'live_model' and kind == 'answered' else kind
            st.metric(label, f"{metric['passed']} / {metric['total']}")
        for label, metric in report.get('quality_metrics', {}).items():
            value = f"{metric['passed']} / {metric['total']}" if metric['total'] else 'Not evaluated'
            st.metric(label.replace('_', ' ').capitalize(), value)
        st.write('Latency in milliseconds', report['latency_ms'])
        st.write('Observed provider calls:', report['model_calls'], 'SQL repairs:', report['sql_repairs'])
        table = pd.DataFrame([{k: v for k, v in row.items() if k != 'trace'} for row in report['cases']])
        st.dataframe(table, hide_index=True)
        scores = table.groupby('category')['passed'].mean()
        st.bar_chart(scores)
        st.download_button('Download evaluation JSON', json.dumps(report, indent=2),
                           file_name='evaluation.json', mime='application/json')
