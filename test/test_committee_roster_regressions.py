"""Deliberate evidence and identity mutations for the roster integrity gates."""

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import polars as pl

from . import committee_roster_integrity as integrity
from . import committee_session_integrity as sessions


class RosterGateRegressions(unittest.TestCase):
    def test_identity_source_gate_rejects_changed_person_date_url_and_orphan(self):
        """Guarantee: changing identity evidence without its published claim turns the gate red."""
        identity = pl.DataFrame({"claim_id": ["c"], "person_id": ["p"], "url": ["source"],
            "observed_start": ["1985-10-08"], "observed_end": ["1985-10-08"]})
        source = pl.DataFrame({"claim_id": ["c"], "person_id": ["p"], "url": ["source"],
            "event_date": ["1985-10-08"], "year": ["1985"]})
        with patch.object(integrity.pl, "read_json", return_value=identity), \
             patch.object(integrity.pl, "read_csv", return_value=source):
            self.gates.test_reviewed_election_identities_retain_published_source_links()
        year_only_source = source.with_columns(pl.lit(None, dtype=pl.String).alias("event_date"))
        with patch.object(integrity.pl, "read_json", return_value=identity), \
             patch.object(integrity.pl, "read_csv", return_value=year_only_source):
            self.gates.test_reviewed_election_identities_retain_published_source_links()
        with patch.object(integrity.pl, "read_json", return_value=identity), \
             patch.object(integrity.pl, "read_csv", return_value=year_only_source.with_columns(
                 pl.lit("1986").alias("year"))), \
             self.assertRaisesRegex(AssertionError, "election identity source links inconsistent"):
            self.gates.test_reviewed_election_identities_retain_published_source_links()
        for changed in (identity.with_columns(pl.lit("other").alias("person_id")),
                        identity.with_columns(pl.lit("other").alias("url")),
                        identity.with_columns(pl.lit("1985").alias("observed_start")),
                        identity.with_columns(pl.lit("other").alias("claim_id")),
                        pl.concat([identity, identity])):
            with patch.object(integrity.pl, "read_json", return_value=changed), \
                 patch.object(integrity.pl, "read_csv", return_value=source), \
                 self.assertRaisesRegex(AssertionError, "election identity source links inconsistent"):
                self.gates.test_reviewed_election_identities_retain_published_source_links()

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

    def setUp(self):
        self.row = {"person_id": "p", "committee_id": "c", "start": None, "end": None, "committee_role_id": "member"}
        self.observation = {"claim_id": "1950:p1:1", "year": 1950, "chamber": "AK", "url": "https://example.org/register",
                            "excerpt": "Ledamot i statsutskottet", "source_header": "Example, LAK",
                            "source_sha256": "source-hash", "source_kind": "annual_register", "event_date": None}
        self.curation = {"batch": integrity.BATCH, "membership": self.row,
                         "roster_observations": [copy.deepcopy(self.observation)]}
        self.sources = pl.DataFrame([{**self.row, **self.observation}]).with_columns(
            pl.col("year", "event_date").cast(pl.String))
        self.gates = integrity.CommitteeRosterIntegrity()


    def test_exact_day_gate_rejects_wrong_service_spell_and_source_year(self):
        """Guarantee: an election day cannot support an earlier spell or a different year."""
        sources = self.sources.with_columns(pl.lit("1950-10-10").alias("event_date"),
            pl.lit("1950-10-01").alias("start"), pl.lit("1951").alias("end"))
        with patch.object(integrity.pl, "read_csv", return_value=sources):
            self.gates.test_dated_roster_observations_fit_their_assigned_service_spells()
        for changed in (sources.with_columns(pl.lit("1950-10-09").alias("end")),
                        sources.with_columns(pl.lit("1951").alias("year"))):
            with patch.object(integrity.pl, "read_csv", return_value=changed), \
                 self.assertRaisesRegex(AssertionError, "1 dated roster claims"):
                self.gates.test_dated_roster_observations_fit_their_assigned_service_spells()

    def test_correction_gate_rejects_reintroduced_fact_or_claim(self):
        """Guarantee: restoring either a scan-disproved fact or its false claim turns the gate red."""
        correction = {"membership": self.row, "claim_id": self.observation["claim_id"],
                      "scan_url": "https://example.org/scan", "reason": "Displaced name"}
        empty_memberships = pl.DataFrame(schema={k: pl.String for k in self.row})
        empty_sources = pl.DataFrame(schema={"claim_id": pl.String})
        for memberships, sources, invalid in ((empty_memberships, empty_sources, False),
                (pl.DataFrame([self.row]), empty_sources, True), (empty_memberships, self.sources, True)):
            with patch.object(integrity.Path, "read_text", return_value=json.dumps([correction])), \
                 patch.object(integrity.pl, "read_csv", side_effect=[memberships, sources]):
                if invalid:
                    with self.assertRaisesRegex(AssertionError, "1 scan-disproved roster facts"):
                        self.gates.test_scan_corrected_false_memberships_are_not_reintroduced()
                else:
                    self.gates.test_scan_corrected_false_memberships_are_not_reintroduced()

    def check_session(self, name, year="1921", chamber="AK"):
        sources = self.sources.with_columns(pl.lit(year).alias("year"), pl.lit(chamber).alias("chamber"))
        tables = {"committee.csv": pl.DataFrame({"committee_id": ["c"], "committee": [name]}),
                  "observations.csv": sources}
        with patch.object(sessions.pl, "read_csv", side_effect=lambda p, **kw: tables[Path(p).name]):
            sessions.CommitteeSessionIntegrity().test_session_scoped_rosters_match_committee_year_and_chamber()

    def test_session_gate_rejects_evidence_from_another_year(self):
        """Guarantee: internally consistent citations cannot move an annual body to another year."""
        name = "Andra kammarens tillfälliga utskott nr 1 (1921 lagtima)"
        self.check_session(name)
        with self.assertRaisesRegex(AssertionError, "1 roster observations"):
            self.check_session(name, year="1922")

    def test_nineteenth_century_split_session_gate_rejects_wrong_year_and_chamber(self):
        """Guarantee: nineteenth-century and split-session bodies receive the same semantic checks."""
        name = "Första kammarens tillfälliga utskott nr 1 (1887 lagtima B)"
        self.check_session(name, year="1887", chamber="FK")
        for year, chamber in (("1888", "FK"), ("1887", "AK")):
            with self.assertRaisesRegex(AssertionError, "1 roster observations"):
                self.check_session(name, year=year, chamber=chamber)

    def test_session_gate_rejects_evidence_from_another_chamber(self):
        """Guarantee: an AK citation cannot attach to an FK temporary committee."""
        name = "Första kammarens tillfälliga utskott nr 1 (1921 lagtima)"
        self.check_session(name, chamber="FK")
        with self.assertRaisesRegex(AssertionError, "1 roster observations"):
            self.check_session(name)


    def test_chamber_gate_rejects_other_chamber(self):
        """Guarantee: a mandate in the wrong chamber cannot support a roster identity."""
        mandates = pl.DataFrame({"person_id": ["p"], "role": ["förstakammarledamot"], "start": ["1940"], "end": ["1960"]})
        tables = {"observations.csv": self.sources, "member_of_parliament.csv": mandates}
        with patch.object(integrity.pl, "read_csv", side_effect=lambda p, **kw: tables[Path(p).name]), \
             self.assertRaisesRegex(AssertionError, "1 roster observations"):
            self.gates.test_roster_observations_have_compatible_chamber_mandates()

    def test_chamber_gate_rejects_a_mandate_starting_later_in_the_same_year(self):
        """Guarantee: adding an exact day tightens every source claim's mandate check."""
        sources = self.sources.with_columns(pl.lit("1989-02-06").alias("event_date"),
            pl.lit("1989").alias("year"), pl.lit("EK").alias("chamber"))
        mandates = pl.DataFrame({"person_id": ["p"], "role": ["ledamot"],
                                 "start": ["1989-05-10"], "end": ["1991-09-30"]})
        tables = {"observations.csv": sources, "member_of_parliament.csv": mandates}
        with patch.object(integrity.pl, "read_csv", side_effect=lambda p, **kw: tables[Path(p).name]):
            with self.assertRaisesRegex(AssertionError, "1 roster observations"):
                self.gates.test_roster_observations_have_compatible_chamber_mandates()
            tables["member_of_parliament.csv"] = mandates.with_columns(pl.lit("1988").alias("start"))
            self.gates.test_roster_observations_have_compatible_chamber_mandates()

    def test_chamber_gate_accepts_unicameral_mandate(self):
        """Guarantee: EK observations use single-chamber mandates from 1971 onward."""
        self.sources = self.sources.with_columns(pl.lit("EK").alias("chamber"), pl.lit("1971").alias("year"))
        mandates = pl.DataFrame({"person_id": ["p"], "role": ["ledamot"], "start": ["1971"], "end": ["1974"]})
        tables = {"observations.csv": self.sources, "member_of_parliament.csv": mandates}
        with patch.object(integrity.pl, "read_csv", side_effect=lambda p, **kw: tables[Path(p).name]):
            self.gates.test_roster_observations_have_compatible_chamber_mandates()
            tables["member_of_parliament.csv"] = mandates.with_columns(pl.lit("andrakammarledamot").alias("role"))
            with self.assertRaisesRegex(AssertionError, "1 roster observations"):
                self.gates.test_roster_observations_have_compatible_chamber_mandates()

    def test_chamber_gate_rejects_anachronistic_unicameral_observation(self):
        """Guarantee: a single-chamber label cannot validate a pre-1971 observation."""
        self.sources = self.sources.with_columns(pl.lit("EK").alias("chamber"))
        mandates = pl.DataFrame({"person_id": ["p"], "role": ["ledamot"], "start": ["1940"], "end": ["1960"]})
        tables = {"observations.csv": self.sources, "member_of_parliament.csv": mandates}
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

    def test_canonical_observation_gate_rejects_orphans_and_duplicate_links(self):
        """Guarantee: canonical observations cannot lose their unique accepted fact."""
        from . import committee_provenance_integrity as evidence
        claims = [{"membership": self.row, "roster_observations": [self.observation["claim_id"]]}]
        published = pl.DataFrame([self.row], schema={k: pl.String for k in self.row})
        gate = evidence.CommitteeProvenanceIntegrity()
        with patch.object(evidence, "read_roster", return_value=self.sources), \
             patch.object(evidence, "read_claims", return_value=claims), \
             patch.object(evidence.pl, "read_csv", return_value=published):
            gate.test_observations_have_exactly_one_curation_and_a_published_membership()
        with patch.object(evidence, "read_roster", return_value=self.sources), \
             patch.object(evidence, "read_claims", return_value=[]), \
             patch.object(evidence.pl, "read_csv", return_value=published), \
             self.assertRaisesRegex(AssertionError, "1 observation claim IDs"):
            gate.test_observations_have_exactly_one_curation_and_a_published_membership()
        with patch.object(evidence, "read_roster", return_value=pl.concat([self.sources, self.sources])), \
             patch.object(evidence, "read_claims", return_value=claims), \
             patch.object(evidence.pl, "read_csv", return_value=published), \
             self.assertRaisesRegex(AssertionError, "1 observation claim IDs"):
            gate.test_observations_have_exactly_one_curation_and_a_published_membership()


if __name__ == "__main__":
    unittest.main()
