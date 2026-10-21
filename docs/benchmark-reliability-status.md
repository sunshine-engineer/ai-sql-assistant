# Benchmark reliability follow-up — 2026-10-21

**Latest status (2026-10-21): all pending verification is complete.**

| Check | Final evidence |
| --- | --- |
| R13 workflow confirmation | Passed on all three datasets; baseline also passed. |
| Revised R30 baseline confirmation | Passed on all three datasets; canonical workflow also passed. |
| PostgreSQL/MySQL integration | Full suite: 351 passed, zero skipped, with both disposable endpoints enabled. |
| Reviewer Docker startup | Healthy, HTTP 200, non-root/read-only execution and canonical plan smoke passed. |

Historical failures and earlier pending lists below are retained as dated
investigation history; the final follow-up sections close those items.

## Review outline

1. Preserve the measured successes and failures.
2. Explain the fixes and their regression coverage.
3. List blocked live checks with bounded reproduction commands.

Work remains on `fix/benchmark-reliability-and-semantics`. The earlier benchmark
reports are unchanged. The [triage report](../evaluation/reports/2026-10-20-triage.json)
and [synthetic-only SQL/plan diagnostics](../evaluation/diagnostics/2026-10-20-triage-synthetic.json)
were recovered from the completed run. Their [checksum manifest](../evaluation/triage-manifest.json)
records that snapshot; it predates the R13 projection clarification and the
provider-failure stop condition added below.

## What the recorded run establishes

The run planned eight questions, two approaches and two repetitions: 32 attempts.
It recorded 19 generic `provider_error` failures, no recorded 429 rate-limit
failures and no quota-budget denials. Local quota admission waited about 948
seconds in aggregate. Those observations do not identify a root cause for the
provider errors, establish provider availability now, or prove quota estimates
are exact. The second repetition has no successful provider calls.

| Case | First repetition across base, skewed and zero-sales | Action and remaining evidence |
| --- | --- | --- |
| R09 | Both approaches passed | Question now explicitly requires the Unknown label and alphabetical order. |
| R13 | Both approaches executed but failed result shape | Diagnostics show extra projected product columns. Current v3 question explicitly requests only product_name in alphabetical order. Targeted live rerun pending. |
| R28 | Both approaches passed | Include every category represented in sales_facts, even with zero refunds. No requirement to include products' categories absent from sales_facts. |
| R30 | Workflow passed; baseline rejected by policy | Baseline used a CTE, which the controlled execution policy rejects. Canonical net-revenue monthly growth uses conditional sums without a CTE, rounds to four decimals and returns NULL for a zero prior denominator. |
| H04 | Both approaches passed | Preserve the older incorrect completed-only ratio as a regression: base and zero-sales pass but skewed fails. Supported workflow refund-rate requests require the canonical all-refunds/gross expression. |
| H05 | Both approaches passed | Current workflow plan uses net revenue, South, March 2026, and no grouping. Repeated live verification remains pending. |
| H07 | Workflow passed; baseline provider error | Zero-refund category semantics are explicit. Baseline rerun remains pending. |
| H08 | Both approaches provider error | Safe NOT EXISTS executes on all three instances in offline tests. Live-model rerun remains pending; do not count this as a model SQL failure. |

Overall recorded pipeline passes were workflow 6/16 and baseline 4/16. These
include provider failures and R13's underspecified projection in the denominators;
they are operational regression evidence, not a fair accuracy ranking. All three
successful canonical workflow answers needed one model call each, with no
subsequent model summary. Their deterministic answers are reported separately
from the four verified model-generated workflow answers.

## Fixes and scope

- A single successful canonical-plan tool call renders result-referenced facts
  deterministically. Multiple tool calls are still processed, and partial results
  retain their truncation warning. A deterministic answer proves result rendering,
  not that the selected metric or SQL captures every possible user intent.
- Explicit metric, region/category filter, grouping and whole-month constraints
  are checked before plan execution. A mismatched supported plan gets a bounded
  repair opportunity. This is a narrow recognizer, not general intent parsing.
