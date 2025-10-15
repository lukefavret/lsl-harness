"""Regression tests for :mod:`lsl_harness.measure`.

The real `pylsl` package requires native libraries that are not available in the
unit-test environment.  A lightweight shim is therefore installed into
``sys.modules`` so the :mod:`lsl_harness.measure` module can be imported without
error.  The shim is intentionally minimal—only the attributes used by the
tests are implemented.
"""

import importlib
import sys
import types
import warnings
from collections.abc import Callable

import numpy as np
import pytest

_fake_pylsl = types.ModuleType("pylsl")
_fake_pylsl.StreamInlet = object
_fake_pylsl.local_clock = lambda: 0.0
_fake_pylsl.resolve_byprop = lambda *args, **kwargs: []
_fake_pylsl.resolve_stream = lambda *args, **kwargs: []
sys.modules.setdefault("pylsl", _fake_pylsl)

# Import the production module only after the stub is installed so importing
# ``pylsl`` within :mod:`lsl_harness.measure` succeeds in the test environment.
measure = importlib.import_module("lsl_harness.measure")
InletWorker = measure.InletWorker


class DummyThread:
    """Minimal thread stand-in that records daemon usage."""

    def __init__(self, target: Callable | None = None, daemon: bool | None = None):
        """Initialise the dummy thread.

        Args:
            target (Callable | None): Callable that would normally run on the
                thread. Stored for completeness so tests can assert it was set.
            daemon (bool | None): Whether the thread should be a daemon.  Tests
                verify this flag is propagated from :class:`InletWorker`.
        """
        self.target = target
        self.daemon = daemon
        self.started = False
        self.join_timeout = None

    def start(self):
        """Record that the thread would have been started."""
        self.started = True

    def join(self, timeout):
        """Capture the timeout passed to ``Thread.join`` for assertions."""
        self.join_timeout = timeout

    def is_alive(self):
        """Pretend the thread has already stopped."""
        return False


def test_start_raises_when_no_stream(monkeypatch):
    """Ensure ``start`` raises when stream resolution finds nothing.

    Args:
        monkeypatch (pytest.MonkeyPatch): Test fixture that temporarily replaces
            :mod:`lsl_harness.measure` attributes.  It ensures the production
            module is untouched outside the scope of this test.
    """
    # Explicitly patch the resolver to return an empty list so the failure path
    # is exercised deterministically.
    monkeypatch.setattr(measure, "resolve_byprop", lambda *args, **kwargs: [])

    worker = InletWorker(selector=("type", "EEG"))

    with pytest.raises(RuntimeError, match="No LSL stream matching type==EEG"):
        worker.start()

    assert worker.inlet is None
    assert worker._thread is None


def test_start_uses_resolve_stream_on_typeerror(monkeypatch):
    """Fallback to ``resolve_stream`` when ``resolve_byprop`` is too old.

    Args:
        monkeypatch (pytest.MonkeyPatch): Fixture that swaps resolver functions
            so we can emulate an older pylsl release that lacks the ``timeout``
            keyword argument.  The dummy thread asserts the daemon flag is
            propagated as expected.
    """

    def fake_resolve_byprop(*args, **kwargs):
        raise TypeError("timeout kwarg not supported")

    def fake_resolve_stream(key, value):
        assert key == "name"
        assert value == "Test"
        return ["stream"]

    created = {}

    class DummyInlet:
        """Capture constructor arguments for assertion."""

        def __init__(self, stream, **kwargs):
            created["stream"] = stream
            created["kwargs"] = kwargs

    monkeypatch.setattr(measure, "resolve_byprop", fake_resolve_byprop)
    monkeypatch.setattr(measure, "resolve_stream", fake_resolve_stream)
    monkeypatch.setattr(measure, "StreamInlet", DummyInlet)
    monkeypatch.setattr(measure.threading, "Thread", DummyThread)

    worker = InletWorker(selector=("name", "Test"))
    worker.start()

    assert created["stream"] == "stream"
    assert created["kwargs"] == {"max_buflen": 5, "max_chunklen": 0, "recover": True}
    assert isinstance(worker._thread, DummyThread)
    assert worker._thread.started is True
    # Background threads should be daemons so they do not block interpreter
    # shutdown in the real application.
    assert worker._thread.daemon is True


