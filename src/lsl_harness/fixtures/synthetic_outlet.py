import math
import time

import numpy as np
from pylsl import StreamInfo, StreamOutlet


def run_synthetic(
    name="EEG_Sim",
    stype="EEG",
    n_ch=8,
    srate=1000.0,
    chunk=32,
    jitter_ms=0.0,
    burst_loss_pct=0.0,
    drift_ms_per_min=0.0,
):
    info = StreamInfo(name, stype, n_ch, srate, "float32", "sim-001")
    outlet = StreamOutlet(info, max_buffered=int(srate * 10))
    dt = 1.0 / srate
    phase = 0.0
    f = 10.0
    chunk_buf = np.zeros((chunk, n_ch), dtype=np.float32)

    drift_per_sec = (drift_ms_per_min / 1000.0) / 60.0
    extra_sleep_accum = 0.0

    while True:
        for i in range(chunk):
            phase += 2 * math.pi * f * dt
            val = math.sin(phase)
            chunk_buf[i, :] = val

        if burst_loss_pct and np.random.rand() < burst_loss_pct:
            pass
        else:
            outlet.push_chunk(chunk_buf.tolist())

        base_sleep = chunk * dt
        if jitter_ms:
            base_sleep += np.random.uniform(0, jitter_ms / 1000.0)
        time.sleep(base_sleep)

        if drift_ms_per_min:
            extra_sleep_accum += drift_per_sec * (chunk * dt)
            if extra_sleep_accum >= 0.001:
                time.sleep(extra_sleep_accum)
                extra_sleep_accum = 0.0


if __name__ == "__main__":
    run_synthetic()
