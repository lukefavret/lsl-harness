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

import typer
from rich import print

from .metrics import compute_metrics

LATENCY_CSV_FILE = "latency.csv"
LATENCY_CSV_HEADERS = ["latency_ms"]

TIME_CSV_FILE = "times.csv"
TIMES_CSV_HEADERS = ["src_time", "recv_time"]

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def measure(
    stream_key: str = typer.Option("type", help="LSL resolve key (e.g., 'name' or 'type')"),
    stream_value: str = typer.Option("EEG", help="LSL resolve value"),
    duration_seconds: float = 10.0,
    chunk_size: int = 32,
    nominal_sample_rate: float = 1000.0,
    output_directory: Path = Path("results/run_001"),
):
    """Collect samples from an LSL stream and writes JSON+CSV artifacts for reporting.

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

    Side Effects:
        - Writes `latency.csv`, `times.csv`, and `summary.json` to the output directory.
        - Prints a completion message to the console.

    """
    from .measure import InletWorker

    output_directory.mkdir(parents=True, exist_ok=True)

    inlet_worker = InletWorker(selector=(stream_key, stream_value), chunk=chunk_size)
    inlet_worker.start()

    end_time = time.time() + duration_seconds
    collected_samples = []

    # Collect samples in small increments to avoid blocking and ensure responsiveness.
    while time.time() < end_time:
        collected_samples.extend(inlet_worker.ring.drain_upto(16))
        time.sleep(0.01)

    # After the main collection, drain any remaining samples from the buffer.
    collected_samples.extend(inlet_worker.ring.drain_upto(1_000_000))
    inlet_worker.stop()

    # Use 'with' to manage both file handles safely
    with open(output_directory / LATENCY_CSV_FILE, "w", newline="") as latency_file, \
         open(output_directory / TIME_CSV_FILE, "w", newline="") as times_file:

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

    summary = compute_metrics(collected_samples, nominal_sample_rate, ring_drops=inlet_worker.ring.drops)
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
        json.dump({**summary.__dict__, **metadata}, summary_file, indent=2)

    print("[bold green]Done[/] ->", output_directory)


@app.command()
def report(run: Path = None):
    """Render an HTML report from measurement artifacts in a results directory.

    Args:
        run (Path): Path to the results directory containing summary.json.

    Side Effects:
        Renders and writes an HTML report to the results directory.
    """
    if run is None:
        run = typer.Argument(..., help="results directory containing summary.json")
    from .report import render_report

    render_report(run)

if __name__ == "__main__":
    app()
