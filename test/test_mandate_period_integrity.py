"""Institutional mandate periods and their parliamentary-year assignments.

Checks coverage and year references against the current corpus tables.
CSVW tests enforce column formats, required fields, keys, and term references.
"""
import unittest

import polars as pl
from trainerlog import get_logger


LOGGER = get_logger("mandate-period-integrity")


class TestMandatePeriodIntegrity(unittest.TestCase):
    def test_each_unicameral_year_has_exactly_one_mandate_period(self):
        """Guarantee: each existing unicameral parliamentary year has one term.

        Data: compares distinct year/chamber pairs in ``riksdag-year.csv``
        with assignments joined to ``mandate_period.csv`` for the chamber.
        Seasonal rows share an assignment; failures count year/chamber pairs.
        """
        LOGGER.info("Checking unicameral year coverage by institutional terms")
        years = (
            pl.read_csv("data/riksdag-year.csv", schema_overrides={"parliament_year": pl.String})
            .filter(pl.col("chamber") == "ek")
            .select("parliament_year", "chamber")
            .unique()
        )
        terms = pl.read_csv("data/mandate_period.csv")
        assignments = pl.read_csv(
            "data/mandate_period_year.csv", schema_overrides={"parliament_year": pl.String}
        ).join(terms.select("mandate_period_id", "chamber"), on="mandate_period_id", how="left")
        counts = assignments.group_by("parliament_year", "chamber").len()
        errors = (
            years.join(counts, on=["parliament_year", "chamber"], how="left")
            .filter(pl.col("len").is_null() | (pl.col("len") != 1))
            .sort("parliament_year", "chamber")
        )
        for row in errors.iter_rows(named=True):
            LOGGER.error("Parliamentary year without exactly one institutional term: %s", row)
        LOGGER.info("Found %s year/chamber pairs without exactly one term", len(errors))
        self.assertEqual(
            len(errors), 0,
            f"{len(errors)} year/chamber pair(s) lack exactly one mandate period; details logged",
        )

    def test_mandate_period_assignments_reference_existing_years(self):
        """Guarantee: every term/year assignment refers to an existing chamber year.

        Data: joins the two mandate-period tables and checks membership in
        distinct year/chamber pairs from ``riksdag-year.csv``. Failures count
        assignment rows, including references to absent parliamentary years.
        """
        LOGGER.info("Checking institutional-term assignments against existing parliamentary years")
        years = pl.read_csv(
            "data/riksdag-year.csv", schema_overrides={"parliament_year": pl.String}
        ).select("parliament_year", "chamber").unique()
        terms = pl.read_csv("data/mandate_period.csv")
        assignments = pl.read_csv(
            "data/mandate_period_year.csv", schema_overrides={"parliament_year": pl.String}
        ).join(terms.select("mandate_period_id", "chamber"), on="mandate_period_id", how="left")
        errors = assignments.join(years, on=["parliament_year", "chamber"], how="anti").sort(
            "mandate_period_id", "parliament_year"
        )
        for row in errors.iter_rows(named=True):
            LOGGER.error("Institutional-term assignment references an absent chamber year: %s", row)
        LOGGER.info("Found %s assignments to absent chamber years", len(errors))
        self.assertEqual(
            len(errors), 0,
            f"{len(errors)} assignment row(s) reference absent chamber years; details logged",
        )

if __name__ == "__main__":
    unittest.main()
