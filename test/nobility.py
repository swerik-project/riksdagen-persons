"""Check optional date intervals in data/nobility.csv.

Schema, uniqueness, person references, and title vocabulary are checked by
test.csvw_metadata using the table's CSVW declarations.
"""
import calendar
from datetime import datetime
from pathlib import Path
import re
import unittest

import pandas as pd


DATA_DIR = Path(".") / "data"
NOBILITY_PATH = DATA_DIR / "nobility.csv"


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

    def test_nobility_date_intervals_are_valid(self):
        """
        Guarantee: optional nobility date intervals parse and are not inverted.
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
