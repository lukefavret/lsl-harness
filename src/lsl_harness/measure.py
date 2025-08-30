import threading
import time

import numpy as np
from pylsl import StreamInlet, local_clock, resolve_byprop, resolve_stream

from .ring import Ring


class InletWorker:
    def __init__(self, selector=("type", "EEG"), chunk=32, timeout=0.1, ring_capacity=256):
        self.selector = selector
        self.chunk = chunk
        self.timeout = timeout
        self.ring = Ring(ring_capacity, drop_oldest=True)
        self.inlet = None
        self._stop = threading.Event()

    def start(self):
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
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        while not self._stop.is_set():
            data, ts = self.inlet.pull_chunk(max_samples=self.chunk, timeout=self.timeout)
            if ts:
                recv = local_clock()  # one receive timestamp per chunk (documented approx)
                self.ring.push(
                    (np.array(data, dtype=np.float32), np.array(ts, dtype=np.float64), recv)
                )

    def stop_now(self):
        self._stop.set()
