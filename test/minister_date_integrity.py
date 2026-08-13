#!/usr/bin/env python3
"""
Test minister date coverage and interval integrity.

This data-integrity test checks that dated rows in `data/minister.csv` use
parseable date values, do not have inverted intervals, do not partially overlap
for the same person and role, and intersect the date interval of the referenced
government in `data/government.csv`. 
"""
from pathlib import Path
import re
import unittest

import pandas as pd
from trainerlog import get_logger


LOGGER = get_logger("minister-date-integrity")
DATA_DIR = Path("data")
RESULT_DIR = Path("test/result")
DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")


def parse_date_interval(value, is_end):
    if pd.isna(value) or str(value).strip() == "":
        if is_end:
            return pd.Timestamp.max.normalize(), None, "blank"
        return None, None, "blank"

    value = str(value).strip()
    match = DATE_RE.match(value)
    if match is None:
        return None, None, "malformed"

    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else None
    day = int(match.group(3)) if match.group(3) else None

    try:
        if month is None:
            if is_end:
                return pd.Timestamp(year + 1, 1, 1), "year", None
            return pd.Timestamp(year, 1, 1), "year", None

        if day is None:
            if is_end:
                if month == 12:
                    return pd.Timestamp(year + 1, 1, 1), "month", None
                return pd.Timestamp(year, month + 1, 1), "month", None
            return pd.Timestamp(year, month, 1), "month", None

        return pd.Timestamp(year, month, day), "day", None
    except ValueError:
        return None, None, "malformed"


def add_date_columns(df):
    starts = df["start"].apply(lambda value: parse_date_interval(value, is_end=False))
    ends = df["end"].apply(lambda value: parse_date_interval(value, is_end=True))

    df = df.copy()
    df["start_date"] = starts.apply(lambda result: result[0])
    df["start_precision"] = starts.apply(lambda result: result[1])
    df["start_issue"] = starts.apply(lambda result: result[2])
    df["end_date"] = ends.apply(lambda result: result[0])
    df["end_precision"] = ends.apply(lambda result: result[1])
    df["end_issue"] = ends.apply(lambda result: result[2])
    return df


def minister_overlap_rows(ministers):
    rows = []
    valid = ministers[
        ministers["start_date"].notna()
        & ministers["end_date"].notna()
        & (ministers["end_issue"] != "blank")
    ]

    for (person_id, role), group in valid.groupby(["person_id", "role"], dropna=False):
        group = group.sort_values(["start_date", "end_date", "government"]).reset_index(drop=True)
        previous = None
        for _, row in group.iterrows():
            if previous is not None and row["start_date"] < previous["end_date"]:
                rows.append({
                    "person_id": person_id,
                    "role": role,
                    "overlap_type": "same_interval" if (
                        row["start_date"] == previous["start_date"]
                        and row["end_date"] == previous["end_date"]
                    ) else "partial_overlap",
                    "previous_government": previous["government"],
                    "previous_start": previous["start"],
                    "previous_end": previous["end"],
                    "current_government": row["government"],
                    "current_start": row["start"],
                    "current_end": row["end"],
                })
            if previous is None or row["end_date"] > previous["end_date"]:
                previous = row

    return pd.DataFrame(rows)


def government_mismatch_rows(ministers, governments):
    rows = []
    government_by_name = governments.set_index("government")
    valid = ministers[ministers["start_date"].notna() & ministers["end_date"].notna()]

    for _, row in valid.iterrows():
        gov = government_by_name.loc[row["government"]]
        has_intersection = row["start_date"] < gov["end_date"] and row["end_date"] > gov["start_date"]
        contained = row["start_date"] >= gov["start_date"] and row["end_date"] <= gov["end_date"]

        if not contained:
            rows.append({
                "person_id": row["person_id"],
                "role": row["role"],
                "government": row["government"],
                "minister_start": row["start"],
                "minister_end": row["end"],
                "government_start": gov["start"],
                "government_end": gov["end"],
                "has_intersection": has_intersection,
                "contained_in_government": contained,
            })

    return pd.DataFrame(rows)


class TestMinisterDateIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        LOGGER.info("Loading minister and government metadata for date integrity tests")
        cls.ministers = add_date_columns(
            pd.read_csv(DATA_DIR / "minister.csv", dtype=str, keep_default_na=False)
        )
        cls.governments = add_date_columns(
            pd.read_csv(DATA_DIR / "government.csv", dtype=str, keep_default_na=False)
        )

    def write_diagnostics(self, name, rows):
        path = RESULT_DIR / f"minister-date-integrity-{name}.csv"
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        rows.to_csv(path, index=False)
        LOGGER.error("Wrote %s diagnostic row(s) to %s", len(rows), path)
        return path

    def assert_no_rows(self, rows, message, diagnostic_name):
        if not rows.empty:
            path = self.write_diagnostics(diagnostic_name, rows)
            self.fail(f"{message}: found {len(rows)} row(s); details written to {path}")

    def test_minister_dates_are_parseable(self):
        """Test that non-empty minister start and end dates are parseable."""
        malformed_starts = self.ministers[self.ministers["start_issue"] == "malformed"][
            ["person_id", "government", "role", "start"]
        ]
        malformed_ends = self.ministers[self.ministers["end_issue"] == "malformed"][
            ["person_id", "government", "role", "end"]
        ]

        self.assert_no_rows(
            malformed_starts,
            "Malformed minister start dates",
            "malformed-start-dates",
        )
        self.assert_no_rows(
            malformed_ends,
            "Malformed minister end dates",
            "malformed-end-dates",
        )

    def test_minister_date_intervals_are_not_inverted(self):
        """Test that minister rows do not start after their end date."""
        inverted = self.ministers[
            self.ministers["start_date"].notna()
            & self.ministers["end_date"].notna()
            & (self.ministers["start_date"] > self.ministers["end_date"])
        ][["person_id", "government", "role", "start", "end"]]

        self.assert_no_rows(
            inverted,
            "Minister rows with start date after end date",
            "inverted-intervals",
        )

    def test_minister_person_role_intervals_do_not_partially_overlap(self):
        """
        Test that dated intervals for the same person and role do not partially overlap.
        """
        overlaps = minister_overlap_rows(self.ministers)
        partial_overlaps = overlaps[
            overlaps["overlap_type"] == "partial_overlap"
        ] if len(overlaps) else overlaps

        self.assert_no_rows(
            partial_overlaps,
            "Minister person-role intervals with partial overlaps",
            "partial-overlaps",
        )

    def test_minister_rows_intersect_government_date_intervals(self):
        """
        Test that dated minister rows overlap the referenced government's date interval.
        """
        government_mismatches = government_mismatch_rows(self.ministers, self.governments)
        no_intersection = government_mismatches[
            ~government_mismatches["has_intersection"]
        ] if len(government_mismatches) else government_mismatches

        self.assert_no_rows(
            no_intersection,
            "Minister rows with no intersection with their government interval",
            "government-no-intersection",
        )


if __name__ == "__main__":
    unittest.main()
