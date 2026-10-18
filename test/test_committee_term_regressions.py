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

    def changed_source(self, source, filename=None):
        original = Path.read_text
        def read(path, *args, **kwargs):
            return json.dumps(source) if path.name == (filename or integrity.SOURCE.name) else original(path, *args, **kwargs)
        return patch.object(Path, "read_text", read)

    def test_allgulander_leave_cover_ends_before_nilsson_returns(self):
        """Guarantee: Nilsson's 15 March return cannot become Allgulander's last service day."""
        source = json.loads(integrity.EXTENSION.read_text())
        spell = next(s for s in source["spells"] if s.get("resolved_position_id") == "5b51c5e260b59b2477fe6c83")
        spell["membership"]["end"] = "1982-03-15"
        with self.changed_source(source, integrity.EXTENSION.name), self.assertRaises(AssertionError):
            self.gates.test_reviewed_term_dates_follow_their_stated_source_basis()

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
