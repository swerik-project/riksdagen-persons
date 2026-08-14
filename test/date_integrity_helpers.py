"""
Shared date helpers for metadata integrity tests.

These helpers intentionally live in the local test package until the same
semantics are available from a released pyriksdagen version.
"""
import re

import pandas as pd


DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")


def parse_date_interval(value, is_end):
    """
    Parse partial date strings as interval boundaries.

    Start dates are expanded to the first possible day. End dates are expanded
    to the exclusive upper bound after the last possible day, so interval
    comparisons can use `start < other_end and end > other_start`.

    Returns:
        tuple: `(timestamp, precision, issue)`, where issue is `"blank"`,
        `"malformed"`, or `None`.
    """
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
