"""
Tests related to party affiliations.
"""
from datetime import datetime
from pytest_cfg_fetcher.fetch import fetch_config
import pandas as pd
import unittest
import warnings





class Unlisted(Warning):

    def __init__(self, m):
        self.message = m

    def __str__(self):
        return self.message


class Info(Warning):

    def __init__(self, m):
        self.message = m

    def __str__(self):
        return self.message




class Test(unittest.TestCase):

    def write_err_df(self, name_str, lol, cols, outdir):
        now = datetime.now().strftime('%Y%m%d-%H%M%S')
        df = pd.DataFrame(lol, columns=cols)
        df.to_csv(f"{outdir}/{now}_{name_str}.csv", index=False)


    #@unittest.skip
    def test_independent_mp(self):
        """
        Make sure known independent MP's are listed as such in the data
        """
        config = fetch_config("independent-mp")
        test_file = pd.read_csv("test/data/independent-mp.csv", sep=';')
        independent = pd.read_csv("data/explicit_no_party.csv")
        ind_wiki = independent['wiki_id'].unique()
        ind_swerik = independent['person_id'].unique()
        missing_ind = []
        for i, r in test_file.iterrows():
            if r['wiki_id'] not in ind_wiki:
                if r['person_id'] not in ind_swerik:
                    missing_ind.append([r['wiki_id'], r['person_id']])
                    warnings.warn(f"Missing From Wikidata {r['wiki_id']} : {r['person_id']}", Unlisted)
        extra_ind = []
        [extra_ind.append(_) for _ in ind_wiki if _ not in test_file['wiki_id'].unique()]
        if len(extra_ind) > 0:
            [warnings.warn(f"\n--> Missing from testfile {_}", Unlisted) for _ in extra_ind]
            warnings.warn(f"\n\n\n~~ {len(extra_ind)} MPs currently listed as independent not in the testfile ({len(test_file)})\n", Info)
            if config and config['write-unlisted-ind-testfile']:
                extra_ind = [[_] for _ in extra_ind]
                self.write_err_df("unlisted-ind-testfile", extra_ind, ["wiki_id"], config['test_out_dir'])
        if len(missing_ind) > 0:
            warnings.warn(f"\n\n\n~~ {len(missing_ind)} MPs currently listed as independent in testfile do not appear as such in Wikidata\n", Info)
            if config and config['write-unlisted-ind-wiki']:
                self.write_err_df("unlisted-ind-wiki", missing_ind, ["wiki_id", "person_id"], config['test_out_dir'])
        #self.assertEqual(len(missing_ind), 0)
        #self.assertEqual(len(extra_ind), 0)


    #@unittest.skip
    def test_party(self):
        """
        Check that known MP party affiliations are correct.
        """
        config = fetch_config("party-affiliation")
        test_file = pd.read_csv("test/data/known-party-affiliation.csv", sep=';')
        party_affiliation = pd.read_csv("data/party_affiliation.csv")

        bad_affil = []
        for i, r in test_file.iterrows():
            if (pd.notnull(r['start']) or r['start'] == '') and \
               (pd.notnull(r["end"]) or r['end'] == ''):
                Q = party_affiliation.loc[
                        (party_affiliation['person_id'] == r["person_id"]) &
                        (party_affiliation['party_id'] == r['party_id']) &
                        (party_affiliation['start'] == str(r['start'])[:4]) &
                        (party_affiliation['end'] == str(r['end'])[:4])]
            else:
                Q = party_affiliation.loc[
                        (party_affiliation['person_id'] == r["person_id"]) &
                        (party_affiliation['party_id'] == r['party_id'])]
            if len(Q) == 0:
                bad_affil.append([r[_] for _ in test_file.columns])
                warnings.warn(f"\n -> Not found in wikidata {'|'.join([str(r[_]) if pd.notnull(r[_]) else '' for _ in test_file.columns])}", Unlisted)
        if len(bad_affil) > 0:
            warnings.warn(f"\n\n\n~~ {len(bad_affil)} mismatches between wikidata and ({len(test_file)}) known party affiliations\n", Info)
            if config and config["write-party-affil-err"]:
                self.write_err_df("unmatched-party-affiliations", bad_affil, test_file.columns, config["test_out_dir"])
        self.assertTrue(len(bad_affil)< 2)




if __name__ == '__main__':
    unittest.main()
