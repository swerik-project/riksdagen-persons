"""Small synthetic regressions for partial dates and committee integrity gates.

These exercise the real corpus checks with changed input tables in memory;
they never mutate published CSVs or depend on Git, network access or siblings.
"""

from datetime import date
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import polars as pl

from . import committee_integrity as integrity


class PartialDateBounds(unittest.TestCase):
    def test_year_bounds(self):
        """Guarantee: a year represents its full calendar interval for comparison."""
        rows = pl.DataFrame({"value": ["1918"]}).select(
            integrity.date_bound("value").alias("first"),
            integrity.date_bound("value", latest=True).alias("last"))
        self.assertEqual([(date(1918, 1, 1), date(1918, 12, 31))], rows.rows())

    def test_month_bounds_observe_leap_years(self):
        """Guarantee: month upper bounds use the correct last calendar day."""
        rows = pl.DataFrame({"value": ["1900-02", "1918-02", "1920-02", "2000-02"]}).select(
            integrity.date_bound("value", latest=True))
        self.assertEqual([date(1900, 2, 28), date(1918, 2, 28), date(1920, 2, 29), date(2000, 2, 29)],
                         rows.to_series().to_list())

    def test_exact_date_is_unchanged(self):
        """Guarantee: an exact date has identical earliest and latest bounds."""
        rows = pl.DataFrame({"value": ["1918-01-21"]}).select(
            integrity.date_bound("value").alias("first"),
            integrity.date_bound("value", latest=True).alias("last"))
        self.assertEqual([(date(1918, 1, 21), date(1918, 1, 21))], rows.rows())

    def test_unknown_is_not_infinite(self):
        """Guarantee: a missing date stays null at both comparison boundaries."""
        rows = pl.DataFrame({"value": [None]}, schema={"value": pl.String}).select(
            integrity.date_bound("value").alias("first"),
            integrity.date_bound("value", latest=True).alias("last"))
        self.assertEqual([(None, None)], rows.rows())

    def test_impossible_dates_are_not_normalized(self):
        """Guarantee: invalid dates are not silently shifted into a valid month."""
        rows = pl.DataFrame({"value": ["1918-02-29", "1918-04-31", "1918-13"]}).select(
            integrity.date_bound("value").alias("first"),
            integrity.date_bound("value", latest=True).alias("last"))
        self.assertEqual([(None, None)] * 3, rows.rows())


