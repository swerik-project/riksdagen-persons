"""Small mutations proving record-supported MP corrections are release-blocking."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

import polars as pl

from . import mandates as mandate_integrity
from . import committee_term_integrity as term_integrity


class MandateRecordRegressions(unittest.TestCase):
    def test_missing_reviewed_mandate_turns_the_gate_red(self):
        """Guarantee: deleting a repaired service segment cannot pass the source gate."""
        review = json.loads(Path("provenance/parliamentary-mandates/1979-1982.json").read_text())
        target = review["changes"][0]["after"]
        original = pl.read_csv
        def read(path, *args, **kwargs):
            frame = original(path, *args, **kwargs)
            if str(path) == "data/member_of_parliament.csv":
                return pl.DataFrame([r for r in frame.to_dicts() if r != target], schema=frame.schema)
            return frame
        with patch.object(pl, "read_csv", read), self.assertRaises(AssertionError):
            mandate_integrity.Test().test_reviewed_parliamentary_intervals_retain_their_recorded_corrections()

    def test_restoring_susanns_reversed_row_turns_the_gate_red(self):
        """Guarantee: keeping the old reversed interval beside its repair is rejected."""
        review = json.loads(Path("provenance/parliamentary-mandates/1979-1982.json").read_text())
        change = next(c for c in review["changes"] if c["name"] == "Susann Torgerson")
        original = pl.read_csv
        def read(path, *args, **kwargs):
            frame = original(path, *args, **kwargs)
            if str(path) == "data/member_of_parliament.csv":
                return pl.DataFrame(frame.to_dicts() + [change["before"]], schema=frame.schema)
            return frame
        with patch.object(pl, "read_csv", read), self.assertRaises(AssertionError):
            mandate_integrity.Test().test_reviewed_parliamentary_intervals_retain_their_recorded_corrections()

    def test_deleting_the_mandate_source_cannot_unprotect_a_resolution(self):
        """Guarantee: removing a review case leaves its committee resolution visibly unsupported."""
        review = json.loads(Path("provenance/parliamentary-mandates/1979-1982.json").read_text())
        review["changes"].pop(0)
        original = Path.read_text
        def read(path, *args, **kwargs):
            return json.dumps(review) if str(path) == "provenance/parliamentary-mandates/1979-1982.json" else original(path, *args, **kwargs)
        with patch.object(Path, "read_text", read), self.assertRaises(AssertionError):
            term_integrity.CommitteeTermIntegrity().test_resolved_positions_retain_their_parliamentary_evidence()
