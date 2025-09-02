"""Functions for generating an HTML report from measurement results."""
import json
from pathlib import Path

import jinja2
import matplotlib.pyplot as plt
import numpy as np

LATENCY_CSV_FILE = "latency.csv"

TIMES_CSV_FILE = "times.csv"

LATENCY_HIST_BINS = 50

def render_report(run_dir: Path) -> None:
    """Generate an HTML report with plots from saved run data.

    This function reads ``summary.json``, ``latency.csv``, and optionally
    ``times.csv`` from the specified run directory. It generates a latency
    histogram plot, and if ``times.csv`` is available, a drift plot. It then
    renders an HTML report using a Jinja2 template.

    The following files are created in ``run_dir``:
    - ``latency_hist.png``: A histogram of latencies.
    - ``drift_plot.png``: A plot of clock offset over time (optional).
    - ``report.html``: The final HTML report.

    Args:
      run_dir: The path to the directory containing the run data.

    """
    run_dir = Path(run_dir)
    summary_data = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    # Latency histogram
    latency_data = np.loadtxt(run_dir / LATENCY_CSV_FILE, delimiter=",", skiprows=1, ndmin=1)
    plt.figure()
    plt.hist(latency_data, LATENCY_HIST_BINS)
    plt.xlabel("Latency (ms)")
    plt.ylabel("Count")
    plt.title("Latency Histogram")
    plt.savefig(run_dir / "latency_hist.png", dpi=120, bbox_inches="tight")
    plt.close()

    # Optional drift plot if times.csv exists
    drift_plot = False
    times_path = run_dir / TIMES_CSV_FILE
    if times_path.exists():
        arr = np.loadtxt(times_path, delimiter=",", skiprows=1)
        if arr.ndim == 1:
            arr = arr[None, :]
        src = arr[:, 0]
        recv = arr[:, 1]
        offset_ms = (recv - src) * 1000.0
        t_norm = src - src[0]
        plt.figure()
        plt.plot(t_norm, offset_ms)
        plt.xlabel("Time (s)")
        plt.ylabel("Offset (ms)")
        plt.title("Offset vs Time (Drift)")
        plt.savefig(run_dir / "drift_plot.png", dpi=120, bbox_inches="tight")
        plt.close()
        drift_plot = True

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"), autoescape=False
    )
    tmpl = env.get_template("report.html.j2")
    html = tmpl.render(drift_plot=drift_plot, **summary_data)
    (run_dir / "report.html").write_text(html, encoding="utf-8")