- H05 has a reproducible synthetic regression: adding region as a dimension to a
  South-filtered scalar total returns the wrong shape on all three instances;
  the all-missing-region instance returns no grouped rows. The correct metric,
  region and dates alone do not prevent that error. Earlier investigation observed
  this proposed-plan shape; its temporary pre-fix capture was lost when the
  temporary environment reset. The committed tests reproduce the mechanism.
  Historical failures had no raw SQL capture, so their exact cause is unproven.
- Supported refund-rate requests use SUM(refund_cents) / NULLIF(SUM(gross_sales_cents), 0).
  Refunds on cancelled orders are retained; the already defined gross expression
  handles order status. The naive additional completed-status filter is incorrect.
- Benchmark admission shares rolling RPM/estimated-TPM reservations between both
  approaches and bound tools. Queue waits consume the request deadline; the HTTP
  timeout is recalculated after admission. Reported usage replaces the estimate.
  This local sequential scheduler cannot reserve quota across other processes or
  account traffic. There are no automatic request retries.
- Three consecutive provider failures now stop a benchmark and save partial
  results. Unattempted cases are counted explicitly and excluded from recorded
  totals. Connection errors get `provider_connection`; timeouts, authentication,
  rate limits and model/request errors retain separate categories. Raw exception
  messages are never exported. SQL policy rejection, database errors, reference
  errors and result mismatches are also separate.
- Raw proposed SQL/plans can be captured only by explicit opt-in on benchmark-owned
  synthetic databases and repository-curated cases. General reports and operational
  traces do not gain raw SQL, result cells, prompts or credentials.

## Network note and pending work

The Codex UI messages “Reconnecting… waiting for network” and “error sending
request” do not identify the failing host or network layer. Their exact cause is
unknown. They must not be conflated with application SQL errors, 429 quota errors,
or the benchmark's generic provider errors. The recovered report contains no raw
transport exception and cannot diagnose DNS, proxy, TLS or service availability.

The temporary Python environment was also lost across interruptions and was
rebuilt to rerun offline validation. No configured GROQ_API_KEY was present when
work resumed. Do not recover or reuse the credential pasted into chat; configure
a fresh credential locally and never commit or paste it. Continue offline work
while waiting for that input instead of repeating network calls.

Earlier pending list (closed by the final follow-ups):

1. H08 live rerun is complete: both approaches passed both repetitions on all three
   instances. Clarified R13 passed both baseline repetitions and the first workflow
   repetition; the second workflow repetition had a provider_connection error.
   One workflow stability confirmation for R13 remains pending; do not repeat it
   automatically during a connection outage.
2. H05/H04/H07/R30 stability rerun is complete: workflow 8/8, baseline 6/8.
   The two baseline failures are R30 CTE policy rejections; see details below.
3. Preserve any provider failures. If a run stops, inspect its sanitized category,
   resolve credentials/connectivity/quota as appropriate, then start a new output
   file. Do not repeatedly restart the same failing run.
4. Run PostgreSQL/MySQL integration checks and container startup in their CI jobs;
   local SQLite tests do not establish those services are working.

With GROQ_API_KEY configured in the command's environment:

```bash
python -m assistant.benchmark --split triage --case-ids H08,R13 --repeats 2 --request-seconds 180 --progress --output evaluation/results/targeted-v3.json --synthetic-diagnostics evaluation/results/targeted-v3-synthetic.json
python -m assistant.benchmark --split triage --case-ids H05,H04,H07,R30 --repeats 2 --request-seconds 180 --progress --output evaluation/results/stability-v3.json --synthetic-diagnostics evaluation/results/stability-v3-synthetic.json
```

The CLI requires an environment variable; Streamlit secrets alone are not read by
this CLI. Default admission is 30 RPM and estimated 8,000 TPM; configure the limits
for the actual account. Previously exposed questions are regression cases, not
independent held-out evidence.

## Local validation

On resumption, Python 3.14 ran 349 passing tests, with two remote-database
integration tests skipped. All 50 frozen reference cases and all 144
cross-instance checks passed. Dependency consistency, Python compilation, diff
whitespace checks and the original report checksums passed. These are offline
application checks, not live-model accuracy. PostgreSQL/MySQL integration and
Docker startup were not exercised locally.

