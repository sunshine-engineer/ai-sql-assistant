"""Show frozen, sanitized live benchmark evidence without making provider calls."""
from collections import Counter
import json
from pathlib import Path
import pandas as pd

REPORTS = Path(__file__).resolve().parent.parent/'evaluation'/'reports'


def render_benchmarks(st):
    st.subheader('Recorded live benchmark evidence')
    st.warning('These are quota-constrained synthetic pilots, not a production accuracy ranking. Provider failures remain in the denominators. Repeated prompts are not independent samples.')
    files=sorted(REPORTS.glob('*.json'))
    if not files:
        st.info('No frozen live benchmark report is bundled yet.')
        return
    chosen=st.selectbox('Recorded run',[p.name for p in files])
    report=json.loads((REPORTS/chosen).read_text())
    st.caption(f"Model: {report['model']} · Split: {report['split']} · Repeats: {report['repeats']} · Recorded: {report['timestamp']}")
    st.write(report['scope'])
    st.dataframe(pd.DataFrame(report['summary']).T,hide_index=False)
    st.caption('SQL-suite pass requires the same SQL to match references on all three data instances. Baseline does not generate final answers. Answer counts cover only candidates with recorded answer validation.')
    st.write('Failure categories',dict(Counter(row['error'] for row in report['rows'] if row['error'])))
    rows=[{k:v for k,v in row.items() if k not in {'trace','instances'}} for row in report['rows']]
    st.dataframe(pd.DataFrame(rows),hide_index=True)
    st.download_button('Download recorded benchmark',json.dumps(report,indent=2),file_name=chosen,mime='application/json')
