"""Semantic guarantees for curated annual committee-roster observations.

Small frozen source fixtures are sufficient; no source archives, network,
neighboring repository or Git checkout are required. Structural CSV guarantees
remain in CSVW and exact published dates/roles in committee_integrity.
"""

import json
from pathlib import Path
from provenance.committee import read_roster
import unittest

import polars as pl
from trainerlog import get_logger

from .committee_integrity import date_bound


LOGGER = get_logger("committee-roster-integrity")
BATCH = "2026-10-16-rosters-1950-1970"


class CommitteeRosterIntegrity(unittest.TestCase):
    def test_reviewed_election_identities_retain_published_source_links(self):
        """Guarantee: identity evidence retains its published person, citation and observation.

        Data: reviewed_committee_election_identities.json and the roster source
        fixture. Each identity check must refer to one published claim and agree
        with its exact day when recorded. Reviewed section evidence may refine
        a year-only source fixture to a day within that year. Duplicate checks
        and orphaned references fail. Failures count identity claim IDs;
        this does not independently authenticate the source or infer service dates.
        """
        identities = pl.read_json("test/data/reviewed_committee_election_identities.json")
        sources = read_roster().select(
            "claim_id", "person_id", "url", "event_date", "year")
        joined = identities.join(sources, on="claim_id", how="left", suffix="_source")
        invalid = joined.filter(pl.col("person_id_source").is_null() |
            (pl.col("person_id") != pl.col("person_id_source")) |
            (pl.col("url") != pl.col("url_source")) |
            pl.col("observed_start").is_null() | pl.col("observed_end").is_null() |
            (pl.col("observed_start") != pl.col("observed_end")) |
            (pl.col("observed_start").str.slice(0, 4) != pl.col("year")) |
            (pl.col("event_date").is_not_null() & (pl.col("observed_start") != pl.col("event_date"))))
        duplicate_ids = identities.group_by("claim_id").len().filter(pl.col("len") > 1)["claim_id"]
        failures = pl.concat([invalid["claim_id"], duplicate_ids]).unique().len()
        LOGGER.info("Checking published source links for %s election identity claims", identities.height)
        for row in invalid.to_dicts():
            LOGGER.error("Election identity check lost its published source link: %s", row)
        for claim_id in duplicate_ids:
            LOGGER.error("Duplicate election identity check: %s", claim_id)
        LOGGER.info("Checked %s election identity claims; %s source links inconsistent", identities.height, failures)
        self.assertEqual(0, failures,
            f"{failures} election identity source links inconsistent; details logged with trainerlog")

    def test_reviewed_election_identities_have_contemporary_mandates(self):
        """Guarantee: election identities retain a mandate at the observed time.

        Data: reviewed_committee_election_identities.json and MP mandates.
        The fixture preserves an exact election day where known, otherwise
        the source's calendar year. These comparison bounds are observation
        precision, never committee service dates. Failures count source claims.
        This strengthens the roster chamber/year gate for recovered readings.
        """
        sources = pl.read_json("test/data/reviewed_committee_election_identities.json")
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
        sources = pl.read_json("test/data/reviewed_committee_election_identities.json").filter(
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
        sources = pl.read_json("test/data/reviewed_committee_election_identities.json").filter(
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


    def test_dated_roster_observations_fit_their_assigned_service_spells(self):
        """Guarantee: exact roster days agree with the source year and assigned spell.

        Data: provenance/committee/observations.csv. An election observed on a
        known day cannot corroborate a service spell that ended earlier in the
        same calendar year. Unknown endpoints remain unknown. Comparison bounds
        allow the stated precision of partial dates without changing those dates.
        Failures count source claim IDs; no Git or archived scans are required.
        """
        rows = read_roster()
        rows = rows.filter(pl.col("event_date").is_not_null()).with_columns(
            pl.col("event_date").str.to_date("%Y-%m-%d", strict=False).alias("observed"))
        invalid = rows.filter(pl.col("observed").is_null() |
            (pl.col("event_date").str.slice(0, 4) != pl.col("year")) |
            (pl.col("start").is_not_null() & (date_bound("start") > pl.col("observed"))) |
            (pl.col("end").is_not_null() & (date_bound("end", True) < pl.col("observed"))))
        LOGGER.info("Checking %s exact roster days against assigned spells", rows.height)
        for row in invalid.to_dicts():
            LOGGER.error("Roster day contradicts its source year or assigned spell: %s", row)
        LOGGER.info("Checked %s exact roster days; %s inconsistent", rows.height, invalid.height)
        self.assertEqual(0, invalid.height,
                         f"{invalid.height} dated roster claims contradict their assigned spells; details logged with trainerlog")

    def test_scan_corrected_false_memberships_are_not_reintroduced(self):
        """Guarantee: scan-disproved undated memberships and claims stay withdrawn.

        Data: reviewed_committee_roster_corrections.json records two displaced
        1976 names, their removed rows, original claim IDs and scan evidence.
        Correct memberships are protected by the positive curation fixture.
        Any later evidence for these same undated facts requires an explicit
        review of this fixture. Failures count corrected source claims.
        """
        corrections = json.loads(Path("test/data/reviewed_committee_roster_corrections.json").read_text())
        memberships = pl.read_csv("data/committee_membership.csv", infer_schema=False).to_dicts()
        source_ids = set(read_roster()["claim_id"])
        failures = 0
        LOGGER.info("Checking %s scan-corrected false roster claims", len(corrections))
        for correction in corrections:
            if correction["membership"] in memberships or correction["claim_id"] in source_ids:
                failures += 1
                LOGGER.error("Scan-disproved roster fact reintroduced: %s", correction)
        LOGGER.info("Checked %s corrected claims; %s reintroduced", len(corrections), failures)
        self.assertEqual(0, failures,
                         f"{failures} scan-disproved roster facts reintroduced; details logged with trainerlog")

    def test_roster_observations_have_compatible_chamber_mandates(self):
        """Guarantee: curated roster observations retain a compatible chamber mandate.

        Data: the frozen roster source fixture and member_of_parliament.csv.
        An accepted identity was matched to a bounded mandate in the printed
        chamber during the observation year, or on its exact day when known.
        Unknown bounds cannot establish that match. Preserve that evidence when
        mandate data changes, or review and update the curation explicitly.
        Failures count source claim IDs.
        This does not infer committee dates from parliamentary mandate dates.
        """
        sources = read_roster()
        mandates = pl.read_csv("data/member_of_parliament.csv", infer_schema=False)
        joined = sources.join(mandates, on="person_id", how="left", suffix="_mp")
        valid = joined.filter(
            (((pl.col("chamber") == "AK") & (pl.col("role") == "andrakammarledamot")) |
             ((pl.col("chamber") == "FK") & (pl.col("role") == "förstakammarledamot")) |
             ((pl.col("chamber") == "EK") & (pl.col("role") == "ledamot") &
              (pl.col("year") >= "1971"))) &
            (pl.col("start_mp").str.slice(0, 4) <= pl.col("year")) &
            (pl.col("end_mp").str.slice(0, 4) >= pl.col("year")) &
            (pl.col("event_date").is_null() |
             ((date_bound("start_mp") <= pl.col("event_date").str.to_date("%Y-%m-%d", strict=False)) &
              (date_bound("end_mp", True) >= pl.col("event_date").str.to_date("%Y-%m-%d", strict=False)))))
        missing = sources.filter(~pl.col("claim_id").is_in(valid["claim_id"].implode()))
        LOGGER.info("Checking chamber mandates for %s roster observations", sources.height)
        for row in missing.to_dicts():
            LOGGER.error("Roster observation lacks compatible chamber mandate: %s", row)
        LOGGER.info("Checked %s roster observations; %s lack a compatible mandate", sources.height, missing.height)
        self.assertEqual(0, missing.height,
                         f"{missing.height} roster observations lack compatible mandates; details logged with trainerlog")

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
