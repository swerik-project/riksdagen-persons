from datetime import date
from trainerlog import get_logger

import argparse
import calendar
import matplotlib.pyplot as plt
import os
import polars as pl

logger = get_logger(name="ebun", level="DEBUG")

def parse_date_fuzzy(v, kind="start"):
    """
    Parse partial dates; fills missing month/day for start/end.
    Supports formats: YYYY, YYYY-MM, YYYY-MM-DD
    """
    if v is None or str(v).strip() == "":
        return date(1000,1,1) if kind == "start" else date(9999,12,31)
    parts = str(v).split("-")
    try:
        if len(parts) == 1:
            return date(int(parts[0]),1 if kind == "start" else 12,1 if kind == "start" else 31)
        elif len(parts) == 2:
            year, month = int(parts[0]), int(parts[1])
            day = 1 if kind == "start" else calendar.monthrange(year, month)[1]
            return date(year, month, day)
        else:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception as e:
        logger.warning(f"Failed to parse date '{v}': {e}")
        return None


def parse_dates_fuzzy(df, start_cols=None, end_cols=None):
    """Apply fuzzy date parsing to specified start/end columns in a Polars DataFrame."""
    start_cols = start_cols or []
    end_cols = end_cols or []

    def apply_fuzzy(col, kind):
        values = df[col].to_list()
        parsed = [parse_date_fuzzy(v, kind=kind) for v in values]
        return pl.Series(col, parsed)

    for c in start_cols:
        if c in df.columns:
            df = df.with_columns(apply_fuzzy(c, kind="start"))

    for c in end_cols:
        if c in df.columns:
            df = df.with_columns(apply_fuzzy(c, kind="end"))

    return df


def build_yearly_long(mp, affiliation, riksdag_year, party, args):
    """Build yearly long-format party distribution with original and mapped Riksdag years using Polars."""

    ###--- 1. Create years we are interested in the snapshot ---###
    calendar_years = list(range(args.start, args.end + 1))

    years = pl.DataFrame({
        "calendar_year": calendar_years,
        "check_date": [date(y, args.month, args.day) for y in calendar_years]
    })

    years = (
        years
        .with_columns(
            pl.when(pl.col("calendar_year") < 1971)
            .then(pl.lit(["fk", "ak"]))
            .otherwise(pl.lit(["ek"]))
            .alias("chamber_list")
        )
        .explode("chamber_list")
        .rename({"chamber_list": "chamber"})
    )

    ###--- 2. Match calendar year with the rightful parliament year ---###
    years_sorted = years.sort("check_date", "chamber")
    riksdag_sorted = riksdag_year.sort("start")
    years_snap = years_sorted.join_asof(
        riksdag_sorted,
        left_on="check_date",
        right_on="start",
        by="chamber",
        strategy="backward", # nearest start <= check_date
        suffix="_riksdag"
    )

    years_snap = years_snap.with_columns([
        pl.when(pl.col("check_date") <= pl.col("end"))
        .then(pl.col("parliament_year"))
        .otherwise(None)
        .alias("riksdag_year"),

        pl.when(pl.col("check_date") <= pl.col("end"))
        .then(pl.col("specifier"))
        .otherwise(None)
        .alias("period")
    ]).select("calendar_year","check_date","parliament_year","specifier","chamber")

    ###--- 3. Find all the mp-s active on those given years on that date ---###
    mp = mp.with_columns([
        pl.when((pl.col("role") == "andrakammarledamot") )
        .then(pl.lit("ak"))
        .otherwise(
            pl.when((pl.col("role") == "förstakammarledamot"))
                .then(pl.lit("fk"))
                .otherwise(pl.lit("ek"))
        )
        .alias("role")
    ]).rename({"start": "start_mandate", "end": "end_mandate", "role": "chamber"})

    mp_snap = mp.join_where(
        years_snap,
        (pl.col("start_mandate") <= pl.col("check_date")) &
        (pl.col("end_mandate") >= pl.col("check_date")) &
        (pl.col("chamber") == pl.col("chamber_right"))
    ).drop("chamber_right")

    ###--- 4.1 Add the party affiliation of MPs on those dates ---###
    affiliation = affiliation.rename({
        "start": "start_aff",
        "end": "end_aff"
    })

    merged = (
        mp_snap
        .join(
            affiliation,
            on="person_id",
            how="inner"
        )
        .filter(
            (pl.col("start_aff") <= pl.col("check_date")) &
            (pl.col("end_aff") >= pl.col("check_date"))
        )
        .with_columns(
            # interval size (used to pick most specific match)
            (pl.col("end_aff") - pl.col("start_aff"))
            .dt.total_days()
            .alias("interval_len")
        )
        .sort([
            "person_id",
            "check_date",
            "interval_len"
        ])
        .group_by(["person_id", "check_date"])
        .agg(pl.all().first())
    ).drop("interval_len")

    ###--- 4.2 Fill missing SWERIK party IDs using party table ---###
    party_lookup = party.select([
        "party",
        "swerik_party_id"
    ]).unique()

    merged = merged.join(
        party_lookup,
        on="party",
        how="left",
        suffix="_party"
    )

    merged = merged.with_columns(
        pl.col("swerik_party_id")
        .fill_null(pl.col("swerik_party_id_party"))
        .fill_null("No SWERIK-id found")
    ).drop("swerik_party_id_party")

    ###--- 5. Aggregate and count the party memberships ---###
    result = (
        merged
        .group_by(["calendar_year", "parliament_year", "chamber", "swerik_party_id"])
        .agg(
            pl.n_unique("person_id").alias("nr_seats")
        )
    )

    # Final column order
    result = result.sort(by=[
        "calendar_year", "chamber"
    ])

    return result


