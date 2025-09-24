"""Tests for HTML report generation."""

import csv
import json
from unittest.mock import patch

import pytest

from lsl_harness.report import (
    LATENCY_CSV_FILE,
    SUMMARY_JSON_FILE,
    TIMES_CSV_FILE,
    render_html_report,
)


@pytest.fixture
def run_directory(tmp_path):
    """Fixture to create a dummy run directory with necessary files."""
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
    (run_dir / SUMMARY_JSON_FILE).write_text(json.dumps(summary_data))

    with open(run_dir / LATENCY_CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["latency_ms"])
        writer.writerow([10.0])
        writer.writerow([20.0])

    return run_dir


def test_render_html_report_success(run_directory):
    """Test successful generation of the HTML report."""
    with patch("lsl_harness.report.plt.savefig") as mock_savefig:
        render_html_report(run_directory)

    report_path = run_directory / "report.html"
    assert report_path.exists()

    # Should be called once for latency histogram
    assert mock_savefig.call_count == 1

    with open(report_path) as f:
        content = f.read()

    assert "<h1>LSL Harness Report</h1>" in content
    assert "<td>10.0 ms</td>" in content  # p50_ms


def test_render_html_report_with_drift_plot(run_directory):
    """Test report generation with the drift plot."""
    # Add times.csv to the run directory
    with open(run_directory / TIMES_CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["src_time", "recv_time"])
        writer.writerow([1000.0, 1000.01])
        writer.writerow([1001.0, 1001.02])

    with patch("lsl_harness.report.plt.savefig") as mock_savefig:
        render_html_report(run_directory)

    report_path = run_directory / "report.html"
    assert report_path.exists()

    # Should be called twice: latency hist and drift plot
    assert mock_savefig.call_count == 2

    with open(report_path) as f:
        content = f.read()

    assert 'src="drift_plot.png"' in content


def test_render_html_report_missing_summary(run_directory):
    """Test error handling when summary.json is missing."""
    (run_directory / SUMMARY_JSON_FILE).unlink()
    with pytest.raises(FileNotFoundError):
        render_html_report(run_directory)


def test_render_html_report_missing_latency_csv(run_directory):
    """Test error handling when latency.csv is missing."""
    (run_directory / LATENCY_CSV_FILE).unlink()
    with pytest.raises(FileNotFoundError):
        render_html_report(run_directory)
