"""Regression checks for final review.

File: tests/test_final_review.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage

from assistant.benchmark import benchmark, case_completion, suites
from assistant.generation import run_workflow
from assistant.plan_intent import PlanIntentError, requires_refund_plan, validate_plan_intent
from assistant.plans import AnalysisPlan


def plan(**changes):
    """Build a supported plan payload with test-specific overrides.

    Args:
        **changes: Scripted positional inputs.

    Returns:
        Scripted result or helper object used by the regression assertions.
    """
    return AnalysisPlan.parse(
        {
            "metric": "net_revenue_cents",
            "grain": "item",
            "dimensions": [],
            "filters": {"region": "South"},
            "date_range": ["2026-03-01", "2026-04-01"],
            **changes,
        }
    )


@pytest.mark.parametrize(
    "filters",
    [
        "for South and North",
        "for South or North",
        "for both South and North",
        "for Hardware and Software",
        "for North or Hardware",
        "excluding South",
        "except South",
        "not for South",
        "where NOT (region = 'South')",
        "for regions other than South",
        "without South",
        "for neither North nor South",
        "where quantity > 2",
        "for orders with status pending",
        "for customer 3",
    ],
)
def test_unsupported_filter_shapes_cannot_execute_partial_canonical_plan(filters):
    """Verify unsupported filter shapes cannot execute partial canonical plan.

    Args:
        filters: Parametrized filters for this regression case.
    """
    with pytest.raises(PlanIntentError) as exc:
        validate_plan_intent(plan(), "March 2026 net revenue " + filters)
    assert "query_database" in exc.value.expected["route"]


def test_supported_conjunction_between_different_dimensions_still_works():
    """Verify supported conjunction between different dimensions still works."""
    validate_plan_intent(
        plan(filters={"region": "South", "category": "Hardware"}),
        "March 2026 net revenue for South and Hardware",
    )


def test_complex_refund_filters_can_use_flexible_sql_instead_of_repair_loop():
    """Verify complex refund filters can use flexible sql instead of repair loop."""
    assert not requires_refund_plan("Refund ratio excluding South")
    assert requires_refund_plan("What is the overall refund-to-gross-sales ratio?")


def test_multiregion_routes_before_db_then_executes_full_requested_filter(retail, monkeypatch):
    """Verify multiregion routes before db then executes full requested filter.

    Args:
        retail: Temporary real SQLite retail service fixture.
        monkeypatch: Pytest helper for reversible runtime substitutions.
    """
    question = "Show March 2026 net revenue in cents for South and North."
    args = {
        "metric": "net_revenue_cents",
        "grain": "item",
        "dimensions": [],
        "filters": {"region": "South"},
        "date_range": ["2026-03-01", "2026-04-01"],
    }
    sql = "SELECT SUM(net_revenue_cents) FROM sales_facts WHERE region IN ('South','North') AND order_date >= '2026-03-01' AND order_date < '2026-04-01'"
    model = Mock(model_name="scripted")
    model.bind_tools.return_value.invoke.side_effect = [
        AIMessage(
            content="", tool_calls=[{"name": "execute_analysis_plan", "args": args, "id": "bad"}]
        ),
        AIMessage(
            content="", tool_calls=[{"name": "query_database", "args": {"sql": sql}, "id": "full"}]
        ),
        AIMessage(content='{"facts":[{"result_id":"q2","row":0,"column":0,"value":644300}]}'),
    ]
    original = retail.query
    executed = []

    def observe(sql, **kw):
        """Record SQL submitted by the workflow, then forward to the original query method.

        Args:
            sql: Untrusted SQL text to validate before any execution.
            **kw: Scripted keyword inputs.

        Returns:
            Scripted result or helper object used by the regression assertions.
        """
        executed.append(sql)
        return original(sql, **kw)

    monkeypatch.setattr(retail, "query", observe)
    report = run_workflow(model, retail, [{"role": "user", "content": question}])
    assert report.outcome == "answered" and report.result["rows"] == [[644300]]
    assert len(executed) == 1 and "'North'" in executed[0]
    assert report.attempts[0]["execution"] == "not_run" and report.trace["retries"] == 1


def test_unattempted_partial_failed_and_complete_cases_are_separate():
    """Verify unattempted partial failed and complete cases are separate."""
    cases = [{"id": x} for x in "ABCD"]
    rows = [
        {"id": "B", "repeat": 1, "passed": True},
        {"id": "C", "repeat": 1, "passed": True},
        {"id": "C", "repeat": 2, "passed": False},
        {"id": "D", "repeat": 1, "passed": True},
        {"id": "D", "repeat": 2, "passed": True},
    ]
    assert case_completion(rows, cases, 2) == dict(
        consistent_cases=1, completed_cases=2, incomplete_cases=1, unattempted_cases=1
    )
    assert case_completion([], cases, 2) == dict(
        consistent_cases=0, completed_cases=0, incomplete_cases=0, unattempted_cases=4
    )


def test_duplicate_repeat_does_not_replace_a_missing_repeat():
    """Verify duplicate repeat does not replace a missing repeat."""
    assert (
        case_completion([{"id": "A", "repeat": 1, "passed": True}] * 2, [{"id": "A"}], 2)[
            "incomplete_cases"
        ]
        == 1
    )


def test_provider_stop_reports_per_approach_completion():
    """Verify provider stop reports per approach completion."""
    from assistant.diagnostics import SyntheticSuite

    model = Mock(model_name="failure")
    model.invoke.side_effect = ConnectionError()
    model.bind_tools.return_value.invoke.side_effect = ConnectionError()
    with SyntheticSuite() as owner:
        report = benchmark(model, owner.services, suites()["heldout"][:2], repeats=2)
    assert report["completion"]["recorded_attempts"] == 3
    for summary in report["summary"].values():
        assert summary["consistent_cases"] == 0
        assert summary["completed_cases"] == 0
        assert summary["incomplete_cases"] + summary["unattempted_cases"] == 2


def test_prospective_suite_is_opt_in_and_reference_rows_are_frozen():
    """Verify prospective suite is opt in and reference rows are frozen."""
    from assistant.diagnostics import SyntheticSuite
    from assistant.evaluation import same_results

    assert "prospective" not in suites()
    cases = suites(include_prospective=True)["prospective"]
    assert len(cases) == 8
    old_questions = {c["question"] for group in suites().values() for c in group}
    assert not old_questions.intersection(c["question"] for c in cases)
    with SyntheticSuite() as owner:
        for case in cases:
            if case["expected_outcome"] == "answered":
                for name, service in owner.services.items():
                    assert same_results(
                        service.query(case["gold_sql"]),
                        {**case, **case["expected_by_instance"][name]},
                    )


def test_prospective_gold_answers_do_not_enter_either_model_prompt():
    """Verify prospective gold answers do not enter either model prompt."""
    from assistant.benchmark import one_shot
    from assistant.diagnostics import SyntheticSuite

    case = suites(include_prospective=True)["prospective"][0]
    model = Mock(model_name="scripted")
    model.invoke.return_value = AIMessage(content='{"sql":"SELECT COUNT(*) FROM orders"}')
    model.bind_tools.return_value.invoke.return_value = AIMessage(content="Please clarify")
    with SyntheticSuite() as owner:
        one_shot(model, owner.services["base"], case["question"])
        run_workflow(model, owner.services["base"], [{"role": "user", "content": case["question"]}])
    for invoke in (model.invoke, model.bind_tools.return_value.invoke):
        messages = invoke.call_args.args[0]
        text = " ".join(str(m.content) for m in messages)
        assert case["gold_sql"] not in text
        assert "expected_by_instance" not in text
        assert case["question"] in text
