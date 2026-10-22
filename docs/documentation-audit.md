# Documentation audit — 2026-10-22

Outline: scope, corrections, checks, limits and acceptance.

## Scope and outcome

Reviewed every tracked Markdown document, including the README, root validation
record, design guides, historical milestone reports, prospective protocol and
recorded-asset instructions. Compared their operational claims with application
configuration/runtime, generation/plans/answers, evaluation/benchmark CLIs,
telemetry, deployment modes, secrets template, Docker/Compose and CI definitions.

The [handover guide](HANDOVER.md) is the current maintainer entry point. Historical
reports remain evidence of their own versions, not replacement setup guides.
This review covers portfolio/reviewer maintenance; it is not production-service
acceptance or a fresh live-model performance measurement.

## Corrections

| Finding | Resolution |
| --- | --- |
| No single operational handover document | Added setup, configuration consumers, ownership, data lifecycle, recovery, rollback, validation and acceptance checklist. |
| Analytics guide said no live results were bundled and no local aggregate existed | Documented archived reports, opt-in telemetry and their separate privacy boundaries. |
| Workflow/answer explanation did not fully cover canonical terminal answers | Distinguished canonical compilation/intent gates, deterministic single-call answers, flexible facts and fallbacks. |
| Old validation reports had contradictory “current”/pending statements | Marked all milestone records as historical; preserve counts/failures and direct readers to current status. |
| CLI success meanings were easy to confuse | Explained evaluation failure exit codes versus benchmark report-generation success, partial runs and separate quality metrics. |
| Operator credential sources unclear | Separated Chat sidebar fields, CLI environment and hosted secrets; documented no automatic .env loading. |
| Dockerfile names the prospective input without a corresponding explicit exception | Added the exception to the build-context allowlist. This is an explicit-input alignment, not a proven reproduction of a failing build. |
| Recorded screenshots could look like a new release capture | Dated their milestone and documented capture dependencies plus the historical report selected by the script. |
| Telemetry aggregation silently omits provider_connection | Recorded the code's actual allowlist limitation; no runtime telemetry change made. |

## Validation record

See the final audit summary below for checks actually executed. External links are
references; no exhaustive external-site availability audit or new provider call is
claimed. Frozen benchmark JSONs and their manifests are not rewritten.

GitHub on 2026-10-22: PRs #3/#4/#5 remain open; PR #5's six existing checks passed.
The docs branch is not part of that previously tested commit. Docker cannot be
executed in this environment at audit time: /usr/bin/docker returns Input/output
error. A fresh image build on this branch/final main is therefore unverified.

## Remaining acceptance

The maintainer must review/include this documentation, merge/retarget the PR
chain, record an accepted main revision, perform final fresh-checkout smoke checks,
confirm exposed-key rotation and task-container cleanup, and assign the receiving
maintainer/contact/environment. These require owner/environment evidence; this
audit does not invent sign-off. Hosted OIDC/TLS/tenant isolation need real deployment
verification only if that is the actual handover target.


## Executed audit checks

- 13 Markdown files reviewed, including the two new handover/audit documents.
- 86 local links/assets and referenced Markdown anchors resolved.
- 18 Bash code blocks passed syntax checks; fenced JSON examples and the hosted
  secrets TOML template parsed successfully. Syntax is not execution proof.
- 18 manifest artifact hashes plus the prospective suite freeze verified;
  historical JSON evidence was not modified.
- Dockerfile COPY inputs exist and have explicit build-context inclusions;
  actual Docker build/start remains blocked by the host CLI I/O error.
- Offline suite rerun: **372 passed, 2 skipped**. The skips require disposable
  PostgreSQL/MySQL endpoints; this audit does not claim a new local real-server run.
- Reference CLI: **50/50**. Instance-check CLI: **144/144**, with the constant-query
  overfit witness still failing the two alternative instances as expected.
- pip check and git diff --check passed. No live provider calls, new screenshots,
  production database changes or new hosted deployment checks were performed.
