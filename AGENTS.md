# Repository Guidelines

## Project Structure & Module Organization

`src/setup_doctor/` contains the Python package. Keep CLI orchestration in
`cli.py`/`runner.py`, data models in `models.py`, dependency diagnosis in
`engine.py`, and rendering in `output.py`. Ecosystem-specific, read-only checks
belong in `checkers/`; shared command, OS, and version helpers belong in
`utils/`. Optional LLM support is isolated in `ai/`; repeatable evaluation code
lives in `study/`.

Tests mirror the package: `tests/unit/` for isolated behavior,
`tests/integration/` for CLI and fixer flows, and `tests/snapshots/` for stable
JSON output. Keep product specs and implementation plans in
`docs/superpowers/`.

## Build, Test, and Development Commands

```powershell
pip install -e ".[dev]"                 # editable package plus pytest
python -m pytest                         # full suite
python -m pytest tests/unit/test_engine.py -k dep
setup-doctor check <repo> --mode dep     # local smoke test
setup-doctor check <repo> --format json  # machine-readable report
```

Use `--fix` only against a disposable or intentionally selected repository: it
may install dependencies or start services, although operations are whitelisted
and backed up where reversible.

## Coding Style & Naming Conventions

Target Python 3.11+, use four-space indentation, type annotations, and
`snake_case` for functions and variables. Use `PascalCase` for classes and
explicit check IDs such as `python.runtime.present`. Prefer small stdlib-based
helpers over new dependencies. No formatter or linter is configured; preserve
the surrounding style and keep diffs focused.

## Testing Guidelines

Use pytest and name tests `test_<behavior>`. Add a regression test for every
bug fix, especially command failures, malformed files, dependency cycles,
path traversal, and platform-specific behavior. Reuse `FakeRunner` from
`tests/conftest.py` instead of invoking package managers or Docker. Run the
full suite before handing off a change.

## Commit & Pull Request Guidelines

Follow the existing imperative prefixes: `feat:`, `fix:`, and `docs:`. Keep
commits atomic. PRs should state the user-visible behavior, affected check IDs,
tests run, and any safety or platform constraint; link the related issue when
one exists. Screenshots are unnecessary unless terminal or JSON output changed
materially.

## Safety & Configuration

Checks must remain read-only. Do not send repository contents or credentials to
AI providers; AI may enhance text only and must not decide check status,
severity, or exit codes. Keep API keys in environment variables, never config
files or commits.
