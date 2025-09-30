"""A synthetic LSL outlet for testing purposes.

This script runs a standalone LSL outlet that generates a synthetic signal with
configurable parameters, including jitter, burst loss, and clock drift.
"""

import time

import numpy as np
from pylsl import StreamInfo, StreamOutlet, cf_float32, local_clock


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
        name, stream_type, num_channels, sample_rate, cf_float32, f"sim-{name}"
    )
    # Buffer up to 10 seconds of data
    outlet = StreamOutlet(info, max_buffered=int(sample_rate * 10))
    print(
        f"Created LSL outlet '{name}' with {num_channels} channels at "
        f"{sample_rate} Hz.",
        flush=True,
    )
    return outlet


def generate_sine_chunk(
    current_phase: float,
    chunk_size: int,
    num_channels: int,
    frequency: float,
    delta_time: float,
) -> tuple[np.ndarray, float]:
    """Generates a chunk of sine wave data with robust phase management.

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
    # Create an array of sample indices for the chunk.
    indices = np.arange(chunk_size, dtype=np.float32)

    # Calculate the phase for each sample in the chunk.
    phase_increment = 2 * np.pi * frequency * delta_time
    phases = current_phase + indices * phase_increment

    # Generate the sine wave values. (np.sin returns float)
    values = np.sin(phases)

    # Calculate the phase for the start of the next chunk.
    # This prevents the phase from growing indefinitely.
    next_phase = current_phase + chunk_size * phase_increment
    wrapped_next_phase = next_phase % (2 * np.pi)

    # Create the full chunk buffer by repeating the values across all channels.
    if num_channels > 1:
        chunk_buffer = np.tile(values[:, np.newaxis], (1, num_channels))
    else:
        chunk_buffer = values

    return chunk_buffer, wrapped_next_phase


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
        seed: Optional seed for the random number generator to ensure reproducibility.
    """
    outlet = create_lsl_outlet(name, stream_type, num_channels, sample_rate)
    rng = np.random.default_rng(seed)

    # --- Initialize state variables ---
    delta_time = 1.0 / sample_rate
    phase = 0.0
    signal_frequency = 10.0  # Hz
    # Convert drift from (milliseconds/minute) to (seconds/second).
    drift_per_second = (drift_ms_per_minute / 1000.0) / 60.0
    # Precompute constants used for timestamps
    sample_indices = np.arange(chunk_size, dtype=np.float64)
    dt_src = delta_time * (1.0 + drift_per_second)

    # High-resolution scheduler setup (monotonic)
    start_nsec = time.perf_counter_ns()
    next_send_nsec = start_nsec

    # Source clock start time in the LSL time domain (seconds)
    src_time_start = local_clock()
    current_src_time = src_time_start

    # Helper: precise sleep-until with coarse sleep + short spin
    def sleep_until(target_nsec: int) -> None:
        while True:
            now_nsec = time.perf_counter_ns()
            remaining_nsec = target_nsec - now_nsec
            if remaining_nsec <= 0:
                return
            # Coarse sleep when far; keep 1ms margin
            if remaining_nsec > 2_000_000:  # > 2 ms
                time.sleep((remaining_nsec - 1_000_000) / 1e9)
            else:
                # Busy-wait for the last ~2 ms.
                # High CPU, but required when on 'untuned' OSes.
                while time.perf_counter_ns() < target_nsec:
                    pass
                return

    print("Now streaming data...", flush=True)

    # --- Prime the pump: Generate and push the very first chunk immediately ---
    chunk, phase = generate_sine_chunk(
        current_phase=phase,
        chunk_size=chunk_size,
        num_channels=num_channels,
        frequency=signal_frequency,
        delta_time=delta_time,
    )
    if chunk.dtype != np.float32:
        chunk = chunk.astype(np.float32, copy=False)
    ts_chunk = current_src_time + sample_indices * dt_src
    # Do not drop the first chunk to ensure immediate startup
    outlet.push_chunk(chunk, timestamp=ts_chunk)

    # Prepare schedule for the next send
    chunk_duration = chunk_size * delta_time
    next_send_nsec += int(chunk_duration * 1e9)

    # --- Main loop: prepare next chunk before waiting, then push at the tick ---
    while True:
        # Advance source clock to the start of the next chunk and synthesize it
        current_src_time += chunk_size * dt_src
        chunk, phase = generate_sine_chunk(
            current_phase=phase,
            chunk_size=chunk_size,
            num_channels=num_channels,
            frequency=signal_frequency,
            delta_time=delta_time,
        )
        if chunk.dtype != np.float32:
            chunk = chunk.astype(np.float32, copy=False)
        ts_chunk = current_src_time + sample_indices * dt_src

        # Compute the precise sleep target (with non-accumulating jitter)
        next_send_nsec += int(chunk_duration * 1e9)
        if jitter_ms > 0:
            jitter_s = rng.uniform(-jitter_ms / 1000.0, jitter_ms / 1000.0)
            sleep_target = next_send_nsec + int(jitter_s * 1e9)
        else:
            sleep_target = next_send_nsec
        sleep_until(sleep_target)

        # At the precise tick, simulate burst loss and push
        drop_prob = burst_loss_percent * 0.01
        if rng.random() >= drop_prob:
            outlet.push_chunk(chunk, timestamp=ts_chunk)


def main():
    """The main entry point for running the outlet from the command line."""
    try:
        # Set a fixed seed for reproducibility in testing scenarios
        run_synthetic_outlet(seed=42)
    except KeyboardInterrupt:
        print("\nOutlet stopped by user.")


if __name__ == "__main__":
    main()
