"""Semantic bounds for annual historical committee identities."""

import unittest
from provenance.committee import read_roster

import polars as pl
from trainerlog import get_logger


LOGGER = get_logger("committee-session-integrity")


class CommitteeSessionIntegrity(unittest.TestCase):
    def test_session_scoped_rosters_match_committee_year_and_chamber(self):
        """Guarantee: session-specific committees retain their stated year and chamber.

        Data: committee.csv and provenance/committee/observations.csv. An annual
        temporary or special body cannot acquire evidence from another year;
        a chamber-specific body cannot acquire evidence from the other chamber.
        Session labels constrain identity, not service dates. Failures count
        source observations and are logged for offline review.
        """
        committees = pl.read_csv("data/committee.csv", infer_schema=False).select("committee_id", "committee")
        sources = read_roster()
        scoped = sources.join(committees, on="committee_id").with_columns(
            pl.col("committee").str.extract(r"\(((?:18|19)\d\d) (?:lagtima|urtima)(?: [AB])?\)$", 1).alias("session_year")
        ).filter(pl.col("session_year").is_not_null())
        invalid = scoped.filter(
            (pl.col("year") != pl.col("session_year")) |
            (pl.col("committee").str.starts_with("Första kammarens ") & (pl.col("chamber") != "FK")) |
            (pl.col("committee").str.starts_with("Andra kammarens ") & (pl.col("chamber") != "AK")))
        LOGGER.info("Checking %s session-scoped roster observations", scoped.height)
        for row in invalid.to_dicts():
            LOGGER.error("Committee session contradicts roster observation: %s", row)
        LOGGER.info("Checked %s session-scoped observations; %s inconsistent", scoped.height, invalid.height)
        self.assertEqual(0, invalid.height,
                         f"{invalid.height} roster observations contradict committee sessions; details logged with trainerlog")


if __name__ == "__main__":
    unittest.main()
