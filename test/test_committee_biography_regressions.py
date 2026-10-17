"""Deliberate source, year and identity mutations for biography integrity gates."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

import polars as pl

from . import committee_biography_integrity as integrity


class BiographyGateRegressions(unittest.TestCase):
    def setUp(self):
        self.period = dict(period_id="bio:p", person_id="p", source_id="123", source_birth_year="1930",
            source_latest_year=2026, source_name="Anna Example", source_surname="Example",
            identity_basis="existing_identifier_name_birth", committee_id="c", committee_role_id="member",
            period="79/80-81/82", years=[1980, 1981], claim_ids=["bio:p:1980"],
            source_clause="Led av KU 79/80-81/82", excerpt="Led av KU 79/80-81/82.",
            url="https://example.org/p", source_sha256="a" * 64)
        self.gates = integrity.CommitteeBiographyIntegrity()

    def check_period(self, period):
        with patch.object(integrity.Path, "read_text", return_value=json.dumps([period])):
            self.gates.test_biography_years_respect_explicit_period_precision()

    def test_period_gate_rejects_session_edges_and_changed_quotation(self):
        """Guarantee: session-edge inflation or a changed source period turns the gate red."""
        self.check_period(self.period)
        for changes in ({"years": [1979, 1980, 1981, 1982]}, {"period": "79/80-81/88"},
                        {"excerpt": "Led av KU 82/83-84/85."}, {"period": "80/81", "years": [1980]}):
            with self.subTest(changes=changes), self.assertRaisesRegex(AssertionError, "1 biography periods"):
                self.check_period(dict(self.period, **changes))

    def test_membership_gate_rejects_wrong_role_and_excluded_year(self):
        """Guarantee: a changed role or boundary excluding the biography year turns the gate red."""
        row = {k: self.period[k] for k in ("person_id", "committee_id", "committee_role_id")}
        row.update(start=None, end=None)
        for changes in ({}, {"committee_role_id": "substitute"}, {"start": "1982"}, {"end": "1979"}):
            frame = pl.DataFrame([dict(row, **changes)], schema={k: pl.String for k in row})
            with patch.object(integrity.Path, "read_text", return_value=json.dumps([self.period])), \
                 patch.object(integrity.pl, "read_csv", return_value=frame):
                if changes:
                    with self.assertRaisesRegex(AssertionError, "2 biography year claims"):
                        self.gates.test_biography_periods_retain_compatible_published_memberships()
                else:
                    self.gates.test_biography_periods_retain_compatible_published_memberships()

    def test_identity_gate_rejects_changed_birth_and_shared_id(self):
        """Guarantee: contradictory birth years or shared source IDs turn the gate red."""
        base = dict(person_id="p", born="1930", riksdagen_id="123")
        names = pl.DataFrame(dict(person_id=["p"], name=["Anna Example"]))
        for people in ([base], [dict(base, born="1931")], [base, dict(base, person_id="other")]):
            tables = {"person.csv": pl.DataFrame(people), "name.csv": names}
            with patch.object(integrity.Path, "read_text", return_value=json.dumps([self.period])), \
                 patch.object(integrity.pl, "read_csv", side_effect=lambda path, **kw: tables[Path(path).name]):
                if people == [base]:
                    self.gates.test_biography_identities_retain_name_birth_and_identifier_support()
                else:
                    with self.assertRaisesRegex(AssertionError, "1 biography identity links"):
                        self.gates.test_biography_identities_retain_name_birth_and_identifier_support()


if __name__ == "__main__":
    unittest.main()