def test_start_creates_inlet_when_stream_found(monkeypatch):
    """Create a ``StreamInlet`` and daemon thread when a stream is available.

    Args:
        monkeypatch (pytest.MonkeyPatch): Fixture that injects deterministic
            stub implementations of the pylsl functions used during start-up.
    """

    def fake_resolve_byprop(key, value, timeout):
        assert timeout == 5
        return ["stream"]

    class DummyInlet:
        """Store the stream handle and inlet configuration."""

        def __init__(self, stream, **kwargs):
            self.stream = stream
            self.kwargs = kwargs

    monkeypatch.setattr(measure, "resolve_byprop", fake_resolve_byprop)
    monkeypatch.setattr(measure, "StreamInlet", DummyInlet)
    monkeypatch.setattr(measure.threading, "Thread", DummyThread)

    worker = InletWorker()
    worker.start()

    assert isinstance(worker.inlet, DummyInlet)
    assert worker.inlet.stream == "stream"
    assert worker.inlet.kwargs == {"max_buflen": 5, "max_chunklen": 0, "recover": True}
    assert worker._thread.started is True
    assert worker._thread.daemon is True


def test_run_pushes_numpy_arrays(monkeypatch):
    """Convert pulled chunks into numpy arrays before pushing to the ring.

    Args:
        monkeypatch (pytest.MonkeyPatch): Fixture that replaces ``local_clock``
            so we can assert the receive timestamp value deterministically.
    """
    worker = InletWorker()
    worker._stop.clear()

    pushed = []

    class DummyRing:
        """Collect values pushed by the worker for later assertions."""

        def push(self, value):
            pushed.append(value)
            worker._stop.set()

    class DummyInlet:
        """Return deterministic chunk data and timestamps for the worker."""

        def pull_chunk(self, max_samples, timeout):
            assert max_samples == worker.chunk
            assert timeout == worker.timeout
            return ([[1.0, 2.0], [3.0, 4.0]], [0.1, 0.2])

    worker.ring = DummyRing()
    worker.inlet = DummyInlet()

    monkeypatch.setattr(measure, "local_clock", lambda: 42.0)

    worker._run()

    assert len(pushed) == 1
    data, timestamps, recv = pushed[0]
    assert isinstance(data, np.ndarray)
    assert data.dtype == np.float32
    assert data.tolist() == [[1.0, 2.0], [3.0, 4.0]]
    assert isinstance(timestamps, np.ndarray)
    assert timestamps.dtype == np.float64
    assert timestamps.tolist() == [0.1, 0.2]
    assert recv == 42.0


def test_stop_handles_inlet_and_thread():
    """Warn when clean-up encounters recoverable errors."""
    worker = InletWorker()

    class DummyInlet:
        """Raise on ``close`` to exercise the warning path."""

        def close(self):
            raise RuntimeError("boom")

    class AliveThread(DummyThread):
        """Simulate a thread that remains alive after ``join`` completes."""

        def __init__(self):
            super().__init__()
            self.alive = True

        def is_alive(self):
            """Report that the thread would still be running."""
            return self.alive

    worker.inlet = DummyInlet()
    worker._thread = AliveThread()
    thread = worker._thread

    with pytest.warns(UserWarning) as record:
        worker.stop()

    messages = [str(w.message) for w in record]
    assert any("Exception occurred while closing inlet" in msg for msg in messages)
    assert any("did not stop gracefully" in msg for msg in messages)

    assert worker.inlet is None
    assert worker._thread is None
    assert worker._stop.is_set()
    assert thread.join_timeout == worker._JOIN_TIMEOUT

    with warnings.catch_warnings(record=True) as post_record:
        warnings.simplefilter("always")
        worker.stop()

    assert post_record == []