class CommitteeGateRegressions(unittest.TestCase):
    def setUp(self):
        self.tables = {
            "committee_membership.csv": pl.DataFrame({
                "person_id": ["person"], "committee_id": ["committee"],
                "start": ["1912"], "end": ["1925"], "committee_role_id": ["member"],
            }),
            "committee.csv": pl.DataFrame({
                "committee_id": ["committee"], "committee": ["KU"],
                "inception": ["1809-05"], "dissolution": ["1970"],
            }),
            "person.csv": pl.DataFrame({
                "person_id": ["person"], "born": ["1859-10-14"], "dead": ["1947-07-30"],
            }),
            "committee_abbreviation.csv": pl.DataFrame({
                "committee_id": ["committee"], "abbreviation": ["KU"],
                "start": ["1912"], "end": ["1925"], "primary_abbreviation": [True],
            }),
        }
        reader = patch.object(integrity.pl, "read_csv",
                              side_effect=lambda path, **kwargs: self.tables[Path(path).name].clone())
        reader.start()
        self.addCleanup(reader.stop)
        self.gates = integrity.CommitteeIntegrity()

    def test_calendar_gate_rejects_impossible_membership_day(self):
        """Guarantee: the calendar gate rejects an impossible membership day."""
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit("1918-02-30").alias("start"))
        with self.assertRaisesRegex(AssertionError, "1 impossible calendar date"):
            self.gates.test_committee_dates_are_possible_calendar_dates()

    def test_calendar_gate_rejects_impossible_committee_month(self):
        """Guarantee: the calendar gate covers committee lifetime dates."""
        self.tables["committee.csv"] = self.tables["committee.csv"].with_columns(
            pl.lit("1809-13").alias("inception"))
        with self.assertRaisesRegex(AssertionError, "1 impossible calendar date"):
            self.gates.test_committee_dates_are_possible_calendar_dates()

    def test_calendar_gate_rejects_impossible_abbreviation_day(self):
        """Guarantee: the calendar gate covers abbreviation dates."""
        self.tables["committee_abbreviation.csv"] = self.tables["committee_abbreviation.csv"].with_columns(
            pl.lit("1918-02-29").alias("end"))
        with self.assertRaisesRegex(AssertionError, "1 impossible calendar date"):
            self.gates.test_committee_dates_are_possible_calendar_dates()

    def test_calendar_gate_allows_unknown_dates(self):
        """Guarantee: an unknown boundary is not an invalid calendar date."""
        self.tables["committee.csv"] = self.tables["committee.csv"].with_columns(
            pl.lit(None, dtype=pl.String).alias("inception"))
        self.gates.test_committee_dates_are_possible_calendar_dates()

    def test_chronology_gate_rejects_inverted_membership(self):
        """Guarantee: a definitely inverted membership fails the chronology gate."""
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit("1926").alias("start"))
        with self.assertRaisesRegex(AssertionError, "1 definitely inverted committee period"):
            self.gates.test_committee_periods_are_not_definitely_inverted()

    def test_chronology_gate_rejects_inverted_committee_lifetime(self):
        """Guarantee: the chronology gate covers committee lifetimes."""
        self.tables["committee.csv"] = self.tables["committee.csv"].with_columns(
            pl.lit("1808").alias("dissolution"))
        with self.assertRaisesRegex(AssertionError, "1 definitely inverted committee period"):
            self.gates.test_committee_periods_are_not_definitely_inverted()

    def test_chronology_gate_rejects_inverted_abbreviation(self):
        """Guarantee: the chronology gate covers abbreviation periods."""
        self.tables["committee_abbreviation.csv"] = self.tables["committee_abbreviation.csv"].with_columns(
            pl.lit("1911").alias("end"))
        with self.assertRaisesRegex(AssertionError, "1 definitely inverted committee period"):
            self.gates.test_committee_periods_are_not_definitely_inverted()

    def test_chronology_gate_accepts_overlapping_partial_bounds(self):
        """Guarantee: a month-only end is not treated as the first of that month."""
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit("1920-02-29").alias("start"), pl.lit("1920-02").alias("end"))
        self.gates.test_committee_periods_are_not_definitely_inverted()

    def test_chronology_gate_accepts_same_day(self):
        """Guarantee: same-day start and end are not an inverted period."""
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit("1918-01-21").alias("start"), pl.lit("1918-01-21").alias("end"))
        self.gates.test_committee_periods_are_not_definitely_inverted()

    def test_inception_gate_counts_memberships_not_endpoints(self):
        """Guarantee: two early boundaries in one membership count as one failure."""
        self.tables["committee.csv"] = self.tables["committee.csv"].with_columns(
            pl.lit("1926").alias("inception"))
        with self.assertRaisesRegex(AssertionError, "1 memberships predate"):
            self.gates.test_memberships_do_not_predate_committee_inception()

    def test_inception_gate_checks_end_when_start_unknown(self):
        """Guarantee: an unknown start does not hide an end before inception."""
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit(None, dtype=pl.String).alias("start"), pl.lit("1808").alias("end"))
        with self.assertRaisesRegex(AssertionError, "1 memberships predate"):
            self.gates.test_memberships_do_not_predate_committee_inception()

    def test_inception_gate_accepts_partial_boundary_overlap(self):
        """Guarantee: membership may start within a year-only inception interval."""
        self.tables["committee.csv"] = self.tables["committee.csv"].with_columns(
            pl.lit("1912-12").alias("inception"))
        self.gates.test_memberships_do_not_predate_committee_inception()

    def test_inception_gate_allows_unknown_inception(self):
        """Guarantee: an unknown inception does not impose an invented boundary."""
        self.tables["committee.csv"] = self.tables["committee.csv"].with_columns(
            pl.lit(None, dtype=pl.String).alias("inception"))
        self.gates.test_memberships_do_not_predate_committee_inception()

    def test_dissolution_gate_rejects_late_end(self):
        """Guarantee: a membership ending after known dissolution fails."""
        self.tables["committee.csv"] = self.tables["committee.csv"].with_columns(
            pl.lit("1924").alias("dissolution"))
        with self.assertRaisesRegex(AssertionError, "1 memberships outlast"):
            self.gates.test_memberships_do_not_outlast_committee_dissolution()

    def test_dissolution_gate_checks_start_when_end_unknown(self):
        """Guarantee: an unknown end does not hide a start after dissolution."""
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit("1971").alias("start"), pl.lit(None, dtype=pl.String).alias("end"))
        with self.assertRaisesRegex(AssertionError, "1 memberships outlast"):
            self.gates.test_memberships_do_not_outlast_committee_dissolution()

    def test_dissolution_gate_does_not_treat_unknown_end_as_infinite(self):
        """Guarantee: unknown membership end does not contradict known dissolution."""
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit(None, dtype=pl.String).alias("end"))
        self.gates.test_memberships_do_not_outlast_committee_dissolution()

    def test_dissolution_gate_accepts_last_day_of_coarse_year(self):
        """Guarantee: year-only dissolution permits a boundary on December 31."""
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit("1970-12-31").alias("end"))
        self.gates.test_memberships_do_not_outlast_committee_dissolution()

    def test_lifetime_gate_rejects_start_before_birth(self):
        """Guarantee: a membership start definitely before birth is rejected."""
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit("1858").alias("start"))
        with self.assertRaisesRegex(AssertionError, "1 membership starts outside"):
            self.gates.test_membership_starts_are_not_outside_person_lifetimes()

    def test_lifetime_gate_rejects_start_after_death(self):
        """Guarantee: a membership start definitely after death is rejected."""
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit("1948").alias("start"))
        with self.assertRaisesRegex(AssertionError, "1 membership starts outside"):
            self.gates.test_membership_starts_are_not_outside_person_lifetimes()

    def test_lifetime_gate_accepts_death_within_start_year(self):
        """Guarantee: a partial start overlapping the death date is not rejected."""
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit("1947").alias("start"))
        self.gates.test_membership_starts_are_not_outside_person_lifetimes()

    def test_lifetime_gate_checks_birth_when_death_unknown(self):
        """Guarantee: unknown death does not hide a definitely pre-birth start."""
        self.tables["person.csv"] = self.tables["person.csv"].with_columns(
            pl.lit(None, dtype=pl.String).alias("dead"))
        self.tables["committee_membership.csv"] = self.tables["committee_membership.csv"].with_columns(
            pl.lit("1858").alias("start"))
        with self.assertRaisesRegex(AssertionError, "1 membership starts outside"):
            self.gates.test_membership_starts_are_not_outside_person_lifetimes()

    def test_primary_abbreviation_gate_retains_month_boundary_overlap(self):
        """Guarantee: the shared bounds helper preserves definite overlap detection."""
        self.tables["committee_abbreviation.csv"] = pl.DataFrame({
            "committee_id": ["committee", "committee"], "abbreviation": ["KU", "K"],
            "start": ["1918-02", "1918-02-28"], "end": ["1918-03", "1918-03-01"],
            "primary_abbreviation": [True, True],
        })
        with self.assertRaisesRegex(AssertionError, "1 definitely overlapping primary pairs"):
            self.gates.test_primary_abbreviation_periods_do_not_definitely_overlap()


