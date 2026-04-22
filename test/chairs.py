#!/usr/bin/env python3
"""
Test chars and chair-mp mapping metadata.
"""
from datetime import datetime
from pyriksdagen.date_handling import yearize_mandates
from pytest_cfg_fetcher.fetch import fetch_config
import json
import pandas as pd
import polars as pl
import unittest
import warnings
import sys
import tqdm
from trainerlog import get_logger
LOGGER = get_logger("unittest")
LOGGER.info("Use the env variable LOGLEVEL=DEBUG to get more detailed error messages")


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
        LOGGER.info("Testing: chairs have unique IDs")
        chairs = self.get_chairs()
        chair_ids = chairs['chair_id'].values
        if len(chair_ids) != len(set(chair_ids)):
            warnings.warn("There's probably a duplicate chair ID.", DuplicateIDWarning)
        msg = f"There's at least one duplicate chair ID, {len(chair_ids)} IDs vs. {len(set(chair_ids))} unique IDs"
        self.assertEqual(len(chair_ids), len(set(chair_ids)), msg)

    #@unittest.skip
    def test_chair_nrs_in_range(self):
        """
        check no chairs are numbered higher than the max chair nr for that chamber
        """
        LOGGER.info("Testing: chairs within max range for chamber")
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
        LOGGER.info("Testing: chair ids are the same set in chairs.csv and chair_mp.csv")
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
        LOGGER.info("Testing: no chairs from tvåkammartiden are used in enkammartid and vice-versa")
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
        LOGGER.info("Testing: chairs are within acceptable range for a given year\n     and that every seat within that range is present at least once")
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
                            error_message = f"OutOfRange error {y}: {x}"
                            LOGGER.error(error_message)

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
                            error_message = f"OutOfRange error {y}: {x}"
                            LOGGER.error(error_message)
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
                df = pd.DataFrame(OutOfRange, columns=["year", "chair"])
                df.to_csv(
                    f"{config['test_out_dir']}/{what_time_it_is}_chair-OOR.csv",
                    sep=';',
                    index=False)
        if len(missing_in_R) > 0:
            if config and config["write_chair_nrs_in_range"]:
                df = pd.DataFrame(missing_in_R, columns=["year", "chair"])
                df.to_csv(
                    f"{config['test_out_dir']}/{self.what_time_it_is()}_chair-missing-in-R.csv",
                    sep=';',
                    index=False)
        self.assertEqual(len(OutOfRange), 0, f"{len(OutOfRange)} chair(s) are outside of an acceptable range for a given year")
        self.assertEqual(len(missing_in_R), 0, f"{len(missing_in_R)} chair(s) are missing in the chair_mp file")

    #
    #  --->  Test integrity of bum to chair mapping
    # ---------------------------------------------
    #
    #@unittest.skip
    def test_chair_hogs(self):
        """
        Chair duplicates, check that
        - no single person sits in two places at once (Chair Hog)
        - multiple people do not sit in the same chair at once (KnaMP)
        """
        name_map = {}
        try:
            name_df = pd.read_csv("data/name.csv")
            primary = name_df[name_df["primary_name"].astype(str).str.lower() == "true"]
            name_map = dict(zip(primary["person_id"].astype(str), primary["name"].astype(str)))
        except Exception as e:
            LOGGER.warning(f"Could not load data/name.csv for resolution: {e}")

        chair_label_map = {}
        try:
            chairs_df = pd.read_csv("data/chairs.csv")
            chair_label_map = {
                str(r.chair_id): f"{r.chamber} {r.chair_nr}"
                for r in chairs_df.itertuples()
            }
        except Exception as e:
            LOGGER.warning(f"Could not load data/chairs.csv for resolution: {e}")

        def resolve_name(pid):
            try:
                n = name_map.get(str(pid))
                return f" ({n})" if n else ""
            except Exception:
                return ""

        def resolve_chair(cid):
            try:
                cid_s = str(cid)
                short = cid_s[:8] if len(cid_s) >= 8 else cid_s
                label = chair_label_map.get(cid_s)
                return f"{short} ({label})" if label else cid_s
            except Exception:
                return str(cid)

        def stringify_row(row_dict):
            pid = row_dict['person_id']
            cid = row_dict['chair_id']
            s = (
                f"In year {row_dict['parliament_year']}, "
                f"person: {pid}{resolve_name(pid)} "
                f"sat in {resolve_chair(cid)}"
            )
            return f"{s} from {row_dict['start_str']} to {row_dict['end_str']}"

        LOGGER.info("Testing: no single person sits in two places at once")
        chair_mp = self.get_chair_mp()
        chair_mp = pl.from_pandas(chair_mp)
        chair_mp = chair_mp.filter(pl.col("person_id").is_not_null())
        
        # Fill out nulls for printing
        chair_mp_imputed = chair_mp.with_columns(pl.col("start").fill_null("N/A").alias("start_str"))
        chair_mp_imputed = chair_mp_imputed.with_columns(pl.col("end").fill_null("N/A").alias("end_str"))

        # Fill out nulls for filtering. Use values that are larger and smaller than all real dates
        chair_mp_imputed = chair_mp_imputed.with_columns(pl.col("start").fill_null("1000-01-01"))
        chair_mp_imputed = chair_mp_imputed.with_columns(pl.col("end").fill_null("3000-12-31"))

        # Impute start years without date to "YYYY-01-01"
        chair_mp_imputed = chair_mp_imputed.with_columns(
            pl.when(pl.col.start.str.len_chars() == 4)
            .then(pl.concat_str("start", pl.lit("-01-01")))
            .otherwise("start"))
        
        # Since one-day overlap is allowed, move the start dates (artificially) one day forward
        chair_mp_imputed = chair_mp_imputed.with_columns((
            pl.col("start").str.to_datetime()
            + pl.duration(days=1)
            ).dt.strftime("%Y-%m-%d"))

        chairhog_error_counter, knamp_error_counter = 0, 0
        for parliament_year in tqdm.tqdm(sorted(set(chair_mp.get_column("parliament_year")))):
            chair_mp_imputed_year = chair_mp_imputed.filter(pl.col("parliament_year") == parliament_year)

            # Test separately for each date where seating might change: 
            # Year start, year end, and every time somebody changes seats
            dates = set(chair_mp_imputed_year.get_column("start")).union(set(chair_mp_imputed_year.get_column("end")))
            chairhog_error_messages, knamp_error_messages = [], []
            for date in dates:
                chair_mp_imputed_date = chair_mp_imputed_year.filter(pl.col("start") <= date)
                chair_mp_imputed_date = chair_mp_imputed_date.filter(pl.col("end") >= date)
                duplicate_ix = chair_mp_imputed_date.select("person_id").is_duplicated()
                if sum(duplicate_ix) >= 1:
                    chair_mp_duplicated = chair_mp_imputed_date.filter(duplicate_ix)
                    descs = "\n".join([stringify_row(row_dict) for row_dict in chair_mp_duplicated.to_dicts()])
                    chairhog_error_messages.append(descs)

                duplicate_ix = chair_mp_imputed_date.select("chair_id").is_duplicated()
                if sum(duplicate_ix) >= 1:
                    chair_mp_duplicated = chair_mp_imputed_date.filter(duplicate_ix)
                    chair_mp_duplicated = chair_mp_duplicated.sort("chair_id")
                    descs = "\n".join([stringify_row(row_dict) for row_dict in chair_mp_duplicated.to_dicts()])
                    knamp_error_messages.append(descs)

            # Only count each error once, even though it might appear on multiple dates
            chairhog_error_counter += len(set(chairhog_error_messages))
            for descs in sorted(set(chairhog_error_messages)):
                LOGGER.error(f"Chair Hog Error:\n{descs}")
            knamp_error_counter += len(set(knamp_error_messages))
            for descs in sorted(set(knamp_error_messages)):
                LOGGER.error(f"KnaMP Error:\n{descs}")

        CHAIRHOG_THRESHOLD_2026_04_22 = 14
        error_message = f"{chairhog_error_counter} instance(s) of a person sitting in two places at once"
        self.assertLessEqual(chairhog_error_counter, CHAIRHOG_THRESHOLD_2026_04_22, error_message)
        if chairhog_error_counter > 0:
            LOGGER.warning(error_message)

        KNAMP_THRESHOLD_2026_04_22 = 17
        error_message = f"{knamp_error_counter} instance(s) of two or more people sitting in one chair at once"
        self.assertLessEqual(knamp_error_counter, KNAMP_THRESHOLD_2026_04_22, error_message)
        if knamp_error_counter > 0:
            LOGGER.warning(error_message)

    #
    #  --->  Test coverage
    # ---------------------
    #
    #@unittest.skip
    def test_chair_coverage(self):
        """
        test all chairs are filled after 1925
        """
        LOGGER.info("Test coverage of chair-MP mapping.")
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

        error_message = f"{counter} empty chairs found ({empty_chairs})"
        self.assertEqual(counter, 0, error_message)




if __name__ == '__main__':
    unittest.main()
