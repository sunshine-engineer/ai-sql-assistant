"""Key-free reviewer walkthrough: real SQL execution of explicit reviewed plans.

File: assistant/demo_ui.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

from dataclasses import asdict

import streamlit as st

from .answers import deterministic_answer
from .config import DEFAULT_DATABASE
from .connections import open_engine
from .demo import TABLES, build_demo
from .execution import QueryService
from .generation import WorkflowResult, run_workflow
from .plans import AnalysisPlan
from .presentation import render_report
from .tracing import Trace


def render_demo():
    """Render an offline plan walkthrough using real controlled execution on synthetic data."""
    st.subheader("Inspectable retail plan demo")
    st.info(
        "Offline plan demo: synthetic data, explicit plan inputs, real controlled SQL execution. No model calls or API key."
    )
    metric = st.selectbox(
        "Metric",
        [
            "net_revenue_cents",
            "gross_sales_cents",
            "refund_cents",
            "refund_rate",
            "orders",
            "units",
        ],
    )
    month = st.selectbox("Month", ["2026-04", "2026-03", "2026-02", "2026-01"])
    region = st.selectbox("Region", ["North", "South", "East", "West", "All regions"])
    from .demo import next_month

    inputs = {
        "metric": metric,
        "grain": "order" if metric == "orders" else "item",
        "dimensions": [],
        "filters": {} if region == "All regions" else {"region": region},
        "date_range": [month + "-01", next_month(month) + "-01"],
    }
    if st.session_state.get("plan_demo_inputs") != inputs:
        st.session_state["plan_demo_report"] = None
        st.session_state["plan_demo_inputs"] = inputs
    st.json(inputs)
    engine = open_engine("sqlite", path=build_demo(DEFAULT_DATABASE))
    try:
        service = QueryService(engine, tables=TABLES)
        service.retail = True
        if st.button("Run reviewed plan"):
            trace = Trace(model="offline-plan-demo")
            trace.stage("understand")
            trace.stage("generate")
            plan = AnalysisPlan.parse(inputs)
            sql = plan.compile()
            trace.stage("validate")
            inspection = service.preview(sql)
            trace.stage("execute")
            result = {**service.query(sql), "result_id": "q1"}
            trace.stage("summarize")
            answer = deterministic_answer(result)
            report = WorkflowResult(
                answer.answer,
                "answered",
                attempts=[
                    {
                        "result_id": "q1",
                        "plan": asdict(plan),
                        "proposed_sql": sql,
                        "sql": result["sql"],
                        "validation": "passed",
                        "execution": "succeeded",
                        "tables": inspection["tables"],
                        "assumptions": [
                            "Explicit reviewer inputs, canonical metric at approved grain."
                        ],
                        "result": result,
                    }
                ],
                trace=trace.export("answered"),
                context={"sql": result["sql"], "assumptions": []},
                facts=answer.facts,
                answer_validation=answer.summary(),
            )
            st.session_state["plan_demo_report"] = asdict(report)
        report = st.session_state.get("plan_demo_report")
        if report:
            if st.button("Compare with previous month"):
                report = asdict(
                    run_workflow(
                        None,
                        service,
                        [{"role": "user", "content": "Compare that with last month."}],
                        context=report["context"],
                    )
                )
                st.session_state["plan_demo_report"] = report
            st.write(report["answer"])
            render_report(st, report, "offline-demo")
    finally:
        engine.dispose()
