"""Render one turn, its query evidence and redacted operational trace."""
from dataclasses import asdict
import json
import pandas as pd
from .charts import chart_data
from .generation import run_workflow


def render_report(st, report, key):
    validation = report.get('answer_validation', {})
    if validation.get('status') == 'rejected':
        st.warning('Model answer rejected: ' + validation['reason'] + '. The displayed values come from the executed result.')
    attempts = report.get('attempts', [])
    if attempts:
        with st.expander('Query inspection', expanded=True):
            for index, attempt in enumerate(attempts, 1):
                st.caption(f"Attempt {index}: validation {attempt['validation']}; execution {attempt['execution']}")
                if attempt.get('plan'):
                    st.write('Proposed analysis plan (inspect metric, filters and grain):')
                    st.json(attempt['plan'])
                if attempt.get('proposed_sql'):
                    st.code(attempt['proposed_sql'], language='sql')
                if attempt.get('sql') and attempt.get('sql') != attempt.get('proposed_sql'):
                    st.caption('Validated SQL, including the enforced row limit:')
                    st.code(attempt['sql'], language='sql')
                st.write('Referenced tables:', attempt.get('tables', []))
                st.write('Assumptions (model supplied unless noted):', attempt.get('assumptions', []))
                if attempt.get('error'):
                    st.error(attempt['error'])
            results = [attempt['result'] for attempt in attempts if attempt.get('result')]
            if results:
                result = report.get('comparison') or results[-1]
                if result.get('error'):
                    st.warning(result['error'])
                frame = pd.DataFrame(result['rows'], columns=result['columns'])
                if not frame.columns.is_unique:
                    used, names = set(), []
                    for column in frame.columns:
                        name, suffix = str(column), 1
                        while name in used:
                            suffix += 1
                            name = f'{column} ({suffix})'
                        used.add(name)
                        names.append(name)
                    frame.columns = names
                    st.caption('Duplicate column names are suffixed for display and CSV; cell values are unchanged.')
                st.caption(f"Returned rows: {len(frame)} · Truncated: {result['truncated']}")
                st.caption('Result reference: ' + result.get('result_id', 'unavailable') + '; row and column indices are zero-based.')
                st.dataframe(frame, hide_index=False)
                st.download_button('Download result CSV', frame.to_csv(index=False),
                                   file_name='query-result.csv', mime='text/csv', key=f'csv-{key}')
                chart = chart_data(result)
                if chart:
                    st.caption(f"Chart from executed columns: {chart['x']} / {chart['y']} (original units)")
                    (st.line_chart if chart['kind'] == 'line' else st.bar_chart)(chart['frame'])
                if result['truncated']:
                    st.warning('The result is partial. Narrow the query before drawing conclusions.')
    trace = report.get('trace', {})
    if trace:
        with st.expander('Operational trace (redacted)'):
            st.json(trace)
            st.download_button('Download trace JSON', json.dumps(trace, indent=2),
                               file_name='trace.json', mime='application/json', key=f'trace-{key}')
        st.metric('Response Time', f"{trace['duration_ms']/1000:.2f}s")


def submit_turn(st, model, service, messages, question, context=None):
    messages.append({'role': 'user', 'content': question})
    with st.chat_message('user'):
        st.write(question)
    with st.chat_message('assistant'):
        try:
            with st.spinner('Understanding → clarifying → generating → validating → executing → summarizing...'):
                result = run_workflow(model, service, messages, context=context)
            report = asdict(result)
            answer = result.answer
        except Exception:
            report = {}
            answer = 'Unable to complete this request. Check the connection and model settings, then retry.'
        messages.append({'role': 'assistant', 'content': answer, 'report': report})
        # Keep query evidence for eight answers; older plain conversation remains available.
        for message in messages[:-16]:
            message.pop('report', None)
        st.write(answer)
        render_report(st, report, key=str(len(messages)))
        return report.get('context') or context or {}
