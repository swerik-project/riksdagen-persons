"""Semantic guarantees for committee identities, historical dates and curated rows.

CSVW owns structural types, required fields, primary keys and foreign keys.
Reviewed evidence is kept in test/data; no reference archives are required.
"""

from itertools import combinations
import json
from pathlib import Path
import unicodedata
import unittest

import polars as pl
from pyriksdagen.metadata import check_date_overlap
from trainerlog import get_logger


LOGGER = get_logger("committee-integrity")
DATA_DIR = Path("data")


def date_bound(column, latest=False):
    """Return a comparison-only bound for a partial date; preserve unknowns.

    Invalid dates produce null and are reported by the calendar-date guarantee.
    Replace with a null-preserving pyriksdagen bounds helper when available:
    increase_date_precision(..., start=False) in 1.10.2 returns None for months.
    """
    value = pl.col(column)
    first = (pl.when(value.str.len_chars() == 4).then(value + "-01-01")
             .when(value.str.len_chars() == 7).then(value + "-01")
             .otherwise(value).str.to_date("%Y-%m-%d", strict=False))
    if not latest:
        return first
    return (pl.when(value.str.len_chars() == 4)
            .then((value + "-12-31").str.to_date("%Y-%m-%d", strict=False))
            .when(value.str.len_chars() == 7).then(first.dt.month_end())
            .otherwise(first))


