# Measured live benchmark — 2026-10-20

## What was measured

One provider model, `qwen/qwen3.8-27b`, verified through Groq's live model-list
endpoint, was run against the tool/plan workflow and a simpler one-shot SQL
baseline. Both used temperature 0, non-thinking mode, a 1500-token output cap,
the same business contract, questions and schema selection. No failed provider
requests were automatically retried. Only synthetic retail data was sent.

The same generated SQL was evaluated on base, skewed and zero-sales instances.
A SQL-suite pass requires matching curated reference results on **all three**.
Pipeline pass additionally requires the expected workflow outcome; answer
faithfulness is scored separately. Baseline answer faithfulness is not applicable.
Application clarification/refusal/unsupported controls are not NL-to-SQL accuracy.

The bundled [raw reports](../evaluation/reports/), [checksums and run settings](../evaluation/report-manifest.json)
retain successes and failures. Earlier runs preceded final implementation review;
they are preserved unchanged. The slower pilot includes a source hash and model
parameters. Re-running the current code may differ from those development snapshots
and from nondeterministic provider behavior.

## Results, including failures

| Run | Approach | Pipeline pass | All-instance SQL pass | Recorded verified model answers |
| --- | --- | --- | --- | --- |
| Development: all 50 questions, one repeat, 2s pacing | Workflow | 21/50 | 2/30 | 1/1 recorded candidate |
| Same | One-shot SQL | 31/50 | 11/30 | N/A |
| Reserved: 10 questions, two repeats, 8s pacing | Workflow | 4/20 | 8/16 | No candidates validated |
| Same | One-shot SQL | 14/20 | 10/16 | N/A |
| Slower pilot: H01–H04, two repeats, 18s pacing | Workflow | **8/8** | **8/8** | **8/8** |
| Same | One-shot SQL | **6/8** | **6/8** | N/A |

All SQL denominators include attempted result questions, including provider
failures. Pipeline totals also include non-query controls. The first two runs
were **quota-constrained operational pilots**, not fair model-accuracy rankings:
workflow calls encountered 29 and 14 rate-limit failures respectively; the
initial baseline encountered 15. Correct SQL was sometimes produced before a
subsequent summarization call hit a rate limit. This explains why a SQL-suite
pass can coexist with a failed pipeline outcome.

The slower pilot was selected as H01–H04 before running it, after observing quota
pressure. It covers customer count, missing regions, completed gross sales and
refund/gross ratio. It encountered **no provider errors**. Its workflow passed
every instance on both repetitions; the baseline failed the refund-ratio case
on the skewed instance twice. This is useful evidence on four questions, **not**
100% NL-to-SQL accuracy or proof that the workflow generally beats one-shot SQL.
The sample is small, selected during development and temperature-zero repeats
are correlated. The new reserved questions are not an independent external test.

Median attempt latency in the slower pilot was 36.05s for the workflow and 17.92s
for one-shot SQL. **These include intentional quota pacing** and cannot be used
as unpaced inference latency. The workflow has additional model stages; the
baseline does not generate an answer.

## Concrete failure evidence

| Observation | Evidence and implication |
| --- | --- |
| Constant query can overfit one fixture | `SELECT 12 AS customers` passes base but fails skewed (19 customers) and zero-sales (13). Regression test preserves this witness. |
| A plausible ratio can still be wrong | Baseline H04 passed base and zero-sales but failed skewed in both reserved repeats and both slower-pilot repeats. Finite multi-instance checks expose errors a single fixture misses. |
| Correct SQL does not imply a completed answer | Several reserved workflow queries passed all three instances, then failed at a later provider call. Pipeline, SQL and answer scores must remain separate. |
| Wrong results remain visible | Workflow H05 mismatched all three instances in both initial reserved repeats. These failures are retained, not removed from the score. |
| The evaluator itself needed a fix | Initial H08 gold SQL used `NOT EXISTS`, rejected by the then-current function allowlist. Its initial SQL score was not a valid measure of model correctness. Safe `EXISTS` is now allowed, nested unsafe functions remain rejected, and all 144 reference/instance checks pass. The original report is retained with this caveat. |
| Fan-out is an execution-boundary issue | Compiled metrics use item-grain facts; retail raw refund joins are rejected before execution. Independent normalized-table oracles check totals on all instances. |

## Operational evidence

The published trace aggregate contains 86 traced requests, including deterministic
controls, with 43 recorded workflow rate-limit errors and 69,641 reported tokens.
Only 19 requests have complete usage metadata. Initial baseline calls lack traces,
so these counters are **not** total provider calls or total billed tokens.
See [the sanitized aggregate](../evaluation/operational-summary.json). Row-level
reports record 58 rate-limit failures across both approaches in the two larger
runs. No prompt, result cell, SQL literal, user identity or API key is in the
persistent operational store or exported benchmark trace.

## What this supports

- The application now has measured live evidence and a paired baseline, rather
  than treating frozen fixture checks as model accuracy.
- The three-instance suite catches demonstrated fixture overfitting and ratio
  errors. It is a finite semantic regression test, not a proof of SQL equivalence.
- The slower four-question pilot supports the stated 8/8 versus 6/8 result only.
- Free-tier quota and a second model call for summarization materially affect
  end-to-end reliability. Reducing prompt size and using deterministic rendering
  after canonical plans are candidate next experiments, not verified improvements.
- A larger independently frozen split and a quota-safe full repeated run are
  needed before making broad accuracy or performance claims.

For methodology and reproduction commands, see [the engineering guide](engineering.md).
The offline UI/video demonstrates application execution; it is **not** live-model
benchmark evidence.
