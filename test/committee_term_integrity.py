"""Source accounting and date semantics for reviewed committee-term spells.

The small reviewed_committee_terms.json fixture is sufficient offline. These
checks supplement the existing exact-row curation gate, not CSVW validation.
"""

from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path
import unittest

import polars as pl
from trainerlog import get_logger

from .committee_integrity import date_bound


LOGGER = get_logger("committee-term-integrity")
SOURCE = Path("test/data/reviewed_committee_terms.json")


class CommitteeTermIntegrity(unittest.TestCase):
    def test_reviewed_election_positions_are_all_accounted_for(self):
        """Guarantee: the pilot retains all 30 initial and nine change-election positions.

        Data: reviewed_committee_terms.json, checked against the original scans.
        The initial roster has 15 distinct ordinary and 15 distinct substitute
        appointees. Every later position must be accepted or explicitly held.
        This is a source-position census, not a claim that 39 new people or
        uninterrupted service spells were discovered. Failures count events.
        """
        source = json.loads(SOURCE.read_text())
        spells, held = source["spells"], source["held"]
        initial = [s for s in spells if s["initial"]]
        counts = Counter(s["role"] for s in initial)
        self.assertEqual({"Ledamot": 15, "Suppleant": 15}, dict(counts),
                         "Initial roster must retain all 15 ordinary and 15 substitute source positions")
        self.assertEqual(30, len({s["membership"]["person_id"] for s in initial}),
                         "Initial source positions must resolve to 30 distinct MPs")
        self.assertEqual(39, len(spells) + len(held), "Every one of the 39 election positions needs an outcome")
        counts = Counter([s["election_event"] for s in spells] + [s["event"] for s in held])
        failures = 0
        for event in source["events"]:
            if event["kind"] == "election_result" and counts[event["id"]] != event["expected_positions"]:
                failures += 1
                LOGGER.error("Unaccounted election positions: %s; observed %s", event["id"], counts[event["id"]])
        LOGGER.info("Checked 39 election positions; %s events have inconsistent counts", failures)
        self.assertEqual(0, failures, f"{failures} election events lost positions; details logged with trainerlog")

    def test_reviewed_term_dates_follow_their_stated_source_basis(self):
        """Guarantee: dates preserve confirmed elections, effective clauses and reviewed precision.

        Data: reviewed_committee_terms.json. A confirmed election constitutes
        appointment here; no deferred start is stated in these reviewed events.
        End months/years deliberately retain uncertainty. Inclusive ends precede
        an explicitly effective departure/return by one day, not its reporting
        day. Temporary appointments cannot acquire the general term end. Unknown
        ends remain null, not continuous service. Failures count service spells.
        References: historical RO provisions and source events in the fixture.
        """
        source = json.loads(SOURCE.read_text())
        events = {e["id"]: e for e in source["events"]}
        failures = 0
        for spell in source["spells"]:
            row, review = spell["membership"], spell["end_review"]
            election = events[spell["election_event"]]
            valid = election["kind"] == "election_result" and row["start"] == election["date"]
            method = review["method"]
            expected = None
            if method != "unknown":
                boundary = events[review["events"][0]]
                if method == "event_month":
                    expected = boundary["date"][:7]
                    valid &= not (spell["temporary"] and boundary["kind"] == "next_full_election")
                elif method == "event_year":
                    expected = boundary["date"][:4]
                elif method == "before_effective_day":
                    expected = (date.fromisoformat(boundary["effective_date"]) - timedelta(days=1)).isoformat()
                    valid &= boundary["kind"] in {"approved_resignation", "return_announcement"}
                else:
                    valid = False
            valid &= row["end"] == expected and bool(review["reason"])
            if not valid:
                failures += 1
                LOGGER.error("Service dates contradict reviewed source basis: %s", spell)
        LOGGER.info("Checked %s reviewed spells; %s have unsupported boundaries", len(source["spells"]), failures)
        self.assertEqual(0, failures, f"{failures} committee spells have unsupported boundaries; details logged with trainerlog")

    def test_dated_term_curations_retain_their_source_evidence(self):
        """Guarantee: every term curation retains its exact reviewed source and interpretation.

        Data: the term fixture and reviewed_committee_memberships.json. Cross-check
        both directions, so deleting a fixture cannot remove protection. Compare
        the membership, election quotation, revision-pinned URL and date rationale.
        Existing committee_integrity checks the actual published membership row.
        These are agent-reviewed source readings, not independent authentication
        of the source or human acceptance. Failures count service-spell claim IDs.
        """
        source = json.loads(SOURCE.read_text())
        spells = {s["claim_id"]: s for s in source["spells"]}
        claims = [c for c in json.loads(Path("test/data/reviewed_committee_memberships.json").read_text())
                  if c["batch"] == source["batch"]]
        actual = {c["service_source"]["claim_id"]: c for c in claims}
        self.assertEqual(len(actual), len(claims), "Term service-spell claim IDs must be unique")
        events = {e["id"]: e for e in source["events"]}
        failures = 0
        for claim_id in sorted(set(spells) | set(actual)):
            spell, claim = spells.get(claim_id), actual.get(claim_id)
            valid = spell is not None and claim is not None
            if valid:
                event, citation = events[spell["election_event"]], claim["service_source"]
                valid = (claim["membership"] == spell["membership"] and citation["url"] == event["url"]
                         and citation["excerpt"] == event["excerpt"] and citation["source_sha256"] == event["source_sha256"]
                         and citation["end_review"] == spell["end_review"] and bool(source["rule_references"])
                         and bool(event["excerpt"]) and bool(event["paragraphs"]))
                for paragraph in event["paragraphs"]:
                    valid &= (f"/blob/{source['records_revision']}/{event['file']}/#L" in paragraph["url"]
                              and paragraph["url"].endswith("#L" + str(paragraph["line"])) and bool(paragraph["text"]))
            if not valid:
                failures += 1
                LOGGER.error("Term curation lost or altered source evidence: %s", claim_id)
        LOGGER.info("Checked %s term curation IDs; %s lost source evidence", len(set(spells) | set(actual)), failures)
        self.assertEqual(0, failures, f"{failures} term curations lost source evidence; details logged with trainerlog")

    def test_dated_committee_elections_have_contemporary_mp_mandates(self):
        """Guarantee: every dated pilot appointment has a bounded MP mandate on election day.

        Data: term spells and member_of_parliament.csv. Unlike the roster-year
        guarantee, these are new service starts and must match an exact day.
        This does not infer uninterrupted service from an MP mandate, nor require
        a leave-taking MP to surrender their original committee appointment.
        Failures count dated appointment claims; unresolved identities stay held.
        """
        source = json.loads(SOURCE.read_text())
        starts = pl.DataFrame([{**s["membership"], "claim_id": s["claim_id"]} for s in source["spells"]])
        mandates = pl.read_csv("data/member_of_parliament.csv", infer_schema=False)
        joined = starts.select("claim_id", "person_id", pl.col("start").alias("election_day")).join(mandates, on="person_id")
        valid = joined.filter((pl.col("role") == "ledamot") &
            (date_bound("start") <= pl.col("election_day").str.to_date()) &
            (date_bound("end", True) >= pl.col("election_day").str.to_date()))
        missing = starts.filter(~pl.col("claim_id").is_in(valid["claim_id"].implode()))
        LOGGER.info("Checking %s dated committee appointments against MP mandates", starts.height)
        for row in missing.to_dicts():
            LOGGER.error("Dated committee appointment lacks contemporary MP mandate: %s", row)
        self.assertEqual(0, missing.height,
                         f"{missing.height} dated appointments lack contemporary mandates; details logged with trainerlog")
