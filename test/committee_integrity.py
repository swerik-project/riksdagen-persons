"""General semantic guarantees for committee identities and historical dates.

CSVW owns structural types, required fields, primary keys and foreign keys.
These checks use the published data tables, not frozen curation fixtures.
"""

from itertools import combinations
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
            ("committee.csv", ("start", "end")),
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

    def test_memberships_do_not_predate_committee_start(self):
        """Guarantee: no known membership boundary definitely predates the committee.

        Data: committee_membership.csv joined to committee.csv. A boundary's
        latest possible day must not precede the earliest possible committee start.
        Check each supplied boundary even if the other is unknown. Missing
        committee start is unknown, not the first observed membership. Failures count
        membership rows, not endpoints. CSVW owns foreign-key validation.
        """
        rows = pl.read_csv(DATA_DIR / "committee_membership.csv", infer_schema=False).join(
            pl.read_csv(DATA_DIR / "committee.csv", infer_schema=False).select(
                "committee_id", pl.col("start").alias("committee_start")), on="committee_id", how="left")
        LOGGER.info("Checking %s memberships against known committee start dates", rows.height)
        failures = 0
        before_start = ((date_bound("start", latest=True) < date_bound("committee_start")) |
                        (date_bound("end", latest=True) < date_bound("committee_start")))
        for row in rows.filter(before_start).iter_rows(named=True):
            failures += 1
            LOGGER.error("Membership definitely predates committee start: %s", row)
        LOGGER.info("Checked %s memberships; %s predate committee start", rows.height, failures)
        self.assertEqual(0, failures, f"{failures} memberships predate committee start; details logged with trainerlog")

    def test_memberships_do_not_outlast_committee_end(self):
        """Guarantee: no known membership boundary definitely outlasts the committee.

        Data: committee_membership.csv joined to committee.csv. Compare earliest
        possible membership boundaries with the latest possible committee end. A
        year-only end permits a boundary in that year. Missing dates
        remain unknown; one missing endpoint does not hide a contradiction in
        the other. Failures count membership rows. CSVW owns foreign keys.
        """
        rows = pl.read_csv(DATA_DIR / "committee_membership.csv", infer_schema=False).join(
            pl.read_csv(DATA_DIR / "committee.csv", infer_schema=False).select(
                "committee_id", pl.col("end").alias("committee_end")), on="committee_id", how="left")
        LOGGER.info("Checking %s memberships against known committee end dates", rows.height)
        failures = 0
        after_end = ((date_bound("start") > date_bound("committee_end", latest=True)) |
                     (date_bound("end") > date_bound("committee_end", latest=True)))
        for row in rows.filter(after_end).iter_rows(named=True):
            failures += 1
            LOGGER.error("Membership definitely outlasts committee end: %s", row)
        LOGGER.info("Checked %s memberships; %s outlast committee end", rows.height, failures)
        self.assertEqual(0, failures, f"{failures} memberships outlast committee end; details logged with trainerlog")

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

    def test_committee_members_have_usable_mp_records(self):
        """Guarantee: every committee member has a usable parliamentary record.

        Data: all committee_membership.csv rows and member_of_parliament.csv.
        Accept generic MP and both historical chamber roles, for every committee
        role and year. Invalid or definitely inverted MP intervals cannot supply
        evidence; missing dates remain unknown. Failures count membership rows
        without a usable MP record, once each, with no current-data allowance.

        MP rows describe active service, not complete parliamentary eligibility.
        Leave can exclude service while a committee appointment continues or
        begins; a committee row start may also be a role change or administrative
        boundary rather than an election. The published tables do not record
        leave or full eligibility intervals. Therefore a start outside recorded
        service is an unresolved diagnostic, not proof of ineligibility. Do not
        invent leave, join career gaps, or require uninterrupted service.

        Compare partial starts with individual service intervals for diagnostics
        only. Bounded overlap supports the service date; incomplete intervals and
        unknown starts remain separate uncertainties. A missing MP record still
        fails independently of committee dates. Calendar validity, committee
        chronology and lifetime compatibility have separate gates. This check
        does not certify eligibility on an appointment date or verify attendance.

        References: Riksdagens protokoll 1998/99:5, sections 2, 3 and 8
        (committee elections and parental leave effective on the same day);
        Utrikesutskottets verksamhet 2012/13, section 1.2 (membership during leave).
        """
        memberships = pl.read_csv(DATA_DIR / "committee_membership.csv", infer_schema=False).with_row_index("row")
        mandates = pl.read_csv(DATA_DIR / "member_of_parliament.csv", infer_schema=False).filter(
            pl.col("role").is_in(["ledamot", "förstakammarledamot", "andrakammarledamot"]))
        mandates = mandates.with_columns(date_bound("start").alias("mandate_start"),
                                         date_bound("end", latest=True).alias("mandate_end"))
        usable = mandates.filter(
            (pl.col("start").is_null() | pl.col("mandate_start").is_not_null()) &
            (pl.col("end").is_null() | pl.col("mandate_end").is_not_null()) &
            (pl.col("mandate_start").is_null() | pl.col("mandate_end").is_null() |
             (pl.col("mandate_start") <= pl.col("mandate_end"))))
        dated = memberships.filter(pl.col("start").is_not_null()).with_columns(
            date_bound("start").alias("start_earliest"), date_bound("start", latest=True).alias("start_latest"))
        candidates = dated.join(usable.select("person_id", "mandate_start", "mandate_end"), on="person_id")
        possible = candidates.filter(
            pl.col("start_earliest").is_not_null() & pl.col("start_latest").is_not_null() &
            (pl.col("mandate_start").is_null() | (pl.col("start_latest") >= pl.col("mandate_start"))) &
            (pl.col("mandate_end").is_null() | (pl.col("start_earliest") <= pl.col("mandate_end"))))
        bounded = possible.filter(pl.col("mandate_start").is_not_null() & pl.col("mandate_end").is_not_null())
        people_with_mandates = set(usable["person_id"])
        possible_rows, bounded_rows = set(possible["row"]), set(bounded["row"])
        missing_mandates = unresolved_starts = unknown_starts = 0
        LOGGER.info("Checking MP record coverage for all %s committee memberships; "
                    "service-date overlap does not establish full parliamentary eligibility", memberships.height)
        for row in memberships.iter_rows(named=True):
            if row["person_id"] not in people_with_mandates:
                missing_mandates += 1
                LOGGER.error("Committee membership has no usable MP record: %s", row)
            elif row["start"] is None:
                unknown_starts += 1
            elif row["row"] not in possible_rows:
                unresolved_starts += 1
                recorded = mandates.filter(pl.col("person_id") == row["person_id"]).select("role", "start", "end")
                LOGGER.warning("Committee role start is outside recorded MP service; eligibility unresolved "
                               "(leave, missing service or a different appointment boundary may explain it): %s; "
                               "MP records: %s", row, recorded.to_dicts())
        LOGGER.info("Checked %s memberships: %s starts overlap bounded MP service; %s unknown starts; "
                    "%s inconclusive due to incomplete MP dates; %s without usable MP records; "
                    "%s outside recorded service with eligibility unresolved",
                    memberships.height, len(bounded_rows), unknown_starts, len(possible_rows - bounded_rows),
                    missing_mandates, unresolved_starts)
        self.assertEqual(0, missing_mandates,
                         f"{missing_mandates} committee memberships lack usable MP records; "
                         "review missing parliamentary records and person identities; details logged with trainerlog. "
                         f"{unresolved_starts} further starts are outside recorded active service; "
                         "their eligibility needs separate evidence, including leave and appointment semantics")

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

    def test_primary_abbreviation_periods_do_not_overlap(self):
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
