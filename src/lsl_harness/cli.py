"""LSL stream measurement and reporting tool.

This script provides command-line utilities to measure and report on the performance
of an LSL (Lab Streaming Layer) stream. It includes commands for collecting data
over a specified duration, computing key metrics like latency and jitter, and
generating a human-readable HTML report from the collected data.
"""

import csv
import importlib.metadata
import json
import platform
import sys
import time
from pathlib import Path
from typing import Annotated

import typer
from rich import print
from rich.table import Table

from .metrics import compute_metrics
from .resource_monitor import ResourceMonitor

LATENCY_CSV_FILE = "latency.csv"
LATENCY_CSV_HEADERS = ["latency_ms"]

TIMES_CSV_FILE = "times.csv"
TIMES_CSV_HEADERS = ["src_time", "recv_time"]

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def measure(
    stream_key: str = typer.Option(
        "type", help="LSL resolve key (e.g., 'name' or 'type')"
    ),
    stream_value: str = typer.Option("EEG", help="LSL resolve value"),
    duration_seconds: float = 10.0,
    chunk_size: int = 32,
    nominal_sample_rate: float = 1000.0,
    output_directory: Path = Path("results/run_001"),
    print_summary: bool = typer.Option(
        True,
        "--summary/--no-summary",
        help="Print brief metrics summary to the console.",
    ),
    verbose_summary: bool = typer.Option(
        False,
        "--verbose-summary/--no-verbose-summary",
        help="Include extended metrics in the console summary.",
    ),
    json_summary: bool = typer.Option(
        False,
        "--json-summary/--no-json-summary",
        help="Print metrics as a compact JSON object to stdout.",
    ),
):
    """Collect samples from an LSL stream and write JSON+CSV artifacts for reporting.

    This command-line utility connects to an LSL stream, collects a specified
    duration of data, and saves key metrics and raw data to files for
    subsequent analysis and reporting.

    Args:
        stream_key: The LSL resolve key (e.g., 'name', 'type').
        stream_value: The LSL resolve value to match.
        duration_seconds: The duration in seconds to collect samples.
        chunk_size: The maximum number of samples to pull from the stream per chunk.
        nominal_sample_rate: The nominal sample rate of the stream in Hz.
        output_directory: The directory where result files will be saved.
        It will be created if it does not exist.
        print_summary: Whether to print a concise metrics table to the console
          (default: True).
        verbose_summary: Whether to include extended metrics in the table
          (default: False).
        json_summary: Whether to print the metrics as compact JSON to stdout
          (default: False).

    Side Effects:
        - Writes `latency.csv`, `times.csv`, and `summary.json` to the output directory.
        - Prints a completion message to the console.
        - Optionally prints a summary table and/or JSON to stdout.
    """
    from .measure import InletWorker

    output_directory.mkdir(parents=True, exist_ok=True)

    inlet_worker = InletWorker(selector=(stream_key, stream_value), chunk=chunk_size)
    inlet_worker.start()

    try:
        resource_monitor = ResourceMonitor()
    except RuntimeError as e:
        print(f"[yellow]Warning:[/] Resource monitoring is disabled ({e})")
        resource_monitor = None

    end_time = time.time() + duration_seconds
    collected_samples: list[tuple] = []

    try:
        # Collect in small increments to avoid blocking and stay responsive.
        while time.time() < end_time:
            if resource_monitor is not None:
                resource_monitor.maybe_sample()
            collected_samples.extend(inlet_worker.ring.drain_upto(16))
            time.sleep(0.01)
        # After the main collection, drain any remaining samples from the buffer.
        collected_samples.extend(inlet_worker.ring.drain_upto(1_000_000))
    finally:
        inlet_worker.stop()
        if resource_monitor is not None:
            resource_monitor.finalize()

    # Use 'with' to manage both file handles safely
    with (
        open(output_directory / LATENCY_CSV_FILE, "w", newline="") as latency_file,
        open(output_directory / TIMES_CSV_FILE, "w", newline="") as times_file,
    ):
        # Create CSV writers for both files
        latency_writer = csv.writer(latency_file)
        times_writer = csv.writer(times_file)

        # Write headers
        latency_writer.writerow(LATENCY_CSV_HEADERS)
        times_writer.writerow(TIMES_CSV_HEADERS)

        # Process each chunk of collected samples
        for _data, src_timestamp_list, receive_timestamp in collected_samples:
            # Iterate through each individual sample within the chunk
            for src_timestamp in src_timestamp_list:
                # Calculate latency for the single sample
                latency_ms = (receive_timestamp - src_timestamp) * 1000.0

                # Write the individual rows directly to the files
                latency_writer.writerow([latency_ms])
                times_writer.writerow([src_timestamp, receive_timestamp])

    summary = compute_metrics(
        collected_samples, nominal_sample_rate, ring_drops=inlet_worker.ring.drops
    )
    resource_usage = (
        resource_monitor.snapshot() if resource_monitor is not None else None
    )
    # Merge summary fields and resource usage into a single dictionary
    summary_dict = dict(summary.__dict__)
    if resource_usage is not None:
        summary_dict.update(
            {
                "process_cpu_percent_avg": resource_usage.process_cpu_percent_avg,
                "process_rss_avg_bytes": resource_usage.process_rss_avg_bytes,
                "system_cpu_percent_avg": resource_usage.system_cpu_percent_avg,
                "system_cpu_percent_per_core_avg": (
                    resource_usage.system_cpu_percent_per_core_avg
                ),
            }
        )
    metadata = {
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pylsl_version": importlib.metadata.version("pylsl"),
        },
        "parameters": {
            "selector": {"key": stream_key, "value": stream_value},
            "duration_seconds": duration_seconds,
            "chunk_size": chunk_size,
            "nominal_sample_rate": nominal_sample_rate,
        },
    }

    with open(output_directory / "summary.json", "w") as summary_file:
        json.dump({**summary_dict, **metadata}, summary_file, indent=2)

    # Optionally print a concise summary table of key metrics
    if print_summary:
        title = (
            "Measurement Summary (verbose)"
            if verbose_summary
            else "Measurement Summary"
        )
        table = Table(title=title, show_lines=False)
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        table.add_row("p50 latency", f"{summary.p50_ms:.2f} ms")
        table.add_row("p95 latency", f"{summary.p95_ms:.2f} ms")
        table.add_row("p99 latency", f"{summary.p99_ms:.2f} ms")
        table.add_row("jitter (p95-p50)", f"{summary.jitter_ms:.2f} ms")
        table.add_row(
            "eff. sample rate",
            f"{summary.effective_sample_rate_hz:.2f} Hz",
        )
        table.add_row(
            "drift",
            f"{summary.drift_ms_per_min:.2f} ms/min",
        )
        table.add_row("drops", f"{summary.drops_percentage:.2f} %")
        table.add_row("samples", f"{summary.total_sample_count}")
        table.add_row("ring drops", f"{summary.ring_drops}")
        if summary.process_cpu_percent_avg is not None:
            table.add_row("proc CPU (avg)", f"{summary.process_cpu_percent_avg:.1f} %")
        if summary.system_cpu_percent_avg is not None:
            table.add_row("system CPU (avg)", f"{summary.system_cpu_percent_avg:.1f} %")
        if summary.process_rss_avg_bytes is not None:
            rss_mib = summary.process_rss_avg_bytes / (1024**2)
            table.add_row("proc RSS (avg)", f"{rss_mib:.1f} MiB")

        if verbose_summary:
            table.add_row("max latency", f"{summary.max_latency_ms:.2f} ms")
            table.add_row("jitter std", f"{summary.jitter_std:.2f} ms")
            table.add_row("ISI p95", f"{summary.isi_p95_ms:.2f} ms")
            table.add_row("ISI p99", f"{summary.isi_p99_ms:.2f} ms")
            table.add_row("R-R std", f"{summary.rr_std_ms:.2f} ms")
            table.add_row(
                "seq discontinuities",
                f"{summary.sequence_discontinuities}",
            )
            if summary.system_cpu_percent_per_core_avg:
                per_core = ", ".join(
                    f"c{idx}:{value:.1f}%"
                    for idx, value in enumerate(summary.system_cpu_percent_per_core_avg)
                )
                table.add_row("system CPU/core", per_core)

        print(table)

    print("[bold green]Done[/] ->", output_directory)

    # Optional: print compact JSON summary to stdout for scripting
    if json_summary:
        print(json.dumps(summary.__dict__, separators=(",", ":")))


@app.command()
def report(
    run: Annotated[
        Path | None,
        typer.Option(
            "--run",
            help=(
                "Results directory containing summary.json (option). If omitted, "
                "fallback to 'results/run_001' if it exists; otherwise prompt (TTY)."
            ),
        ),
    ] = None,
):
    """Render an HTML report from measurement artifacts.

    If --run is not provided: use 'results/run_001' if present; otherwise prompt
    (only when running interactively with a TTY).
    """
    from .report import render_html_report

    selected = run
    if selected is None:
        default_path = Path("results/run_001")
        if default_path.exists():
            selected = default_path
        elif sys.stdin.isatty():  # pragma: no cover
            selected = typer.prompt(
                "Enter the results directory containing summary.json",
                type=Path,
            )
        else:
            raise typer.BadParameter(
                "No --run provided and default 'results/run_001' not found"
            )
    render_html_report(selected)


if __name__ == "__main__":
    app()
