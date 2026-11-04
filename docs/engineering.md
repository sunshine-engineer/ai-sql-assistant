<!-- File: docs/engineering.md | Purpose: Engineering and supporting evidence. | Maintainer: sunshine-engineer | Modified: 2026-10-23 -->

# Measured analytics engineering

Start with the [handover and operations guide](HANDOVER.md) for configuration,
acceptance, troubleshooting and document navigation.

## Review outline

1. Run the key-free plan demo and inspect real execution evidence.
2. Run unit/regression checks and the 50 frozen fixture cases.
3. Compare one supported live model against one-shot SQL on identical questions.
4. Grade the same candidate SQL on three data instances.
5. Inspect failures, resource limits, schema selection and access boundaries.

## Canonical business plans

`execute_analysis_plan` accepts exactly `metric`, `dimensions`, `filters`,
`date_range` and `grain`. The compiler is a closed subset, not generated SQL:

```json
{"metric":"net_revenue_cents","dimensions":["category"],"filters":{"region":"South"},"date_range":["2026-04-01","2026-05-01"],"grain":"item"}
```

The compiler uses canonical expressions over item-grain `sales_facts`. Its source
is the approved normalized join path order item → order → customer/product, with
refunds aggregated per item before joining. Orders count distinct completed
order IDs; units exclude cancelled orders; customers count the customer table.
Refund/gross ratio uses `NULLIF` for a zero denominator. Empty sums remain null;
counts return zero. Values become AST string
literals, while identifiers and expressions come from code allowlists. Plans
are inspected in the UI and always pass through `QueryService` validation and
read-only execution. No model-supplied join expression can enter a compiled plan.

Supported dimensions are region, category and month for ordinary sales metrics;
customers support region only, and monthly growth supports region/category only.
Filters are equality predicates with one value per dimension. Recognized
conjunctions involving multiple values, disjunctions, exclusions and unsupported
conditions cannot silently become a partial canonical plan; route to flexible
SQL or clarification. The closed subset does not implement general NL parsing. Date ranges are inclusive-start/exclusive-end
within the fixed fixture coverage. Unsupported grain, fields and metrics are
rejected. Net-revenue monthly growth is supported for a complete current month and its
covered previous month, rounded to four decimals with a NULL zero denominator.
Targets, other growth definitions, arbitrary expressions, complex filters and
unrelated schemas continue to use flexible SQL; canonical analytical meaning is **not**
guaranteed for that path. Retail raw refund joins are explicitly rejected at
preview and execution, including joined subqueries; use `sales_facts` instead.
This intentionally conservative rule can reject otherwise legitimate queries.

Explicit supported metric, filter, grouping and calendar-month constraints are
checked before plan execution, with bounded repairs for mismatches. This narrow
recognizer is not general intent verification. Inspect proposed plans and compare
results to references. A single successful canonical-plan call renders result-backed
facts directly, avoiding a second model summarization call. Deterministic displayed
answers and verified model-generated answers have separate evaluation counts.

## Multiple data instances

`assistant.instances` generates fresh, versioned databases:

| Instance | Deliberate differences |
| --- | --- |
| base | Original 12 customers and split refunds |
| skewed | 19 customers, extra missing regions, changed quantities/cancellations/refunds and a zero target month |
| zero_sales | 13 customers, no refunds, zero sales/targets and all regions missing |