A credential was subsequently supplied for a bounded targeted live run. It is
used only in the child process environment and is not saved to the checkout or
reports. The targeted run's outcome will be recorded below; earlier evidence and
its failures remain unchanged.

## Targeted live follow-up

The [targeted v3 report](../evaluation/reports/2026-10-21-targeted-v3.json)
records eight attempts: workflow 3/4, baseline 4/4. Both H08 repetitions passed
all three datasets for both approaches. Clarified R13 passed both baseline
repetitions and one workflow repetition; its second workflow attempt failed with
`provider_connection` before producing SQL. There were no rate limits, quota
budget denials or invalid references. Seven model calls produced SQL candidates
that passed all instances; verified model summaries are separately counted for
the three completed workflow attempts. This small regression run is not an
independent accuracy benchmark.

The [opt-in synthetic diagnostics](../evaluation/diagnostics/2026-10-21-targeted-v3-synthetic.json)
retain proposed/executed SQL without model prose or credentials. Report source
hash matched the current assistant modules when archived. Checksums are in the
triage manifest linked above.

One bounded, unauthenticated HTTP check to the Groq models endpoint returned the
expected 401. It establishes reachability at probe time, not reliable availability
throughout the run or an explanation of the earlier connection error. The final
baseline model call also succeeded. No raw transport exception was retained, so
DNS, proxy, TLS and upstream-service causes remain unproven. The separate Codex
UI reconnect messages likewise cannot be attributed from this evidence.

## Stability live follow-up

The [stability v3 report](../evaluation/reports/2026-10-21-stability-v3.json)
records 16 attempts: **workflow 8/8, baseline 6/8**. H05, H04 and H07 passed both
repetitions for both approaches across all three datasets. R30's canonical
workflow passed both repetitions; both baseline SQL proposals used a CTE and
were classified as `policy_rejection`, not database failures or numerical
mismatches. This policy incompatibility does not establish that the rejected SQL
would have computed the wrong number. The baseline's prompt requests one SELECT
but does not explicitly repeat the workflow tool's no-CTE instruction, which
limits policy-level comparability. A subsequent protocol now explicitly supplies
the no-CTE/comment rule to the baseline and records its own baseline prompt
version. A separate R30 rerun is recorded below; these reports are not rescored.

The six H05/H04/R30 workflow attempts each used exactly one model call and a
deterministic canonical answer. H07 used two calls per attempt and had verified
result-referenced model summaries. No provider errors, rate limits, quota-budget
denials or invalid references occurred in this stability run. Local quota waiting
was about 392 seconds in aggregate; durations include admission waits and are not
unpaced inference latency. These small, previously exposed synthetic regression
cases do not establish production accuracy or general model superiority.

The [synthetic diagnostics](../evaluation/diagnostics/2026-10-21-stability-v3-synthetic.json)
show H05's metric, filter, month and scalar grain explicitly, and retain both R30
baseline CTE proposals. Both new runs use the same assistant source hash and
current case-contract versions. The original failed runs remain available.

One pending live stability confirmation is R13's second workflow success, which
was blocked by an intermittent connection error. The subsequent policy-parity
run also leaves one R30 baseline repetition pending after a rate-limit error.
Neither failed request was automatically retried. After checking connectivity, use a new output file:

```bash
python -m assistant.benchmark --split triage --case-ids R13 --repeats 1 --request-seconds 180 --progress --output evaluation/results/r13-confirmation.json --synthetic-diagnostics evaluation/results/r13-confirmation-synthetic.json
```

The baseline policy-instruction parity improvement is implemented in a new
protocol version. Remote database integration and container startup remain
external follow-up work. No claim is made that the
Codex reconnect UI's underlying cause has been diagnosed.

## Baseline execution-policy parity

The [separate R30 policy-parity run](../evaluation/reports/2026-10-21-r30-policy-parity.json)
uses benchmark protocol `v3-baseline-policy-parity` and baseline prompt
`one-shot-v2-no-cte-policy`. Its prompt now explicitly prohibits CTEs and comments,
as the workflow tool does. The algorithm remains one-shot SQL generation without
repairs. The earlier reports keep their original prompts, source hashes and failures.

