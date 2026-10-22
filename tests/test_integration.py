"""Optional real-server tests. CI supplies disposable PostgreSQL/MySQL services.

File: tests/test_integration.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError

from assistant.connections import open_engine
from assistant.execution import QueryService


@pytest.fixture(params=["postgres", "mysql"])
def remote(request):
    """Yield a disposable restricted remote database service when integration credentials exist.

    Args:
        request: Pytest fixture request selecting the remote database kind.

    Yields:
        Temporary test resource, disposed when the fixture scope exits.
    """
    kind = request.param
    admin_url = os.environ.get(f"TEST_{kind.upper()}_ADMIN_URL")
    if not admin_url:
        pytest.skip(f"No disposable {kind} endpoint configured")
    admin = create_engine(admin_url)
    with admin.begin() as db:
        if kind == "postgres":
            db.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS test_analytics")
            db.exec_driver_sql("DROP TABLE IF EXISTS test_analytics.students")
            db.exec_driver_sql("CREATE TABLE test_analytics.students (marks INTEGER)")
            db.exec_driver_sql("INSERT INTO test_analytics.students SELECT generate_series(1,1000)")
            db.exec_driver_sql(
                "CREATE ROLE test_reader LOGIN PASSWORD 'disposable-reader' NOSUPERUSER NOCREATEDB NOCREATEROLE"
            )
            db.exec_driver_sql("GRANT USAGE ON SCHEMA test_analytics TO test_reader")
            db.exec_driver_sql("GRANT SELECT ON test_analytics.students TO test_reader")
        else:
            db.exec_driver_sql("DROP TABLE IF EXISTS students")
            db.exec_driver_sql("CREATE TABLE students (marks INTEGER)")
            db.exec_driver_sql(
                "INSERT INTO students VALUES " + ",".join(f"({i})" for i in range(1000))
            )
            db.exec_driver_sql("CREATE USER 'test_reader'@'%' IDENTIFIED BY 'disposable-reader'")
            db.exec_driver_sql("GRANT SELECT ON testdb.students TO 'test_reader'@'%'")
    url = admin.url
    engine = open_engine(
        kind,
        host=url.host,
        port=url.port,
        user="test_reader",
        password="disposable-reader",
        database=url.database,
    )
    service = QueryService(
        engine,
        schema="test_analytics" if kind == "postgres" else None,
        tables=["students"],
        max_rows=2,
        timeout_ms=50,
    )
    yield service
    engine.dispose()
    with admin.begin() as db:
        if kind == "postgres":
            db.exec_driver_sql("DROP SCHEMA test_analytics CASCADE")
            db.exec_driver_sql("DROP ROLE test_reader")
        else:
            db.exec_driver_sql("DROP TABLE students")
            db.exec_driver_sql("DROP USER 'test_reader'@'%'")
    admin.dispose()


def test_real_remote_permissions_results_and_timeout(remote):
    """Verify real remote permissions results and timeout.

    Args:
        remote: Disposable restricted PostgreSQL or MySQL fixture.
    """
    assert remote.query("SELECT COUNT(*) FROM students")["rows"] == [[1000]]
    assert remote.query("SELECT * FROM students")["truncated"]
    # Even bypassing our SQL parser, the database reader cannot write.
    table = "test_analytics.students" if remote.dialect == "postgres" else "students"
    with remote.engine.connect() as db:
        with pytest.raises(DBAPIError):
            db.exec_driver_sql(f"DELETE FROM {table}")
        db.rollback()
    with pytest.raises(DBAPIError):
        # A bare COUNT can be optimized without enumerating the Cartesian product.
        remote.query(
            "SELECT SUM(ABS(a.marks - b.marks + c.marks - d.marks)) FROM students a CROSS JOIN students b CROSS JOIN students c CROSS JOIN students d"
        )
    assert remote.query("SELECT COUNT(*) FROM students")["rows"] == [[1000]]
