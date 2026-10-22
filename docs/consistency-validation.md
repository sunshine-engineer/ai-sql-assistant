<!-- File: docs/consistency-validation.md | Purpose: Source-bound validation and limitations for the project consistency change. | Maintainer: sunshine-engineer | Modified: 2026-10-23 -->

# Project consistency validation

Reviewed on 2026-10-23 on `chore/project-consistency`, starting from the local
handover-documentation commit `7921e4a`. This is a maintenance change: no prompt,
business metric, SQL policy, or frozen evaluation contract was intentionally changed.

## Changes

- All Python modules use consistent metadata, import ordering, Ruff formatting,
  and class/function/helper docstrings with argument/result/error contracts where
  applicable. Shared defaults moved to `assistant/config.py` with their previous
  values retained; no secret-loading side effects or new environment overrides.
- README directory map, configuration reference, contributor conventions, native
  text headers, adjacent artifact READMEs, and a complete file index support handover.
- The legacy student builder now lives in `scripts/build_student.py`; root
  `sqlite.py` remains a command-compatible shim. Both accept `--output`, generate
  the same five rows, and refuse an existing table. Imports no longer build data.
- Ruff is pinned at 0.14.3. CI checks lint, formatting, documentation contracts,
  parseable JSON, and archived evidence checksums before offline tests.
- JSON, CSV, SQLite, recordings, and LICENSE attribution remain unchanged; their
  formats/provenance are documented externally. Versioned evidence keeps its dates
  and source hashes; new module metadata necessarily changes current source hashes.

## Validation record

The initial existing-suite run passed **372 tests, with 2 remote-database tests
skipped**. Final verification results follow. The local environment uses Python 3.14.4; CI
and the reviewer image use Python 3.12.

| Check | Result |
| --- | --- |
| Full suite including relocated builder regressions | **375 passed, 2 skipped**, 23.79 seconds; skips require disposable PostgreSQL/MySQL endpoints. |
| Ruff lint and formatter | Passed across all 53 Python files. |
| Documentation contracts, JSON, frozen manifests | 129 project files inventoried; all 299 declared Python interfaces documented; 24 JSON files parse; 18 artifact hashes plus prospective freeze match. |
| Reference evaluation and alternate data instances | **50/50** reference cases; **144/144** instance checks; constant-query witness passes base and fails both altered instances as expected. |
| Dependency consistency | `pip check` passed; evaluation/benchmark/student-builder/capture CLI help commands passed. |
| Text configuration, examples, local links, binary integrity | TOML/YAML parse; 245 local links resolve; 19 Bash blocks pass syntax checks; 2 CSVs retain consistent row widths; 14 PNGs verify; SQLite integrity check and WebM signature pass. All retained JSON/CSV/media/database/LICENSE bytes match the parent. |
| GitHub CI on implementation commit `f6043cc` | All three jobs passed: Python 3.12 offline/lint/docs/reference checks, real disposable PostgreSQL/MySQL, and Docker build/startup/HTTP health. [Run](https://github.com/sunshine-engineer/ai-sql-assistant/actions/runs/39837829320). Subsequent edits clarify docstrings and this record; inspect final-head checks on the PR. |
| Local Docker image and real PostgreSQL/MySQL | Locally blocked: `/usr/bin/docker` exits with `Input/output error` before reaching the daemon; user is restarting Docker Desktop/WSL integration. |

An AST comparison of existing Python modules, ignoring docstrings/import ordering
and resolving extracted scalar defaults, flagged only the three intentional
repository-path extractions (`benchmark`, `benchmark_ui`, `evaluation`). Config
consolidation and the explicitly relocated legacy script were reviewed separately.
The full suite checks observable behavior; the AST comparison is supporting evidence,
not a proof of semantic equivalence.

No live provider calls or new screenshots were required for this maintenance scope.
Historical Docker/database verification is not claimed as evidence for this revision.
The new CI run above exercises fresh PostgreSQL, MySQL, and reviewer-image jobs on
`f6043cc`; final-head checks must also be inspected on this PR. Existing hosted OIDC/TLS and real-data deployment acceptance
remain outside this change, as documented in [HANDOVER.md](HANDOVER.md).

## Remaining environment check

After Docker Desktop/WSL integration is restored, rerun `docker info` once, then
run the reviewer-container and disposable-database checks from
[HANDOVER.md](HANDOVER.md). Never point the administrator test variables at a real
application database. Record results against the accepted commit and clean up only
containers created for these checks. If Docker remains unavailable, retain this
blocker explicitly and rely only on verified CI outcomes for those layers.
