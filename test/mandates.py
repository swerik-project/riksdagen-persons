"""Data integrity checks for manually verified MP mandate dates."""
import unittest

import polars as pl
from trainerlog import get_logger


LOGGER = get_logger(name="mandate-date-integrity")


class MandateDateIntegrityTest(unittest.TestCase):

    def test_manually_checked_mandates(self):
        """Guarantee: manually verified MP mandate dates in the metadata.

        Why this matters: manually checked start and end dates are curated
        reference points. If they drift, corpus users can get incorrect mandate
        intervals even when the metadata file remains structurally valid.

        Data: compares ``test/data/mandate-dates.csv`` with
        ``data/member_of_parliament.csv``.
        """
        expected_dates = pl.read_csv("test/data/mandate-dates.csv", separator=";")
        member_dates = pl.read_csv("data/member_of_parliament.csv")

        observed_dates = pl.concat(
            [
                member_dates.select(
                    "person_id",
                    pl.col("start").alias("date"),
                ).with_columns(pl.lit("START").alias("type")),
                member_dates.select(
                    "person_id",
                    pl.col("end").alias("date"),
                ).with_columns(pl.lit("END").alias("type")),
            ],
        )

        missing_dates = (
            expected_dates.join(
                observed_dates,
                on=["person_id", "date", "type"],
                how="anti",
            )
            .sort(["person_id", "type", "date"])
        )

        LOGGER.info(
            f"Checked {expected_dates.height} manually verified mandate date(s) "
            f"against {member_dates.height} member_of_parliament row(s)"
        )

        if missing_dates.height:
            LOGGER.error(
                f"{missing_dates.height} manually verified mandate date(s) "
                "are missing from data/member_of_parliament.csv"
            )
            for row in missing_dates.iter_rows(named=True):
                LOGGER.error(
                    f"Missing {row['type']} mandate date {row['date']} "
                    f"for {row['person_id']}"
                )

        self.assertEqual(
            missing_dates.height,
            0,
            f"{missing_dates.height} manually verified MP mandate date(s) "
            "are missing from data/member_of_parliament.csv. Details were "
            "logged with trainerlog.",
        )


if __name__ == "__main__":
    unittest.main()
