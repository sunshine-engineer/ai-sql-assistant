"""Offline reference and mutation witnesses across multiple data instances; no model."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
from .benchmark import suites, grade_sql
from .connections import open_engine
from .demo import TABLES
from .evaluation import same_results
from .execution import QueryService
from .instances import INSTANCES, build_instance


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('evaluation/results/instance-checks.json'))
    args=parser.parse_args()
    checks=[]
    with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
        services={}
        for name in INSTANCES:
            engine=open_engine('sqlite',path=build_instance(directory,name));stack.callback(engine.dispose)
            service=QueryService(engine,tables=TABLES);service.retail=True;services[name]=service
        for split,cases in suites().items():
            for case in cases:
                if case['expected_outcome']!='answered':continue
                if split=='development':
                    actual=services['base'].query(case['gold_sql'])
                    checks.append({'id':case['id'],'check':'frozen_base','passed':same_results(actual,case)})
                for row in grade_sql(case['gold_sql'],services,case):
                    checks.append({'id':case['id'],'check':'reference_execution','instance':row['instance'],'passed':row['passed']})
        witness=grade_sql('SELECT 12 AS customers',services,suites()['heldout'][0])
    report={'mode':'offline_instance_regression','instance_version':'retail-instances-v1',
            'checks':checks,'passed':sum(c['passed'] for c in checks),'total':len(checks),
            'constant_query_witness':witness,'scope':'Gold execution and original frozen rows; not model accuracy or proof of gold SQL correctness.'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},indent=2))
    return 0 if all(c['passed'] for c in checks) and [r['passed'] for r in witness]==[True,False,False] else 1


if __name__=='__main__':raise SystemExit(main())
