"""
Tests related to party affiliations.
"""
from datetime import datetime
from pytest_cfg_fetcher.fetch import fetch_config
import pandas as pd
import unittest
import warnings
from trainerlog import get_logger
import polars as pl
LOGGER = get_logger("test-party-affiliation")


class Test(unittest.TestCase):

    def write_err_df(self, name_str, lol, cols, outdir):
        now = datetime.now().strftime('%Y%m%d-%H%M%S')
        df = pd.DataFrame(lol, columns=cols)
        df.to_csv(f"{outdir}/{now}_{name_str}.csv", index=False)


    #@unittest.skip
    def test_independent_mp(self):
        """
        Guarantee: manually verified independent MP's are listed as such in the data
        """
        config = fetch_config("independent-mp")
        test_file = pl.read_csv("test/data/independent-mp.csv", separator=';')
        independent = pl.read_csv("data/explicit_no_party.csv")
        ind_swerik = set(independent['person_id'])

        errors = test_file.filter(~pl.col("person_id").is_in(ind_swerik))
        self.assertEqual(len(errors), 0, f"Some known independent MPs were not found in explicit_no_party.csv:\n{errors}")

    #@unittest.skip
    def test_party(self):
        """
        Guarantee: manually verified MP party affiliations exist in the data, up to an error thresold.
        """
        THRESHOLD_2026_10_19 = 2
        config = fetch_config("party-affiliation")
        test_file = pl.read_csv("test/data/known-party-affiliation.csv", separator=';')
        party_affiliation = pl.read_csv("data/party_affiliation.csv")

        # Convert year ranges to multiple rows with each year
        test_file = test_file.with_columns(pl.int_ranges("start", pl.col("end") + 1).alias("year"))
        test_w_year = test_file.filter(pl.col("year").is_not_null())
        test_w_year = test_w_year.explode("year")
        test_wo_year = test_file.filter(pl.col("year").is_null()).drop("year")
        test_file = pl.concat([test_w_year, test_wo_year], how="diagonal")
        test_file = test_file.drop("start", "end")

        bad_affil = []
        for r in test_file.unique().to_dicts():
            Q = party_affiliation.filter(pl.col('person_id') == r["person_id"])
            Q = Q.filter(pl.col('party_id') == r["party_id"])
            if r['year'] is not None:
                Q = Q.filter(pl.col("start").str.head(4) <= str(r['year'])[:4])
                Q = Q.filter(pl.col("end").str.head(4) >= str(r['year'])[:4])
            if len(Q) == 0:
                bad_affil.append([r[_] for _ in test_file.columns])
                LOGGER.error(f"Row: {r} in known-party-affiliation.csv not matched in party_affiliation.csv")
        if len(bad_affil) > 0:
            LOGGER.warning(f"{len(bad_affil)} mismatch(es) between party_affiliation.csv and {len(test_file)} known party affiliations.")
            if config and config["write-party-affil-err"]:
                self.write_err_df("unmatched-party-affiliations", bad_affil, test_file.columns, config["test_out_dir"])
        self.assertLessEqual(len(bad_affil), THRESHOLD_2026_10_19, f"{len(bad_affil)} incorrect party affiliations found")




if __name__ == '__main__':
    unittest.main()
