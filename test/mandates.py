"""
Test that known MP start/end dates that have been manually verified do not change in the metadata.
"""
from datetime import datetime
from pytest_cfg_fetcher.fetch import fetch_config
import pandas as pd
import unittest
import warnings




class DateErrorWarning(Warning):
    def __init__(self, date_error):
        self.message = f"Date Error: {date_error}"

    def __str__(self):
        return self.message



class Test(unittest.TestCase):

    def fetch_known_mandate_dates(self):
        return pd.read_csv("test/data/mandate-dates.csv", sep=';')


    def fetch_mep_meta(self):
        return pd.read_csv("data/member_of_parliament.csv")


    def test_manually_checked_mandates(self):
        """Guarantee: manually reviewed MP endpoints remain on the recorded person.

        Data: test/data/mandate-dates.csv and member_of_parliament.csv. Each
        reference row protects one start or end, not an inferred continuous
        career. Bager's 1981-1982 endpoints follow Enkammarriksdagen volume 2,
        pages 79 and 503, with the first session day from protocol 1981/82:1.
        Allgulander's existing February-March 1982 period is corroborated by
        volume 2, page 498 and the approved leave and actual return notices.
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
