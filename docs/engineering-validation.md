# Engineering feature validation

Outline: implemented boundaries, measured evidence, reviewer artifacts and limits.

**Current follow-up (2026-10-21):** the reliability branch passed all 351 tests
with real disposable PostgreSQL/MySQL endpoints, including the two previously
skipped integration tests. The R13/R30 live confirmations and Docker build, health and canonical-plan
smoke checks passed. See the
[reliability validation record](benchmark-reliability-status.md) for container
verification and current delivery status. The earlier feature snapshot below
retains its original limitations.

Branch: `feat/measured-analytics-engineering`, based on the existing feature
checkout. Includes the preceding four correctness fixes that were still local
when this work started.

## Executed checks

Temporary Python 3.14 environment, 2026-10-20:

- `python -m pytest -q`: **312 passed, 2 skipped**.
- `python -m assistant.evaluation`: **50/50** offline fixture/control cases pass.
- `python -m assistant.instance_checks`: **144/144** original frozen result and
  three-instance reference execution checks pass; constant-query overfitting
  witness passes base and fails both alternatives as expected.
- `python -m pip check`: no broken requirements.
- Python compilation and `git diff --check`: pass.
- Playwright with Chromium 141: actual running app executes a reviewed plan,
  compares months and runs reference evaluation without browser exceptions.
  [Screenshots and walkthrough](../assets/current/README.md) are captured from
  that flow, without a provider key.
- Groq live API: all 50 development questions, two repeats of 10 reserved
  questions and two slower repeats of four reserved questions, each paired
  with one-shot SQL. [Measured results and failures](benchmark-report.md).

Tests cover plan field/grain validation, literal injection, compiled SQL in all
three supported dialects, independent normalized-table metric oracles, nulls,
zero denominators/targets, refund fan-out refusal, real 502-table catalog
selection, token admission without a provider call, post-provider/post-database
deadline stops, provider error classes, telemetry allowlisting and aggregation,
OIDC identity/expiry checks, cross-user access denial, private-column/predicate
and wildcard/subquery rejection, and certificate/hostname verification options.

## Delivery and validation limits

- Docker/Compose package and a CI container health-check job are included. Local
  Docker execution is **unverified**: Docker Desktop is not integrated with this
  WSL environment. The local Streamlit server and browser flow were tested.
- CI changes have not run on GitHub; no CI success is claimed.
- Two real PostgreSQL/MySQL integration tests remain skipped locally; no remote
  database permissions or data were changed.
- Hosted identity/view/TLS controls are covered by unit and boundary tests, not a
  real OIDC provider or certificate-protected database. Configure trusted OIDC,
  HTTPS, de-identified views, read-only DB grants and provider approval before
  using hosted mode with real data. Reviewer mode blocks real remote databases.
- Canonical plans enforce supported metric expressions and grain, not arbitrary
  business intent. Flexible SQL outside that subset still needs semantic review.
- Request deadlines are cooperative; normal chat includes connection/schema setup, while
  benchmark/evaluation budgets exclude shared fixture preparation. Token admission is conservative accounting, not exact billing.
- Published benchmark artifacts come from development snapshots and retain their
  limitations. The slower pilot is not a general accuracy claim.
