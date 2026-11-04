"""Reference-fixture validation and opt-in live model execution-result evaluation."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from statistics import median
from time import perf_counter

from .business import preflight
from .budgets import RequestBudget
from .config import DEFAULT_DATABASE, DEFAULT_MODEL
from .connections import open_engine
from .demo import build_demo, TABLES, DEMO_VERSION, AS_OF_DATE
from .execution import QueryService
from .generation import run_workflow
from .tracing import PROMPT_VERSION, model_identifier

CASE_FILE = Path(__file__).resolve().parent.parent / 'evaluation' / 'retail_v1.json'


def load_cases():
    return json.loads(CASE_FILE.read_text())['cases']


def same_results(actual, case):
    if not actual or actual.get('truncated') or actual.get('error'):
        return False
    expected = case['rows']
    rows = actual['rows']
    if len(actual['columns']) != len(case['columns']) or len(rows) != len(expected):
        return False

    def equal(a, b):
        if len(a) != len(b):
            return False
        for x, y in zip(a, b):
            if isinstance(x, (int, float)) and not isinstance(x, bool) and isinstance(y, (int, float)) and not isinstance(y, bool):
                if not math.isclose(x, y, rel_tol=1e-7, abs_tol=1e-6):
                    return False
            elif x != y:
                return False
        return True

    if case.get('ordered', False):
        return all(equal(a, b) for a, b in zip(rows, expected))
    remaining = list(rows)
    for row in expected:
        found = next((i for i, value in enumerate(remaining) if equal(value, row)), None)
        if found is None:
            return False
        remaining.pop(found)
    return True


def evaluate(service, model=None, cases=None):
    mode = 'live_model' if model is not None else 'reference_fixture'
    outcomes = []
    for case in cases if cases is not None else load_cases():
        started = perf_counter()
        trace = None
        query_passed = answer_passed = displayed_passed = model_answer_passed = None
        answer_method = None
        try:
            if model is None:
                if case['expected_outcome'] == 'answered':
                    result = service.query(case['gold_sql'])
                    query_passed = same_results(result, case)
                    passed = query_passed
                else:
                    decision = preflight(case['question'])
                    passed = decision is not None and decision[0] == case['expected_outcome']
                outcome = case['expected_outcome'] if passed else 'mismatch'
            else:
                report = run_workflow(model, service, [{'role': 'user', 'content': case['question']}], budget=RequestBudget())
                outcome, trace = report.outcome, report.trace
                passed = outcome == case['expected_outcome']
                if case['expected_outcome'] == 'answered':
                    query_passed = same_results(report.result, case)
                    status = report.answer_validation.get('status')
                    answer_method = report.answer_validation.get('method', status)
                    model_answer_passed = report.answer_validation.get('model_verified', False) if status in {'verified','rejected'} else None
                    answer_passed = (report.answer_validation.get('displayed_verified',False) if status == 'deterministic'
                                     else report.answer_validation.get('model_verified',False))
                    displayed_passed = report.answer_validation.get('displayed_verified', False)
                    passed = passed and query_passed and answer_passed
            if passed:
                error = None
            elif outcome != case['expected_outcome']:
                error = 'outcome_mismatch'
            elif query_passed is False:
                error = 'sql_result_mismatch'
            elif answer_passed is False:
                error = 'answer_not_faithful'
            else:
                error = 'reference_mismatch'
        except Exception:
            passed, outcome, error = False, 'failed', 'evaluation_error'
            if case['expected_outcome'] == 'answered':
                query_passed = False
                if model is not None:
                    answer_passed = displayed_passed = False
        outcomes.append({'id': case['id'], 'category': case['category'],
                         'expected_outcome': case['expected_outcome'], 'outcome': outcome,
                         'passed': passed, 'error': error,
                         'query_passed': query_passed, 'answer_passed': answer_passed,
                         'model_answer_passed':model_answer_passed,'answer_method':answer_method,
                         'displayed_answer_passed': displayed_passed,
                         'duration_ms': round((perf_counter()-started)*1000, 2), 'trace': trace})
    metrics = {}
    for kind in ['answered', 'clarify', 'refused', 'unsupported']:
        selected = [r for r in outcomes if r['expected_outcome'] == kind]
        metrics[kind] = {'passed': sum(r['passed'] for r in selected), 'total': len(selected)}
    quality = {}
    for label, field in [('query_results', 'query_passed'), ('answer_faithfulness','answer_passed'), ('model_answer_faithfulness', 'model_answer_passed'),
                         ('displayed_answer_faithfulness', 'displayed_answer_passed')]:
        values = [row[field] for row in outcomes if row[field] is not None]
        quality[label] = {'passed': sum(values), 'total': len(values)}
    latencies = sorted(row['duration_ms'] for row in outcomes)
    traces = [row['trace'] for row in outcomes if row['trace']]
    return {'mode': mode, 'dataset_version': DEMO_VERSION, 'as_of_date': AS_OF_DATE,
            'evaluated_at': datetime.now(timezone.utc).isoformat(),
            'prompt_version': PROMPT_VERSION,
            'model': model_identifier(model) if model is not None else None,
            'model_calls': sum(len(t['model_calls']) for t in traces),
            'sql_repairs': sum(t['retries'] for t in traces),
            'scope': 'Synthetic SQLite retail fixture. Live mode separately checks query results and result-referenced answer facts; excludes SQL semantic proof and unrestricted prose grading.',
            'evaluation_version': 'v3-canonical-answers', 'quality_metrics': quality,
            'metrics': metrics, 'categories': dict(Counter(r['category'] for r in outcomes)),
            'latency_ms': {'p50': median(latencies) if latencies else None,
                           'p95': latencies[max(0, math.ceil(len(latencies)*.95)-1)] if latencies else None},
            'cases': outcomes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Call Groq with GROQ_API_KEY; uses your provider quota.')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--output', type=Path, default=Path('evaluation/results/latest.json'))
    args = parser.parse_args()
    if not 1 <= args.limit <= 50 or not 0 <= args.offset < 50:
        parser.error('limit must be 1..50 and offset 0..49')
    model = None
    if args.live:
        import langchain_groq
        key = os.environ.get('GROQ_API_KEY')
        if not key:
            parser.error('GROQ_API_KEY is required for --live; do not pass credentials on the command line.')
        model = langchain_groq.ChatGroq(api_key=key, model=args.model, temperature=0,
                                        max_retries=0, timeout=20, max_tokens=1500)
    build_demo(DEFAULT_DATABASE)
    engine = open_engine('sqlite', path=DEFAULT_DATABASE)
    try:
        service = QueryService(engine, tables=TABLES)
        service.retail = True
        report = evaluate(service, model=model, cases=load_cases()[args.offset:args.offset+args.limit])
    finally:
        engine.dispose()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({'mode': report['mode'], 'metrics': report['metrics'], 'output': str(args.output)}, indent=2))
    return 0 if all(row['passed'] for row in report['cases']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
