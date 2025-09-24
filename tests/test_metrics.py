"""Unit tests for lsl_harness.metrics.

This module tests the compute_metrics function using synthetic LSL-like data.
It verifies latency percentiles, jitter, effective rate, drift, drop percent,
ISI stats, sequence discontinuities, and receive-interval (R-R) metrics.
"""

import numpy as np
import pytest

from lsl_harness.metrics import compute_metrics


def generate_synthetic_chunk(num_samples=1000):
    """Yield a single synthetic chunk of LSL data for testing.

    Args:
        num_samples (int): Number of samples in the chunk.

    Yields:
        tuple: (data, timestamps, receive_time) where:
            data (np.ndarray): Array of zeros, shape (num_samples, 1), dtype float32.
            timestamps (np.ndarray): Source timestamps, evenly spaced, offset by 1000.0.
            receive_time (float): Receive time for the chunk (last ts + 5ms).
    """
    timestamps = np.linspace(0, 1, num_samples, endpoint=False) + 1000.0
    receive_times = timestamps + 0.005
    yield (np.zeros((num_samples, 1), dtype=np.float32), timestamps, receive_times[-1])


def test_metrics_basic():
    """Test compute_metrics with a basic synthetic chunk.

    Verifies latency, drop percentage, ISI mean/std, and max latency behavior.
    """
    summary = compute_metrics(list(generate_synthetic_chunk()), 1000.0, ring_drops=0)
    assert 4.0 <= summary.p50_ms <= 6.0
    assert summary.drops_percentage == 0.0
    # ISI should be close to 1 ms for 1000 Hz, stddev near zero
    assert abs(summary.isi_mean_ms - 1.0) < 1e-3
    assert summary.isi_std_ms < 1e-6
    # Max latency should be close to p99 for this synthetic data
    assert abs(summary.max_latency_ms - summary.p99_ms) < 1.0
    # Resource metrics defaults
    assert summary.process_cpu_percent_avg is None
    assert summary.process_rss_avg_bytes is None
    assert summary.system_cpu_percent_avg is None
    assert summary.system_cpu_percent_per_core_avg == ()


def test_max_latency_outlier():
    """Test that compute_metrics correctly identifies a max latency outlier.

    Sets all latencies to 5ms except one at 100ms, checks max_latency_ms > 90ms.
    """
    num_samples = 1000
    timestamps = np.linspace(0, 1, num_samples, endpoint=False) + 1000.0
    receive_times = timestamps + 0.005
    receive_times[-1] = timestamps[-1] + 0.1  # Outlier for last sample
    chunk = (
        np.zeros((num_samples, 1), dtype=np.float32),
        timestamps,
        receive_times[-1],
    )
    summary = compute_metrics([chunk], 1000.0, ring_drops=0)
    assert summary.max_latency_ms > 90.0


def make_chunk(
    num_samples: int,
    start_time_s: float,
    sample_rate_hz: float,
    latency_ms: float,
):
    """Create a single chunk with evenly spaced timestamps and fixed latency.

    Returns a tuple suitable for compute_metrics: (data, timestamps, receive_time).
    """
    dt = 1.0 / sample_rate_hz
    timestamps = start_time_s + np.arange(num_samples, dtype=np.float64) * dt
    receive_time = float(timestamps[-1] + latency_ms / 1000.0)
    data = np.zeros((num_samples, 1), dtype=np.float32)
    return (data, timestamps, receive_time)


def test_percentiles_and_jitter():
    """Verify p50/p95/p99 and jitter from mixed-latency chunks."""
    # 900 samples at 5 ms, 100 samples at 20 ms
    chunk_5ms = make_chunk(900, 0.0, 1000.0, 5.0)
    chunk_20ms = make_chunk(100, 0.9, 1000.0, 20.0)
    summary = compute_metrics(
        [chunk_5ms, chunk_20ms], nominal_rate=1000.0, ring_drops=0
    )
    assert 4.9 <= summary.p50_ms <= 5.1
    assert 19.9 <= summary.p95_ms <= 20.1
    assert 19.9 <= summary.p99_ms <= 20.1
    assert 14.8 <= summary.jitter_ms <= 15.2
    # jitter_std equals std of a vector with 900x5 and 100x20
    latencies = np.array([5.0] * 900 + [20.0] * 100, dtype=np.float64)
    expected_std = float(np.std(latencies))
    assert abs(summary.jitter_std - expected_std) < 1e-9


