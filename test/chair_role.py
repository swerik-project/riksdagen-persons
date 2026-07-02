#!/usr/bin/env python3
"""
Test that chair chamber assignments and MP roles agree.
"""
import pandas as pd
import unittest


class Test(unittest.TestCase):
    def get_chairs(self):
        return pd.read_csv("data/chairs.csv")

    def get_chair_mp(self):
        return pd.read_csv("data/chair_mp.csv")

    def get_mep(self):
        return pd.read_csv("data/member_of_parliament.csv").rename(
            columns={"start": "meta_start", "end": "meta_end"}
        )

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
        chamber_role = {
            "ak": "andrakammarledamot",
            "fk": "förstakammarledamot",
            "ek": "ledamot",
        }

        chair_mp = self.get_chair_mp().reset_index(names="chair_mp_row")
        chairs = self.get_chairs()
        mep = self.get_mep().reset_index(names="mep_row")

        chair_mp = chair_mp[pd.notnull(chair_mp["person_id"])].copy()
        chair_mp = chair_mp.merge(
            chairs[["chair_id", "chamber", "chair_nr"]],
            on="chair_id",
            how="left",
        )
        chair_mp["chair_start"] = chair_mp.apply(
            lambda row: self.parse_start_date(
                row["start"],
                self.parliament_year_start(row["parliament_year"]),
            ),
            axis=1,
        )
        chair_mp["chair_end"] = chair_mp.apply(
            lambda row: self.parse_end_date(
                row["end"],
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
            "start",
            "end",
            "mep_row",
            "meta_start",
            "meta_end",
            "role",
        ]
        return mismatches[report_cols].sort_values(
            ["person_id", "parliament_year", "chair_mp_row"]
        )

    def test_chair_chamber_matches_mp_role(self):
        """
        A person's MP role should match the chamber of their chair assignment
        for overlapping date intervals.
        """
        mismatch_report = self.build_mismatch_report()
        error_message = (
            f"{len(mismatch_report)} chair-to-role chamber mismatch(es) found.\n"
            f"{mismatch_report.to_string(index=False)}"
        )
        self.assertEqual(len(mismatch_report), 0, error_message)


if __name__ == "__main__":
    unittest.main()
