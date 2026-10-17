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

    def test_thin_1982_census_rejects_a_missing_opening_position(self):
        """Guarantee: deleting one accepted 1982 position turns its independent term census red."""
        source = json.loads(integrity.TERM_1982.read_text())
        source["positions"].remove(next(p for p in source["positions"] if p["initial"]))
        with self.changed_source(source, integrity.TERM_1982.name), self.assertRaises(AssertionError):
            self.gates.test_reviewed_election_positions_are_all_accounted_for()

    def test_thin_1982_deferred_start_and_unknown_end_keep_their_meaning(self):
        """Guarantee: deferred elections cannot start on the report day or gain a fictitious end."""
        for mutation in ("start", "end", "precision"):
            source = json.loads(integrity.TERM_1982.read_text())
            if mutation == "start":
                spell = next(s for s in source["positions"] if s["membership"]["start"] == "1983-02-01")
                spell["membership"]["start"] = "1983-01-31"
            elif mutation == "end":
                spell = next(s for s in source["positions"] if s["end_review"]["method"] == "unknown")
                spell["membership"]["end"] = "1985-10"
            else:
                spell = next(s for s in source["positions"] if s["end_review"]["method"] == "event_year")
                spell["membership"]["end"] = "1985-10"
            with self.changed_source(source, integrity.TERM_1982.name), self.assertRaises(AssertionError):
                self.gates.test_reviewed_term_dates_follow_their_stated_source_basis()