Workflow passed **2/2**, each with one model call and a deterministic answer.
Baseline passed its first attempt on all three instances using allowed SQL; its
second attempt failed with `rate_limit` before producing SQL. There were no new
CTE policy rejections. The one successful SQL candidate is evidence that the
instruction correction can work, not repeated baseline stability or a general
accuracy comparison. Raw synthetic SQL is retained in the
[separate diagnostics](../evaluation/diagnostics/2026-10-21-r30-policy-parity-synthetic.json).

The scheduler recorded one provider 429 despite estimated quota admission. Its
local token estimate cannot account exactly for tokenizer differences, undisclosed
limits or other account traffic. The run retained the failure and applied the
provider cooldown before the next admitted workflow call; no failed request was
retried. Further live calls were stopped after this bounded run rather than
continually restarting to obtain passing results.

**Pending:** confirm one R13 workflow repetition after the connection issue, and
one R30 baseline repetition after quota availability is established. Also run the
remote-database and container CI checks. No further user input is needed for the
implemented offline fixes; future live runs need a locally configured credential
and suitable quota. Avoid pasting credentials into chat.


## Final confirmation follow-up

The [final confirmation report](../evaluation/reports/2026-10-21-final-confirmations.json)
completed all four planned attempts: R13 workflow and baseline, and R30 baseline
and workflow. **All four passed across base, skewed and zero-sales datasets.**
R13's workflow answer facts were verified; R30 used one model call and a
canonical deterministic answer. No provider errors, rate limits, budget denials
or invalid references occurred. This closes both previously pending live checks.

The run used 1 RPM, a 65-second minimum interval, the same estimated 8,000 TPM
admission ceiling and a 240-second per-request budget. Aggregate quota wait was
about 205 seconds. These timings include deliberate admission waits. The
[synthetic diagnostics](../evaluation/diagnostics/2026-10-21-final-confirmations-synthetic.json)
and triage manifest retain the SQL proposals and checksums. The source snapshot
matches the preceding policy-parity run. These selected confirmations are not a
new independent benchmark; earlier connection and quota failures remain recorded.


## Real database and container verification

The [infrastructure validation record](../evaluation/infrastructure-validation-2026-10-21.json)
records **351 tests passed, zero skipped**, with disposable PostgreSQL 16.15 and
MySQL 8.0.46 endpoints enabled. The real-server tests verified result counts,
truncation, denied DELETE permissions for the restricted reader, expensive-query
statement timeouts and successful reads after timeout recovery. Tests use only
their disposable test tables/users; no user database was used.

Docker 29.7.2 built and started the reviewer package using Python 3.12.13. A
second cached build included the newly archived final report. The running image
reached healthy status and returned HTTP 200 from its health endpoint. An
in-container smoke test created the synthetic retail fixture and executed a
canonical customer-count plan through QueryService, obtaining 12. Its source
hash matched the successful live confirmation report. UID 10001, read-only root
filesystem and dropped capabilities were verified from the running container.

The first MySQL image download timed out awaiting Docker Hub response headers;
one retry reused downloaded layers and succeeded. This identified that specific
image-pull failure, not the cause of earlier Codex reconnect messages. No product
code change was needed for the completed local checks. Hosted OIDC, external
certificate-verified TLS and real-data authorization remain separate deployment
checks, outside these synthetic integration tests.

Reproduce the database suite using disposable endpoints:

```bash
# Configure both URLs locally for disposable PostgreSQL/MySQL databases.
# Tests create/drop test tables and test_reader users; never use production URLs.
python -m pytest -q
# Reviewer image build and health check:
docker compose up --build --detach --wait --wait-timeout 120
curl --fail http://127.0.0.1:8501/_stcore/health
```

Both TEST_POSTGRES_ADMIN_URL and TEST_MYSQL_ADMIN_URL must be configured for
pytest to include the real-server tests. Their exact ephemeral ports and
credentials are deliberately omitted from the published validation record.
