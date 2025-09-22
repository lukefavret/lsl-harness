# Copilot Instructions — lsl-harness

This repo measures LSL (Lab Streaming Layer) stream performance and produces metrics, plots, and an HTML report. The CLI has two primary commands: collect data (`measure`) and render a report (`report`).

## Architecture
- CLI: `src/lsl_harness/cli.py` (Typer app)
  - `measure`: pulls samples, writes artifacts, prints a concise/verbose summary, optional JSON summary.
  - `report`: reads artifacts and renders HTML via Jinja2 templates.
- Acquisition: `src/lsl_harness/measure.py`
  - `InletWorker` resolves an LSL stream and pulls chunks in a background thread into a `Ring`.
- Buffer: `src/lsl_harness/ring.py` provides `Ring` with `push`, `drain_upto`, `drops`.
- Metrics: `src/lsl_harness/metrics.py`
  - `compute_metrics(chunks, nominal_rate, ring_drops)` returns `Summary` dataclass (many fields: latency percentiles, jitter, drift, drops, ISI, R-R, etc.).
- Reporting: `src/lsl_harness/report.py`
  - Reads `summary.json`, `latency.csv`, `times.csv`; writes `latency_hist.png`, optional `drift_plot.png`, and `report.html` from `templates/report.html.j2`.

## Developer Workflows
- Dependency/env (uv):
  - Create venv + runtime deps: `uv venv --python 3.11 && uv sync`
  - Dev deps: `uv sync --group dev`
- Run tests: `uv run pytest -q` (configured via `[tool.pytest.ini_options]`)
- Lint/format: `ruff format` and `ruff check` (line length 88; Google-style docstrings)
- CLI quickstart:
  - Collect: `uv run lsl-harness measure --duration-seconds 5 --summary --json-summary`
  - Report: `uv run lsl-harness report results/run_001`

## Data Artifacts (written by `measure`)
- `latency.csv` with header `latency_ms`
- `times.csv` with headers `src_time,recv_time`
- `summary.json`: merges `Summary.__dict__` and environment/parameters
  - CLI can also emit compact JSON to stdout with `--json-summary`.

## Conventions & Patterns
- Typing: Python 3.11 features are used; prefer `Path | None` over `Optional[Path]` in annotations.
- Typer:
  - Avoid function calls in default arguments (Ruff B008). Use booleans or `None`, then handle inside the function.
  - For required arguments, prefer Typer’s `Argument(...)` pattern, but to satisfy B008 use it directly in the signature only when allowed by your lint config; otherwise use a parameter that defaults to `None` and prompt/validate in the body.
- Docstrings: Google style; summary line must start on the first line; wrap at 88 chars.
- File I/O: Use `Path` and explicit encodings; check existence and raise `FileNotFoundError` with clear messages.
- Matplotlib: Always `plt.close()` after saving; use constants like `PLOT_DPI`.
- Jinja2: Template loader at `Path(__file__).parent / "templates"`; render with explicit context keys.

## External Dependencies & Environment
- `pylsl==1.16.*`, `numpy==2.0.*`, `jinja2`, `matplotlib`, `typer`, `rich`.
- Linux/WSL: `pylsl` needs `liblsl.so`. If missing, set `PYLSL_LIB` to a valid `liblsl.so` (see `README.md`).

## Testing & Examples
- Unit tests live in `tests/` (e.g., `test_metrics.py`, `test_ring.py`). Keep changes focused; don’t break existing APIs without updating tests.
- Example flow in code:
  - Acquisition loop drains with `ring.drain_upto(N)` to avoid blocking.
  - Metrics use a single receive timestamp per chunk to approximate per-sample latency by shifting by `(ts_last - ts_i)`.

## When Adding Features
- Extending metrics: add fields to `Summary`; `summary.json` will include them automatically (CLI dumps `summary.__dict__`).
- Adding CLI flags: prefer boolean flags (`--feature/--no-feature`) for toggles; document args and side effects; keep console tables short.
- New artifacts: update both writer (in `measure`) and reader (in `report`) and adjust the template.

## Gotchas
- Ruff rules: B008 (no calls in defaults), Dxxx (docstrings), UP (use modern union types), 88-col wrap.
- `Path | None` parameters: validate and convert to `Path` before calling functions that require `Path`.

If anything here is unclear or you need more detail on a specific workflow (e.g., CI, fixtures, or adding plots/metrics), propose an update and we’ll refine this guide.
