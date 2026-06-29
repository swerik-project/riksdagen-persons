#!/usr/bin/env python3
"""
Test minister date coverage and interval integrity.

This normalizes partial dates to intervals so YYYY and YYYY-MM values can be
compared with full ISO dates.
"""
from pathlib import Path
import re

import pandas as pd


DATA_DIR = Path("data")
DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")


def parse_date_interval(value, is_end):
    if pd.isna(value) or str(value).strip() == "":
        if is_end:
            return pd.Timestamp.max.normalize(), None, "blank"
        return None, None, "blank"

    value = str(value).strip()
    match = DATE_RE.match(value)
    if match is None:
        return None, None, "malformed"

    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else None
    day = int(match.group(3)) if match.group(3) else None

    try:
        if month is None:
            if is_end:
                return pd.Timestamp(year + 1, 1, 1), "year", None
            return pd.Timestamp(year, 1, 1), "year", None

        if day is None:
            if is_end:
                if month == 12:
                    return pd.Timestamp(year + 1, 1, 1), "month", None
                return pd.Timestamp(year, month + 1, 1), "month", None
            return pd.Timestamp(year, month, 1), "month", None

        return pd.Timestamp(year, month, day), "day", None
    except ValueError:
        return None, None, "malformed"


def add_date_columns(df):
    starts = df["start"].apply(lambda value: parse_date_interval(value, is_end=False))
    ends = df["end"].apply(lambda value: parse_date_interval(value, is_end=True))

    df = df.copy()
    df["start_date"] = starts.apply(lambda result: result[0])
    df["start_precision"] = starts.apply(lambda result: result[1])
    df["start_issue"] = starts.apply(lambda result: result[2])
    df["end_date"] = ends.apply(lambda result: result[0])
    df["end_precision"] = ends.apply(lambda result: result[1])
    df["end_issue"] = ends.apply(lambda result: result[2])
    return df


def get_overlaps(ministers):
    rows = []
    valid = ministers[
        ministers["start_date"].notna()
        & ministers["end_date"].notna()
        & (ministers["end_issue"] != "blank")
    ]

    for (person_id, role), group in valid.groupby(["person_id", "role"], dropna=False):
        group = group.sort_values(["start_date", "end_date", "government"]).reset_index(drop=True)
        previous = None
        for _, row in group.iterrows():
            if previous is not None and row["start_date"] < previous["end_date"]:
                rows.append({
                    "person_id": person_id,
                    "role": role,
                    "overlap_type": "same_interval" if (
                        row["start_date"] == previous["start_date"]
                        and row["end_date"] == previous["end_date"]
                    ) else "partial_overlap",
                    "previous_government": previous["government"],
                    "previous_start": previous["start"],
                    "previous_end": previous["end"],
                    "current_government": row["government"],
                    "current_start": row["start"],
                    "current_end": row["end"],
                })
            if previous is None or row["end_date"] > previous["end_date"]:
                previous = row

    return pd.DataFrame(rows)


def get_government_mismatches(ministers, governments):
    rows = []
    government_by_name = governments.set_index("government")
    valid = ministers[ministers["start_date"].notna() & ministers["end_date"].notna()]

    for _, row in valid.iterrows():
        gov = government_by_name.loc[row["government"]]
        has_intersection = row["start_date"] < gov["end_date"] and row["end_date"] > gov["start_date"]
        contained = row["start_date"] >= gov["start_date"] and row["end_date"] <= gov["end_date"]

        if not contained:
            rows.append({
                "person_id": row["person_id"],
                "role": row["role"],
                "government": row["government"],
                "minister_start": row["start"],
                "minister_end": row["end"],
                "government_start": gov["start"],
                "government_end": gov["end"],
                "has_intersection": has_intersection,
                "contained_in_government": contained,
            })

    return pd.DataFrame(rows)


def format_rows(df, columns, limit=10):
    if df.empty:
        return ""
    return "\n" + df[columns].head(limit).to_string(index=False)


def main():
    ministers = pd.read_csv(DATA_DIR / "minister.csv", dtype=str, keep_default_na=False)
    governments = pd.read_csv(DATA_DIR / "government.csv", dtype=str, keep_default_na=False)

    ministers = add_date_columns(ministers)
    governments = add_date_columns(governments)

    inverted_minister_dates = ministers[
        ministers["start_date"].notna()
        & ministers["end_date"].notna()
        & (ministers["start_date"] > ministers["end_date"])
    ]

    overlaps = get_overlaps(ministers)
    government_mismatches = get_government_mismatches(ministers, governments)
    partial_overlaps = overlaps[
        overlaps["overlap_type"] == "partial_overlap"
    ] if len(overlaps) else overlaps
    no_intersection = government_mismatches[
        ~government_mismatches["has_intersection"]
    ] if len(government_mismatches) else government_mismatches

    malformed_starts = ministers[ministers["start_issue"] == "malformed"]
    malformed_ends = ministers[ministers["end_issue"] == "malformed"]

    assert malformed_starts.empty, (
        "Malformed minister start dates:"
        + format_rows(malformed_starts, ["person_id", "government", "role", "start"])
    )
    assert malformed_ends.empty, (
        "Malformed minister end dates:"
        + format_rows(malformed_ends, ["person_id", "government", "role", "end"])
    )
    assert inverted_minister_dates.empty, (
        "Minister rows with start after end:"
        + format_rows(inverted_minister_dates, ["person_id", "government", "role", "start", "end"])
    )
    assert partial_overlaps.empty, (
        "Minister person-role intervals with partial overlaps:"
        + format_rows(
            partial_overlaps,
            [
                "person_id",
                "role",
                "previous_government",
                "previous_start",
                "previous_end",
                "current_government",
                "current_start",
                "current_end",
            ],
        )
    )
    assert no_intersection.empty, (
        "Minister rows with no intersection with their government interval:"
        + format_rows(
            no_intersection,
            [
                "person_id",
                "role",
                "government",
                "minister_start",
                "minister_end",
                "government_start",
                "government_end",
            ],
        )
    )


if __name__ == "__main__":
    main()
