"""Paired live workflow vs one-shot SQL, repeated on reserved prompts and data instances."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter, sleep

from langchain_core.messages import SystemMessage, HumanMessage
from .business import CONTRACT, preflight
from .budgets import RequestBudget, BudgetExceeded, provider_error
from .connections import open_engine
from .demo import TABLES
from .evaluation import load_cases, same_results
from .execution import QueryService
from .generation import run_workflow
from .instances import build_instance, INSTANCES
from .tracing import PROMPT_VERSION, model_identifier, Trace

HELDOUT = Path(__file__).resolve().parent.parent / 'evaluation/heldout_v1.json'


def suites():
    return {'development': load_cases(), 'heldout': json.loads(HELDOUT.read_text())['cases']}


def grade_sql(sql, services, case):
    """Execute the SAME generated SQL on every instance, not a fresh generation."""
    outcomes = []
    for name, service in services.items():
        try:
            expected = service.query(case['gold_sql'])
            if expected.get('error') or expected.get('truncated'):
                raise ValueError('invalid_reference')
            reference = {**case, 'columns': expected['columns'], 'rows': expected['rows']}
        except Exception:
            outcomes.append({'instance':name,'passed':False,'error':'reference_execution_failed'})
            continue
        try:
            actual = service.query(sql)
            passed = same_results(actual, reference)
            outcomes.append({'instance': name, 'passed': passed, 'error': None if passed else 'result_mismatch'})
        except Exception:
            outcomes.append({'instance': name, 'passed': False, 'error': 'execution_rejected_or_failed'})
    return outcomes


def one_shot(model, service, question):
    decision = preflight(question)
    if decision:
        return {'outcome': decision[0], 'sql': None, 'answer_verified': None, 'trace': None}
    system = ('Return ONLY JSON with one key sql containing one SQLite SELECT. No tools, no repairs. '
              'Use this retail contract: ' + json.dumps(CONTRACT) + '. Metadata: ' + service.describe(question))
    messages = [SystemMessage(content=system), HumanMessage(content=question)]
    budget = RequestBudget()
    trace=Trace(model=model_identifier(model))
    started=perf_counter()
    admitted=False
    try:
        kwargs, reserved = budget.admit(messages, [])
        admitted=True
        reply = model.invoke(messages, response_format={'type':'json_object'}, **kwargs)
        trace.usage(reply)
        budget.charge(reply, reserved)
        trace.model_calls.append({'outcome':'succeeded','duration_ms':round((perf_counter()-started)*1000,2)})
        payload = json.loads(reply.content)
        if not isinstance(payload, dict) or set(payload) != {'sql'} or not isinstance(payload['sql'], str):
            raise ValueError('invalid_baseline_output')
        return {'outcome':'answered','sql':payload['sql'],'answer_verified':None,'trace':trace.export('answered')}
    except Exception as exc:
        if isinstance(exc, BudgetExceeded):
            error='budget_exhausted'
        elif isinstance(exc, (ValueError, TypeError)):
            error='generation_or_format_failure'
        else:
            error=provider_error(exc)
        if admitted and not trace.model_calls:
            trace.model_calls.append({'outcome':'failed','error_category':error,
                                      'duration_ms':round((perf_counter()-started)*1000,2)})
        return {'outcome':'failed','sql':None,'answer_verified':None,'trace':trace.export('failed'),'error':error}



def benchmark(model, services, cases, repeats=2, split='heldout'):
    source_hash = hashlib.sha256()
    for source in sorted(Path(__file__).parent.glob('*.py')):
        source_hash.update(source.name.encode()+source.read_bytes())
    rows = []
    base = services['base']
    for repetition in range(repeats):
        for index, case in enumerate(cases):
            # Counterbalance ordering to reduce systematic rate-limit/time bias.
            approaches = ('workflow', 'one_shot') if (index+repetition) % 2 == 0 else ('one_shot', 'workflow')
            for approach in approaches:
                started = perf_counter()
                try:
                    if approach == 'workflow':
                        report = run_workflow(model, base, [{'role':'user','content':case['question']}])
                        sql = next((a['sql'] for a in reversed(report.attempts) if a.get('result')), None)
                        candidate = {'outcome':report.outcome, 'sql':sql,
                                     'answer_verified': report.answer_validation.get('model_verified'), 'trace':report.trace}
                    else:
                        candidate = one_shot(model, base, case['question'])
                    per_instance = grade_sql(candidate['sql'], services, case) if case['expected_outcome'] == 'answered' and candidate['sql'] else []
                    sql_passed = bool(per_instance) and all(i['passed'] for i in per_instance)
                    passed = candidate['outcome'] == case['expected_outcome'] and (sql_passed if case['expected_outcome']=='answered' else True)
                    error = candidate.get('error') or (None if passed else 'query_or_outcome_mismatch')
                    if candidate['trace']:
                        provider_failures = [c.get('error_category') for c in candidate['trace']['model_calls'] if c.get('error_category')]
                        if provider_failures:
                            error = provider_failures[-1]
                    row = {'outcome': candidate['outcome'], 'passed': passed,
                           'sql_suite_passed': sql_passed if case['expected_outcome']=='answered' else None,
                           'answer_verified':candidate['answer_verified'], 'instances':per_instance,
                           'trace':candidate['trace'], 'error':error}
                except Exception as exc:
                    row = {'outcome':'failed', 'passed':False, 'sql_suite_passed':False if case['expected_outcome']=='answered' else None,
                           'answer_verified':None, 'instances':[], 'trace':None,
                           'error':'generation_or_format_failure' if isinstance(exc,(ValueError,TypeError)) else provider_error(exc)}
                rows.append({'id':case['id'], 'split':split, 'repeat':repetition+1, 'approach':approach,
                             'expected_outcome':case['expected_outcome'], 'duration_ms':round((perf_counter()-started)*1000,2), **row})
    summary = {}
    for approach in ('workflow','one_shot'):
        selected = [r for r in rows if r['approach']==approach]
        sql_rows = [r for r in selected if r['sql_suite_passed'] is not None]
        answers = [r for r in selected if r['answer_verified'] is not None]
        by_case = {case['id']: [r for r in selected if r['id']==case['id']] for case in cases}
        summary[approach] = {'passed':sum(r['passed'] for r in selected), 'total':len(selected),
                            'sql_suite_passed':sum(r['sql_suite_passed'] for r in sql_rows), 'sql_total':len(sql_rows),
                            'answer_verified':sum(r['answer_verified'] for r in answers), 'answer_total':len(answers),
                            'consistent_cases':sum(all(r['passed'] for r in group) for group in by_case.values()),
                            'cases':len(by_case)}
    return {'mode':'live_paired_benchmark', 'model':model_identifier(model), 'prompt_version':PROMPT_VERSION,
            'source_sha256':source_hash.hexdigest(), 'interval_seconds':getattr(model,'interval',0) if type(getattr(model,'interval',0)) in (int,float) else None,
            'model_parameters':{'temperature':0,'max_output_tokens':1500,'reasoning_effort':'none'},
            'timestamp':datetime.now(timezone.utc).isoformat(), 'split':split, 'repeats':repeats,
            'suite_sha256':hashlib.sha256(json.dumps(cases,sort_keys=True).encode()).hexdigest(),
            'instance_version':'retail-instances-v1', 'instances':list(services),
            'scope':'Same SQL executed across synthetic instances. Baseline has no answer-generation stage. Preflight shared. Repeats are not independent samples.',
            'summary':summary, 'rows':rows}


class PacedModel:
    """Shared pacing for bound tools and baseline; failures are never retried."""
    def __init__(self, model, interval=5, state=None):
        if interval < 0 or interval > 60:
            raise ValueError('interval must be 0..60')
        self.model, self.interval = model, interval
        self.state = state if state is not None else [0.0]
        self.model_name = getattr(model,'model_name','bound')

    def bind_tools(self, tools):
        return PacedModel(self.model.bind_tools(tools),self.interval,self.state)._named(self.model_name)

    def _named(self,name):
        self.model_name=name
        return self

    def invoke(self, messages, **kwargs):
        delay=max(0,self.interval-(perf_counter()-self.state[0]))
        timeout=kwargs.get('timeout',20)
        if delay>=timeout:
            raise TimeoutError('Benchmark pacing exceeded request time budget.')
        if delay:
            sleep(delay)
        kwargs['timeout']=max(0.01,timeout-delay)
        self.state[0]=perf_counter()
        return self.model.invoke(messages,**kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['development','heldout'], default='heldout')
    parser.add_argument('--repeats',type=int,default=2)
    parser.add_argument('--limit',type=int,default=10)
    parser.add_argument('--model',default='qwen/qwen3.8-27b')
    parser.add_argument('--interval',type=float,default=5,help='Minimum seconds between provider calls; no automatic retry.')
    parser.add_argument('--output',type=Path,default=Path('evaluation/results/benchmark.json'))
    args=parser.parse_args()
    if not 1<=args.repeats<=5 or not 1<=args.limit<=50:
        parser.error('repeats must be 1..5 and limit 1..50')
    key=os.getenv('GROQ_API_KEY')
    if not key:
        parser.error('Configure GROQ_API_KEY locally; do not pass credentials as CLI arguments.')
    import langchain_groq
    model=langchain_groq.ChatGroq(api_key=key,model=args.model,temperature=0,max_retries=0,timeout=20,max_tokens=1500,reasoning_effort='none')
    model=PacedModel(model,args.interval)
    with tempfile.TemporaryDirectory(prefix='sql-benchmark-') as directory, ExitStack() as stack:
        services={}
        for name in INSTANCES:
            engine=open_engine('sqlite',path=build_instance(directory,name))
            stack.callback(engine.dispose)
            service=QueryService(engine,tables=TABLES)
            service.retail=True
            services[name]=service
        report=benchmark(model,services,suites()[args.split][:args.limit],args.repeats,args.split)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'model':report['model'],'split':args.split,'summary':report['summary'],'output':str(args.output)},indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