class CommitteeIntegrity(unittest.TestCase):
    def test_committee_dates_are_possible_calendar_dates(self):
        """Guarantee: every supplied committee date denotes a real calendar date.

        Data: committee lifetimes, membership dates and abbreviation periods.
        CSVW validates string shape, not whether e.g. 1918-02-30 exists.
        Missing dates remain unknown and are allowed; failures count date values.
        """
        failures = 0
        checked = 0
        LOGGER.info("Checking calendar validity of supplied committee dates")
        for filename, columns in (
            ("committee.csv", ("inception", "dissolution")),
            ("committee_membership.csv", ("start", "end")),
            ("committee_abbreviation.csv", ("start", "end")),
        ):
            rows = pl.read_csv(DATA_DIR / filename, infer_schema=False)
            for column in columns:
                checked += rows[column].count()
                for row in rows.filter(pl.col(column).is_not_null() & date_bound(column).is_null()).iter_rows(named=True):
                    failures += 1
                    LOGGER.error("Impossible calendar date in %s.%s: %s", filename, column, row)
        LOGGER.info("Checked %s supplied dates; %s impossible calendar dates", checked, failures)
        self.assertEqual(0, failures, f"{failures} impossible calendar date values; details logged with trainerlog")

    def test_committee_periods_are_not_definitely_inverted(self):
        """Guarantee: no committee period definitely starts after it ends.

        Data: committee lifetimes, memberships and abbreviation periods.
        Compare earliest possible start with latest possible end (Decision 0015).
        Equal dates and overlapping partial-date bounds are allowed. An unknown
        endpoint does not establish inversion. Failures count rows. Invalid
        calendar values are owned by test_committee_dates_are_possible_calendar_dates.
        """
        failures = 0
        checked = 0
        LOGGER.info("Checking chronology of committee periods")
        for filename, start, end in (
            ("committee.csv", "inception", "dissolution"),
            ("committee_membership.csv", "start", "end"),
            ("committee_abbreviation.csv", "start", "end"),
        ):
            rows = pl.read_csv(DATA_DIR / filename, infer_schema=False)
            checked += rows.height
            for row in rows.filter(date_bound(start) > date_bound(end, latest=True)).iter_rows(named=True):
                failures += 1
                LOGGER.error("Definitely inverted period in %s: %s", filename, row)
        LOGGER.info("Checked %s periods; %s definitely inverted rows", checked, failures)
        self.assertEqual(0, failures, f"{failures} definitely inverted committee periods; details logged with trainerlog")

    def test_memberships_do_not_predate_committee_inception(self):
        """Guarantee: no known membership boundary definitely predates inception.

        Data: committee_membership.csv joined to committee.csv. A boundary's
        latest possible day must not precede the earliest possible inception.
        Check each supplied boundary even if the other is unknown. Missing
        inception is unknown, not the first observed membership. Failures count
        membership rows, not endpoints. CSVW owns foreign-key validation.
        """
        rows = pl.read_csv(DATA_DIR / "committee_membership.csv", infer_schema=False).join(
            pl.read_csv(DATA_DIR / "committee.csv", infer_schema=False), on="committee_id", how="left")
        LOGGER.info("Checking %s memberships against known committee inception dates", rows.height)
        failures = 0
        before_inception = ((date_bound("start", latest=True) < date_bound("inception")) |
                            (date_bound("end", latest=True) < date_bound("inception")))
        for row in rows.filter(before_inception).iter_rows(named=True):
            failures += 1
            LOGGER.error("Membership definitely predates committee inception: %s", row)
        LOGGER.info("Checked %s memberships; %s predate inception", rows.height, failures)
        self.assertEqual(0, failures, f"{failures} memberships predate committee inception; details logged with trainerlog")

    def test_memberships_do_not_outlast_committee_dissolution(self):
        """Guarantee: no known membership boundary definitely follows dissolution.

        Data: committee_membership.csv joined to committee.csv. Compare earliest
        possible membership boundaries with latest possible dissolution. A
        year-only dissolution permits a boundary in that year. Missing dates
        remain unknown; one missing endpoint does not hide a contradiction in
        the other. Failures count membership rows. CSVW owns foreign keys.
        """
        rows = pl.read_csv(DATA_DIR / "committee_membership.csv", infer_schema=False).join(
            pl.read_csv(DATA_DIR / "committee.csv", infer_schema=False), on="committee_id", how="left")
        LOGGER.info("Checking %s memberships against known committee dissolution dates", rows.height)
        failures = 0
        after_dissolution = ((date_bound("start") > date_bound("dissolution", latest=True)) |
                             (date_bound("end") > date_bound("dissolution", latest=True)))
        for row in rows.filter(after_dissolution).iter_rows(named=True):
            failures += 1
            LOGGER.error("Membership definitely outlasts committee dissolution: %s", row)
        LOGGER.info("Checked %s memberships; %s outlast dissolution", rows.height, failures)
        self.assertEqual(0, failures, f"{failures} memberships outlast committee dissolution; details logged with trainerlog")

    def test_membership_starts_are_not_outside_person_lifetimes(self):
        """Guarantee: membership cannot definitely start before birth or after death.

        Data: committee_membership.csv and person.csv. Compare the latest
        possible start with earliest birth, and earliest start with latest death.
        Unknowns remain unknown; the comparison does not impute any date.
        Failures count membership rows. This does not test ends against death:
        supplied end dates may be administrative or planned, and their endpoint
        semantics need separate source review. It does not require full MP
        mandate coverage. CSVW owns the person foreign key.
        """
        rows = pl.read_csv(DATA_DIR / "committee_membership.csv", infer_schema=False).join(
            pl.read_csv(DATA_DIR / "person.csv", infer_schema=False).select("person_id", "born", "dead"),
            on="person_id", how="left")
        LOGGER.info("Checking %s membership starts against person lifetimes", rows.height)
        failures = 0
        outside_lifetime = ((date_bound("start", latest=True) < date_bound("born")) |
                            (date_bound("start") > date_bound("dead", latest=True)))
        for row in rows.filter(outside_lifetime).iter_rows(named=True):
            failures += 1
            LOGGER.error("Membership starts definitely outside person lifetime: %s", row)
        LOGGER.info("Checked %s membership starts; %s outside lifetimes", rows.height, failures)
        self.assertEqual(0, failures, f"{failures} membership starts outside person lifetimes; details logged with trainerlog")

    def test_sbl_linked_mps_retain_source_identifiers(self):
        """Guarantee: MPs processed in the SBL batch retain their article IDs.

        Data: test/data/reviewed_sbl_links.csv and external_identifiers.csv.
        DiSweNaBiID is the existing authority for SBL. This protects all
        processed links, including explicitly unresolved source conflicts;
        it does not assert that every MP has an SBL biography. Failures count
        person/article links. New identity corrections must update the fixture.
        The fixture retains only the 622 reviewed person/article pairs.
        """
        links = pl.read_csv("test/data/reviewed_sbl_links.csv", infer_schema=False).to_dicts()
        self.assertTrue(links, "The SBL linkage reference must not be empty")
        identifiers = pl.read_csv(DATA_DIR / "external_identifiers.csv", infer_schema=False)
        published = set(identifiers.filter(pl.col("authority") == "DiSweNaBiID").select("person_id", "identifier").iter_rows())
        failures = 0
        LOGGER.info("Checking %s reviewed SBL person/article links", len(links))
        for link in links:
            if (link["person_id"], link["identifier"]) not in published:
                failures += 1
                LOGGER.error("Missing SBL identifier for linked MP: %s", link)
        LOGGER.info("Checked %s SBL links; %s missing", len(links), failures)
        self.assertEqual(0, failures, f"{failures} SBL person/article links missing; details logged with trainerlog")

    def test_sbl_memberships_retain_reviewed_dates_and_roles(self):
        """Guarantee: SBL-supported memberships retain their reviewed dates and roles.

        Data: reviewed_sbl_committee_sources.csv and committee_membership.csv.
        Compare the exact five membership fields, retaining unknown endpoints.
        The tracked fixture also retains the article ID, URL and quoted clause;
        this check cannot authenticate quotations against an external archive.
        Failures count source claims, not distinct people or membership rows.
        """
        sources = pl.read_csv("test/data/reviewed_sbl_committee_sources.csv", infer_schema=False).to_dicts()
        self.assertTrue(sources, "The reviewed SBL source fixture must not be empty")
        rows = pl.read_csv(DATA_DIR / "committee_membership.csv", infer_schema=False)
        published = set(rows.iter_rows())
        failures = 0
        LOGGER.info("Checking %s SBL-supported membership claims", len(sources))
        for source in sources:
            expected = tuple(source[column] for column in rows.columns)
            if (expected not in published or not source["source_clause"] or not source["sbl_id"]
                    or source["source_url"] != f"https://sok.riksarkivet.se/sbl/Presentation.aspx?id={source['sbl_id']}"):
                failures += 1
                LOGGER.error("Missing or altered SBL-supported membership: %s", source)
        LOGGER.info("Checked %s SBL membership claims; %s inconsistent", len(sources), failures)
        self.assertEqual(0, failures, f"{failures} SBL membership claims missing or altered; details logged with trainerlog")

    def test_sbl_reviewed_lifetime_corrections_retain_source_dates(self):
        """Guarantee: SBL-reviewed lifetime corrections retain the sourced date.

        Data: person.csv, external_identifiers.csv and
        test/data/reviewed_sbl_person_dates.json. The fixture retains the reviewed
        date, SBL article ID and quoted evidence, checked against both the career
        summary and structured SBL date when frozen. Protect the exact date and
        its linked biography citation; do not infer unreviewed dates. This
        prevents Palmstierna's impossible pre-birth death date from returning.
        Failures count person/field corrections, not committee memberships.
        """
        corrections = json.loads(Path("test/data/reviewed_sbl_person_dates.json").read_text())
        self.assertTrue(corrections, "The lifetime-correction reference must not be empty")
        people = {row["person_id"]: row for row in pl.read_csv(DATA_DIR / "person.csv", infer_schema=False).to_dicts()}
        links = set(pl.read_csv(DATA_DIR / "external_identifiers.csv", infer_schema=False)
                    .filter(pl.col("authority") == "DiSweNaBiID").select("person_id", "identifier").iter_rows())
        failures = 0
        LOGGER.info("Checking %s reviewed SBL lifetime corrections", len(corrections))
        for correction in corrections:
            if (people.get(correction["person_id"], {}).get(correction["field"]) != correction["after"]
                    or (correction["person_id"], correction["sbl_id"]) not in links
                    or correction["source_url"] != f"https://sok.riksarkivet.se/sbl/Presentation.aspx?id={correction['sbl_id']}"
                    or not correction["source_clause"]):
                failures += 1
                LOGGER.error("Missing or altered SBL lifetime correction: %s", correction)
        LOGGER.info("Checked %s SBL lifetime corrections; %s altered", len(corrections), failures)
        self.assertEqual(0, failures, f"{failures} SBL lifetime corrections altered; details logged with trainerlog")

    def test_ku1918_memberships_retain_resolved_identities_and_roles(self):
        """Guarantee: source-supported KU 1918 identities and roles remain published.

        Data: reviewed_ku1918_elections.json and committee_membership.csv.
        The tracked fixture identifies accepted people, committees and roles,
        but does not state their service boundaries. Do not infer those from
        the election day. Source conflicts cannot become accepted evidence.
        Failures count election evidence IDs; archive-wide curation accounting
        and independent authentication of the citations are outside this check.
        """
        evidence = {}
        for row in json.loads(Path("test/data/reviewed_ku1918_elections.json").read_text()):
            self.assertNotIn(row["election_evidence_id"], evidence, "Duplicate reviewed KU election")
            evidence[row["election_evidence_id"]] = row
        self.assertTrue(evidence, "The reviewed KU election fixture must not be empty")
        roles = dict(pl.read_csv(DATA_DIR / "committee_role.csv").select("role", "committee_role_id").iter_rows())
        published = set(pl.read_csv(DATA_DIR / "committee_membership.csv", infer_schema=False)
                        .select("person_id", "committee_id", "committee_role_id").iter_rows())
        failures = 0
        LOGGER.info("Checking %s reviewed KU election identities and roles", len(evidence))
        for evidence_id, source in evidence.items():
            expected = source["person_id"], source["committee_id"], roles.get(source["role"])
            if (source["identity_status"] != "resolved_by_agent" or source["review_status"] != "source_supported"
                    or expected not in published or not source["election_source_url"]
                    or not source["register_source_url"] or not source["register_excerpt"]):
                failures += 1
                LOGGER.error("Missing or unsupported KU identity/role: %s: %s", evidence_id, source)
        LOGGER.info("Checked %s KU election identities; %s inconsistent", len(evidence), failures)
        self.assertEqual(0, failures, f"{failures} KU election identities missing or unsupported; details logged with trainerlog")

    def test_wikidata_items_identify_one_committee(self):
        """Guarantee: a Wikidata item never merges distinct committee entities.

        Data: committee_external_identifiers.csv. Deferred incarnations must
        stay unresolved instead of sharing an aggregate Wikidata identifier.
        """
        rows = pl.read_csv(DATA_DIR / "committee_external_identifiers.csv").filter(pl.col("authority") == "wikidata")
        failures = 0
        for group in rows.partition_by("identifier"):
            if group["committee_id"].n_unique() != 1:
                failures += 1
                LOGGER.error("Wikidata item maps to multiple committees: %s", group.to_dicts())
        LOGGER.info("Checked %s committee Wikidata links; %s ambiguous items", rows.height, failures)
        self.assertEqual(0, failures, f"{failures} ambiguous Wikidata items; details logged")

    def test_committees_have_one_wikidata_identity(self):
        """Guarantee: a committee is not equated with multiple Wikidata entities.

        Ordinary renames retain one identity; historic and modern Civilutskottet
        must not both be linked to the same committee.
        """
        rows = pl.read_csv(DATA_DIR / "committee_external_identifiers.csv").filter(pl.col("authority") == "wikidata")
        failures = 0
        for group in rows.partition_by("committee_id"):
            if group["identifier"].n_unique() != 1:
                failures += 1
                LOGGER.error("Committee maps to multiple Wikidata items: %s", group.to_dicts())
        LOGGER.info("Checked %s committee Wikidata links; %s ambiguous committees", rows.height, failures)
        self.assertEqual(0, failures, f"{failures} ambiguous committee identities; details logged")

    def test_source_organ_codes_resolve_to_one_committee(self):
        """Guarantee: a Riksdagen source organ code identifies one committee.

        Case and NFC variants denote the same source code, independently of
        historical abbreviation periods. Reused codes with unresolved entity
        identities are withheld from this first batch, not silently merged.
        """
        rows = pl.read_csv(DATA_DIR / "committee_external_identifiers.csv").filter(
            pl.col("authority") == "riksdagen_org_code"
        )
        targets = {}
        for row in rows.iter_rows(named=True):
            key = unicodedata.normalize("NFC", row["identifier"]).casefold()
            targets.setdefault(key, set()).add(row["committee_id"])
        failures = 0
        for code, committees in sorted(targets.items()):
            if len(committees) != 1:
                failures += 1
                LOGGER.error("Ambiguous source code %s: %s", code, sorted(committees))
        LOGGER.info("Checked %s source organ codes; %s ambiguous", len(targets), failures)
        self.assertEqual(0, failures, f"{failures} ambiguous source organ codes; details logged")

    def test_raw_abbreviations_have_nfc_counterparts(self):
        """Guarantee: every raw abbreviation has an NFC spelling for that committee.

        Preserve raw spellings as aliases; normalization must not erase them.
        """
        rows = pl.read_csv(DATA_DIR / "committee_abbreviation.csv").select("committee_id", "abbreviation")
        spellings = set(rows.iter_rows())
        failures = 0
        for committee_id, abbreviation in sorted(spellings):
            if (committee_id, unicodedata.normalize("NFC", abbreviation)) not in spellings:
                failures += 1
                LOGGER.error("Missing NFC alias for %s: %r", committee_id, abbreviation)
        LOGGER.info("Checked %s abbreviation spellings; %s missing NFC aliases", len(spellings), failures)
        self.assertEqual(0, failures, f"{failures} missing NFC aliases; details logged")

    def test_primary_abbreviation_periods_do_not_definitely_overlap(self):
        """Guarantee: two primary abbreviations never definitely overlap in time.

        For partial dates, compare latest possible starts with earliest possible
        ends. A missing boundary is unknown, not infinite. This does not assert
        complete period coverage or duplicate the general interval validation.
        """
        rows = pl.read_csv(DATA_DIR / "committee_abbreviation.csv", schema_overrides={
            "start": pl.String, "end": pl.String,
        }).filter(pl.col("primary_abbreviation")).with_columns(
            date_bound("start", latest=True).alias("latest_start"),
            date_bound("end").alias("earliest_end"))
        failures = 0
        for group in rows.partition_by("committee_id"):
            for left, right in combinations(group.iter_rows(named=True), 2):
                a, b = left["latest_start"], left["earliest_end"]
                c, d = right["latest_start"], right["earliest_end"]
                if None not in (a, b, c, d) and check_date_overlap(a, b, c, d):
                    failures += 1
                    LOGGER.error("Definitely overlapping primary abbreviations: %s / %s", left, right)
        LOGGER.info("Checked %s primary abbreviation rows; %s definitely overlapping pairs", rows.height, failures)
        self.assertEqual(0, failures, f"{failures} definitely overlapping primary pairs; details logged")


if __name__ == "__main__":
    unittest.main()
