"""Source-date semantics and MP mandate support for reviewed 1979-1982 spells.

The two retained term fixtures supply the source events and appointments.
These checks do not freeze published membership rows or roster totals.
"""

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


def reviewed_terms():
    """Load the self-contained pilot and extension for the reviewed 1979 term."""
    return [dict(json.loads(path.read_text()), census_term="1979-1982") for path in (SOURCE, EXTENSION)]


class CommitteeTermIntegrity(unittest.TestCase):
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
        """Guarantee: reviewed 1979-1982 appointments have MP service on their start day.

        Data: term spells and member_of_parliament.csv. Unlike the roster-year
        guarantee, these starts must match an exact day. This check covers only
        appointments recorded in the two self-contained 1979-1982 fixtures.
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
