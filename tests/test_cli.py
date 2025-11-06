"""CLI command tests for lsl-harness.

Validates measure/report flows, JSON output, and integration with mocked metrics.
"""

import csv
import json
import sys
import textwrap
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from typer.testing import CliRunner

from lsl_harness.cli import app
from lsl_harness.metrics import reconstruct_receive_times

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_pylsl(monkeypatch):
    """Fixture to mock the entire pylsl module to avoid liblsl dependency."""
    mock_pylsl_module = MagicMock()
    monkeypatch.setitem(sys.modules, "pylsl", mock_pylsl_module)


@pytest.fixture
def sample_chunk_layout():
    """Provide deterministic sample data for CLI tests."""
    return [
        {"src": [1.0, 1.1], "recv": 1.2},
        {"src": [], "recv": 1.25},
        {"src": [1.2, 1.3], "recv": 1.4},
    ]


@pytest.fixture
def mock_inlet_worker(sample_chunk_layout):
    """Fixture to mock the InletWorker with predictable chunk drains."""
    with patch("lsl_harness.measure.InletWorker") as mock:
        mock_ring = MagicMock()

        # Each call to ``drain_upto`` returns the next batch of chunks.  The
        # sequence includes an empty chunk to exercise skip logic in the CLI.
        drain_plan = [
            [
                (
                    MagicMock(),
                    list(sample_chunk_layout[0]["src"]),
                    sample_chunk_layout[0]["recv"],
                ),
                (
                    MagicMock(),
                    list(sample_chunk_layout[1]["src"]),
                    sample_chunk_layout[1]["recv"],
                ),
            ],
            [
                (
                    MagicMock(),
                    list(sample_chunk_layout[2]["src"]),
                    sample_chunk_layout[2]["recv"],
                ),
            ],
            [],
        ]

        def drain_side_effect(_max_items):
            if drain_plan:
                return drain_plan.pop(0)
            return []

        mock_ring.drain_upto.side_effect = drain_side_effect
        mock_ring.drops = 5

        mock_worker_instance = mock.return_value
        mock_worker_instance.ring = mock_ring

        yield mock


@pytest.fixture
def mock_compute_metrics():
    """Fixture to mock the compute_metrics function."""
    with patch("lsl_harness.cli.compute_metrics") as mock:
        mock_summary = SimpleNamespace(
            p50_ms=10.0,
            p95_ms=20.0,
            p99_ms=30.0,
            jitter_ms=10.0,
            effective_sample_rate_hz=1000.0,
            drift_ms_per_min=1.0,
            drops_percentage=5.0,
            total_sample_count=100,
            ring_drops=5,
            max_latency_ms=40.0,
            jitter_std=2.0,
            isi_p95_ms=1.1,
            isi_p99_ms=1.2,
            rr_std_ms=0.5,
            sequence_discontinuities=1,
            # Add resource usage attributes for CLI summary compatibility
            process_cpu_percent_avg=None,
            process_rss_avg_bytes=None,
            system_cpu_percent_avg=None,
            system_cpu_percent_per_core_avg=(),
        )
        mock.return_value = mock_summary
        yield mock


def test_measure_command(
    tmp_path, sample_chunk_layout, mock_inlet_worker, mock_compute_metrics
):
    """Test the 'measure' command."""
    output_dir = tmp_path / "test_run"
    with patch("time.sleep"), patch("time.time") as mock_time:
        # Control the collection loop to run exactly once
        mock_time.side_effect = [1000.0, 1000.05, 1000.11]
        result = runner.invoke(
            app,
            [
                "measure",
                "--output-directory",
                str(output_dir),
                "--duration-seconds",
                "0.1",
            ],
        )

    assert result.exit_code == 0
    assert "Done" in result.stdout
    assert str(output_dir) in result.stdout

    # Check that the files were created
    summary_path = output_dir / "summary.json"
    latency_path = output_dir / "latency.csv"
    times_path = output_dir / "times.csv"

    assert summary_path.exists()
    assert latency_path.exists()
    assert times_path.exists()

    # Check the content of summary.json
    with open(summary_path) as f:
        summary_data = json.load(f)
    assert summary_data["p50_ms"] == 10.0
    assert summary_data["parameters"]["duration_seconds"] == 0.1

    # Check the content of latency.csv
    with open(latency_path) as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ["latency_ms"]
        rows = [float(row[0]) for row in reader]

    expected_latencies = []
    for chunk in sample_chunk_layout:
        if not chunk["src"]:
            continue
        per_sample_recv = reconstruct_receive_times(
            np.asarray(chunk["src"], dtype=np.float64), chunk["recv"]
        )
        expected_latencies.extend(
            (
                (per_sample_recv - np.asarray(chunk["src"], dtype=np.float64)) * 1000.0
            ).tolist()
        )

    assert rows == expected_latencies


