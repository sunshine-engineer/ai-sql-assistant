<!-- File: docs/prospective-evaluation.md | Purpose: Prospective evaluation and supporting evidence. | Maintainer: sunshine-engineer | Modified: 2026-10-23 -->

# Prospective retail evaluation v1

Outline: authorship, freeze, protocol, result interpretation and reproduction.

This is the frozen 2026-10-21 protocol/result record. Current setup, operator
configuration and transfer acceptance are in the [handover guide](HANDOVER.md).

## Authorship and selection

The user approved a **prospective holdout with an explicit same-author limit**.
The implementation agent authored these eight questions after the targeted
regression fixes. They were not authored independently by another person or
sampled from an external benchmark. Calling this an independent test would be
incorrect. Six questions require SQL results; two exercise clarification and
unsupported-request controls, which do not establish model accuracy.

Questions, reference SQL and expected rows for base, skewed and zero-sales are
in [the frozen suite](../evaluation/prospective_v1.json). References were checked
before provider calls. The source and suite hashes, timestamp and planned run
settings are in [the freeze manifest](../evaluation/prospective-v1-freeze.json).
Gold SQL and expected rows never enter either model's prompt; regression tests
check this boundary. Gold references still require human business review: passing
the same finite fixtures is not proof of universal SQL equivalence.

## Paired protocol

Both approaches receive identical questions, selected metadata, retail business
contract, model, temperature, output cap and execution policy. Workflow uses
bounded tools and repairs; baseline generates one SQL JSON object without repairs
or an answer stage. Both execute through the controlled service.

- Model: qwen/qwen3.8-27b; temperature 0; 1,500 output-token cap per call.
- All eight questions, one repetition; counterbalanced approach order.
- Same generated SQL evaluated on all three data instances.
- Per-request budget: 240 seconds and the shared default token-admission allowance.
- Shared quota admission: 2 RPM, estimated 8,000 TPM, minimum interval 35 seconds.
- No automatic request retries; stop after three consecutive provider failures.
- Preserve every failure and explicitly count unattempted/incomplete cases.
- Opt-in diagnostics contain only benchmark-owned synthetic plan/SQL evidence.

The one-shot baseline has no final answer, so model-answer faithfulness is N/A.
Canonical workflow answers are deterministic and counted separately from
verified model-generated facts. A result match can coexist with an application
outcome or answer failure; inspect each metric instead of one headline score.

## Interpretation and reuse

This is a prospective, same-author operational sample. It is small, has one run
per case, and uses synthetic data. It cannot establish repeat stability, general
NL-to-SQL accuracy, production performance or general superiority over a baseline.
Quota waiting is included in latency, so timings are not unpaced inference latency.

Do not tune prompts, routing or the compiler against v1 results and continue to
call it held out. Any resulting fixes must treat v1 as a regression set. A future
independent benchmark requires independently authored questions and a new version.
The original development/reserved/triage reports remain historical regressions
and are not rescored using this patch.

## Reproduce

Configure GROQ_API_KEY locally in the command environment, then run:

```bash
python -m assistant.benchmark --split prospective --repeats 1 --request-seconds 240 --requests-per-minute 2 --tokens-per-minute 8000 --interval 35 --progress --output evaluation/results/prospective-new-run.json --synthetic-diagnostics evaluation/results/prospective-new-run-synthetic.json
```

Use a new output filename for subsequent runs and retain failures. Current run
results are linked from [the review follow-up](final-review-follow-up.md).
The frozen suite is opt-in: it is not included in the development/triage pool or
fed into the operational system prompt.

The separation between component checks, regression tests and benchmarking follows
[LangChain’s evaluation guidance](https://docs.langchain.com/langsmith/evaluation-types).


## Recorded v1 results

[Recorded paired run](../evaluation/reports/2026-10-21-prospective-v1.json) ·
[Synthetic SQL diagnostics](../evaluation/diagnostics/2026-10-21-prospective-v1-synthetic.json) ·
[Checksums](../evaluation/prospective-v1-results-manifest.json)

| Measure | Workflow | One-shot SQL |
| --- | --- | --- |
| Pipeline/control outcomes | 8/8 | 8/8 |
| SQL questions matching all three instances | 6/6 | 6/6 |
| Verified model-generated answer candidates | 6/6 | N/A |
| Canonical deterministic answers | 0 | N/A |
| Recorded provider calls | 13 | 6 |
| Incomplete/unattempted cases | 0/0 | 0/0 |

There were no provider errors, rate limits, quota-budget denials or invalid
references. Both approaches matched every SQL reference. The workflow selected
flexible SQL for all six queries, so this run does not measure the canonical
terminal-answer optimization or establish an accuracy advantage over baseline.
The new canonical-filter guard is covered by the separate scripted regressions.
One repetition establishes no repeated-run stability even though all planned
slots are complete and the schema's consistency counter is 8 for each approach.

Aggregate quota waiting was about 687 seconds. Do not interpret run durations as
unpaced inference latency. Source and suite hashes match the pre-run freeze;
there were no implementation or prompt changes during the run. These eight
same-author examples are a small prospective sample, not a general accuracy
estimate or evidence of real-user adoption. Future tuning on their outcomes
retires v1 from holdout status.