def compute_regression_metrics(diff_df):
    """Aggregate L1 distance per calendar and parliamentary year."""

    l1_df = (
        diff_df
        .group_by(["calendar_year", "parliament_year", "chamber"])
        .agg(
            pl.col("abs_diff").sum().alias("l1_distance")
        )
    )

    return {
        "l1_per_year_chamber": l1_df,
        "max_l1": l1_df.select(pl.col("l1_distance").max()).item() if l1_df.height > 0 else 0,
        "mean_l1": l1_df.select(pl.col("l1_distance").mean()).item() if l1_df.height > 0 else 0.0,
        "max_party_diff": diff_df.select(pl.col("abs_diff").max()).item() if diff_df.height > 0 else 0,
        "nr_rows_with_diff": diff_df.select(
            (pl.col("abs_diff") > 0).sum()
        ).item(),
    }


def compute_distribution_diff(df_snapshot, df_gold, party_df):

    # --- 1. Prepare snapshot ---
    snap = df_snapshot.with_columns([
        pl.col("swerik_party_id").cast(pl.Utf8),
        pl.col("chamber").cast(pl.Utf8),
        pl.col("parliament_year").cast(pl.Int64),
    ]).rename({"nr_seats": "nr_seats_snapshot"})

    # --- 2. Prepare gold ---
    gold = df_gold.with_columns([
        pl.col("swerik_party_id").cast(pl.Utf8),
        pl.col("chamber").cast(pl.Utf8),
        pl.col("parliament_year").cast(pl.Int64),
    ]).rename({"nr_seats": "nr_seats_gold"})

    # --- 3. Build FULL key universe---
    keys = pl.concat([
        snap.select(["parliament_year", "chamber", "swerik_party_id"]),
        gold.select(["parliament_year", "chamber", "swerik_party_id"])
    ]).unique()

    # --- 4. Attach snapshot ---
    merged = keys.join(
        snap,
        on=["parliament_year", "chamber", "swerik_party_id"],
        how="left"
    )

    # --- 5. Attach gold using ASOF logic ---
    snap = merged.sort(["chamber", "swerik_party_id", "parliament_year"])
    gold = gold.sort(["chamber", "swerik_party_id", "parliament_year"])

    merged = snap.join_asof(
        gold,
        left_on="parliament_year",
        right_on="parliament_year",
        by=["chamber", "swerik_party_id"],
        strategy="backward",
        suffix="_gold"
    )

    # --- 6. Fill missing values ---
    merged = merged.with_columns([
        pl.col("nr_seats_snapshot").fill_null(0),
        pl.col("nr_seats_gold").fill_null(0),
    ])

    # --- restrict gold to snapshot support due to 1th of October can land in two different year patches.
    valid_years = df_snapshot.select("parliament_year").unique()

    merged = merged.filter(
        pl.col("parliament_year").is_in(valid_years["parliament_year"])
    )

    # --- 8. Add party names ---
    party_lookup = party_df.select([
        "swerik_party_id",
        "party",
        "inception",
        "dissolution"
    ]).unique()


    merged = merged.join(
        party_lookup,
        on="swerik_party_id",
        how="left"
    )

    merged = merged.with_columns([
        pl.when(
            (pl.col("calendar_year") < pl.col("inception").dt.year()) |
            (
                pl.col("dissolution").is_not_null() &
                (pl.col("calendar_year") > pl.col("dissolution").dt.year())
            )
        )
        .then(0)
        .otherwise(pl.col("nr_seats_gold"))
        .alias("nr_seats_gold")
    ])

    merged = merged.with_columns(
        pl.col("party").fill_null("No SWERIK-id found")
    )

    # --- 9. Debug flag ---
    merged = merged.with_columns(
        pl.when(pl.col("swerik_party_id").is_in(party_df["swerik_party_id"]))
        .then(pl.lit(False))
        .otherwise(pl.lit(True))
        .alias("missing_party_mapping")
    )

    # --- 7. Compute diffs ---
    merged = merged.with_columns([
        (pl.col("nr_seats_snapshot") - pl.col("nr_seats_gold")).alias("diff"),
        (pl.col("nr_seats_snapshot") - pl.col("nr_seats_gold")).abs().alias("abs_diff"),
    ])

    merged = merged.with_columns([
        pl.col("calendar_year").fill_null(pl.col("parliament_year"))
    ])

    # --- 10. Final sort ---
    return merged.sort([
        "calendar_year",
        "parliament_year",
        "chamber",
        "swerik_party_id"
    ])


