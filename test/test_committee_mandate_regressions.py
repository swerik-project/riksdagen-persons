"""Synthetic regressions for MP record coverage and service-date diagnostics.

The real corpus check reads in-memory tables. No historical fixtures, published
data changes, network access or source archives are needed.
"""

from pathlib import Path
import unittest
from unittest.mock import patch

import polars as pl

from . import committee_integrity as integrity


class CommitteeMandateRegressions(unittest.TestCase):
    def setUp(self):
        self.memberships = [dict(person_id="p", committee_id="c", start="1980-06-01",
                                 end="1982", committee_role_id="member")]
        self.mandates = [dict(person_id="p", start="1979-10-01", end="1982-10-01", role="ledamot")]

        def read(path, **kwargs):
            if Path(path).name == "committee_membership.csv":
                rows, columns = self.memberships, ("person_id", "committee_id", "start", "end", "committee_role_id")
            else:
                self.assertEqual(Path(path).name, "member_of_parliament.csv")
                rows, columns = self.mandates, ("person_id", "start", "end", "role")
            return pl.DataFrame(rows, schema={c: pl.String for c in columns})

        for target, name, options in ((integrity.pl, "read_csv", {"side_effect": read}),
                                      (integrity.LOGGER, "info", {}), (integrity.LOGGER, "error", {}),
                                      (integrity.LOGGER, "warning", {})):
            mock = patch.object(target, name, **options)
            result = mock.start()
            self.addCleanup(mock.stop)
            if name in {"info", "error", "warning"}:
                setattr(self, name, result)
        self.gate = integrity.CommitteeIntegrity().test_committee_members_have_usable_mp_records

    def test_exact_start_within_recorded_service_has_date_support(self):
        """Guarantee: bounded service overlap is reported without an eligibility assertion."""
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 1, 0, 0, 0, 0))
        self.error.assert_not_called()
        self.warning.assert_not_called()

    def test_start_before_recorded_service_is_unresolved(self):
        """Guarantee: the earliest recorded service does not prove when eligibility began."""
        self.memberships[0]["start"] = "1979-09-30"
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 0, 0, 1))
        self.warning.assert_called_once()
        self.assertIn("eligibility unresolved", self.warning.call_args.args[0])
        self.error.assert_not_called()

    def test_start_after_recorded_service_is_unresolved(self):
        """Guarantee: the last recorded service does not prove when eligibility ended."""
        self.memberships[0]["start"] = "1982-10-02"
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 0, 0, 1))
        self.warning.assert_called_once()

    def test_service_gap_is_not_filled_or_declared_ineligible(self):
        """Guarantee: service gaps remain unresolved without inventing continuous eligibility."""
        self.mandates = [dict(self.mandates[0], start="1979", end="1980-05-31"),
                         dict(self.mandates[0], start="1980-06-02", end="1982")]
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 0, 0, 1))
        self.warning.assert_called_once()
        self.error.assert_not_called()

    def test_appointment_entirely_during_leave_is_not_rejected(self):
        """Guarantee: an appointment can begin and end while active service is interrupted.

        Mirrors the same-day election and parental-leave pattern in 1998/99:5.
        The tables alone cannot distinguish documented leave from missing service;
        report unresolved eligibility rather than invalidating the appointment.
        """
        self.memberships[0].update(start="1998-10-13", end="1998-12-31")
        self.mandates = [dict(self.mandates[0], start="1998-10-05", end="1998-10-12"),
                         dict(self.mandates[0], start="1999-01-01", end="2002-09-30")]
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 0, 0, 1))
        self.warning.assert_called_once()
        self.error.assert_not_called()

    def test_role_change_during_leave_is_not_a_new_ineligible_appointment(self):
        """Guarantee: chair/member role boundaries need not fall within active service.

        Mirrors the chair/member/chair sequence documented by UU in 2012/13.
        """
        self.memberships = [
            dict(self.memberships[0], start="2012-04-26", end="2012-11-18", committee_role_id="chair"),
            dict(self.memberships[0], start="2012-11-19", end="2013-03-31"),
            dict(self.memberships[0], start="2013-04-01", end="2014-09-29", committee_role_id="chair"),
        ]
        self.mandates = [dict(self.mandates[0], start="2010-10-04", end="2012-11-18"),
                         dict(self.mandates[0], start="2013-04-01", end="2014-09-29")]
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (3, 2, 0, 0, 0, 1))
        self.warning.assert_called_once()
        self.error.assert_not_called()

    def test_a_long_career_gap_is_not_assumed_to_be_leave(self):
        """Guarantee: separate terms do not supply positive evidence across a career gap."""
        self.memberships[0]["start"] = "1990"
        self.mandates = [dict(self.mandates[0], start="1979", end="1982"),
                         dict(self.mandates[0], start="2002", end="2006")]
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 0, 0, 1))

    def test_partial_start_year_can_overlap_recorded_service(self):
        """Guarantee: a year-only start is not imputed to January 1."""
        self.memberships[0]["start"] = "1979"
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 1, 0, 0, 0, 0))

    def test_partial_start_month_includes_its_last_day(self):
        """Guarantee: month-precision starts may overlap service on the final calendar day."""
        self.memberships[0]["start"] = "1980-02"
        self.mandates[0]["start"] = "1980-02-29"
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 1, 0, 0, 0, 0))

    def test_partial_mp_end_includes_its_last_day(self):
        """Guarantee: month-precision service ends include leap day in comparisons."""
        self.memberships[0]["start"] = "1980-02-29"
        self.mandates[0]["end"] = "1980-02"
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 1, 0, 0, 0, 0))

    def test_unknown_committee_start_is_reported_not_inferred_from_end(self):
        """Guarantee: an end date cannot stand in for an unknown role-period start."""
        self.memberships[0].update(start=None, end="1970")
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 1, 0, 0, 0))
        self.warning.assert_not_called()

    def test_unknown_committee_end_does_not_hide_a_service_gap(self):
        """Guarantee: an undated end does not suppress diagnostics for a known start."""
        self.memberships[0].update(start="1978", end=None)
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 0, 0, 1))
        self.warning.assert_called_once()

    def test_unknown_mp_start_is_inconclusive_not_bounded_support(self):
        """Guarantee: a potentially matching unknown start remains uncertainty."""
        self.mandates[0]["start"] = None
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 1, 0, 0))

    def test_unknown_mp_end_is_inconclusive_not_ongoing_service(self):
        """Guarantee: an absent service end cannot establish ongoing service."""
        self.mandates[0]["end"] = None
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 1, 0, 0))

    def test_fully_undated_mp_record_remains_inconclusive(self):
        """Guarantee: an undated MP record supports identity but not the service year."""
        self.mandates[0].update(start=None, end=None)
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 1, 0, 0))

    def test_unknown_mp_start_does_not_hide_a_known_service_end(self):
        """Guarantee: a known early end cannot supply service-date support for a later start."""
        self.mandates[0].update(start=None, end="1978")
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 0, 0, 1))

    def test_unknown_mp_end_does_not_hide_a_known_service_start(self):
        """Guarantee: a known late start cannot supply service-date support for an earlier start."""
        self.mandates[0].update(start="1981", end=None)
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 0, 0, 1))

    def test_bounded_support_takes_precedence_over_an_undated_alternative(self):
        """Guarantee: an extra unknown record does not erase bounded service-date support."""
        self.mandates.append(dict(self.mandates[0], start=None, end=None))
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 1, 0, 0, 0, 0))

    def test_malformed_mp_date_cannot_supply_a_usable_record(self):
        """Guarantee: an impossible service date cannot masquerade as an unknown endpoint."""
        self.mandates[0]["end"] = "1980-02-30"
        with self.assertRaisesRegex(AssertionError, "1 committee memberships lack usable MP records"):
            self.gate()
        self.error.assert_called_once()
        self.warning.assert_not_called()

    def test_inverted_mp_interval_cannot_supply_a_usable_record(self):
        """Guarantee: a definitely inverted service interval cannot provide MP evidence."""
        self.mandates[0].update(start="1982", end="1979")
        with self.assertRaisesRegex(AssertionError, "1 committee memberships lack usable MP records"):
            self.gate()

    def test_both_historical_chamber_roles_supply_mp_records(self):
        """Guarantee: both historical chambers provide MP evidence without a generic role."""
        self.memberships = [dict(self.memberships[0], person_id=p, start="1880") for p in ("fk", "ak")]
        self.mandates = [dict(person_id="fk", start="1879", end="1881", role="förstakammarledamot"),
                         dict(person_id="ak", start="1879", end="1881", role="andrakammarledamot")]
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (2, 2, 0, 0, 0, 0))

    def test_all_committee_roles_and_years_receive_diagnostics(self):
        """Guarantee: early and future role starts remain unresolved without date support."""
        self.memberships = [dict(self.memberships[0], start="1850", committee_role_id="substitute"),
                            dict(self.memberships[0], start="2030", committee_role_id="chair")]
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (2, 0, 0, 0, 0, 2))
        self.assertEqual(self.warning.call_count, 2)

    def test_estates_era_start_is_not_rejected_against_later_chamber_service(self):
        """Guarantee: a pre-1867 start is not invalidated by missing estates-era coverage."""
        self.memberships[0].update(start="1856", end="1869")
        self.mandates[0].update(start="1867", end="1869", role="andrakammarledamot")
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 0, 0, 1))
        self.warning.assert_called_once()

    def test_missing_mp_records_fail_even_for_an_undated_membership(self):
        """Guarantee: missing parliamentary records still fail independently of date precision."""
        self.memberships.append(dict(self.memberships[0], committee_id="other", start=None, end=None))
        self.mandates = []
        with self.assertRaisesRegex(AssertionError, "2 committee memberships lack usable MP records"):
            self.gate()
        self.assertEqual(self.error.call_count, 2)
        self.assertEqual(self.info.call_args.args[1:], (2, 0, 0, 0, 2, 0))

    def test_a_non_mp_role_cannot_establish_parliamentary_membership(self):
        """Guarantee: being a minister alone does not establish membership of parliament."""
        self.mandates[0]["role"] = "minister"
        with self.assertRaisesRegex(AssertionError, "1 committee memberships lack usable MP records"):
            self.gate()

    def test_missing_mp_record_still_fails_alongside_a_service_gap(self):
        """Guarantee: unresolved dates do not excuse another person's missing MP record."""
        self.memberships[0]["start"] = "1978"
        self.memberships.append(dict(self.memberships[0], person_id="other"))
        with self.assertRaisesRegex(AssertionError, "1 committee memberships lack usable MP records"):
            self.gate()
        self.assertEqual(self.info.call_args.args[1:], (2, 0, 0, 0, 1, 1))
        self.error.assert_called_once()
        self.warning.assert_called_once()

    def test_multiple_mp_rows_do_not_multiply_unresolved_memberships(self):
        """Guarantee: a membership without service-date support is counted and logged once."""
        self.mandates.append(dict(self.mandates[0]))
        self.memberships[0]["start"] = "1978"
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 0, 0, 1))
        self.warning.assert_called_once()

    def test_later_leave_and_committee_end_do_not_require_uninterrupted_service(self):
        """Guarantee: service-date diagnostics do not assert coverage of the whole committee spell."""
        self.mandates[0]["end"] = "1980-06-01"
        self.mandates.append(dict(self.mandates[0], start="1981", end="1982"))
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 1, 0, 0, 0, 0))
        self.warning.assert_not_called()

    def test_malformed_committee_start_is_not_service_date_support(self):
        """Guarantee: invalid role dates remain unsupported; the calendar gate owns their rejection."""
        self.memberships[0]["start"] = "1980-02-30"
        self.mandates[0].update(start=None, end=None)
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 0, 0, 1))
        self.warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
