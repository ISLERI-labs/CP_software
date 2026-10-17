from datetime import datetime, timezone
from io import BytesIO
import unittest

import pandas as pd

from cerephyte.data import (
    CHANNEL_COLUMNS,
    EXPORT_COLUMNS,
    TIMESTAMP_COLUMN,
    samples_to_csv,
    summarize_samples,
    validate_samples,
)
from cerephyte.simulation import generate_simulated_sample


class SampleDataTests(unittest.TestCase):
    def make_samples(self, count: int = 3) -> pd.DataFrame:
        rows = [
            generate_simulated_sample(
                index,
                datetime(2026, 10, 17, 12, 0, index, tzinfo=timezone.utc),
            )
            for index in range(count)
        ]
        return pd.DataFrame(rows, columns=EXPORT_COLUMNS)

    def test_simulation_has_stable_schema_and_repeatable_values(self) -> None:
        first = generate_simulated_sample(4)
        second = generate_simulated_sample(4)

        self.assertEqual(tuple(first), EXPORT_COLUMNS)
        self.assertEqual(
            [first[channel] for channel in CHANNEL_COLUMNS],
            [second[channel] for channel in CHANNEL_COLUMNS],
        )
        self.assertEqual(first["source_mode"], "SIMULATION")

    def test_csv_round_trip_keeps_schema_and_utc_timestamps(self) -> None:
        original = self.make_samples()
        imported = pd.read_csv(BytesIO(samples_to_csv(original)))
        normalized = validate_samples(imported)

        self.assertEqual(tuple(normalized.columns), EXPORT_COLUMNS)
        self.assertEqual(str(normalized[TIMESTAMP_COLUMN].dt.tz), "UTC")
        self.assertEqual(normalized["source_mode"].tolist(), ["SIMULATION"] * 3)

    def test_import_without_source_column_is_labeled_imported(self) -> None:
        samples = self.make_samples().drop(columns=["source_mode"])

        normalized = validate_samples(samples)

        self.assertEqual(normalized["source_mode"].unique().tolist(), ["IMPORTED DATA"])

    def test_import_rejects_missing_columns_and_invalid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "Missing required column"):
            validate_samples(pd.DataFrame({"timestamp_utc": ["2026-10-17T12:00:00Z"]}))

        samples = self.make_samples()
        samples.loc[0, "CH1"] = "not-a-number"
        with self.assertRaisesRegex(ValueError, "finite numeric values"):
            validate_samples(samples)

    def test_summary_reports_channel_statistics(self) -> None:
        summary = summarize_samples(self.make_samples())

        self.assertEqual(summary.index.tolist(), list(CHANNEL_COLUMNS))
        self.assertEqual(summary.loc["CH1", "count"], 3)


if __name__ == "__main__":
    unittest.main()
