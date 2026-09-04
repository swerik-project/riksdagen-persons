"""Data integrity checks for manually verified MP mandate dates."""
import unittest

import polars as pl
from trainerlog import get_logger


class MandateDateIntegrityTest(unittest.TestCase):
    def test_manually_checked_mandates(self):
        """Guarantee: manually verified MP mandate dates remain in the metadata.

        Data: compares ``test/data/mandate-dates.csv`` with
        ``data/member_of_parliament.csv``.
        """
        manually_checked_dates = pl.read_csv(
            "test/data/mandate-dates.csv",
            separator=";",
        )
        recorded_mandates = pl.read_csv(
            "data/member_of_parliament.csv",
            columns=["person_id", "start", "end"],
        )

        recorded_dates = pl.concat(
            [
                recorded_mandates.select(
                    "person_id",
                    pl.col("start").alias("date"),
                    pl.lit("START").alias("type"),
                ),
                recorded_mandates.select(
                    "person_id",
                    pl.col("end").alias("date"),
                    pl.lit("END").alias("type"),
                ),
            ],
        )

        missing_dates = (
            manually_checked_dates.join(
                recorded_dates,
                on=["person_id", "date", "type"],
                how="anti",
            )
            .sort(["person_id", "type", "date"])
        )
        missing_count = missing_dates.height

        if missing_count:
            logger = get_logger(name="mandate-date-integrity")
            logger.error(
                f"{missing_count} manually verified mandate date(s) "
                "are missing from data/member_of_parliament.csv"
            )
            for row in missing_dates.iter_rows(named=True):
                logger.error(
                    f"Missing {row['type']} mandate date {row['date']} "
                    f"for {row['person_id']}"
                )

        self.assertEqual(
            missing_count,
            0,
            f"{missing_count} manually verified MP mandate date(s) "
            "are missing from data/member_of_parliament.csv. Details were "
            "logged with trainerlog.",
        )


if __name__ == "__main__":
    unittest.main()
