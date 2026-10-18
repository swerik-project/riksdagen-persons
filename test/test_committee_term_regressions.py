"""Intentional small mutations proving the committee-term source gates turn red."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

import polars as pl

from . import committee_term_integrity as integrity


class CommitteeTermRegressions(unittest.TestCase):
    def setUp(self):
        self.source = json.loads(integrity.SOURCE.read_text())
        self.gates = integrity.CommitteeTermIntegrity()

    def changed_source(self, source, filename=None):
        original = Path.read_text
        def read(path, *args, **kwargs):
            return json.dumps(source) if path.name == (filename or integrity.SOURCE.name) else original(path, *args, **kwargs)
        return patch.object(Path, "read_text", read)

    def test_allgulander_alias_cannot_be_deleted_or_reassigned(self):
        """Guarantee: losing the sourced alias or assigning it to another MP turns the gate red."""
        names = pl.read_csv("data/name.csv", infer_schema=False)
        target = (pl.col("person_id") == "i-4GBx7Um4NanvqMymTXXzRL") & (pl.col("name") == "Swante Allgulander")
        remaining = names.filter(~target)
        reassigned = names.filter(target).with_columns(pl.lit("other-person").alias("person_id"))
        for mutated in (remaining, pl.concat([remaining, reassigned])):
            with patch.object(integrity.pl, "read_csv", return_value=mutated), self.assertRaisesRegex(AssertionError, "1 required Allgulander alias rows"):
                self.gates.test_allgulander_source_spelling_retains_the_existing_person()

    def test_allgulander_leave_cover_ends_before_nilsson_returns(self):
        """Guarantee: Nilsson's 15 March return cannot become Allgulander's last service day."""
        source = json.loads(integrity.EXTENSION.read_text())
        spell = next(s for s in source["spells"] if s.get("resolved_position_id") == "5b51c5e260b59b2477fe6c83")
        spell["membership"]["end"] = "1982-03-15"
        with self.changed_source(source, integrity.EXTENSION.name), self.assertRaises(AssertionError):
            self.gates.test_reviewed_term_dates_follow_their_stated_source_basis()

    def test_missing_initial_roster_position_turns_the_gate_red(self):
        """Guarantee: dropping one initial appointee cannot pass the 30-position census."""
        self.source["spells"].pop(0)
        with self.changed_source(self.source), self.assertRaises(AssertionError):
            self.gates.test_reviewed_election_positions_are_all_accounted_for()

    def test_nomination_cannot_support_a_service_start(self):
        """Guarantee: a nomination substituted for the confirmed election turns the gate red."""
        self.source["events"][0]["kind"] = "nomination"
        with self.changed_source(self.source), self.assertRaises(AssertionError):
            self.gates.test_reviewed_term_dates_follow_their_stated_source_basis()

    def test_reporting_day_cannot_replace_effective_return_day(self):
        """Guarantee: using 24 May rather than the explicit 20 May return fails."""
        spell = next(s for s in self.source["spells"] if s["election_event"] == "egervarn_second")
        spell["membership"]["end"] = "1982-05-23"
        with self.changed_source(self.source), self.assertRaises(AssertionError):
            self.gates.test_reviewed_term_dates_follow_their_stated_source_basis()

    def test_unknown_temporary_end_cannot_be_filled(self):
        """Guarantee: extending the leave-conditional appointment to term end fails."""
        spell = next(s for s in self.source["spells"] if s["election_event"] == "abark_temporary")
        spell["membership"]["end"] = "1982-10"
        with self.changed_source(self.source), self.assertRaises(AssertionError):
            self.gates.test_reviewed_term_dates_follow_their_stated_source_basis()

    def test_coarse_end_cannot_gain_unreviewed_day_precision(self):
        """Guarantee: converting a reviewed month into an invented final day fails."""
        spell = next(s for s in self.source["spells"] if s["membership"]["end"] == "1982-10")
        spell["membership"]["end"] = "1982-10-11"
        with self.changed_source(self.source), self.assertRaises(AssertionError):
            self.gates.test_reviewed_term_dates_follow_their_stated_source_basis()

    def test_merging_two_temporary_elections_loses_a_source_position(self):
        """Guarantee: joining Egervarn's 1981 and 1982 appointments cannot hide the missing election."""
        spell = next(s for s in self.source["spells"] if s["election_event"] == "egervarn_second")
        self.source["spells"].remove(spell)
        with self.changed_source(self.source), self.assertRaises(AssertionError):
            self.gates.test_reviewed_election_positions_are_all_accounted_for()


    def test_losing_an_extension_committee_turns_the_census_red(self):
        """Guarantee: the all-committee extension cannot silently lose an opening roster."""
        source = json.loads(integrity.EXTENSION.read_text())
        committee = source["spells"][0]["membership"]["committee_id"]
        source["spells"] = [s for s in source["spells"] if not
                            (s["initial"] and s["membership"]["committee_id"] == committee)]
        with self.changed_source(source, integrity.EXTENSION.name), self.assertRaises(AssertionError):
            self.gates.test_reviewed_election_positions_are_all_accounted_for()

    def test_deferred_effective_start_cannot_be_dropped(self):
        """Guarantee: holding an unresolved identity does not erase the explicit September start."""
        source = json.loads(integrity.EXTENSION.read_text())
        event = next(e for e in source["events"] if e["kind"] == "election_result" and e.get("effective_date"))
        del event["effective_date"]
        with self.changed_source(source, integrity.EXTENSION.name), self.assertRaises(AssertionError):
            self.gates.test_reviewed_term_dates_follow_their_stated_source_basis()

    def test_january_announcement_cannot_extend_december_leave_cover(self):
        """Guarantee: an announcement in January cannot replace the explicit December return."""
        source = json.loads(integrity.EXTENSION.read_text())
        spell = next(s for s in source["spells"] if s["end_review"]["events"] == ["december18_returns"])
        spell["membership"]["end"] = "1982-01-10"
        with self.changed_source(source, integrity.EXTENSION.name), self.assertRaises(AssertionError):
            self.gates.test_reviewed_term_dates_follow_their_stated_source_basis()

    def test_extension_temporary_cover_cannot_inherit_term_end(self):
        """Guarantee: even a changed rationale cannot extend temporary cover to the next election."""
        source = json.loads(integrity.EXTENSION.read_text())
        spell = next(s for s in source["spells"] if s["temporary"])
        spell["membership"]["end"] = "1982-10"
        spell["end_review"].update(method="event_month", events=["next_roster"])
        with self.changed_source(source, integrity.EXTENSION.name), self.assertRaises(AssertionError):
            self.gates.test_reviewed_term_dates_follow_their_stated_source_basis()

    def test_published_appointments_cannot_lose_reviewed_dates_or_roles(self):
        """Guarantee: deleting an appointment or changing its dates/role turns the gate red."""
        target = self.source["spells"][0]["membership"]
        rows = pl.read_csv("data/committee_membership.csv", infer_schema=False)
        matches = pl.all_horizontal([pl.col(key).eq_missing(pl.lit(value, dtype=pl.String))
                                     for key, value in target.items()])
        remaining = rows.filter(~matches)
        for changes in (None, {"end": "1980"}, {"committee_role_id": "other-role"}):
            mutated = remaining if changes is None else pl.concat([
                remaining, pl.DataFrame([{**target, **changes}], schema=rows.schema)])
            with patch.object(integrity.pl, "read_csv", return_value=mutated), \
                 self.assertRaisesRegex(AssertionError, "1 reviewed appointments missing or altered"):
                self.gates.test_reviewed_term_memberships_keep_dates_and_roles()

    def test_resolved_appointment_cannot_disagree_with_its_tracked_summary(self):
        """Guarantee: a formerly held position cannot silently change its resolved membership."""
        source = json.loads(integrity.EXTENSION.read_text())
        summary = source["resolutions"][0]["resolved_positions"][0]
        summary["membership"]["person_id"] = "other-person"
        with self.changed_source(source, integrity.EXTENSION.name), \
             self.assertRaisesRegex(AssertionError, "1 resolved positions contradict"):
            self.gates.test_resolved_positions_retain_their_reviewed_appointment_keys()
