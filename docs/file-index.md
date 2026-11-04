<!-- File: docs/file-index.md | Purpose: Inventory every version-controlled project file by location, type, and purpose. | Maintainer: sunshine-engineer | Modified: 2026-10-23 -->

# Project file index

This inventory covers the checked-in project and new files in this change. Generated
virtual environments, local secrets, telemetry, retail databases, and local results
are excluded by Git ignore rules. `sunshine-engineer` is the maintenance default,
not a claim of original authorship or ownership. Native headers use 2026-10-23 for
this maintenance pass; original report dates, license attribution, binary data,
and checksum-protected JSON remain intact.

No further file moves are needed: scripts now hold maintenance implementation;
root entry points, bundled demo assets, and versioned evidence retain stable paths.
Each directory agrees with the purpose in the [README](../README.md#project-structure).

| File | Type | Purpose / handling |
| --- | --- | --- |
| [.dockerignore](../.dockerignore) | Text configuration | Explicit reviewer image build-input allowlist. |
| [.editorconfig](../.editorconfig) | Text configuration | Editor encoding, whitespace, and indentation conventions. |
| [.env.example](../.env.example) | Text configuration | Optional explicit shell environment template with no real credentials. |
| [.github/workflows/tests.yml](../.github/workflows/tests.yml) | YAML | Formatting/docs, offline evaluations, disposable database, and reviewer image CI. |
| [.gitignore](../.gitignore) | Text configuration | Secrets and generated artifact exclusions. |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Markdown | Contributing |
| [Dockerfile](../Dockerfile) | Text configuration | Restricted non-root synthetic reviewer image. |
| [LICENSE](../LICENSE) | Text configuration | Original MIT license and copyright attribution; preserved verbatim. |
| [README.md](../README.md) | Markdown | 🤖 AI SQL Assistant |
| [VALIDATION.md](../VALIDATION.md) | Markdown | Fix validation |
| [app.py](../app.py) | Python | Streamlit launcher. Run with: streamlit run app.py. |
| [assets/Chat_Interface.png](../assets/Chat_Interface.png) | PNG | Legacy UI screenshot; capture revision/author not recorded, see assets README. |
| [assets/DB_Select_MySQL.png](../assets/DB_Select_MySQL.png) | PNG | Legacy UI screenshot; capture revision/author not recorded, see assets README. |
| [assets/GR_delete_data.png](../assets/GR_delete_data.png) | PNG | Legacy UI screenshot; capture revision/author not recorded, see assets README. |
| [assets/HOME.png](../assets/HOME.png) | PNG | Legacy UI screenshot; capture revision/author not recorded, see assets README. |
| [assets/README.md](../assets/README.md) | Markdown | UI media |
| [assets/current/README.md](../assets/current/README.md) | Markdown | Recorded reviewer walkthrough |
| [assets/current/benchmark.png](../assets/current/benchmark.png) | PNG | Recorded reviewer media; see assets/current/README.md. |
| [assets/current/comparison.png](../assets/current/comparison.png) | PNG | Recorded reviewer media; see assets/current/README.md. |
| [assets/current/evaluation.png](../assets/current/evaluation.png) | PNG | Recorded reviewer media; see assets/current/README.md. |
| [assets/current/plan.png](../assets/current/plan.png) | PNG | Recorded reviewer media; see assets/current/README.md. |
| [assets/current/reviewer-demo.webm](../assets/current/reviewer-demo.webm) | WebM | Recorded reviewer media; see assets/current/README.md. |
| [assets/database_selection.png](../assets/database_selection.png) | PNG | Legacy UI screenshot; capture revision/author not recorded, see assets README. |
| [assets/db_select_psql.png](../assets/db_select_psql.png) | PNG | Legacy UI screenshot; capture revision/author not recorded, see assets README. |
| [assets/db_select_sqllite.png](../assets/db_select_sqllite.png) | PNG | Legacy UI screenshot; capture revision/author not recorded, see assets README. |
| [assets/guard_rails.png](../assets/guard_rails.png) | PNG | Legacy UI screenshot; capture revision/author not recorded, see assets README. |
| [assets/postgres_conn_window.png](../assets/postgres_conn_window.png) | PNG | Legacy UI screenshot; capture revision/author not recorded, see assets README. |
| [assets/sql_guardrails.png](../assets/sql_guardrails.png) | PNG | Legacy UI screenshot; capture revision/author not recorded, see assets README. |
| [assistant/__init__.py](../assistant/__init__.py) | Python | Build the legacy synthetic student database. |
| [assistant/access.py](../assistant/access.py) | Python | Trusted OIDC principal -> operator-managed, per-user approved view projection. |
| [assistant/answers.py](../assistant/answers.py) | Python | Result-referenced answer facts; unverified model prose is never displayed. |
| [assistant/benchmark.py](../assistant/benchmark.py) | Python | Paired, quota-admitted synthetic regressions with distinct failure layers. |
| [assistant/benchmark_ui.py](../assistant/benchmark_ui.py) | Python | Show frozen, sanitized live benchmark evidence without making provider calls. |
| [assistant/budgets.py](../assistant/budgets.py) | Python | Conservative admission budgets; no provider retries or work after exhaustion. |
| [assistant/business.py](../assistant/business.py) | Python | Versioned retail semantics and deterministic clarification/refusal checks. |
| [assistant/catalog.py](../assistant/catalog.py) | Python | Deterministic metadata selection, separate from database authorization. |
| [assistant/charts.py](../assistant/charts.py) | Python | Chart recommendations depend exclusively on executed tabular values. |
| [assistant/chat.py](../assistant/chat.py) | Python | Session history with bounded model context. |
| [assistant/config.py](../assistant/config.py) | Python | Application settings shared by the UI and runtime; no framework side effects. |
| [assistant/connections.py](../assistant/connections.py) | Python | Connection construction without credential interpolation or shared user caches. |
| [assistant/dates.py](../assistant/dates.py) | Python | Recognize explicit retail date expressions without treating polite 'May I' as dates. |
| [assistant/demo.py](../assistant/demo.py) | Python | Deterministic retail fixture. All people, transactions and targets are synthetic. |
| [assistant/demo_ui.py](../assistant/demo_ui.py) | Python | Key-free reviewer walkthrough: real SQL execution of explicit reviewed plans. |
| [assistant/deployment.py](../assistant/deployment.py) | Python | Deployment boundary: the packaged reviewer app accepts synthetic data only. |
| [assistant/diagnostics.py](../assistant/diagnostics.py) | Python | Raw plan/SQL diagnostics restricted to benchmark-owned synthetic fixtures. |
| [assistant/evaluation.py](../assistant/evaluation.py) | Python | Reference-fixture validation and opt-in live model execution-result evaluation. |
| [assistant/evaluation_ui.py](../assistant/evaluation_ui.py) | Python | Evaluation dashboard distinguishes fixture checks from actual model runs. |
| [assistant/execution.py](../assistant/execution.py) | Python | The only path through which model-generated SQL can execute. |
| [assistant/followups.py](../assistant/followups.py) | Python | Conservative month comparisons: reject extra intent and noncanonical predicates. |
| [assistant/generation.py](../assistant/generation.py) | Python | Explicit, bounded analytics workflow with inspectable attempts and safe traces. |
| [assistant/instance_checks.py](../assistant/instance_checks.py) | Python | Offline reference and mutation witnesses across multiple data instances; no model. |
| [assistant/instances.py](../assistant/instances.py) | Python | Versioned alternate synthetic instances, generated only in a fresh directory. |
| [assistant/plan_intent.py](../assistant/plan_intent.py) | Python | Conservative checks for explicit metric, grouping, region and calendar-month intent. |
| [assistant/plans.py](../assistant/plans.py) | Python | Closed retail semantic subset. Plans compile to the item-grain semantic table. |
| [assistant/presentation.py](../assistant/presentation.py) | Python | Render one turn, its query evidence and redacted operational trace. |
| [assistant/runtime.py](../assistant/runtime.py) | Python | Construct request-scoped resources and close them on success or failure. |
| [assistant/scheduling.py](../assistant/scheduling.py) | Python | Sequential benchmark quota admission, shared by both approaches and tool bindings. |
| [assistant/telemetry.py](../assistant/telemetry.py) | Python | Persistent operational counters with an explicit sanitized scalar allowlist. |
| [assistant/tracing.py](../assistant/tracing.py) | Python | Operational trace allowlist: no prompts, SQL literals, results or credentials. |
| [assistant/ui.py](../assistant/ui.py) | Python | Streamlit composition: collect settings, manage the chat, render responses. |
| [assistant/validation.py](../assistant/validation.py) | Python | Conservative SQL policy. SQL is untrusted even when generated by our model. |
| [compose.yaml](../compose.yaml) | YAML | Localhost reviewer startup and resource bounds. |
| [dataset/AllIndices_01012026.csv](../dataset/AllIndices_01012026.csv) | CSV | Legacy market CSV input; preserve original columns/values, see dataset README for provenance limits. |
| [dataset/AllIndices_02012026.csv](../dataset/AllIndices_02012026.csv) | CSV | Legacy market CSV input; preserve original columns/values, see dataset README for provenance limits. |
| [dataset/README.md](../dataset/README.md) | Markdown | Legacy market CSV inputs |
| [deployment/secrets.example.toml](../deployment/secrets.example.toml) | TOML | Placeholder OIDC/provider/per-user view grants for hosted mode. |
| [docs/HANDOVER.md](../docs/HANDOVER.md) | Markdown | Maintainer handover |
| [docs/analytics.md](../docs/analytics.md) | Markdown | Analytics workflow and evaluation |
| [docs/benchmark-reliability-status.md](../docs/benchmark-reliability-status.md) | Markdown | Benchmark reliability follow-up — 2026-10-21 |
| [docs/benchmark-report.md](../docs/benchmark-report.md) | Markdown | Measured live benchmark — 2026-10-20 |
| [docs/configuration.md](../docs/configuration.md) | Markdown | Configuration reference |
| [docs/consistency-validation.md](../docs/consistency-validation.md) | Markdown | Project consistency validation |
| [docs/documentation-audit.md](../docs/documentation-audit.md) | Markdown | Documentation audit — 2026-10-22 |
| [docs/engineering-validation.md](../docs/engineering-validation.md) | Markdown | Engineering feature validation |
| [docs/engineering.md](../docs/engineering.md) | Markdown | Measured analytics engineering |
| [docs/feature-validation.md](../docs/feature-validation.md) | Markdown | Analytics feature validation |
| [docs/file-index.md](../docs/file-index.md) | Markdown | Complete repository file inventory and header exemptions. |
| [docs/final-review-follow-up.md](../docs/final-review-follow-up.md) | Markdown | Final portfolio review follow-up |
| [docs/prospective-evaluation.md](../docs/prospective-evaluation.md) | Markdown | Prospective retail evaluation v1 |
| [evaluation/README.md](../evaluation/README.md) | Markdown | Evaluation artifacts |
| [evaluation/diagnostics/2026-10-20-triage-synthetic.json](../evaluation/diagnostics/2026-10-20-triage-synthetic.json) | JSON | Frozen suite-owned synthetic raw plan/SQL diagnostics; preserve checksum. |
| [evaluation/diagnostics/2026-10-21-final-confirmations-synthetic.json](../evaluation/diagnostics/2026-10-21-final-confirmations-synthetic.json) | JSON | Frozen suite-owned synthetic raw plan/SQL diagnostics; preserve checksum. |
| [evaluation/diagnostics/2026-10-21-prospective-v1-synthetic.json](../evaluation/diagnostics/2026-10-21-prospective-v1-synthetic.json) | JSON | Frozen suite-owned synthetic raw plan/SQL diagnostics; preserve checksum. |
| [evaluation/diagnostics/2026-10-21-r30-policy-parity-synthetic.json](../evaluation/diagnostics/2026-10-21-r30-policy-parity-synthetic.json) | JSON | Frozen suite-owned synthetic raw plan/SQL diagnostics; preserve checksum. |
| [evaluation/diagnostics/2026-10-21-stability-v3-synthetic.json](../evaluation/diagnostics/2026-10-21-stability-v3-synthetic.json) | JSON | Frozen suite-owned synthetic raw plan/SQL diagnostics; preserve checksum. |
| [evaluation/diagnostics/2026-10-21-targeted-v3-synthetic.json](../evaluation/diagnostics/2026-10-21-targeted-v3-synthetic.json) | JSON | Frozen suite-owned synthetic raw plan/SQL diagnostics; preserve checksum. |
| [evaluation/heldout_v1.json](../evaluation/heldout_v1.json) | JSON | Exposed reserved questions, retained as regressions. |
| [evaluation/infrastructure-validation-2026-10-21.json](../evaluation/infrastructure-validation-2026-10-21.json) | JSON | Historical revision-bound Docker and remote database verification. |
| [evaluation/operational-summary.json](../evaluation/operational-summary.json) | JSON | Historical sanitized operational aggregate sample. |
| [evaluation/prospective-v1-freeze.json](../evaluation/prospective-v1-freeze.json) | JSON | Pre-run prospective protocol, suite hash, and historical source fingerprint. |
| [evaluation/prospective-v1-results-manifest.json](../evaluation/prospective-v1-results-manifest.json) | JSON | Prospective report, diagnostics, freeze, and suite checksums. |
| [evaluation/prospective_v1.json](../evaluation/prospective_v1.json) | JSON | Frozen same-author prospective questions and expected results. |
| [evaluation/report-manifest.json](../evaluation/report-manifest.json) | JSON | Original benchmark report hashes and interpretation notes. |
| [evaluation/reports/2026-10-20-development.json](../evaluation/reports/2026-10-20-development.json) | JSON | Frozen dated live benchmark report; preserve bytes and recorded successes/failures. |
| [evaluation/reports/2026-10-20-heldout.json](../evaluation/reports/2026-10-20-heldout.json) | JSON | Frozen dated live benchmark report; preserve bytes and recorded successes/failures. |
| [evaluation/reports/2026-10-20-paced-pilot.json](../evaluation/reports/2026-10-20-paced-pilot.json) | JSON | Frozen dated live benchmark report; preserve bytes and recorded successes/failures. |
| [evaluation/reports/2026-10-20-triage.json](../evaluation/reports/2026-10-20-triage.json) | JSON | Frozen dated live benchmark report; preserve bytes and recorded successes/failures. |
| [evaluation/reports/2026-10-21-final-confirmations.json](../evaluation/reports/2026-10-21-final-confirmations.json) | JSON | Frozen dated live benchmark report; preserve bytes and recorded successes/failures. |
| [evaluation/reports/2026-10-21-prospective-v1.json](../evaluation/reports/2026-10-21-prospective-v1.json) | JSON | Frozen dated live benchmark report; preserve bytes and recorded successes/failures. |
| [evaluation/reports/2026-10-21-r30-policy-parity.json](../evaluation/reports/2026-10-21-r30-policy-parity.json) | JSON | Frozen dated live benchmark report; preserve bytes and recorded successes/failures. |
| [evaluation/reports/2026-10-21-stability-v3.json](../evaluation/reports/2026-10-21-stability-v3.json) | JSON | Frozen dated live benchmark report; preserve bytes and recorded successes/failures. |
| [evaluation/reports/2026-10-21-targeted-v3.json](../evaluation/reports/2026-10-21-targeted-v3.json) | JSON | Frozen dated live benchmark report; preserve bytes and recorded successes/failures. |
| [evaluation/retail_v1.json](../evaluation/retail_v1.json) | JSON | 50 versioned retail regression questions and expected results. |
| [evaluation/triage-manifest.json](../evaluation/triage-manifest.json) | JSON | Triage/recovery report and diagnostic checksums. |
| [pyproject.toml](../pyproject.toml) | TOML | Pinned Ruff formatting/import/docstring configuration. |
| [requirements-browser.txt](../requirements-browser.txt) | Requirements | Optional pinned Playwright capture tooling. |
| [requirements-dev.txt](../requirements-dev.txt) | Requirements | Runtime plus pytest and pinned Ruff development checks. |
| [requirements.txt](../requirements.txt) | Requirements | Pinned application runtime dependencies. |
| [scripts/__init__.py](../scripts/__init__.py) | Python | Maintenance commands; importing this package performs no work. |
| [scripts/build_student.py](../scripts/build_student.py) | Python | Build the legacy five-row synthetic student fixture in a new database. |
| [scripts/capture_demo.py](../scripts/capture_demo.py) | Python | Capture the actual localhost UI. Requires Playwright and Chromium, no provider key. |
| [scripts/check_consistency.py](../scripts/check_consistency.py) | Python | Check documented Python interfaces, file metadata, and frozen evidence hashes. |
| [sql_queries.sql](../sql_queries.sql) | psql/SQL | Fresh PostgreSQL administrator bootstrap, read-only role, and legacy CSV example queries. |
| [sqlite.py](../sqlite.py) | Python | Compatibility launcher; maintenance implementation is scripts/build_student.py. |
| [student.db](../student.db) | SQLite | Bundled five-row synthetic student database; preserve bytes, read-only at runtime. |
| [tests/conftest.py](../tests/conftest.py) | Python | Shared real SQLite retail fixture; no live model or external database needed. |
| [tests/test_analytics.py](../tests/test_analytics.py) | Python | Analytics contracts use real deterministic data and a scripted provider. |
| [tests/test_answer_faithfulness.py](../tests/test_answer_faithfulness.py) | Python | Numeric claims must identify an actual cell; correct SQL alone is insufficient. |
| [tests/test_app.py](../tests/test_app.py) | Python | Regression checks for app. |
| [tests/test_benchmark_reliability.py](../tests/test_benchmark_reliability.py) | Python | Regression checks for benchmark reliability. |
| [tests/test_chat.py](../tests/test_chat.py) | Python | Regression checks for chat. |
| [tests/test_comparison_and_dates.py](../tests/test_comparison_and_dates.py) | Python | Regression cases from review: intent changes, date polarity and courtesy phrasing. |
| [tests/test_engineering.py](../tests/test_engineering.py) | Python | Regression checks for engineering. |
| [tests/test_final_review.py](../tests/test_final_review.py) | Python | Regression checks for final review. |
| [tests/test_integration.py](../tests/test_integration.py) | Python | Optional real-server tests. CI supplies disposable PostgreSQL/MySQL services. |
| [tests/test_maintenance.py](../tests/test_maintenance.py) | Python | Verify relocated maintenance commands preserve legacy fixture behavior. |
| [tests/test_remote_controls.py](../tests/test_remote_controls.py) | Python | Regression checks for remote controls. |
| [tests/test_runtime.py](../tests/test_runtime.py) | Python | Resource lifecycle contracts independent of Streamlit and live providers. |
| [tests/test_safety.py](../tests/test_safety.py) | Python | Regression checks for safety. |