def plot_l1_distances(l1_df, output_dir, suffix):
    """Plot L1 distances per chamber over years and save as PNG."""

    l1_df = (
        l1_df
        .with_columns(
            pl.col("calendar_year").cast(pl.Int64)
        )
        .sort("calendar_year")
    )

    unique_years = l1_df.select("calendar_year").unique().sort("calendar_year").to_series().to_list()
    year_positions = {year: idx for idx, year in enumerate(unique_years)}

    l1_df = l1_df.with_columns(
        pl.col("calendar_year")
        .replace_strict(year_positions)
        .alias("x_pos")
    )

    pdf = l1_df.to_pandas()

    plt.figure(figsize=(14, 6))

    for chamber, grp in pdf.groupby("chamber"):
        plt.plot(grp["x_pos"], grp["l1_distance"], marker='o', label=chamber.upper())

    plt.title("L1 Distance Between Snapshot and Gold-Standard per Chamber")
    plt.xlabel("Calendar Year")
    plt.ylabel("L1 Distance")

    tick_positions = [year_positions[y] for i, y in enumerate(unique_years) if i % 5 == 0]
    tick_labels = [y for i, y in enumerate(unique_years) if i % 5 == 0]

    plt.xticks(ticks=tick_positions, labels=tick_labels, rotation=45)
    plt.legend(title="Chamber")
    plt.grid(True)
    plt.tight_layout()

    plot_file = os.path.join(output_dir, f"snapshot-{suffix}-l1-plot.png")
    plt.savefig(plot_file, dpi=150)
    plt.close()

    logger.info(f"L1 distance plot saved to: {plot_file}")


def main(args):
    os.makedirs(args.output, exist_ok=True)

    try:
        date(year = args.start, month = args.month, day=args.day)
    except ValueError:
        raise ValueError(f"Invalid date: {args.start}-{args.month}-{args.day}")
    
    if args.start > args.end:
        raise ValueError("Start year cannot be greater than end year.")
    
    suffix = f"{args.month:02d}-{args.day:02d}"

    logger.info("Loading data...")
    affiliation = parse_dates_fuzzy(pl.read_csv("data/party_affiliation.csv"), ["start"], ["end"]).drop("party_id", "start_precision", "end_precision")
    mp = parse_dates_fuzzy(pl.read_csv("data/member_of_parliament.csv"), ["start"], ["end"]).drop("district")
    riksdag_year_df = parse_dates_fuzzy(pl.read_csv("data/riksdag-year.csv"), ["start"], ["end"])
    party = parse_dates_fuzzy(pl.read_csv("data/party.csv"), ["inception"], ["dissolution"])
    gold = parse_dates_fuzzy(pl.read_csv(args.gold)) if args.gold else None

    logger.info("Building snapshot...")

    df = build_yearly_long(mp, affiliation, riksdag_year_df, party, args)
    df.write_csv(os.path.join(args.output, f"snapshot-distribution-{suffix}.csv"), float_precision=0)

    if gold is not None:
        logger.info("Running metrics...")

        diff_df = compute_distribution_diff(df, gold, party)
        metrics = compute_regression_metrics(diff_df)

        diff_df.write_csv(os.path.join(args.output, f"snapshot-{suffix}-diff.csv"))

        l1_df = metrics["l1_per_year_chamber"]
        l1_sorted = l1_df.sort(
            ["calendar_year", "parliament_year", "chamber"]
        )
        l1_sorted.write_csv(os.path.join(args.output, f"snapshot-{suffix}-l1.csv"))

        logger.debug(f"Metrics:\n{l1_sorted}")

        plot_l1_distances(metrics["l1_per_year_chamber"], args.output, suffix)

    logger.info("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=str, help="Path to gold-standard.")
    parser.add_argument("--day", type=int, required=True, help="Day to take the party distribution.")
    parser.add_argument("--month", type=int, required=True, help="Month to take the party distribution.")
    parser.add_argument("--output", type=str, default="quality/estimates/party-distribution/", help="Output directory.")
    parser.add_argument("--start", type=int, default=1912, help="Define the start year to build the party distribution.")
    parser.add_argument("--end", type=int, default=2023, help="Define the end year to build the party distribution.")
    args = parser.parse_args()
    main(args)