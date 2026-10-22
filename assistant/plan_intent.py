"""Conservative checks for explicit metric, grouping, region and calendar-month intent.

File: assistant/plan_intent.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import re

from .dates import MONTH, MONTH_NUMBERS, requested_dates
from .demo import next_month


def unsupported_plan_filters(question):
    """Identify filter shapes that cannot be represented by canonical equality filters.

    This intentionally routes to reviewed SQL instead of extracting one member
    of a list, discarding a negation or pretending to understand general filters.

    Args:
        question: Current natural-language analysis request.

    Returns:
        str | None: Unsupported shape category, or None for the recognized subset.
    """
    q = question.lower()
    regions = set(re.findall(r"\b(north|south|east|west)\b", q))
    categories = set(re.findall(r"\b(hardware|software|accessories)\b", q))
    if len(regions) > 1 or len(categories) > 1:
        return "multiple_values"
    if (regions or categories or re.search(r"\b(region|category|status)\b", q)) and re.search(
        r"\bnot\b", q
    ):
        return "exclusion"
    if re.search(r"\b(or|either|neither|nor)\b", q):
        return "disjunction"
    if re.search(
        r"\b(exclud\w*|except|other than|not in|not equal|not from|not for|outside)\b|!=|<>", q
    ):
        return "exclusion"
    if re.search(
        r"\b(?:not|without)\s+(?:the\s+)?(?:north|south|east|west|hardware|software|accessories)\b",
        q,
    ):
        return "exclusion"
    if re.search(
        r"\b(where|having|above|below|over|under|between|more than|less than|at least|at most)\b|[<>]",
        q,
    ):
        return "conditional_filter"
    if re.search(
        r"\b(cancelled|canceled|pending|status)\b|\bwith\s+(?:no|quantity|amount|orders?)\b|\bcustomer\s+(?:id\s*)?\d+\b",
        q,
    ):
        return "unsupported_filter"
    return None


class PlanIntentError(ValueError):
    """Signal an explicit question constraint or routing requirement missing from a plan."""

    def __init__(self, expected):
        """Retain expected intent fields without embedding private input text.

        Args:
            expected: Expected explicit intent fields or routing requirements.
        """
        self.expected = expected
        super().__init__("plan_intent_mismatch")


def explicit_constraints(question):
    """Extract conservative metric, grouping, region, and calendar-month constraints.

    Args:
        question: Current natural-language analysis request.

    Returns:
        dict: Conservative explicit intent fields; not a complete language parse.
    """
    q = question.lower()
    expected = {}
    growth = "growth" in q
    if re.search(r"refund.*(?:ratio|rate)|(?:ratio|rate).*refund", q):
        expected["metric"] = "refund_rate"
    elif re.search(r"\bnet\s+(?:revenue|sales)\b", q):
        expected["metric"] = "net_revenue_growth_ratio" if growth else "net_revenue_cents"
    elif re.search(r"\bgross\s+sales\b", q) and not growth:
        expected["metric"] = "gross_sales_cents"
    elif re.search(r"\brefund\s+(?:amounts?|cents)\b", q) and not growth:
        expected["metric"] = "refund_cents"
    # Never reinterpret vague requests or multiple metrics as a single metric.
    if re.search(r"net.*(?:and|versus|vs)\s+gross|gross.*(?:and|versus|vs)\s+net", q):
        expected.pop("metric", None)
    if expected:
        groups = []
        for match in re.finditer(
            r"\b(?:by|per|grouped by)\s+((?:(?:product\s+)?categor(?:y|ies)|regions?|months?)(?:\s*(?:,|and)\s*(?:(?:product\s+)?categor(?:y|ies)|regions?|months?))*)",
            q,
        ):
            for token in re.findall(r"categor(?:y|ies)|regions?|months?", match[1]):
                name = (
                    "category"
                    if token.startswith("categor")
                    else "region"
                    if token.startswith("region")
                    else "month"
                )
                if name not in groups:
                    groups.append(name)
        if groups or not re.search(r"\b(?:by|per|each|breakdown|break.down|across|group)\b", q):
            expected["dimensions"] = groups
    regions = re.findall(r"\b(north|south|east|west)\b", q)
    if len(set(regions)) == 1:
        expected["region"] = regions[0].title()
    categories = re.findall(r"\b(hardware|software|accessories)\b", q)
    if (
        expected.get("metric")
        and len(set(regions)) <= 1
        and len(set(categories)) <= 1
        and not re.search(r"\b(?:where|with|having|above|below|over|excluding|only|except)\b", q)
    ):
        expected["filters"] = {}
        if regions:
            expected["filters"]["region"] = regions[0].title()
        if categories:
            expected["filters"]["category"] = categories[0].title()
    years, months = requested_dates(question)
    if growth:
        named = [MONTH_NUMBERS[m[0]] for m in re.finditer(r"\b" + MONTH + r"\b", q)]
        if len(named) == 2 and years == {2026} and named[1] == named[0] + 1:
            current = f"2026-{named[1]:02}"
            expected["date_range"] = [current + "-01", next_month(current) + "-01"]
    elif (
        len(years) == 1
        and len(months) == 1
        and not re.search(
            r"\b(?:between|since|until|through)\b|\d{4}-\d{2}-\d{2}|\b" + MONTH + r"\s+\d{1,2}\b", q
        )
    ):
        # Only whole named months, not arbitrary day/range expressions.
        current = f"{next(iter(years)):04}-{next(iter(months)):02}"
        try:
            expected["date_range"] = [current + "-01", next_month(current) + "-01"]
        except ValueError:
            pass
    return expected


def validate_plan_intent(plan, question):
    """Reject canonical plans that contradict explicit intent or omit unsupported filters.

    Args:
        plan: Optional validated canonical plan associated with this execution.
        question: Current natural-language analysis request.

    Raises:
        PlanIntentError: If explicit intent cannot be represented faithfully by the proposed plan.
    """
    reason = unsupported_plan_filters(question)
    if reason:
        raise PlanIntentError(
            {
                "route": "Use query_database and preserve every requested filter, or ask clarification; canonical equality filters cannot represent "
                + reason
                + "."
            }
        )
    expected = explicit_constraints(question)
    q = question.lower()
    if re.search(r"products?.*(?:never|not).*order", q):
        raise PlanIntentError(
            {"route": "Use query_database: products with NOT EXISTS in order_items; no CTE needed."}
        )
    if re.search(r"label.*unknown|unknown.*label", q) and "region" in q:
        raise PlanIntentError(
            {
                "route": "Use query_database with COALESCE(region, 'Unknown') for the explicitly requested label."
            }
        )
    mismatch = {}
    for field in ("metric", "dimensions", "date_range", "filters"):
        if field in expected:
            actual = getattr(plan, field)
            actual = list(actual) if isinstance(actual, tuple) else actual
            if actual != expected[field]:
                mismatch[field] = expected[field]
    if "region" in expected and plan.filters.get("region") != expected["region"]:
        mismatch["filters"] = {"region": expected["region"]}
    if mismatch:
        raise PlanIntentError(mismatch)


def requires_refund_plan(question):
    """Require canonical refund semantics only for representable supported requests.

    Args:
        question: Current natural-language analysis request.

    Returns:
        bool: Whether supported canonical refund semantics must be enforced.
    """
    q = question.lower()
    return (
        explicit_constraints(question).get("metric") == "refund_rate"
        and unsupported_plan_filters(question) is None
        and not re.search(
            r"\b(?:where|having|top|over|above|below|excluding|between|customers|status)\b", q
        )
    )