class ReviewedMembershipRegressions(unittest.TestCase):
    def setUp(self):
        self.membership = {"person_id": "person", "committee_id": "committee", "start": None,
                           "end": None, "committee_role_id": "member"}
        self.rows = pl.DataFrame([self.membership], schema={key: pl.String for key in self.membership})
        self.source = {"election_evidence_id": "election", "election_date": "1918-01-21",
                       "election_source_url": "https://example.org/protocol", "person_id": "person",
                       "committee_id": "committee", "role": "Ledamot", "parliament_year": "1918",
                       "session": "regular", "chamber": "FK", "register_source_url": "https://example.org/register#page=3",
                       "register_printed_page": 1, "register_excerpt": "Ledamot i konstitutionsutskottet.",
                       "review_status": "source_supported", "identity_status": "resolved_by_agent"}
        self.claim = {"batch": "2026-10-16-ku1918-undated", "membership": dict(self.membership),
                      **{key: self.source[key] for key in ("election_evidence_id", "election_date", "election_source_url",
                         "role", "parliament_year", "session", "chamber", "register_source_url",
                         "register_printed_page", "register_excerpt")}}
        self.claims = [self.claim]
        fixture = patch.object(integrity.Path, "read_text", autospec=True, side_effect=lambda path:
                               json.dumps(self.claims if path.name == "reviewed_committee_memberships.json" else [self.source]))
        fixture.start()
        self.addCleanup(fixture.stop)
        csv_reader = patch.object(integrity.pl, "read_csv", side_effect=lambda path, **kwargs:
                                 self.rows.clone() if Path(path).name == "committee_membership.csv" else
                                 pl.DataFrame({"role": ["Ledamot"], "committee_role_id": ["member"]}))
        csv_reader.start()
        self.addCleanup(csv_reader.stop)
        self.gates = integrity.CommitteeIntegrity()

    def test_reviewed_guard_accepts_null_service_boundaries(self):
        """Guarantee: an undated source-supported membership passes the curation guard."""
        self.gates.test_reviewed_memberships_keep_source_dates_and_roles()

    def test_reviewed_guard_rejects_missing_undated_membership(self):
        """Guarantee: removing an undated curated row fails with an actionable assertion."""
        self.rows = self.rows.clear()
        with self.assertRaisesRegex(AssertionError, "1 reviewed memberships missing or altered"):
            self.gates.test_reviewed_memberships_keep_source_dates_and_roles()

    def test_reviewed_guard_rejects_election_date_as_service_start(self):
        """Guarantee: an election date cannot silently replace a curated unknown start."""
        self.rows = self.rows.with_columns(pl.lit("1918-01-21").alias("start"))
        with self.assertRaisesRegex(AssertionError, "1 reviewed memberships missing or altered"):
            self.gates.test_reviewed_memberships_keep_source_dates_and_roles()

    def test_reviewed_guard_rejects_invented_service_end(self):
        """Guarantee: a session year cannot silently replace a curated unknown end."""
        self.rows = self.rows.with_columns(pl.lit("1918").alias("end"))
        with self.assertRaisesRegex(AssertionError, "1 reviewed memberships missing or altered"):
            self.gates.test_reviewed_memberships_keep_source_dates_and_roles()

    def test_reviewed_guard_rejects_changed_role(self):
        """Guarantee: a curated ordinary member cannot silently become a substitute."""
        self.rows = self.rows.with_columns(pl.lit("substitute").alias("committee_role_id"))
        with self.assertRaisesRegex(AssertionError, "1 reviewed memberships missing or altered"):
            self.gates.test_reviewed_memberships_keep_source_dates_and_roles()

    def test_source_guard_accepts_resolved_election_and_register(self):
        """Guarantee: consistent identity, election and register citations pass."""
        self.gates.test_ku1918_curations_match_resolved_election_evidence()

    def test_source_guard_rejects_missing_fixture(self):
        """Guarantee: deleting a curated fixture cannot silently remove its protection."""
        self.claims.clear()
        with self.assertRaisesRegex(AssertionError, "1 KU election curations lack matching"):
            self.gates.test_ku1918_curations_match_resolved_election_evidence()

    def test_source_guard_rejects_duplicate_fixture(self):
        """Guarantee: each curated election has exactly one fixture."""
        self.claims.append(dict(self.claim))
        with self.assertRaisesRegex(AssertionError, "1 KU election curations lack matching"):
            self.gates.test_ku1918_curations_match_resolved_election_evidence()

    def test_source_guard_rejects_wrong_register_citation(self):
        """Guarantee: a register citation cannot point to an unrelated source."""
        self.claim["register_source_url"] = "https://example.org/unrelated"
        with self.assertRaisesRegex(AssertionError, "1 KU election curations lack matching"):
            self.gates.test_ku1918_curations_match_resolved_election_evidence()

    def test_source_guard_rejects_wrong_election_date(self):
        """Guarantee: a dated election observation retains its source date."""
        self.claim["election_date"] = "1918-02-01"
        with self.assertRaisesRegex(AssertionError, "1 KU election curations lack matching"):
            self.gates.test_ku1918_curations_match_resolved_election_evidence()

    def test_source_guard_rejects_wrong_person(self):
        """Guarantee: a curation cannot be assigned to a different resolved person."""
        self.claim["membership"]["person_id"] = "other"
        with self.assertRaisesRegex(AssertionError, "1 KU election curations lack matching"):
            self.gates.test_ku1918_curations_match_resolved_election_evidence()

    def test_source_guard_rejects_conflicting_evidence(self):
        """Guarantee: a source conflict cannot become an accepted undated membership."""
        self.source["review_status"] = "source_conflict"
        with self.assertRaisesRegex(AssertionError, "1 KU election curations lack matching"):
            self.gates.test_ku1918_curations_match_resolved_election_evidence()


