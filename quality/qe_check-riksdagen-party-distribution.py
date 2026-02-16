#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import calendar
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
from trainerlog import get_logger

logger = get_logger(name="ebun", level="DEBUG")

def read_csv_safe(path):
    try:
        df = pd.read_csv(path, dtype=str).replace({"": None})
        if df.empty:
            logger.warning(f"CSV at {path} is empty.")
        return df
    except FileNotFoundError:
        logger.error(f"File not found: {path}")
        raise
    except pd.errors.ParserError as e:
        logger.error(f"Error parsing CSV {path}: {e}")
        raise

def parse_date_fuzzy(v, kind="start"):
    if pd.isna(v):
        return pd.NaT
    parts = str(v).split("-")
    try:
        if len(parts) == 1:
            return pd.Timestamp(f"{parts[0]}-01-01" if kind=="start" else f"{parts[0]}-12-31")
        elif len(parts) == 2:
            year, month = int(parts[0]), int(parts[1])
            day = 1 if kind=="start" else calendar.monthrange(year, month)[1]
            return pd.Timestamp(f"{year}-{month:02d}-{day}")
        else:
            return pd.Timestamp(v)
    except Exception as e:
        logger.warning(f"Failed to parse date '{v}': {e}")
        return pd.NaT
    

def parse_dates_fuzzy(df, start_cols=[], end_cols=[]):
    for c in start_cols:
        if c in df.columns:
            df[c] = df[c].apply(parse_date_fuzzy, kind="start")
    for c in end_cols:
        if c in df.columns:
            df[c] = df[c].apply(parse_date_fuzzy, kind="end")
    return df


def compute_distribution_diff(df_snapshot, df_gold):
    snap = df_snapshot.rename(columns={"nr_seats": "nr_seats_snapshot"}).copy()
    gold = df_gold.rename(columns={"nr_seats": "nr_seats_gold"}).copy()

    snap = snap.astype({"party_id": str, "chamber": str, "year": int})
    gold = gold.astype({"party_id": str, "chamber": str, "year": int})

    snap_blocks = []

    for chamber, snap_grp in snap.groupby("chamber", sort=False):
        gold_grp = gold[gold["chamber"] == chamber]
        elections = np.sort(gold_grp["year"].unique())
        breaks = np.append(elections, np.inf)
        intervals = pd.IntervalIndex.from_breaks(breaks, closed="left")

        idx = intervals.get_indexer(snap_grp["year"])
        snap_grp = snap_grp.copy()
        snap_grp["year_block"] = np.where(idx >= 0, elections[idx], -1)
        snap_blocks.append(snap_grp)

    snap = pd.concat(snap_blocks, ignore_index=True)

    gold_blocked = gold.rename(columns={"year": "year_block"})

    merged = snap.merge(
        gold_blocked[["year_block","chamber","party_id","nr_seats_gold"]],
        on=["year_block","chamber","party_id"],
        how="outer"
    )

    merged["nr_seats_gold"] = merged["nr_seats_gold"].fillna(0).astype(int)
    merged["nr_seats_snapshot"] = merged["nr_seats_snapshot"].fillna(0).astype(int)
    
    merged["seat_diff"] = merged["nr_seats_snapshot"] - merged["nr_seats_gold"]
    merged["abs_diff"] = merged["seat_diff"].abs()

    merged = merged.rename(columns={"year": "riksdagen_year", "year_block": "gold_year", "seat_diff": "diff"})
    merged = merged[["riksdagen_year", "chamber", "gold_year", "party_id", "party_name", "nr_seats_snapshot", "nr_seats_gold", "diff", "abs_diff"]]
    merged = merged.sort_values(["riksdagen_year", "chamber", "party_id"]).reset_index(drop=True)

    return merged



def compute_regression_metrics(diff_df):
    l1_df = (
        diff_df
        .groupby(["riksdagen_year", "chamber"])["abs_diff"]
        .sum()
        .reset_index(name="l1_distance")
    )
    return {
        "l1_per_year_chamber": l1_df,
        "max_l1": int(l1_df["l1_distance"].max()) if len(l1_df) else 0,
        "mean_l1": float(l1_df["l1_distance"].mean()) if len(l1_df) else 0.0,
        "max_party_diff": int(diff_df["abs_diff"].max()) if len(diff_df) else 0,
        "nr_rows_with_diff": int((diff_df["abs_diff"] > 0).sum()),
    }


