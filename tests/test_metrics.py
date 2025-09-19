import numpy as np

from lsl_harness.metrics import compute_metrics


def fake_chunks(n=1000):
    ts = np.linspace(0, 1, n, endpoint=False) + 1000.0
    recv = ts + 0.005
    yield (np.zeros((n, 1), dtype=np.float32), ts, recv[-1])


def test_metrics_basic():
    s = compute_metrics(list(fake_chunks()), 1000.0, ring_drops=0)
    assert 4.0 <= s.p50_ms <= 6.0
    assert s.drop_estimate == 0.0
    # ISI should be close to 1 ms for 1000 Hz, stddev near zero
    assert abs(s.isi_mean_ms - 1.0) < 1e-3
    assert s.isi_std_ms < 1e-6
    # Max latency should be close to p99 for this synthetic data
    assert abs(s.max_latency_ms - s.p99_ms) < 1.0

def test_max_latency_outlier():
    # All latencies are 5ms except one outlier at 100ms
    n = 1000
    ts = np.linspace(0, 1, n, endpoint=False) + 1000.0
    recv = ts + 0.005
    recv[-1] = ts[-1] + 0.1  # Outlier
    chunks = [(np.zeros((n, 1), dtype=np.float32), ts, recv[-1])]
    s = compute_metrics(chunks, 1000.0, ring_drops=0)
    assert s.max_latency_ms > 90.0
