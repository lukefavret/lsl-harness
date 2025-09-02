"""Manages LSL stream data acquisition in a background thread."""
import threading

import numpy as np
from pylsl import StreamInlet, local_clock, resolve_byprop, resolve_stream

from .ring import Ring


class InletWorker:
    """Manages an LSL inlet and pulls data into a ring buffer in a background thread.

    This worker resolves an LSL stream based on a selector, creates an inlet,
    and continuously pulls data chunks into a thread-safe ring buffer.

    Attributes:
      selector: A tuple ``(prop, value)`` used to resolve the LSL stream.
      chunk: The max number of samples to pull in each chunk.
      timeout: The timeout in **seconds** for ``pull_chunk``.
      ring: The ``Ring`` buffer where data is stored.
      inlet: The ``pylsl.StreamInlet`` instance.
      _stop: A ``threading.Event`` to signal the worker thread to stop.

    """

    def __init__(self, selector=("type", "EEG"), chunk=32, timeout=0.1, ring_capacity=256):
        """Initialize the InletWorker.

        Args:
          selector: A tuple ``(prop, value)`` for resolving the LSL stream.
          chunk: The max number of samples per ``pull_chunk`` call.
          timeout: The timeout in **seconds** for the ``pull_chunk`` call.
          ring_capacity: The capacity of the ring buffer.

        """
        self.selector = selector
        self.chunk = chunk
        self.timeout = timeout
        self.ring = Ring(ring_capacity, drop_oldest=True)
        self.inlet = None
        self.thread = None
        self._stop = threading.Event()

    def start(self):
        """Resolve the LSL stream and start the data acquisition thread.

        This method attempts to find an LSL stream matching the selector. If
        found, it creates an ``Inlet`` and starts a background thread to pull
        data.

        Raises:
          RuntimeError: If no LSL stream matching the selector is found.

        """
        key, val = self.selector
        try:
            # Preferred: supports timeout in pylsl 1.16.x
            streams = resolve_byprop(key, val, timeout=5)
        except TypeError:
            # Fallback for older bindings: no timeout kwarg supported
            streams = resolve_stream(key, val)
        if not streams:
            raise RuntimeError(f"No LSL stream matching {key}=={val}")
        self.inlet = StreamInlet(streams[0], max_buflen=5, max_chunklen=0, recover=True)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        """Run the main loop for the background data acquisition thread.

        Continuously pulls data chunks from the LSL inlet and pushes them into
        the ring buffer until the ``_stop`` event is set.
        """
        while not self._stop.is_set():
            data, ts = self.inlet.pull_chunk(max_samples=self.chunk, timeout=self.timeout)
            if ts:
                recv = local_clock()  # one receive timestamp per chunk (documented approx)
                self.ring.push(
                    (np.array(data, dtype=np.float32), np.array(ts, dtype=np.float64), recv)
                )

    def stop(self):
        """Signal the background thread to stop and wait for it to exit."""
        self._stop.set()
        if self.thread:
            self.thread.join(timeout=5.0)  # Wait for the thread to finish, with timeout
        if self.inlet:
            self.inlet.close() # Good place for cleanup
