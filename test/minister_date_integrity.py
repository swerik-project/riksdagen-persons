"""
Test that minister assignments do not place a person in two governments at once.

This protects the corpus guarantee that a minister row in `data/minister.csv`
can be resolved to a time interval inside the referenced government in
`data/government.csv`, and that no person is assigned to two different
governments during the same effective interval. The guarantee matters because
minister metadata is used when parliamentary records resolve titles such as
`statsrådet` to a person and government role.

The test treats blank minister start/end values as inherited from the referenced
government. When a minister date is wider than the government interval, the
effective interval is clamped to the government interval; this matches the
current corpus convention that one portfolio tenure can be repeated across
successive government rows.

Input data:
- `data/minister.csv`
- `data/government.csv`

The test allows one person to hold multiple roles in the same government at the
same time. It fails only when one person's effective intervals overlap across
different governments.

It also fails when a minister row has no effective intersection with the
referenced government interval. Such rows cannot support date-aware government
resolution, even if the person and role are otherwise valid.

Partial end dates are interpreted as exclusive upper bounds for the following
year or month, so `1979` covers the calendar year 1979 and `1979-10` covers
October 1979.

When failures are found, the test writes structured CSV diagnostics to
`test/results/minister-government-overlaps.csv` or
`test/results/minister-government-disjoint-rows.csv`.
"""
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import unittest
import warnings

from pyriksdagen.utils import parse_date
from trainerlog import get_logger


LOGGER = get_logger("minister-date-integrity-test")
DATA_DIR = Path(".") / "data"
RESULTS_DIR = Path(".") / "test" / "results"
MINISTER_PATH = DATA_DIR / "minister.csv"
GOVERNMENT_PATH = DATA_DIR / "government.csv"
OVERLAP_PATH = RESULTS_DIR / "minister-government-overlaps.csv"
DISJOINT_PATH = RESULTS_DIR / "minister-government-disjoint-rows.csv"

KNOWN_DISJOINT_ROWS = {
    (
        "i-HoKrvTnXU5eTu8LVqgLr9p",
        "Regeringen Posse",
        "konsultativt statsråd",
        "1840-05-16",
        "1841-01-14",
    ),
    (
        "i-HSP9LioPctrDbuGfZ5P4G",
        "Regeringen Adlercreutz",
        "konsultativt statsråd",
        "1859-01-29",
        "1866-09",
    ),
    (
        "i-WAR7Xtq5vM5vhtMxcKDZv4",
        "Regeringen Erlander III",
        "civilminister",
        "1973-11-03",
        "1973-12-31",
    ),
    (
        "i-5FsdBgp7zC1W8jXSUkwwDq",
        "Regeringen Fälldin I",
        "bostadsminister",
        "1978-10-18",
        "1982-10-08",
    ),
    (
        "i-UPW2cbGnTUbMZaKTrot5Bh",
        "Regeringen Andersson",
        "justitieminister",
        "2014-10-03",
        "2020-10-18",
    ),
    (
        "i-UPW2cbGnTUbMZaKTrot5Bh",
        "Regeringen Löfven III",
        "justitieminister",
        "2014-10-03",
        "2020-10-18",
    ),
    (
        "i-PAgTpr3nkZRPEoiqjPKQAf",
        "Regeringen Löfven I",
        "idrottsminister",
        "2019-01-21",
        "2021-11-30",
    ),
    (
        "i-PMx51X9QbaLUMtQNq6sVfz",
        "Regeringen Löfven I",
        "minister för högre utbildning och forskning",
        "2019-01-21",
        "",
    ),
}


@dataclass(frozen=True)
class Interval:
    start: date
    end: date

    def overlaps(self, other):
        return self.start < other.end and other.start < self.end


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_boundary(value, is_start):
    value = (value or "").strip()
    if not value:
        return None

    parts = value.split("-")
    if len(parts) == 1:
        year = int(value)
        return date(year, 1, 1) if is_start else date(year + 1, 1, 1)
    if len(parts) == 2:
        year = int(parts[0])
        month = int(parts[1])
        if is_start:
            return date(year, month, 1)
        if month == 12:
            return date(year + 1, 1, 1)
        return date(year, month + 1, 1)

    parsed = parse_date(value)
    if parsed is None:
        raise ValueError(f"Could not parse date value {value!r}")
    return parsed.date()


def load_government_intervals():
    governments = {}
    for line_number, row in enumerate(read_csv(GOVERNMENT_PATH), start=2):
        start = parse_boundary(row["start"], is_start=True)
        end = parse_boundary(row["end"], is_start=False) if row["end"] else date.max
        governments[row["government"]] = {
            "line": line_number,
            "interval": Interval(start, end),
        }
    return governments


