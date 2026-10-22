"""Chart recommendations depend exclusively on executed tabular values.

File: assistant/charts.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import math
import re
from decimal import Decimal

import pandas as pd


def chart_data(result):
    """Choose a chart only when executed values support an unambiguous dimension and measure.

    Args:
        result: Executed result payload containing columns, rows, and truncation metadata.

    Returns:
        dict | None: Chart kind, axes, and frame, or None for ambiguous data.
    """
    if not result or not result.get("rows") or len(result["columns"]) < 2:
        return None
    frame = pd.DataFrame(result["rows"], columns=result["columns"])
    if not frame.columns.is_unique:
        return None
    measures = []
    for column in frame.columns:
        values = frame[column].dropna().tolist()
        numeric = values and all(
            isinstance(v, (int, float, Decimal)) and not isinstance(v, bool) for v in values
        )
        if numeric and not column.lower().endswith("_id"):
            try:
                if all(math.isfinite(float(v)) for v in values):
                    frame[column] = pd.to_numeric(frame[column])
                    measures.append(column)
            except (OverflowError, ValueError):
                pass
    dimensions = [c for c in frame.columns if c not in measures]
    if not measures or not dimensions:
        return None
    x, y = dimensions[0], measures[0]
    if frame[x].isna().any() or frame[x].duplicated().any():
        return None  # Never invent an aggregation to make a chart fit.
    dates = all(re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", str(v)) for v in frame[x])
    return {"kind": "line" if dates else "bar", "x": x, "y": y, "frame": frame[[x, y]].set_index(x)}
