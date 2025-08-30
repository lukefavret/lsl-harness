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