def test_effective_sample_rate_and_total_count():
    """Check effective sample rate calculation and total sample count."""
    chunk_750 = make_chunk(750, 0.0, 1000.0, 5.0)
    chunk_250 = make_chunk(250, 0.75, 1000.0, 5.0)
    chunks = [chunk_750, chunk_250]
    summary = compute_metrics(chunks, nominal_rate=1000.0, ring_drops=3)
    # Total count is exact
    assert summary.total_sample_count == 1000
    assert summary.ring_drops == 3
    # Compute expected effective rate using same formula
    all_timestamps = np.concatenate([chunk_750[1], chunk_250[1]])
    duration = float(all_timestamps[-1] - all_timestamps[0])
    expected_rate = 1000 / max(duration, 1e-6)
    assert abs(summary.effective_sample_rate_hz - expected_rate) < 1e-9


def test_drift_ms_per_min_least_squares():
    """Validate drift using the same least-squares method as implementation."""
    # First second at 5 ms, second second at 15 ms latency
    chunk_5ms = make_chunk(1000, 0.0, 1000.0, 5.0)
    chunk_15ms = make_chunk(1000, 1.0, 1000.0, 15.0)
    summary = compute_metrics(
        [chunk_5ms, chunk_15ms], nominal_rate=1000.0, ring_drops=0
    )
    # Recompute expected slope using the exact algorithm
    all_timestamps = np.concatenate([chunk_5ms[1], chunk_15ms[1]])
    recv_last_offsets = np.array([5.0] * 1000 + [15.0] * 1000) / 1000.0
    # Per-sample recv = ts_i + const_offset for each chunk -> offsets constant
    offset_ms = recv_last_offsets * 1000.0
    t_norm = all_timestamps - all_timestamps[0]
    regression_matrix = np.vstack([t_norm, np.ones_like(t_norm)]).T
    slope_ms_per_s, _ = np.linalg.lstsq(regression_matrix, offset_ms, rcond=None)[0]
    expected_drift = float(slope_ms_per_s * 60.0)
    assert abs(summary.drift_ms_per_min - expected_drift) < 1e-9


def test_drop_percentage():
    """Check drop percentage against expected for under-sampled stream."""
    # Build 1500 samples over ~2 seconds at 1000 Hz -> ~25% drop vs nominal
    chunk_1000 = make_chunk(1000, 0.0, 1000.0, 5.0)
    chunk_500 = make_chunk(500, 1.0, 1000.0, 5.0)
    chunks = [chunk_1000, chunk_500]
    summary = compute_metrics(chunks, nominal_rate=1000.0, ring_drops=0)
    all_timestamps = np.concatenate([chunk_1000[1], chunk_500[1]])
    duration = float(all_timestamps[-1] - all_timestamps[0])
    expected_drop_pct = 100.0 * max(
        0.0,
        (1000.0 * duration - 1500) / max(1000.0 * duration, 1.0),
    )
    assert abs(summary.drops_percentage - expected_drop_pct) < 1e-9


def test_isi_statistics():
    """ISI stats should match a perfectly uniform 1000 Hz source."""
    chunk_uniform = make_chunk(2000, 0.0, 1000.0, 5.0)
    summary = compute_metrics([chunk_uniform], nominal_rate=1000.0, ring_drops=0)
    assert abs(summary.isi_mean_ms - 1.0) < 1e-12
    assert summary.isi_std_ms < 1e-12
    assert abs(summary.isi_p50_ms - 1.0) < 1e-12
    assert abs(summary.isi_p95_ms - 1.0) < 1e-12
    assert abs(summary.isi_p99_ms - 1.0) < 1e-12


def test_sequence_discontinuities_and_rr_stats():
    """Count out-of-order chunk and verify R-R mean/std in ms."""
    # Two chunks where the second starts earlier than the end of the first
    chunk_early = make_chunk(1000, 0.0, 1000.0, 5.0)
    chunk_overlap = make_chunk(500, 0.9, 1000.0, 10.0)
    chunk_late = make_chunk(500, 1.6, 1000.0, 10.0)
    # Set explicit receive times to control R-R: 10.00s, 10.05s, 10.12s
    chunk_early = (chunk_early[0], chunk_early[1], 10.00)
    chunk_overlap = (chunk_overlap[0], chunk_overlap[1], 10.05)
    chunk_late = (chunk_late[0], chunk_late[1], 10.12)
    summary = compute_metrics(
        [chunk_early, chunk_overlap, chunk_late],
        nominal_rate=1000.0,
        ring_drops=0,
    )
    assert summary.sequence_discontinuities == 1
    assert abs(summary.rr_mean_ms - 60.0) < 1e-12
    assert abs(summary.rr_std_ms - 10.0) < 2e-12


def test_rr_warning_and_zero_values(recwarn):
    """With one or zero chunks, RR stats should be zero and warn."""
    # Ensure this test sees the warning, overriding global ignore
    import warnings

    warnings.filterwarnings(
        "default",
        message="R-R interval statistics will be zero",
        category=UserWarning,
        module=r"lsl_harness\.metrics",
    )
    chunk = make_chunk(1000, 0.0, 1000.0, 5.0)
    with pytest.warns(UserWarning, match="R-R interval statistics will be zero"):
        summary = compute_metrics([chunk], nominal_rate=1000.0, ring_drops=0)
    assert summary.rr_mean_ms == 0.0
    assert summary.rr_std_ms == 0.0


