"""Deterministic month comparisons preserve the previous SQL metric and filters."""
import re
import sqlglot
from sqlglot import exp
from .demo import previous_month, next_month


def is_month_comparison(question):
    return bool(re.search(r'compare\s+(that|it|this).*\b(last|previous) month\b', question, re.I))


def comparison_queries(context, dialect):
    if not context or not isinstance(context.get('sql'), str):
        return None
    try:
        tree = sqlglot.parse_one(context['sql'], read=dialect)
        where = tree.args.get('where')
        if where is None or list(where.find_all(exp.Or)) or list(tree.find_all(exp.Subquery)):
            return None
        starts, ends = [], []
        for node in where.walk():
            if isinstance(node, (exp.GTE, exp.LT)) and isinstance(node.this, exp.Column) and node.this.name == 'order_date' and isinstance(node.expression, exp.Literal):
                (starts if isinstance(node, exp.GTE) else ends).append(node.expression.this)
        if len(starts) != 1 or len(ends) != 1 or not re.fullmatch(r'\d{4}-\d{2}-01', starts[0]):
            return None
        current = starts[0][:7]
        if ends[0] != next_month(current) + '-01':
            return None
        prior = previous_month(current)
        old = tree.copy()
        for node in old.args['where'].walk():
            if isinstance(node, (exp.GTE, exp.LT)) and isinstance(node.this, exp.Column) and node.this.name == 'order_date' and isinstance(node.expression, exp.Literal):
                node.set('expression', exp.Literal.string((prior if isinstance(node, exp.GTE) else current) + '-01'))
        return [(prior, old.sql(dialect=dialect)), (current, tree.sql(dialect=dialect))]
    except (ValueError, sqlglot.errors.SqlglotError):
        return None