def build_yearly_long(mp, affiliation, party, explicit_no_party, month_day, year_start, year_end, riksdag_df):

    def prioritize_chamber(df):
        if df["year"].iloc[0] >= 1971:
            df = df.sort_values(by="chamber", key=lambda x: x.map({"ek":0, "ak":1, "fk":2}))
        return df
    
    def map_to_riksdag_year(row):
        year = row["year"]
        if year <= 1975:
            return year

        snapshot_date = pd.Timestamp(year, month, day)
        candidates = riksdag_df.query("@snapshot_date >= start and @snapshot_date <= end")
        if not candidates.empty:
            ry = str(candidates.iloc[0]["parliament_year"])
            return 199900 if ry == "19992000" else int(ry)

        past = riksdag_df[riksdag_df["start"] <= snapshot_date].sort_values("start", ascending=False)
        future = riksdag_df[riksdag_df["start"] > snapshot_date].sort_values("start")
        if not past.empty:
            return int(past.iloc[0]["parliament_year"])
        elif not future.empty:
            return int(future.iloc[0]["parliament_year"])
        return year

    month, day = month_day

    years = pd.DataFrame({
        "year": range(year_start, year_end + 1)
    })
    years["check_date"] = pd.to_datetime(
        years["year"].astype(str) + f"-{month:02d}-{day:02d}"
    )

    mp["start"] = mp["start"].fillna(pd.Timestamp("1000-01-01"))
    mp["end"] = mp["end"].fillna(pd.Timestamp("9999-12-31"))

    mp["_tmp"] = 1
    years["_tmp"] = 1
    mp_snap = mp.merge(years, on="_tmp").drop(columns="_tmp")

    mp_snap = mp_snap[
        (mp_snap["start"] <= mp_snap["check_date"]) &
        (mp_snap["end"] >= mp_snap["check_date"])
    ]

    mp_snap["chamber"] = None
    mp_snap.loc[(mp_snap["role"] == "andrakammarledamot") & (mp_snap["year"] < 1971), "chamber"] = "ak"
    mp_snap.loc[(mp_snap["role"] == "förstakammarledamot") & (mp_snap["year"] < 1971), "chamber"] = "fk"

    mp_snap.loc[(mp_snap["chamber"].isna()) & (mp_snap["year"] >= 1971), "chamber"] = "ek"

    mp_snap = mp_snap.dropna(subset=["chamber"])

    affiliation["start"] = affiliation["start"].fillna(pd.Timestamp("1000-01-01"))
    affiliation["end"] = affiliation["end"].fillna(pd.Timestamp("9999-12-31"))

    merged = mp_snap.merge(
        affiliation[['person_id','swerik_party_id','start','end']],
        on='person_id',
        how='left',
        suffixes=("_mp","_aff")
    )

    merged["active_aff"] = (
        (merged['start_aff'] <= merged['check_date']) &
        (merged['end_aff'] >= merged['check_date'])
    )

    merged["active_rank"] = merged["active_aff"].astype(int)

    merged["start_aff"] = merged["start_aff"].fillna(pd.Timestamp("1000-01-01"))

    merged = merged.sort_values(
        ["person_id","year","chamber","active_rank","start_aff"],
        ascending=[True,True,True,False,False]
    )

    merged = merged.groupby(["person_id","year"], group_keys=False).apply(prioritize_chamber)
    merged = merged.drop_duplicates(["person_id","year"])

    merged.loc[~merged["active_aff"], "swerik_party_id"] = None

    party_map = dict(zip(
        party["swerik_party_id"],
        party["party"].fillna("utan_partibeteckning")
            .str.strip()
            .str.lower()
            .str.replace(" ", "_", regex=False)
    ))
    merged["party_name"] = merged["swerik_party_id"].map(party_map).fillna("utan_partibeteckning")
    merged["party_id"] = merged["swerik_party_id"]

    no_party_ids = set(explicit_no_party["person_id"])
    mask = merged["person_id"].isin(no_party_ids)
    merged.loc[mask, "party_name"] = "utan_partibeteckning"
    merged.loc[mask, "party_id"] = None

    merged["party_name"] = merged["party_name"].fillna("utan_partibeteckning")

    df_long = (
        merged
        .drop_duplicates(["year","person_id","party_name","chamber"])
        .groupby(["year","chamber","party_id","party_name"])
        .size()
        .reset_index(name="nr_seats")
    )

    riksdag_df = riksdag_df.copy()
    riksdag_df["start"] = pd.to_datetime(riksdag_df["start"])
    riksdag_df["end"] = pd.to_datetime(riksdag_df["end"])

    df_long["year"] = df_long.apply(map_to_riksdag_year, axis=1)
    df_long = df_long[["year", "chamber", "party_id", "party_name", "nr_seats"]]
    df_long["year"] = pd.to_numeric(df_long["year"], errors='coerce').astype(int)

    return df_long