The benchmark generates SQL once against base metadata, then executes **that same
SQL** on every instance. Expected alternative results come from curated reference
SQL; original fixture rows remain frozen. This catches `SELECT 12 AS customers`,
which passes base and fails both alternatives. Independent normalized-table
oracles additionally check compiled totals and grain. These finite tests do not
prove equivalence for all possible databases, and reference SQL can itself have
bugs. The approach is inspired by [text-to-SQL test-suite evaluation](https://github.com/taoyds/test-suite-sql-eval);
it does not implement that repository's distilled test-suite algorithm.

## Live benchmark protocol

```bash
export GROQ_API_KEY=...  # configure locally; never commit the key
python -m assistant.benchmark --split triage --case-ids H08,R13 --repeats 2 --request-seconds 180 --progress --output evaluation/results/targeted.json
python -m assistant.benchmark --split development --limit 50 --repeats 1 --requests-per-minute 30 --tokens-per-minute 8000 --request-seconds 180 --output evaluation/results/development.json
```

Choose an identifier returned by the provider's model-list API with `--model`.
The CLI default is `qwen/qwen3.8-27b`, verified during this implementation. Both
approaches use the same provider model, temperature 0, non-thinking mode,
1500-token output cap, business contract and metadata selector. The workflow has
plans, tools, result-backed answers and bounded repairs. The simpler baseline
makes one JSON SQL-generation call with no repairs, followed by controlled SQL
execution. Both share application preflight checks. The current baseline explicitly receives
the no-CTE/comment execution policy and records a separate baseline prompt version;
earlier measured protocols did not repeat that instruction. Those checks are not model
accuracy. Baseline answer faithfulness is not applicable: it generates no answer.

Results include every attempted case, provider failures, latency, model/version,
instance suite, split and repeat. SQL-suite pass means all three instances pass.
The main pass score checks SQL/outcome, while answer faithfulness is separate.
Repeated temperature-zero calls measure stability, not independent samples.
The ten previously exposed reserved questions are regression cases;
they are not a blind external benchmark and have regression tests. Do not tune
against them and continue claiming independent held-out performance. Freeze a
new independent split for subsequent model selection.

Rolling request/token admission is shared between bound tools and baseline calls;
approach order is counterbalanced. Waiting consumes each request deadline; the
HTTP timeout is recalculated afterward. Token estimates are replaced by usage
when reported. Configure RPM/TPM for the actual account; this sequential local
scheduler cannot reserve shared-account traffic. An additional minimum interval
is optional. There are no automatic request retries. Three consecutive provider
failures stop the run and save partial evidence with unattempted counts. A quota-constrained run is an
operational pilot, not a valid ranking of NL-to-SQL accuracy. Use **Benchmarks** in the app to inspect the bundled runs without a key.
See the published
[measured report](benchmark-report.md) for successes **and failures**, and the
[reliability follow-up](benchmark-reliability-status.md) for current fixes, recorded
triage results and completed reruns. The [prospective protocol](prospective-evaluation.md)
records eight same-author questions frozen before their paired run. They are not
an independently authored test set. Current reporting distinguishes complete,
incomplete and unattempted cases; consistency requires every planned repetition
to be present once and pass. Optional `--synthetic-diagnostics path.json`
captures raw SQL/plans only for benchmark-owned synthetic fixtures; keep that
separate from general reports. The CLI reads GROQ_API_KEY from its environment.

The 50 offline reference checks remain application regressions, not a live
benchmark. This separation follows [LangChain's evaluation guidance](https://docs.langchain.com/langsmith/evaluation-types).

## Runtime controls and operational evidence

Each workflow has a 60-second deadline, a 60,000-token admission allowance,
1500-token output cap, four tool calls, five model rounds and two recoverable SQL
repairs. Model timeout is capped at remaining time (and 20 seconds); database
statement timeout is capped at remaining time (and five seconds). Time is checked
before/after external operations. SDK retries are disabled. This is cooperative
admission/deadline enforcement, not a process-killing hard wall-clock guarantee.
Normal chat starts its budget before connection/schema setup and checks it between
metadata reads. Benchmark/evaluation cases use independent budgets after their
shared fixture setup. Provider transport and
server cancellation must still be validated in a real deployment.

Token admission reserves serialized message/tool UTF-8 bytes plus protocol
headroom. Actual usage is charged when reported; otherwise the reservation is
charged. This conservative accounting is not a model-tokenizer estimate or a
billing guarantee. Trace usage completeness remains explicit.

Provider errors are sanitized into rate-limit, authentication, model/request,
connection, timeout, unavailable and unknown categories. Exception text is not exported.

```bash
export ASSISTANT_TELEMETRY_PATH=.telemetry/requests.db
python -m streamlit run app.py
python -m assistant.telemetry .telemetry/requests.db
```

The opt-in SQLite operational store keeps only outcome/error enums, elapsed time,
token count/completeness, retries and tool-call count. It excludes prompts, SQL,
results, model names and identities. Concurrent SQLite writes are transactional;
a store failure does not fail the answer. This local aggregate is not a hosted
monitoring service; no retention scheduler or alert delivery is configured.
The controls align with [OWASP's agent guidance](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html).

For large catalogs, deterministic table/column keyword scoring sends at most
eight tables and 12 KB of metadata. A 502-table regression checks relevant customer
and order selection. Metadata selection is **not authorization**: it neither adds
nor removes the user's granted tables. Ambiguous/no-match schemas may need an
explicit table name. Enumeration/introspection still happens locally; no claim
of learned retrieval quality or production catalog-scale latency is made.

## Reviewer deployment and hosted access

```bash
docker compose up --build
# Open http://127.0.0.1:8501 and select Plan demo or Evaluation.
```

The package runs as a non-root user, binds to loopback, drops capabilities and
uses a read-only root filesystem with bounded temporary data. It copies only
application/fixture inputs, never local secrets. Reviewer mode rejects remote
connections and arbitrary SQLite paths at the runtime boundary. No key is needed
for Plan demo or reference evaluation. Docker startup and real database checks
have recorded validation evidence; consult the [handover acceptance status](HANDOVER.md#acceptance-and-transfer)
for its source revision and any fresh-clone checks still required.

A separate `ASSISTANT_DEPLOYMENT=hosted` mode uses Streamlit OIDC sign-in. It requires
a verified email, an unexpired OIDC `exp` claim and operator-managed grants from local secrets, then selects only
approved database **views** and explicitly approved columns for that user. Hosted
mode has no user-entered connection settings. For row-level tenant isolation, filter rows in the database views themselves;
column projections alone do not enforce tenant row boundaries. The database must use a dedicated
read-only role and certificate-verified TLS (`verify-full` for PostgreSQL;
certificate and hostname verification for MySQL). See the
[PostgreSQL TLS documentation](https://www.postgresql.org/docs/current/libpq-ssl.html)
and [MySQL connector options](https://dev.mysql.com/doc/connector-python/en/connector-python-connectargs.html). Each grant's `provider_approved`
flag records operator approval to send that view projection to Groq. Do not use
that flag as a substitute for reviewing/creating de-identified views.

Restricted projections reject wildcard selection, private columns in expressions
or predicates, and subqueries. Only approved projection metadata reaches the
model. Email/credential redaction in conversational text is extra hygiene, not a
complete sensitive-data classifier. The primary boundary is reviewed DB views,
column enforcement, per-user grants and least-privilege database roles. Users must
also avoid entering sensitive free-form text not covered by those detectors.

See [the secrets template](../deployment/secrets.example.toml) for configuration.
Configure HTTPS, an OIDC provider issuing `email_verified` and `exp`, trusted CA files, a
read-only DB role with grants **only** to approved views, operator-approved provider
retention and organization policies, and session expiry before exposing real data.
None of those external services is provisioned or verified by the local tests.
The reviewer package does not expose real databases publicly.
