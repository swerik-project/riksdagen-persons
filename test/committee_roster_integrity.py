"""Semantic guarantees for curated annual committee-roster observations.

Small frozen source fixtures are sufficient; no source archives, network,
neighboring repository or Git checkout are required. Structural CSV guarantees
remain in CSVW and exact published dates/roles in committee_integrity.
"""

from collections import defaultdict
import json
from pathlib import Path
import unittest

import polars as pl
from trainerlog import get_logger


LOGGER = get_logger("committee-roster-integrity")
BATCH = "2026-10-16-rosters-1950-1970"


class CommitteeRosterIntegrity(unittest.TestCase):
    def test_roster_curations_retain_source_observations(self):
        """Guarantee: every roster curation retains its reviewed year and evidence.

        Data: reviewed_committee_roster_sources.csv and all roster observations
        in reviewed_committee_memberships.json. Compare exact membership, quote,
        source header, chamber, year and citation for every source claim. This
        protects observation years without converting them into service dates.
        Multiple observations may support one undated row, not a continuous
        spell. Failures count claim IDs. Fixtures are agent-curated evidence,
        not proof of source authenticity, roster completeness or human acceptance.
        """
        expected = pl.read_csv("test/data/reviewed_committee_roster_sources.csv", infer_schema=False).to_dicts()
        claims = [c for c in json.loads(Path("test/data/reviewed_committee_memberships.json").read_text())
                  if "roster_observations" in c]
        actual = defaultdict(list)
        for c in claims:
            for observation in c.get("roster_observations", []):
                actual[observation["claim_id"]].append({**c["membership"], **observation})
        reference = {r["claim_id"]: r for r in expected}
        self.assertTrue(reference, "The roster source fixture must not be empty")
        self.assertEqual(len(expected), len(reference), "Roster reference repeats source claim IDs")
        failures = 0
        keys = set(reference) | set(actual)
        LOGGER.info("Checking %s curated roster source claims", len(keys))
        for claim_id in sorted(keys):
            source, matches = reference.get(claim_id), actual.get(claim_id, [])
            if source is None or len(matches) != 1:
                failures += 1
                LOGGER.error("Missing, duplicate or unsupported roster source claim %s", claim_id)
                continue
            claim = matches[0]
            fields = ("person_id", "committee_id", "start", "end", "committee_role_id", "chamber",
                      "url", "excerpt", "source_header", "source_sha256", "source_kind")
            if (any(claim.get(k) != source[k] for k in fields) or str(claim.get("year")) != source["year"]
                    or not source["excerpt"] or not source["url"]):
                failures += 1
                LOGGER.error("Altered roster evidence for %s; expected %s", claim_id, source)
        LOGGER.info("Checked %s roster source claims; %s inconsistent", len(keys), failures)
        self.assertEqual(0, failures, f"{failures} roster claims lack matching evidence; details logged with trainerlog")

    def test_roster_observations_have_compatible_chamber_mandates(self):
        """Guarantee: curated roster observations retain a compatible chamber mandate.

        Data: the frozen roster source fixture and member_of_parliament.csv.
        An accepted identity was matched to a bounded mandate in the printed
        chamber during the observation year. Unknown bounds cannot establish
        that match. Preserve that evidence when mandate data changes, or review
        and update the curation explicitly. Failures count source claim IDs.
        This does not infer committee dates from parliamentary mandate dates.
        """
        sources = pl.read_csv("test/data/reviewed_committee_roster_sources.csv", infer_schema=False)
        mandates = pl.read_csv("data/member_of_parliament.csv", infer_schema=False)
        joined = sources.join(mandates, on="person_id", how="left", suffix="_mp")
        valid = joined.filter(
            (((pl.col("chamber") == "AK") & (pl.col("role") == "andrakammarledamot")) |
             ((pl.col("chamber") == "FK") & (pl.col("role") == "förstakammarledamot"))) &
            (pl.col("start_mp").str.slice(0, 4) <= pl.col("year")) &
            (pl.col("end_mp").str.slice(0, 4) >= pl.col("year")))
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