class SBLProvenanceRegressions(unittest.TestCase):
    def setUp(self):
        membership = dict(person_id="person", committee_id="committee", start="1910", end=None, committee_role_id="member")
        self.source = dict(membership, claim_id="claim", batch="2026-10-16-sbl", sbl_id="123",
                           source_url="https://example.org/sbl/123", source_clause="led av KU från 10")
        self.claim = {"membership": dict(membership), "service_source": {
            "batch": "2026-10-16-sbl", "claim_id": "claim", "sbl_id": "123", "url": self.source["source_url"],
            "excerpt": self.source["source_clause"]}}
        self.claims = [self.claim]
        self.links = pl.DataFrame(dict(person_id=["person"], identifier=["123"]))
        self.identifiers = pl.DataFrame(dict(person_id=["person"], authority=["DiSweNaBiID"], identifier=["123"]))
        reader = patch.object(integrity.Path, "read_text", autospec=True,
                              side_effect=lambda path, **kwargs: json.dumps(self.claims))
        reader.start()
        self.addCleanup(reader.stop)
        csv_reader = patch.object(integrity.pl, "read_csv", side_effect=lambda path, **kwargs:
                                 pl.DataFrame([self.source], schema={key: pl.String for key in self.source})
                                 if Path(path).name == "reviewed_sbl_committee_sources.csv" else
                                 self.links.clone() if Path(path).name == "reviewed_sbl_links.csv" else self.identifiers.clone())
        csv_reader.start()
        self.addCleanup(csv_reader.stop)
        self.gates = integrity.CommitteeIntegrity()

    def test_source_guard_accepts_matching_curation(self):
        """Guarantee: a consistent SBL source, fixture and excerpt pass provenance."""
        self.gates.test_sbl_curations_retain_reviewed_source_claims()

    def test_source_guard_rejects_deleted_fixture(self):
        """Guarantee: deleting a fixture cannot delete protection for an SBL claim."""
        self.claims.clear()
        with self.assertRaisesRegex(AssertionError, "1 SBL curations lack"):
            self.gates.test_sbl_curations_retain_reviewed_source_claims()

    def test_source_guard_rejects_invented_end(self):
        """Guarantee: a fixture cannot invent an end absent from the SBL claim."""
        self.claim["membership"]["end"] = "1940"
        with self.assertRaisesRegex(AssertionError, "1 SBL curations lack"):
            self.gates.test_sbl_curations_retain_reviewed_source_claims()

    def test_source_guard_rejects_wrong_biography(self):
        """Guarantee: an SBL curation cannot cite a different biography."""
        self.claim["service_source"]["sbl_id"] = "456"
        with self.assertRaisesRegex(AssertionError, "1 SBL curations lack"):
            self.gates.test_sbl_curations_retain_reviewed_source_claims()

    def test_source_guard_rejects_changed_excerpt(self):
        """Guarantee: the citation retains the reviewed source clause."""
        self.claim["service_source"]["excerpt"] = "unrelated career"
        with self.assertRaisesRegex(AssertionError, "1 SBL curations lack"):
            self.gates.test_sbl_curations_retain_reviewed_source_claims()

    def test_source_guard_rejects_duplicate_fixture(self):
        """Guarantee: an SBL source claim has exactly one curation fixture."""
        self.claims.append(self.claim)
        with self.assertRaisesRegex(AssertionError, "1 SBL curations lack"):
            self.gates.test_sbl_curations_retain_reviewed_source_claims()

    def test_identifier_guard_accepts_existing_link(self):
        """Guarantee: the reviewed person/article identifier passes when retained."""
        self.gates.test_sbl_linked_mps_retain_source_identifiers()

    def test_identifier_guard_rejects_removed_link(self):
        """Guarantee: removal of a reviewed SBL link fails the identifier gate."""
        self.identifiers = self.identifiers.clear()
        with self.assertRaisesRegex(AssertionError, "1 SBL person/article links missing"):
            self.gates.test_sbl_linked_mps_retain_source_identifiers()

    def test_followup_source_guard_protects_new_batch(self):
        """Guarantee: resolved-batch dates receive the same protection as first-pass facts."""
        self.source["batch"] = "2026-10-16-sbl-resolved"
        self.claim["service_source"]["batch"] = "2026-10-16-sbl-resolved"
        self.gates.test_sbl_curations_retain_reviewed_source_claims()
        self.claim["membership"]["start"] = "1909"
        with self.assertRaisesRegex(AssertionError, "1 SBL curations lack"):
            self.gates.test_sbl_curations_retain_reviewed_source_claims()


