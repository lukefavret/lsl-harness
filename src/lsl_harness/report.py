"""Functions for generating an HTML report from measurement results.

This module provides utilities to read measurement results, generate plots, and render a
human-readable HTML report using Jinja2 templates. It checks for required files and uses
constants for filenames and plotting parameters.
"""

import json
from pathlib import Path

import jinja2

# Third-party imports; set non-interactive backend before importing pyplot
import matplotlib

matplotlib.use("Agg")  # must be set before importing pyplot
import matplotlib.pyplot as plt
import numpy as np

LATENCY_CSV_FILE = "latency.csv"
TIMES_CSV_FILE = "times.csv"
SUMMARY_JSON_FILE = "summary.json"

LATENCY_HIST_BINS = 50
PLOT_DPI = 120
MS_PER_SECOND = 1000.0


def render_html_report(run_directory: Path) -> None:
    """Generate an HTML report with plots from measurement run data.

    This function checks for the existence of required files (``summary.json``,
    ``latency.csv``) in the specified run directory. It loads measurement
    results, generates a latency histogram plot, and, if ``times.csv`` is
    available, a drift plot. The report is rendered using a Jinja2 template and
    written to ``report.html``.

    Args:
        run_directory (Path): Path to the directory containing the run data.

    Raises:
        FileNotFoundError: If ``summary.json`` or ``latency.csv`` is missing in
        the run directory.

    Notes:
        - Uses constants for filenames and plotting parameters.
        - Creates the following files in ``run_directory``:
            - ``latency_hist.png``: Histogram of latencies.
            - ``drift_plot.png``: Plot of clock offset over time (optional).
            - ``report.html``: The final HTML report.
    """
    # Convert input to Path if not already
    run_directory = Path(run_directory)

    # --- Load summary data ---
    summary_file_path = run_directory / SUMMARY_JSON_FILE
    if not summary_file_path.exists():
        raise FileNotFoundError(f"Missing required file: {summary_file_path}")
    summary = json.loads(summary_file_path.read_text(encoding="utf-8"))

    # --- Generate latency histogram plot ---
    latency_file_path = run_directory / LATENCY_CSV_FILE
    if not latency_file_path.exists():
        raise FileNotFoundError(f"Missing required file: {latency_file_path}")
    latency_values = np.loadtxt(latency_file_path, delimiter=",", skiprows=1, ndmin=1)
    plt.figure()
    plt.hist(latency_values, bins=LATENCY_HIST_BINS)
    plt.xlabel("Latency (ms)")
    plt.ylabel("Count")
    plt.title("Latency Histogram")
    plt.savefig(
        run_directory / "latency_hist.png",
        dpi=PLOT_DPI,
        bbox_inches="tight",
    )
    plt.close()

    # --- Generate drift plot if times.csv exists ---
    drift_plot_exists = False
    times_file_path = run_directory / TIMES_CSV_FILE
    if times_file_path.exists():
        times_data = np.loadtxt(times_file_path, delimiter=",", skiprows=1)
        # If only one row is present, np.loadtxt returns a 1D array;
        # reshape to 2D for consistency
        if times_data.ndim == 1:
            times_data = times_data[None, :]
        source_times = times_data[:, 0]
        received_times = times_data[:, 1]
        offset_milliseconds = (received_times - source_times) * MS_PER_SECOND
        elapsed_seconds = source_times - source_times[0]
        plt.figure()
        plt.plot(elapsed_seconds, offset_milliseconds)
        plt.xlabel("Time (s)")
        plt.ylabel("Offset (ms)")
        plt.title("Offset vs Time (Drift)")
        plt.savefig(
            run_directory / "drift_plot.png",
            dpi=PLOT_DPI,
            bbox_inches="tight",
        )
        plt.close()
        drift_plot_exists = True

    # --- Render HTML report using Jinja2 template ---
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=False,
    )
    template = jinja_env.get_template("report.html.j2")
    html_report = template.render(drift_plot=drift_plot_exists, **summary)
    (run_directory / "report.html").write_text(html_report, encoding="utf-8")