def test_measure_records_reconstructed_receive_times(
    tmp_path, sample_chunk_layout, mock_inlet_worker, mock_compute_metrics
):
    """Regression test ensuring per-sample receive timestamps are reconstructed."""
    output_dir = tmp_path / "test_run_times"
    result = runner.invoke(
        app,
        [
            "measure",
            "--output-directory",
            str(output_dir),
            "--duration-seconds",
            "0.1",
        ],
    )

    assert result.exit_code == 0

    with open(output_dir / "times.csv") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ["src_time", "recv_time"]
        rows = [(float(src), float(recv)) for src, recv in reader]

    expected_rows: list[tuple[float, float]] = []
    for chunk in sample_chunk_layout:
        if not chunk["src"]:
            continue
        src_array = np.asarray(chunk["src"], dtype=np.float64)
        per_sample_recv = reconstruct_receive_times(src_array, chunk["recv"])
        expected_rows.extend(
            zip(src_array.tolist(), per_sample_recv.tolist(), strict=True)
        )

    assert rows == expected_rows


def test_measure_json_summary(tmp_path, mock_inlet_worker, mock_compute_metrics):
    """Test the 'measure' command with --json-summary."""
    output_dir = tmp_path / "test_run"
    result = runner.invoke(
        app,
        [
            "measure",
            "--output-directory",
            str(output_dir),
            "--duration-seconds",
            "0.1",
            "--json-summary",
            "--no-summary",
        ],
    )

    assert result.exit_code == 0

    # The JSON is printed after the "Done ->" line, but might be wrapped.
    stdout = result.stdout.strip()
    json_part_start = stdout.find("{")
    assert json_part_start != -1, "Could not find start of JSON in output"

    # Reconstruct the JSON string by removing newlines
    json_output = stdout[json_part_start:].replace("\n", "")

    assert json_output, "No JSON output found"
    summary_data = json.loads(json_output)
    assert summary_data["p50_ms"] == 10.0


def test_measure_uses_settings_file(tmp_path, mock_inlet_worker, mock_compute_metrics):
    """Ensure a settings file provides defaults for the measure command."""
    output_dir = tmp_path / "settings_run"
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        textwrap.dedent(
            f"""
            [measure]
            stream_key = "name"
            stream_value = "Config"
            duration_seconds = 0.1
            chunk_size = 16
            nominal_sample_rate = 250.0
            output_directory = "{output_dir.as_posix()}"
            print_summary = false
            json_summary = true
            """
        ).strip()
    )

    with patch("time.sleep"), patch("time.time") as mock_time:
        mock_time.side_effect = [1000.0, 1000.05, 1000.11, 1000.2, 1000.31]
        result = runner.invoke(
            app,
            ["measure", "--settings-file", str(settings_path)],
        )

    assert result.exit_code == 0
    summary_data = json.loads((output_dir / "summary.json").read_text())
    assert summary_data["parameters"]["selector"] == {"key": "name", "value": "Config"}
    assert summary_data["parameters"]["duration_seconds"] == 0.1
    assert summary_data["parameters"]["chunk_size"] == 16
    assert summary_data["parameters"]["nominal_sample_rate"] == 250.0


