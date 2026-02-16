"""
Regression tests for party distribution L1 quality metrics.
"""

import os
import logging
from datetime import datetime
import pandas as pd
import unittest

logger = logging.getLogger("party_distribution_l1_test")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class TestPartyDistributionL1(unittest.TestCase):

    BASELINE_FILES = {
        "03-01": "test/data/test-party-distribution-l1-baseline-03-01.csv",
        "10-01": "test/data/test-party-distribution-l1-baseline-10-01.csv",
    }

    GENERATED_FILES = {
        "03-01": "quality/estimates/party-distribution/snapshot-03-01-l1.csv",
        "10-01": "quality/estimates/party-distribution/snapshot-10-01-l1.csv",
    }

    OUTPUT_DIR = "test/result"
    THRESHOLD = 0.05  # 5% allowed deterioration

    def write_err_df(self, name_str, df):
        now = datetime.now().strftime('%Y%m%d-%H%M%S')
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        outpath = f"{self.OUTPUT_DIR}/{now}_{name_str}.csv"
        df.to_csv(outpath, index=False)
        logger.warning(f"Wrote diagnostic file to {outpath}")

    def load_l1(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing file: {path}")

        df = pd.read_csv(path)

        required_cols = {"riksdagen_year", "chamber", "l1_distance"}
        if not required_cols.issubset(df.columns):
            raise ValueError(
                f"{path} missing required columns {required_cols}"
            )

        return df[["riksdagen_year", "chamber", "l1_distance"]]

    def compare_files(self, label):
        baseline_path = self.BASELINE_FILES[label]
        generated_path = self.GENERATED_FILES[label]

        logger.info(f"Comparing {label} baseline vs generated snapshot")

        baseline = self.load_l1(baseline_path)
        new = self.load_l1(generated_path)

        merged = baseline.merge(
            new,
            on=["riksdagen_year", "chamber"],
            suffixes=("_base", "_new"),
            how="outer",
            indicator=True
        )

        if not all(merged["_merge"] == "both"):
            mismatch = merged[merged["_merge"] != "both"]
            self.write_err_df(f"structural_mismatch_{label}", mismatch)
            self.fail(f"{label}: Structural mismatch detected.")

        merged["delta"] = merged["l1_distance_new"] - merged["l1_distance_base"]

        def pct_change(row):
            if row["l1_distance_base"] == 0:
                return 0 if row["l1_distance_new"] == 0 else float("inf")
            return row["delta"] / row["l1_distance_base"]

        merged["pct_change"] = merged.apply(pct_change, axis=1)

        regressions = merged[
            (merged["delta"] > 0) &
            (merged["pct_change"] > self.THRESHOLD)
        ]

        if not regressions.empty:
            logger.error(
                f"{label}: Regression exceeds {self.THRESHOLD*100:.0f}% threshold."
            )
            self.write_err_df(f"l1_regression_{label}", regressions)
            self.fail(
                f"{label}: L1 regression exceeds allowed threshold."
            )

        logger.info(
            f"{label} PASS — "
            f"mean baseline={baseline['l1_distance'].mean():.2f}, "
            f"mean snapshot={new['l1_distance'].mean():.2f}"
        )

    def test_l1_snapshot_03_01(self):
        self.compare_files("03-01")

    def test_l1_snapshot_10_01(self):
        self.compare_files("10-01")

    def tearDown(self):
        logger.info("Finished L1 regression test.\n")

if __name__ == "__main__":
    unittest.main()
