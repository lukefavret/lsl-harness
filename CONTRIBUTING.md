# Contributing to lsl-harness

Thank you for your interest in improving lsl-harness. This guide explains how to set up your environment, coding conventions, how to run checks, and how to propose changes.

> TL;DR

> - Use Python 3.11 with uv for env/deps
> - Run: format, lint, tests before pushing
> - Keep plots headless (Matplotlib Agg) for CI
> - Small PRs with clear scope and tests

## 1. Project scope

This repo measures Lab Streaming Layer (LSL) stream performance and produces metrics, plots, and an HTML report. The CLI has two primary commands: collect data (`measure`) and render a report (`report`).

- CLI: `src/lsl_harness/cli.py` (Typer)
- Acquisition: `src/lsl_harness/measure.py` (background inlet worker, `Ring` buffer)
- Metrics: `src/lsl_harness/metrics.py` (`compute_metrics` → `Summary` dataclass)
- Reporting: `src/lsl_harness/report.py` (reads artifacts, writes plots and HTML)

## 2. Environment setup

Requirements:

- Python 3.11
- uv ([astral-sh/uv](https://github.com/astral-sh/uv))
- On Linux/WSL: `pylsl` needs a `liblsl.so` (see below)

Setup:

```bash
# create venv and install runtime deps
uv venv --python 3.11 && uv sync

# for development (adds lint/test tools)
uv sync --group dev
```

Linux/WSL note (pylsl):

- `pylsl` looks for `liblsl.so` in its wheel, system paths, or where `PYLSL_LIB` points.
- If missing, set `PYLSL_LIB` to a valid path (e.g., `$CONDA_PREFIX/lib/liblsl.so` or a local `vendor/liblsl/liblsl.so`).

## 3. Commands

- Lint & format:
  - `ruff format`
  - `ruff check`
- Tests:
  - `uv run pytest -q`
- CLI quickstart:
  - Collect: `uv run lsl-harness measure --duration-seconds 5 --summary --json-summary`
  - Report: `uv run lsl-harness report results/run_001`

## 4. Coding conventions

- Python: 3.11 typing (prefer `Path | None` unions), Google-style docstrings, 88-col wrap
- Typer CLI:
  - Avoid function calls in default args (Ruff B008). Use booleans or `None`, then handle inside.
  - For required args, prefer Typer’s `Argument(...)` pattern within lint constraints.
- File I/O: use `pathlib.Path`, explicit encodings; check existence and raise `FileNotFoundError` with clear messages.
- Matplotlib:
  - Always close figures after saving (`plt.close()`); use constants like `PLOT_DPI`.
  - Use `Agg` backend in headless/CI contexts (see Headless plotting note below).
- Jinja2: loader at `Path(__file__).parent / "templates"`; render with explicit context keys.

## 5. Headless plotting (Agg backend)

Tests run with warnings treated as errors (see `pytest.ini`). GUI backends can trigger toolkit/Pillow warnings in headless environments. To avoid this, we configure Matplotlib to use the non-interactive `Agg` backend in `lsl_harness/report.py` before importing `pyplot`.

If you add new plotting code that executes during tests/CI, either:

- Import and use `plt` from `lsl_harness/report.py` (which already sets `Agg`), or
- Call `matplotlib.use("Agg")` before importing `matplotlib.pyplot` in the new module.

## 6. Tests and quality gates

- Pytest is configured with warnings-as-errors. Keep output clean.
- Add tests for any user-facing behavior change. Minimal tests: happy path + 1–2 edge cases.
- Quality gates you should run locally before pushing:
  - Build/Import: import the module(s) you changed
  - Lint/Format: `ruff format` and `ruff check`
  - Tests: `uv run pytest -q`

## 7. Git workflow

- Branch from `main`: `feature/<short-name>`, `fix/<short-name>`
- Keep PRs small and focused. Include a short description, rationale, and screenshots for visual changes.
- Link related issues. Note any follow-ups explicitly.
- Checklists for PRs:
  - [ ] Code formatted and linted
  - [ ] Tests added/updated and passing
  - [ ] Docs updated (CLI help, README, Developer Guide) if behavior changed

Commit message tips:

- Imperative mood, present tense: "Add metric X", "Fix latency calc"
- Reference issues/PRs when relevant

## 8. Extending the project

- Extending metrics:
  - Add fields to `Summary` in `metrics.py`; `summary.json` includes them automatically via `__dict__`.
  - Update report template context as needed.
- New CLI flags:
  - Prefer boolean toggles (`--feature/--no-feature`), document side effects, keep console tables short.
- New artifacts:
  - Update both writer (in `measure.py`) and reader (in `report.py`), adjust the Jinja2 template, and add tests.

## 9. Platform notes

- Linux/WSL: ensure `liblsl.so` is available; set `PYLSL_LIB` if needed.
- Headless environments (CI): plots are saved as images; interactive HTML plots are not enabled by default. If you add interactivity, ensure CI fallback to static.

## 10. License and notices

- License: MIT (see `LICENSE`)
- Third-party notices: `third_party_notices.md`

---

Questions or ideas? Open a discussion or an issue. Thanks for contributing!
