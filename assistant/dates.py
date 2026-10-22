"""Recognize explicit retail date expressions without treating polite 'May I' as dates.

File: assistant/dates.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import re

MONTH_NAMES = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
MONTH_NUMBERS = {name: number for number, name in enumerate(MONTH_NAMES, 1)}
MONTH_NUMBERS.update({name[:3]: number for number, name in enumerate(MONTH_NAMES, 1)})
MONTH_NUMBERS["sept"] = 9
MONTH = "(?:" + "|".join(sorted(MONTH_NUMBERS, key=len, reverse=True)) + ")"
YEAR = r"(?:19|20)\d{2}"
MEASURE = r"(?:net\s+revenue|gross\s+sales|net\s+sales|sales|revenue|orders|units)"


def requested_dates(question):
    """Recognize explicit year and month expressions without interpreting polite May as a date.

    This intentionally small recognizer is a domain input check, not a general
    natural-language date parser. The model still handles other date expressions.

    Args:
        question: Current natural-language analysis request.

    Returns:
        tuple[set, set]: Explicitly referenced years and month numbers.
    """
    q = question.lower()
    years, months = set(), set()
    for match in re.finditer(r"\b(" + YEAR + r")-(\d{2})(?:-\d{2})?\b", q):
        years.add(int(match[1]))
        months.add(int(match[2]))
    # A named month with a year/day, or a possessive/metric, has a date role.
    patterns = [
        rf"\b(?P<month>{MONTH})\s+(?:(?:\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+)?(?P<year>{YEAR})\b",
        rf"\b(?:in|for|during|since|until|through|from|between|to)\s+(?:the\s+month\s+of\s+)?(?P<month>{MONTH})\b",
        rf"\b(?:the\s+)?month\s+of\s+(?P<month>{MONTH})\b",
        rf"\b(?P<month>{MONTH})(?:[’\x27]s\s+|\s+){MEASURE}\b",
        rf"\b(?P<month>{MONTH})\s+\d{{1,2}}(?:st|nd|rd|th)?\b",
        rf"\b{MONTH}\s*(?:and|to|through|versus|vs\.?|[-–])\s*(?P<month>{MONTH})\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, q):
            months.add(MONTH_NUMBERS[match["month"]])
            if match.groupdict().get("year"):
                years.add(int(match["year"]))
    for pattern in [
        rf"\b(?:in|for|during|since|until|through|from|year|fy)\s+(?:the\s+year\s+)?({YEAR})\b",
        rf"\b({YEAR})\s+{MEASURE}\b",
        rf"\b{MEASURE}\s+({YEAR})\b",
        rf"\bq[1-4]\s+({YEAR})\b",
    ]:
        years.update(int(m[1]) for m in re.finditer(pattern, q))
    bare = q.strip(" .!?")
    if bare in MONTH_NUMBERS:
        months.add(MONTH_NUMBERS[bare])
    if re.fullmatch(YEAR, bare):
        years.add(int(bare))
    return years, months
