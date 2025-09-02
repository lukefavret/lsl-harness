import csv
import json
import platform
import sys
import time
from pathlib import Path

import typer
from rich import print

from .metrics import compute_metrics

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def measure(
    selector_key: str = typer.Option("type", help="resolve key (e.g., name|type)"),
    selector_val: str = typer.Option("EEG", help="resolve value"),
    duration_s: float = 10.0,
    chunk: int = 32,
    nominal_rate: float = 1000.0,
    out: Path = Path("results/run_001"),
):
    """Collect samples and write JSON+CSV artifacts for reporting."""
    from .measure import InletWorker

    out.mkdir(parents=True, exist_ok=True)
    w = InletWorker(selector=(selector_key, selector_val), chunk=chunk)
    w.start()
    t_end = time.time() + duration_s
    collected = []
    while time.time() < t_end:
        collected.extend(w.ring.drain_upto(16))
        time.sleep(0.01)
    w.stop()
    collected.extend(w.ring.drain_upto(1_000_000))

    # Save raw per-sample latency and times for plots
    lat_ms, src_times, recv_times = [], [], []
    for _data, ts, recv in collected:
        lat_ms.extend([(recv - t) * 1000.0 for t in ts])
        src_times.extend(ts.tolist())
        recv_times.extend([recv] * len(ts))

    with open(out / "latency.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["latency_ms"])
        wr.writerows([[x] for x in lat_ms])

    with open(out / "times.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["src_time", "recv_time"])
        wr.writerows([[s, r] for s, r in zip(src_times, recv_times, strict=True)])

    summary = compute_metrics(collected, nominal_rate, ring_drops=w.ring.drops)
    meta = {
        "env": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pylsl_version": "1.16.x (pinned)",
        },
        "params": {
            "selector": {"key": selector_key, "val": selector_val},
            "duration_s": duration_s,
            "chunk": chunk,
            "nominal_rate": nominal_rate,
        },
    }
    with open(out / "summary.json", "w") as f:
        json.dump({**summary.__dict__, **meta}, f, indent=2)

    print("[bold green]Done[/] ->", out)


@app.command()
def report(run: Path = None):
    """Render HTML report from artifacts."""
    from .report import render_report

    if run is None:
        run = typer.Argument(..., help="results directory containing summary.json")
    render_report(run)


if __name__ == "__main__":
    app()
