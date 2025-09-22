import pytest
from typer.testing import CliRunner
from pathlib import Path
import json
import csv
import sys
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from lsl_harness.cli import app

runner = CliRunner()

@pytest.fixture(autouse=True)
def mock_pylsl(monkeypatch):
    """Fixture to mock the entire pylsl module to avoid liblsl dependency."""
    mock_pylsl_module = MagicMock()
    monkeypatch.setitem(sys.modules, 'pylsl', mock_pylsl_module)

@pytest.fixture
def mock_inlet_worker():
    """Fixture to mock the InletWorker."""
    with patch('lsl_harness.measure.InletWorker') as mock:
        # Mock the ring buffer and its drain_upto method
        mock_ring = MagicMock()
        # Simulate some collected samples
        mock_ring.drain_upto.return_value = [
            (MagicMock(), [1.0, 1.1], 1.2),
            (MagicMock(), [1.2, 1.3], 1.4)
        ]
        mock_ring.drops = 5

        mock_worker_instance = mock.return_value
        mock_worker_instance.ring = mock_ring

        yield mock

@pytest.fixture
def mock_compute_metrics():
    """Fixture to mock the compute_metrics function."""
    with patch('lsl_harness.cli.compute_metrics') as mock:
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
        )
        mock.return_value = mock_summary
        yield mock

def test_measure_command(tmp_path, mock_inlet_worker, mock_compute_metrics):
    """Test the 'measure' command."""
    output_dir = tmp_path / "test_run"
    with patch('time.sleep'), patch('time.time') as mock_time:
        # Control the collection loop to run exactly once
        mock_time.side_effect = [1000.0, 1000.05, 1000.11]
        result = runner.invoke(app, ["measure", "--output-directory", str(output_dir), "--duration-seconds", "0.1"])

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
    with open(summary_path, 'r') as f:
        summary_data = json.load(f)
    assert summary_data['p50_ms'] == 10.0
    assert summary_data['parameters']['duration_seconds'] == 0.1

    # Check the content of latency.csv
    with open(latency_path, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ['latency_ms']
        rows = list(reader)
        # drain_upto is called once in the loop and once after
        assert len(rows) == 8

def test_measure_json_summary(tmp_path, mock_inlet_worker, mock_compute_metrics):
    """Test the 'measure' command with --json-summary."""
    output_dir = tmp_path / "test_run"
    result = runner.invoke(app, ["measure", "--output-directory", str(output_dir), "--duration-seconds", "0.1", "--json-summary", "--no-summary"])

    assert result.exit_code == 0

    # The JSON is printed after the "Done ->" line, but might be wrapped.
    stdout = result.stdout.strip()
    json_part_start = stdout.find('{')
    assert json_part_start != -1, "Could not find start of JSON in output"

    # Reconstruct the JSON string by removing newlines
    json_output = stdout[json_part_start:].replace('\n', '')

    assert json_output, "No JSON output found"
    summary_data = json.loads(json_output)
    assert summary_data['p50_ms'] == 10.0

def test_report_command(tmp_path):
    """Test the 'report' command."""
    # First, create some dummy data that the report command can use
    run_dir = tmp_path / "test_run"
    run_dir.mkdir()

    summary_data = {
        "p50_ms": 10.0, "p95_ms": 20.0, "p99_ms": 30.0, "max_latency_ms": 40.0,
        "jitter_ms": 10.0, "jitter_std": 2.0, "effective_sample_rate_hz": 1000.0,
        "drops_percentage": 5.0, "total_sample_count": 100, "ring_drops": 5,
        "isi_mean_ms": 1.0, "isi_std_ms": 0.1, "isi_p50_ms": 1.0, "isi_p95_ms": 1.1, "isi_p99_ms": 1.2,
        "rr_mean_ms": 10.0, "rr_std_ms": 0.5, "drift_ms_per_min": 1.0, "sequence_discontinuities": 1,
        "parameters": {"selector": {"key": "type", "value": "EEG"}, "duration_seconds": 10, "chunk_size": 32, "nominal_sample_rate": 1000},
        "environment": {"python": "3.11", "platform": "linux", "pylsl_version": "1.16.2"}
    }
    with open(run_dir / "summary.json", 'w') as f:
        json.dump(summary_data, f)

    with open(run_dir / "latency.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['latency_ms'])
        writer.writerow([10.0])
        writer.writerow([20.0])

    with patch('lsl_harness.report.plt.show'), \
         patch('lsl_harness.report.plt.savefig') as mock_savefig:
        result = runner.invoke(app, ["report", "--run", str(run_dir)])

    assert result.exit_code == 0

    report_path = run_dir / "report.html"
    assert report_path.exists()

    # Check that plots were generated
    assert mock_savefig.called

    with open(report_path, 'r') as f:
        report_content = f.read()
    assert "<h1>LSL Harness Report</h1>" in report_content
    assert "<td>10.0 ms</td>" in report_content
