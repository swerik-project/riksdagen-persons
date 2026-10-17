"""Source accounting and date semantics for reviewed committee-term spells.

The two reviewed committee-term fixtures are sufficient offline. These
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
EXTENSION = Path("test/data/reviewed_committee_term_extension.json")


class CommitteeTermIntegrity(unittest.TestCase):
    def test_reviewed_election_positions_are_all_accounted_for(self):
        """Guarantee: all 482 opening positions and every reviewed change are accounted for.

        Data: both term fixtures, checked against the original scans. Every
        committee has 15 ordinary members and 15 substitutes (16 for KU and UU).
        Every later position must be accepted or explicitly held. This is a
        source-position census, not a claim that this many new people or
        uninterrupted service spells were discovered. Failures count events.
        """
        committees, opening_total, total = set(), 0, 0
        for path in (SOURCE, EXTENSION):
            source = json.loads(path.read_text())
            spells, held = source["spells"], source["held"]
            initial = [s for s in spells if s["initial"]]
            expected = source.get("initial_expected_by_committee") or {source["committee_id"]: source["initial_expected"]}
            counts = Counter((s["membership"]["committee_id"], s["role"]) for s in initial)
            counts.update((s["committee_id"], s["role"]) for s in held if s["initial"])
            self.assertEqual({(c, r): n for c, roles in expected.items() for r, n in roles.items()}, dict(counts))
            for committee in expected:
                accepted = [s for s in initial if s["membership"]["committee_id"] == committee]
                self.assertEqual(len(accepted), len({s["membership"]["person_id"] for s in accepted}))
            self.assertFalse(committees.intersection(expected), "A committee must not be counted in both fixtures")
            committees.update(expected)
            opening_total += sum(counts.values())
            self.assertEqual(source["election_positions_expected"], len(spells) + len(held))
            counts = Counter([s["election_event"] for s in spells] +
                             [s.get("election_event", s["event"]) for s in held])
            failures = 0
            for event in source["events"]:
                if event["kind"] == "election_result" and counts[event["id"]] != event["expected_positions"]:
                    failures += 1
                    LOGGER.error("Unaccounted election positions: %s; observed %s", event["id"], counts[event["id"]])
            self.assertEqual(0, failures, f"{failures} election events lost positions; details logged with trainerlog")
            total += len(spells) + len(held)
        LOGGER.info("Checked %s election positions across %s committees", total, len(committees))
        self.assertEqual(16, len(committees))
        self.assertEqual(482, opening_total)

    def test_reviewed_term_dates_follow_their_stated_source_basis(self):
        """Guarantee: dates preserve confirmed elections, effective clauses and reviewed precision.

        Data: both term fixtures. A confirmed election constitutes appointment
        unless an explicit effective-date clause defers its start.
        End months/years deliberately retain uncertainty. Inclusive ends precede
        an explicitly effective departure/return by one day, not its reporting
        day. Temporary appointments cannot acquire the general term end. Unknown
        ends remain null, not continuous service. Failures count service spells.
        References: historical RO provisions and source events in the fixture.
        """
        failures = 0
        total = 0
        for path in (SOURCE, EXTENSION):
            source = json.loads(path.read_text())
            events = {e["id"]: e for e in source["events"]}
            for spell in source["spells"]:
                row, review = spell["membership"], spell["end_review"]
                election = events[spell["election_event"]]
                valid = election["kind"] == "election_result" and row["start"] == election.get("effective_date", election["date"])
                method, expected = review["method"], None
                if method != "unknown":
                    boundary = events[review["events"][0]]
                    valid &= not (spell["temporary"] and boundary["kind"] == "next_full_election")
                    if method == "event_month":
                        expected = boundary["date"][:7]
                    elif method == "event_year":
                        expected = boundary["date"][:4]
                    elif method == "before_effective_day":
                        expected = (date.fromisoformat(boundary["effective_date"]) - timedelta(days=1)).isoformat()
                        valid &= boundary["kind"] in {"approved_resignation", "return_announcement", "replacement_change"}
                    else:
                        valid = False
                    precision = review.get("precision", "day")
                    valid &= precision in {"day", "month", "year"}
                    if expected:
                        expected = expected[:{"day": 10, "month": 7, "year": 4}.get(precision, 10)]
                valid &= row["end"] == expected and bool(review["reason"])
                if not valid:
                    failures += 1
                    LOGGER.error("Service dates contradict reviewed source basis: %s", spell)
            for position in source["held"]:
                if "effective_start" not in position:
                    continue
                election = events[position["election_event"]]
                if position["effective_start"] != election.get("effective_date", election["date"]):
                    failures += 1
                    LOGGER.error("Held position lost its deferred-start evidence: %s", position["name_as_printed"])
            total += len(source["spells"])
        LOGGER.info("Checked %s reviewed spells; %s have unsupported boundaries", total, failures)
        self.assertEqual(0, failures, f"{failures} committee spells have unsupported boundaries; details logged with trainerlog")

    def test_dated_term_curations_retain_their_source_evidence(self):
        """Guarantee: every term curation retains its exact reviewed source and interpretation.

        Data: both term fixtures and reviewed_committee_memberships.json. Cross-check
        both directions, so deleting a fixture cannot remove protection. Compare
        the membership, election quotation, revision-pinned URL and date rationale.
        Existing committee_integrity checks the actual published membership row.
        These are agent-reviewed source readings, not independent authentication
        of the source or human acceptance. Failures count service-spell claim IDs.
        """
        failures = 0
        total = 0
        all_claims = json.loads(Path("test/data/reviewed_committee_memberships.json").read_text())
        for path in (SOURCE, EXTENSION):
            source = json.loads(path.read_text())
            spells = {s["claim_id"]: s for s in source["spells"]}
            self.assertEqual(len(spells), len(source["spells"]), "Fixture claim IDs must be unique")
            claims = [c for c in all_claims if c["batch"] == source["batch"]]
            actual = {c["service_source"]["claim_id"]: c for c in claims}
            self.assertEqual(len(actual), len(claims), "Term service-spell claim IDs must be unique")
            events = {e["id"]: e for e in source["events"]}
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
            total += len(set(spells) | set(actual))
        LOGGER.info("Checked %s term curation IDs; %s lost source evidence", total, failures)
        self.assertEqual(0, failures, f"{failures} term curations lost source evidence; details logged with trainerlog")

    def test_dated_committee_elections_have_contemporary_mp_mandates(self):
        """Guarantee: every dated appointment has a bounded MP mandate on its effective start.

        Data: term spells and member_of_parliament.csv. Unlike the roster-year
        guarantee, these are new service starts and must match an exact day.
        This does not infer uninterrupted service from an MP mandate, nor require
        a leave-taking MP to surrender their original committee appointment.
        Failures count dated appointment claims; unresolved identities stay held.
        """
        spells = [s for path in (SOURCE, EXTENSION) for s in json.loads(path.read_text())["spells"]]
        starts = pl.DataFrame([{**s["membership"], "claim_id": s["claim_id"]} for s in spells])
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
