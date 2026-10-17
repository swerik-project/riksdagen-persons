"""Semantic guarantees supported by tracked committee identity/correction fixtures.

Small frozen source fixtures are sufficient; no source archives, network,
neighboring repository or Git checkout are required. Structural CSV guarantees
remain in CSVW. Archive-wide roster observation accounting is outside this suite.
"""

import json
from pathlib import Path
import unittest

import polars as pl
from trainerlog import get_logger

from .committee_integrity import date_bound
from provenance.committee import read_roster


LOGGER = get_logger("committee-roster-integrity")


class CommitteeRosterIntegrity(unittest.TestCase):
    def test_recovered_kultur_rosters_retain_all_printed_positions(self):
        """Guarantee: all six scan-reviewed Kultur rosters retain their 15 positions.

        Data: a thin reviewed claim census, canonical observations and published
        memberships. Preserve the observed day/year, identity and role without
        interpreting annual observations as uninterrupted service. Failures
        count rosters; source quotations are shared in the source catalog.
        """
        review = json.loads(Path("provenance/committee/reviews/kultur-1971-1973.json").read_text())
        self.assertEqual(review["expected_rosters"], len(review["rosters"]), "A recovered Kultur roster disappeared")
        observations = read_roster().to_dicts()
        by_claim = {row["claim_id"]: row for row in observations}
        memberships = pl.read_csv("data/committee_membership.csv", infer_schema=False)
        keys = memberships.columns
        published = set(memberships.iter_rows())
        failures = 0
        for roster in review["rosters"]:
            rows = [by_claim.get(identifier) for identifier in roster["claim_ids"]]
            valid = len(rows) == roster["expected"] and all(rows)
            if valid:
                valid = len({row["person_id"] for row in rows}) == roster["expected"]
                valid &= all(all(row[key] == roster[key] for key in
                    ("committee_id", "committee_role_id", "year")) and
                    row["event_date"] == (None if row["claim_id"] in roster.get("year_only_claim_ids", []) else roster["event_date"]) and
                    tuple(row[key] for key in keys) in published for row in rows)
            if not valid:
                failures += 1
                LOGGER.error("Recovered Kultur roster lost a position, precision or role: %s", roster)
        LOGGER.info("Checked %s recovered Kultur rosters; %s inconsistent", len(review["rosters"]), failures)
        self.assertEqual(0, failures, f"{failures} recovered Kultur rosters changed; details logged with trainerlog")

    def test_reviewed_election_identities_have_contemporary_mandates(self):
        """Guarantee: election identities retain a mandate at the observed time.

        Data: reviewed_committee_election_identities.json and MP mandates.
        The fixture preserves an exact election day where known, otherwise
        the source's calendar year. These comparison bounds are observation
        precision, never committee service dates. Failures count source claims.
        This does not check observations in an external roster archive.
        """
        sources = pl.read_json("test/data/reviewed_committee_election_identities.json", infer_schema_length=None)
        mandates = pl.read_csv("data/member_of_parliament.csv", infer_schema=False)
        joined = sources.join(mandates, on="person_id", how="left")
        valid = joined.filter((pl.col("role") == "ledamot") &
            (date_bound("start") <= date_bound("observed_end", True)) &
            (date_bound("end", True) >= date_bound("observed_start")))
        missing = sources.filter(~pl.col("claim_id").is_in(valid["claim_id"].implode()))
        LOGGER.info("Checking contemporaneous mandates for %s recovered election claims", sources.height)
        for row in missing.to_dicts():
            LOGGER.error("Recovered election identity lacks contemporary mandate: %s", row)
        LOGGER.info("Checked %s recovered election claims; %s lack a contemporary mandate", sources.height, missing.height)
        self.assertEqual(0, missing.height,
            f"{missing.height} recovered election identities lack contemporary mandates; details logged with trainerlog")

    def test_party_disambiguated_election_identities_retain_dated_party_evidence(self):
        """Guarantee: party-disambiguated election identities keep dated party support.

        Data: the reviewed election identity fixture and party_affiliation.csv.
        Only claims that needed the printed party to choose between names are
        checked. Unknown party dates cannot establish an identity at that time.
        Failures count source claims; this does not change party affiliations.
        """
        sources = pl.read_json("test/data/reviewed_committee_election_identities.json", infer_schema_length=None).filter(
            pl.col("party_required")).rename({"party": "printed_party"})
        parties = pl.read_csv("data/party_affiliation.csv", infer_schema=False)
        joined = sources.join(parties, on="person_id", how="left")
        valid = joined.filter((pl.col("party") == pl.col("printed_party")) &
            (date_bound("start") <= date_bound("observed_end", True)) &
            (date_bound("end", True) >= date_bound("observed_start")))
        missing = sources.filter(~pl.col("claim_id").is_in(valid["claim_id"].implode()))
        LOGGER.info("Checking dated party evidence for %s disambiguated election claims", sources.height)
        for row in missing.to_dicts():
            LOGGER.error("Party-disambiguated election identity lost dated party evidence: %s", row)
        LOGGER.info("Checked %s party-disambiguated claims; %s lost evidence", sources.height, missing.height)
        self.assertEqual(0, missing.height,
            f"{missing.height} election identities lack required dated party evidence; details logged with trainerlog")

    def test_reviewed_election_identities_retain_printed_gender_agreement(self):
        """Guarantee: reviewed honorific readings agree with the selected person's gender.

        Data: the reviewed election identity fixture and person.csv. Printed
        honorifics and their ditto repetitions help distinguish shared surnames
        in the 1976 scan. Unknown printed gender is allowed and never guessed.
        Failures count source claims; source authenticity still needs review.
        """
        sources = pl.read_json("test/data/reviewed_committee_election_identities.json", infer_schema_length=None).filter(
            pl.col("gender").is_not_null())
        persons = pl.read_csv("data/person.csv", infer_schema=False)
        joined = sources.join(persons, on="person_id", how="left", suffix="_recorded")
        invalid = joined.filter((pl.col("gender") != pl.col("gender_recorded")) |
                                pl.col("gender_recorded").is_null())
        LOGGER.info("Checking printed honorifics for %s recovered election claims", sources.height)
        for row in invalid.to_dicts():
            LOGGER.error("Recovered election honorific disagrees with selected identity: %s", row)
        LOGGER.info("Checked %s honorific readings; %s disagree", sources.height, invalid.height)
        self.assertEqual(0, invalid.height,
            f"{invalid.height} election identities contradict printed honorifics; details logged with trainerlog")


    def test_scan_corrected_false_memberships_are_not_reintroduced(self):
        """Guarantee: scan-disproved undated memberships stay withdrawn.

        Data: reviewed_committee_roster_corrections.json records two displaced
        1976 names, their removed rows, original claim IDs and scan evidence.
        Any later evidence for these same undated facts requires an explicit
        review of this fixture. Failures count corrected memberships. This
        does not inspect claim IDs in an external source archive.
        """
        corrections = json.loads(Path("test/data/reviewed_committee_roster_corrections.json").read_text())
        memberships = pl.read_csv("data/committee_membership.csv", infer_schema=False).to_dicts()
        failures = 0
        LOGGER.info("Checking %s scan-corrected false roster claims", len(corrections))
        for correction in corrections:
            if correction["membership"] in memberships:
                failures += 1
                LOGGER.error("Scan-disproved roster fact reintroduced: %s", correction)
        LOGGER.info("Checked %s corrected claims; %s reintroduced", len(corrections), failures)
        self.assertEqual(0, failures,
                         f"{failures} scan-disproved roster facts reintroduced; details logged with trainerlog")

    def test_reviewed_historical_committee_identities_remain_distinct(self):
        """Guarantee: reviewed historical bodies retain their distinct identities.

        Data: committee.csv and reviewed_committee_roster_entities.json. The
        chamber preparation committees must not be conflated with each other
        or the common body used from 1954 onward. Special committees remain
        scoped to their sessions. Unknown institutional boundaries stay unknown.
        Later sourced enrichment must update the fixture. Failures count bodies.
        CSVW owns primary keys and foreign keys, not these historical meanings.
        """
        expected = json.loads(Path("test/data/reviewed_committee_roster_entities.json").read_text())
        rows = pl.read_csv("data/committee.csv", infer_schema=False)
        published = {r["committee_id"]: r for r in rows.to_dicts()}
        failures = 0
        LOGGER.info("Checking %s reviewed historical committee identities", len(expected))
        for reference in expected:
            entity = reference["entity"]
            if published.get(entity["committee_id"]) != entity:
                failures += 1
                LOGGER.error("Missing or altered historical committee identity: %s; source: %s",
                             entity, reference["source"]["url"])
        LOGGER.info("Checked %s historical bodies; %s missing or altered", len(expected), failures)
        self.assertEqual(0, failures,
                         f"{failures} historical committee identities changed; details logged with trainerlog")


if __name__ == "__main__":
    unittest.main()
