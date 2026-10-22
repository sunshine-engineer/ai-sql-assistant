<!-- File: evaluation/README.md | Purpose: Explain suite, report, diagnostic, and manifest organization. | Maintainer: sunshine-engineer | Modified: 2026-10-23 -->

# Evaluation artifacts

| Path | Purpose |
| --- | --- |
| `retail_v1.json` | 50 versioned application regression questions and expected rows. |
| `heldout_v1.json` | Previously exposed reserved questions, now regression evidence. |
| `prospective_v1.json` | Frozen same-author prospective questions; authorship limit is explicit. |
| `reports/` | Immutable dated live workflow/baseline reports, including failures. |
| `diagnostics/` | Opt-in raw proposed plans/SQL for suite-owned synthetic instances only. |
| `report-manifest.json`, `triage-manifest.json` | Checksums and interpretation notes for recorded runs. |
| `prospective-v1-freeze.json`, `prospective-v1-results-manifest.json` | Pre-run freeze and resulting artifact hashes. |
| `infrastructure-validation-2026-10-21.json` | Historical source-bound Docker and real database verification. |
| `operational-summary.json` | Historical sanitized operational aggregate sample. |
| `results/` (ignored) | Regenerable local evaluation outputs; no committed secrets or real-data exports. |

JSON does not support comment headers. Do not insert metadata fields, reformat
frozen records, update historical dates, or rewrite their source hashes as part
of maintenance. Use [the file index](../docs/file-index.md) for descriptions and
[prospective evaluation](../docs/prospective-evaluation.md) for authorship and
interpretation boundaries. `python -m scripts.check_consistency` verifies the
existing artifact manifests and suite freeze; it does not assert historical
source hashes equal the current source.
