# Analytics feature validation

Outline: implemented scope, executed evidence, reproducible commands and limits.

## Scope

Feature branch: `feat/analytics-workflow-and-evaluation`, based on merged fixes in
`main` (`f3cc899`). The seven requested features are implemented together:

| Feature | Delivered behavior | Evidence |
| --- | --- | --- |
| Evaluation dashboard | 50 curated cases, separate offline reference/live modes, outcome/category scores, latency, JSON export and CLI | All 50 reference cases pass; scripted-provider tests catch wrong executed results even when prose looks correct; dashboard AppTest runs without a key |
| Query inspection | Proposed/validated SQL, tables, assumptions, validation/execution, result table, returned count, truncation and CSV | Real SQLite query and Streamlit AppTest; duplicate names disambiguated without changing values |
| Business definitions | Versioned retail metrics, join/grain/date guidance, synonyms and deterministic clarification | Contract/control tests; ambiguous questions do not reach SQL execution |
| Multi-table demo | Reproducible customers, products, orders, items, split refunds, targets and item-level facts | Fixture reproducibility, foreign keys, missing data, cancellations and refund reconciliation checks |
| Bounded recovery | Workflow stages, two SQL repair limit, terminal policy/timeout errors, four-call/five-round cap | Real unknown-column repair, retry exhaustion, policy refusal and timeout tests |
| Grounded charts/follow-ups | Charts from executed data; deterministic prior-month comparison preserves SQL metric/filter expressions | Chart provenance/decimal tests; real period/region/category comparison; Streamlit follow-up/reset test |
| Operational traces | Model/prompt version, stages, call timing, token availability/completeness, retries/outcomes and literal-free fingerprints | Privacy tests exclude prompts, SQL values, results and raw errors; partial/missing usage stays explicit |

## Local execution on 2026-10-20

Python 3.14 isolated temporary virtual environment; dependencies from
`requirements-dev.txt`:

```text
python -m pytest -q
133 passed, 2 skipped

python -m assistant.evaluation --output evaluation/results/reference.json
reference_fixture:
  result checks: 30/30
  clarification: 8/8
  refusal: 6/6
  unsupported: 6/6

python -m pip check
No broken requirements found.

python -m compileall -q app.py assistant tests
Passed

git diff --check
Passed
```

CI runs the offline suite/reference evaluation and uploads a reference JSON
artifact. The separate PostgreSQL 16/MySQL 8 service job retains live reader
permission, result, truncation, timeout and recovery checks. Consult the PR checks
for the actual latest CI results, rather than treating this configuration as proof.

## Verification limits

The 50/50 result is reference-fixture validation, **not LLM accuracy**. Live model
evaluation is implemented but was not executed against Groq. Scripted model tests
prove routing and result grading, not model quality or provider compatibility.
The two local skips require live PostgreSQL/MySQL services. No production data,
commercial usage or general SQL semantic correctness is claimed.

The retail contract only applies to the synthetic demo; join/metric definitions
are prompt guidance and evaluation targets, not formal semantic verification.
Month-comparison preservation requires canonical one-month date bounds, no
subqueries and no OR clause; other shapes ask clarification. General follow-ups
use bounded model context without the same deterministic guarantee. Charts may
skip duplicate axes, and monetary units remain cents. See `docs/analytics.md`.
