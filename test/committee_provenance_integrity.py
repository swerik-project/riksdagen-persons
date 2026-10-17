"""Integrity of the single canonical committee evidence graph, not copied stores."""

from collections import Counter
import json
from pathlib import Path
import unittest

import polars as pl
from trainerlog import get_logger

from provenance.committee import CLAIMS, ROSTER, MEMBERSHIP, read_claims, read_roster, read_sources


LOGGER = get_logger("committee-provenance-integrity")


class CommitteeProvenanceIntegrity(unittest.TestCase):
    def test_observations_have_exactly_one_curation_and_a_published_membership(self):
        """Guarantee: each observation belongs to one accepted, published fact.

        Data: canonical provenance tables and committee_membership.csv. Check
        references, not agreement between two copies of quotations. Unknown
        dates remain null. Failures count observation claim IDs. The shared
        source reader also rejects duplicate or altered content-addressed IDs.
        """
        observations = read_roster()
        claims = read_claims()
        expected = {}
        duplicate = set()
        for claim in claims:
            for cid in claim.get("roster_observations", []):
                if cid in expected:
                    duplicate.add(cid)
                expected[cid] = tuple(claim["membership"][k] for k in MEMBERSHIP)
        actual = {r["claim_id"]: r for r in observations.to_dicts()}
        counts = Counter(observations["claim_id"])
        published = set(pl.read_csv("data/committee_membership.csv", infer_schema=False).select(MEMBERSHIP).iter_rows())
        failures = 0
        for cid in sorted(set(expected) | set(actual)):
            row = actual.get(cid)
            key = tuple(row[k] for k in MEMBERSHIP) if row else None
            if cid in duplicate or counts[cid] != 1 or key != expected.get(cid) or key not in published:
                failures += 1
                LOGGER.error("Orphaned, duplicated or mismatched committee observation: %s", cid)
        LOGGER.info("Checked %s canonical observations; %s broken links", observations.height, failures)
        self.assertEqual(0, failures, f"{failures} observation claim IDs have broken evidence links; details logged with trainerlog")

    def test_source_and_curation_catalogs_are_complete(self):
        """Guarantee: thin membership rows have unique metadata and valid sources.

        Data: memberships.csv and the sharded source/curation catalogs. A source
        content hash detects accidental quotation edits, not historical truth.
        Preserve all metadata, including unlinked historical source context.
        Failures count accepted fact IDs; source corruption raises explicitly.
        """
        sources = read_sources()
        rows = pl.read_csv(CLAIMS, infer_schema=False)
        ids = rows["curation_id"].to_list()
        metadata = []
        for path in sorted((CLAIMS.parent / "curations").glob("*.jsonl")):
            metadata.extend(json.loads(line) for line in path.read_text().splitlines())
        counts = Counter(r["curation_id"] for r in metadata)
        self.assertEqual(len(ids), len(set(ids)), "Duplicate accepted membership IDs")
        self.assertEqual(set(ids), set(counts), "Accepted facts and curation metadata have orphaned references")
        failures = 0
        for row in metadata:
            citation = row["metadata"].get("service_source")
            if counts[row["curation_id"]] != 1 or (citation and citation["source_id"] not in sources):
                failures += 1
                LOGGER.error("Accepted fact lost source or unique metadata: %s", row["curation_id"])
        LOGGER.info("Checked %s fact metadata records; %s broken links", len(metadata), failures)
        self.assertEqual(0, failures, f"{failures} accepted facts have broken source metadata; details logged with trainerlog")

    def test_test_fixtures_and_provenance_do_not_regrow_large_snapshots(self):
        """Guarantee: fixtures stay below 5 MiB and evidence files below 10 MiB.

        Data: test/data and provenance/committee. These explicit size budgets
        prevent the former 60 MiB duplicate ledger from silently returning.
        If canonical data outgrows a budget, partition by a meaningful domain
        boundary and update readers; do not discard observations or quotations.
        Failures count files. Published corpus data is not size-limited here.
        """
        failures = 0
        for directory, limit in ((Path("test/data"), 5 * 1024**2), (CLAIMS.parent, 10 * 1024**2)):
            for path in directory.rglob("*"):
                if path.is_file() and path.stat().st_size > limit:
                    failures += 1
                    LOGGER.error("Oversized fixture/evidence file: %s (%s bytes)", path, path.stat().st_size)
        self.assertEqual(0, failures, f"{failures} fixture/evidence files exceed size budgets; details logged with trainerlog")