def test_raises_value_error_for_small_sample_count():
    """Total samples < 8 should raise ValueError."""
    chunk = make_chunk(7, 0.0, 1000.0, 5.0)
    with pytest.raises(ValueError):
        compute_metrics([chunk], nominal_rate=1000.0, ring_drops=0)


def test_zero_duration_guard_and_rate():
    """Identical timestamps trigger MIN_DURATION guard and compute rate accordingly."""
    # Create a chunk where all timestamps are identical
    num_samples = 100
    timestamps = np.array([1000.0] * num_samples, dtype=np.float64)
    data = np.zeros((num_samples, 1), dtype=np.float32)
    receive_time = float(timestamps[-1] + 0.005)
    chunk = (data, timestamps, receive_time)
    summary = compute_metrics([chunk], nominal_rate=1000.0, ring_drops=0)
    # Duration is clamped to 1e-6, effective rate = n / 1e-6
    assert abs(summary.effective_sample_rate_hz - num_samples / 1e-6) < 1e-3
    # ISI metrics degenerate to zeros since diff of identical timestamps is zero-length
    assert summary.isi_mean_ms == 0.0
    assert summary.isi_std_ms == 0.0


def test_non_uniform_isi_statistics():
    """ISI stats reflect variable interval sequence."""
    # Manually craft non-uniform source intervals: 1ms,2ms,3ms repeating
    intervals_ms = np.array([1.0, 2.0, 3.0] * 1000, dtype=np.float64)
    intervals_s = intervals_ms / 1000.0
    timestamps = 1000.0 + np.cumsum(np.concatenate([[0.0], intervals_s]))
    data = np.zeros((len(timestamps), 1), dtype=np.float32)
    receive_time = float(timestamps[-1] + 0.005)
    chunk = (data, timestamps, receive_time)
    summary = compute_metrics([chunk], nominal_rate=1000.0, ring_drops=0)
    assert abs(summary.isi_mean_ms - float(np.mean(intervals_ms))) < 1e-12
    assert abs(summary.isi_std_ms - float(np.std(intervals_ms))) < 1e-10
    p50, p95, p99 = np.percentile(intervals_ms, [50, 95, 99])
    assert abs(summary.isi_p50_ms - float(p50)) < 1e-10
    assert abs(summary.isi_p95_ms - float(p95)) < 1e-10
    assert abs(summary.isi_p99_ms - float(p99)) < 1e-10


def test_negative_drift():
    """Drift goes negative when latency decreases over time."""
    chunk_high_latency = make_chunk(1000, 0.0, 1000.0, 20.0)
    chunk_low_latency = make_chunk(1000, 1.0, 1000.0, 5.0)
    summary = compute_metrics(
        [chunk_high_latency, chunk_low_latency],
        nominal_rate=1000.0,
        ring_drops=0,
    )
    assert summary.drift_ms_per_min < 0.0


def test_rr_stats_many_single_sample_chunks():
    """RR mean/std computed correctly across many 1-sample chunks."""
    # Build 8 one-sample chunks with receive times at specified intervals
    timestamp_value = 1000.0
    receive_times_s = [0.0, 0.1, 0.25, 0.45, 0.7, 1.0, 1.4, 1.9]
    single_sample_chunks = []
    for receive_time in receive_times_s:
        data = np.zeros((1, 1), dtype=np.float32)
        timestamps = np.array([timestamp_value], dtype=np.float64)
        single_sample_chunks.append((data, timestamps, receive_time))
    summary = compute_metrics(single_sample_chunks, nominal_rate=1000.0, ring_drops=0)
    rr_intervals_ms = np.diff(np.array(receive_times_s)) * 1000.0
    assert abs(summary.rr_mean_ms - float(np.mean(rr_intervals_ms))) < 1e-12
    assert abs(summary.rr_std_ms - float(np.std(rr_intervals_ms))) < 1e-12


def test_sequence_equal_boundary_no_discontinuity():
    """If chunk2 starts exactly at last ts of chunk1, no discontinuity."""
    # chunk1 ends at t=1.0, chunk2 starts at exactly 1.0
    chunk1 = make_chunk(1000, 0.0, 1000.0, 5.0)
    chunk2 = make_chunk(500, 1.0, 1000.0, 10.0)
    chunk1 = (chunk1[0], chunk1[1], 10.00)
    chunk2 = (chunk2[0], chunk2[1], 10.05)
    summary = compute_metrics([chunk1, chunk2], nominal_rate=1000.0, ring_drops=0)
    assert summary.sequence_discontinuities == 0
