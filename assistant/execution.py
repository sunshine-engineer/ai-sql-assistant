"""The only path through which model-generated SQL can execute."""
import json
import time
from sqlalchemy import inspect
import sqlglot
from sqlglot import exp
from .validation import validate_sql


class QueryService:
    def __init__(self, engine, schema=None, tables=None, max_rows=200, timeout_ms=5000):
        self.engine = engine
        self.dialect = {'postgresql': 'postgres'}.get(engine.dialect.name, engine.dialect.name)
        self.schema = schema
        self.max_rows = max_rows
        self.timeout_ms = timeout_ms
        inspector = inspect(engine)
        available = inspector.get_table_names(schema=schema)
        selected = available if tables is None else tables
        if not selected or not set(selected).issubset(available):
            raise ValueError('Select existing, approved tables.')
        self.allowed = {(schema or '', name) for name in selected}
        # Bare identifiers resolve through a fixed search path, never arbitrary schemas.
        self.allowed |= {('', name) for name in selected}
        self.description = json.dumps({name: [
            {'name': col['name'], 'type': str(col['type'])}
            for col in inspector.get_columns(name, schema=schema)
        ] for name in selected})

    def preview(self, sql):
        safe = validate_sql(sql, self.dialect, self.allowed, self.max_rows)
        tree = sqlglot.parse_one(safe, read=self.dialect)
        tables = sorted({table.sql(dialect=self.dialect) for table in tree.find_all(exp.Table)})
        return {'sql': safe, 'tables': tables}

    def query(self, sql):
        safe = self.preview(sql)['sql']
        with self.engine.connect() as connection:
            raw = None
            try:
                if self.dialect == 'postgres':
                    connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                    connection.exec_driver_sql('SET LOCAL standard_conforming_strings = on')
                    connection.exec_driver_sql(f'SET LOCAL statement_timeout = {int(self.timeout_ms)}')
                    connection.exec_driver_sql(f'SET LOCAL lock_timeout = {int(self.timeout_ms)}')
                    schema = self.schema or 'public'
                    quoted = connection.dialect.identifier_preparer.quote_identifier(schema)
                    connection.exec_driver_sql(f'SET LOCAL search_path TO {quoted}')
                elif self.dialect == 'mysql':
                    connection.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
                    # Keep server literal parsing consistent with the SQLGlot dialect.
                    connection.exec_driver_sql("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY'")
                    connection.exec_driver_sql(f'SET SESSION MAX_EXECUTION_TIME = {int(self.timeout_ms)}')
                    connection.exec_driver_sql('START TRANSACTION READ ONLY')
                elif self.dialect == 'sqlite':
                    raw = connection.connection.driver_connection
                    deadline = time.monotonic() + self.timeout_ms / 1000
                    raw.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
                else:
                    raise ValueError('Unsupported database.')
                result = connection.exec_driver_sql(safe)
                columns = list(result.keys())
                rows = result.fetchmany(self.max_rows + 1)
                payload = {'sql': safe, 'columns': columns,
                           'rows': [list(row) for row in rows[:self.max_rows]],
                           'truncated': len(rows) > self.max_rows}
                # Cap tool context as well as returned rows.
                while len(json.dumps(payload, default=str)) > 20000 and payload['rows']:
                    payload['rows'].pop()
                    payload['truncated'] = True
                if len(json.dumps(payload, default=str)) > 20000:
                    return {'sql': safe[:1000], 'columns': [], 'rows': [],
                            'truncated': True,
                            'error': 'Result metadata is too large; select fewer columns.'}
                return payload
            finally:
                if raw is not None:
                    raw.set_progress_handler(None, 0)
                connection.rollback()
