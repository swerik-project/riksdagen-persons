"""
Test that the CSVW metadata describes the released CSV files.
"""
import csv
import json
from pathlib import Path
import unittest
from csvw import TableGroup
from trainerlog import get_logger
LOGGER = get_logger("csvw-test")
import polars as pl


class Test(unittest.TestCase):

    def get_data_dir(self):
        return Path(".") / "data"


    def get_metadata_path(self):
        return self.get_data_dir() / "csvw-metadata.json"


    def get_metadata(self):
        with open(self.get_metadata_path(), encoding="utf-8") as f:
            return json.load(f)


    def get_csv_files(self):
        return sorted(p.name for p in self.get_data_dir().glob("*.csv"))


    def get_metadata_tables(self):
        metadata = self.get_metadata()
        return metadata["tables"]


    def get_metadata_files(self):
        return sorted(table["url"] for table in self.get_metadata_tables())


    def get_csv_header(self, csv_file):
        with open(self.get_data_dir() / csv_file, encoding="utf-8", newline="") as f:
            return next(csv.reader(f))


    def get_metadata_header(self, table):
        return [column["name"] for column in table["tableSchema"]["columns"]]


    def test_csvw_metadata_is_valid_json(self):
        """
        test CSVW metadata can be parsed as JSON
        """
        metadata = self.get_metadata()
        self.assertIn("tables", metadata)


    def test_all_csv_files_are_listed_in_metadata(self):
        """
        test all released CSV files are listed in the CSVW metadata
        """
        csv_files = self.get_csv_files()
        metadata_files = self.get_metadata_files()
        missing_files = sorted(set(csv_files) - set(metadata_files))
        self.assertEqual(missing_files, [])


    def test_metadata_has_no_extra_csv_files(self):
        """
        test CSVW metadata does not list files that are not released CSV files
        """
        csv_files = self.get_csv_files()
        metadata_files = self.get_metadata_files()
        extra_files = sorted(set(metadata_files) - set(csv_files))
        self.assertEqual(extra_files, [])


    def test_csv_headers_match_metadata_column_order(self):
        """
        test CSVW column declarations match the actual CSV header order
        """
        mismatches = []
        for table in self.get_metadata_tables():
            table_name = table["url"]
            csv_header = self.get_csv_header(table["url"])
            metadata_header = self.get_metadata_header(table)
            if csv_header != metadata_header:
                LOGGER.error(f"In {table_name}, CSV headers do not match:\nfound {csv_header}, should be {metadata_header}")
                mismatches.append(table_name)

        self.assertEqual(len(mismatches), 0, f"Erroneous columns found in {len(mismatches)} file(s)")

    def test_primary_keys(self):
        """
        test that all primary keys are unique
        """
        tg = TableGroup.from_url(str(self.get_metadata_path()))
        erroneous_tables = []
        for table in tg.tables:
            table_name = table.url
            try:
                table.check_primary_key()
            except Exception as e:
                LOGGER.error(f"ERROR in {table_name}:\n{e}")
                if "external" in str(table.url):
                    LOGGER.warning(f"Do not crash on external links being non-unique: {table.url}")
                else:
                    erroneous_tables.append(str(table_name))

        no_errors = len(erroneous_tables)
        erroneous_tables = ", ".join(erroneous_tables)
        self.assertEqual(0, no_errors, f"Non-unique primary keys found in {no_errors} table(s): {erroneous_tables}.")

    def test_foreign_keys(self):
        """
        test that all primary keys are unique
        """
        tg = TableGroup.from_url(str(self.get_metadata_path()))

        tg.check_referential_integrity()

    def test_validate_schema(self):
        """
        validate CSVW schema
        """
        tg = TableGroup.from_url(str(self.get_metadata_path()))
        tg.validate_schema()



    def test_column_formats(self):
        """
        validate CSVW schema
        """
        tg = TableGroup.from_url(str(self.get_metadata_path()))
        erroneous_tables = []
        no_errors = 0
        for table in tg.tables:
            table_name = table.url
            df = pl.read_csv(self.get_data_dir() / str(table_name), infer_schema_length=10000)
            for col in table.tableSchema.columns:
                pl_col = df.get_column(col.name)
                datatype = col.datatype

                # BOOLEAN
                if datatype.format == "^(True|False)$":
                    if pl_col.dtype != pl.Boolean:
                        LOGGER.error(f"Expected boolean data type for {col.name}, got {pl_col.dtype}")
                        no_errors += 1

                # Integer
                elif datatype.base == "integer":
                    if pl_col.dtype != pl.Int64:
                        LOGGER.error(f"Expected integer data type for {col.name}, got {pl_col.dtype}")
                        no_errors += 1

                # String with regular expression
                elif datatype.base == "string" and datatype.format is not None:
                    matched = df.filter(pl.col(col.name).is_not_null())
                    matched = matched.with_columns(pl.col(col.name).str.extract(datatype.format, group_index=0).alias(f"matches"))
                    matched = matched.filter(pl.col("matches").is_null())
                    if len(matched) >= 1:
                        LOGGER.error(f"Non format-matching ({datatype.base}, {datatype.format}) values found for column {col.name}:\n{matched}")
                        no_errors += len(matched)

                # ISO date yyyy-MM-dd
                elif datatype.base == "date":
                    expression = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"

                    matched = df.filter(pl.col(col.name).is_not_null())
                    matched = matched.with_columns(pl.col(col.name).str.extract(expression, group_index=0).alias(f"matches"))
                    matched = matched.filter(pl.col("matches").is_null())

                    if len(matched) >= 1:
                        LOGGER.error(f"Expected ISO date data type for '{col.name}', non-matching values found\n{matched}")
                        no_errors += len(matched)

        self.assertEqual(0, no_errors, f"{no_errors} format error(s) found")

    def test_primary_key_exists(self):
        """
        Test that each table has a primary key
        """
        tg = TableGroup.from_url(str(self.get_metadata_path()))
        for table in tg.tables:
            pk = table.tableSchema.primaryKey
            self.assertTrue(pk is not None, f"Table {table.url} does not have a CSVW primary key")

    def test_start_end(self):
        """
        Test that each date range column pair is coherent

        1. For each row, 'start' is earlier or same as 'end'
        2. For each unique (composite) primary key, the time ranges do not overlap

        These are tested for all tables with dates; for start/end, born/dead and inception/dissolution.
        """
        tg = TableGroup.from_url(str(self.get_metadata_path()))
        no_errors = 0
        no_overlaps = 0

        for table in tg.tables:
            df = pl.read_csv(self.get_data_dir() / str(table.url), infer_schema_length=10000)
            pk = table.tableSchema.primaryKey

            for start, end in [("start", "end"), ("born", "dead"), ("inception", "dissolution")]:
                if start in df.columns:
                    # Per row: start <= end
                    LOGGER.info(f"Check {start}/{end} for table {table.url}")
                    df = df.filter(pl.col(start).is_not_null())
                    df = df.filter(pl.col(end).is_not_null())

                    # For mixed precision, truncate longer value of start/end
                    charlen = pl.min_horizontal(
                        pl.col(start).str.len_chars(),
                        pl.col(end).str.len_chars(),
                    )
                    df_errors = df.filter(pl.col(start).str.head(charlen) > pl.col(end).str.head(charlen))

                    if len(df_errors) >= 1:
                        no_errors += len(df_errors)
                        LOGGER.error(f"Inconsistent start dates in {table.url}:\n{df_errors}")

                    # Per primary key:
                    # Date ranges should not overlap with more than one day (or year/month if that's the precision).
                    # This is checked via: sorted values should have end_prev <= start. Equivalent in terms of
                    # error-free, but might undercount errors
                    pk_wo_start = [key for key in pk if key != "start"]
                    df = df.with_columns(pl.concat_str(pk_wo_start, ignore_nulls=True).alias("pk"))
                    df = df.sort("pk", start, end)
                    df = df.with_columns(pl.col(end).shift(1).alias("prev_end"))

                    df_small = df.select("pk", start, end, "prev_end")
                    df_small = df_small.sort("pk", start, end)
                    df_small = df_small.filter(pl.col("pk").shift(1) == pl.col("pk"))
                    df_small = df_small.sort("pk", start)
                    errors = df_small.filter(pl.col(start) < pl.col("prev_end"))

                    no_overlaps += len(errors)
                    if len(errors) >= 1:
                        for primary_key in set(errors["pk"]):
                            df_pk = df.filter(pl.col("pk") == primary_key)
                            df_pk[0, "prev_end"] = None
                            df_pk = df_pk.with_columns((pl.col(start) < pl.col("prev_end")).alias("overlaps_w_previous").fill_null(False))
                            df_pk = df_pk.drop("pk")
                            LOGGER.error(f"Overlapping values with the same primary key in {table.url}:\n{df_pk}")

        self.assertEqual(no_errors, 0, f"{no_errors} inconsistent start and end dates found")
        self.assertEqual(no_overlaps, 0, f"{no_overlaps} overlapping primary keys found")

if __name__ == '__main__':
    unittest.main()
