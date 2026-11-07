#!/usr/bin/env python3
"""
Test that chair chamber assignments and MP roles agree.
"""
import pandas as pd
import unittest

from trainerlog import get_logger


LOGGER = get_logger("chair-role-integrity")

# Temporary baseline for the overlapping chair–mandate pairs flagged in PR #130.
# Lower it as the chamber discrepancies from issue #56 are reviewed and resolved.
MAX_CHAIR_MANDATE_MISMATCH_PAIRS = 32


class TestChairRoleIntegrity(unittest.TestCase):
    def parliament_year_start(self, parliament_year):
        parliament_year = str(parliament_year)
        if len(parliament_year) == 4:
            return pd.Timestamp(f"{parliament_year}-01-01")
        if len(parliament_year) == 6:
            return pd.Timestamp(f"{parliament_year[:4]}-09-01")
        return pd.NaT

    def parliament_year_end(self, parliament_year):
        parliament_year = str(parliament_year)
        if len(parliament_year) == 4:
            return pd.Timestamp(f"{parliament_year}-12-31")
        if len(parliament_year) == 6:
            return pd.Timestamp(f"{int(parliament_year[:4]) + 1}-08-31")
        return pd.NaT

    def parse_start_date(self, value, default):
        if pd.isna(value):
            return default
        value = str(value)
        if value == "" or value.lower() == "nan":
            return default
        if len(value) == 4 and value.isdigit():
            return pd.Timestamp(f"{value}-01-01")
        return pd.to_datetime(value, errors="coerce")

    def parse_end_date(self, value, default):
        if pd.isna(value):
            return default
        value = str(value)
        if value == "" or value.lower() == "nan":
            return default
        if len(value) == 4 and value.isdigit():
            return pd.Timestamp(f"{value}-12-31")
        return pd.to_datetime(value, errors="coerce")

    def build_mismatch_report(self):
        """List the conflicting chair–mandate pairs for source review."""
        chamber_role = {
            "ak": "andrakammarledamot",
            "fk": "förstakammarledamot",
            "ek": "ledamot",
        }

        chair_mp = pd.read_csv("data/chair_mp.csv").reset_index(names="chair_mp_row")
        chairs = pd.read_csv("data/chairs.csv", usecols=["chair_id", "chamber", "chair_nr"])
        mep = pd.read_csv("data/member_of_parliament.csv").rename(
            columns={"start": "meta_start", "end": "meta_end"}
        ).reset_index(names="mep_row")

        chair_mp = chair_mp[pd.notnull(chair_mp["person_id"])].copy()
        chair_mp = chair_mp.rename(
            columns={"start": "chair_raw_start", "end": "chair_raw_end"}
        )
        chair_mp = chair_mp.merge(
            chairs[["chair_id", "chamber", "chair_nr"]],
            on="chair_id",
            how="left",
        )
        chair_mp["chair_start"] = chair_mp.apply(
            lambda row: self.parse_start_date(
                row["chair_raw_start"],
                self.parliament_year_start(row["parliament_year"]),
            ),
            axis=1,
        )
        chair_mp["chair_end"] = chair_mp.apply(
            lambda row: self.parse_end_date(
                row["chair_raw_end"],
                self.parliament_year_end(row["parliament_year"]),
            ),
            axis=1,
        )

        mep["mep_start"] = mep["meta_start"].apply(
            lambda value: self.parse_start_date(value, pd.Timestamp("1800-01-01"))
        )
        mep["mep_end"] = mep["meta_end"].apply(
            lambda value: self.parse_end_date(value, pd.Timestamp("2100-12-31"))
        )
        mep["expected_chamber"] = mep["role"].map(
            {role: chamber for chamber, role in chamber_role.items()}
        )

        joined = chair_mp.merge(
            mep,
            on="person_id",
            how="left",
            suffixes=("_chair", "_mep"),
        )
        joined = joined[
            (joined["chair_start"] <= joined["mep_end"])
            & (joined["chair_end"] >= joined["mep_start"])
        ].copy()
        mismatches = joined[joined["chamber"] != joined["expected_chamber"]].copy()

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
        return mismatches[report_cols].sort_values(
            ["person_id", "parliament_year", "chair_mp_row"]
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
        for row in mismatch_report.itertuples(index=False):
            LOGGER.warning(
                "Chair–mandate chamber mismatch: person_id=%s parliament_year=%s "
                "chair_mp_row=%s chair_id=%s chamber=%s chair_bounds=%s..%s "
                "mep_row=%s role=%s mandate_bounds=%s..%s",
                row.person_id,
                row.parliament_year,
                row.chair_mp_row,
                row.chair_id,
                row.chamber,
                row.chair_start.date(),
                row.chair_end.date(),
                row.mep_row,
                row.role,
                row.mep_start.date(),
                row.mep_end.date(),
            )
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
