"""Closed retail semantic subset. Plans compile to the item-grain semantic table."""
from dataclasses import dataclass, asdict
from datetime import date
import sqlglot
from sqlglot import exp
from .demo import previous_month, next_month


METRICS = {
    'gross_sales_cents': ('item', 'SUM(gross_sales_cents)'),
    'net_revenue_cents': ('item', 'SUM(net_revenue_cents)'),
    'refund_cents': ('item', 'SUM(refund_cents)'),
    'units': ('item', "SUM(CASE WHEN status = 'completed' THEN quantity ELSE 0 END)"),
    'orders': ('order', "COUNT(DISTINCT CASE WHEN status = 'completed' THEN order_id END)"),
    'customers': ('customer', 'COUNT(*)'),
    'net_revenue_growth_ratio': ('item', None),
    'refund_rate': ('item', 'SUM(refund_cents) * 1.0 / NULLIF(SUM(gross_sales_cents), 0)'),
}
DIMENSIONS = ('region', 'category', 'month')


@dataclass(frozen=True)
class AnalysisPlan:
    metric: str
    dimensions: tuple
    filters: dict
    date_range: tuple | None
    grain: str

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict) or set(value) != {'metric', 'dimensions', 'filters', 'date_range', 'grain'}:
            raise ValueError('invalid_plan_fields')
        metric = value['metric']
        if not isinstance(metric, str) or metric not in METRICS or value['grain'] != METRICS[metric][0]:
            raise ValueError('unsupported_metric_or_grain')
        dimensions, filters, dates = value['dimensions'], value['filters'], value['date_range']
        allowed = ('region',) if metric == 'customers' else ('region','category') if metric == 'net_revenue_growth_ratio' else DIMENSIONS
        if (not isinstance(dimensions, list) or len(dimensions) > len(allowed) or
                any(not isinstance(d, str) or d not in allowed for d in dimensions) or
                len(set(dimensions)) != len(dimensions)):
            raise ValueError('unsupported_dimensions')
        if (not isinstance(filters, dict) or any(k not in allowed for k in filters) or
                any(not isinstance(v, str) or not v or len(v) > 100 for v in filters.values())):
            raise ValueError('unsupported_filters')
        if dates is not None:
            if metric == 'customers' or not isinstance(dates, list) or len(dates) != 2:
                raise ValueError('unsupported_date_range')
            if any(not isinstance(d, str) or date.fromisoformat(d).isoformat() != d for d in dates):
                raise ValueError('invalid_date_range')
            if dates[0] >= dates[1]:
                raise ValueError('invalid_date_range')
            # Fixed synthetic coverage; no silent partial date windows.
            if dates[0] < '2026-01-01' or dates[1] > '2026-05-01':
                raise ValueError('outside_demo_coverage')
        if metric == 'net_revenue_growth_ratio':
            if (not dates or dates[0][8:] != '01' or dates[1] != next_month(dates[0][:7])+'-01' or
                    previous_month(dates[0][:7]) < '2026-01'):
                raise ValueError('Growth needs a current calendar month with a covered previous month.')
        return cls(metric, tuple(dimensions), dict(filters), tuple(dates) if dates else None, value['grain'])

    def compile(self, dialect='sqlite'):
        # Revalidate even direct constructor calls. Identifiers/expressions come only
        # from code; every caller-controlled value is an AST string literal.
        plan = self.parse({**asdict(self), 'dimensions': list(self.dimensions),
                           'date_range': list(self.date_range) if self.date_range else None})
        expression = METRICS[plan.metric][1]
        lower = plan.date_range[0] if plan.date_range else None
        if plan.metric == 'net_revenue_growth_ratio':
            start,end = plan.date_range
            lower = previous_month(start[:7])+'-01'
            current = f"SUM(CASE WHEN order_date >= '{start}' AND order_date < '{end}' THEN net_revenue_cents ELSE 0 END)"
            prior = f"SUM(CASE WHEN order_date >= '{lower}' AND order_date < '{start}' THEN net_revenue_cents ELSE 0 END)"
            expression = f'ROUND(({current} - {prior}) * 1.0 / NULLIF({prior}, 0), 4)'
        table = 'customers' if plan.metric == 'customers' else 'sales_facts'
        tree = sqlglot.select(*plan.dimensions, exp.alias_(sqlglot.parse_one(expression), plan.metric)).from_(table)
        conditions = [exp.EQ(this=exp.column(k), expression=exp.Literal.string(v)) for k, v in sorted(plan.filters.items())]
        if plan.date_range:
            conditions += [exp.GTE(this=exp.column('order_date'), expression=exp.Literal.string(lower)),
                           exp.LT(this=exp.column('order_date'), expression=exp.Literal.string(plan.date_range[1]))]
        for condition in conditions:
            tree = tree.where(condition)
        if plan.dimensions:
            tree = tree.group_by(*plan.dimensions).order_by(*plan.dimensions)
        return tree.sql(dialect=dialect)


PLAN_TOOL = {'type': 'function', 'function': {
    'name': 'execute_analysis_plan',
    'description': 'Canonical retail analysis. Dimensions are ONLY explicitly requested grouping, never filters. Growth uses the current month date_range, compares the previous month, and rounds to 4 decimals.',
    'parameters': {'type': 'object', 'properties': {
        'metric': {'type': 'string', 'enum': list(METRICS)},
        'dimensions': {'type': 'array', 'items': {'type': 'string', 'enum': list(DIMENSIONS)}},
        'filters': {'type': 'object', 'properties': {k: {'type': 'string'} for k in DIMENSIONS}, 'additionalProperties': False},
        'date_range': {'anyOf': [{'type': 'array', 'items': {'type': 'string'}, 'minItems': 2, 'maxItems': 2}, {'type': 'null'}]},
        'grain': {'type': 'string', 'enum': ['item', 'order', 'customer']},
    }, 'required': ['metric', 'dimensions', 'filters', 'date_range', 'grain'], 'additionalProperties': False},
}}
