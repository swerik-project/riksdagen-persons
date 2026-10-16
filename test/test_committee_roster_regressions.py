"""Deliberate evidence and identity mutations for the roster integrity gates."""

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import polars as pl

from . import committee_roster_integrity as integrity


class RosterGateRegressions(unittest.TestCase):
    def setUp(self):
        self.row = {"person_id": "p", "committee_id": "c", "start": None, "end": None, "committee_role_id": "member"}
        self.observation = {"claim_id": "1950:p1:1", "year": 1950, "chamber": "AK", "url": "https://example.org/register",
                            "excerpt": "Ledamot i statsutskottet", "source_header": "Example, LAK",
                            "source_sha256": "source-hash", "source_kind": "annual_register"}
        self.curation = {"batch": integrity.BATCH, "membership": self.row,
                         "roster_observations": [copy.deepcopy(self.observation)]}
        self.sources = pl.DataFrame([{**self.row, **self.observation}]).with_columns(pl.col("year").cast(pl.String))
        self.gates = integrity.CommitteeRosterIntegrity()

    def check_sources(self):
        with patch.object(integrity.pl, "read_csv", return_value=self.sources), \
             patch.object(integrity.Path, "read_text", return_value=json.dumps([self.curation])):
            self.gates.test_roster_curations_retain_source_observations()

    def test_source_gate_passes_unchanged_evidence(self):
        """Guarantee: the source gate accepts an unchanged supported claim."""
        self.check_sources()

    def test_source_gate_rejects_lost_observation(self):
        """Guarantee: retaining the membership row does not hide a lost source year."""
        self.curation["roster_observations"] = []
        with self.assertRaisesRegex(AssertionError, "1 roster claims"):
            self.check_sources()

    def test_source_gate_rejects_changed_year(self):
        """Guarantee: an observation cannot migrate silently to another year."""
        self.curation["roster_observations"][0]["year"] = 1970
        with self.assertRaisesRegex(AssertionError, "1 roster claims"):
            self.check_sources()

    def test_source_gate_rejects_changed_quote(self):
        """Guarantee: replacing an ordinary-member quote with a substitute quote fails."""
        self.curation["roster_observations"][0]["excerpt"] = "Suppleant i statsutskottet"
        with self.assertRaisesRegex(AssertionError, "1 roster claims"):
            self.check_sources()

    def test_chamber_gate_rejects_other_chamber(self):
        """Guarantee: a mandate in the wrong chamber cannot support a roster identity."""
        mandates = pl.DataFrame({"person_id": ["p"], "role": ["förstakammarledamot"], "start": ["1940"], "end": ["1960"]})
        tables = {"reviewed_committee_roster_sources.csv": self.sources, "member_of_parliament.csv": mandates}
        with patch.object(integrity.pl, "read_csv", side_effect=lambda p, **kw: tables[Path(p).name]), \
             self.assertRaisesRegex(AssertionError, "1 roster observations"):
            self.gates.test_roster_observations_have_compatible_chamber_mandates()

    def test_entity_gate_rejects_merged_chamber_body(self):
        """Guarantee: merging a chamber preparation committee into the common body fails."""
        entity = {"committee_id": "c", "committee": "Andra kammarens allmänna beredningsutskott",
                  "committee_type": "other", "inception": None, "dissolution": None}
        wrong = dict(entity, committee="Allmänna beredningsutskottet")
        fixture = [{"entity": entity, "source": {"url": "https://example.org/register"}}]
        with patch.object(integrity.pl, "read_csv", return_value=pl.DataFrame([wrong])), \
             patch.object(integrity.Path, "read_text", return_value=json.dumps(fixture)), \
             self.assertRaisesRegex(AssertionError, "1 historical committee identities"):
            self.gates.test_reviewed_historical_committee_identities_remain_distinct()


if __name__ == "__main__":
    unittest.main()