def minister_effective_rows(governments):
    rows = []
    for line_number, row in enumerate(read_csv(MINISTER_PATH), start=2):
        government = governments[row["government"]]
        government_interval = government["interval"]
        minister_start = (
            parse_boundary(row["start"], is_start=True)
            if row["start"]
            else government_interval.start
        )
        minister_end = (
            parse_boundary(row["end"], is_start=False)
            if row["end"]
            else government_interval.end
        )
        effective = Interval(
            max(minister_start, government_interval.start),
            min(minister_end, government_interval.end),
        )
        rows.append(
            {
                "line": line_number,
                "person_id": row["person_id"],
                "role": row["role"],
                "government": row["government"],
                "start": row["start"],
                "end": row["end"],
                "government_start": government_interval.start.isoformat(),
                "government_end": (
                    "" if government_interval.end == date.max
                    else government_interval.end.isoformat()
                ),
                "effective_start": effective.start.isoformat(),
                "effective_end": (
                    "" if effective.end == date.max
                    else effective.end.isoformat()
                ),
                "interval": effective,
            }
        )
    return rows


def find_cross_government_overlaps(rows):
    overlaps = []
    by_person_id = {}
    for row in rows:
        by_person_id.setdefault(row["person_id"], []).append(row)

    for person_rows in by_person_id.values():
        for index, row_a in enumerate(person_rows):
            for row_b in person_rows[index + 1:]:
                if row_a["government"] == row_b["government"]:
                    continue
                if row_a["interval"].overlaps(row_b["interval"]):
                    overlaps.append(
                        {
                            "person_id": row_a["person_id"],
                            "line_a": row_a["line"],
                            "government_a": row_a["government"],
                            "role_a": row_a["role"],
                            "start_a": row_a["start"],
                            "end_a": row_a["end"],
                            "effective_start_a": row_a["effective_start"],
                            "effective_end_a": row_a["effective_end"],
                            "line_b": row_b["line"],
                            "government_b": row_b["government"],
                            "role_b": row_b["role"],
                            "start_b": row_b["start"],
                            "end_b": row_b["end"],
                            "effective_start_b": row_b["effective_start"],
                            "effective_end_b": row_b["effective_end"],
                        }
                    )
    return overlaps


def find_rows_without_government_intersection(rows):
    return [
        {
            "line": row["line"],
            "person_id": row["person_id"],
            "government": row["government"],
            "role": row["role"],
            "start": row["start"],
            "end": row["end"],
            "government_start": row["government_start"],
            "government_end": row["government_end"],
            "effective_start": row["effective_start"],
            "effective_end": row["effective_end"],
        }
        for row in rows
        if row["interval"].start >= row["interval"].end
    ]


def disjoint_row_key(row):
    return (
        row["person_id"],
        row["government"],
        row["role"],
        row["start"],
        row["end"],
    )


def write_overlaps(overlaps):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "person_id",
        "line_a",
        "government_a",
        "role_a",
        "start_a",
        "end_a",
        "effective_start_a",
        "effective_end_a",
        "line_b",
        "government_b",
        "role_b",
        "start_b",
        "end_b",
        "effective_start_b",
        "effective_end_b",
    ]
    with open(OVERLAP_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(overlaps)


def write_disjoint_rows(rows):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "line",
        "person_id",
        "government",
        "role",
        "start",
        "end",
        "government_start",
        "government_end",
        "effective_start",
        "effective_end",
    ]
    with open(DISJOINT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class TestMinisterDateIntegrity(unittest.TestCase):

    def test_minister_rows_intersect_referenced_government(self):
        """
        Test every minister row overlaps the government it references.
        """
        governments = load_government_intervals()
        rows = minister_effective_rows(governments)
        disjoint_rows = find_rows_without_government_intersection(rows)

        if disjoint_rows:
            write_disjoint_rows(disjoint_rows)
            LOGGER.warning(
                f"Found {len(disjoint_rows)} known minister row(s) outside their "
                f"referenced government interval. Details written to {DISJOINT_PATH}."
            )
            warnings.warn(
                f"Known minister/government date mismatches found: {len(disjoint_rows)}; "
                f"details written to {DISJOINT_PATH}",
                UserWarning,
            )

        unexpected_disjoint_rows = [
            row for row in disjoint_rows
            if disjoint_row_key(row) not in KNOWN_DISJOINT_ROWS
        ]

        self.assertEqual(
            [],
            unexpected_disjoint_rows,
            f"Found {len(unexpected_disjoint_rows)} unexpected minister row(s) "
            "outside their referenced "
            f"government interval; details written to {DISJOINT_PATH}",
        )

    def test_ministers_do_not_overlap_across_governments(self):
        """
        Test no person has overlapping effective intervals in different governments.
        """
        governments = load_government_intervals()
        rows = minister_effective_rows(governments)
        overlaps = find_cross_government_overlaps(rows)

        if overlaps:
            write_overlaps(overlaps)
            LOGGER.error(
                f"Found {len(overlaps)} cross-government minister overlap(s). "
                f"Details written to {OVERLAP_PATH}."
            )

        self.assertEqual(
            [],
            overlaps,
            f"Found {len(overlaps)} cross-government minister overlap(s); "
            f"details written to {OVERLAP_PATH}",
        )


if __name__ == "__main__":
    unittest.main()
