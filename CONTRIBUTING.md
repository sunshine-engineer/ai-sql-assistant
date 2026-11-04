<!-- File: CONTRIBUTING.md | Purpose: Contributor conventions and verification commands. | Maintainer: sunshine-engineer | Modified: 2026-10-23 -->

# Contributing

Use Python 3.12, matching CI and the reviewer image. Start from a fresh branch and
install `python -m pip install -r requirements-dev.txt`. Browser capture is optional
and has a separate dependency file. See [handover](docs/HANDOVER.md) for environment
setup and [configuration](docs/configuration.md) for secrets and adjustable limits.

## File conventions

- Python: module purpose and `File`, `Maintainer`, and ISO `Modified` metadata in
  the module docstring; imports; constants; logically ordered classes/functions;
  entry point last. Constants that depend on a class may follow that class.
- Every declared class and function, including private/test helpers and special
  methods, needs a useful docstring. Document arguments other than `self`/`cls`,
  returned or yielded values, and errors that callers must handle. Use Google-style
  `Args`, `Returns`, `Yields`, `Raises`, and `Attributes` where relevant. Avoid
  documenting caught errors as propagated exceptions. Add examples for non-obvious
  behavior; do not repeat an obvious one-line implementation as a long tutorial.
- Use `sunshine-engineer` as the default maintainer, not an invented original
  author or copyright holder. Update `Modified` only when editing that file.
- Markdown: one H1, logical headings, fenced examples, repository-relative links,
  and an HTML metadata comment. Preserve dated milestone evidence as historical.
- YAML, TOML, requirement lists, ignore files, and Dockerfiles use native `#`
  metadata comments. SQL uses `--` comments. Do not run broad formatters on SQL
  embedded in strings: it may be a versioned prompt or evaluation contract.
- JSON, CSV, SQLite, media, and `LICENSE` are deliberately exempt from inline
  headers. JSON/CSV headers would alter their data contract; media/database edits
  may invalidate reproducibility; license attribution must remain verbatim.
  Their descriptions belong in [the file index](docs/file-index.md) and adjacent
  READMEs. Frozen evaluation records keep their original bytes and dates.
- Keep UI code in `assistant/*_ui.py`, shared policies/services in `assistant/`,
  standalone maintenance in `scripts/`, tests in `tests/`, operating instructions
  in `docs/`, and deployment examples in `deployment/`. Existing root launcher and
  compatibility commands remain stable. Update the README directory map and file
  index when moving or adding files.

Ruff **0.14.3** is pinned in the development requirements and pyproject; use its
formatter and import sorting for all Python files. `.editorconfig` defines common
text conventions. Python indentation is four spaces; YAML/JSON examples use two.
Historical JSON is not reformatted. No package install/build backend is introduced:
`pyproject.toml` currently configures tooling only.

## Configuration boundaries

Keep credentials in the environment, the local sidebar, or ignored Streamlit
secrets as appropriate. `.env.example` is a shell template; nothing auto-loads it.
Use SQLAlchemy `URL.create` for application connection credentials. Shared default
model, request, query, and benchmark settings live in `assistant/config.py`;
callers/CLI supply supported overrides. Allowlisted SQL constructs, repair bounds,
row/context caps, fixture dates, gold results, and prompt versions are deliberate
policy or reproducibility constants. Do not silently make security ceilings
unbounded through environment variables.

## Required checks

```bash
python -m ruff check .
python -m ruff format --check .
python -m scripts.check_consistency
python -m pip check
python -m pytest -q
python -m assistant.evaluation --output evaluation/results/reference.json
python -m assistant.instance_checks --output evaluation/results/instance-checks.json
git diff --check
```

To apply formatting, run `python -m ruff check --fix .` then
`python -m ruff format .`, and review the diff. The consistency command checks every
Python callable, argument documentation, module metadata, parseable JSON, and
frozen evidence hashes. It does not prove prose accuracy, detect all secrets, or
replace code review. Running it requires a Git checkout.

Before requesting review, run the remote-database and reviewer-container checks
in [HANDOVER.md](docs/HANDOVER.md) when available. Integration tests require
explicit disposable administrator URLs and otherwise skip. A skipped check is
not a pass. CI runs the same format/doc checks, disposable PostgreSQL/MySQL tests,
and a reviewer Docker startup job. Live model benchmarks are opt-in and consume
quota; they are separate from offline tests and require careful result reporting.
Do not rewrite historical reports to make new source hashes look current.
