"""The only path through which model-generated SQL can execute.

File: assistant/execution.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import json
import time

import sqlglot
from sqlalchemy import inspect
from sqlglot import exp

from .catalog import select_catalog
from .config import DEFAULT_QUERY_ROWS, DEFAULT_QUERY_TIMEOUT_MS
from .validation import UnsafeSQL, validate_sql


class QueryService:
    """Discover approved metadata and enforce validation and execution limits for every query."""

    def __init__(
        self,
        engine,
        schema=None,
        tables=None,
        max_rows=DEFAULT_QUERY_ROWS,
        timeout_ms=DEFAULT_QUERY_TIMEOUT_MS,
        approved_columns=None,
        budget=None,
    ):
        """Discover approved schema metadata and establish query execution limits.

        Args:
            engine: SQLAlchemy engine whose selected tables or views may be queried.
            schema: Optional approved remote schema name.
            tables: Selected existing table or view names; None selects the discovered catalog.
            max_rows: Maximum number of rows exposed to the caller.
            timeout_ms: Execution deadline in milliseconds; query calls may shorten the service limit.
            approved_columns: Optional operator-approved projection for each selected view.
            budget: RequestBudget shared by setup, provider admission, and execution.

        Raises:
            ValueError: If selected tables are empty or unavailable.
            PermissionError: If approved projections do not cover every selected view.
            BudgetExceeded: If schema discovery exhausts the request deadline.
        """
        self.request_budget = budget
        if budget:
            budget.remaining_seconds()
        self.engine = engine
        self.dialect = {"postgresql": "postgres"}.get(engine.dialect.name, engine.dialect.name)
        self.schema = schema
        self.max_rows = max_rows
        self.timeout_ms = timeout_ms
        self.approved_columns = approved_columns
        inspector = inspect(engine)
        available = inspector.get_table_names(schema=schema) + inspector.get_view_names(
            schema=schema
        )
        selected = available if tables is None else tables
        if not selected or not set(selected).issubset(available):
            raise ValueError("Select existing, approved tables.")
        self.allowed = {(schema or "", name) for name in selected}
        # Bare identifiers resolve through a fixed search path, never arbitrary schemas.
        self.allowed |= {("", name) for name in selected}
        self.catalog = {}
        for name in selected:
            if budget:
                budget.remaining_seconds()
            self.catalog[name] = [
                {"name": col["name"], "type": str(col["type"])}
                for col in inspector.get_columns(name, schema=schema)
            ]
        if budget:
            budget.remaining_seconds()
        if approved_columns is not None:
            if set(approved_columns) != set(selected):
                raise PermissionError("Every selected view needs a projection.")
            self.provider_catalog = {
                name: [c for c in self.catalog[name] if c["name"] in approved_columns[name]]
                for name in selected
            }
        else:
            self.provider_catalog = self.catalog
        self.description = json.dumps(self.provider_catalog)

    def describe(self, question):
        """Serialize only the bounded, relevant provider-visible schema metadata.

        Args:
            question: Current natural-language analysis request.

        Returns:
            str: JSON metadata selected for the current question.
        """
        return json.dumps(select_catalog(self.provider_catalog, question))

    def preview(self, sql):
        """Validate SQL and restricted projections, returning normalized SQL and referenced tables.

        Args:
            sql: Untrusted SQL text to validate before any execution.

        Returns:
            dict: Validated SQL and referenced table names; no execution occurs.

        Raises:
            UnsafeSQL: If SQL violates the execution policy, projection, or retail refund-join contract.
        """
        safe = validate_sql(sql, self.dialect, self.allowed, self.max_rows)
        tree = sqlglot.parse_one(safe, read=self.dialect)
        if getattr(self, "approved_columns", None) is not None:
            from .access import validate_projection

            validate_projection(tree, self.catalog, self.approved_columns)
        tables = sorted({table.sql(dialect=self.dialect) for table in tree.find_all(exp.Table)})
        if getattr(self, "retail", False):
            for select in tree.find_all(exp.Select):
                # Refund rows are one-to-many. Raw joins bypass the item-grain
                # contract; use sales_facts for joined refund analyses.
                if select.args.get("joins") and any(
                    t.name == "refunds" for t in select.find_all(exp.Table)
                ):
                    raise UnsafeSQL("Retail refund joins require the canonical sales_facts table.")
        return {"sql": safe, "tables": tables}

    def query(self, sql, timeout_ms=None):
        """Execute a validated SELECT in a read-only transaction with row, time, and context limits.

        Args:
            sql: Untrusted SQL text to validate before any execution.
            timeout_ms: Execution deadline in milliseconds; query calls may shorten the service limit.

        Returns:
            dict: SQL, columns, bounded rows, truncation flag, and optional metadata error.

        Raises:
            UnsafeSQL: If SQL is rejected before execution.
            SQLAlchemyError: If connection setup, database execution, or rollback fails.
            ValueError: If the engine dialect is unsupported.
        """
        safe = self.preview(sql)["sql"]
        timeout_ms = min(self.timeout_ms, timeout_ms) if timeout_ms is not None else self.timeout_ms
        with self.engine.connect() as connection:
            raw = None
            try:
                if self.dialect == "postgres":
                    connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                    connection.exec_driver_sql("SET LOCAL standard_conforming_strings = on")
                    connection.exec_driver_sql(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
                    connection.exec_driver_sql(f"SET LOCAL lock_timeout = {int(timeout_ms)}")
                    schema = self.schema or "public"
                    quoted = connection.dialect.identifier_preparer.quote_identifier(schema)
                    connection.exec_driver_sql(f"SET LOCAL search_path TO {quoted}")
                elif self.dialect == "mysql":
                    connection.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
                    # Keep server literal parsing consistent with the SQLGlot dialect.
                    connection.exec_driver_sql(
                        "SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY'"
                    )
                    connection.exec_driver_sql(
                        f"SET SESSION MAX_EXECUTION_TIME = {int(timeout_ms)}"
                    )
                    connection.exec_driver_sql("START TRANSACTION READ ONLY")
                elif self.dialect == "sqlite":
                    raw = connection.connection.driver_connection
                    deadline = time.monotonic() + timeout_ms / 1000
                    raw.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
                else:
                    raise ValueError("Unsupported database.")
                result = connection.exec_driver_sql(safe)
                columns = list(result.keys())
                rows = result.fetchmany(self.max_rows + 1)
                payload = {
                    "sql": safe,
                    "columns": columns,
                    "rows": [list(row) for row in rows[: self.max_rows]],
                    "truncated": len(rows) > self.max_rows,
                }
                # Cap tool context as well as returned rows.
                while len(json.dumps(payload, default=str)) > 20000 and payload["rows"]:
                    payload["rows"].pop()
                    payload["truncated"] = True
                if len(json.dumps(payload, default=str)) > 20000:
                    return {
                        "sql": safe[:1000],
                        "columns": [],
                        "rows": [],
                        "truncated": True,
                        "error": "Result metadata is too large; select fewer columns.",
                    }
                return payload
            finally:
                if raw is not None:
                    raw.set_progress_handler(None, 0)
                connection.rollback()
