"""Versioned retail semantics and deterministic clarification/refusal checks."""
import re
from .demo import AS_OF_DATE, DEMO_VERSION
from .dates import requested_dates

CONTRACT = {
    'version': DEMO_VERSION,
    'as_of_date': AS_OF_DATE,
    'currency': 'USD cents (integer amounts; divide by 100 only when explicitly labeling dollars)',
    'grain': {'sales_facts': 'one order item; safe starting point for revenue analytics',
              'refunds': 'one refund event; multiple refunds can reference one item',
              'targets': 'one calendar month and category'},
    'metrics': {
        'gross_sales': 'SUM(sales_facts.gross_sales_cents); completed orders only; cancelled items have zero gross',
        'net_revenue': 'SUM(sales_facts.net_revenue_cents); gross less refunds; refunds recognized in original order month',
        'units': 'SUM(quantity) WHERE status = completed',
        'orders': 'COUNT(DISTINCT order_id) WHERE status = completed',
        'growth': '(current-prior)/prior; undefined when prior is zero; specify metric and periods',
        'target_attainment': 'monthly category net revenue / target_cents; aggregate facts BEFORE joining targets',
    },
    'approved_joins': [
        'orders.customer_id = customers.customer_id (many-to-one)',
        'order_items.order_id = orders.order_id (many-to-one)',
        'order_items.product_id = products.product_id (many-to-one)',
        'Use item-grain sales_facts for joined refund analysis; raw refunds joins are blocked',
        'aggregate sales_facts by month/category, then join targets on BOTH month AND category',
    ],
    'dates': 'ISO dates, UTC calendar months, half-open order_date >= month-start AND order_date < next-month-start. Last month means April 2026 in this fixed fixture.',
    'missing_data': 'NULL region means unknown; preserve it as a separate group. Customer 12 has no orders; product 7 has no sales.',
    'synonyms': {'sales': 'gross_sales', 'turnover': 'gross_sales', 'net sales': 'net_revenue', 'purchases': 'orders'},
    'unsupported': ['profit/cost/margin (no cost data)', 'forecasting', 'PII such as email/phone', 'writes', 'external sources'],
}


def preflight(question, retail=True):
    q = question.lower()
    destructive = re.search(r'\b(drop|delete|truncate|alter|insert|update)\s+(table|database|schema|all|from|into|orders|customers|products|students)\b', q)
    if destructive or re.search(r'remove every|erase all|disable.*read.only|bypass.*guard|pg_read_file|load_file\(|load_extension|read.*server files', q):
        return 'refused', 'This assistant only reads approved tables. Database writes, server-file access and guardrail bypasses are refused.'
    if not retail:
        return None
    years, months = requested_dates(question)
    if any(year != 2026 for year in years) or any(month not in range(1, 5) for month in months) or re.search(r'forecast|predict|profit|margin|email|phone number|password|external api|internet', q):
        return 'unsupported', 'The retail fixture cannot answer that request: it has no costs, forecasts, PII or external data, and covers January–April 2026.'
    if re.search(r'\brevenue\b', q) and not re.search(r'\bnet\b|\bgross\b', q):
        return 'clarify', 'Do you mean gross sales or net revenue after refunds? Please specify a month or date range.'
    if re.search(r'growth|best.performing|top customers|compare.*last month', q) and not re.search(r'net revenue|gross sales|units|order count|completed orders', q):
        return 'clarify', 'Which metric (net revenue, gross sales, units or completed orders) and which periods should I compare?'
    return None
