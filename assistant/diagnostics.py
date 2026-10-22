"""Raw plan/SQL diagnostics restricted to benchmark-owned synthetic fixtures.

File: assistant/diagnostics.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import tempfile
from contextlib import contextmanager

from .connections import open_engine
from .demo import TABLES
from .execution import QueryService
from .instances import INSTANCES, build_instance


class SyntheticSuite:
    """Own disposable synthetic databases and authorize diagnostic capture by resource identity."""

    def __init__(self):
        """Initialize an inactive owner of disposable synthetic resources."""
        self._directory = None
        self.services = {}
        self._engines = {}

    def __enter__(self):
        """Build and yield suite-owned services for every synthetic instance.

        Returns:
            SyntheticSuite: Active owner containing services for all synthetic instances.
        """
        self._directory = tempfile.TemporaryDirectory(prefix="synthetic-benchmark-")
        try:
            for name in INSTANCES:
                path = build_instance(self._directory.name, name)
                engine = open_engine("sqlite", path=path)
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
        """Dispose synthetic engines and remove their temporary database directory."""
        for engine in self._engines.values():
            engine.dispose()
        self._engines.clear()
        self.services.clear()
        if self._directory:
            self._directory.cleanup()
            self._directory = None

    def __exit__(self, *args):
        """Dispose owned engines and remove temporary fixtures on context exit.

        Args:
            *args: Additional context-manager exception details.
        """
        self.close()

    def authorize(self, services):
        # Identity and ownership, not a boolean retail marker or a filename prefix.
        """Verify that every supplied service belongs to this active synthetic suite.

        Args:
            services: Mapping from synthetic instance names to their controlled query services.

        Raises:
            PermissionError: If services are not owned by this active suite.
        """
        if self._directory is None or set(services) != set(self.services):
            raise PermissionError("Diagnostics require an active benchmark-owned synthetic suite.")
        if any(
            services[name] is not service or service.engine is not self._engines[name]
            for name, service in self.services.items()
        ):
            raise PermissionError("Diagnostics cannot capture arbitrary database services.")

    @contextmanager
    def capture(self, services):
        """Yield a diagnostic collector scoped to the active suite-owned services.

        Args:
            services: Mapping from synthetic instance names to their controlled query services.

        Yields:
            SyntheticDiagnostics: Collector authorized for this active synthetic suite.
        """
        self.authorize(services)
        yield SyntheticDiagnostics(self, services)


class SyntheticDiagnostics:
    """Collect raw plans and SQL exclusively for curated synthetic benchmark cases."""

    def __init__(self, owner, services):
        """Attach diagnostic collection to suite-owned services.

        Args:
            owner: SyntheticSuite that owns and authorizes the diagnostic resources.
            services: Mapping from synthetic instance names to their controlled query services.
        """
        self._owner = owner
        self._services = services
        self.rows = []

    def validate_cases(self, cases):
        """Reject cases whose identity or query contract differs from the repository suite.

        Args:
            cases: Selected versioned cases with expected outcomes and reference SQL or rows.

        Raises:
            PermissionError: If a case is not an unchanged curated synthetic question contract.
        """
        from .benchmark import suites

        known = {c["id"]: c for group in suites(include_prospective=True).values() for c in group}
        for case in cases:
            source = known.get(case.get("id"))
            if not source or any(
                case.get(k) != source.get(k) for k in ("question", "gold_sql", "expected_outcome")
            ):
                raise PermissionError("Diagnostics accept repository-curated synthetic cases only.")

    def record(self, case, approach, repetition, sql, attempts=None):
        """Record curated synthetic proposed plans and SQL after checking ownership.

        Args:
            case: One versioned question contract with expected result or control outcome.
            approach: Benchmark approach label, workflow or one_shot.
            repetition: One-based benchmark repetition number.
            sql: Untrusted SQL text to validate before any execution.
            attempts: Inspectable workflow attempts restricted to synthetic diagnostic fields.
        """
        self._owner.authorize(self._services)
        # Only source plans/SQL and known synthetic case IDs. No model prose,
        # provider exceptions, results, prompts, identities or credentials.
        self.validate_cases([case])
        attempts = attempts or []
        self.rows.append(
            {
                "id": case["id"],
                "approach": approach,
                "repeat": repetition,
                "sql": sql,
                "attempts": [
                    {
                        k: a[k]
                        for k in ("plan", "proposed_sql", "sql", "validation", "execution", "error")
                        if k in a
                    }
                    for a in attempts
                ],
            }
        )

    def export(self):
        """Export synthetic-only proposed plans and SQL after rechecking ownership.

        Returns:
            dict: Sanitized operational metadata.
        """
        self._owner.authorize(self._services)
        return {
            "scope": "Raw proposed plans and SQL for benchmark-owned synthetic fixtures only.",
            "rows": self.rows,
        }
