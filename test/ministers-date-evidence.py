"""
Test that manually reviewed minister date evidence remains present in metadata.
"""
import pandas as pd
import unittest


class Test(unittest.TestCase):

    def fetch_known_minister_date_evidence(self):
        return pd.read_csv("test/data/ministers-date-evidence.csv", sep=";")

    def fetch_minister_meta(self):
        return pd.read_csv("data/minister.csv").fillna("")

    def date_matches_observation(self, actual, expected):
        actual = str(actual).strip()
        expected = str(expected).strip()
        if not actual or not expected:
            return False
        if len(expected) == 4:
            return actual == expected or actual.startswith(f"{expected}-")
        if len(expected) == 7:
            return actual == expected or actual.startswith(f"{expected}-")
        return actual == expected

    def test_manually_checked_minister_date_evidence(self):
        """
        Find each manual minister date observation in minister.csv.
        """
        ministers = self.fetch_minister_meta()
        evidence = self.fetch_known_minister_date_evidence()
        missing = []

        for _, row in evidence.iterrows():
            date_column = row["type"].lower()
            matching_rows = ministers.loc[
                (ministers["person_id"] == row["person_id"])
                & (ministers["role"] == row["role"])
            ]
            date_match = matching_rows[date_column].apply(
                lambda value: self.date_matches_observation(value, row["date"])
            )

            if matching_rows.empty or not date_match.any():
                missing.append(row.to_dict())

        self.assertEqual(
            len(missing),
            0,
            pd.DataFrame(missing).to_string(index=False),
        )


if __name__ == "__main__":
    unittest.main()
