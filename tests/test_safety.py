import sqlite3
import pytest
from sqlalchemy import event
from sqlalchemy.exc import DBAPIError
from assistant.connections import open_engine, connection_url
from assistant.execution import QueryService
from assistant.validation import validate_sql, UnsafeSQL


@pytest.fixture
def service(tmp_path):
    path = tmp_path / 'fixture.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE students (name TEXT, marks INTEGER)')
        db.executemany('INSERT INTO students VALUES (?,?)', [('A', 90), ('B', 50), ('C', 80)])
        db.execute('CREATE TABLE secrets (token TEXT)')
    engine = open_engine('sqlite', path=path)
    yield QueryService(engine, tables=['students'], max_rows=2)
    engine.dispose()


@pytest.mark.parametrize('sql', [
    'DELETE FROM students', 'SELECT * FROM students; DROP TABLE students',
    'SELECT * INTO other FROM students', 'SELECT * FROM students FOR UPDATE',
    'SELECT * FROM secrets', 'SELECT * FROM main.students',
    'SELECT * FROM sqlite_master', "SELECT load_extension('x')",
    "SELECT pg_read_file('/etc/passwd')", 'SELECT pg_sleep(10)',
    "SELECT readfile('/etc/passwd')", 'SELECT randomblob(1000000000)',
    'SELECT public.count(*) FROM students', 'SELECT * FROM students -- hint',
    'WITH x AS (DELETE FROM students RETURNING *) SELECT * FROM x',
    'WITH RECURSIVE x AS (SELECT 1) SELECT * FROM x',
    'PRAGMA query_only=OFF', "ATTACH DATABASE '/tmp/x' AS x",
    'SELECT * FROM students UNION SELECT * FROM secrets',
    'SELECT * FROM students LIMIT -1', 'SELECT CAST(1 AS custom_type)',
    'SELECT * FROM students TABLESAMPLE SYSTEM(50)', 'SELECT * FROM students LIMIT ?',
])
def test_reject_before_execution(service, sql):
    executed = []
    event.listen(service.engine, 'before_cursor_execute', lambda *args: executed.append(args[2]))
    with pytest.raises(UnsafeSQL):
        service.query(sql)
    assert executed == []


def test_rows_and_aggregate(service):
    result = service.query('SELECT name, marks FROM students ORDER BY marks DESC')
    assert result['rows'] == [['A', 90], ['C', 80]]
    assert result['truncated'] is True
    assert service.query('SELECT COUNT(*) AS n FROM students')['rows'] == [[3]]
    assert service.query('SELECT name FROM students LIMIT 1')['rows'] == [['A']]


def test_joins_and_subqueries(service):
    result = service.query('SELECT s.name FROM students s JOIN students t ON s.name=t.name WHERE s.marks > (SELECT AVG(marks) FROM students) ORDER BY s.name')
    assert result['rows'] == [['A'], ['C']]


def test_sqlite_connection_is_read_only(service):
    with service.engine.connect() as db:
        db.exec_driver_sql('PRAGMA query_only=OFF')
        with pytest.raises(DBAPIError):
            db.exec_driver_sql("INSERT INTO students VALUES ('D', 1)")
    assert service.query('SELECT COUNT(*) FROM students')['rows'] == [[3]]


def test_sqlite_timeout(service):
    service.timeout_ms = 0
    with pytest.raises(DBAPIError):
        service.query('SELECT COUNT(*) FROM students a CROSS JOIN students b CROSS JOIN students c CROSS JOIN students d CROSS JOIN students e')
    service.timeout_ms = 5000
    assert service.query('SELECT COUNT(*) FROM students')['rows'] == [[3]]


@pytest.mark.parametrize('kind', ['postgres', 'mysql'])
def test_url_special_characters(kind):
    password = 'a@b:/?#% secret'
    url = connection_url(kind, 'localhost', '5432', 'user@name', password, 'demo')
    assert url.password == password
    assert url.username == 'user@name'
    assert url.host == 'localhost'
    assert password not in str(url)


@pytest.mark.parametrize('dialect', ['postgres', 'mysql', 'sqlite'])
def test_dialect_validation(dialect):
    assert 'LIMIT 201' in validate_sql('SELECT COUNT(*) FROM students', dialect, {('', 'students')})


@pytest.mark.parametrize('sql', [
    "SELECT * FROM students INTO OUTFILE '/tmp/leak'",
    'SELECT @x := 1', 'SELECT /*+ MAX_EXECUTION_TIME(999999) */ * FROM students',
    'SELECT SLEEP(5)', 'SELECT BENCHMARK(999999, 1)',
    "SELECT LOAD_FILE('/etc/passwd')", 'SELECT @@version',
])
def test_mysql_special_constructs(sql):
    with pytest.raises(UnsafeSQL):
        validate_sql(sql, 'mysql', {('', 'students')})


def test_postgres_date_aggregation():
    query = validate_sql("SELECT DATE_TRUNC('month', trade_date), AVG(marks) FROM students GROUP BY DATE_TRUNC('month', trade_date)", 'postgres', {('', 'students')})
    assert 'DATE_TRUNC' in query


def test_oversized_tool_result_is_marked_partial(service):
    result = service.query("SELECT '" + ('x' * 19900) + "' AS a FROM students")
    assert result['truncated']
    assert len(result['rows']) == 0  # SQL text and one row together exceed the context budget.


def test_oversized_column_metadata_cannot_overflow_context(service):
    import json
    result = service.query("SELECT '" + ('x' * 15000) + "' FROM students")
    assert len(json.dumps(result, default=str)) <= 20000
    assert result['truncated']


@pytest.mark.parametrize('kind', ['postgres', 'mysql'])
def test_required_driver_loads_without_connecting(kind):
    engine = open_engine(kind, host='localhost', port=5432 if kind == 'postgres' else 3306,
                         user='reader', password='special@:/?#%', database='demo')
    try:
        assert engine.url.password == 'special@:/?#%'
        assert engine.dialect.dbapi is not None
    finally:
        engine.dispose()



def test_compound_filters_allow_logic_but_still_check_nested_functions(service):
    assert service.query("SELECT name FROM students WHERE marks > 80 AND name = 'A'")['rows'] == [['A']]
    assert service.query("SELECT name FROM students WHERE name = 'A' OR name = 'B' ORDER BY name")['rows'] == [['A'],['B']]
    with pytest.raises(UnsafeSQL):
        service.query("SELECT name FROM students WHERE marks > 80 OR load_extension('bad') IS NULL")
