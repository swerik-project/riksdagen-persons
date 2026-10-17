"""Source accounting and date semantics for reviewed committee-term spells.

The legacy term fixtures and thin reviewed source references are sufficient
offline. No external source archives or neighboring repositories are needed.
"""

from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path
import unittest

import polars as pl
from trainerlog import get_logger

from .committee_integrity import date_bound
from provenance.committee import read_sources


LOGGER = get_logger("committee-term-integrity")
SOURCE = Path("test/data/reviewed_committee_terms.json")
EXTENSION = Path("test/data/reviewed_committee_term_extension.json")
TERM_1982 = Path("provenance/committee/reviews/term-1982-1985.json")


def reviewed_terms():
    """Project the thin term review without duplicating its shared source text."""
    terms = [dict(json.loads(path.read_text()), census_term="1979-1982") for path in (SOURCE, EXTENSION)]
    source = json.loads(TERM_1982.read_text())
    catalog = read_sources()
    source["spells"] = source.pop("positions")
    source["events"] = [catalog[identifier] for identifier in source["events"].values()]
    source["census_term"] = "1982-1985"
    terms.append(source)
    return terms


class CommitteeTermIntegrity(unittest.TestCase):
    def test_resolved_positions_retain_their_reviewed_appointment_keys(self):
        """Guarantee: resolved held positions retain the appointments recorded in the fixture.

        Data: reviewed_committee_term_extension.json. Its resolution summaries
        and appointment spells must agree, accounting for all 90 originally
        held positions. This does not validate the external MP correction
        reviews referenced by the fixture. Published rows and contemporary
        mandates are checked separately. Failures count resolved positions.
        """
        source = json.loads(EXTENSION.read_text())
        resolved = [s for s in source["spells"] if s.get("resolution_batch")]
        summaries = {p["claim_id"]: p for block in source["resolutions"] for p in block["resolved_positions"]}
        self.assertEqual(90, len(resolved) + len(source["held"]), "The original held-position census must remain complete")
        self.assertEqual({s["claim_id"] for s in resolved}, set(summaries), "Resolved appointments and their summaries must agree")
        failures = 0
        for spell in resolved:
            summary = summaries[spell["claim_id"]]
            valid = (summary["membership"] == spell["membership"]
                     and summary["position_id"] == spell["resolved_position_id"]
                     and summary["election_event"] == spell["election_event"])
            if not valid:
                failures += 1
                LOGGER.error("Resolved position contradicts its appointment summary: %s", spell["resolved_position_id"])
        LOGGER.info("Checked %s resolved positions; %s inconsistent appointments", len(resolved), failures)
        self.assertEqual(0, failures, f"{failures} resolved positions contradict their summaries; details logged with trainerlog")

    def test_reviewed_term_memberships_keep_dates_and_roles(self):
        """Guarantee: every reviewed term appointment remains published at its stated precision.

        Data: reviewed term fixtures and committee_membership.csv. Compare all five
        membership fields exactly, including unknown ends. Later supported date
        refinements must update the affected fixture as well as the data. This
        protects the tracked appointments, not an external curation ledger.
        Failures count appointment claims; CSVW owns structural validation.
        """
        rows = pl.read_csv("data/committee_membership.csv", infer_schema=False)
        published = set(rows.iter_rows())
        failures, total = 0, 0
        for source in reviewed_terms():
            for spell in source["spells"]:
                total += 1
                expected = tuple(spell["membership"][key] for key in rows.columns)
                if expected not in published:
                    failures += 1
                    LOGGER.error("Missing or altered reviewed term appointment: %s", spell["claim_id"])
        LOGGER.info("Checked %s reviewed appointments; %s missing or altered", total, failures)
        self.assertEqual(0, failures, f"{failures} reviewed appointments missing or altered; details logged with trainerlog")

    def test_reviewed_election_positions_are_all_accounted_for(self):
        """Guarantee: each reviewed opening roster and subsequent change is accounted for.

        Data: reviewed term fixtures, checked against the original scans. The
        openings contain 482 positions in 1979 and 496 in 1982; substitute
        allocations differ by committee and term and are never assumed uniform.
        Every later position must be accepted or explicitly held. This is a
        source-position census, not a claim that this many new people or
        uninterrupted service spells were discovered. Failures count events.
        """
        committees, opening_total, total = {}, Counter(), 0
        for source in reviewed_terms():
            term = source["census_term"]
            committees.setdefault(term, set())
            spells, held = source["spells"], source["held"]
            initial = [s for s in spells if s["initial"]]
            expected = source.get("initial_expected_by_committee") or {source["committee_id"]: source["initial_expected"]}
            counts = Counter((s["membership"]["committee_id"], s["role"]) for s in initial)
            counts.update((s["committee_id"], s["role"]) for s in held if s["initial"])
            self.assertEqual({(c, r): n for c, roles in expected.items() for r, n in roles.items()}, dict(counts))
            for committee in expected:
                accepted = [s for s in initial if s["membership"]["committee_id"] == committee]
                self.assertEqual(len(accepted), len({s["membership"]["person_id"] for s in accepted}))
            self.assertFalse(committees[term].intersection(expected), "A committee must not be counted twice within a term")
            committees[term].update(expected)
            opening_total[term] += sum(counts.values())
            self.assertEqual(source["election_positions_expected"], len(spells) + len(held))
            counts = Counter([s["election_event"] for s in spells] +
                             [s.get("election_event") or s["event"] for s in held])
            failures = 0
            for event in source["events"]:
                if event["kind"] == "election_result" and counts[event["id"]] != event["expected_positions"]:
                    failures += 1
                    LOGGER.error("Unaccounted election positions: %s; observed %s", event["id"], counts[event["id"]])
            self.assertEqual(0, failures, f"{failures} election events lost positions; details logged with trainerlog")
            total += len(spells) + len(held)
        LOGGER.info("Checked %s election positions across %s terms", total, len(committees))
        for term in committees:
            self.assertEqual(16, len(committees[term]))
            self.assertEqual({"1979-1982": 482, "1982-1985": 496}[term], opening_total[term])

    def test_reviewed_term_dates_follow_their_stated_source_basis(self):
        """Guarantee: dates preserve confirmed elections, effective clauses and reviewed precision.

        Data: reviewed term fixtures. A confirmed election constitutes appointment
        unless an explicit effective-date clause defers its start.
        End months/years deliberately retain uncertainty. Inclusive ends precede
        an explicitly effective departure/return by one day, not its reporting
        day. Temporary appointments cannot acquire the general term end. Unknown
        ends remain null, not continuous service. Failures count service spells.
        References: historical RO provisions and source events in the fixture.
        """
        failures = 0
        total = 0
        for source in reviewed_terms():
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


    def test_dated_committee_elections_have_contemporary_mp_mandates(self):
        """Guarantee: every dated appointment has a bounded MP mandate on its effective start.

        Data: term spells and member_of_parliament.csv. Unlike the roster-year
        guarantee, these are new service starts and must match an exact day.
        This does not infer uninterrupted service from an MP mandate, nor require
        a leave-taking MP to surrender their original committee appointment.
        Failures count dated appointment claims; unresolved identities stay held.
        """
        spells = [s for source in reviewed_terms() for s in source["spells"]]
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
