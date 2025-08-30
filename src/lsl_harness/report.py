import json
from pathlib import Path

import jinja2
import matplotlib.pyplot as plt
import numpy as np


def render_report(run_dir: Path):
    run_dir = Path(run_dir)
    s = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    # Latency histogram
    lat = np.loadtxt(run_dir / "latency.csv", delimiter=",", skiprows=1, ndmin=1)
    plt.figure()
    plt.hist(lat, bins=50)
    plt.xlabel("Latency (ms)")
    plt.ylabel("Count")
    plt.title("Latency Histogram")
    plt.savefig(run_dir / "latency_hist.png", dpi=120, bbox_inches="tight")
    plt.close()

    # Optional drift plot if times.csv exists
    drift_plot = False
    times_path = run_dir / "times.csv"
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
    html = tmpl.render(drift_plot=drift_plot, **s)
    (run_dir / "report.html").write_text(html, encoding="utf-8")
