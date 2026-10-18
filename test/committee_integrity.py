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

    def test_committee_appointment_starts_are_compatible_with_mp_mandates(self):
        """Guarantee: committee appointments have MP mandates compatible with known starts.

        Data: all committee_membership.csv rows and member_of_parliament.csv.
        Accept generic MP and both historical chamber roles, for every committee
        role and year. Compare each start's earliest/latest possible day with
        individual mandate intervals, never the envelope of a person's career.
        A matching bounded mandate establishes compatibility, not an exact start
        day. Missing committee starts and potentially matching incomplete MP
        intervals are reported separately as inconclusive, not verified service.
        Unknown endpoints stay null; a known opposing boundary still rules out
        a mandate. Invalid or inverted mandate intervals cannot provide support.
        A person with no usable MP mandate is a failure even if the start is
        unknown. Calendar validity and committee chronology have separate gates.
        This checks appointment starts, not ends or uninterrupted service: leave
        can interrupt recorded MP service without ending a committee appointment.
        Failures count membership rows, once each. There is no historical
        exception list, date cutoff or allowance for existing discrepancies.
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
        missing_mandates = incompatible_starts = unknown_starts = 0
        LOGGER.info("Checking appointment-start compatibility for all %s committee memberships", memberships.height)
        for row in memberships.iter_rows(named=True):
            if row["person_id"] not in people_with_mandates:
                missing_mandates += 1
                LOGGER.error("Committee membership has no usable MP mandate: %s", row)
            elif row["start"] is None:
                unknown_starts += 1
            elif row["row"] not in possible_rows:
                incompatible_starts += 1
                recorded = mandates.filter(pl.col("person_id") == row["person_id"]).select("role", "start", "end")
                LOGGER.error("Committee appointment start conflicts with recorded MP mandates: %s; mandates: %s",
                             row, recorded.to_dicts())
        failures = missing_mandates + incompatible_starts
        LOGGER.info("Checked %s memberships: %s compatible with bounded mandates; %s unknown starts; "
                    "%s inconclusive due to incomplete mandate dates; %s without usable mandates; %s incompatible starts",
                    memberships.height, len(bounded_rows), unknown_starts, len(possible_rows - bounded_rows),
                    missing_mandates, incompatible_starts)
        self.assertEqual(0, failures,
                         f"{failures} committee memberships lack compatible MP mandates "
                         f"({missing_mandates} without usable mandates, {incompatible_starts} incompatible starts); "
                         "review membership and mandate dates; details logged with trainerlog")

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
