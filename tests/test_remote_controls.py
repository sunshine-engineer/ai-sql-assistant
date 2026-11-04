"""Regression checks for remote controls.

File: tests/test_remote_controls.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

from unittest.mock import MagicMock as Mock

import pytest

from assistant.execution import QueryService


@pytest.mark.parametrize(
    "dialect,expected",
    [
        (
            "postgres",
            [
                "SET TRANSACTION READ ONLY",
                "SET LOCAL standard_conforming_strings = on",
                "SET LOCAL statement_timeout = 5000",
                "SET LOCAL lock_timeout = 5000",
                'SET LOCAL search_path TO "genai"',
            ],
        ),
        (
            "mysql",
            [
                "SET SESSION TRANSACTION READ ONLY",
                "SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY'",
                "SET SESSION MAX_EXECUTION_TIME = 5000",
                "START TRANSACTION READ ONLY",
            ],
        ),
    ],
)
def test_controls_precede_generated_sql_and_rollback(dialect, expected):
    """Verify controls precede generated sql and rollback.

    Args:
        dialect: SQLGlot dialect name: sqlite, postgres, or mysql.
        expected: Expected explicit intent fields or routing requirements.
    """
    service = object.__new__(QueryService)
    service.dialect = dialect
    service.schema = "genai" if dialect == "postgres" else None
    service.max_rows = 200
    service.timeout_ms = 5000
    service.allowed = {("", "students")}
    service.engine = Mock()
    connection = service.engine.connect.return_value.__enter__.return_value
    connection.dialect.identifier_preparer.quote_identifier.return_value = '"genai"'
    connection.exec_driver_sql.return_value.keys.return_value = ["n"]
    connection.exec_driver_sql.return_value.fetchmany.return_value = [(3,)]
    assert service.query("SELECT COUNT(*) FROM students")["rows"] == [[3]]
    executed = [call.args[0] for call in connection.exec_driver_sql.call_args_list]
    assert executed[:-1] == expected
    assert executed[-1].startswith("SELECT COUNT(*)")
    connection.rollback.assert_called_once()


def test_remote_setup_failure_never_executes_query():
    """Verify remote setup failure never executes query."""
    service = object.__new__(QueryService)
    service.dialect = "mysql"
    service.max_rows = 200
    service.timeout_ms = 5000
    service.allowed = {("", "students")}
    service.engine = Mock()
    connection = service.engine.connect.return_value.__enter__.return_value
    connection.exec_driver_sql.side_effect = RuntimeError("read-only setting failed")
    with pytest.raises(RuntimeError):
        service.query("SELECT * FROM students")
    assert connection.exec_driver_sql.call_count == 1
    connection.rollback.assert_called_once()
