"""Shared data schema and validation for dashboard data sources."""

from __future__ import annotations

import numpy as np
import pandas as pd

CHANNEL_COLUMNS = tuple(f"CH{channel}" for channel in range(1, 9))
TIMESTAMP_COLUMN = "timestamp_utc"
SOURCE_COLUMN = "source_mode"
EXPORT_COLUMNS = (TIMESTAMP_COLUMN, SOURCE_COLUMN, *CHANNEL_COLUMNS)
SOURCE_MODES = ("SIMULATION", "DEVICE", "IMPORTED DATA")


def validate_samples(samples: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize rows to the documented dashboard CSV schema."""
    if samples.empty:
        raise ValueError("The file contains no sample rows.")

    required_columns = (TIMESTAMP_COLUMN, *CHANNEL_COLUMNS)
    missing_columns = [column for column in required_columns if column not in samples.columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Missing required column(s): {missing}.")

    normalized = samples.copy()
    timestamps = pd.to_datetime(normalized[TIMESTAMP_COLUMN], utc=True, errors="coerce")
    if timestamps.isna().any():
        raise ValueError(f"Column '{TIMESTAMP_COLUMN}' must contain valid timestamps.")
    normalized[TIMESTAMP_COLUMN] = timestamps

    for channel in CHANNEL_COLUMNS:
        values = pd.to_numeric(normalized[channel], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"Column '{channel}' must contain finite numeric values.")
        normalized[channel] = values

    if SOURCE_COLUMN not in normalized.columns:
        normalized[SOURCE_COLUMN] = "IMPORTED DATA"
    else:
        normalized[SOURCE_COLUMN] = normalized[SOURCE_COLUMN].fillna("IMPORTED DATA")
        unknown_sources = set(normalized[SOURCE_COLUMN]) - set(SOURCE_MODES)
        if unknown_sources:
            raise ValueError(
                "Column 'source_mode' contains unsupported value(s): "
                + ", ".join(sorted(str(source) for source in unknown_sources))
                + "."
            )

    return normalized.loc[:, EXPORT_COLUMNS]


def samples_to_csv(samples: pd.DataFrame) -> bytes:
    """Serialize validated samples using the stable UTF-8 CSV schema."""
    normalized = validate_samples(samples)
    return normalized.to_csv(index=False).encode("utf-8")


def summarize_samples(samples: pd.DataFrame) -> pd.DataFrame:
    """Return descriptive statistics for each channel without assigning units."""
    normalized = validate_samples(samples)
    summary = normalized.loc[:, CHANNEL_COLUMNS].describe().loc[
        ["count", "mean", "std", "min", "max"]
    ]
    return summary.transpose().rename_axis("channel")
