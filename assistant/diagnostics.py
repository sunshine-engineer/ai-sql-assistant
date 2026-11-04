"""Raw plan/SQL diagnostics restricted to benchmark-owned synthetic fixtures."""
from contextlib import contextmanager
import tempfile
from .connections import open_engine
from .demo import TABLES
from .execution import QueryService
from .instances import INSTANCES, build_instance


class SyntheticSuite:
    """Own all connections and paths; never accept caller-supplied services/paths."""
    def __init__(self):
        self._directory = None
        self.services = {}
        self._engines = {}

    def __enter__(self):
        self._directory = tempfile.TemporaryDirectory(prefix='synthetic-benchmark-')
        try:
            for name in INSTANCES:
                path = build_instance(self._directory.name, name)
                engine = open_engine('sqlite', path=path)
                try:
                    self._engines[name] = engine
                    service = QueryService(engine, tables=TABLES)
                    service.retail = True
                    self.services[name] = service
                except BaseException:
                    engine.dispose()
                    raise
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        for engine in self._engines.values():
            engine.dispose()
        self._engines.clear()
        self.services.clear()
        if self._directory:
            self._directory.cleanup()
            self._directory = None

    def __exit__(self, *args):
        self.close()

    def authorize(self, services):
        # Identity and ownership, not a boolean retail marker or a filename prefix.
        if self._directory is None or set(services) != set(self.services):
            raise PermissionError('Diagnostics require an active benchmark-owned synthetic suite.')
        if any(services[name] is not service or service.engine is not self._engines[name] for name, service in self.services.items()):
            raise PermissionError('Diagnostics cannot capture arbitrary database services.')

    @contextmanager
    def capture(self, services):
        self.authorize(services)
        yield SyntheticDiagnostics(self, services)


class SyntheticDiagnostics:
    def __init__(self, owner, services):
        self._owner = owner
        self._services = services
        self.rows = []

    def validate_cases(self, cases):
        from .benchmark import suites
        known = {c['id']:c for group in suites(include_prospective=True).values() for c in group}
        for case in cases:
            source = known.get(case.get('id'))
            if not source or any(case.get(k)!=source.get(k) for k in ('question','gold_sql','expected_outcome')):
                raise PermissionError('Diagnostics accept repository-curated synthetic cases only.')

    def record(self, case, approach, repetition, sql, attempts=None):
        self._owner.authorize(self._services)
        # Only source plans/SQL and known synthetic case IDs. No model prose,
        # provider exceptions, results, prompts, identities or credentials.
        self.validate_cases([case])
        attempts = attempts or []
        self.rows.append({'id':case['id'], 'approach':approach, 'repeat':repetition,
                          'sql':sql, 'attempts':[
                              {k:a[k] for k in ('plan','proposed_sql','sql','validation','execution','error') if k in a}
                              for a in attempts]})

    def export(self):
        self._owner.authorize(self._services)
        return {'scope':'Raw proposed plans and SQL for benchmark-owned synthetic fixtures only.',
                'rows':self.rows}
