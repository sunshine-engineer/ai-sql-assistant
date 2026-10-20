"""Deterministic metadata selection, separate from database authorization."""
import json
import re


def select_catalog(catalog, question, max_tables=8, max_bytes=12000):
    words = set(re.findall(r'[a-z0-9]+', question.lower()))
    scored = []
    for name, columns in catalog.items():
        table_words = set(re.findall(r'[a-z0-9]+', name.lower()))
        column_words = set(re.findall(r'[a-z0-9]+', ' '.join(c['name'] for c in columns).lower()))
        # Singular/plural matching, without sending the full catalog to the model.
        normalized = lambda values: {w.rstrip('s') for w in values}
        score = 4 * len(normalized(words) & normalized(table_words)) + len(normalized(words) & normalized(column_words))
        scored.append((-score, name))
    ranked = sorted(scored)
    relevant = [name for negative, name in ranked if negative < 0]
    if len(catalog) <= max_tables:
        relevant = [name for _, name in ranked]
    selected = {}
    for name in relevant[:max_tables]:
        candidate = {**selected, name: catalog[name]}
        if len(json.dumps(candidate).encode()) <= max_bytes:
            selected = candidate
    return selected
