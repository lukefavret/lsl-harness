from dataclasses import dataclass

import numpy as np


@dataclass
class Summary:
    p50_ms: float
    p95_ms: float
    p99_ms: float
    jitter_ms: float
    eff_hz: float
    drift_ms_per_min: float
    drop_estimate: float  # %
    n_samples: int
    ring_drops: int


def compute_metrics(chunks, nominal_rate: float, ring_drops: int = 0) -> Summary:
    latencies = []
    recv_times = []
    src_times = []
    n_total = 0

    for data, ts, recv in chunks:
        n = len(ts)
        if n == 0:
            continue
        n_total += n
        latencies.extend((recv - ts) * 1000.0)  # ms
        recv_times.extend([recv] * n)
        src_times.extend(ts)

    if n_total < 8:
        raise ValueError("Not enough samples")

    lat = np.array(latencies, dtype=np.float64)
    recv_arr = np.array(recv_times, dtype=np.float64)
    src_arr = np.array(src_times, dtype=np.float64)

    p50, p95, p99 = np.percentile(lat, [50, 95, 99])
    jitter = p95 - p50

    dur = float(max(src_arr[-1] - src_arr[0], 1e-6))
    eff_hz = n_total / dur

    offset_ms = (recv_arr - src_arr) * 1000.0
    t_norm = src_arr - src_arr[0]
    A = np.vstack([t_norm, np.ones_like(t_norm)]).T
    slope_ms_per_s, _ = np.linalg.lstsq(A, offset_ms, rcond=None)[0]
    drift_ms_per_min = float(slope_ms_per_s * 60.0)

    expected = nominal_rate * dur
    drops_pct = float(max(0.0, (expected - n_total) / max(expected, 1.0) * 100.0))

    return Summary(
        float(p50),
        float(p95),
        float(p99),
        float(jitter),
        float(eff_hz),
        float(drift_ms_per_min),
        drops_pct,
        int(n_total),
        int(ring_drops),
    )
