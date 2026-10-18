"""Mandate and party support for reviewed committee election identities.

The retained identity fixture is compared with published mandate and party
tables. These checks do not cover every committee membership in the corpus.
"""

import unittest

import polars as pl
from trainerlog import get_logger

from .committee_integrity import date_bound


LOGGER = get_logger("committee-roster-integrity")


class CommitteeRosterIntegrity(unittest.TestCase):
    def test_reviewed_election_identities_have_contemporary_mandates(self):
        """Guarantee: election identities retain a mandate at the observed time.

        Data: reviewed_committee_election_identities.json and MP mandates.
        The fixture preserves an exact election day where known, otherwise
        the source's calendar year. These comparison bounds are observation
        precision, never committee service dates. Failures count source claims.
        This does not check observations in an external roster archive.
        """
        sources = pl.read_json("test/data/reviewed_committee_election_identities.json", infer_schema_length=None)
        mandates = pl.read_csv("data/member_of_parliament.csv", infer_schema=False)
        joined = sources.join(mandates, on="person_id", how="left")
        valid = joined.filter((pl.col("role") == "ledamot") &
            (date_bound("start") <= date_bound("observed_end", True)) &
            (date_bound("end", True) >= date_bound("observed_start")))
        missing = sources.filter(~pl.col("claim_id").is_in(valid["claim_id"].implode()))
        LOGGER.info("Checking contemporaneous mandates for %s recovered election claims", sources.height)
        for row in missing.to_dicts():
            LOGGER.error("Recovered election identity lacks contemporary mandate: %s", row)
        LOGGER.info("Checked %s recovered election claims; %s lack a contemporary mandate", sources.height, missing.height)
        self.assertEqual(0, missing.height,
            f"{missing.height} recovered election identities lack contemporary mandates; details logged with trainerlog")

    def test_party_disambiguated_election_identities_retain_dated_party_evidence(self):
        """Guarantee: party-disambiguated election identities keep dated party support.

        Data: the reviewed election identity fixture and party_affiliation.csv.
        Only claims that needed the printed party to choose between names are
        checked. Unknown party dates cannot establish an identity at that time.
        Failures count source claims; this does not change party affiliations.
        """
        sources = pl.read_json("test/data/reviewed_committee_election_identities.json", infer_schema_length=None).filter(
            pl.col("party_required")).rename({"party": "printed_party"})
        parties = pl.read_csv("data/party_affiliation.csv", infer_schema=False)
        joined = sources.join(parties, on="person_id", how="left")
        valid = joined.filter((pl.col("party") == pl.col("printed_party")) &
            (date_bound("start") <= date_bound("observed_end", True)) &
            (date_bound("end", True) >= date_bound("observed_start")))
        missing = sources.filter(~pl.col("claim_id").is_in(valid["claim_id"].implode()))
        LOGGER.info("Checking dated party evidence for %s disambiguated election claims", sources.height)
        for row in missing.to_dicts():
            LOGGER.error("Party-disambiguated election identity lost dated party evidence: %s", row)
        LOGGER.info("Checked %s party-disambiguated claims; %s lost evidence", sources.height, missing.height)
        self.assertEqual(0, missing.height,
            f"{missing.height} election identities lack required dated party evidence; details logged with trainerlog")

if __name__ == "__main__":
    unittest.main()
