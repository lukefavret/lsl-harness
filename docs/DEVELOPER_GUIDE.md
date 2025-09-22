# Developer Guide — lsl-harness

This guide dives into architecture, data flow, artifacts, plotting/reporting, testing, and extensibility. It complements `CONTRIBUTING.md` and the README.

## Table of contents

- Architecture overview
- Data artifacts and formats
- Acquisition and buffering
- Metrics and calculations
- Reporting and templates
- Plotting (headless vs interactive)
- Testing strategy
- Performance and troubleshooting
- Conventions and style
- Extensibility playbook

## Architecture overview

- CLI (`src/lsl_harness/cli.py`): Typer app with two commands:
  - `measure`: pulls samples, writes artifacts, prints summary (optionally JSON)
  - `report`: reads artifacts and renders HTML via Jinja2 templates
- Acquisition (`src/lsl_harness/measure.py`):
  - `InletWorker` resolves an LSL stream and pulls chunks in a background thread into a `Ring`
- Buffer (`src/lsl_harness/ring.py`): lock-free-ish `Ring` with `push`, `drain_upto`, `drops`
- Metrics (`src/lsl_harness/metrics.py`):
  - `compute_metrics(chunks, nominal_rate, ring_drops)` → `Summary` dataclass (latency percentiles, jitter, drift, drops, ISI, R–R, etc.)
- Reporting (`src/lsl_harness/report.py`):
  - Reads `summary.json`, `latency.csv`, `times.csv`; writes `latency_hist.png`, optional `drift_plot.png`, and `report.html` from `templates/report.html.j2`

## Data artifacts and formats

Written by `measure` into a run directory (e.g., `results/run_001/`):
- `latency.csv` — header `latency_ms`; one value per sample
- `times.csv` — headers `src_time,recv_time` (optional; enables drift plot)
- `summary.json` — merged `Summary.__dict__` + environment/parameters (nominal rate, chunk size, duration, selector)

Conventions:
- Use SI units; times in seconds unless suffixed `_ms`
- Explicit encodings for file I/O (`utf-8`) via `pathlib.Path`

## Acquisition and buffering

- Acquisition loop drains with `ring.drain_upto(N)` to avoid blocking
- `Ring.drops()` counts overwritten entries; include in `Summary.ring_drops`
- Edge cases and guidance:
  - Handle empty reads and partial final chunks
  - Keep a single receive timestamp per chunk and back-calculate per-sample latency by index offset

## Metrics and calculations

`compute_metrics` inputs:

- `chunks`: iterable of `(src_timestamps, recv_time)`
- `nominal_rate`: float (Hz)
- `ring_drops`: int (from `Ring`)

Outputs (`Summary` fields include, not exhaustive):

- Latency percentiles (p50, p95, p99, max) in ms
- Jitter and jitter std
- Effective sample rate
- Drops percentage and counts
- Inter-sample interval (ISI) stats
- R–R (chunk-to-chunk) stats
- Drift slope (ms/min)
- Sequence discontinuities

Edge cases:

- Few samples → percentiles may be degenerate; tests cover reduced inputs
- Single-row `times.csv` → ensure proper shape when loading

## Reporting and templates

- Jinja2 templates live in `src/lsl_harness/templates/`
- Template loader: `Path(__file__).parent / "templates"`
- Render with explicit context keys; pass `drift_plot` flag to indicate `times.csv` presence
- Save plots with explicit DPI (`PLOT_DPI`) and `bbox_inches="tight"`; always `plt.close()`

## Plotting (headless vs interactive)

Headless/CI default:

- Matplotlib is configured to use the non-interactive `Agg` backend in `lsl_harness/report.py` before importing `pyplot`.
- This avoids GUI toolkit initialization that can trigger warnings (treated as errors in tests) and ensures rendering works in CI.

Adding plotting code:

- Import `plt` from `lsl_harness.report` (preferred) or set `matplotlib.use("Agg")` before `import matplotlib.pyplot as plt` in your module.
- Close figures after saving; stick to constants for DPI and bins.

Interactive plots (optional direction):

- For HTML interactivity, consider Plotly (preferred) or mpld3. If adding, also provide a static fallback for CI/tests and a CLI toggle (`--interactive/--no-interactive`).

## Testing strategy

- Tests live under `tests/` and cover ring buffer, metrics, report rendering, and CLI
- Pytest configured with `filterwarnings = error` (warnings-as-errors) in `pytest.ini`
- Write small, focused tests (happy path + 1–2 edge/boundary cases)
- Prefer deterministic behavior; seed where randomness is involved (fixtures exist under `src/lsl_harness/fixtures/`)

## Performance and troubleshooting

- `pylsl` on Linux/WSL: ensure `liblsl.so` is present; if missing, set `PYLSL_LIB` to a valid path
- CPU scheduling variance exists; keep runs consistent and document versions
- Large runs: drain ring periodically; avoid unbounded memory growth

## Conventions and style

- Python 3.11 typing; prefer `Path | None` over `Optional[Path]`
- Docstrings: Google style; summary line on first line; wrap at 88 chars
- Lint/format: `ruff format` and `ruff check` (see `pyproject.toml`)
- Typer patterns: avoid default-arg calls (B008); use booleans/None and validate in function body
- File I/O: explicit encodings; clear `FileNotFoundError` messages when expecting artifacts

## Extensibility playbook

- Adding a metric:
  1. Extend `Summary` in `metrics.py`
  2. Update computation in `compute_metrics`
  3. Ensure `summary.json` includes the new fields (automatic via `__dict__`)
  4. Update report template to display the metric
  5. Add/adjust tests
- Adding a plot:
  1. Reuse `plt` from `report.py` or set `Agg` before pyplot import
  2. Save to run directory with consistent naming, `PLOT_DPI`, and `plt.close()`
  3. Update template and tests
- Adding a CLI flag:
  - Prefer `--flag/--no-flag` toggles; document behavior and defaults in help text

---

Questions or corrections? Open a PR improving this guide alongside your change.
