"""Deliberate mutations for the tracked committee identity/correction fixtures."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

import polars as pl

from . import committee_roster_integrity as integrity
from . import committee_session_integrity as sessions


class RosterGateRegressions(unittest.TestCase):
    def setUp(self):
        self.row = dict(person_id="p", committee_id="c", start=None, end=None, committee_role_id="member")
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

    def test_honorific_identity_gate_rejects_changed_gender(self):
        """Guarantee: a selected identity contradicting a printed honorific turns the gate red."""
        source = pl.DataFrame({"claim_id": ["c"], "person_id": ["p"], "gender": ["woman"]})
        persons = pl.DataFrame({"person_id": ["p"], "gender": ["woman"]})
        with patch.object(integrity.pl, "read_json", return_value=source), \
             patch.object(integrity.pl, "read_csv", return_value=persons):
            self.gates.test_reviewed_election_identities_retain_printed_gender_agreement()
        persons = persons.with_columns(pl.lit("man").alias("gender"))
        with patch.object(integrity.pl, "read_json", return_value=source), \
             patch.object(integrity.pl, "read_csv", return_value=persons), \
             self.assertRaisesRegex(AssertionError, "1 election identities"):
            self.gates.test_reviewed_election_identities_retain_printed_gender_agreement()

    def test_correction_gate_rejects_reintroduced_membership(self):
        """Guarantee: restoring a scan-disproved undated membership turns the gate red."""
        correction = {"membership": self.row, "claim_id": "false-claim",
                      "scan_url": "https://example.org/scan", "reason": "Displaced name"}
        empty = pl.DataFrame(schema={k: pl.String for k in self.row})
        for memberships, invalid in ((empty, False), (pl.DataFrame([self.row]), True)):
            with patch.object(integrity.Path, "read_text", return_value=json.dumps([correction])), \
                 patch.object(integrity.pl, "read_csv", return_value=memberships):
                if invalid:
                    with self.assertRaisesRegex(AssertionError, "1 scan-disproved roster facts"):
                        self.gates.test_scan_corrected_false_memberships_are_not_reintroduced()
                else:
                    self.gates.test_scan_corrected_false_memberships_are_not_reintroduced()

    def check_session(self, name, year="1921", chamber="AK"):
        reference = [{"entity": {"committee_id": "c"}, "source": {"year": year, "chamber": chamber}}]
        committees = pl.DataFrame({"committee_id": ["c"], "committee": [name]})
        with patch.object(sessions.Path, "read_text", return_value=json.dumps(reference)), \
             patch.object(sessions.pl, "read_csv", return_value=committees):
            sessions.CommitteeSessionIntegrity().test_session_scoped_rosters_match_committee_year_and_chamber()

    def test_session_gate_rejects_evidence_from_another_year(self):
        """Guarantee: a reviewed source cannot move an annual body to another year."""
        name = "Andra kammarens tillfälliga utskott nr 1 (1921 lagtima)"
        self.check_session(name)
        with self.assertRaisesRegex(AssertionError, "1 entity citations"):
            self.check_session(name, year="1922")

    def test_nineteenth_century_split_session_gate_rejects_wrong_year_and_chamber(self):
        """Guarantee: nineteenth-century and split-session bodies keep their reviewed context."""
        name = "Första kammarens tillfälliga utskott nr 1 (1887 lagtima B)"
        self.check_session(name, year="1887", chamber="FK")
        for year, chamber in (("1888", "FK"), ("1887", "AK")):
            with self.assertRaisesRegex(AssertionError, "1 entity citations"):
                self.check_session(name, year=year, chamber=chamber)

    def test_session_gate_rejects_evidence_from_another_chamber(self):
        """Guarantee: an AK source cannot support an FK temporary committee identity."""
        name = "Första kammarens tillfälliga utskott nr 1 (1921 lagtima)"
        self.check_session(name, chamber="FK")
        with self.assertRaisesRegex(AssertionError, "1 entity citations"):
            self.check_session(name)

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

    def test_entity_gate_rejects_merging_1964_special_committees(self):
        """Guarantee: the spring and autumn 1964 special committees remain distinct bodies."""
        entities = [{"committee_id": f"c{n}", "committee": f"Särskilda utskottet nr {n} (1964)",
                     "committee_type": "special", "inception": None, "dissolution": None} for n in (1, 2)]
        fixture = [{"entity": e, "source": {"url": "https://example.org/1964-register"}} for e in entities]
        wrong = [entities[0], dict(entities[1], committee=entities[0]["committee"])]
        with patch.object(integrity.pl, "read_csv", return_value=pl.DataFrame(wrong)), \
             patch.object(integrity.Path, "read_text", return_value=json.dumps(fixture)), \
             self.assertRaisesRegex(AssertionError, "1 historical committee identities"):
            self.gates.test_reviewed_historical_committee_identities_remain_distinct()


if __name__ == "__main__":
    unittest.main()
