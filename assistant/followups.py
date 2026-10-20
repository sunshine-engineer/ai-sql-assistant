"""Conservative month comparisons: reject extra intent and noncanonical predicates."""
import re
from datetime import date

import sqlglot
from sqlglot import exp

from .demo import previous_month, next_month


COMPARISON = re.compile(r'compare\s+(that|it|this).*\b(last|previous) month\b', re.I)
SIMPLE_COMPARISON = re.compile(
    r'(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?'
    r'compare\s+(?:that|it|this)\s+(?:with|to|against)\s+(?:the\s+)?'
    r'(?:last|previous)\s+month(?:,?\s+please)?[.!?]*', re.I,
)


def is_month_comparison(question):
    return bool(COMPARISON.search(question))


def can_reuse_comparison(question):
    """Only a complete, standalone request can reuse old metric/filter expressions.

    Extra clauses may change filters, metric, grouping or dates. Ask clarification
    rather than silently throwing away any part of those instructions.
    """
    return bool(SIMPLE_COMPARISON.fullmatch(question.strip()))


def _conjuncts(node):
    while isinstance(node, exp.Paren):
        node = node.this
    if isinstance(node, exp.And):
        return _conjuncts(node.this) + _conjuncts(node.expression)
    return [node]


def _date_column(column):
    return column.catalog, column.db, column.table, column.name


def comparison_queries(context, dialect):
    if not context or not isinstance(context.get('sql'), str):
        return None
    try:
        statements = sqlglot.parse(context['sql'], read=dialect)
        if len(statements) != 1 or not isinstance(statements[0], exp.Select):
            return None
        tree = statements[0]
        where = tree.args.get('where')
        if where is None or any(isinstance(node, (exp.Not, exp.Or, exp.Subquery, exp.With)) for node in tree.walk()):
            return None
        bounds = {}
        for predicate in _conjuncts(where.this):
            date_columns = [c for c in predicate.find_all(exp.Column) if c.name == 'order_date']
            if not date_columns:
                continue
            # Bounds must be positive top-level AND operands, not inside CASE,
            # functions, NOT, another comparison, or a transformed date column.
            if (not isinstance(predicate, (exp.GTE, exp.LT)) or
                    not isinstance(predicate.this, exp.Column) or
                    predicate.this.name != 'order_date' or
                    not isinstance(predicate.expression, exp.Literal) or
                    not predicate.expression.is_string or type(predicate) in bounds):
                return None
            value = predicate.expression.this
            if not re.fullmatch(r'\d{4}-\d{2}-01', value):
                return None
            date.fromisoformat(value)
            bounds[type(predicate)] = predicate
        if set(bounds) != {exp.GTE, exp.LT}:
            return None
        start, end = bounds[exp.GTE], bounds[exp.LT]
        if _date_column(start.this) != _date_column(end.this):
            return None
        current = start.expression.this[:7]
        if end.expression.this != next_month(current) + '-01':
            return None
        prior = previous_month(current)
        old = tree.copy()
        for predicate in _conjuncts(old.args['where'].this):
            if isinstance(predicate, (exp.GTE, exp.LT)) and isinstance(predicate.this, exp.Column) and _date_column(predicate.this) == _date_column(start.this):
                month = prior if isinstance(predicate, exp.GTE) else current
                predicate.set('expression', exp.Literal.string(month + '-01'))
        return [(prior, old.sql(dialect=dialect)), (current, tree.sql(dialect=dialect))]
    except (ValueError, sqlglot.errors.SqlglotError):
        return None
