"""A synthetic LSL outlet for testing purposes.

This script runs a standalone LSL outlet that generates a synthetic signal with
configurable parameters, including jitter, burst loss, and clock drift.
"""
import math
import time

import numpy as np
from pylsl import StreamInfo, StreamOutlet


def create_lsl_outlet(
    name: str, stream_type: str, num_channels: int, sample_rate: float
) -> StreamOutlet:
    """Initializes and returns a pylsl StreamOutlet.

    Args:
        name: The name of the LSL stream.
        stream_type: The type of the LSL stream.
        num_channels: The number of channels in the stream.
        sample_rate: The nominal sample rate in Hz.

    Returns:
        A configured StreamOutlet instance.
    """
    info = StreamInfo(
        name, stream_type, num_channels, sample_rate, "float32", f"sim-{name}"
    )
    # Buffer up to 10 seconds of data
    outlet = StreamOutlet(info, max_buffered=int(sample_rate * 10))
    print(f"Created LSL outlet '{name}' with {num_channels} channels at {sample_rate} Hz.")
    return outlet


def generate_sine_chunk(
    current_phase: float,
    chunk_size: int,
    num_channels: int,
    frequency: float,
    delta_time: float,
) -> tuple[np.ndarray, float]:
    """Generates a chunk of sine wave data.

    Args:
        current_phase: The starting phase for the sine wave.
        chunk_size: The number of samples in the chunk.
        num_channels: The number of channels.
        frequency: The frequency of the sine wave in Hz.
        delta_time: The time step between samples (1 / sample_rate).

    Returns:
        A tuple containing the generated data chunk (numpy array) and the
        updated phase for the next chunk.
    """
    chunk_buffer = np.zeros((chunk_size, num_channels), dtype=np.float32)
    phase = current_phase
    for i in range(chunk_size):
        phase += 2 * math.pi * frequency * delta_time
        value = math.sin(phase)
        chunk_buffer[i, :] = value
    return chunk_buffer, phase


def run_synthetic_outlet(
    name: str = "EEG_Sim",
    stream_type: str = "EEG",
    num_channels: int = 8,
    sample_rate: float = 1000.0,
    chunk_size: int = 32,
    jitter_ms: float = 0.0,
    burst_loss_percent: float = 0.0,
    drift_ms_per_minute: float = 0.0,
    seed: int | None = None,
):
    """Runs the main loop for the synthetic LSL outlet.

    This function orchestrates the creation of an LSL outlet, the generation
    of data, and the simulation of signal impairments.

    Args:
        name: The name of the LSL stream.
        stream_type: The type of the LSL stream.
        num_channels: The number of channels in the stream.
        sample_rate: The nominal sample rate in Hz.
        chunk_size: The number of samples per chunk.
        jitter_ms: Random jitter added to sleep time between chunks (ms).
        burst_loss_percent: Percentage (0-100) of chunks to drop.
        drift_ms_per_minute: Simulated clock drift (ms/minute).
    """
    outlet = create_lsl_outlet(name, stream_type, num_channels, sample_rate)
    rng = np.random.default_rng(seed)

    # --- Initialize state variables ---
    delta_time = 1.0 / sample_rate
    phase = 0.0
    signal_frequency = 10.0  # Hz
     # Convert drift from (milliseconds/minute) to (seconds/second).
    drift_per_second = (drift_ms_per_minute / 1000.0) / 60.0
    extra_sleep_accumulator = 0.0

    print("Now streaming data...")
    while True:
        # 1. Generate a chunk of data
        chunk, phase = generate_sine_chunk(
            current_phase=phase,
            chunk_size=chunk_size,
            num_channels=num_channels,
            frequency=signal_frequency,
            delta_time=delta_time,
        )

        # 2. Simulate burst loss and push the chunk
        if np.random.rand() >= burst_loss_percent / 100:
            # outlet.push_chunk requires a list of lists, not a numpy array.
            outlet.push_chunk(chunk.tolist())

        # 3. Calculate sleep duration with impairments
        chunk_duration = chunk_size * delta_time
        sleep_time = chunk_duration

        # Add jitter
        if jitter_ms > 0:
            sleep_time += rng.uniform(-jitter_ms / 1000.0, jitter_ms / 1000.0)
        time.sleep(sleep_time)

        # Add clock drift
        if drift_ms_per_minute != 0:
            extra_sleep_accumulator += drift_per_second * chunk_duration
            # To avoid performance issues with very small sleep durations,
            # only sleep when the accumulated drift is at least 1ms.
            if extra_sleep_accumulator >= 0.001:  # Sleep for accumulated drift
                time.sleep(extra_sleep_accumulator)
                extra_sleep_accumulator = 0.0

def main():
    """The main entry point for running the outlet from the command line."""
    try:
        # Set a fixed seed for reproducibility in testing scenarios
        run_synthetic_outlet(seed=42)
    except KeyboardInterrupt:
        print("\nOutlet stopped by user.")

if __name__ == "__main__":
    main()