"""
Test that known MP start/end dates that have been manually verified do not change in the metadata.
"""
from datetime import datetime
from pytest_cfg_fetcher.fetch import fetch_config
import json
from pathlib import Path
import pandas as pd
import polars as pl
import unittest
import warnings
from trainerlog import get_logger




class DateErrorWarning(Warning):
    def __init__(self, date_error):
        self.message = f"Date Error: {date_error}"

    def __str__(self):
        return self.message



class Test(unittest.TestCase):

    def test_reviewed_parliamentary_intervals_retain_their_recorded_corrections(self):
        """Guarantee: reviewed record-supported MP intervals cannot be lost or reverted.

        Data: provenance/parliamentary-mandates/1979-1982.json and the published
        MP table. These 54 reviewed changes include new authorized service
        segments and five replacements of incorrect rows. Segments need not
        be maximal careers: later extensions remain separate evidence. A coarse
        boundary must not gain invented day precision. Unknown districts stay
        unknown. CSVW owns key and format validation; the legacy guarantee below
        continues protecting earlier manually reviewed individual endpoints.
        Failures count reviewed interval changes, logged with trainerlog.
        """
        logger = get_logger("record-mandate-integrity")
        review = json.loads(Path("provenance/parliamentary-mandates/1979-1982.json").read_text())
        published = pl.read_csv("data/member_of_parliament.csv", infer_schema=False)
        rows = published.to_dicts()
        failures = 0
        for change in review["changes"]:
            valid = change["after"] in rows and (not change["before"] or change["before"] not in rows)
            valid &= bool(change["reason"]) and bool(change["citations"])
            for identifier in change["citations"]:
                citation = review["citations"].get(identifier)
                valid &= bool(citation) and bool(citation.get("excerpt")) and bool(citation.get("paragraphs"))
            if not valid:
                failures += 1
                logger.error("Reviewed parliamentary interval lost or reverted: %s", change)
        logger.info("Checked %s reviewed MP interval changes; %s inconsistent", len(review["changes"]), failures)
        self.assertEqual(54, len(review["changes"]), "The reviewed 54-interval census lost a source-supported change")
        self.assertEqual(0, failures, f"{failures} reviewed MP intervals lost support; details logged with trainerlog")

    def fetch_known_mandate_dates(self):
        return pd.read_csv("test/data/mandate-dates.csv", sep=';')


    def fetch_mep_meta(self):
        return pd.read_csv("data/member_of_parliament.csv")


    def test_manually_checked_mandates(self):
        """
        Find each manual mandate in the data... make sure dates are same.
        """
        mep = self.fetch_mep_meta()
        df = self.fetch_known_mandate_dates()
        config = fetch_config("mandates")
        counter = 0
        rows = []
        cols = ["person_id", "date", "type"]
        for i, r in df.iterrows():
            fil = mep.loc[(mep['person_id'] == r["person_id"]) & (mep[r["type"].lower()] == r['date'])]
            if fil.empty:
                counter += 1
                rows.append([r["person_id"], r["date"], r["type"]])
                warnings.warn(f"({r['type']}): {r['date']}, {r['person_id']}" , DateErrorWarning)
        if len(rows) > 0:
            if config and config['write_errors']:
                now = datetime.now().strftime("%Y%m%d-%H%M")
                out = pd.DataFrame(rows, columns=cols)
                out.to_csv(f"{config['test_out_dir']}{now}_mandates-test.csv", index=False)

        self.assertEqual(counter, 0)




if __name__ == '__main__':
    unittest.test()
