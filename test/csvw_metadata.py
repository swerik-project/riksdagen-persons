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
                erroneous_tables.append(str(table_name))

        no_errors = len(erroneous_tables)
        erroneous_tables = ", ".join(erroneous_tables)
        self.assertEqual(0, no_errors, f"Non-unique primary keys found in {no_errors} table(s): {erroneous_tables}.")


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



if __name__ == '__main__':
    unittest.main()
