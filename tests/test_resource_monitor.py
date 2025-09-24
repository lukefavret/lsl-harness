"""Tests for resource monitoring helpers in lsl_harness.resource_monitor.

Includes unit tests for ResourceMonitor using fake psutil/process/clock classes.
"""

import pytest

from lsl_harness.resource_monitor import ResourceMonitor


class _FakeMemoryInfo:
    """Fake memory info object to mimic psutil's memory_info()."""

    def __init__(self, rss: float) -> None:
        self.rss = rss


class _FakeProcess:
    """Fake process object to mimic psutil.Process().

    Args:
        cpu_values (list[float]): Sequence of CPU percent values to yield.
        rss_values (list[float]): Sequence of RSS values to yield.
    """

    def __init__(self, cpu_values: list[float], rss_values: list[float]) -> None:
        self._cpu_values = iter(cpu_values)
        self._rss_values = iter(rss_values)

    def cpu_percent(self, interval=None):  # noqa: D401 - mirror psutil signature
        """Return next fake CPU percent value."""
        return next(self._cpu_values)

    def memory_info(self):  # noqa: D401 - mirror psutil signature
        """Return next fake memory info object."""
        return _FakeMemoryInfo(next(self._rss_values))


class _FakePsutil:
    """Fake psutil module to inject into ResourceMonitor for testing.

    Args:
        per_core_samples (list[list[float]]): List of per-core CPU percent samples.
    """

    def __init__(self, per_core_samples: list[list[float]]) -> None:
        self._process = _FakeProcess(
            cpu_values=[0.0, 10.0, 20.0, 30.0],
            rss_values=[100.0, 200.0, 300.0],
        )
        self._per_core_iter = iter(per_core_samples)

    def Process(self):  # noqa: D401 - mirror psutil signature
        """Return fake process object."""
        return self._process

    def cpu_percent(self, interval=None, percpu=False):  # noqa: D401 - mirror psutil signature
        """Return next per-core CPU percent sample."""
        if not percpu:
            raise AssertionError("Only percpu=True calls are expected in tests")
        return next(self._per_core_iter)


class _FakeClock:
    """Fake monotonic clock for deterministic time advancement in tests."""

    def __init__(self) -> None:
        self.value = 0.0

    def advance(self, delta: float) -> float:
        """Advance the clock by delta seconds and return the new value."""
        self.value += delta
        return self.value

    def __call__(self) -> float:  # pragma: no cover - trivial
        """Return the current clock value."""
        return self.value


def test_resource_monitor_collects_and_averages():
    """ResourceMonitor aggregates process/system CPU and RSS correctly."""
    per_core_samples = [
        [0.0, 0.0],  # warm-up discard (used only to prime)
        [40.0, 60.0],
        [50.0, 55.0],
        [45.0, 50.0],
    ]
    clock = _FakeClock()
    monitor = ResourceMonitor(
        sample_interval_seconds=0.5,
        psutil_module=_FakePsutil(per_core_samples),
        monotonic_fn=clock,
    )

    # First maybe_sample should not sample (interval not elapsed)
    assert not monitor.maybe_sample(now=clock.advance(0.2))
    # Next two exceed interval
    assert monitor.maybe_sample(now=clock.advance(0.4))
    assert monitor.maybe_sample(now=clock.advance(0.6))
    # Finalize after advancing again
    clock.advance(0.5)
    monitor.finalize()

    usage = monitor.snapshot()
    assert usage is not None
    # Process cpu samples taken: 10.0, 20.0, 30.0 -> average 20.0
    assert usage.process_cpu_percent_avg == pytest.approx(20.0)
    # RSS samples captured correspond to each CPU sample (excluding priming).
    # Sequence yields rss values: 100.0, 200.0, 300.0 -> average 200.0
    assert usage.process_rss_avg_bytes == pytest.approx((100.0 + 200.0 + 300.0) / 3.0)
    # Per-core averages: [40,60],[50,55],[45,50]
    expected_core0 = (40.0 + 50.0 + 45.0) / 3.0
    expected_core1 = (60.0 + 55.0 + 50.0) / 3.0
    assert usage.system_cpu_percent_avg == pytest.approx(
        (expected_core0 + expected_core1) / 2.0
    )
    assert usage.system_cpu_percent_per_core_avg[0] == pytest.approx(expected_core0)
    assert usage.system_cpu_percent_per_core_avg[1] == pytest.approx(expected_core1)


def test_snapshot_none_when_no_samples():
    """Snapshot returns None if no sampling occurred."""
    clock = _FakeClock()
    monitor = ResourceMonitor(
        sample_interval_seconds=0.5,
        psutil_module=_FakePsutil([[0.0, 0.0]]),
        monotonic_fn=clock,
    )
    # No sampling performed
    assert monitor.snapshot() is None
