"""
Test that metadata tables are sorted correctly
"""
import json
import polars as pl
from pytest_cfg_fetcher.fetch import fetch_config
import json
import unittest
from pathlib import Path
from trainerlog import get_logger
LOGGER = get_logger("test-sort-order")
import numpy as np

class Test(unittest.TestCase):

    def fetch_sort_order(self):
        with open("test/data/sort-order.json") as f: 
            sort_order =  json.load(f)
        return sort_order

    def test_keys_provided(self):
        """
        Test that sort-order.json contains each file in data/*.csv 
        """
        sort_order = self.fetch_sort_order()
        missing = 0
        for p in Path("data").glob("*.csv"):
            filename = p.stem + p.suffix
            if not filename in sort_order:
                LOGGER.error(f"A sort key was not provided for {filename}")
                missing += 1
        self.assertEqual(missing, 0, f"A sort key was not provided for {missing} file(s)")

    def test_sort_order(self):
        """
        Test that the files in sort-order.json are properly sorted
        """
        sort_order = self.fetch_sort_order()
        errors = 0
        no_duplicates = 0
        missing = 0
        for filename, val in sort_order.items():
            sort_keys = None
            descending = False
            if isinstance(val, list):
                sort_keys = val
            else:
                sort_keys = val["columns"]
                descending = not val["ascending"]
            if len(sort_keys) >= 1:
                df = pl.read_csv(f"data/{filename}", infer_schema_length=10000)
                duplicated = df.filter(df.select(sort_keys).is_duplicated())
                if not len(duplicated) == 0:
                    LOGGER.error(f"Sort keys for table {filename} are duplicatd for:\n{duplicated}")
                    no_duplicates += 1
                else:
                    df = df.with_row_index()
                    df_clone = df.clone()

                    df = df.sort(sort_keys, descending = descending)

                    index_matching = df.get_column("index") == df_clone.get_column("index")
                    rank1 = np.array(df.get_column("index"))
                    rank2 = np.array(df_clone.get_column("index"))

                    corr = np.corrcoef(rank1, rank2)[0,1]
                    if not index_matching.all():
                        LOGGER.error(f"The table {filename} is not sorted by {sort_keys} (rank correlation {corr} < 1.0)")
                        errors += 1
            else:
                LOGGER.error(f"No sort keys provided for {filename}")
                missing += 1
        
        self.assertEqual(missing, 0, f"A sort key was not provided for {missing} file(s)")
        self.assertEqual(0, errors, f"{errors} table(s) not properly sorted")
        self.assertEqual(0, no_duplicates, f"Sort keys are duplicatd in {no_duplicates} files")

if __name__ == '__main__':
    unittest.test()
