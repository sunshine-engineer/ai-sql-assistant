<!-- File: docs/configuration.md | Purpose: Runtime configuration sources, defaults, and environment reference. | Maintainer: sunshine-engineer | Modified: 2026-10-23 -->

# Configuration reference

No secrets are committed. The default maintainer is sunshine-engineer; original
authorship is not inferred from that maintenance label. Environment variables are
read at the boundary that consumes them, without network/database work at import.

## Environment variables

| Variable | Consumer / default | Required use and constraints |
| --- | --- | --- |
| `GROQ_API_KEY` | CLI `assistant.evaluation --live` and `assistant.benchmark`; unset | Required for live CLI runs. Local/reviewer Chat takes its sidebar key; hosted Chat takes `[provider].api_key` from Streamlit secrets. Never pass a key in CLI arguments or commit it. |
| `ASSISTANT_DEPLOYMENT` | Deployment guard and sidebar; `local` | `local`, `reviewer`, or `hosted`. Reviewer permits bundled synthetic SQLite paths. Hosted requires verified identity, scoped grants, approved views, and verified TLS. The image and Compose set `reviewer`. |
| `ASSISTANT_TELEMETRY_PATH` | Workflow finalization; unset | Opt-in local SQLite aggregate destination. Parent directory must be writable. Compose uses `/app/.telemetry/requests.db` on disposable tmpfs. No automatic retention or export approval is supplied. |
| `TEST_POSTGRES_ADMIN_URL` | Remote integration fixture; unset | SQLAlchemy `postgresql+psycopg` URL for a disposable test database. The fixture creates and removes its own role/table. Never point this at production. |
| `TEST_MYSQL_ADMIN_URL` | Remote integration fixture; unset | SQLAlchemy `mysql+mysqlconnector` URL for a disposable test database, with permission to create/drop the fixture role/table. Never point this at production. |

Copy [.env.example](../.env.example) to ignored `.env` only if useful. The
application does **not** load dotenv files. In a trusted Bash session, explicitly
load your privately edited values with `set -a; source .env; set +a`. Hosted secrets
use [deployment/secrets.example.toml](../deployment/secrets.example.toml), copied
to ignored `.streamlit/secrets.toml`; do not put hosted secrets in the reviewer image.
Blank/example values are placeholders and cannot authenticate.

## Request and query settings

Shared defaults are declared in [assistant/config.py](../assistant/config.py).
They retain the prior values; extracting them does not change limits or add hidden
environment overrides.

| Setting | Default | Supported override |
| --- | --- | --- |
| Model | `qwen/qwen3.8-27b` | Local sidebar, hosted `[provider].model`, or live CLI `--model`; availability is provider-dependent. |
| Default retail path | Repository `data/retail-v1.db` | Local sidebar chooses a database. Reviewer policy constrains paths. `assistant.demo --output` generates a separate fixture; it does not change the app default. |
| Request deadline | 60 seconds | Explicit `RequestBudget(seconds=...)` for application callers. Benchmark CLI `--request-seconds` defaults to 120, range >0 to 300. |
| Request tokens | 60,000 | Explicit `RequestBudget(tokens=...)`; estimated admission, measured usage when reported. |
| Output cap / HTTP timeout | 1,500 tokens / 20 seconds | Explicit `RequestBudget(output_tokens=...)` for workflow admission. Model construction uses the shared defaults; time remaining may shorten the timeout. |
| Remote connection timeout | 5 seconds | Shared connection default; no hidden environment override. |
| Query rows / timeout | 200 / 5,000 ms | Explicit `QueryService(max_rows=..., timeout_ms=...)`; per-query timeout may shorten the service limit. Deployment operators remain responsible for database permissions. |
| Benchmark local quota | 30 requests/minute, 8,000 estimated tokens/minute | `--requests-per-minute`, `--tokens-per-minute`, `--interval`; shared-account traffic can still produce rate limits. |
| Report destination | `evaluation/results/` | Evaluation, instance-check, and benchmark `--output`; outputs here are ignored. A custom path is the caller's responsibility. |
| Synthetic diagnostics | Disabled | Benchmark `--synthetic-diagnostics PATH`; suite-owned synthetic resources and curated cases only. Raw SQL may be recorded. |
| Browser capture target/output | `http://127.0.0.1:8507` / `assets/current` | `python -m scripts.capture_demo --url URL --output PATH`. Use a separate output directory to preserve recorded media. |
| Legacy student builder | Working-directory `student.db` | `python -m scripts.build_student --output PATH`; fails if the STUDENT table already exists. Root `sqlite.py` forwards to this command. |

`python -m assistant.benchmark --help` and `python -m assistant.evaluation --help`
list the other explicit split, repetition, selection, progress, and output options.
`AppConfig.settings` takes `path` for SQLite; remote engines take `host`, `port`,
`user`, `password`, `database`, and optional `tls_ca`. Hosted mode requires a trusted
CA file and verifies certificate identity. `AppConfig.schema` scopes PostgreSQL
metadata/search path. Hosted examples additionally show OIDC redirect, cookie
secret, client credentials, issuer metadata, email grants, permitted columns,
`provider_approved`, and per-user connection settings.

## Fixed policy and reproducibility values

The SQL function/table/statement allowlists, repair/tool-call bounds, 20,000-character
SQL/tool-context limits, eight-message history window, and versioned retail
calendar/metrics remain fixed application logic. The January–April 2026 fixture
and May 1 anchor are not wall-clock defaults. Synthetic names, prices, regions,
counts, and CI-only disposable passwords are test data, not production credentials.
Historical report model names, URLs, prompts, and source hashes describe their
recorded run and must not be replaced by current defaults.

Compose's localhost bind, port, resource caps, non-root UID, and tmpfs mounts are
reviewer deployment configuration in [compose.yaml](../compose.yaml). For another
environment, use an explicitly reviewed Compose override rather than changing
production behavior through undocumented environment variables. Real hosted OIDC,
TLS, authorization, and provider-data review still need environment-specific
verification; see [handover acceptance](HANDOVER.md).
