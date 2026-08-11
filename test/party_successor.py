#!/usr/bin/env python3
"""
Validate the normalized party successor table.

Corpus guarantee:
`data/party_successor.csv` is the authoritative normalized table for party
succession links, with one SWERIK party successor relation per row.

Why this matters:
`successor_id` and `swerik_successor` in `data/party.csv` are deprecated
compatibility columns. During the transition they may remain in the CSV, but
new code should be able to rely on `data/party_successor.csv` without parsing
pipe-separated successor values from `data/party.csv`.

Input data:
The test compares `data/party_successor.csv` with party identifiers and the
temporary deprecated `swerik_successor` compatibility column in
`data/party.csv`.

Documentation:
See `README.md` for the table descriptions and
`the-swedish-parliament-corpus/docs/decisions/decision-0021_writing-data-integrity-tests.md`
for the data integrity test style guide.
"""

import unittest

import pandas as pd


class TestPartySuccessor(unittest.TestCase):
    def _load_data(self):
        party_names = pd.read_csv("data/party.csv")
        successors = pd.read_csv("data/party_successor.csv")
        return party_names, successors

    def _successor_edges_from_deprecated_column(self, party_names):
        edges = set()
        for _, row in party_names.iterrows():
            if pd.isna(row["swerik_successor"]):
                continue
            for successor in str(row["swerik_successor"]).split("|"):
                successor = successor.strip()
                if successor:
                    edges.add((row["swerik_party_id"], successor))
        return edges

    def test_successor_table_matches_deprecated_party_csv_column(self):
        """
        Allow deprecated successor columns temporarily while requiring the
        normalized successor table to preserve the same SWERIK-ID edges.
        """
        party_names, successors = self._load_data()

        expected_columns = ["swerik_party_id", "successor_swerik_party_id"]
        self.assertEqual(
            list(successors.columns),
            expected_columns,
            "data/party_successor.csv must have columns "
            f"{expected_columns}; found {list(successors.columns)}")

        duplicated_party_ids = (
            party_names.loc[
                party_names["swerik_party_id"].duplicated(),
                "swerik_party_id"
            ]
            .dropna()
            .unique()
            .tolist()
        )
        self.assertFalse(
            duplicated_party_ids,
            "data/party.csv must have unique swerik_party_id values; "
            f"found {len(duplicated_party_ids)} duplicates: "
            f"{duplicated_party_ids[:10]}")

        duplicated_successors = successors.loc[successors.duplicated()]
        self.assertTrue(
            duplicated_successors.empty,
            "data/party_successor.csv must not contain duplicate rows; "
            f"found {len(duplicated_successors)} duplicates: "
            f"{duplicated_successors.head(10).to_dict('records')}")

        party_ids = set(party_names["swerik_party_id"])
        source_ids = set(successors["swerik_party_id"])
        target_ids = set(successors["successor_swerik_party_id"])
        missing_source_ids = sorted(source_ids - party_ids)
        missing_target_ids = sorted(target_ids - party_ids)

        self.assertFalse(
            missing_source_ids,
            "All source IDs in data/party_successor.csv must exist in "
            "data/party.csv swerik_party_id; found "
            f"{len(missing_source_ids)} missing source IDs: "
            f"{missing_source_ids[:10]}")
        self.assertFalse(
            missing_target_ids,
            "All target IDs in data/party_successor.csv must exist in "
            "data/party.csv swerik_party_id; found "
            f"{len(missing_target_ids)} missing target IDs: "
            f"{missing_target_ids[:10]}")

        expected_edges = self._successor_edges_from_deprecated_column(
            party_names)
        actual_edges = set(
            zip(successors["swerik_party_id"],
                successors["successor_swerik_party_id"]))
        missing_edges = sorted(expected_edges - actual_edges)
        extra_edges = sorted(actual_edges - expected_edges)

        self.assertEqual(
            expected_edges,
            actual_edges,
            "data/party_successor.csv must match the deprecated "
            "data/party.csv swerik_successor links during the transition; "
            f"missing {len(missing_edges)} edges: {missing_edges[:10]}; "
            f"extra {len(extra_edges)} edges: {extra_edges[:10]}")


if __name__ == "__main__":
    unittest.main()
