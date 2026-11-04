"""Persistent operational counters with an explicit sanitized scalar allowlist."""
from collections import Counter
import argparse
import json
from pathlib import Path
import sqlite3

OUTCOMES = {'answered', 'clarify', 'refused', 'unsupported', 'failed', 'budget_exhausted'}
ERRORS = {'rate_limit', 'authentication', 'model_or_request', 'provider_timeout', 'provider_unavailable', 'provider_error'}


def record(path, trace):
    # No question, SQL, schema, model name, credentials, cell values or exception text.
    outcome = trace.get('outcome')
    outcome = outcome if outcome in OUTCOMES else 'failed'
    errors = [c.get('error_category') for c in trace.get('model_calls', [])]
    category = next((e for e in errors if e in ERRORS), None)
    number = lambda value: value if type(value) in (int, float) and 0 <= value <= 1e10 else 0
    usage = trace.get('token_usage') or {}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS requests
        (outcome TEXT, error_category TEXT, duration_ms REAL, tokens INTEGER,
         usage_complete INTEGER, retries INTEGER, calls INTEGER)''')
        db.execute('INSERT INTO requests VALUES (?,?,?,?,?,?,?)',
                   (outcome, category, number(trace.get('request_elapsed_ms', trace.get('duration_ms'))),
                    number(usage.get('total_tokens')), int(trace.get('token_usage_complete') is True),
                    number(trace.get('retries')), len(trace.get('tool_calls', []))))


def aggregate(path):
    with sqlite3.connect(path) as db:
        rows = db.execute('SELECT * FROM requests').fetchall()
    return {'requests': len(rows), 'outcomes': dict(Counter(r[0] for r in rows)),
            'provider_errors': dict(Counter(r[1] for r in rows if r[1])),
            'measured_tokens': sum(r[3] for r in rows),
            'requests_with_complete_usage': sum(r[4] for r in rows),
            'retries': sum(r[5] for r in rows), 'tool_calls': sum(r[6] for r in rows),
            'duration_ms_mean': sum(r[2] for r in rows)/len(rows) if rows else None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    print(json.dumps(aggregate(parser.parse_args().path), indent=2))
