#!/usr/bin/env python3
"""
Validate the normalized party successor table.

Corpus guarantee:
`data/party_successor.csv` is the authoritative normalized table for party
succession links, with one party successor relation per row.

Why this matters:
`successor_id` and `swerik_successor` in `data/party.csv` are deprecated
compatibility columns. During the transition they may remain in the CSV, but
new code should be able to rely on `data/party_successor.csv` without parsing
pipe-separated successor values from `data/party.csv`.

Input data:
The test compares `data/party_successor.csv` with party identifiers and the
temporary deprecated `swerik_successor` compatibility column in
`data/party.csv`. CSVW tests cover schema, primary-key, and foreign-key
integrity; this test covers successor-specific semantics.

Documentation:
See `README.md` for the table descriptions and
`the-swedish-parliament-corpus/docs/decisions/decision-0024_writing-data-integrity-tests.md`
for the data integrity test style guide.
"""

import unittest

import networkx as nx
import polars as pl

from trainerlog import get_logger

LOGGER = get_logger("test-party-successor")


SOCIALDEMOCRATERNA_ID = "i-VS8ddgxigwL5TceKtXGApS"
SOCIALDEMOKRATISKA_VANSTERGRUPPEN_ID = "i-SwzbNNYoyZYULLDiTu2zGP"


def successor_edges_from_deprecated_column(party_names):
    edges = set()
    rows = (
        party_names
        .select("swerik_party_id", "swerik_successor")
        .filter(pl.col("swerik_successor").is_not_null())
    )
    for party_id, successors in rows.iter_rows():
        for successor_id in successors.split("|"):
            successor_id = successor_id.strip()
            if successor_id:
                edges.add((party_id, successor_id))
    return edges


def successor_edges_from_table(successors):
    return set(successors.select("party_id", "successor_party_id").iter_rows())


def party_name_by_id(party_names):
    return dict(party_names.select("swerik_party_id", "party").iter_rows())


def successor_graph(successors):
    graph = nx.DiGraph()
    graph.add_edges_from(successor_edges_from_table(successors))
    return graph


def canonical_cycle(cycle):
    rotations = [
        tuple(cycle[i:] + cycle[:i])
        for i in range(len(cycle))
    ]
    return min(rotations)


ALLOWED_CYCLES = {
    canonical_cycle([
        SOCIALDEMOCRATERNA_ID,
        SOCIALDEMOKRATISKA_VANSTERGRUPPEN_ID,
    ])
}


class TestPartySuccessor(unittest.TestCase):

    def test_successor_table_matches_deprecated_party_csv_column(self):
        """
        Allow deprecated successor columns temporarily while requiring the
        normalized successor table to preserve the same SWERIK-ID edges.
        """
        party_names = pl.read_csv("data/party.csv")
        successors = pl.read_csv("data/party_successor.csv")

        expected_edges = successor_edges_from_deprecated_column(party_names)
        actual_edges = successor_edges_from_table(successors)
        missing_edges = sorted(expected_edges - actual_edges)
        extra_edges = sorted(actual_edges - expected_edges)

        self.assertEqual(
            expected_edges,
            actual_edges,
            "data/party_successor.csv must match the deprecated "
            "data/party.csv swerik_successor links during the transition; "
            f"missing {len(missing_edges)} edges: {missing_edges[:10]}; "
            f"extra {len(extra_edges)} edges: {extra_edges[:10]}")

    def test_no_unexpected_successor_cycles(self):
        party_names = pl.read_csv("data/party.csv")
        successors = pl.read_csv("data/party_successor.csv")

        names = party_name_by_id(party_names)
        graph = successor_graph(successors)
        cycles = list(nx.simple_cycles(graph))
        unexpected_cycles = []
        for cycle in cycles:
            cycle_names = ", ".join(names[party_id] for party_id in cycle)
            if canonical_cycle(cycle) in ALLOWED_CYCLES:
                LOGGER.info(f"Allowed cycle found: {cycle}\nNames: {cycle_names}")
            else:
                unexpected_cycles.append(cycle)
                LOGGER.error(f"Unexpected cycle found: {cycle}\nNames: {cycle_names}")

        self.assertEqual(
            len(unexpected_cycles),
            0,
            "The party successor graph has unexpected cycles; allowed cycles "
            f"are {sorted(ALLOWED_CYCLES)}, found {unexpected_cycles}")


if __name__ == "__main__":
    unittest.main()
