#!/usr/bin/env python3
"""
Dump the chairs metadata to a usable data set.
"""
import argparse
from datetime import datetime
from pyriksdagen.metadata import load_Corpus_metadata
from pyriksdagen.utils import get_data_location
from tqdm import tqdm
import os
import pandas as pd


CORPUS_ROOT = os.environ.get("CORPUS_ROOT", ".")



def test_chamber_coherance(corpus):
    print("test chamber coherance in result df")
    oepsie_woepsie = 0
    chamber_map = {
            0: "ek",
            1: "fk",
            2: "ak"
        }
    for i, r in corpus.iterrows():
        if pd.notnull(r['chamber']) and pd.notnull(r['chair_chamber']):
            if chamber_map[r['chamber']] != r['chair_chamber']:
                print(r)
                oepsie_woepsie += 1
    return oepsie_woepsie




def impute_chair_dates(chair_mp, riksmote):
    chair_mp['imp_start'] = None
    chair_mp['imp_end'] = None
    for i, r in tqdm(chair_mp.iterrows(), total=len(chair_mp)):
        py = r['parliament_year']

        if pd.isna(r['start']) or r['start'] == 'nan':
            #print("start is na")
            chair_mp.at[i, "imp_start"] = sorted(list(riksmote.loc[riksmote['parliament_year'] == py, 'start']))[0]
        else:
            chair_mp.at[i, "imp_start"] = chair_mp.at[i, "start"]
        if pd.isna(r['end']) or r['end'] == 'nan':
            #print("end is na")
            chair_mp.at[i, "imp_end"] = sorted(list(riksmote.loc[riksmote['parliament_year'] == py, 'end']), reverse=True)[0]
        else:
            chair_mp.at[i, "imp_end"] = chair_mp.at[i, "end"]
    print(chair_mp)
    return chair_mp




def add_multi(sitting, row, add_rows, chairs_d):

    for chair in sitting['chair_id'].unique():
        tmp_row = row
        tmp_seat = sitting.loc[sitting['chair_id'] == chair].copy()
        tmp_seat.reset_index(inplace=True)
        chair_info = chairs_d[sitting.at[0, 'chair_id']]
        tmp_row['chair_nr'] = chair_info[0]
        tmp_row['chair_chamber'] = chair_info[1]
        tmp_row['sitting_from'] = tmp_seat.at[0, 'start']
        tmp_row['sitting_to']  = tmp_seat.at[len(tmp_seat)-1, 'end']
        add_rows.append(pd.DataFrame(tmp_row).T)
    return add_rows




def main(args):
    chairs = pd.read_csv("data/chairs.csv")
    chairs_d = {}
    for i, r in chairs.iterrows():
        chairs_d[r['chair_id']] = (r['chair_nr'], r['chamber'])
    chair_mp = pd.read_csv("data/chair_mp.csv")
    chair_mp['start'] = chair_mp['start'].astype(str)
    chair_mp['end'] = chair_mp['end'].astype(str)

    riksmote = pd.read_csv("data/riksdag-year.csv")
    chair_mp = impute_chair_dates(chair_mp, riksmote)

    corpus = load_Corpus_metadata(metadata_folder="data")
    corpus = corpus.loc[
            (corpus['source'] == "member_of_parliament") &
            (corpus['primary_name'] == True) &
            (corpus['start'] >= "1925-01-01") &
            (corpus['start'] <= "1993-06-30")
        ].copy()
    corpus['start'] = corpus['start'].astype(str)
    corpus['end'] = corpus['end'].astype(str)
    corpus['born'] = corpus['born'].apply(lambda x: str(x)[:4])
    corpus.drop(columns=["district", "role", "source", "dead", "riksdagen_id", "location", "primary_name", "twitter"], inplace=True)
    cols = ["person_id", "name", "gender", "born", "start", "end", "chamber", "party_abbrev", "party"]
    corpus = corpus[cols]


    corpus["chair_nr"] = None
    corpus["chair_chamber"] = None
    corpus["sitting_from"] = None
    corpus["sitting_to"] = None
    empty = 0
    multi = 0
    add_rows = []
    rm_rows = []
    for i, r in tqdm(corpus.iterrows(), total=len(corpus)):
        swerik = r["person_id"]
        start = r["start"]
        end = r['end']
        if start == end:
            continue
        sitting = chair_mp.loc[
                (chair_mp['person_id'] == swerik) &
                (chair_mp['imp_start'] < end) &
                (chair_mp['imp_end'] >= start)
            ].copy()
        sitting.reset_index(inplace=True)
        sitting.sort_values(by=['parliament_year'], inplace=True)
        if not sitting.empty:
            if len(sitting['chair_id'].unique()) == 1:
                corpus.at[i, "sitting_from"] = sitting.at[0, 'start']
                corpus.at[i, "sitting_to"] = sitting.at[len(sitting)-1, 'end']
                chair_info = chairs_d[sitting.at[0, 'chair_id']]
                corpus.at[i, 'chair_nr'] = chair_info[0]
                corpus.at[i, 'chair_chamber'] = chair_info[1]
            else:
                #print("MULTIPLE CHAIRS IN MANDATE", swerik)
                #print(start, end)
                #print(sitting)
                rm_rows.append(i)
                add_rows = add_multi(sitting, r, add_rows, chairs_d)
                #multi += 1
        else:
            print("NO SEAT FOR", swerik)
            empty += 1
    corpus.drop(index=rm_rows, inplace=True)
    add_rows.append(corpus)
    corpus = pd.concat(add_rows, ignore_index=True)
    corpus.reset_index(inplace=True)
    corpus.sort_values(by=["person_id", "start", "chamber", "chair_nr"], inplace=True)
    corpus['sitting_from'] = corpus['sitting_from'].apply(lambda x: None if x == "nan" else x)
    corpus['sitting_to'] = corpus['sitting_to'].apply(lambda x: None if x == "nan" else x)
    corpus.drop(columns=['index'], inplace=True)
    corpus.drop_duplicates(inplace=True)
    corpus.drop(corpus.loc[(pd.notnull(corpus["start"])) & (corpus["start"] == corpus["end"])].index, axis=0, inplace=True)
    print(corpus)
    if args.version is None:
        args.version = datetime.now().strftime("%Y%m%d-%H%M%S")
    corpus.to_csv(f"{args.outfolder}/chair-dump-full_{args.version}.csv", index=False)

    print("empty chairs:", empty)
    #print("multi chairs:", multi)

    print("MP w/ no chair assignment:", len(corpus.loc[pd.isna(corpus['chair_nr'])]))
    print("MP w/ no party assignment:", len(corpus.loc[pd.isna(corpus['party'])]))
    print("chamber incoherance", test_chamber_coherance(corpus), 'of ', len(corpus))




if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--outfolder", type=str, default="dumps")
    parser.add_argument("--version", default=None)
    args = parser.parse_args()
    main(args)
