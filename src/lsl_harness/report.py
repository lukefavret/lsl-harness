"""Functions for generating an HTML report from measurement results."""
import json
from pathlib import Path

import jinja2
import matplotlib.pyplot as plt
import numpy as np

LATENCY_CSV_FILE = "latency.csv"
TIMES_CSV_FILE = "times.csv"
SUMMARY_JSON_FILE = "summary.json"

LATENCY_HIST_BINS = 50
PLOT_DPI = 120
MS_PER_SECOND = 1000.0

def render_report(run_dir: Path) -> None:
    """Generates an HTML report with plots from saved run data.

    Reads ``summary.json``, ``latency.csv``, and optionally ``times.csv`` from the specified run directory.
    Generates a latency histogram plot, and if ``times.csv`` is available, a drift plot.
    Renders an HTML report using a Jinja2 template.

    Args:
        run_dir (Path): Path to the directory containing the run data.

    Returns:
        None

    Side Effects:
        Creates the following files in ``run_dir``:
            - ``latency_hist.png``: Histogram of latencies.
            - ``drift_plot.png``: Plot of clock offset over time (optional).
            - ``report.html``: The final HTML report.
    """
    # --- Load summary data ---
    run_dir = Path(run_dir)
    summary_path = run_dir / SUMMARY_JSON_FILE
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing required file: {summary_path}")
    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))

    # --- Generate latency histogram plot ---
    latency_csv_path = run_dir / LATENCY_CSV_FILE
    if not latency_csv_path.exists():
        raise FileNotFoundError(f"Missing required file: {latency_csv_path}")
    latency_data = np.loadtxt(latency_csv_path, delimiter=",", skiprows=1, ndmin=1)
    plt.figure()
    plt.hist(latency_data, LATENCY_HIST_BINS)
    plt.xlabel("Latency (ms)")
    plt.ylabel("Count")
    plt.title("Latency Histogram")
    plt.savefig(run_dir / "latency_hist.png", dpi=PLOT_DPI, bbox_inches="tight")
    plt.close()

    # --- Generate drift plot if times.csv exists ---
    drift_plot = False
    times_path = run_dir / TIMES_CSV_FILE
    if times_path.exists():
        time_data_array = np.loadtxt(times_path, delimiter=",", skiprows=1)
        # If only one row is present, np.loadtxt returns a 1D array; reshape to 2D for consistency
        if time_data_array.ndim == 1:
            time_data_array = time_data_array[None, :]
        source_timestamps = time_data_array[:, 0]
        received_timestamps = time_data_array[:, 1]
        offset_ms = (received_timestamps - source_timestamps) * MS_PER_SECOND
        time_diff_from_start = source_timestamps - source_timestamps[0]
        plt.figure()
        plt.plot(time_diff_from_start, offset_ms)
        plt.xlabel("Time (s)")
        plt.ylabel("Offset (ms)")
        plt.title("Offset vs Time (Drift)")
        plt.savefig(run_dir / "drift_plot.png", dpi=120, bbox_inches="tight")
        plt.close()
        drift_plot = True

    # --- Render HTML report using Jinja2 template ---
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"), autoescape=False
    )
    tmpl = env.get_template("report.html.j2")
    html = tmpl.render(drift_plot=drift_plot, **summary_data)
    (run_dir / "report.html").write_text(html, encoding="utf-8")
