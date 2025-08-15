#!/usr/bin/env python3
"""
Check that everyone sitting (chair_mp) has a role matching the chamber of the chair they're sitting on.
"""
from pyriksdagen.date_handling import yearize_mandates
from tqdm import tqdm
import pandas as pd
import unittest




class ChairAndMandateInSameChamber(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super(ChairAndMandateInSameChamber, cls).setUpClass()
        cls.mandates = yearize_mandates()
        cls.seats = pd.read_csv("data/chair_mp.csv")
        cls.chair_chambers = {}
        df = pd.read_csv("data/chairs.csv")
        for i, r in df.iterrows():
            cls.chair_chambers[r["chair_id"]] = r["chamber"]
        cls.chamber_role = {
                "fk": "förstakammarledamot",
                "ak": "andrakammarledamot",
                "ek": "ledamot"
            }
        cls.chamber_mismatch = []


    @classmethod
    def tearDownClass(cls):
        if len(cls.chamber_mismatch) > 0:
            pd.DataFrame(cls.chamber_mismatch, columns=cls.seats.columns).to_csv("test/_test-results/chair-role-chamber-mismatch.tsv", sep='\t')


    def test_chair_chamber_matches_mandate(self):
        for i, r in tqdm(self.seats.iterrows(), total=len(self.seats)):
            if pd.isna(r["person_id"]) or len(r["person_id"]) == 0:
                continue
            chairch = self.chair_chambers[r["chair_id"]]
            chairrole = self.chamber_role[chairch]
            m = self.mandates.loc[(self.mandates["person_id"] == r["person_id"]) &
                                (self.mandates["parliament_year"] == r["parliament_year"])]
            if len(m) == 0:
                continue
            if chairrole not in list(m["role"].unique()):
                self.chamber_mismatch.append(r)
        self.assertEqual(0, len(self.chamber_mismatch))




if __name__ == '__main__':
    unittest.main()
