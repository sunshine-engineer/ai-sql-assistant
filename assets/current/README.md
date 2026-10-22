# Recorded reviewer walkthrough

Captured during the 2026-10-20 engineering milestone. Screens show that version;
use the [handover guide](../../docs/HANDOVER.md) for current operating instructions.
The capture script intentionally selects the historical paced-pilot report.

These are captures of the running application, using real controlled SQLite
execution over bundled synthetic data. **This walkthrough makes no model call**;
the separately recorded benchmark is the live-model evidence.

- [Short walkthrough video](reviewer-demo.webm): explicit plan → execution →
  previous-month comparison → 50 offline reference checks → recorded live benchmark.
- [Plan execution](plan.png)
- [Month comparison](comparison.png)
- [Reference evaluation](evaluation.png)
- [Recorded live benchmark](benchmark.png)

To reproduce:

```bash
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
# On Linux, Playwright may require system browser dependencies.
python -m streamlit run app.py --server.address=127.0.0.1 --server.port=8507
# In another shell, with Playwright + Chromium installed:
python scripts/capture_demo.py
```

Select **Plan demo** to explore without a provider key. Change region or metric,
run the reviewed plan, and inspect generated SQL, rows, truncation and references.
