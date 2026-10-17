"""Intentional small mutations proving the committee-term source gates turn red."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from . import committee_term_integrity as integrity


class CommitteeTermRegressions(unittest.TestCase):
    def setUp(self):
        self.source = json.loads(integrity.SOURCE.read_text())
        self.gates = integrity.CommitteeTermIntegrity()

    def changed_source(self, source):
        original = Path.read_text
        def read(path, *args, **kwargs):
            return json.dumps(source) if path.name == integrity.SOURCE.name else original(path, *args, **kwargs)
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

    def test_deleting_a_term_fixture_does_not_remove_source_protection(self):
        """Guarantee: removing a spell fixture while its curation remains turns the source gate red."""
        self.source["spells"].pop(0)
        with self.changed_source(self.source), self.assertRaises(AssertionError):
            self.gates.test_dated_term_curations_retain_their_source_evidence()
