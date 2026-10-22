# Maintainer handover

Reviewed: **2026-10-22**. Scope: the personal portfolio/reviewer prototype and
maintainer transfer. This is not approval to operate real data in a public service.

Outline: status and document map → setup → configuration → architecture →
validation → operations/recovery → acceptance and transfer.

## Status and source of truth

This guide describes application source at `b8e99ca` (PR #5), plus the documentation
and explicit Docker-context entry on `docs/handover-readiness`. It does not assert
that these changes are on `main`. Recheck branch tips before accepting a transfer.

GitHub checked on 2026-10-22: [PR #3](https://github.com/sunshine-engineer/ai-sql-assistant/pull/3),
[PR #4](https://github.com/sunshine-engineer/ai-sql-assistant/pull/4) and
[PR #5](https://github.com/sunshine-engineer/ai-sql-assistant/pull/5) are open.
PR #5's six recorded checks pass: offline, real database and reviewer-container
jobs for its push and pull-request events. Those checks validate its revision,
not uncommitted documentation, future merges or this branch's context adjustment.
Merge/review is an owner action: #3 → #4 → #5, retargeting dependents to main and
checking their final diffs/checks. Include the handover documentation afterward.
Do not merge a dependent PR directly into a prerequisite branch unintentionally.

| Document | Role |
| --- | --- |
| [README](../README.md) | Reviewer entry point, walkthrough, concise features and commands. |
| This guide | Current operator/maintainer instructions and acceptance checklist. |
| [Analytics](analytics.md) | Data semantics, query evidence, follow-ups, answer checks and privacy. |
| [Engineering](engineering.md) | Canonical compiler, budgets, metadata selection and hosted boundaries. |
| [Prospective evaluation](prospective-evaluation.md) | Frozen protocol, authorship limit, run results and reproduction. |
| [Final review follow-up](final-review-follow-up.md) | PR #5's correctness fixes and validation snapshot. |
| [Reliability log](benchmark-reliability-status.md) | Historical investigation, failures and later confirmations. |
| [Initial benchmark report](benchmark-report.md) | Historical measured runs; not the latest overall score. |
| [Initial validation](../VALIDATION.md), [feature validation](feature-validation.md), [engineering validation](engineering-validation.md) | Dated historical milestones. Counts/old pending lists are not current acceptance status. |
| [Recorded assets](../assets/current/README.md) | Model-free video/screenshots and capture instructions. |
| [Audit](documentation-audit.md) | What was reviewed, corrected, checked and left externally unverified. |

## Quick start: synthetic reviewer

Run commands from the repository root. Docker Desktop/Engine and Compose must be
running and accessible to the current user. The package binds to localhost only.
No provider key is required for Plan demo, reference Evaluation or recorded Benchmarks.

```bash
docker compose up --build --detach --wait --wait-timeout 120
curl --fail http://127.0.0.1:8501/_stcore/health
# Open http://127.0.0.1:8501
```

In Plan demo, execute a reviewed plan, inspect SQL/results, then compare with the
previous month. Evaluation defaults to 50 reference checks; Benchmarks reads
archived reports without provider calls. Chat requires a provider key.

```bash
docker compose logs --tail 100 reviewer
docker compose down
```

The container runs as UID 10001 with a read-only root, dropped capabilities and
writable tmpfs directories for demo data/telemetry. Container recreation discards
those temporary files; it does not delete repository report artifacts. Compose
is a synthetic reviewer package, not a hosted real-database deployment recipe.

## Local Python setup

Use Python 3.12 for alignment with CI and the container. Earlier local evidence
also used Python 3.14. Top-level dependencies are pinned; transitive packages and
the base image tag are not a complete immutable environment lock.

```bash
python -m venv .venv
# Linux / WSL / macOS:
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip check
python -m streamlit run app.py
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead. Runtime
installation alone uses requirements.txt; requirements-dev.txt adds pytest.
Browser capture is optional; see the asset guide for Playwright installation.
Record `python --version` and a local `python -m pip freeze` for the transfer's
actual environment. Do not treat an old validation count as a new test run.

The default retail fixture is generated once at data/retail-v1.db. Existing files
are never overwritten. All retail data is synthetic, covering January–April 2026
with a fixed reporting anchor of May 1, 2026. “Last month” means April 2026 in this
demo, not the machine's previous calendar month. Legacy students is a separate
five-row demonstration. Retail metrics are not automatically applied to arbitrary
remote schemas.

## Configuration and credentials

| Setting | Consumer and purpose |
| --- | --- |
| ASSISTANT_DEPLOYMENT | Unset/local: development UI; reviewer: synthetic SQLite only; hosted: authenticated, approved remote views. |
| Groq API Key and model sidebar fields | Local/reviewer Chat configuration. Default model is qwen/qwen3.8-27b, used in the recorded runs; availability must be checked for the provider account before new live calls. |
| GROQ_API_KEY | Environment variable read by evaluation/benchmark CLIs. The Chat sidebar does not automatically read it. |
| .streamlit/secrets.toml | Hosted OIDC, provider key and operator-managed grants. Ignored by Git. Copy the [template](../deployment/secrets.example.toml), replace placeholders and protect local permissions. CLI tools do not read these secrets. |
| ASSISTANT_TELEMETRY_PATH | Opt-in local SQLite aggregate, e.g. .telemetry/requests.db. Compose uses a temporary container store. |
| TEST_POSTGRES_ADMIN_URL / TEST_MYSQL_ADMIN_URL | Integration-test endpoints only. Tests create/drop tables and reader accounts; use disposable databases exclusively. |

.env files are not automatically loaded by the application. Supply environment
variables in the launching shell/process, not as credential CLI arguments. Do
not include real keys, credential URLs, private CSVs or external-database captures
in a handover bundle. Keys previously shared in chat require owner-confirmed
revocation/rotation; no credential is delivered with this repository.

For local PostgreSQL/MySQL Chat, configure a dedicated SELECT-only account,
approved schema and optional trusted CA path. URL creation handles special
characters. Local optional TLS is not equivalent to hosted verified TLS.
[sql_queries.sql](../sql_queries.sql) is a fresh PostgreSQL/psql loader/reader
bootstrap for the bundled market CSV, not a retail migration or a repair script
for existing roles. Run only as the administrator against a fresh disposable
installation after review; no MySQL provisioning/migration script is supplied.

Hosted mode needs an operator-managed OIDC provider, verified email and unexpired
exp claim, allowed view/column grants, CA files and provider approval. The example
uses an approved_sales view which the operator must create; it is not bundled.
Enforce tenant row filtering in database views, provide certificate-verified TLS
and HTTPS, and verify identity/session expiration with the real infrastructure.
These external services are not provisioned or validated by the prototype tests.

## Architecture and maintenance boundaries

1. ui/runtime collect configuration and construct request-scoped resources.
2. generation applies bounded history, clarification and tool orchestration.
3. Retail execute_analysis_plan goes through intent checks and the closed metric
   compiler; query_database handles controlled flexible SQL. Unsupported filter
   shapes cannot be silently forced into a partial canonical plan.
4. Both paths pass QueryService preview/execution validation, database read-only
   controls, result limits and statement timeouts. Permissions remain essential.
5. A single successful canonical call renders deterministic cited facts. Flexible
   SQL/multi-tool paths verify structured model facts or display a cited fallback.
6. presentation retains inspectable query evidence; traces/telemetry have separate
   redaction/retention boundaries. Engines are disposed on success and errors.

Normal request defaults: 60 seconds/60,000 admitted tokens, 1,500 output tokens,
20-second maximum model timeout, 5-second query timeout, 200 rows, four tool calls,
five model rounds and two recoverable repairs. Context is eight messages capped
at 2,000 characters each. Deadlines are cooperative, not process-killing hard limits.
A correct cell reference does not prove that SQL captured business intent.

Maintain metric definitions in business.py/plans.py, policy in validation.py and
execution.py, routing in plan_intent.py/followups.py and provider orchestration in
generation.py. The docs link deeper design details rather than duplicating all
allowlist entries. Changes to metrics/fixtures must version and reconcile reference
outputs and normalized-table oracles. Preserve historical benchmark JSONs and
checksum manifests. If tuning on prospective v1, retire it from holdout status;
new independent claims require a separately authored/versioned set.

## Validation and evidence

```bash
python -m pytest -q
python -m assistant.evaluation --output evaluation/results/handover-reference.json
python -m assistant.instance_checks --output evaluation/results/handover-instances.json
```

Without both disposable endpoints, two real-server tests skip. Run them separately
with those environment variables configured:

```bash
python -m pytest -q tests/test_integration.py
```

Stored evidence: PR #5 had 372 passing local tests/two skips; the earlier full
real-server run had 351 passed/zero skips. These were different source snapshots.
Original reference checks are 50/50 and original instance checks 144/144. Prospective
v1 passed 8/8 application outcomes for each approach, including 6/6 SQL tasks per
approach on three instances. It is same-author, single-repeat and synthetic; both
approaches matched results and the workflow used more provider calls. It does
not establish general accuracy, repeat stability or workflow superiority.

New live runs consume quota and require a locally configured key. Use the paired
[prospective protocol](prospective-evaluation.md#reproduce) or a small regression
selection, with account-appropriate quotas and new output filenames. SDK retries
are disabled; the scheduler stops after three consecutive provider failures.
assistant.evaluation returns nonzero when any case fails. assistant.benchmark
returns zero after report generation even for failed/partial runs: inspect rows,
completion.not_attempted and each approach's SQL/answer/completion metrics before
acceptance. Never use its shell exit code alone as a quality gate.

## Operations, data and recovery

| Item | Lifecycle / action |
| --- | --- |
| Session chat/query evidence | In-memory Streamlit session; clear history or restart. Connection changes reset context. |
| data/retail-*.db | Local synthetic files, generated once. Stop the app and rename/back up the fixture before regenerating; do not delete external databases or legacy source files. |
| evaluation/results/ | Ignored new-run output. Preserve useful runs before cleanup; freeze reports/metadata deliberately. |
| evaluation/reports/ | Committed sanitized evidence read by the dashboard. Keep original JSONs immutable. |
| evaluation/diagnostics/ | Explicitly opted-in synthetic SQL/plans; more detailed than operational traces. Not a general private-data logging mechanism. |
| CSV exports / inspected SQL | Actual query data, unlike redacted traces. Review before sharing or attaching to issues. |
| .telemetry/ | Optional sanitized local counters. No automatic retention/backup; owner must choose policy. Compose's tmpfs copy is ephemeral. |

For a populated aggregate:

```bash
export ASSISTANT_TELEMETRY_PATH=.telemetry/requests.db
python -m streamlit run app.py
# After requests create the store:
python -m assistant.telemetry .telemetry/requests.db
```

Known instrumentation limit: provider_connection is visible in request traces,
but the persistent telemetry error allowlist currently omits that category. Its
aggregate can undercount connection errors; do not use it as a complete provider
availability monitor. No managed monitoring service or alerting is configured.

| Symptom | First response |
| --- | --- |
| authentication / 401 / 403 | Verify account/key configuration privately; rotate exposed keys. Do not paste keys or raw exception payloads into tickets. |
| rate_limit / 429 | Respect provider cooldown, reduce RPM/TPM or postpone. Shared account traffic and token estimates can still cause 429; retain failures. |
| provider_connection / provider_timeout | Check provider/network/proxy/TLS reachability; use one bounded probe. SQL changes do not diagnose Codex UI reconnect errors. |
| budget_exhausted / quota_wait_budget | Inspect deadline/queue and schema size; use a smaller request or explicitly budgeted benchmark. Avoid blind retries. |
| policy rejection | Inspect proposed SQL and permitted subset. CTEs, writes, comments, unsafe functions and raw retail refund joins are intentionally rejected. |
| database error / statement timeout | Check schema/permissions, simplify the query and confirm recovery with a small SELECT. |
| clarification / fallback / truncated result | Resolve metric/filter ambiguity, inspect cells and SQL, and narrow the result. A safe fallback is not a verified model-answer pass. |
| Docker permission, missing CLI or I/O error | Check Docker Desktop WSL integration/Engine access. This audit saw /usr/bin/docker fail with Input/output error, so no fresh local image build is claimed. |
| Hosted access denied | Verify verified-email/exp claims, exact grant identity, existing approved views/columns, CA mount and provider approval. |

Back up local results/approved configuration through the owner's private process;
never commit secrets. To roll back, use a clean checkout/image of a recorded
passing revision, restore matching fixture/configuration versions and rerun smoke
checks. Application rollback does not reverse external grants or database changes.
Stop a reviewer deployment with docker compose down; remove only task-owned
containers/volumes after confirming their identity. Earlier cleanup names were
ai-sql-review-check, ai-sql-check-pg-20261021a and ai-sql-check-mysql-20261021a;
cleanup completion is not confirmed by this audit.

## Acceptance and transfer

- [ ] Owner reviews and merges the prerequisite PR chain and documentation.
- [ ] Record the accepted main commit/tag and its final CI URLs.
- [ ] From a fresh checkout of that revision, install dependencies, run offline
      checks and verify Docker startup, Plan demo, Evaluation and Benchmarks.
- [ ] For live Chat, configure a supported model privately and record a bounded
      smoke result; distinguish it from model-free demonstration.
- [ ] Confirm credential rotation and task-container cleanup.
- [ ] Name the incoming maintainer, contact/escalation route, target environment,
      backup/retention owner and transfer date. Repository owner is
      sunshine-engineer; a receiving maintainer/operational SLA is not assigned.
- [ ] Share secrets/access through the owner's secure channel, not this document.

These are acceptance/ownership actions, not claims of missing core features.
Independent evaluation and verified hosted infrastructure remain separate future
work unless the handover target explicitly includes a real-data production service.