def test_measure_env_overrides_settings(
    tmp_path, mock_inlet_worker, mock_compute_metrics
):
    """Environment variables should override values from the settings file."""
    settings_output = tmp_path / "settings_base"
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        textwrap.dedent(
            f"""
            [measure]
            duration_seconds = 0.1
            output_directory = "{settings_output.as_posix()}"
            """
        ).strip()
    )

    env_output = tmp_path / "env_output"
    env = {
        "LSL_MEASURE_DURATION_SECONDS": "0.3",
        "LSL_MEASURE_OUTPUT_DIRECTORY": str(env_output),
    }

    with patch("time.sleep"), patch("time.time") as mock_time:
        mock_time.side_effect = [1000.0, 1000.05, 1000.11, 1000.2, 1000.35, 1000.51]
        result = runner.invoke(
            app,
            ["measure", "--settings-file", str(settings_path)],
            env=env,
        )

    assert result.exit_code == 0
    summary_data = json.loads((env_output / "summary.json").read_text())
    assert summary_data["parameters"]["duration_seconds"] == 0.3


def test_measure_cli_overrides_env(tmp_path, mock_inlet_worker, mock_compute_metrics):
    """CLI arguments should take precedence over environment variables."""
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text("[measure]\nduration_seconds = 0.1\n")

    env_output = tmp_path / "env_output"
    cli_output = tmp_path / "cli_output"
    env = {
        "LSL_MEASURE_DURATION_SECONDS": "0.3",
        "LSL_MEASURE_OUTPUT_DIRECTORY": str(env_output),
    }

    with patch("time.sleep"), patch("time.time") as mock_time:
        mock_time.side_effect = [
            1000.0,
            1000.05,
            1000.11,
            1000.2,
            1000.35,
            1000.45,
            1000.6,
        ]
        result = runner.invoke(
            app,
            [
                "measure",
                "--settings-file",
                str(settings_path),
                "--duration-seconds",
                "0.5",
                "--output-directory",
                str(cli_output),
            ],
            env=env,
        )

    assert result.exit_code == 0
    summary_data = json.loads((cli_output / "summary.json").read_text())
    assert summary_data["parameters"]["duration_seconds"] == 0.5
    assert summary_data["parameters"]["selector"] == {"key": "type", "value": "EEG"}


def test_report_command(tmp_path):
    """Test the 'report' command."""
    # First, create some dummy data that the report command can use
    run_dir = tmp_path / "test_run"
    run_dir.mkdir()
    summary_data = {
        "p50_ms": 10.0,
        "p95_ms": 20.0,
        "p99_ms": 30.0,
        "max_latency_ms": 40.0,
        "jitter_ms": 10.0,
        "jitter_std": 2.0,
        "effective_sample_rate_hz": 1000.0,
        "drops_percentage": 5.0,
        "total_sample_count": 100,
        "ring_drops": 5,
        "isi_mean_ms": 1.0,
        "isi_std_ms": 0.1,
        "isi_p50_ms": 1.0,
        "isi_p95_ms": 1.1,
        "isi_p99_ms": 1.2,
        "rr_mean_ms": 10.0,
        "rr_std_ms": 0.5,
        "drift_ms_per_min": 1.0,
        "sequence_discontinuities": 1,
        # Resource metrics (None acceptable) for template
        "process_cpu_percent_avg": None,
        "process_rss_avg_bytes": None,
        "system_cpu_percent_avg": None,
        "system_cpu_percent_per_core_avg": [],
        "parameters": {
            "selector": {"key": "type", "value": "EEG"},
            "duration_seconds": 10,
            "chunk_size": 32,
            "nominal_sample_rate": 1000,
        },
        "environment": {
            "python": "3.11",
            "platform": "linux",
            "pylsl_version": "1.16.2",
        },
    }
    with open(run_dir / "summary.json", "w") as f:
        json.dump(summary_data, f)

    with open(run_dir / "latency.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["latency_ms"])
        writer.writerow([10.0])
        writer.writerow([20.0])

    with (
        patch("lsl_harness.report.plt.show"),
        patch("lsl_harness.report.plt.savefig") as mock_savefig,
    ):
        result = runner.invoke(app, ["report", "--run", str(run_dir)])

    assert result.exit_code == 0

    report_path = run_dir / "report.html"
    assert report_path.exists()

    # Check that plots were generated
    assert mock_savefig.called

    with open(report_path) as f:
        report_content = f.read()
    assert "<h1>LSL Harness Report</h1>" in report_content
    assert "<td>10.0 ms</td>" in report_content
