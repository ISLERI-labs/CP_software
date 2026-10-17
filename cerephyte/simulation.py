"""Deterministic, clearly labeled example data for dashboard development."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from cerephyte.data import CHANNEL_COLUMNS, SOURCE_COLUMN, TIMESTAMP_COLUMN


def generate_simulated_sample(
    sample_index: int,
    timestamp: datetime | None = None,
) -> dict[str, object]:
    """Create one repeatable, unitless example row; it is not plant data."""
    if sample_index < 0:
        raise ValueError("sample_index must be zero or greater.")

    elapsed_seconds = float(sample_index)
    rng = np.random.default_rng(104729 + sample_index)
    sample: dict[str, object] = {
        TIMESTAMP_COLUMN: timestamp or datetime.now(timezone.utc),
        SOURCE_COLUMN: "SIMULATION",
    }

    for channel_index, channel in enumerate(CHANNEL_COLUMNS):
        frequency = 0.025 + channel_index * 0.003
        phase = channel_index * 0.47
        waveform = (
            0.65 * np.sin(2 * np.pi * frequency * elapsed_seconds + phase)
            + 0.12 * np.sin(2 * np.pi * frequency * 2.7 * elapsed_seconds + phase / 2)
        )
        sample[channel] = float(waveform + rng.normal(0, 0.025))

    return sample
