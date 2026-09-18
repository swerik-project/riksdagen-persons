"""
Test nobility metadata integrity.

These tests protect person-level noble-title metadata in data/nobility.csv. The
table is used when historical speaker introductions contain titles such as
greve or friherre, so malformed or duplicate title rows can create incorrect or
ambiguous speaker-resolution candidates.

The test cases verify that:

* data/nobility.csv has the expected columns in the expected order
* each person_id and title pair occurs at most once
* full rows are not duplicated
* every person_id exists in data/person.csv
* every title is normalized to the accepted vocabulary
* optional date intervals parse and do not have start after end
"""
import calendar
from datetime import datetime
from pathlib import Path
import re
import unittest

import pandas as pd
from trainerlog import get_logger


LOGGER = get_logger("nobility-integrity-test")
DATA_DIR = Path(".") / "data"
NOBILITY_PATH = DATA_DIR / "nobility.csv"
PERSON_PATH = DATA_DIR / "person.csv"
EXPECTED_COLUMNS = ["person_id", "start", "end", "title"]
VALID_TITLES = {"greve", "friherre"}


def read_nobility():
    return pd.read_csv(NOBILITY_PATH).fillna("").astype(str)


def parse_endpoint(value, is_end=False):
    if value == "":
        return None
    if re.fullmatch(r"\d{4}", value):
        month = 12 if is_end else 1
        day = 31 if is_end else 1
        return datetime(int(value), month, day)
    if re.fullmatch(r"\d{4}-\d{2}", value):
        year, month = [int(part) for part in value.split("-")]
        day = calendar.monthrange(year, month)[1] if is_end else 1
        return datetime(year, month, day)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return datetime.strptime(value, "%Y-%m-%d")
    raise ValueError(f"invalid date value: {value}")


class Test(unittest.TestCase):

    def test_nobility_schema_is_stable(self):
        """
        Test nobility metadata has the expected columns in the expected order.
        """
        columns = list(pd.read_csv(NOBILITY_PATH, nrows=0).columns)

        self.assertEqual(
            EXPECTED_COLUMNS,
            columns,
            f"{NOBILITY_PATH} must have columns {EXPECTED_COLUMNS}; found {columns}",
        )

    def test_nobility_person_title_pairs_are_unique(self):
        """
        Test that each person has at most one row for each noble title.
        """
        df = read_nobility()
        duplicates = df[df.duplicated(["person_id", "title"], keep=False)]

        if not duplicates.empty:
            LOGGER.error(
                f"Found {len(duplicates)} duplicate person-title row(s) in "
                f"{NOBILITY_PATH}: {duplicates.head(20).to_dict('records')}"
            )

        self.assertTrue(
            duplicates.empty,
            f"Found {len(duplicates)} duplicate person-title row(s) in "
            f"{NOBILITY_PATH}; first examples: {duplicates.head(20).to_dict('records')}",
        )

    def test_nobility_rows_are_unique(self):
        """
        Test that nobility metadata does not contain duplicate full rows.
        """
        df = read_nobility()
        duplicates = df[df.duplicated(keep=False)]

        self.assertTrue(
            duplicates.empty,
            f"Found {len(duplicates)} duplicate full row(s) in {NOBILITY_PATH}; "
            f"first examples: {duplicates.head(20).to_dict('records')}",
        )

    def test_nobility_person_references_exist(self):
        """
        Test that every nobility row references a person in person.csv.
        """
        df = read_nobility()
        person = pd.read_csv(PERSON_PATH, usecols=["person_id"]).fillna("").astype(str)
        missing_persons = df[~df["person_id"].isin(person["person_id"])]

        self.assertTrue(
            missing_persons.empty,
            f"Found {len(missing_persons)} nobility row(s) whose person_id is missing "
            f"from {PERSON_PATH}; first examples: {missing_persons.head(20).to_dict('records')}",
        )

    def test_nobility_titles_are_normalized(self):
        """
        Test that nobility titles use the normalized title vocabulary.
        """
        df = read_nobility()
        invalid_titles = df[~df["title"].isin(VALID_TITLES)]

        self.assertTrue(
            invalid_titles.empty,
            f"Found {len(invalid_titles)} row(s) in {NOBILITY_PATH} with titles outside "
            f"{sorted(VALID_TITLES)}; first examples: {invalid_titles.head(20).to_dict('records')}",
        )

    def test_nobility_date_intervals_are_valid(self):
        """
        Test that optional nobility date intervals parse and are not inverted.
        """
        invalid_dates = []
        for i, row in read_nobility().iterrows():
            try:
                start = parse_endpoint(row["start"])
                end = parse_endpoint(row["end"], is_end=True)
            except ValueError as err:
                invalid_dates.append({
                    "row": i + 2,
                    "person_id": row["person_id"],
                    "title": row["title"],
                    "issue": str(err),
                })
                continue

            if start and end and start > end:
                invalid_dates.append({
                    "row": i + 2,
                    "person_id": row["person_id"],
                    "title": row["title"],
                    "issue": "start is after end",
                })

        self.assertEqual(
            [],
            invalid_dates,
            f"Found {len(invalid_dates)} invalid date interval(s) in {NOBILITY_PATH}; "
            f"first examples: {invalid_dates[:20]}",
        )


if __name__ == "__main__":
    unittest.main()
