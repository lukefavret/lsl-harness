"""Functions for computing performance metrics from LSL chunk data."""
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np


@dataclass
class Summary:
    """Container for computed performance metrics.

    Attributes:
        p50_ms (float): p50 (median) latency in milliseconds.
        p95_ms (float): p95 latency in milliseconds.
        p99_ms (float): p99 latency in milliseconds.
        jitter_ms (float): Jitter (p95 - p50 latency) in milliseconds.
        effective_sample_rate_hz (float): Effective sample rate in Hz.
        drift_ms_per_min (float): Clock drift in milliseconds per minute.
        drop_estimate (float): Estimated percentage of dropped samples.
        total_sample_count (int): Total number of samples received.
        ring_drops (int): Count of items dropped by the ring buffer.
    """

    p50_ms: float
    p95_ms: float
    p99_ms: float
    jitter_ms: float
    effective_sample_rate_hz: float
    drift_ms_per_min: float
    drop_estimate: float  # %
    total_sample_count: int
    ring_drops: int


def compute_metrics(chunks: Iterable[tuple[np.ndarray, np.ndarray, float]], nominal_rate: float, ring_drops: int = 0) -> Summary:
    """Compute latency, jitter, effective sample rate, drift, and drop estimate from LSL chunk data.

    Args:
        chunks (Iterable): Iterable of tuples (data, ts, recv) where:
            data (np.ndarray): Array of shape (n_samples, n_channels) (float32).
            ts (np.ndarray): Source timestamps in seconds (float64), length n_samples.
            recv (float): Single receive time in seconds for the entire chunk.
        nominal_rate (float): Claimed sample rate of the stream, in Hz.
        ring_drops (int, optional): Count of items overwritten or rejected by the ring buffer. Defaults to 0.

    Returns:
        Summary: Container with p50/p95/p99 latency (ms), jitter (ms), effective sample rate (Hz),
            drift (ms/min), drop_estimate (%), total sample count, and ring_drops.

    Raises:
        ValueError: If the total number of samples is less than 8.

    Notes:
        Latency uses one receive timestamp per chunk (approximation).
        Drift is the least-squares slope of (recv - src) over time, reported in ms/min.
        Drop estimate compares expected (nominal_rate * duration) vs. received samples.
    """
    # --- Aggregate all samples and timestamps from chunks ---
    latencies = []
    recv_times = []
    src_times = []
    total_sample_count = 0

    for _data, source_timestamps, chunk_rcv_timestamp in chunks:
        sample_count = len(source_timestamps)
        if sample_count == 0:
            continue
        total_sample_count += sample_count
        # Compute per-sample latency (ms) for this chunk
        latencies.extend((chunk_rcv_timestamp - source_timestamps) * 1000.0)
        # Store receive time for each sample in the chunk
        recv_times.extend([chunk_rcv_timestamp] * sample_count)
        # Store source timestamps for each sample
        src_times.extend(source_timestamps)

    # --- Validate sample count ---
    if total_sample_count < 8:
        raise ValueError("Not enough samples")

    # --- Convert lists to numpy arrays for efficient computation ---
    latency_array = np.array(latencies, dtype=np.float64)
    recv_timestamp_array = np.array(recv_times, dtype=np.float64)
    src_timestamps_array = np.array(src_times, dtype=np.float64)

    # --- Compute latency percentiles and jitter ---
    p50, p95, p99 = np.percentile(latency_array, [50, 95, 99])
    jitter = p95 - p50

    # --- Compute effective sample rate (Hz) ---
    duration = float(max(src_timestamps_array[-1] - src_timestamps_array[0], 1e-6))
    effective_sample_rate_hz = total_sample_count / duration

    # --- Estimate clock drift (ms/min) using least-squares regression ---
    offset_ms = (recv_timestamp_array - src_timestamps_array) * 1000.0
    t_norm = src_timestamps_array - src_timestamps_array[0]
    regression_matrix = np.vstack([t_norm, np.ones_like(t_norm)]).T
    slope_ms_per_s, _ = np.linalg.lstsq(regression_matrix, offset_ms, rcond=None)[0]
    drift_ms_per_min = float(slope_ms_per_s * 60.0)

    # --- Estimate drop percentage compared to expected sample count ---
    expected = nominal_rate * duration
    drops_percentage = float(max(0.0, (expected - total_sample_count) / max(expected, 1.0) * 100.0))

    # --- Package results in Summary dataclass ---
    return Summary(
        float(p50),
        float(p95),
        float(p99),
        float(jitter),
        float(effective_sample_rate_hz),
        float(drift_ms_per_min),
        drops_percentage,
        int(total_sample_count),
        int(ring_drops),
    )
