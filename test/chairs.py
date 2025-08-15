#!/usr/bin/env python3
"""
Test chars and chair-mp mapping metadata.
"""
from datetime import datetime
from pyriksdagen.date_handling import yearize_mandates
from pytest_cfg_fetcher.fetch import fetch_config
import json
import pandas as pd
import unittest
import warnings
import sys




class ChairHog(Warning):

    def __init__(self, m):
        self.message = "\n" + f"The following MPs sit in two chairs in {m}:."

    def __str__(self):
        return self.message


class ChairInWrongTimePeriod(Warning):

    def __init__(self, m):
        self.message = f"There is {m}."

    def __str__(self):
        return self.message


class ChairMissingFromRange(Warning):

    def __init__(self, m):
        self.message = f" in {m} is missing."

    def __str__(self):
        return self.message


class ChairOutOfRange(Warning):

    def __init__(self, chamber):
        self.message = f"There are chairs that are not within the acceptable range of the chamber: {chamber}."

    def __str__(self):
        return self.message


class ChairYearOutOfRange(Warning):

    def __init__(self, m):
        self.message = f"In {m} <-- chair is missing."

    def __str__(self):
        return self.message


class DuplicateIDWarning(Warning):

    def __init__(self, m):
        self.message = f"{m}"

    def __str__(self):
        return self.message


class EmptyChair(Warning):

    def __init__(self, m):
        self.message = "\n" + f"The following chairs are empty in in {m}:."

    def __str__(self):
        return self.message


class KnaMP(Warning):

    def __init__(self, m):
        self.message = "\n" + f"The following chairs are occupied by more than one person at the same time in {m}:."

    def __str__(self):
        return self.message




