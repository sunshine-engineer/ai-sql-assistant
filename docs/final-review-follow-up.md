# Final portfolio review follow-up

Outline: correctness fixes, reporting, presentation, evaluation and validation.

## Canonical filter routing

Canonical plans support one equality value per region/category. The intent gate
now detects multiple region/category values, disjunctions, exclusions, negated
predicates and recognized unsupported conditions. Such plans are rejected before
database execution, with a bounded instruction to preserve every filter in
controlled flexible SQL or ask clarification. The equality compiler was not
expanded to represent these shapes implicitly.

The South/North regression verifies that the partial South plan never executes;
the repaired SQL includes both regions and returns 644,300 cents on the base
fixture. The previous South-only total was 335,600 cents. Other regressions cover
category lists, mixed-dimension OR, NOT predicates, customer IDs and status/range
conditions. A supported South AND Hardware equality conjunction still works.
Complex refund conditions may route to SQL instead of repeatedly being forced
back into a canonical plan that cannot represent them.

This remains a conservative recognizer, not general natural-language semantic
proof. Flexible SQL still needs business-result evaluation and inspection.

## Honest repetition reporting

A case counts as consistent only when there is exactly one passing record for
every planned repetition. Empty, partial, duplicate-repeat and failed cases do
not count as consistent. Each approach separately reports completed, incomplete
and unattempted cases. Completed means all expected slots were recorded; those
records can contain failures. Stopped runs retain their attempt-level outcomes.
Historical reports are unchanged and retain their original metric versions.

## Reviewer presentation

The README now starts with the existing walkthrough, a current plan screenshot
and the key-free Docker entry point. It distinguishes the model-free demo from
live-model reports, states the configured Qwen 3.8 model, describes both query
tools and shows intent/compiler, execution and answer-verification paths.
Previous real-database and Docker evidence is explicitly labeled as its earlier
snapshot rather than attributed to this patch's new tests.

## Prospective evaluation

The user chose a same-author prospective set instead of claiming independent
authorship. Eight questions were frozen before provider calls, with reference
outputs on all three data instances. The [protocol](prospective-evaluation.md)
records authorship limits, identical paired conditions, failure retention and
retirement from holdout status if used for tuning. No historical regression pass
rate is presented as general NL-to-SQL accuracy.

## Validation

- Current local suite: 372 passed, two real-database tests skipped because this
  resumed environment has no configured disposable endpoints.
- Original reference cases: 50/50. Original cross-instance checks: 144/144.
- Prospective reference queries: all six execute and match their frozen results
  on all three instances. This is reference sanity checking, not model accuracy.
- The earlier 351-test run with PostgreSQL/MySQL and reviewer-container smoke
  remains in the archived infrastructure record. This patch does not claim a new
  local Docker or real-server run.
- Live prospective results and MR/PR checks are recorded after completion.
