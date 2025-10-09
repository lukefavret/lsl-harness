# LSL-Harness

LSL-Harness is a lightweight, portable tool for measuring surface-level performance of Lab Streaming Layer (LSL) streams. With it you can calculate latency, jitter, drift, effective sample rate, dropped samples, and (optionally) basic resource usage (CPU & memory) without spinning up a full LabRecorder pipeline.

[Quickstart](#quickstart)

## What it does

- Measure LSL latency, jitter, drift, effective sample rate, and drop percentages.
- Sample optional process + system resource usage (CPU %, RSS) during acquisition.
- Emit CSV + JSON artifacts that are easy to diff or archive.
- Render polished HTML summaries that you can share with teammates or attach to tickets.

## Quickstart

### 1. Prepare a Python environment

Install dependencies with your preferred tool:

```bash
# Using uv (recommended)
uv sync --frozen

# Using pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Both flows install the `lsl-harness` CLI as well as the `synthetic-outlet` helper script used in the next step.

### 2. Start the synthetic outlet

In one terminal, launch the built-in outlet that mimics an EEG-like stream:

```bash
# With uv
uv run synthetic-outlet

# With pip / virtualenv
synthetic-outlet
```

Leave this terminal running while you collect measurements.

### 3. Measure the stream

Open a second terminal in the project directory and record a run:

```bash
# Customize --duration-seconds or --output-directory as needed
uv run lsl-harness measure --duration-seconds 10 --output-directory results/demo_run
```

When the command finishes you will see a `results/demo_run/` directory containing:

- `latency.csv` — per-sample latency in milliseconds.
- `times.csv` — source and receive timestamps for drift analysis.
- `summary.json` — computed statistics and environment metadata (plus resource metrics if `psutil` is installed).

(If you omit `--output-directory`, the default is `results/run_001`.)

### 4. Render the HTML report

Transform the measurement artifacts into a shareable report:

```bash
uv run lsl-harness report results/demo_run
```

This writes the following files back into `results/demo_run/`:

- `report.html` — the full report to open in your browser.
- `latency_hist.png` — histogram of per-sample latency.
- `drift_plot.png` — offset-vs-time graph (present when `times.csv` exists).

## Configuration reference

The CLI, environment variables, and optional settings files all surface the same
configuration knobs. Values are resolved in the following order of precedence:

```md
CLI flags → Environment variables → Settings file → Built-in defaults
```

### `measure` command

| Purpose | CLI flag | Environment variable | Settings file key | Default |
| --- | --- | --- | --- | --- |
| Stream selector key | `--stream-key` | `LSL_MEASURE_STREAM_KEY` | `stream_key` | `"type"` |
| Stream selector value | `--stream-value` | `LSL_MEASURE_STREAM_VALUE` | `stream_value` | `"EEG"` |
| Acquisition duration (seconds) | `--duration-seconds` | `LSL_MEASURE_DURATION_SECONDS` | `duration_seconds` | `10.0` |
| Samples per pull | `--chunk-size` | `LSL_MEASURE_CHUNK_SIZE` | `chunk_size` | `32` |
| Nominal sample rate (Hz) | `--nominal-sample-rate` | `LSL_MEASURE_NOMINAL_SAMPLE_RATE` | `nominal_sample_rate` | `1000.0` |
| Output directory | `--output-directory` | `LSL_MEASURE_OUTPUT_DIRECTORY` | `output_directory` | `results/run_001` |
| Print console summary | `--summary/--no-summary` | `LSL_MEASURE_SUMMARY` | `print_summary` | `true` |
| Include extended metrics | `--verbose-summary/--no-verbose-summary` | `LSL_MEASURE_VERBOSE_SUMMARY` | `verbose_summary` | `false` |
| Emit JSON metrics to stdout | `--json-summary/--no-json-summary` | `LSL_MEASURE_JSON_SUMMARY` | `json_summary` | `false` |

Additional helpers:

- Use `--settings-file` (or `LSL_HARNESS_SETTINGS_FILE`) to point to a TOML/JSON
  file that mirrors the keys above. An example template lives at
  `docs/examples/measure_settings.toml`.
- All boolean environment variables accept any of `1/0`, `true/false`,
  `yes/no`, or `on/off` (case-insensitive).

### `report` command

| Purpose | CLI flag | Environment variable | Default |
| --- | --- | --- | --- |
| Results directory containing `summary.json` | `--run` | _(none)_ | `results/run_001` when present |

The report command does not currently read from a settings file. It falls back
to `results/run_001` if the flag is omitted and that directory exists. In a
non-interactive context without the flag the command raises a helpful error.

## Troubleshooting `PYLSL_LIB`

On Linux and WSL, `pylsl` looks for the native `liblsl.so` in its package directory, on the system library path, or wherever the `PYLSL_LIB` environment variable points. If you already run other LSL apps you probably have it available—otherwise try the following:

1. **Point to Conda’s copy** – If you installed `liblsl` through Conda or Mamba, run `export PYLSL_LIB="$CONDA_PREFIX/lib/liblsl.so"` before launching `lsl-harness`.
2. **Bundle a local build** – Drop `liblsl.so` under `vendor/liblsl/` in this repository and `export PYLSL_LIB="$(pwd)/vendor/liblsl/liblsl.so"`.
3. **Verify the setting** – Use `python -c "import pylsl, os; print(os.environ.get('PYLSL_LIB'), pylsl.lib.__file__)"` inside your virtual environment to confirm that Python can load the shared library.
4. **Check architecture mismatches** – Ensure that the `liblsl.so` you point to matches your Python architecture (e.g., both x86_64). A wrong architecture manifests as `OSError: wrong ELF class` when importing `pylsl`.

Once `pylsl` can load `liblsl.so`, re-run the quickstart steps above.

- Project license: MIT (see `LICENSE`).
- Third-party components: see `third_party_notices.md`.
