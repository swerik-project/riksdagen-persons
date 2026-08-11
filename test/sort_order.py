"""
Test that metadata tables are sorted correctly
"""
import json
import polars as pl
from pytest_cfg_fetcher.fetch import fetch_config
import json
import unittest
from trainerlog import get_logger
LOGGER = get_logger("test-sort-order")

class Test(unittest.TestCase):

    def fetch_sort_order(self):
        with open("test/data/sort-order.json") as f: 
            sort_order =  json.load(f)
        return sort_order

    def test_manually_checked_mandates(self):
        """
        Find each manual mandate in the data... make sure dates are same.
        """
        sort_order = self.fetch_sort_order()

        for filename, sort_keys in sort_order.items():
            if len(sort_keys) >= 1:
                df = pl.read_csv(f"data/{filename}", infer_schema_length=10000)
                duplicated = df.filter(df.select(sort_keys).is_duplicated())
                self.assertEqual(0, len(duplicated), f"Sort keys for table {filename} are duplicatd for:\n{duplicated}")

                df = df.with_row_index()
                df_clone = df.clone()

                df = df.sort(sort_keys)

                index_matching = df.get_column("index") == df_clone.get_column("index")
                self.assertTrue(index_matching.all(), f"The table {filename} is not sorted by {sort_keys}")

            else:
                LOGGER.error(f"No sort keys provided for {filename}")


if __name__ == '__main__':
    unittest.test()
