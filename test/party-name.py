#!/usr/bin/env python3
from pytest_cfg_fetcher.fetch import fetch_config
from tqdm import tqdm
import pandas as pd
import unittest


class Test(unittest.TestCase):

    def _load_data(self):
        party_names = pd.read_csv("data/party.csv")
        party_affil = pd.read_csv("data/party_affiliation.csv")
        return party_names, party_affil


    def test_party_names(self):
        names, affil = self._load_data()
        config = fetch_config("party-names")
        party_ids_found = {n:False for n in names['party_id'].unique()}

        parties_se = {}
        for i, r in names.iterrows():
            end  = r["dissolution"]
            if pd.isna(end) or end is None:
                end = "Current"
            parties_se[r["swerik_party_id"]] = {'start': r['inception'], "end": end}
        unlisted_parties = []
        unlisted_cols = ["person", "start", "end", "swerik_party_id"]
        rows = []
        cols = ["person_id", "start", "end", "swerik_party_id", "party_start", "party_end"]

        for i, r in tqdm(affil.iterrows(), total=len(affil)):
            if r["swerik_party_id"] in [
                                # Some Party IDs need to be ignored
                                # ---------------------------------
                                "i-851f4cdfa36f4dbab4b24855a1eb43ce"   # utan partibeteckning
                                ]:
                continue
            try:
                party_se = parties_se[r['swerik_party_id']]
                print(r["swerik_party_id"], party_se)
            except:
                unlisted_parties.append([
                    r["person_id"],
                    r["start"],
                    r["end"],
                    r['swerik_party_id']])
            else:
                if (
                        pd.notnull(r['start']) and \
                        r['start'][:len(party_se['start'])] < party_se['start']
                    ) or \
                    (
                        pd.notnull(r['end']) and \
                        r["end"] != "Current" and \
                        r['end'][:len(party_se['end'])] > party_se['end']
                    ):
                    rows.append([r["person_id"], r["start"] ,r["end"], r["swerik_party_id"], party_se["start"], party_se["end"]])
                else:
                    party_ids_found[r["swerik_party_id"]] = True

        """
        ks = []
        for k, v in party_ids_found.items():
            if v == False:
                ks.append(k)
        if len(ks) > 0:
            print("FAIL, all test IDs not found in data")
            print(ks)
            if config and config["write-not-found-data"]:
                with open(f"{config['test_out_dir']}/party-names_not-found-data.txt", "w+") as o:
                    [o.write(f"{k}\n") for k in ks]
        """
        if len(rows) > 0:
            print("FAIL, some IDs out of range")

            print(len(rows), "out of correct time range", len(rows)/len(affil))
            if config and config["write-oor"]:
                df = pd.DataFrame(rows, columns=cols)
                print(df['swerik_party_id'].value_counts())
                df.to_csv(f"{config['test_out_dir']}/party-names_oor.csv", sep=';', index=False)
        """
        if len(unlisted_parties) > 0:
            print("FAIL, some data IDs not in test set")
            print(len(unlisted_parties), "are found in the data but not our list of parties", len(unlisted_parties)/len(affil))
            if config and config["write-not-found-test"]:
                df = pd.DataFrame(unlisted_parties, columns=unlisted_cols)
                print(df['party_id'].value_counts())
                df.to_csv(f"{config['test_out_dir']}/party-names_not-found-test.csv", sep=';', index=False)
        print("done")
        """
        #self.assertEqual(len(ks), 0)
        self.assertEqual(len(rows), 0)
        #self.assertEqual(len(unlisted_parties), 0)

if __name__ == '__main__':
    unittest.main()
