#!/usr/bin/env python3
"""
Data integrity tests for Riksdag-year date ranges.

These tests check release-blocking guarantees for ``data/riksdag-year.csv``,
the shared reference table used to map dates to Riksdag years.
"""
import unittest

import polars as pl
from trainerlog import get_logger


LOGGER = get_logger("riksdag-year-date-integrity")
RIKSDAG_YEAR_PATH = "data/riksdag-year.csv"


class TestRiksdagYearDateIntegrity(unittest.TestCase):
    def test_riksdag_year_ranges_are_not_inverted(self):
        """Guarantee: every Riksdag-year range starts on or before it ends.

        Why this matters: inverted Riksdag-year ranges break date-to-riksmote
        mapping and make valid protocol dates look outside their expected
        Riksdag-year interval.

        Data: reads ``data/riksdag-year.csv``.
        """
        riksdag_years = pl.read_csv(RIKSDAG_YEAR_PATH, try_parse_dates=True)
        inverted = riksdag_years.filter(pl.col("start") > pl.col("end"))

        for row in inverted.to_dicts():
            LOGGER.error(
                "Inverted Riksdag-year range: parliament_year=%s specifier=%s "
                "chamber=%s start=%s end=%s",
                row["parliament_year"],
                row["specifier"],
                row["chamber"],
                row["start"],
                row["end"],
            )

        self.assertEqual(
            len(inverted),
            0,
            f"{len(inverted)} Riksdag-year range row(s) start after end; "
            f"details logged from {RIKSDAG_YEAR_PATH}",
        )

    def test_riksdag_year_ranges_do_not_overlap_within_chamber(self):
        """Guarantee: two Riksdag-year ranges for one chamber never overlap.

        Why this matters: overlapping ranges make date-to-riksmote mapping
        ambiguous because a single protocol date can match multiple
        Riksdag-year intervals. Ranges that only meet at a boundary are allowed.

        Data: reads ``data/riksdag-year.csv``.
        """
        riksdag_years = pl.read_csv(RIKSDAG_YEAR_PATH, try_parse_dates=True)
        ordered = riksdag_years.sort(
            ["chamber", "start", "end", "parliament_year", "specifier"]
        )

        with_previous = ordered.with_columns(
            pl.col("parliament_year")
            .shift(1)
            .over("chamber")
            .alias("previous_parliament_year"),
            pl.col("specifier").shift(1).over("chamber").alias("previous_specifier"),
            pl.col("start").shift(1).over("chamber").alias("previous_start"),
            pl.col("end").shift(1).over("chamber").alias("previous_end"),
        )
        overlaps = with_previous.filter(pl.col("start") < pl.col("previous_end"))

        for row in overlaps.to_dicts():
            LOGGER.error(
                "Overlapping Riksdag-year range: chamber=%s previous=%s/%s "
                "%s..%s current=%s/%s %s..%s",
                row["chamber"],
                row["previous_parliament_year"],
                row["previous_specifier"],
                row["previous_start"],
                row["previous_end"],
                row["parliament_year"],
                row["specifier"],
                row["start"],
                row["end"],
            )

        self.assertEqual(
            len(overlaps),
            0,
            f"{len(overlaps)} Riksdag-year range row(s) overlap within chamber; "
            f"details logged from {RIKSDAG_YEAR_PATH}",
        )


if __name__ == "__main__":
    unittest.main()
