"""Show frozen, sanitized live benchmark evidence without making provider calls.

File: assistant/benchmark_ui.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import json
from collections import Counter

import pandas as pd

from .config import EVALUATION_DIRECTORY

REPORTS = EVALUATION_DIRECTORY / "reports"


def render_benchmarks(st):
    """Display archived benchmark reports without making provider calls.

    Args:
        st: Streamlit-compatible interface used to render the workspace.
    """
    st.subheader("Recorded live benchmark evidence")
    st.warning(
        "Historical runs may be quota-constrained. These synthetic runs are not a production accuracy ranking. Provider failures remain in the denominators. Repeated prompts are not independent samples."
    )
    files = sorted(REPORTS.glob("*.json"))
    if not files:
        st.info("No frozen live benchmark report is bundled yet.")
        return
    chosen = st.selectbox("Recorded run", [p.name for p in files])
    report = json.loads((REPORTS / chosen).read_text())
    st.caption(
        f"Model: {report['model']} · Split: {report['split']} · Repeats: {report['repeats']} · Recorded: {report['timestamp']}"
    )
    st.write(report["scope"])
    if report.get("evaluation_role"):
        st.caption("Evaluation role: " + report["evaluation_role"])
    if report.get("completion", {}).get("stop_reason"):
        st.warning(
            f"Run stopped early: {report['completion']['stop_reason']}. Unattempted cases are excluded from the recorded totals."
        )
    if report.get("scheduling"):
        with st.expander("Quota admission and request budgets"):
            st.json(report["scheduling"])
            st.write("Request deadline in seconds:", report.get("request_seconds"))
    st.dataframe(pd.DataFrame(report["summary"]).T, hide_index=False)
    st.caption(
        "SQL-suite pass requires the same SQL to match references on all three data instances. Consistency requires every planned repetition to be present and passing; incomplete and unattempted cases are separate. Historical report metrics are preserved. Baseline does not generate final answers. Model-answer counts exclude deterministic canonical-plan answers; displayed-answer and canonical-answer columns report those separately. Invalid references are explicit and excluded from SQL scores."
    )
    st.write(
        "Failure categories", dict(Counter(row["error"] for row in report["rows"] if row["error"]))
    )
    rows = [
        {k: v for k, v in row.items() if k not in {"trace", "instances"}} for row in report["rows"]
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.download_button(
        "Download recorded benchmark",
        json.dumps(report, indent=2),
        file_name=chosen,
        mime="application/json",
    )
