"""Manages LSL stream data acquisition in a background thread.

This module provides the InletWorker class for acquiring LSL stream data in a background thread and storing it in a ring buffer.
"""

import threading
import warnings

import numpy as np
from pylsl import StreamInlet, local_clock, resolve_byprop, resolve_stream

from .ring import Ring


class InletWorker:
    """Manages an LSL inlet and pulls data into a ring buffer in a background thread.

    This worker resolves an LSL stream based on a selector, creates an inlet,
    and continuously pulls data chunks into a thread-safe ring buffer.

    Attributes:
        selector (tuple): A tuple (prop, value) used to resolve the LSL stream.
        chunk (int): The max number of samples to pull in each chunk.
        timeout (float): The timeout in seconds for pull_chunk.
        ring (Ring): The Ring buffer where data is stored.
        inlet (StreamInlet): The pylsl.StreamInlet instance.
        thread (threading.Thread): The background thread for data acquisition.
        _stop (threading.Event): Event to signal the worker thread to stop.
        JOIN_TIMEOUT (float): Timeout in seconds for thread join.
    """

    def __init__(self, selector=("type", "EEG"), chunk=32, timeout=0.1, ring_capacity=256):
        """Initialize the InletWorker.

        Args:
            selector (tuple): A tuple (prop, value) for resolving the LSL stream.
            chunk (int): The max number of samples per pull_chunk call.
            timeout (float): The timeout in seconds for the pull_chunk call.
            ring_capacity (int): The capacity of the ring buffer.
        """
        self.selector = selector
        self.chunk = chunk
        self.timeout = timeout
        self.ring = Ring(ring_capacity, drop_oldest=True)
        self.inlet = None
        self._thread = None
        self._stop = threading.Event()
        self._JOIN_TIMEOUT = 5.0  # seconds

    def start(self):
        """Resolve the LSL stream and start the data acquisition thread.

        This method attempts to find an LSL stream matching the selector. If found,
        it creates an Inlet and starts a background thread to pull data.

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
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

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
        """Signal the background thread to stop, wait for it to exit, and close the inlet.

        This method sets the stop event, waits for the thread to exit, closes the LSL inlet,
        and may issue warnings if the thread does not stop gracefully or if closing the inlet fails.
        """
        if self._stop.is_set():
            return
        self._stop.set()

        # Handle the inlet first to avoid blocking issues.
        if self.inlet:
            try:
                self.inlet.close()
            except Exception as e:
                warnings.warn(f"Exception occurred while closing inlet: {e}", stacklevel=2)
            finally:
                # Ensure the reference is always cleared.
                self.inlet = None

        # Handle the thread second.
        if self._thread:
            self._thread.join(self._JOIN_TIMEOUT)
            if self._thread.is_alive():
                warnings.warn(
                    f"InletWorker thread did not stop gracefully within the timeout ({self._JOIN_TIMEOUT} seconds). "
                    "Python does not support forceful termination of threads; "
                    "resources may not be fully cleaned up. Restart the process if necessary.",
                    stacklevel=2,
                )
            # Clear thread reference after it has been handled.
            self._thread = None
