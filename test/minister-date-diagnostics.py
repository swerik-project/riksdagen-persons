#!/usr/bin/env python3
"""
Write a diagnostic report for minister date coverage and interval issues.

This is intentionally a reporting script, not a failing integrity test. It
normalizes partial dates to intervals so YYYY and YYYY-MM values can be compared
with full ISO dates.
"""
from pathlib import Path
import re

import pandas as pd


DATA_DIR = Path("data")
OUT_DIR = Path("test/result")
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


def get_gaps(ministers):
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
            if previous is not None and row["start_date"] > previous["end_date"]:
                rows.append({
                    "person_id": person_id,
                    "role": role,
                    "previous_government": previous["government"],
                    "previous_start": previous["start"],
                    "previous_end": previous["end"],
                    "current_government": row["government"],
                    "current_start": row["start"],
                    "current_end": row["end"],
                    "gap_days": (row["start_date"] - previous["end_date"]).days,
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


def write_report(summary, overlaps, gaps, government_mismatches):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    overlaps.to_csv(OUT_DIR / "minister-date-overlaps.csv", index=False)
    gaps.to_csv(OUT_DIR / "minister-date-gaps.csv", index=False)
    government_mismatches.to_csv(OUT_DIR / "minister-government-date-mismatches.csv", index=False)
    no_intersection = government_mismatches[
        ~government_mismatches["has_intersection"]
    ] if len(government_mismatches) else government_mismatches
    no_intersection.to_csv(OUT_DIR / "minister-government-date-no-intersection.csv", index=False)

    lines = [
        "# Minister Date Diagnostics",
        "",
        "This diagnostic normalizes partial dates to half-open intervals:",
        "",
        "- `YYYY` start dates begin on January 1; end dates stop at January 1 the following year.",
        "- `YYYY-MM` start dates begin on the first day; end dates stop at the first day of the following month.",
        "- `YYYY-MM-DD` dates use the recorded day as the boundary.",
        "- A minister row ending on the same date another begins is treated as adjacent, not overlapping.",
        "",
        "## Summary",
        "",
    ]

    for key, value in summary.items():
        lines.append(f"- {key}: {value}")

    lines.extend([
        "",
        "## Output Files",
        "",
        "- `test/result/minister-date-overlaps.csv`",
        "- `test/result/minister-date-gaps.csv`",
        "- `test/result/minister-government-date-mismatches.csv`",
        "- `test/result/minister-government-date-no-intersection.csv`",
        "",
    ])

    (OUT_DIR / "minister-date-diagnostics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    gaps = get_gaps(ministers)
    government_mismatches = get_government_mismatches(ministers, governments)

    summary = {
        "minister rows": len(ministers),
        "unique minister person IDs": ministers["person_id"].nunique(),
        "unique person-role groups": ministers[["person_id", "role"]].drop_duplicates().shape[0],
        "blank minister start": int((ministers["start_issue"] == "blank").sum()),
        "blank minister end": int((ministers["end_issue"] == "blank").sum()),
        "malformed minister start": int((ministers["start_issue"] == "malformed").sum()),
        "malformed minister end": int((ministers["end_issue"] == "malformed").sum()),
        "inverted minister intervals": len(inverted_minister_dates),
        "person-role adjacent overlaps": len(overlaps),
        "person-role same-interval overlaps": int((overlaps["overlap_type"] == "same_interval").sum()) if len(overlaps) else 0,
        "person-role partial overlaps": int((overlaps["overlap_type"] == "partial_overlap").sum()) if len(overlaps) else 0,
        "person-role adjacent gaps": len(gaps),
        "minister rows not contained in government interval": len(government_mismatches),
        "minister rows with no government interval intersection": int((~government_mismatches["has_intersection"]).sum()) if len(government_mismatches) else 0,
    }

    write_report(summary, overlaps, gaps, government_mismatches)
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
