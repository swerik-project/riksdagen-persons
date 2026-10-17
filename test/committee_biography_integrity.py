"""Offline semantic guarantees for biography-supported committee years, 1980-1987."""

import json
from pathlib import Path
import re
import unittest

import polars as pl
from pyriksdagen.match_mp import clean_names, names_in
from trainerlog import get_logger


LOGGER = get_logger("committee-biography-integrity")
FIXTURE = "test/data/reviewed_committee_biography_periods.json"


class CommitteeBiographyIntegrity(unittest.TestCase):
    def test_biography_years_respect_explicit_period_precision(self):
        """Guarantee: session endpoints never become unsupported calendar years.

        Data: the frozen biography-period fixture. A single 1980/81 session
        cannot select either calendar year; 1979/80-1981/82 guarantees only
        1980 and 1981. Plain calendar-year endpoints are inclusive. Independently
        derives eligible years without the importer. Failures count period IDs.
        """
        periods = json.loads(Path(FIXTURE).read_text())
        failures = 0
        LOGGER.info("Checking calendar precision for %s biography periods", len(periods))
        for p in periods:
            try:
                match = re.fullmatch(r"(\d{2}|\d{4})(/\d{2})?(?:\s*-{1,2}\s*(\d{2}|\d{4})(/\d{2})?)?", p["period"])
                if not match:
                    raise ValueError("Invalid period")
                bounds = []
                for token, session in ((match[1], match[2]), (match[3] or match[1], match[4] if match[3] else match[2])):
                    years = [y for y in range(int(p["source_birth_year"]), p["source_latest_year"] + 1)
                             if (str(y) == token if len(token) == 4 else y % 100 == int(token))]
                    if len(years) != 1 or (session and (years[0] + 1) % 100 != int(session[1:])):
                        raise ValueError("Ambiguous year or malformed session")
                    bounds.append(years[0])
                expected = list(range(max(1980, bounds[0] + bool(match[2])), min(1987, bounds[1]) + 1))
                normalized = " ".join(p["excerpt"].replace("–", "-").replace("—", "-").split())
                normalized = re.sub(r"\b(Led|Suppl)\.(?=\s)", r"\1", normalized, flags=re.I)
                valid = (bool(expected) and p["years"] == expected and p["source_clause"] in normalized
                         and p["period"] in p["source_clause"] and bool(p["claim_ids"]))
            except (ValueError, TypeError, KeyError):
                valid = False
            if not valid:
                failures += 1
                LOGGER.error("Biography period has unsupported precision or quotation: %s", p)
        LOGGER.info("Checked %s periods; %s invalid", len(periods), failures)
        self.assertEqual(0, failures, f"{failures} biography periods have unsupported years or quotations; details logged with trainerlog")

    def test_biography_periods_retain_exact_published_claims(self):
        """Guarantee: every biography year retains its person, role and source.

        Data: biography periods and reviewed_committee_roster_sources.csv.
        Both fixtures account for exactly the same claim IDs. No exact event day
        may be invented from a session label. Failures count source claims.
        Existing roster gates separately check membership keys and mandates.
        """
        periods = json.loads(Path(FIXTURE).read_text())
        rows = pl.read_csv("test/data/reviewed_committee_roster_sources.csv", infer_schema=False).filter(
            pl.col("source_kind") == "biography_period").to_dicts()
        expected = {cid: p for p in periods for cid in p["claim_ids"]}
        actual = {r["claim_id"]: r for r in rows}
        self.assertEqual(len(expected), sum(len(p["claim_ids"]) for p in periods), "Duplicate biography period claim IDs")
        self.assertEqual(len(actual), len(rows), "Duplicate published biography claim IDs")
        failures = 0
        LOGGER.info("Checking source links for %s biography year claims", len(expected))
        for cid in sorted(set(expected) | set(actual)):
            p, r = expected.get(cid), actual.get(cid)
            valid = bool(p and r)
            if valid:
                valid = (all(r[key] == p[key] for key in
                    ("person_id", "committee_id", "committee_role_id", "url", "excerpt", "source_sha256"))
                    and int(r["year"]) in p["years"] and cid == p["period_id"] + ":" + r["year"]
                    and r["event_date"] is None and r["chamber"] == "EK"
                    and bool(re.fullmatch(r"[0-9a-f]{64}", r["source_sha256"])))
            if not valid:
                failures += 1
                LOGGER.error("Biography year lost matching evidence: %s; period=%s; published=%s", cid, p, r)
        LOGGER.info("Checked biography year claims; %s inconsistent", failures)
        self.assertEqual(0, failures, f"{failures} biography year claims inconsistent; details logged with trainerlog")

    def test_biography_identities_retain_name_birth_and_identifier_support(self):
        """Guarantee: biography links retain unique ID, name and birth-year support.

        Data: frozen biography identities, person.csv and name.csv. An existing
        source ID must remain unique and attached to the selected person.
        Name/birth-only links cannot override another existing identifier.
        Failures count source-person pairs. No identifiers are added here.
        """
        periods = json.loads(Path(FIXTURE).read_text())
        people = pl.read_csv("data/person.csv", infer_schema=False).to_dicts()
        names = pl.read_csv("data/name.csv", infer_schema=False).to_pandas()
        names["name"] = clean_names(names["name"])
        by_person = {p["person_id"]: p for p in people}
        identities = {(p["person_id"], p["source_id"]): p for p in periods}
        failures = 0
        LOGGER.info("Checking %s biography identity links", len(identities))
        for (pid, sid), reference in identities.items():
            person = by_person.get(pid)
            linked = [p["person_id"] for p in people if p["riksdagen_id"] == sid]
            valid = person is not None
            if valid:
                aliases = names[names["person_id"] == pid]
                valid = (bool(person["born"]) and person["born"][:4] == reference["source_birth_year"]
                         and not names_in(clean_names(reference["source_name"]), aliases).empty
                         and (linked == [pid] if reference["identity_basis"] == "existing_identifier_name_birth"
                              else not linked and not person["riksdagen_id"]))
            if not valid:
                failures += 1
                LOGGER.error("Biography identity no longer supported: %s / %s; %s", pid, sid, reference)
        LOGGER.info("Checked %s biography identities; %s inconsistent", len(identities), failures)
        self.assertEqual(0, failures, f"{failures} biography identity links inconsistent; details logged with trainerlog")


if __name__ == "__main__":
    unittest.main()
