"""Source accounting and date semantics for reviewed committee-term spells.

The legacy term fixtures and thin reviewed source references are sufficient
offline. No external source archives or neighboring repositories are needed.
"""

from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path
import unittest

import polars as pl
from trainerlog import get_logger

from .committee_integrity import date_bound
from provenance.committee import read_sources


LOGGER = get_logger("committee-term-integrity")
SOURCE = Path("test/data/reviewed_committee_terms.json")
EXTENSION = Path("test/data/reviewed_committee_term_extension.json")
TERM_1982 = Path("provenance/committee/reviews/term-1982-1985.json")
CONTINUITY = Path("provenance/parliamentary-mandates/1982-1985-continuity.json")


def retained_mandate_claims(spells):
    """Narrow, source-bound exceptions for elected MPs on approved leave."""
    review = json.loads(CONTINUITY.read_text())
    catalog = read_sources()
    granted = review["retained_mp_leaves"]
    valid = set()
    for spell in spells:
        leave = spell.get("retained_mp_leave")
        if not leave or leave not in granted or leave["source_id"] not in catalog:
            continue
        source, row = catalog[leave["source_id"]], spell["membership"]
        if (source.get("kind") == "approved_mp_leave" and spell["initial"]
                and source.get("person_id") == leave["person_id"] == row["person_id"]
                and source.get("start") == leave["start"] <= row["start"] <= leave["end"] == source.get("end")):
            valid.add(spell["claim_id"])
    return valid


def reviewed_terms():
    """Project the thin term review without duplicating its shared source text."""
    terms = [dict(json.loads(path.read_text()), census_term="1979-1982") for path in (SOURCE, EXTENSION)]
    source = json.loads(TERM_1982.read_text())
    catalog = read_sources()
    source["spells"] = source.pop("positions")
    source["events"] = [catalog[identifier] for identifier in source["events"].values()]
    source["census_term"] = "1982-1985"
    terms.append(source)
    return terms


