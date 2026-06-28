#!/usr/bin/env python3
"""
Assert that at least 95% of parliament days have the correct number of MPs in the metadata with a 10% tolerance.
"""
from pyriksdagen.metadata import (
    load_Corpus_metadata
)
from pyriksdagen.utils import (
    get_data_location,
)
from pytest_cfg_fetcher.fetch import fetch_config
from tqdm import tqdm
import datetime as dt
import pandas as pd
import unittest, warnings



class Info(Warning):
    def __init__(self, m):
        self.message = m
    def __str__(self):
        return self.message

class Test(unittest.TestCase):

    def write_err_df(self, name_str, df, outdir):
        now = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
        df.to_csv(f"{outdir}/{now}_{name_str}.csv", index=False)

    def get_spec(self, protocol_path):
        spec = None
        spl = protocol_path.split('/')[-1].split('-')
        if len(spl) == 4:
            return spec
        else:
            if len(spl[2]) > 0:
                spec = spl[2]
            return spec

    def mk_py(self, row):
        if pd.isna(row['spec']):
            return row['year']
        else:
            return str(row['year']) + row['spec']

    def get_baseline(self, row, baseline_df):
        y = row['year']
        c = row['chamber']
        fdf = baseline_df.loc[(baseline_df['year'] == y) & (baseline_df['chamber'] == c)].copy()
        fdf.reset_index(inplace=True)
        return fdf.at[0, "n_mps"]

    def get_ch(self, protocol_path):
        chamber = None
        spl = protocol_path.split('/')[-1].split('-')
        if len(spl) == 4:
            chamber = "ek"
        else:
            chamber = spl[3]
        return chamber

    def is_within_tolerance(self, nmp, baseline):
        ratio = nmp/baseline
        #print(f" ---> R: {ratio}")
        if ratio > 1.1:
            return False, ratio
        elif ratio > 0.9:
            return True, ratio
        else:
            return False, ratio

    def preprocess_Corpus_metadata(self):
        corpus_meta = load_Corpus_metadata(metadata_folder='data')
        mp_meta = corpus_meta[corpus_meta['source'] == 'member_of_parliament']
        mp_meta = mp_meta[mp_meta.start.notnull()]
        mp_meta['start'] = mp_meta['start'].apply(lambda x: pd.to_datetime(x, format='%Y-%m-%d', errors='ignore'))
        mp_meta['end'] = mp_meta['end'].apply(lambda x: pd.to_datetime(x, format='%Y-%m-%d', errors='ignore'))
        return mp_meta

    def expand_dates_df(self, dates, baseline_df):
        for _ in ["N_MP", "passes_test", "almost_passes_test",
                "ratio", "year", "spec", "parliament_year",
                "chamber", "baseline_N", "MEPs"]:
            if _ not in dates.columns:
                dates[_] = None

        dates["year"] = dates["protocol"].apply(lambda x: str(x.split('/')[0][:4]))
        dates["spec"] = dates["protocol"].apply(lambda x: self.get_spec(x))
        dates["parliament_year"] = dates.apply(self.mk_py, axis=1)
        dates['chamber'] = dates['protocol'].apply(lambda x: self.get_ch(x))
        dates['baseline_N'] = dates.apply(self.get_baseline, args=(baseline_df,), axis=1)
        return dates

    def test_mp_frequency(self):
        """
        Test daily frequencies.
        """
        config = fetch_config("mp-freq-test")
        baseline_df = pd.read_csv(f"./test/data/baseline-n-mps-year.csv")
        baseline_df['year'] = baseline_df['year'].apply(lambda x: str(x)[:4])
        dates = pd.read_csv(f"./test/data/session-dates.csv", sep=";")
        dates = self.expand_dates_df(dates, baseline_df)
        mp_meta = self.preprocess_Corpus_metadata()

        ledamot_map = {
            "fk": 1,
            "ak": 2,
            "ek": 0
        }

        filtered_DFs = {}
        for k, v in ledamot_map.items():
            filtered_DFs[k] = mp_meta.loc[mp_meta['chamber'] == v]

        shouldnt_happen = 0

        with tqdm(total=len(dates)) as prgbr:
            for i, r in dates.iterrows():
                N_MP = 0
                chamber = r['chamber']
                MEPs = []
                if not pd.isna(chamber):
                    parliament_day = r['date']
                    baseline = r['baseline_N']
                    prgbr.set_postfix_str(f"{chamber} / {r['parliament_year']} / {shouldnt_happen}")

                    if len(parliament_day) == 10:
                        #print(r['date'], type(r['date']))
                        day = dt.datetime.strptime(r['date'], '%Y-%m-%d')
                        year = day.year

                        sub_df = filtered_DFs[chamber]
                        sub_df = sub_df[sub_df["start"] <= day]
                        sub_df = sub_df[sub_df["end"] > day]

                        N_MP = len(sub_df["person_id"].unique())
                        MEPs = list(sub_df["person_id"].unique())

                    dates.at[i, 'N_MP'] = N_MP

                    if N_MP != 0:
                        if N_MP == r['baseline_N']:
                            dates.at[i, 'passes_test'] = True
                            dates.at[i, 'almost_passes_test'], dates.at[i, "ratio"] = self.is_within_tolerance(N_MP, baseline)
                        else:
                            dates.at[i, 'passes_test'] = False
                            dates.at[i, 'almost_passes_test'], dates.at[i, "ratio"] = self.is_within_tolerance(N_MP, baseline)
                    else:
                        dates.at[i, 'passes_test'] = False
                        dates.at[i, 'almost_passes_test'] = False
                        dates.at[i, "ratio"] = 0
                else:
                    dates.at[i, 'passes_test'] = "None"
                    dates.at[i, 'almost_passes_test'] = "None"
                    dates.at[i, "ratio"] = "None"
                dates.at[i, "MEPs"] = list(MEPs)
                prgbr.update()
        dates = dates.sort_values(by=['protocol', 'date'], ignore_index=True)

        total_passed = len(dates.loc[dates['passes_test'] == True])
        total_almost = len(dates.loc[dates['almost_passes_test'] == True])
        total = len(dates)
        if total > total_almost:
            if config and config["write-err-days"]:
                no_passdf = dates.loc[dates['almost_passes_test'] == False]
                self.write_err_df("mp-freq-oor", no_passdf, config["test_out_dir"])

        warnings.warn(f"\n\n\n --> of {total} Parliament days, {total_almost} almost have the correct number of MPs (+/-10%) {total_almost/total}\n", Info)

        warnings.warn(f"\n\n\n --> of {total} Parliament days, {total_passed} have exactly the correct number of MPs (+/-10%) {total_passed/total}\n", Info)

        self.assertTrue(total_almost/total > 0.95)




if __name__ == '__main__':
    unittest.main()
