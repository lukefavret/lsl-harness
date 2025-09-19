"""Functions for computing performance metrics from LSL chunk data."""
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np


@dataclass
class Summary:
    """Container for computed performance metrics.

    Attributes:
        p50_ms (float): Median (50th percentile) latency in milliseconds.
        p95_ms (float): 95th percentile latency in milliseconds.
        p99_ms (float): 99th percentile latency in milliseconds.
        max_latency_ms (float): Maximum observed latency in milliseconds (worst-case single sample).
        jitter_ms (float): Jitter, defined as (p95 - p50) latency in milliseconds.
        jitter_std (float): Standard deviation of all per-sample latencies (ms).
        effective_sample_rate_hz (float): Effective sample rate in Hz, based on source timestamps.
        drift_ms_per_min (float): Estimated clock drift in milliseconds per minute (recv - src slope).
        drop_estimate (float): Estimated percentage of dropped samples compared to nominal rate.
        total_sample_count (int): Total number of samples received.
        ring_drops (int): Count of items dropped by the ring buffer.
        isi_mean_ms (float): Mean inter-sample interval (ISI) in milliseconds (source clock).
        isi_std_ms (float): Standard deviation of ISI (ms).
        isi_p50_ms (float): Median (50th percentile) ISI in milliseconds.
        isi_p95_ms (float): 95th percentile ISI in milliseconds.
        isi_p99_ms (float): 99th percentile ISI in milliseconds.
        sequence_discontinuities (int): Number of chunks where the first timestamp is less than the previous chunk's last timestamp (chronological order violation).
    """

    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_latency_ms: float
    jitter_ms: float
    jitter_std: float
    effective_sample_rate_hz: float
    drift_ms_per_min: float
    drop_estimate: float  # %
    total_sample_count: int
    ring_drops: int
    isi_mean_ms: float
    isi_std_ms: float
    isi_p50_ms: float
    isi_p95_ms: float
    isi_p99_ms: float
    sequence_discontinuities: int


def compute_metrics(chunks: Iterable[tuple[np.ndarray, np.ndarray, float]], nominal_rate: float, ring_drops: int = 0) -> Summary:
    """Compute latency, jitter, effective sample rate, drift, drop estimate, and ISI metrics from LSL chunk data.

    Args:
        chunks (Iterable): Iterable of tuples (data, ts, recv) where:
            data (np.ndarray): Array of shape (n_samples, n_channels) (float32).
            ts (np.ndarray): Source timestamps in seconds (float64), length n_samples.
            recv (float): Single receive time in seconds for the entire chunk.
        nominal_rate (float): Claimed sample rate of the stream, in Hz.
        ring_drops (int, optional): Count of items overwritten or rejected by the ring buffer. Defaults to 0.

    Returns:
        Summary: Container with:
            - p50/p95/p99 latency (ms)
            - max_latency_ms (worst-case single-sample latency, ms)
            - jitter (ms) and jitter_std (ms)
            - effective sample rate (Hz)
            - drift (ms/min)
            - drop_estimate (%)
            - total sample count
            - ring_drops
            - ISI mean, std, and percentiles (ms)

    Raises:
        ValueError: If the total number of samples is less than 8.

    Notes:
        - Latency uses one receive timestamp per chunk (approximation).
        - Drift is the least-squares slope of (recv - src) over time, reported in ms/min.
        - Drop estimate compares expected (nominal_rate * duration) vs. received samples.
        - ISI (inter-sample interval) metrics are computed from source timestamps and reflect the timing regularity of the data source itself.
    """
    # --- Aggregate all samples and timestamps from chunks ---
    latencies = []
    recv_times = []
    src_times = []
    total_sample_count = 0
    sequence_discontinuities = 0
    prev_last_ts = None

    for _data, source_timestamps, chunk_rcv_timestamp in chunks:
        sample_count = len(source_timestamps)
        if sample_count == 0:
            continue
        # Chronological order check: first ts of this chunk vs last ts of previous chunk
        if prev_last_ts is not None and source_timestamps[0] < prev_last_ts:
            sequence_discontinuities += 1
        prev_last_ts = float(source_timestamps[-1])

        total_sample_count += sample_count
        # Reconstruct per-sample receive timestamps assuming the provided
        # chunk receive time corresponds to the last sample in the chunk.
        # This yields recv_individual = recv_last - (ts_last - ts_individual), which equals ts_individual + constant latency.
        ts_last = float(source_timestamps[-1])
        per_sample_recv = chunk_rcv_timestamp - (ts_last - source_timestamps)
        # Compute per-sample latency (ms) for samples in this chunk
        chunk_latencies = (per_sample_recv - source_timestamps) * 1000.0
        # Convert to Python floats to avoid keeping a reference to the NumPy array, 
        # which helps with memory management and prevents unintended side effects from array mutation
        # (np types, like np.float64, can hold references to the original array. Specifically, when np does a view rather than a copy)
        latencies.extend(chunk_latencies.tolist())
        recv_times.extend(per_sample_recv.tolist())
        src_times.extend(source_timestamps.tolist())

    # --- Validate sample count ---
    if total_sample_count < 8:
        raise ValueError("Not enough samples")

    # --- Convert lists to numpy arrays for efficient computation ---
    latency_array = np.array(latencies, dtype=np.float64)
    recv_timestamp_array = np.array(recv_times, dtype=np.float64)
    src_timestamps_array = np.array(src_times, dtype=np.float64)

    # --- Compute latency percentiles, max, and jitter, jitter standard deviation---
    p50, p95, p99 = np.percentile(latency_array, [50, 95, 99])
    max_latency_ms = float(np.max(latency_array))
    jitter_ms = p95 - p50
    jitter_std = np.std(latency_array)

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
    expected_sample_count = nominal_rate * duration
    drops_percentage = float(max(0.0, (expected_sample_count - total_sample_count) / max(expected_sample_count, 1.0) * 100.0))

    # --- Compute ISI (inter-sample interval) statistics ---
    isi = np.diff(src_timestamps_array)
    isi_ms = isi * 1000.0
    isi_mean = float(np.mean(isi_ms))
    isi_std = float(np.std(isi_ms))
    isi_p50, isi_p95, isi_p99 = np.percentile(isi_ms, [50, 95, 99])

    # --- Package results in Summary dataclass ---
    return Summary(
        float(p50),
        float(p95),
        float(p99),
        max_latency_ms,
        float(jitter_ms),
        float(jitter_std),
        float(effective_sample_rate_hz),
        float(drift_ms_per_min),
        drops_percentage,
        int(total_sample_count),
        int(ring_drops),
        isi_mean,
        isi_std,
        float(isi_p50),
        float(isi_p95),
        float(isi_p99),
        int(sequence_discontinuities),
    )
