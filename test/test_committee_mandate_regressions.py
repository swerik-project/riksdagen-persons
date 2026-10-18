"""Synthetic mutations for the all-year committee appointment-start guarantee.

The real corpus gate reads small in-memory tables; no historical fixtures,
published data changes, network access or source archives are needed.
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
                                      (integrity.LOGGER, "info", {}), (integrity.LOGGER, "error", {})):
            mock = patch.object(target, name, **options)
            result = mock.start()
            self.addCleanup(mock.stop)
            if name == "info":
                self.info = result
            elif name == "error":
                self.error = result
        self.gate = integrity.CommitteeIntegrity().test_committee_appointment_starts_are_compatible_with_mp_mandates

    def test_exact_start_within_a_mandate_is_compatible(self):
        """Guarantee: a dated appointment inside a bounded MP mandate passes."""
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 1, 0, 0, 0, 0))
        self.error.assert_not_called()

    def test_start_before_every_mandate_turns_the_gate_red(self):
        """Guarantee: moving an appointment before MP service causes a failure."""
        self.memberships[0]["start"] = "1979-09-30"
        with self.assertRaisesRegex(AssertionError, "1 incompatible starts"):
            self.gate()
        self.error.assert_called_once()

    def test_start_after_every_mandate_turns_the_gate_red(self):
        """Guarantee: moving an appointment after MP service causes a failure."""
        self.memberships[0]["start"] = "1982-10-02"
        with self.assertRaisesRegex(AssertionError, "1 incompatible starts"):
            self.gate()

    def test_separate_mandates_do_not_bridge_an_appointment_gap(self):
        """Guarantee: earliest career start and latest end cannot fill a mandate gap."""
        self.mandates = [dict(self.mandates[0], start="1979", end="1980-05-31"),
                         dict(self.mandates[0], start="1980-06-02", end="1982")]
        with self.assertRaisesRegex(AssertionError, "1 incompatible starts"):
            self.gate()

    def test_partial_start_year_can_overlap_a_mandate(self):
        """Guarantee: a year-only start is not imputed to January 1."""
        self.memberships[0]["start"] = "1979"
        self.gate()

    def test_partial_start_month_includes_its_last_day(self):
        """Guarantee: a month-only appointment can start on its last calendar day."""
        self.memberships[0]["start"] = "1980-02"
        self.mandates[0]["start"] = "1980-02-29"
        self.gate()

    def test_partial_mandate_end_includes_its_last_day(self):
        """Guarantee: month-precision MP ends permit an appointment on leap day."""
        self.memberships[0]["start"] = "1980-02-29"
        self.mandates[0]["end"] = "1980-02"
        self.gate()

    def test_unknown_committee_start_is_reported_not_inferred_from_end(self):
        """Guarantee: an end date cannot stand in for an unknown appointment start."""
        self.memberships[0].update(start=None, end="1970")
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 1, 0, 0, 0))

    def test_unknown_committee_end_does_not_hide_an_incompatible_start(self):
        """Guarantee: a missing committee end does not exempt its known start."""
        self.memberships[0].update(start="1978", end=None)
        with self.assertRaisesRegex(AssertionError, "1 incompatible starts"):
            self.gate()

    def test_unknown_mandate_start_is_inconclusive_not_bounded_support(self):
        """Guarantee: a potentially matching open start is reported as uncertainty."""
        self.mandates[0]["start"] = None
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 1, 0, 0))

    def test_unknown_mandate_end_is_inconclusive_not_ongoing_service(self):
        """Guarantee: an absent mandate end cannot establish ongoing service."""
        self.mandates[0]["end"] = None
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 1, 0, 0))

    def test_fully_undated_mandate_remains_inconclusive(self):
        """Guarantee: an undated MP record does not verify an appointment year."""
        self.mandates[0].update(start=None, end=None)
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 0, 0, 1, 0, 0))

    def test_unknown_mandate_start_does_not_hide_a_contradicting_end(self):
        """Guarantee: a known early MP end excludes a later appointment."""
        self.mandates[0].update(start=None, end="1978")
        with self.assertRaisesRegex(AssertionError, "1 incompatible starts"):
            self.gate()

    def test_unknown_mandate_end_does_not_hide_a_contradicting_start(self):
        """Guarantee: a known late MP start excludes an earlier appointment."""
        self.mandates[0].update(start="1981", end=None)
        with self.assertRaisesRegex(AssertionError, "1 incompatible starts"):
            self.gate()

    def test_bounded_support_takes_precedence_over_an_undated_alternative(self):
        """Guarantee: an extra unknown mandate does not erase bounded compatibility."""
        self.mandates.append(dict(self.mandates[0], start=None, end=None))
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (1, 1, 0, 0, 0, 0))

    def test_malformed_mandate_date_cannot_be_treated_as_unknown(self):
        """Guarantee: an impossible MP date cannot supply an open-ended match."""
        self.mandates[0]["end"] = "1980-02-30"
        with self.assertRaisesRegex(AssertionError, "1 without usable mandates"):
            self.gate()

    def test_inverted_mandate_cannot_supply_support(self):
        """Guarantee: an MP interval ending before it starts is not evidence."""
        self.mandates[0].update(start="1982", end="1979")
        with self.assertRaisesRegex(AssertionError, "1 without usable mandates"):
            self.gate()

    def test_both_historical_chamber_roles_supply_mp_support(self):
        """Guarantee: first- and second-chamber MPs are eligible without a generic role."""
        self.memberships = [dict(self.memberships[0], person_id=p, start="1880") for p in ("fk", "ak")]
        self.mandates = [dict(person_id="fk", start="1879", end="1881", role="förstakammarledamot"),
                         dict(person_id="ak", start="1879", end="1881", role="andrakammarledamot")]
        self.gate()
        self.assertEqual(self.info.call_args.args[1:], (2, 2, 0, 0, 0, 0))

    def test_all_committee_roles_and_years_are_checked(self):
        """Guarantee: neither early/future years nor substitute roles escape the gate."""
        self.memberships = [dict(self.memberships[0], start="1850", committee_role_id="substitute"),
                            dict(self.memberships[0], start="2030", committee_role_id="chair")]
        with self.assertRaisesRegex(AssertionError, "2 incompatible starts"):
            self.gate()

    def test_missing_mandates_fail_even_for_an_undated_membership(self):
        """Guarantee: an MP record is required independently of date precision."""
        self.memberships.append(dict(self.memberships[0], committee_id="other", start=None, end=None))
        self.mandates = []
        with self.assertRaisesRegex(AssertionError, "2 without usable mandates"):
            self.gate()

    def test_a_non_mp_role_cannot_establish_parliamentary_service(self):
        """Guarantee: an unrelated role cannot stand in for an MP mandate."""
        self.mandates[0]["role"] = "minister"
        with self.assertRaisesRegex(AssertionError, "1 without usable mandates"):
            self.gate()

    def test_multiple_mandates_do_not_multiply_a_membership_failure(self):
        """Guarantee: one incompatible membership counts once despite multiple mandates."""
        self.mandates.append(dict(self.mandates[0]))
        self.memberships[0]["start"] = "1978"
        with self.assertRaisesRegex(AssertionError, "1 committee memberships"):
            self.gate()
        self.error.assert_called_once()

    def test_later_leave_and_committee_end_do_not_invalidate_an_eligible_start(self):
        """Guarantee: this gate does not impose uninterrupted MP service after appointment."""
        self.mandates[0]["end"] = "1980-06-01"
        self.mandates.append(dict(self.mandates[0], start="1981", end="1982"))
        self.gate()

    def test_malformed_committee_start_cannot_be_supported_by_unknown_mandates(self):
        """Guarantee: invalid input does not masquerade as an unknown appointment date."""
        self.memberships[0]["start"] = "1980-02-30"
        self.mandates[0].update(start=None, end=None)
        with self.assertRaisesRegex(AssertionError, "1 incompatible starts"):
            self.gate()


if __name__ == "__main__":
    unittest.main()