class CommitteeTermIntegrity(unittest.TestCase):
    def test_continuity_replacement_periods_and_alias_retain_their_sources(self):
        """Guarantee: source-reviewed replacement periods and spelling keep their identities.

        Data: member_of_parliament.csv and name.csv; thin continuity review and
        content-addressed sources. Compare documented intervals at their actual
        precision, including three session/year-only ends. These are MP periods,
        not inferred committee ends. References: Enkammarriksdagen volumes 1/2,
        the PDF pages and file hashes recorded in the review. Failures count rows.
        """
        review = json.loads(CONTINUITY.read_text())
        catalog = read_sources()
        failures = 0
        mp_rows = review["mp_additions"] + [{"row":r["after"],"sources":r["sources"]} for r in review["mp_refinements"]]
        for filename, required in (("member_of_parliament", mp_rows),
                                   ("name", [review["name_alias"]])):
            table = pl.read_csv(f"data/{filename}.csv", infer_schema=False)
            published = set(table.iter_rows())
            for entry in required:
                if (tuple(entry["row"][k] for k in table.columns) not in published
                        or not entry["sources"] or any(s not in catalog for s in entry["sources"])):
                    failures += 1
                    LOGGER.error("Missing or reassigned sourced replacement/alias: %s", entry["row"])
        LOGGER.info("Checked %s added/corrected MP periods and one source spelling; %s row failures", len(mp_rows), failures)
        self.assertEqual(0, failures, f"{failures} sourced replacement/alias rows changed; details logged with trainerlog")

    def test_continuity_refinements_and_held_positions_remain_accounted_for(self):
        """Guarantee: reviewed end refinements do not change identities, roles or starts.

        Data: thin 1982 term and continuity reviews. Each refinement changes only
        the end and agrees with the term's source-basis decision. Rename support
        stays on the historical Bostadsutskottet entity and retains year precision;
        it cannot attach to the different Civilutskottet created in 2006. All 34
        original holds remain resolved or held. Failures count reviewed decisions.
        """
        review, term = json.loads(CONTINUITY.read_text()), json.loads(TERM_1982.read_text())
        positions = {p["claim_id"]: p for p in term["positions"]}
        failures = 0
        catalog = read_sources()
        for change in review["refinements"]:
            after, before = change["after"], change["before"]
            spell = positions.get(change["claim_id"], {})
            valid = (spell.get("membership") == after and spell.get("end_review") == change["end_review"]
                and all(before[k] == after[k] for k in before if k != "end"))
            rename = change["end_review"].get("continuity_source")
            if rename:
                valid &= (rename in catalog and catalog[rename].get("committee_id") == after["committee_id"]
                          == "i-Pe7qrS2HBQEA3mhF4ARDnH" and after["end"] == "1985")
            if not valid:
                failures += 1
                LOGGER.error("Continuity decision contradicts its appointment/source: %s", change["claim_id"])
        resolved = review["resolved_positions"]
        valid_ids = {p["claim_id"] for p in resolved}
        failures += len(valid_ids - set(positions))
        self.assertEqual(34, len(valid_ids) + len(term["held"]), "Original held election census changed")
        self.assertEqual(review["remaining_held"], term["held"], "Remaining identity holds changed without review")
        LOGGER.info("Checked %s refinements and %s resolved elections; %s decision failures", len(review["refinements"]), len(resolved), failures)
        self.assertEqual(0, failures, f"{failures} continuity decisions changed; details logged with trainerlog")

    def test_approved_leave_is_not_fabricated_as_active_mp_service(self):
        """Guarantee: the three reviewed leave-day elections retain office, not active service.

        Data: the term review, source-bound approved leave grants and MP data.
        Lars-Ake Larsson and Marie-Ann Johansson were elected MPs on approved
        leave on 12 October 1982. Their active-service gaps must not be filled
        merely to pass an election-day identity filter. Failures count elections.
        References: protocol 1982/83:1, approved leave and replacement announcements.
        """
        spells = json.loads(TERM_1982.read_text())["positions"]
        expected = [s for s in spells if s.get("retained_mp_leave")]
        authorized = retained_mandate_claims(expected)
        mandates = pl.read_csv("data/member_of_parliament.csv", infer_schema=False)
        failures = 0
        for s in expected:
            row = s["membership"]
            active = mandates.filter((pl.col("person_id") == row["person_id"]) & (pl.col("role") == "ledamot") &
                (date_bound("start") <= pl.lit(row["start"]).str.to_date()) &
                (date_bound("end", True) >= pl.lit(row["start"]).str.to_date()))
            if s["claim_id"] not in authorized or active.height:
                failures += 1
                LOGGER.error("Approved leave lost its office/service distinction: %s", s["claim_id"])
        self.assertEqual(3, len(expected), "The reviewed leave-election census changed")
        LOGGER.info("Checked three retained-MP leave elections; %s unsupported service/identity changes", failures)
        self.assertEqual(0, failures, f"{failures} retained-MP leave elections changed; details logged with trainerlog")

    def test_allgulander_source_spelling_retains_the_existing_person(self):
        """Guarantee: the reviewed Swante Allgulander alias stays on the existing MP.

        Data: name.csv. The source spelling is a non-primary alias of the person
        already named Svante Allgullander, not a newly created identity. The
        1982 leave, party and service dates identify that same person. Existing
        appointment and mandate tests own service-date validation.
        References: Enkammarriksdagen volume 2, page 498; protocols 1981/82:42
        and 1981/82:79. Failures count required alias rows, not name variants.
        """
        names = pl.read_csv("data/name.csv", infer_schema=False)
        expected = ("i-4GBx7Um4NanvqMymTXXzRL", "Swante Allgulander", "false")
        failures = int(expected not in set(names.select("person_id", "name", "primary_name").iter_rows()))
        if failures:
            LOGGER.error("Missing or reassigned non-primary Allgulander alias: %s", expected)
        LOGGER.info("Checked one reviewed source alias; %s missing or reassigned", failures)
        self.assertEqual(0, failures, f"{failures} required Allgulander alias rows missing or reassigned; details logged with trainerlog")

    def test_resolved_positions_retain_their_reviewed_appointment_keys(self):
        """Guarantee: resolved held positions retain the appointments recorded in the fixture.

        Data: reviewed_committee_term_extension.json. Its resolution summaries
        and appointment spells must agree, accounting for all 90 originally
        held positions. This does not validate the external MP correction
        reviews referenced by the fixture. Published rows and contemporary
        mandates are checked separately. Failures count resolved positions.
        """
        source = json.loads(EXTENSION.read_text())
        resolved = [s for s in source["spells"] if s.get("resolution_batch")]
        summaries = {p["claim_id"]: p for block in source["resolutions"] for p in block["resolved_positions"]}
        self.assertEqual(90, len(resolved) + len(source["held"]), "The original held-position census must remain complete")
        self.assertEqual({s["claim_id"] for s in resolved}, set(summaries), "Resolved appointments and their summaries must agree")
        failures = 0
        for spell in resolved:
            summary = summaries[spell["claim_id"]]
            valid = (summary["membership"] == spell["membership"]
                     and summary["position_id"] == spell["resolved_position_id"]
                     and summary["election_event"] == spell["election_event"])
            if not valid:
                failures += 1
                LOGGER.error("Resolved position contradicts its appointment summary: %s", spell["resolved_position_id"])
        LOGGER.info("Checked %s resolved positions; %s inconsistent appointments", len(resolved), failures)
        self.assertEqual(0, failures, f"{failures} resolved positions contradict their summaries; details logged with trainerlog")

    def test_reviewed_term_memberships_keep_dates_and_roles(self):
        """Guarantee: every reviewed term appointment remains published at its stated precision.

        Data: reviewed term fixtures and committee_membership.csv. Compare all five
        membership fields exactly, including unknown ends. Later supported date
        refinements must update the affected fixture as well as the data. This
        protects the tracked appointments, not an external curation ledger.
        Failures count appointment claims; CSVW owns structural validation.
        """
        rows = pl.read_csv("data/committee_membership.csv", infer_schema=False)
        published = set(rows.iter_rows())
        failures, total = 0, 0
        for source in reviewed_terms():
            for spell in source["spells"]:
                total += 1
                expected = tuple(spell["membership"][key] for key in rows.columns)
                if expected not in published:
                    failures += 1
                    LOGGER.error("Missing or altered reviewed term appointment: %s", spell["claim_id"])
        LOGGER.info("Checked %s reviewed appointments; %s missing or altered", total, failures)
        self.assertEqual(0, failures, f"{failures} reviewed appointments missing or altered; details logged with trainerlog")

    def test_reviewed_election_positions_are_all_accounted_for(self):
        """Guarantee: each reviewed opening roster and subsequent change is accounted for.

        Data: reviewed term fixtures, checked against the original scans. The
        openings contain 482 positions in 1979 and 496 in 1982; substitute
        allocations differ by committee and term and are never assumed uniform.
        Every later position must be accepted or explicitly held. This is a
        source-position census, not a claim that this many new people or
        uninterrupted service spells were discovered. Failures count events.
        """
        committees, opening_total, total = {}, Counter(), 0
        for source in reviewed_terms():
            term = source["census_term"]
            committees.setdefault(term, set())
            spells, held = source["spells"], source["held"]
            initial = [s for s in spells if s["initial"]]
            expected = source.get("initial_expected_by_committee") or {source["committee_id"]: source["initial_expected"]}
            counts = Counter((s["membership"]["committee_id"], s["role"]) for s in initial)
            counts.update((s["committee_id"], s["role"]) for s in held if s["initial"])
            self.assertEqual({(c, r): n for c, roles in expected.items() for r, n in roles.items()}, dict(counts))
            for committee in expected:
                accepted = [s for s in initial if s["membership"]["committee_id"] == committee]
                self.assertEqual(len(accepted), len({s["membership"]["person_id"] for s in accepted}))
            self.assertFalse(committees[term].intersection(expected), "A committee must not be counted twice within a term")
            committees[term].update(expected)
            opening_total[term] += sum(counts.values())
            self.assertEqual(source["election_positions_expected"], len(spells) + len(held))
            counts = Counter([s["election_event"] for s in spells] +
                             [s.get("election_event") or s["event"] for s in held])
            failures = 0
            for event in source["events"]:
                if event["kind"] == "election_result" and counts[event["id"]] != event["expected_positions"]:
                    failures += 1
                    LOGGER.error("Unaccounted election positions: %s; observed %s", event["id"], counts[event["id"]])
            self.assertEqual(0, failures, f"{failures} election events lost positions; details logged with trainerlog")
            total += len(spells) + len(held)
        LOGGER.info("Checked %s election positions across %s terms", total, len(committees))
        for term in committees:
            self.assertEqual(16, len(committees[term]))
            self.assertEqual({"1979-1982": 482, "1982-1985": 496}[term], opening_total[term])

    def test_reviewed_term_dates_follow_their_stated_source_basis(self):
        """Guarantee: dates preserve confirmed elections, effective clauses and reviewed precision.

        Data: reviewed term fixtures. A confirmed election constitutes appointment
        unless an explicit effective-date clause defers its start.
        End months/years deliberately retain uncertainty. Inclusive ends precede
        an explicitly effective departure/return by one day, not its reporting
        day. Temporary appointments cannot acquire the general term end. Unknown
        ends remain null, not continuous service. Failures count service spells.
        References: historical RO provisions and source events in the fixture.
        """
        failures = 0
        total = 0
        for source in reviewed_terms():
            events = {e["id"]: e for e in source["events"]}
            for spell in source["spells"]:
                row, review = spell["membership"], spell["end_review"]
                election = events[spell["election_event"]]
                valid = election["kind"] == "election_result" and row["start"] == election.get("effective_date", election["date"])
                method, expected = review["method"], None
                if method != "unknown":
                    boundary = events[review["events"][0]]
                    valid &= not (spell["temporary"] and boundary["kind"] == "next_full_election")
                    if method == "event_month":
                        expected = boundary["date"][:7]
                    elif method == "event_year":
                        expected = boundary["date"][:4]
                    elif method == "before_effective_day":
                        expected = (date.fromisoformat(boundary["effective_date"]) - timedelta(days=1)).isoformat()
                        valid &= boundary["kind"] in {"approved_resignation", "return_announcement", "replacement_change"}
                    else:
                        valid = False
                    precision = review.get("precision", "day")
                    valid &= precision in {"day", "month", "year"}
                    if expected:
                        expected = expected[:{"day": 10, "month": 7, "year": 4}.get(precision, 10)]
                valid &= row["end"] == expected and bool(review["reason"])
                if not valid:
                    failures += 1
                    LOGGER.error("Service dates contradict reviewed source basis: %s", spell)
            for position in source["held"]:
                if "effective_start" not in position:
                    continue
                election = events[position["election_event"]]
                if position["effective_start"] != election.get("effective_date", election["date"]):
                    failures += 1
                    LOGGER.error("Held position lost its deferred-start evidence: %s", position["name_as_printed"])
            total += len(source["spells"])
        LOGGER.info("Checked %s reviewed spells; %s have unsupported boundaries", total, failures)
        self.assertEqual(0, failures, f"{failures} committee spells have unsupported boundaries; details logged with trainerlog")


    def test_dated_committee_elections_have_contemporary_mp_mandates(self):
        """Guarantee: dated appointments have MP service or a sourced retained-office leave.

        Data: term spells and member_of_parliament.csv. Unlike the roster-year
        guarantee, these starts must match an exact day. Three opening elections
        of elected MPs on approved leave have source-bound exceptions; active
        service and holding an elected mandate are not interchangeable.
        This does not infer uninterrupted service from an MP mandate, nor require
        a leave-taking MP to surrender their original committee appointment.
        Failures count dated appointment claims; unresolved identities stay held.
        """
        spells = [s for source in reviewed_terms() for s in source["spells"]]
        starts = pl.DataFrame([{**s["membership"], "claim_id": s["claim_id"]} for s in spells])
        mandates = pl.read_csv("data/member_of_parliament.csv", infer_schema=False)
        joined = starts.select("claim_id", "person_id", pl.col("start").alias("election_day")).join(mandates, on="person_id")
        valid = joined.filter((pl.col("role") == "ledamot") &
            (date_bound("start") <= pl.col("election_day").str.to_date()) &
            (date_bound("end", True) >= pl.col("election_day").str.to_date()))
        authorized = set(valid["claim_id"]) | retained_mandate_claims(spells)
        missing = starts.filter(~pl.col("claim_id").is_in(sorted(authorized)))
        LOGGER.info("Checking %s dated committee appointments against MP mandates", starts.height)
        for row in missing.to_dicts():
            LOGGER.error("Dated committee appointment lacks contemporary MP mandate: %s", row)
        self.assertEqual(0, missing.height,
                         f"{missing.height} dated appointments lack contemporary mandates; details logged with trainerlog")
