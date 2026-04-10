"""
Tests related to constituency.
"""
from datetime import datetime
from pytest_cfg_fetcher.fetch import fetch_config
import pandas as pd
import unittest
import warnings
import json
from trainerlog import get_logger
logger = get_logger(name="ebun", level="DEBUG")

file_path = "test/data/reference-coverage.json"
with open(file_path, "r", encoding="utf-8") as f:
    reference_data = json.load(f)

#For dynamic non decreasing reference
REFERENCE_COVERAGE = reference_data

#Variance threshold for the number of MPs per district per year, to detect potential outliers in the data. This is a heuristic value and may need adjustment based on the specific dataset and context.
VARIANCE_THRESHOLD = 5 #this number is almost arbitrary and needs fine tuning   


class Unlisted(Warning):

    def __init__(self, m):
        self.message = m

    def __str__(self):
        return self.message


class Info(Warning):

    def __init__(self, m):
        self.message = m

    def __str__(self):
        return self.message




class Test(unittest.TestCase):
    def get_constituency_completion_by_start_year(self, members):

        members['start'] = members['start'].astype(str).str[:4]
        members['district'] = members['district'].fillna('').astype(str).str.strip()

        incomplete_years = []
        all_years = []

        for year, group in members.groupby('start'):
            total = len(group)
            filled = (group['district'] != '').sum()
            completion_rate = filled / total if total > 0 else 1.0
            completion_rate = round(completion_rate, 4)
            missing = total - filled

            all_years.append({
                "year": str(year),
                "total": int(total),
                "filled": int(filled),
                "missing": int(missing),
                "completion_rate": f"{completion_rate:.2%}"
            })

            if completion_rate < 1.0:
                incomplete_years.append({
                        "year": str(year),
                        "total": int(total),
                        "filled": int(filled),
                        "missing": int(missing),
                        "completion_rate": f"{completion_rate:.2%}"
                    })
        return all_years, incomplete_years
    
    def get_MP_per_district_per_year(self, members):

        members['year'] = members['start'].astype(str).str[:4]
        members['district'] = members['district'].fillna('').astype(str).str.strip()

        df_counts = (
            members[members['district'] != '']
            .groupby(['year', 'district'])
            .size() 
            .reset_index(name='mp_count') 
        )

        return df_counts
    

    """ Test if MP do have a constituency, and if the constituency is listed in the data. """
    def test_constituency_completion_by_start_year(self):
        
        members = pd.read_csv("data/member_of_parliament.csv")
        all_years, incomplete_years = self.get_constituency_completion_by_start_year(members)
   
        REFERENCE = {d['year']: d for d in REFERENCE_COVERAGE}

        failures = 0

        for entry in all_years:
            current_rate = float(entry['completion_rate'].strip('%')) / 100
            ref_rate = float(REFERENCE[entry['year']]['completion_rate'].strip('%')) / 100
            if current_rate < (ref_rate - 0.0001):
                msg = f"Year {entry['year']}: {entry['completion_rate']} (ref: {REFERENCE[entry['year']]['completion_rate']})"
                failures += 1
                logger.error(msg)
        
        self.assertEqual(failures, 0, f"All years should have a completion rate at least as good as the reference. Failures: {failures}")
        #REFERENCE_COVERAGE = all_years #for dynamic non decreasing reference
    
    """ Tests the coherence of the data based on the computation of empirical variance"""
    def test_MP_per_district_per_year(self):

        members = pd.read_csv("data/member_of_parliament.csv")
        df_counts = self.get_MP_per_district_per_year(members)
        pivot_counts = df_counts.pivot(index='year', columns='district', values='mp_count').fillna(0)
        districts_variance = pivot_counts.var(axis=0, ddof=0)
        failures = 0

        for district, var in districts_variance.items():
            if var > VARIANCE_THRESHOLD: #this number is almost arbitrary and needs fine tuning
                failures += 1
                logger.error(f"District {district} has a suspicious variance of {var}.")   
        self.assertEqual(failures, 0, f"All districts should have a variance of MP count per year below {VARIANCE_THRESHOLD}. Failures: {failures}")             


if __name__ == '__main__':
    unittest.main()