class ReviewedLifetimeRegressions(unittest.TestCase):
    def test_corrected_death_and_its_source_are_protected(self):
        """Guarantee: reverting a reviewed death or citing the wrong article fails."""
        correction = dict(person_id="p", field="dead", after="1959-11-22", sbl_id="1",
                          source_url="https://sok.riksarkivet.se/sbl/Presentation.aspx?id=1", source_clause="d 22 nov 1959")
        table = pl.DataFrame(dict(person_id=["p"], dead=["1959-11-22"]))
        links = pl.DataFrame(dict(person_id=["p"], authority=["DiSweNaBiID"], identifier=["1"]))
        with patch.object(integrity.Path, "read_text", autospec=True,
                          side_effect=lambda path: json.dumps([correction])), \
                patch.object(integrity.pl, "read_csv", side_effect=lambda path, **kwargs:
                             table if Path(path).name == "person.csv" else links):
            gate = integrity.CommitteeIntegrity().test_sbl_reviewed_lifetime_corrections_retain_source_dates
            gate()
            table = table.with_columns(pl.lit("1859-10-22").alias("dead"))
            with self.assertRaisesRegex(AssertionError, "1 SBL lifetime corrections altered"):
                gate()
            table = table.with_columns(pl.lit("1959-11-22").alias("dead"))
            correction["source_url"] = "https://example.org/wrong"
            with self.assertRaisesRegex(AssertionError, "1 SBL lifetime corrections altered"):
                gate()


if __name__ == "__main__":
    unittest.main()
