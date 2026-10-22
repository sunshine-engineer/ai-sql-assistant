"""Regression cases from review: intent changes, date polarity and courtesy phrasing.

File: tests/test_comparison_and_dates.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

from unittest.mock import Mock

import pytest

from assistant.business import preflight
from assistant.dates import requested_dates
from assistant.followups import can_reuse_comparison, comparison_queries
from assistant.generation import run_workflow

SQL = "SELECT SUM(net_revenue_cents) AS net FROM sales_facts WHERE order_date >= '2026-04-01' AND order_date < '2026-05-01' AND region='North'"


@pytest.mark.parametrize(
    "question",
    [
        "Compare that with last month, but use South instead of North.",
        "Compare that with last month but use gross sales instead of net revenue.",
        "Compare that with last month and remove the region filter.",
        "Compare that with last month for Software only.",
        "Compare that with last month, grouped by category.",
        "Compare that for South with last month.",
        "Compare that with last month and also include February.",
        "Do not compare that with last month.",
    ],
)
def test_changed_comparison_intent_never_reuses_stale_sql(retail, question):
    """Verify changed comparison intent never reuses stale sql.

    Args:
        retail: Temporary real SQLite retail service fixture.
        question: Current natural-language analysis request.
    """
    service = Mock(wraps=retail)
    service.dialect = retail.dialect
    model = Mock()
    result = run_workflow(
        model, service, [{"role": "user", "content": question}], context={"sql": SQL}
    )
    assert result.outcome == "clarify"
    assert "changes or additional instructions" in result.answer
    service.query.assert_not_called()
    service.preview.assert_not_called()
    model.bind_tools.assert_not_called()
    assert result.attempts == []


@pytest.mark.parametrize(
    "question",
    [
        "Compare that with last month.",
        "Please compare it to the previous month!",
        "Could you compare this against last month, please?",
        "Can you please compare that with last month?",
    ],
)
def test_standalone_comparison_intents(question):
    """Verify standalone comparison intents.

    Args:
        question: Current natural-language analysis request.
    """
    assert can_reuse_comparison(question)


@pytest.mark.parametrize(
    "where",
    [
        "NOT (order_date >= '2026-04-01' AND order_date < '2026-05-01')",
        "NOT NOT (order_date >= '2026-04-01' AND order_date < '2026-05-01')",
        "order_date >= '2026-04-01' OR order_date < '2026-05-01'",
        "order_date >= '2026-04-01' AND NOT order_date < '2026-05-01'",
        "order_date >= '2026-04-01' AND other.order_date < '2026-05-01'",
        "a.order_date >= '2026-04-01' AND b.order_date < '2026-05-01'",
        "DATE(order_date) >= '2026-04-01' AND order_date < '2026-05-01'",
        "CASE WHEN order_date >= '2026-04-01' THEN 1 ELSE 0 END = 1 AND order_date < '2026-05-01'",
        "order_date >= '2026-04-01' AND order_date < '2026-05-01' AND order_date <> '2026-04-15'",
        "order_date >= '2026-04-01' AND order_date >= '2026-04-01' AND order_date < '2026-05-01'",
        "order_date >= '2026-04-01' AND order_date < '2026-06-01'",
        "order_date > '2026-04-01' AND order_date < '2026-05-01'",
        "order_date >= '2026-04-02' AND order_date < '2026-05-01'",
        "order_date >= '2026-13-01' AND order_date < '2026-14-01'",
        "order_date >= '0000-04-01' AND order_date < '0000-05-01'",
    ],
)
@pytest.mark.parametrize("dialect", ["sqlite", "postgres", "mysql"])
def test_only_positive_same_column_canonical_month_is_rewritten(where, dialect):
    """Verify only positive same column canonical month is rewritten.

    Args:
        where: Parametrized where for this regression case.
        dialect: SQLGlot dialect name: sqlite, postgres, or mysql.
    """
    assert (
        comparison_queries({"sql": "SELECT COUNT(*) FROM sales_facts WHERE " + where}, dialect)
        is None
    )


@pytest.mark.parametrize("dialect", ["sqlite", "postgres", "mysql"])
def test_qualified_parenthesized_bounds_preserve_other_filters(dialect):
    """Verify qualified parenthesized bounds preserve other filters.

    Args:
        dialect: SQLGlot dialect name: sqlite, postgres, or mysql.
    """
    sql = "SELECT SUM(f.net_revenue_cents) AS net FROM sales_facts f WHERE (f.order_date >= '2026-04-01') AND ((f.order_date < '2026-05-01') AND f.region='North')"
    context = {"sql": sql}
    queries = comparison_queries(context, dialect)
    assert [period for period, _ in queries] == ["2026-03", "2026-04"]
    assert "f.region = 'North'" in queries[0][1]
    assert "f.order_date >= '2026-03-01'" in queries[0][1]
    assert "f.order_date < '2026-04-01'" in queries[0][1]
    assert context["sql"] == sql


def test_negated_month_comparison_executes_nothing(retail):
    """Verify negated month comparison executes nothing.

    Args:
        retail: Temporary real SQLite retail service fixture.
    """
    context = {
        "sql": "SELECT SUM(net_revenue_cents) FROM sales_facts WHERE NOT (order_date >= '2026-04-01' AND order_date < '2026-05-01')"
    }
    result = run_workflow(
        Mock(),
        retail,
        [{"role": "user", "content": "Compare that with last month."}],
        context=context,
    )
    assert result.outcome == "clarify" and result.attempts == []
    assert result.trace["tool_calls"] == []


@pytest.mark.parametrize(
    "question",
    [
        "May I see net revenue for April 2026?",
        "May we see gross sales in March 2026?",
        "May I see April net revenue?",
        "Show net revenue for customer 2025 in April 2026.",
        "Show orders over 2025 cents in April 2026.",
        "Maybe show gross sales for January.",
    ],
)
def test_courtesy_and_non_date_numbers_are_not_outside_dates(question):
    """Verify courtesy and non date numbers are not outside dates.

    Args:
        question: Current natural-language analysis request.
    """
    assert preflight(question) is None


@pytest.mark.parametrize(
    "question",
    [
        "May I see net revenue for May 2026?",
        "Show gross sales for June.",
        "Show net revenue in May.",
        "Show May net revenue.",
        "Show net revenue during the month of September.",
        "May",
        "Show net revenue from April to May.",
        "Show net revenue for Apr and May.",
        "Show gross sales for May 1, 2026.",
        "Show net revenue for 2025.",
        "Get 2025 net revenue.",
        "Show net revenue 2025.",
        "Show net revenue in 2026-05.",
    ],
)
def test_real_outside_date_expressions_still_refused(question):
    """Verify real outside date expressions still refused.

    Args:
        question: Current natural-language analysis request.
    """
    assert preflight(question)[0] == "unsupported"


def test_courtesy_may_is_not_a_requested_month():
    """Verify courtesy may is not a requested month."""
    assert requested_dates("May I see net revenue for April 2026?") == ({2026}, {4})
    assert requested_dates("May I see net revenue for May 2026?") == ({2026}, {5})
