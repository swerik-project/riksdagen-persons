#!/usr/bin/env python3
"""
Check that everyone sitting (chair_mp) has a corresponding mandate (member_of_parliament / minister / speaker).
"""
from pyriksdagen.date_handling import yearize_mandates
from tqdm import tqdm
import pandas as pd
import unittest




class SittingWithNoRole(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super(SittingWithNoRole, cls).setUpClass()
        cls.mandates = yearize_mandates()
        cls.seats = pd.read_csv("data/chair_mp.csv")
        cls.missing_from_year = []
        cls.out_of_date_range = []


    @classmethod
    def tearDownClass(cls):
        if len(cls.missing_from_year) > 0:
            pd.DataFrame(cls.missing_from_year, columns=cls.seats.columns).to_csv("test/_test-results/sitting-wout-mandate.tsv", sep='\t')


    def test_sitting_is_mop_in_parliament_yeat(self):
        for i, r in tqdm(self.seats.iterrows(), total=len(self.seats)):
            if pd.isna(r["person_id"]) or len(r["person_id"]) == 0:
                continue
            if len(self.mandates.loc[
                                        (self.mandates["person_id"] == r["person_id"]) &
                                        (self.mandates["parliament_year"] == r["parliament_year"])
                                    ]) == 0:
                self.missing_from_year.append(r)
        self.assertEqual(0, len(self.missing_from_year))




if __name__ == '__main__':
    unittest.main()