def plot_l1_distances(l1_df, output_dir, suffix):
    l1_df = l1_df.copy()
    
    l1_df["riksdagen_year"] = pd.to_numeric(l1_df["riksdagen_year"], errors="coerce").astype(int)

    l1_df = l1_df.sort_values("riksdagen_year").reset_index(drop=True)

    year_positions = {year: idx for idx, year in enumerate(l1_df["riksdagen_year"].unique())}
    l1_df["x_pos"] = l1_df["riksdagen_year"].map(year_positions)

    plt.figure(figsize=(14, 6))
    for chamber, grp in l1_df.groupby("chamber"):
        plt.plot(grp["x_pos"], grp["l1_distance"], marker='o', label=chamber.upper())

    plt.title("L1 Distance Between Snapshot and Gold-Standard per Chamber")
    plt.xlabel("Riksdagen Year")
    plt.ylabel("L1 Distance")

    all_years = list(year_positions.keys())
    tick_positions = [year_positions[year] for i, year in enumerate(all_years) if i % 5 == 0]
    tick_labels = [all_years[i] for i in range(len(all_years)) if i % 5 == 0]

    plt.xticks(ticks=tick_positions, labels=tick_labels, rotation=45)
    plt.legend(title="Chamber")
    plt.grid(True)
    plt.tight_layout()

    plot_file = os.path.join(output_dir, f"snapshot-{suffix}-l1-plot.png")
    plt.savefig(plot_file, dpi=150)
    plt.close()
    logger.info(f"L1 distance plot saved to: {plot_file}")


def main(args):
    corpus_dir = args.corpus_data
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    party_csv = os.path.join(corpus_dir, "party.csv")
    affiliation_csv = os.path.join(corpus_dir, "party_affiliation.csv")
    member_csv = os.path.join(corpus_dir, "member_of_parliament.csv")
    no_party_csv = os.path.join(corpus_dir, "explicit_no_party.csv")
    riksdag_year_csv = os.path.join(corpus_dir, "riksdag-year.csv")
    year_start = args.start
    year_end = args.end

    try:
        pd.Timestamp(year=args.start, month=args.month, day=args.day)
    except ValueError:
        raise ValueError(f"Invalid date: {args.year}-{args.month}-{args.day}")


    if args.start > args.end:
        raise ValueError("Start year cannot be greater than end year.")

    
    suffix = f"{args.month:02d}-{args.day:02d}"
    output_snap = os.path.join(output_dir, f"snapshot-distribution-{suffix}.csv")

    logger.info("Loading data...")
    party = parse_dates_fuzzy(read_csv_safe(party_csv), ["inception"], ["dissolution"])
    affiliation = parse_dates_fuzzy(read_csv_safe(affiliation_csv), ["start"], ["end"])
    mp = parse_dates_fuzzy(read_csv_safe(member_csv), ["start"], ["end"])
    explicit_no_party = read_csv_safe(no_party_csv)
    gold_df = read_csv_safe(args.gold) if args.gold else None
    riksdag_year_df = read_csv_safe(riksdag_year_csv)

    logger.info("Building snapshot...")

    df = build_yearly_long(
        mp.copy(),
        affiliation.copy(),
        party.copy(),
        explicit_no_party,
        (args.month, args.day),
        year_start,
        year_end,
        riksdag_year_df
    )
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype(int)
    df.to_csv(output_snap, index=False, float_format='%.0f')


    if gold_df is not None:
        logger.info("Running metrics...")
        diff_df = compute_distribution_diff(df, gold_df)
        metrics = compute_regression_metrics(diff_df)

        diff_df.to_csv(os.path.join(output_dir, f"snapshot-{suffix}-diff.csv"), index=False)
        metrics["l1_per_year_chamber"].to_csv(os.path.join(output_dir, f"snapshot-{suffix}-l1.csv"), index=False)

        logger.debug(f"Metrics:\n{metrics}")

        plot_l1_distances(metrics["l1_per_year_chamber"], output_dir, suffix)

    logger.info("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=str, help="Path to gold-standard.")
    parser.add_argument("--day", type=int, required=True, help="Day to take the party distribution.")
    parser.add_argument("--month", type=int, required=True, help="Month to take the party distribution.")
    parser.add_argument("--corpus-data", type=str, default="data/", help="Location of the riksdagen-persons data files.")
    parser.add_argument("--output", type=str, default="quality/estimates/party-distribution/", help="Output directory.")
    parser.add_argument("--start", type=int, default=1912, help="Define the start year to build the party distribution.")
    parser.add_argument("--end", type=int, default=2023, help="Define the end year to build the party distribution.")
    args = parser.parse_args()
    main(args)

