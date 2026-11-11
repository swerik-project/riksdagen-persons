#!/usr/bin/env python3
"""
Test that chair chamber assignments and MP roles agree.
"""
from datetime import date
import unittest

import polars as pl
from trainerlog import get_logger


LOGGER = get_logger("chair-role-integrity")

# Temporary baseline for the overlapping chair–mandate pairs flagged in PR #130.
# Lower it as the chamber discrepancies from issue #56 are reviewed and resolved.
MAX_CHAIR_MANDATE_MISMATCH_PAIRS = 32


class TestChairRoleIntegrity(unittest.TestCase):
    def build_mismatch_report(self):
        """List the conflicting chair–mandate pairs for source review."""
        def date_bound(column, year_suffix, fallback):
            # Preserve the existing bounds until the follow-up reviews them.
            value = pl.col(column)
            date_text = (
                pl.when(value.str.len_chars() == 4).then(value + year_suffix)
                .when(value.str.len_chars() == 7).then(value + "-01")
                .otherwise(value)
            )
            return (
                pl.when(value.is_null()).then(fallback)
                .otherwise(date_text.str.to_date("%Y-%m-%d", strict=False))
            )

        date_columns = {"start": pl.String, "end": pl.String}
        parliament_year = pl.col("parliament_year").cast(pl.String)
        first_year = parliament_year.str.slice(0, 4).cast(pl.Int32, strict=False)
        year_length = parliament_year.str.len_chars()
        chair_year_start = (
            pl.when(year_length == 4).then(pl.date(first_year, 1, 1))
            .when(year_length == 6).then(pl.date(first_year, 9, 1))
        )
        chair_year_end = (
            pl.when(year_length == 4).then(pl.date(first_year, 12, 31))
            .when(year_length == 6).then(pl.date(first_year + 1, 8, 31))
        )
        chairs = pl.read_csv("data/chairs.csv", columns=["chair_id", "chamber", "chair_nr"])
        chair_mp = (
            pl.read_csv("data/chair_mp.csv", schema_overrides=date_columns, row_index_name="chair_mp_row")
            .filter(pl.col("person_id").is_not_null())
            .rename({"start": "chair_raw_start", "end": "chair_raw_end"})
            .with_columns(
                date_bound("chair_raw_start", "-01-01", chair_year_start).alias("chair_start"),
                date_bound("chair_raw_end", "-12-31", chair_year_end).alias("chair_end"),
            )
            .join(chairs, on="chair_id", how="left")
        )
        mep = (
            pl.read_csv("data/member_of_parliament.csv", schema_overrides=date_columns, row_index_name="mep_row")
            .rename({"start": "meta_start", "end": "meta_end"})
            .with_columns(
                date_bound("meta_start", "-01-01", pl.lit(date(1800, 1, 1))).alias("mep_start"),
                date_bound("meta_end", "-12-31", pl.lit(date(2100, 12, 31))).alias("mep_end"),
                pl.col("role").replace_strict(
                    {"andrakammarledamot": "ak", "förstakammarledamot": "fk", "ledamot": "ek"},
                    default=None,
                    return_dtype=pl.String,
                ).alias("expected_chamber"),
            )
        )
        mismatches = chair_mp.join(mep, on="person_id", how="inner").filter(
            pl.col("chair_start") <= pl.col("mep_end"),
            pl.col("chair_end") >= pl.col("mep_start"),
            pl.col("chamber").ne_missing(pl.col("expected_chamber"))
            | pl.col("expected_chamber").is_null(),
        )

        report_cols = [
            "chair_mp_row",
            "parliament_year",
            "person_id",
            "chair_id",
            "chamber",
            "chair_nr",
            "chair_raw_start",
            "chair_raw_end",
            "chair_start",
            "chair_end",
            "mep_row",
            "meta_start",
            "meta_end",
            "mep_start",
            "mep_end",
            "role",
        ]
        return mismatches.select(report_cols).sort(
            ["person_id", "parliament_year", "chair_mp_row", "mep_row"]
        )

    def test_chair_chamber_matches_mp_role(self):
        """Guarantee: overlapping chair–mandate pairs with different chambers
        stay below the baseline.

        Why this matters: a chair assignment and the corresponding mandate should
        identify the same chamber, including when an MP transfers chambers.
        An MP can only sit in one chamber at a time.

        Data: reads ``data/chair_mp.csv``, ``data/chairs.csv``, and
        ``data/member_of_parliament.csv``. Counts each mismatching pair once.
        """
        LOGGER.info("Checking chamber agreement for overlapping chair–mandate pairs")
        mismatch_report = self.build_mismatch_report()
        mismatch_count = len(mismatch_report)
        for row in mismatch_report.iter_rows(named=True):
            LOGGER.warning(f"Chair–mandate chamber mismatch: {row}")
        LOGGER.info(
            "Found %s mismatching chair–mandate pairs (temporary ceiling: %s)",
            mismatch_count,
            MAX_CHAIR_MANDATE_MISMATCH_PAIRS,
        )
        self.assertLessEqual(
            mismatch_count,
            MAX_CHAIR_MANDATE_MISMATCH_PAIRS,
            f"{mismatch_count} mismatching chair–mandate pairs exceed the temporary "
            f"ceiling of {MAX_CHAIR_MANDATE_MISMATCH_PAIRS}; details were logged.",
        )


if __name__ == "__main__":
    unittest.main()
