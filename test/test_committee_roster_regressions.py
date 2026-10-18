"""Deliberate mutations for reviewed election mandate and party support."""

import unittest
from unittest.mock import patch

import polars as pl

from . import committee_roster_integrity as integrity


class RosterGateRegressions(unittest.TestCase):
    def setUp(self):
        self.gates = integrity.CommitteeRosterIntegrity()

    def test_election_day_gate_rejects_an_earlier_ended_mandate(self):
        """Guarantee: changing a mandate to end before the source day turns the gate red."""
        source = pl.DataFrame({"claim_id": ["c"], "person_id": ["p"],
            "observed_start": ["1988-10-11"], "observed_end": ["1988-10-11"]})
        mandates = pl.DataFrame({"person_id": ["p"], "start": ["1988"], "end": ["1989"], "role": ["ledamot"]})
        with patch.object(integrity.pl, "read_json", return_value=source), \
             patch.object(integrity.pl, "read_csv", return_value=mandates):
            self.gates.test_reviewed_election_identities_have_contemporary_mandates()
        mandates = mandates.with_columns(pl.lit("1988-10-10").alias("end"))
        with patch.object(integrity.pl, "read_json", return_value=source), \
             patch.object(integrity.pl, "read_csv", return_value=mandates), \
             self.assertRaisesRegex(AssertionError, "1 recovered election identities"):
            self.gates.test_reviewed_election_identities_have_contemporary_mandates()

    def test_party_identity_gate_rejects_lost_dated_evidence(self):
        """Guarantee: removing the party date used for disambiguation turns the gate red."""
        source = pl.DataFrame({"claim_id": ["c"], "person_id": ["p"], "party_required": [True],
            "party": ["party"], "observed_start": ["1985"], "observed_end": ["1985"]})
        parties = pl.DataFrame({"person_id": ["p"], "party": ["party"], "start": ["1982"], "end": ["1988"]})
        with patch.object(integrity.pl, "read_json", return_value=source), \
             patch.object(integrity.pl, "read_csv", return_value=parties):
            self.gates.test_party_disambiguated_election_identities_retain_dated_party_evidence()
        parties = parties.with_columns(pl.lit(None, dtype=pl.String).alias("start"))
        with patch.object(integrity.pl, "read_json", return_value=source), \
             patch.object(integrity.pl, "read_csv", return_value=parties), \
             self.assertRaisesRegex(AssertionError, "1 election identities"):
            self.gates.test_party_disambiguated_election_identities_retain_dated_party_evidence()

if __name__ == "__main__":
    unittest.main()
