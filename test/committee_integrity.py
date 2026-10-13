"""Semantic guarantees for committee source identifiers and abbreviations.

CSVW owns structural types, required fields, primary keys and foreign keys.
"""

import calendar
from datetime import date
from itertools import combinations
from pathlib import Path
import unicodedata
import unittest

import polars as pl
from pyriksdagen.metadata import check_date_overlap
from trainerlog import get_logger


LOGGER = get_logger("committee-integrity")
DATA_DIR = Path("data")


class CommitteeIntegrity(unittest.TestCase):
    def test_wikidata_items_identify_one_committee(self):
        """Guarantee: a Wikidata item never merges distinct committee entities.

        Data: committee_external_identifiers.csv. Deferred incarnations must
        stay unresolved instead of sharing an aggregate Wikidata identifier.
        """
        rows = pl.read_csv(DATA_DIR / "committee_external_identifiers.csv").filter(pl.col("authority") == "wikidata")
        failures = 0
        for group in rows.partition_by("identifier"):
            if group["committee_id"].n_unique() != 1:
                failures += 1
                LOGGER.error("Wikidata item maps to multiple committees: %s", group.to_dicts())
        LOGGER.info("Checked %s committee Wikidata links; %s ambiguous items", rows.height, failures)
        self.assertEqual(0, failures, f"{failures} ambiguous Wikidata items; details logged")

    def test_committees_have_one_wikidata_identity(self):
        """Guarantee: a committee is not equated with multiple Wikidata entities.

        Ordinary renames retain one identity; historic and modern Civilutskottet
        must not both be linked to the same committee.
        """
        rows = pl.read_csv(DATA_DIR / "committee_external_identifiers.csv").filter(pl.col("authority") == "wikidata")
        failures = 0
        for group in rows.partition_by("committee_id"):
            if group["identifier"].n_unique() != 1:
                failures += 1
                LOGGER.error("Committee maps to multiple Wikidata items: %s", group.to_dicts())
        LOGGER.info("Checked %s committee Wikidata links; %s ambiguous committees", rows.height, failures)
        self.assertEqual(0, failures, f"{failures} ambiguous committee identities; details logged")

    def test_source_organ_codes_resolve_to_one_committee(self):
        """Guarantee: a Riksdagen source organ code identifies one committee.

        Case and NFC variants denote the same source code, independently of
        historical abbreviation periods. Reused codes with unresolved entity
        identities are withheld from this first batch, not silently merged.
        """
        rows = pl.read_csv(DATA_DIR / "committee_external_identifiers.csv").filter(
            pl.col("authority") == "riksdagen_org_code"
        )
        targets = {}
        for row in rows.iter_rows(named=True):
            key = unicodedata.normalize("NFC", row["identifier"]).casefold()
            targets.setdefault(key, set()).add(row["committee_id"])
        failures = 0
        for code, committees in sorted(targets.items()):
            if len(committees) != 1:
                failures += 1
                LOGGER.error("Ambiguous source code %s: %s", code, sorted(committees))
        LOGGER.info("Checked %s source organ codes; %s ambiguous", len(targets), failures)
        self.assertEqual(0, failures, f"{failures} ambiguous source organ codes; details logged")

    def test_raw_abbreviations_have_nfc_counterparts(self):
        """Guarantee: every raw abbreviation has an NFC spelling for that committee.

        Preserve raw spellings as aliases; normalization must not erase them.
        """
        rows = pl.read_csv(DATA_DIR / "committee_abbreviation.csv").select("committee_id", "abbreviation")
        spellings = set(rows.iter_rows())
        failures = 0
        for committee_id, abbreviation in sorted(spellings):
            if (committee_id, unicodedata.normalize("NFC", abbreviation)) not in spellings:
                failures += 1
                LOGGER.error("Missing NFC alias for %s: %r", committee_id, abbreviation)
        LOGGER.info("Checked %s abbreviation spellings; %s missing NFC aliases", len(spellings), failures)
        self.assertEqual(0, failures, f"{failures} missing NFC aliases; details logged")

    def test_primary_abbreviation_periods_do_not_definitely_overlap(self):
        """Guarantee: two primary abbreviations never definitely overlap in time.

        For partial dates, compare latest possible starts with earliest possible
        ends. A missing boundary is unknown, not infinite. This does not assert
        complete period coverage or duplicate the general interval validation.
        """
        def bound(value, latest):
            if value is None:
                return None
            parts = [int(part) for part in value.split("-")]
            year = parts[0]
            month = parts[1] if len(parts) > 1 else 12 if latest else 1
            day = parts[2] if len(parts) > 2 else calendar.monthrange(year, month)[1] if latest else 1
            return date(year, month, day)

        rows = pl.read_csv(DATA_DIR / "committee_abbreviation.csv", schema_overrides={
            "start": pl.String, "end": pl.String,
        }).filter(pl.col("primary_abbreviation"))
        failures = 0
        for group in rows.partition_by("committee_id"):
            for left, right in combinations(group.iter_rows(named=True), 2):
                a, b = bound(left["start"], True), bound(left["end"], False)
                c, d = bound(right["start"], True), bound(right["end"], False)
                if None not in (a, b, c, d) and check_date_overlap(a, b, c, d):
                    failures += 1
                    LOGGER.error("Definitely overlapping primary abbreviations: %s / %s", left, right)
        LOGGER.info("Checked %s primary abbreviation rows; %s definitely overlapping pairs", rows.height, failures)
        self.assertEqual(0, failures, f"{failures} definitely overlapping primary pairs; details logged")


if __name__ == "__main__":
    unittest.main()
