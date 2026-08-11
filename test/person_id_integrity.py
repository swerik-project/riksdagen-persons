"""
Test that local SWERIK person identifiers remain stable.

This checks the corpus guarantee that every person in data/person.csv has a
local SWERIK identifier, that those identifiers are unique, and that identifiers
captured in test/data/swerik-person-id-baseline.csv are still present after
metadata synchronization. The guarantee matters because Wikidata synchronization
may refresh external metadata, but it must not remove or rename locally curated
persons such as newly added MPs or ministers.
"""
from collections import Counter
import csv
from pathlib import Path
import re
import unittest

from trainerlog import get_logger


LOGGER = get_logger("person-id-integrity-test")
DATA_DIR = Path(".") / "data"
TEST_DATA_DIR = Path(".") / "test" / "data"
RESULTS_DIR = Path(".") / "test" / "results"
PERSON_PATH = DATA_DIR / "person.csv"
WIKI_ID_PATH = DATA_DIR / "wiki_id.csv"
BASELINE_PATH = TEST_DATA_DIR / "swerik-person-id-baseline.csv"
MISSING_BASELINE_PATH = RESULTS_DIR / "missing-swerik-person-ids.csv"
SWERIK_ID_PATTERN = re.compile(r"^i-[A-Za-z0-9]+$")
WIKIDATA_ID_PATTERN = re.compile(r"^Q[1-9][0-9]*$")


def read_column(path, column):
    with open(path, encoding="utf-8", newline="") as f:
        return [row[column] for row in csv.DictReader(f)]


def write_missing_person_ids(person_ids):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MISSING_BASELINE_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["person_id"])
        for person_id in person_ids:
            writer.writerow([person_id])


class Test(unittest.TestCase):

    def test_person_ids_are_present_and_swerik_ids(self):
        """
        Test every person row has a non-empty local SWERIK person_id.
        """
        invalid = []
        with open(PERSON_PATH, encoding="utf-8", newline="") as f:
            for line_number, row in enumerate(csv.DictReader(f), start=2):
                person_id = row["person_id"]
                if not person_id or not SWERIK_ID_PATTERN.fullmatch(person_id):
                    invalid.append({"line": line_number, "person_id": person_id})

        if invalid:
            LOGGER.error(f"Invalid person_id values found in {PERSON_PATH}: {invalid[:20]}")

        self.assertEqual(
            0,
            len(invalid),
            f"Found {len(invalid)} missing or non-SWERIK person_id value(s) in "
            f"{PERSON_PATH}; first examples: {invalid[:20]}",
        )

    def test_person_ids_are_unique(self):
        """
        Test local SWERIK person_id values are unique in person.csv.
        """
        person_ids = read_column(PERSON_PATH, "person_id")
        counts = Counter(person_ids)
        duplicates = sorted(person_id for person_id, count in counts.items() if count > 1)

        if duplicates:
            LOGGER.error(f"Duplicate person_id values found in {PERSON_PATH}: {duplicates[:20]}")

        self.assertEqual(
            [],
            duplicates,
            f"Found {len(duplicates)} duplicate person_id value(s) in {PERSON_PATH}; "
            f"first examples: {duplicates[:20]}",
        )

    def test_baseline_person_ids_are_unique(self):
        """
        Test the baseline of protected SWERIK person IDs has no duplicates.
        """
        baseline_ids = read_column(BASELINE_PATH, "person_id")
        counts = Counter(baseline_ids)
        duplicates = sorted(person_id for person_id, count in counts.items() if count > 1)

        self.assertEqual(
            [],
            duplicates,
            f"Found {len(duplicates)} duplicate person_id value(s) in {BASELINE_PATH}; "
            f"first examples: {duplicates[:20]}",
        )

    def test_baseline_person_ids_are_still_present(self):
        """
        Test existing local SWERIK person IDs survive Wikidata synchronization.
        """
        current_ids = set(read_column(PERSON_PATH, "person_id"))
        baseline_ids = set(read_column(BASELINE_PATH, "person_id"))
        missing_ids = sorted(baseline_ids - current_ids)

        if missing_ids:
            write_missing_person_ids(missing_ids)
            LOGGER.error(
                f"{len(missing_ids)} baseline person_id value(s) are missing from "
                f"{PERSON_PATH}. Details written to {MISSING_BASELINE_PATH}."
            )

        self.assertEqual(
            [],
            missing_ids,
            f"{len(missing_ids)} baseline person_id value(s) are missing from "
            f"{PERSON_PATH}; details written to {MISSING_BASELINE_PATH}",
        )

    def test_wikidata_ids_are_unique_and_valid(self):
        """
        Test Wikidata item IDs are valid QIDs and do not map to multiple people.
        """
        wiki_ids = read_column(WIKI_ID_PATH, "wiki_id")
        invalid = sorted(wiki_id for wiki_id in wiki_ids if not WIKIDATA_ID_PATTERN.fullmatch(wiki_id))
        counts = Counter(wiki_ids)
        duplicates = sorted(wiki_id for wiki_id, count in counts.items() if count > 1)

        if invalid:
            LOGGER.error(f"Invalid Wikidata IDs found in {WIKI_ID_PATH}: {invalid[:20]}")
        if duplicates:
            LOGGER.error(f"Duplicate Wikidata IDs found in {WIKI_ID_PATH}: {duplicates[:20]}")

        self.assertEqual(
            [],
            invalid,
            f"Found {len(invalid)} invalid Wikidata ID value(s) in {WIKI_ID_PATH}; "
            f"first examples: {invalid[:20]}",
        )
        self.assertEqual(
            [],
            duplicates,
            f"Found {len(duplicates)} duplicate Wikidata ID value(s) in {WIKI_ID_PATH}; "
            f"first examples: {duplicates[:20]}",
        )


if __name__ == "__main__":
    unittest.main()
