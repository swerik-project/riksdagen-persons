"""
Test that manually reviewed minister date evidence remains present in metadata.

This protects the corpus guarantee that hand-reviewed minister start and end
date observations from `test/data/ministers-date-evidence.csv` are represented
in `data/minister.csv`. The guarantee matters because later metadata refreshes
or curation passes must not silently remove dates that have already been
checked against external sources.

Input data:
- `data/minister.csv`
- `test/data/ministers-date-evidence.csv`

The test is boundary-based rather than full-row-based because `minister.csv`
can store the same portfolio across multiple government rows. Year-only
evidence, such as `1858`, is accepted against a more precise date in
`minister.csv`, such as `1858-04-07`.

When evidence is missing, the test writes structured CSV diagnostics to
`test/results/missing-minister-date-evidence.csv`.
"""
import csv
from pathlib import Path
import unittest

from trainerlog import get_logger


LOGGER = get_logger("minister-date-evidence-test")
DATA_DIR = Path(".") / "data"
TEST_DATA_DIR = Path(".") / "test" / "data"
RESULTS_DIR = Path(".") / "test" / "results"
MINISTER_PATH = DATA_DIR / "minister.csv"
EVIDENCE_PATH = TEST_DATA_DIR / "ministers-date-evidence.csv"
MISSING_EVIDENCE_PATH = RESULTS_DIR / "missing-minister-date-evidence.csv"


def read_csv(path, delimiter=","):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def write_missing_evidence(rows):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["date", "type", "person_id", "name", "role", "source"]
    with open(MISSING_EVIDENCE_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def date_matches_observation(actual, expected):
    actual = str(actual).strip()
    expected = str(expected).strip()
    if not actual or not expected:
        return False
    if len(expected) == 4:
        return actual == expected or actual.startswith(f"{expected}-")
    if len(expected) == 7:
        return actual == expected or actual.startswith(f"{expected}-")
    return actual == expected


class TestMinisterDateEvidence(unittest.TestCase):

    def test_manually_checked_minister_date_evidence_is_present(self):
        """
        Test each reviewed boundary observation exists in `data/minister.csv`.
        """
        ministers = read_csv(MINISTER_PATH)
        evidence = read_csv(EVIDENCE_PATH, delimiter=";")
        missing = []

        for observation in evidence:
            date_column = observation["type"].lower()
            matching_rows = [
                row
                for row in ministers
                if row["person_id"] == observation["person_id"]
                and row["role"] == observation["role"]
            ]
            has_date_match = any(
                date_matches_observation(row[date_column], observation["date"])
                for row in matching_rows
            )

            if not matching_rows or not has_date_match:
                missing.append(observation)

        if missing:
            write_missing_evidence(missing)
            LOGGER.error(
                f"{len(missing)} manually checked minister date observation(s) "
                f"are missing from {MINISTER_PATH}. Details written to "
                f"{MISSING_EVIDENCE_PATH}."
            )

        self.assertEqual(
            [],
            missing,
            f"{len(missing)} manually checked minister date observation(s) "
            f"are missing from {MINISTER_PATH}; details written to "
            f"{MISSING_EVIDENCE_PATH}",
        )


if __name__ == "__main__":
    unittest.main()
