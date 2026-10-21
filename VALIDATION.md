# Fix validation

Outline: scope, executed checks, issue coverage, remaining integration checks.

**2026-10-21 follow-up:** real PostgreSQL/MySQL integration is now verified; all
351 tests passed with both database endpoints enabled. See the
[current reliability record](docs/benchmark-reliability-status.md) for live-model
confirmations and Docker verification. The historical results below are retained.

## Scope

Branch: `fix/sql-safety-and-chat`, based on `84bcc3e`.

All seven review categories are addressed.
No remote database permissions or data were changed.

## Executed on 2026-10-20

Isolated temporary Python 3.14 environment, with dependencies installed from
`requirements-dev.txt`:

```text
python -m pytest -q
57 passed, 2 skipped in 1.75s

python -m pip check
No broken requirements found.

git diff --check
Passed
```

Python compilation also passed for the entry point, modules and tests.

## Coverage

| Review finding | Implementation | Executed evidence |
| --- | --- | --- |
| Unchecked generated SQL | One query tool, SQLGlot AST checks, schema/table/function policy, read-only execution, timeout, row/context/tool budgets | Unsafe statements rejected before any SQL execution; real SQLite SELECT/join/aggregate results, write refusal, timeout and result truncation; fake-model-to-real-database refusal/recovery test |
| Excessive PostgreSQL grants | Separate loader/reader bootstrap; client-side psql copy; no server-file role or reader write grants | Source reviewed; remote bootstrap not executed locally |
| Duplicate messages | One user append/render and one assistant append/render per turn | Presentation regression and Streamlit AppTest |
| Missing conversational context | Eight-message context with 2,000-character message caps; connection/schema changes clear history | Model-message inspection, reset tests, Streamlit AppTest |
| Missing driver/unsafe URLs | Installed MySQL connector and binary psycopg; SQLAlchemy URL.create | Special-character credentials round-trip correctly; both DBAPI drivers load without connecting |
| Misleading streaming claim | Buffered model invocation, accurate UI and README | AppTest and code/documentation review |
| Missing modules/tests/CI | Six focused modules, offline suite, GitHub Actions offline and database-service jobs | Local suite executed; CI definition reviewed but not run remotely |

Remote-control unit tests verify ordering of read-only transactions, timeouts,
fixed string parsing and rollback, and verify that setup failure prevents query
execution. These are mocks, not proof that a remote server enforces those settings.

## Remaining integration checks

- The two skipped tests require disposable PostgreSQL/MySQL endpoints. Docker is
  not available to this WSL distro. CI provisions PostgreSQL 16 and MySQL 8;
  tests cover actual reader permissions, query results and expensive-query timeouts.
- This document records local verification before publication. Consult the pull
  request checks for subsequent CI results.
- Live Groq calls were not made. Fake-model tests exercise tool routing and chat
  behavior, not provider availability, model compatibility or answer accuracy.
- `sql_queries.sql` is a fresh-database psql bootstrap, not an existing-role
  migration. Existing broad credentials require a separately audited transition
  to the new restricted reader. It has not been executed against a live server.

The policy deliberately rejects CTEs, set operations, comments, custom types,
locking clauses, session variables and unapproved functions. Database SELECT-only
permissions remain required; parser validation is defense in depth.

## Modular structure follow-up

The entry point is now a five-line launcher. `assistant/config.py` defines
application settings/defaults, `assistant/ui.py` composes the Streamlit interface,
and `assistant/runtime.py` owns database/model initialization and engine cleanup.
The existing SQL safety, generation, chat and presentation modules are retained.

Local validation after this refactor: **63 passed, 2 skipped** on Python 3.14;
`pip check`, Python compilation and `git diff --check` passed. New tests verify
resource disposal after success, schema/model initialization errors and request
failures, and verify that configuration representations hide credentials.
Existing Streamlit and SQL safety regressions pass without behavior changes.
The two skips remain live PostgreSQL/MySQL tests; consult PR checks for CI results
against disposable database services on the latest commit.
