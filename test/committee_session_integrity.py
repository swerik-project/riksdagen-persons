"""Semantic bounds for annual historical committee identities."""

import json
from pathlib import Path
import unittest

import polars as pl
from trainerlog import get_logger


LOGGER = get_logger("committee-session-integrity")


class CommitteeSessionIntegrity(unittest.TestCase):
    def test_session_scoped_rosters_match_committee_year_and_chamber(self):
        """Guarantee: session-specific committees retain their stated year and chamber.

        Data: committee.csv and reviewed_committee_roster_entities.json. An annual
        temporary or special body cannot contradict its tracked source's year;
        a chamber-specific body cannot acquire evidence from the other chamber.
        Session labels constrain identity, not service dates. Failures count
        reviewed entity citations, not observations in a separate roster archive.
        """
        committees = pl.read_csv("data/committee.csv", infer_schema=False).select("committee_id", "committee")
        references = json.loads(Path("test/data/reviewed_committee_roster_entities.json").read_text())
        sources = pl.DataFrame([{"committee_id": r["entity"]["committee_id"],
                                 "year": str(r["source"]["year"]), "chamber": r["source"]["chamber"]}
                                for r in references])
        scoped = sources.join(committees, on="committee_id").with_columns(
            pl.col("committee").str.extract(r"\(((?:18|19)\d\d) (?:lagtima|urtima)(?: [AB])?\)$", 1).alias("session_year")
        ).filter(pl.col("session_year").is_not_null())
        invalid = scoped.filter(
            (pl.col("year") != pl.col("session_year")) |
            (pl.col("committee").str.starts_with("Första kammarens ") & (pl.col("chamber") != "FK")) |
            (pl.col("committee").str.starts_with("Andra kammarens ") & (pl.col("chamber") != "AK")))
        LOGGER.info("Checking %s session-scoped entity citations", scoped.height)
        for row in invalid.to_dicts():
            LOGGER.error("Committee session contradicts its reviewed citation: %s", row)
        LOGGER.info("Checked %s session-scoped citations; %s inconsistent", scoped.height, invalid.height)
        self.assertEqual(0, invalid.height,
                         f"{invalid.height} entity citations contradict committee sessions; details logged with trainerlog")


if __name__ == "__main__":
    unittest.main()