class Test(unittest.TestCase):
    #
    #  --->  get var fns
    #  -----------------
    #
    #  read in chairs.csv
    def get_chairs(self):
        return pd.read_csv("data/chairs.csv")

    #  read in chair_mp.csv
    def get_chair_mp(self):
        return pd.read_csv("data/chair_mp.csv")

    # read in mep metadata
    def get_mep(self):
        df = pd.read_csv("data/member_of_parliament.csv")
        return df.rename(columns={"start": "meta_start", "end":"meta_end"})

    # read in parliament start end dates
    def get_riksdag_year(self):
        return pd.read_csv("data/riksdag-year.csv")

    #  set max values for each chamber
    def get_max_chair(self):
        max_chair = {
            'ak':233,
            'fk':151,
            'ek':350
        }
        return max_chair

    #  Out of range chair for specific years
    def get_oor_year(self):
        oor_year = {
            '1957':
                    [    # until 1957 -- if year < 1957
                    '814127872a174909bd6ecaeaf59290fe',  # a231
                    'd423710cb9e64b17b93484e120f07e66',  # a232
                    'c77cdeebf789416e98cf8afb05b75a23',  # a233
                    '34ad45b358764a388b53c45ae1ce3681'   # f151
                    ],
            '1959':
                    [    # until 1959 -- elif year < 1959
                    '814127872a174909bd6ecaeaf59290fe',  # a231
                    'd423710cb9e64b17b93484e120f07e66',  # a232
                    'c77cdeebf789416e98cf8afb05b75a23'   # a233
                    ],
            '1961':
                    [    # unitl 1961 -- elif year < 1961
                    'd423710cb9e64b17b93484e120f07e66',  # a232
                    'c77cdeebf789416e98cf8afb05b75a23'   # a233
                    ],
            '1965':
                    [    # until 1965 -- elif year < 1965
                    'c77cdeebf789416e98cf8afb05b75a23'   # a233
                    ],
            '7677':
                    [    # from 197677
                    'af0ebaa9aed64c2d91750aa72651ea74'   # e350
                    ]
        }
        return oor_year

    #
    #  --->  misc fns
    #  --------------
    #
    def get_duplicated_items(self, l):
        """
        return duplicates in a list
        """
        seen = set()
        return [_ for _ in l if _ in seen or seen.add(_)]


    def what_time_it_is(self):
        """
        get formatted datetimestring
        """
        return datetime.now().strftime('%Y%m%d-%H%M%S')


    #
    #  --->  Test integrity of chairs data
    #  -------------------------------------------
    #
    #@unittest.skip
    def test_unique_chair_id(self):
        """
        check chair IDs are unique
        """
        print("Testing: chairs have unique IDs")
        chairs = self.get_chairs()
        chair_ids = chairs['chair_id'].values
        if len(chair_ids) != len(set(chair_ids)):
            warnings.warn("There's probably a duplicate chair ID.", DuplicateIDWarning)
        self.assertEqual(len(chair_ids), len(set(chair_ids)))

    #@unittest.skip
    def test_chair_nrs_in_range(self):
        """
        check no chairs are numbered higher than the max chair nr for that chamber
        """
        print("Testing: chairs within max range for chamber")
        chairs = self.get_chairs()
        max_chair = self.get_max_chair()
        for k, v in max_chair.items():
            oor_chairs = chairs.loc[(chairs['chamber'] == k) & (chairs['chair_nr'] > v)]
            if len(oor_chairs) > 0:
                warnings.warn(k, ChairOutOfRange)
            self.assertEqual(len(oor_chairs), 0)

    #
    #  --->  Test integrity of chair_mp mapping
    #  --------------------------------
    #
    #@unittest.skip
    def test_chair_id_sets(self):
        """
        check chair IDs in chair_mp are the same set as chairs
        """
        print("Testing: chair ids are the same set in chairs.csv and chair_mp.csv")
        chairs = self.get_chairs()
        chair_mp = self.get_chair_mp()
        chair_ids_a = chairs['chair_id'].unique()
        chair_ids_b = chair_mp['chair_id'].unique()
        if set(chair_ids_a) != set(chair_ids_b):
            warnings.warn(ChairIDMismatchW)
        self.assertEqual(len(chair_ids_a), len(chair_ids_b))

    #@unittest.skip
    def test_chair_chambertime_concurrence(self):
        """
        check no chairs from tvåkammartiden are used in enkammartid and vice-versa
        """
        print("Testing: no chairs from tvåkammartiden are used in enkammartid and vice-versa")
        chairs = self.get_chairs()
        config = fetch_config("chairs")
        tvok_chairs = chairs.loc[chairs['chamber'] != 'ek', 'chair_id'].unique()
        enk_chairs =  chairs.loc[chairs['chamber'] == 'ek', 'chair_id'].unique()
        chair_mp = self.get_chair_mp()
        tvok_chair_mp_chairs = chair_mp.loc[
            chair_mp['parliament_year'] < 1971,
            'chair_id'
        ].unique()
        enk_chair_mp_chairs = chair_mp.loc[
            chair_mp['parliament_year'] > 1970,
            'chair_id'
        ].unique()
        tkc_in_enkt = []           # tvåkammar chair in enkammartid
        ekc_in_tvkt = []           # enkammar chair in tvåkammartid
        for c in tvok_chair_mp_chairs:
            if c in enk_chairs:
                ekc_in_tvkt.append(c)
        for c in enk_chair_mp_chairs:
            if c in tvok_chairs:
                tkc_in_enkt.append(c)
        if len(tkc_in_enkt) > 0:
            warnings.warn('tvåkammar chair in enkammartid',ChairInWrongTimePeriod)
            if config and config['write_tkc_in_enkt']:
                with open(f"{config['test_out_dir']}/{self.what_time_it_is()}_tkc_in_enkt.txt", "w+") as o:
                    [o.write(f"{_}\n") for _ in tkc_in_enkt]
        if len(ekc_in_tvkt) > 0:
            warnings.warn('enkammar chair in tvåkammartid', ChairInWrongTimePeriod)
            if config and config['write_ekc_in_tvkt']:
                with open(f"{config['test_out_dir']}/{self.what_time_it_is()}_ekc_in_tvkt.txt", "w+") as o:
                    [o.write(f"{_}\n") for _ in ekc_in_tvkt]
        self.assertEqual(len(tkc_in_enkt), 0)
        self.assertEqual(len(ekc_in_tvkt), 0)

    #@unittest.skip
    def test_chair_nrs_in_range_for_year(self):
        """
        check that chairs are within acceptable range for a given year
           and that every seat within that range is present at least once
           in the chair_mp file (whether filled or not)
        """
        print("Testing: chairs are within acceptable range for a given year\n     and that every seat within that range is present at least once")
        chairs = self.get_chairs()
        config = fetch_config("chairs")
        tvok_chairs = chairs.loc[chairs['chamber'] != 'ek', 'chair_id'].unique()
        enk_chairs = chairs.loc[chairs['chamber'] == 'ek', 'chair_id'].unique()
        chair_mp = self.get_chair_mp()
        oor_year = self.get_oor_year()
        rd_years = chair_mp['parliament_year'].unique()
        OutOfRange = []
        missing_in_R = []
        for y in rd_years:
            year_chair_mp_chairs = chair_mp.loc[
                chair_mp['parliament_year'] == y,
                'chair_id'
            ].unique()
            excludes = []
            if y < 1971:
                if y <= 1957:
                    excludes = oor_year['1957']
                elif y < 1959:
                    excludes = oor_year['1959']
                elif y < 1961:
                    excludes = oor_year['1961']
                elif y < 1965:
                    excludes = oor_year['1965']
                if len(excludes) > 0:
                    for x in excludes:
                        if x in year_chair_mp_chairs:
                            OutOfRange.append([y, x])
                            warnings.warn(f"{y}: {x}", ChairYearOutOfRange)
                if len(tvok_chairs) > len(year_chair_mp_chairs)+len(excludes):
                    for c in tvok_chairs:
                        if c not in year_chair_mp_chairs and c not in excludes:
                            missing_in_R.append([y, c])
                            warnings.warn(f"{y}: {c}", ChairMissingFromRange)
                elif len(tvok_chairs) > len(year_chair_mp_chairs)+len(excludes):
                    self.assertFalse(True, "¡Sth is super wrong!")
            else:
                if y > 197576 or y == 1980:
                    excludes = oor_year['7677']
                if len(excludes) > 0:
                    for x in excludes:
                        if x in year_chair_mp_chairs:
                            OutOfRange.append([y, x])
                            warnings.warn(f"{y}: {x}", ChairYearOutOfRange)
                if len(enk_chairs) < len(year_chair_mp_chairs)+len(excludes):
                    for c in tvok_chairs:
                        if c not in year_chair_mp_chairs and c not in excludes:
                            missing_in_R.append([y, c])
                            warnings.warn(f"{y}: {c}", ChairMissingFromRange)
                elif len(enk_chairs) > len(year_chair_mp_chairs)+len(excludes):
                    [print(_) for _ in enk_chairs if _ not in year_chair_mp_chairs]
                    self.assertFalse(True, "¡Sth is super wrong!")
        if len(OutOfRange) > 0:
            if config and config["write_chair_nrs_in_range"]:
                df = pd.DataFrame(OutOfRange, columne=["year", "chair"])
                df.to_csv(
                    f"{config['test_out_dir']}/{what_time_it_is}_chair-OOR.csv",
                    sep=';',
                    index=False)
        if len(missing_in_R) > 0:
            if config and config["write_chair_nrs_in_range"]:
                df = pd.DataFrame(missing_in_R, columne=["year", "chair"])
                df.to_csv(
                    f"{config['test_out_dir']}/{self.what_time_it_is()}_chair-missing-in-R.csv",
                    sep=';',
                    index=False)
        self.assertEqual(len(OutOfRange), 0)
        self.assertEqual(len(missing_in_R), 0)

    #
    #  --->  Test integrity of bum to chair mapping
    # ---------------------------------------------
    #
    #@unittest.skip
    def test_chair_hogs(self):
        """
        check no single person sits in two places at once
        """
        print("Testing: no single person sits in two places at once")
        chair_mp = self.get_chair_mp()
        chair_mp.rename(columns={"start": "chair_start", "end":"chair_end"}, inplace=True)
        chair_mp = chair_mp[chair_mp["person_id"].notna()]
        chairs = self.get_chairs()
        chair_mp = pd.merge(chair_mp, chairs, on="chair_id", how="left")
        mep_by_year = yearize_mandates()
        mep_by_year.rename(columns={"start": "meta_start", "end":"meta_end"}, inplace=True)
        mep_by_year = mep_by_year[mep_by_year["meta_start"].notna()]
        config = fetch_config("chairs")
        if config and config['write_ch_chmp_merge']:
            mep_by_year.to_csv(
                f"{config['test_out_dir']}/{self.what_time_it_is()}_chair-chairmp_merge.csv",
                sep=';',
                index=False)
        chair_mp = pd.merge(chair_mp, mep_by_year, on=["person_id", "parliament_year"], how="left")

        if config and config['write_trouble_matching']:
            outdf = chair_mp.loc[pd.isna(chair_mp["role"])].copy()
            if not outdf.empty:
                outdf.to_csv(
                    f"{config['test_out_dir']}/{self.what_time_it_is()}_trouble-matching-yearize.csv",
                    sep=';',
                    index=False)

        general_start_end = self.get_riksdag_year()
        no_chair_hogs = True
        counter = 0
        ddups = []
        issues = pd.DataFrame(columns=chair_mp.columns)
        for y in chair_mp['parliament_year'].unique():
            year_chair_mp = chair_mp.loc[chair_mp['parliament_year'] == y]
            yse = general_start_end.loc[general_start_end['parliament_year'] == y].copy()
            yse.reset_index(drop=True, inplace=True)
            yse.sort_values(by=["chamber", "start", "end"], inplace=True)
            cs = yse["chamber"].unique()
            d = {}
            for c in cs:
                cdf = yse.loc[yse["chamber"] == c].copy()
                cdf.reset_index(drop=True, inplace=True)
                d[c] = {"earliest": cdf.at[0, "start"], "latest": cdf.at[len(cdf.index)-1, "end"]}
            mps = year_chair_mp.loc[pd.notnull(year_chair_mp['person_id']), 'person_id'].values
            if len(mps) > len(set(mps)):
                dups = self.get_duplicated_items(mps)
                ch = []
                for dup in dups:
                    df = year_chair_mp.loc[year_chair_mp["person_id"] == dup].copy()
                    df.drop_duplicates(subset=["chair_id", "parliament_year", "chair_start", "chair_end", "person_id"], inplace=True)
                    if len(df["chair_id"].unique()) == 1:
                        pass
                    else:
                        ranges = []
                        for i, r in df.iterrows():
                            rstart = None
                            if pd.notnull(r["chair_start"]):
                                rstart = r["chair_start"]
                            elif pd.notnull(r['meta_start']):
                                rstart = r['meta_start']
                            else:
                                rstart = d[r["chamber"]]["earliest"]
                            rend = None
                            if pd.notnull(r["chair_end"]):
                                rend = r["chair_end"]
                            elif pd.notnull(r["meta_end"]):
                                rend = r["meta_end"]
                            else:
                                rend = d[r["chamber"]]["latest"]
                            ranges.append((rstart, rend))
                        ranges = sorted(ranges, key=lambda x: (x[0], x[1]))
                        for ridx, _range in enumerate(ranges):
                            if ridx < len(ranges)-1:
                                delta = (datetime.strptime(_range[1], "%Y-%m-%d") - datetime.strptime(ranges[ridx+1][0], "%Y-%m-%d")).days
                                if max(0, delta) > 0:
                                    issues = pd.concat([issues,df], ignore_index=True)
                                    if dup not in ch:
                                        ch.append(dup)
                                        print("\n--->>>>", dup)
                                        print(ranges)
                                        print(df)
                                        print(_range, ranges[ridx+1])

                if len(ch) > 0:
                    print("\n\n")
                    warnings.warn(f"{y}: [{', '.join(ch)}]", ChairHog)
                    no_chair_hogs = False
                    counter += len(ch)
                    [ddups.append(_) for _ in ch]
        if config and config['write_chairhogs']:
            issues.drop_duplicates(inplace=True)
            issues.to_csv(
                f"{config['test_out_dir']}/{self.what_time_it_is()}_ChairHogs.csv",
                sep=';',
                index=False)
        print(counter, ddups)
        self.assertTrue(no_chair_hogs)


    #@unittest.skip
    def test_knaMP(self):
        """
        Check no one is sharing a chare
        """
        print("Testing no one sits on the same chair at the same time")
        config = fetch_config("chairs")
        chair_mp = self.get_chair_mp()
        chair_mp.rename(columns={"start": "chair_start", "end":"chair_end"}, inplace=True)
        chair_mp = chair_mp[chair_mp["person_id"].notna()]
        chairs = self.get_chairs()
        chair_mp = pd.merge(chair_mp, chairs, on="chair_id", how="left")
        mep_by_year = yearize_mandates()
        mep_by_year.rename(columns={"start": "meta_start", "end":"meta_end"}, inplace=True)
        mep_by_year = mep_by_year[mep_by_year["meta_start"].notna()]
        chair_mp = pd.merge(chair_mp, mep_by_year, on=["person_id", "parliament_year"], how="left")
        general_start_end = self.get_riksdag_year()
        ingen_knahund = True
        counter = 0
        ddups = []
        issues = pd.DataFrame(columns=chair_mp.columns)
        for y in chair_mp['parliament_year'].unique():
            year_chair_mp = chair_mp.loc[chair_mp['parliament_year'] == y].copy()
            yse = general_start_end.loc[general_start_end['parliament_year'] == y].copy()
            yse.reset_index(drop=True, inplace=True)
            yse.sort_values(by=["chamber", "start", "end"], inplace=True)
            cs = yse["chamber"].unique()
            d = {}
            for c in cs:
                cdf = yse.loc[yse["chamber"] == c].copy()
                cdf.reset_index(drop=True, inplace=True)
                d[c] = {"earliest": cdf.at[0, "start"], "latest": cdf.at[len(cdf.index)-1, "end"]}
            year_chair_mp.drop_duplicates(inplace=True)
            chairs = year_chair_mp.loc[pd.notnull(year_chair_mp['chair_id']), 'chair_id'].values
            if len(chairs) > len(set(chairs)):
                dups = self.get_duplicated_items(chairs)
                kh = []
                for dup in dups:
                    df = year_chair_mp.loc[year_chair_mp["chair_id"] == dup].copy()
                    df.drop_duplicates(subset=["chair_id", "parliament_year", "chair_start", "chair_end", "person_id"], inplace=True)
                    if len(df["person_id"].unique()) == 1:
                        pass
                    else:
                        ranges = []
                        for i, r in df.iterrows():
                            rstart = None
                            if pd.notnull(r["chair_start"]):
                                rstart = r["chair_start"]
                            elif pd.notnull(r["meta_start"]):
                                rstart = r["meta_start"]
                            else:
                                rstart = d[r["chamber"]]["earliest"]
                            rend = None
                            if pd.notnull(r["chair_end"]):
                                rend = r["chair_end"]
                            elif pd.notnull(r["meta_end"]):
                                rend = r["meta_end"]
                            else:
                                rend = d[r["chamber"]]["latest"]
                            ranges.append((rstart, rend))

                        ranges = sorted(ranges, key=lambda x: (x[0], x[1]))
                        for ridx, _range in enumerate(ranges):
                            if ridx < len(ranges)-1:
                                try:
                                    delta = (datetime.strptime(_range[1], "%Y-%m-%d") - datetime.strptime(ranges[ridx+1][0], "%Y-%m-%d")).days
                                except:
                                    print("~~~~~~~~~XXXX", ranges[ridx+1][0], _range[1])
                                    self.assertTrue(False)
                                if max(0, delta) > 0:
                                    issues = pd.concat([issues,df], ignore_index=True)
                                    if dup not in kh:
                                        kh.append(dup)
                                        print("\n--->>>>", dup)
                                        print(df)
                                        print(ranges)
                                        print(_range, ranges[ridx+1])
                if len(kh) > 0:
                    print("\n\n")
                    warnings.warn(f"{y}: [{', '.join(kh)}]", KnaMP)
                    ingen_knahund = False
                    counter += len(kh)
                    [ddups.append(_) for _ in kh]
        if config and config['write_knahund']:
            issues.drop_duplicates(inplace=True)
            issues.to_csv(
                f"{config['test_out_dir']}/{self.what_time_it_is()}_LoveSeats.csv",
                sep=';',
                index=False)

        print(counter, ddups)
        self.assertTrue(ingen_knahund)

    #
    #  --->  Test coverage
    # ---------------------
    #
    #@unittest.skip
    def test_chair_coverage(self):
        """
        test all chairs are filled after 1925
        """
        print("Test coverage of chair-MP mapping.")
        config = fetch_config("chairs")
        chair_mp = self.get_chair_mp()
        no_empty_chairs = True
        empty_chairs = []
        counter = 0
        for y in chair_mp['parliament_year'].unique():
            y_empty_chairs = []
            y_counter = 0
            year_chair_mp = chair_mp.loc[
                    (chair_mp['parliament_year'] == y) &
                    (chair_mp['parliament_year'] > 1925)
                ]
            year_chairs = year_chair_mp["chair_id"].unique()
            if year_chair_mp["person_id"].isnull().any():
                for i, r in year_chair_mp.iterrows():
                    if pd.isna(r["person_id"]):
                        df = year_chair_mp.loc[
                            (year_chair_mp["chair_id"] == r["chair_id"]) &
                            (pd.notnull(year_chair_mp["person_id"]))]
                        if df.empty:
                            y_counter += 1
                            y_empty_chairs.append(r["chair_id"])
            if y_counter > 0:
                no_empty_chairs = False
                print("\n\n")
                warnings.warn(f"{y}: [{', '.join(y_empty_chairs)}]", EmptyChair)
                counter += y_counter
                [empty_chairs.append([str(y), _]) for _ in y_empty_chairs]
                print("\n" + str(y_counter / len(year_chairs)) + " emptiness in year")

        if config and config['write_empty_seats']:
            issues = pd.DataFrame(empty_chairs, columns=['year', 'chair_id'])
            issues.to_csv(
                f"{config['test_out_dir']}/{self.what_time_it_is()}_EmptySeats.csv",
                sep=';',
                index=False)

        print(counter, empty_chairs)
        self.assertTrue(no_empty_chairs)




if __name__ == '__main__':
    unittest.main()
