"""Resource usage sampling utilities for lsl-harness measurements.

Provides a ResourceMonitor for periodic CPU/memory sampling and a ResourceUsage
dataclass for summary stats.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import fmean
from time import monotonic
from typing import Any

# Try to import psutil for resource monitoring; handle missing dependency gracefully.
try:  # pragma: no cover - import is only exercised at runtime, not during tests
    import psutil as _psutil  # type: ignore
except ModuleNotFoundError as exc:
    # pragma: no cover - fallback path is only hit if psutil is missing at runtime
    _psutil = None  # type: ignore
    _PSUTIL_IMPORT_ERROR = exc  # type: ignore
else:
    # pragma: no cover - else branch is only hit if psutil import succeeds at runtime
    _PSUTIL_IMPORT_ERROR = None


@dataclass(frozen=True)
class ResourceUsage:
    """Aggregate CPU and memory statistics collected during a measurement.

    Attributes:
        process_cpu_percent_avg (float): Average CPU percent for the process.
        process_rss_avg_bytes (float): Average resident set size (RSS) in bytes.
        system_cpu_percent_avg (float | None):
            Average system-wide CPU percent, or None if unavailable.
        system_cpu_percent_per_core_avg (tuple[float, ...]):
            Average CPU percent per core.
    """

    process_cpu_percent_avg: float
    process_rss_avg_bytes: float
    system_cpu_percent_avg: float | None
    system_cpu_percent_per_core_avg: tuple[float, ...]


class ResourceMonitor:
    """Periodically sample CPU and memory usage for the current process.

    Collects process and system CPU usage and memory (RSS) at a fixed interval.
    Samples are aggregated for summary statistics via the snapshot() method.
    """

    def __init__(
        self,
        *,
        sample_interval_seconds: float = 0.5,
        psutil_module: Any | None = None,
        monotonic_fn: Callable[[], float] | None = None,
    ) -> None:
        """Initialize a resource monitor.

        Args:
            sample_interval_seconds (float): Minimum seconds between samples.
            psutil_module (Any | None):
                Optional injected psutil-like module for testing.
            monotonic_fn (Callable[[], float] | None):
                Optional injected monotonic clock for testing.

        Raises:
            ValueError: If sample_interval_seconds is not positive.
            RuntimeError: If psutil is not available and not injected.
        """
        if sample_interval_seconds <= 0:
            raise ValueError("sample_interval_seconds must be positive")

        if psutil_module is None:
            if _psutil is None:
                message = (
                    "psutil is required to sample resource metrics. Install it or "
                    "provide a compatible module via psutil_module."
                )
                raise RuntimeError(message) from _PSUTIL_IMPORT_ERROR
            psutil_module = _psutil

        self._psutil = psutil_module
        self._interval = sample_interval_seconds
        self._monotonic = monotonic_fn or monotonic
        self._last_sample_time = self._monotonic()
        self._process = self._psutil.Process()
        self._process_cpu_samples: list[float] = []
        self._rss_samples: list[float] = []
        self._system_cpu_per_core_samples: list[tuple[float, ...]] = []

        # Prime psutil's internal counters so subsequent calls measure deltas.
        self._process.cpu_percent(interval=None)
        self._per_core_supported = True
        try:
            self._psutil.cpu_percent(interval=None, percpu=True)
        except TypeError:
            # pragma: no cover - only triggered if psutil does not support
            # per-core stats
            self._per_core_supported = False

    def maybe_sample(self, *, now: float | None = None) -> bool:
        """Record a sample if the configured interval has elapsed.

        Args:
            now (float | None): Optional timestamp override (for testing).

        Returns:
            bool: True if a sample was recorded, False otherwise.
        """
        timestamp = now if now is not None else self._monotonic()
        if timestamp - self._last_sample_time < self._interval:
            return False
        self._last_sample_time = timestamp
        self._record_sample()
        return True

    def finalize(self) -> None:
        """Force a final sample to capture end-of-run resource usage.

        Useful for ensuring the last state is recorded before shutdown.
        """
        self._last_sample_time = self._monotonic()
        self._record_sample()

    def snapshot(self) -> ResourceUsage | None:
        """Return aggregate statistics for collected samples.

        Returns:
            ResourceUsage | None: Aggregated resource usage, or None if no samples.
        """
        if not self._process_cpu_samples:
            return None

        process_cpu_avg = fmean(self._process_cpu_samples)
        process_rss_avg = fmean(self._rss_samples)
        if self._system_cpu_per_core_samples:
            per_core_avg = _mean_per_index(self._system_cpu_per_core_samples)
            system_cpu_avg: float | None = fmean(per_core_avg)
        else:
            per_core_avg = ()
            system_cpu_avg = None

        return ResourceUsage(
            process_cpu_percent_avg=process_cpu_avg,
            process_rss_avg_bytes=process_rss_avg,
            system_cpu_percent_avg=system_cpu_avg,
            system_cpu_percent_per_core_avg=per_core_avg,
        )

    def _record_sample(self) -> None:
        """Sample process and system resource usage and store results."""
        cpu_percent = float(self._process.cpu_percent(interval=None))
        rss_bytes = float(self._process.memory_info().rss)
        self._process_cpu_samples.append(cpu_percent)
        self._rss_samples.append(rss_bytes)

        if self._per_core_supported:
            per_core = tuple(
                float(value)
                for value in self._psutil.cpu_percent(interval=None, percpu=True)
            )
            if per_core:
                self._system_cpu_per_core_samples.append(per_core)


def _mean_per_index(samples: Sequence[Sequence[float]]) -> tuple[float, ...]:
    """Compute the mean for each index across a sequence of sequences.

    Args:
        samples (Sequence[Sequence[float]]): List of tuples/lists of floats.

    Returns:
        tuple[float, ...]: Mean for each index position.
    """
    counts = len(samples)
    if counts == 0:
        return ()
    length = len(samples[0])
    totals = [0.0] * length
    for sample in samples:
        for idx, value in enumerate(sample):
            totals[idx] += value
    return tuple(total / counts for total in totals)
