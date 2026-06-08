"""
Tests related to constituency.
"""
from datetime import datetime
from pytest_cfg_fetcher.fetch import fetch_config
import pandas as pd
import unittest
import warnings
import json
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from trainerlog import get_logger
import re
logger = get_logger(name="constituency_test")



#Variance threshold for the number of MPs per district per year, to detect potential outliers in the data. This is a heuristic value and may need adjustment based on the specific dataset and context.
VARIANCE_THRESHOLD = 5 #this number is almost arbitrary and needs fine tuning   

#Number of constituencies threshold
CONSTITUENCY_COUNT_THRESHOLD = 437 



class Test(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.members = pd.read_csv("data/member_of_parliament.csv")
        cls.REFERENCE_COVERAGE = [{"year": "1867", "total": 318, "filled": 273, "missing": 45, "completion_rate": "85.85%"},
  {"year": "1868", "total": 17, "filled": 15, "missing": 2, "completion_rate": "88.24%"},
  {"year": "1869", "total": 23, "filled": 20, "missing": 3, "completion_rate": "86.96%"},
  {"year": "1870", "total": 121, "filled": 95, "missing": 26, "completion_rate": "78.51%"},
  {"year": "1871", "total": 33, "filled": 28, "missing": 5, "completion_rate": "84.85%"},
  {"year": "1872", "total": 8, "filled": 7, "missing": 1, "completion_rate": "87.50%"},
  {"year": "1873", "total": 106, "filled": 95, "missing": 11, "completion_rate": "89.62%"},
  {"year": "1874", "total": 22, "filled": 21, "missing": 1, "completion_rate": "95.45%"},
  {"year": "1875", "total": 29, "filled": 28, "missing": 1, "completion_rate": "96.55%"},
  {"year": "1876", "total": 111, "filled": 97, "missing": 14, "completion_rate": "87.39%"},
  {"year": "1877", "total": 19, "filled": 16, "missing": 3, "completion_rate": "84.21%"},
  {"year": "1878", "total": 39, "filled": 34, "missing": 5, "completion_rate": "87.18%"},
  {"year": "1879", "total": 93, "filled": 89, "missing": 4, "completion_rate": "95.70%"},
  {"year": "1880", "total": 35, "filled": 34, "missing": 1, "completion_rate": "97.14%"},
  {"year": "1881", "total": 18, "filled": 18, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1882", "total": 88, "filled": 78, "missing": 10, "completion_rate": "88.64%"},
  {"year": "1883", "total": 25, "filled": 25, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1884", "total": 30, "filled": 28, "missing": 2, "completion_rate": "93.33%"},
  {"year": "1885", "total": 108, "filled": 103, "missing": 5, "completion_rate": "95.37%"},
  {"year": "1886", "total": 31, "filled": 31, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1887", "total": 103, "filled": 86, "missing": 17, "completion_rate": "83.50%"},
  {"year": "1888", "total": 99, "filled": 85, "missing": 14, "completion_rate": "85.86%"},
  {"year": "1889", "total": 33, "filled": 33, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1890", "total": 25, "filled": 23, "missing": 2, "completion_rate": "92.00%"},
  {"year": "1891", "total": 101, "filled": 95, "missing": 6, "completion_rate": "94.06%"},
  {"year": "1892", "total": 53, "filled": 49, "missing": 4, "completion_rate": "92.45%"},
  {"year": "1893", "total": 2, "filled": 2, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1894", "total": 102, "filled": 97, "missing": 5, "completion_rate": "95.10%"},
  {"year": "1895", "total": 27, "filled": 26, "missing": 1, "completion_rate": "96.30%"},
  {"year": "1896", "total": 19, "filled": 17, "missing": 2, "completion_rate": "89.47%"},
  {"year": "1897", "total": 98, "filled": 92, "missing": 6, "completion_rate": "93.88%"},
  {"year": "1898", "total": 16, "filled": 16, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1899", "total": 16, "filled": 15, "missing": 1, "completion_rate": "93.75%"},
  {"year": "1900", "total": 83, "filled": 80, "missing": 3, "completion_rate": "96.39%"},
  {"year": "1901", "total": 14, "filled": 14, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1902", "total": 22, "filled": 21, "missing": 1, "completion_rate": "95.45%"},
  {"year": "1903", "total": 90, "filled": 86, "missing": 4, "completion_rate": "95.56%"},
  {"year": "1904", "total": 13, "filled": 13, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1905", "total": 27, "filled": 27, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1906", "total": 61, "filled": 55, "missing": 6, "completion_rate": "90.16%"},
  {"year": "1907", "total": 25, "filled": 24, "missing": 1, "completion_rate": "96.00%"},
  {"year": "1908", "total": 27, "filled": 27, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1909", "total": 117, "filled": 112, "missing": 5, "completion_rate": "95.73%"},
  {"year": "1910", "total": 25, "filled": 24, "missing": 1, "completion_rate": "96.00%"},
  {"year": "1911", "total": 31, "filled": 30, "missing": 1, "completion_rate": "96.77%"},
  {"year": "1912", "total": 283, "filled": 268, "missing": 15, "completion_rate": "94.70%"},
  {"year": "1913", "total": 25, "filled": 19, "missing": 6, "completion_rate": "76.00%"},
  {"year": "1914", "total": 65, "filled": 56, "missing": 9, "completion_rate": "86.15%"},
  {"year": "1915", "total": 54, "filled": 48, "missing": 6, "completion_rate": "88.89%"},
  {"year": "1916", "total": 21, "filled": 20, "missing": 1, "completion_rate": "95.24%"},
  {"year": "1917", "total": 17, "filled": 14, "missing": 3, "completion_rate": "82.35%"},
  {"year": "1918", "total": 114, "filled": 100, "missing": 14, "completion_rate": "87.72%"},
  {"year": "1919", "total": 125, "filled": 113, "missing": 12, "completion_rate": "90.40%"},
  {"year": "1920", "total": 27, "filled": 25, "missing": 2, "completion_rate": "92.59%"},
  {"year": "1921", "total": 91, "filled": 81, "missing": 10, "completion_rate": "89.01%"},
  {"year": "1922", "total": 262, "filled": 240, "missing": 22, "completion_rate": "91.60%"},
  {"year": "1923", "total": 8, "filled": 7, "missing": 1, "completion_rate": "87.50%"},
  {"year": "1924", "total": 11, "filled": 10, "missing": 1, "completion_rate": "90.91%"},
  {"year": "1925", "total": 68, "filled": 66, "missing": 2, "completion_rate": "97.06%"},
  {"year": "1926", "total": 15, "filled": 13, "missing": 2, "completion_rate": "86.67%"},
  {"year": "1927", "total": 14, "filled": 14, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1928", "total": 21, "filled": 19, "missing": 2, "completion_rate": "90.48%"},
  {"year": "1929", "total": 78, "filled": 75, "missing": 3, "completion_rate": "96.15%"},
  {"year": "1930", "total": 12, "filled": 12, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1931", "total": 28, "filled": 26, "missing": 2, "completion_rate": "92.86%"},
  {"year": "1932", "total": 11, "filled": 9, "missing": 2, "completion_rate": "81.82%"},
  {"year": "1933", "total": 83, "filled": 80, "missing": 3, "completion_rate": "96.39%"},
  {"year": "1934", "total": 22, "filled": 22, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1935", "total": 20, "filled": 20, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1936", "total": 25, "filled": 22, "missing": 3, "completion_rate": "88.00%"},
  {"year": "1937", "total": 83, "filled": 82, "missing": 1, "completion_rate": "98.80%"},
  {"year": "1938", "total": 29, "filled": 29, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1939", "total": 25, "filled": 24, "missing": 1, "completion_rate": "96.00%"},
  {"year": "1940", "total": 22, "filled": 21, "missing": 1, "completion_rate": "95.45%"},
  {"year": "1941", "total": 76, "filled": 73, "missing": 3, "completion_rate": "96.05%"},
  {"year": "1942", "total": 23, "filled": 20, "missing": 3, "completion_rate": "86.96%"},
  {"year": "1943", "total": 27, "filled": 24, "missing": 3, "completion_rate": "88.89%"},
  {"year": "1944", "total": 23, "filled": 20, "missing": 3, "completion_rate": "86.96%"},
  {"year": "1945", "total": 60, "filled": 53, "missing": 7, "completion_rate": "88.33%"},
  {"year": "1946", "total": 22, "filled": 22, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1947", "total": 17, "filled": 17, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1948", "total": 25, "filled": 25, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1949", "total": 84, "filled": 81, "missing": 3, "completion_rate": "96.43%"},
  {"year": "1950", "total": 21, "filled": 20, "missing": 1, "completion_rate": "95.24%"},
  {"year": "1951", "total": 22, "filled": 21, "missing": 1, "completion_rate": "95.45%"},
  {"year": "1952", "total": 15, "filled": 14, "missing": 1, "completion_rate": "93.33%"},
  {"year": "1953", "total": 64, "filled": 63, "missing": 1, "completion_rate": "98.44%"},
  {"year": "1954", "total": 24, "filled": 23, "missing": 1, "completion_rate": "95.83%"},
  {"year": "1955", "total": 14, "filled": 13, "missing": 1, "completion_rate": "92.86%"},
  {"year": "1956", "total": 19, "filled": 18, "missing": 1, "completion_rate": "94.74%"},
  {"year": "1957", "total": 68, "filled": 66, "missing": 2, "completion_rate": "97.06%"},
  {"year": "1958", "total": 51, "filled": 48, "missing": 3, "completion_rate": "94.12%"},
  {"year": "1959", "total": 20, "filled": 19, "missing": 1, "completion_rate": "95.00%"},
  {"year": "1960", "total": 18, "filled": 18, "missing": 0, "completion_rate": "100.00%"},
  {"year": "1961", "total": 52, "filled": 51, "missing": 1, "completion_rate": "98.08%"},
  {"year": "1962", "total": 24, "filled": 21, "missing": 3, "completion_rate": "87.50%"},
  {"year": "1963", "total": 17, "filled": 16, "missing": 1, "completion_rate": "94.12%"},
  {"year": "1964", "total": 26, "filled": 23, "missing": 3, "completion_rate": "88.46%"},
  {"year": "1965", "total": 68, "filled": 62, "missing": 6, "completion_rate": "91.18%"},
  {"year": "1966", "total": 16, "filled": 15, "missing": 1, "completion_rate": "93.75%"},
  {"year": "1967", "total": 13, "filled": 12, "missing": 1, "completion_rate": "92.31%"},
  {"year": "1968", "total": 19, "filled": 14, "missing": 5, "completion_rate": "73.68%"},
  {"year": "1969", "total": 83, "filled": 79, "missing": 4, "completion_rate": "95.18%"},
  {"year": "1970", "total": 11, "filled": 9, "missing": 2, "completion_rate": "81.82%"},
  {"year": "1971", "total": 360, "filled": 357, "missing": 3, "completion_rate": "99.17%"},
  {"year": "1972", "total": 8, "filled": 1, "missing": 7, "completion_rate": "12.50%"},
  {"year": "1973", "total": 5, "filled": 1, "missing": 4, "completion_rate": "20.00%"},
  {"year": "1974", "total": 385, "filled": 358, "missing": 27, "completion_rate": "92.99%"},
  {"year": "1975", "total": 12, "filled": 8, "missing": 4, "completion_rate": "66.67%"},
  {"year": "1976", "total": 385, "filled": 362, "missing": 23, "completion_rate": "94.03%"},
  {"year": "1977", "total": 32, "filled": 23, "missing": 9, "completion_rate": "71.88%"},
  {"year": "1978", "total": 44, "filled": 20, "missing": 24, "completion_rate": "45.45%"},
  {"year": "1979", "total": 407, "filled": 387, "missing": 20, "completion_rate": "95.09%"},
  {"year": "1980", "total": 26, "filled": 20, "missing": 6, "completion_rate": "76.92%"},
  {"year": "1981", "total": 52, "filled": 37, "missing": 15, "completion_rate": "71.15%"},
  {"year": "1982", "total": 411, "filled": 390, "missing": 21, "completion_rate": "94.89%"},
  {"year": "1983", "total": 60, "filled": 32, "missing": 28, "completion_rate": "53.33%"},
  {"year": "1984", "total": 37, "filled": 23, "missing": 14, "completion_rate": "62.16%"},
  {"year": "1985", "total": 412, "filled": 385, "missing": 27, "completion_rate": "93.45%"},
  {"year": "1986", "total": 41, "filled": 21, "missing": 20, "completion_rate": "51.22%"},
  {"year": "1987", "total": 40, "filled": 25, "missing": 15, "completion_rate": "62.50%"},
  {"year": "1988", "total": 418, "filled": 393, "missing": 25, "completion_rate": "94.02%"},
  {"year": "1989", "total": 43, "filled": 26, "missing": 17, "completion_rate": "60.47%"},
  {"year": "1990", "total": 43, "filled": 30, "missing": 13, "completion_rate": "69.77%"},
  {"year": "1991", "total": 412, "filled": 385, "missing": 27, "completion_rate": "93.45%"},
  {"year": "1992", "total": 49, "filled": 35, "missing": 14, "completion_rate": "71.43%"},
  {"year": "1993", "total": 40, "filled": 30, "missing": 10, "completion_rate": "75.00%"},
  {"year": "1994", "total": 394, "filled": 373, "missing": 21, "completion_rate": "94.67%"},
  {"year": "1995", "total": 72, "filled": 42, "missing": 30, "completion_rate": "58.33%"},
  {"year": "1996", "total": 45, "filled": 18, "missing": 27, "completion_rate": "40.00%"},
  {"year": "1997", "total": 17, "filled": 9, "missing": 8, "completion_rate": "52.94%"},
  {"year": "1998", "total": 382, "filled": 370, "missing": 12, "completion_rate": "96.86%"},
  {"year": "1999", "total": 26, "filled": 14, "missing": 12, "completion_rate": "53.85%"},
  {"year": "2000", "total": 27, "filled": 19, "missing": 8, "completion_rate": "70.37%"},
  {"year": "2001", "total": 26, "filled": 18, "missing": 8, "completion_rate": "69.23%"},
  {"year": "2002", "total": 405, "filled": 380, "missing": 25, "completion_rate": "93.83%"},
  {"year": "2003", "total": 48, "filled": 36, "missing": 12, "completion_rate": "75.00%"},
  {"year": "2004", "total": 60, "filled": 43, "missing": 17, "completion_rate": "71.67%"},
  {"year": "2005", "total": 50, "filled": 39, "missing": 11, "completion_rate": "78.00%"},
  {"year": "2006", "total": 419, "filled": 390, "missing": 29, "completion_rate": "93.08%"},
  {"year": "2007", "total": 44, "filled": 33, "missing": 11, "completion_rate": "75.00%"},
  {"year": "2008", "total": 35, "filled": 26, "missing": 9, "completion_rate": "74.29%"},
  {"year": "2009", "total": 40, "filled": 29, "missing": 11, "completion_rate": "72.50%"},
  {"year": "2010", "total": 407, "filled": 396, "missing": 11, "completion_rate": "97.30%"},
  {"year": "2011", "total": 47, "filled": 38, "missing": 9, "completion_rate": "80.85%"},
  {"year": "2012", "total": 54, "filled": 45, "missing": 9, "completion_rate": "83.33%"},
  {"year": "2013", "total": 53, "filled": 45, "missing": 8, "completion_rate": "84.91%"},
  {"year": "2014", "total": 417, "filled": 401, "missing": 16, "completion_rate": "96.16%"},
  {"year": "2015", "total": 41, "filled": 35, "missing": 6, "completion_rate": "85.37%"},
  {"year": "2016", "total": 46, "filled": 42, "missing": 4, "completion_rate": "91.30%"},
  {"year": "2017", "total": 77, "filled": 69, "missing": 8, "completion_rate": "89.61%"},
  {"year": "2018", "total": 406, "filled": 405, "missing": 1, "completion_rate": "99.75%"},
  {"year": "2019", "total": 67, "filled": 65, "missing": 2, "completion_rate": "97.01%"},
  {"year": "2020", "total": 42, "filled": 41, "missing": 1, "completion_rate": "97.62%"},
  {"year": "2021", "total": 56, "filled": 56, "missing": 0, "completion_rate": "100.00%"},
  {"year": "2022", "total": 446, "filled": 445, "missing": 1, "completion_rate": "99.78%"},
  {"year": "2023", "total": 44, "filled": 44, "missing": 0, "completion_rate": "100.00%"},
  {"year": "2024", "total": 18, "filled": 17, "missing": 1, "completion_rate": "94.44%"}
]
        cls.REFERENCE_VARIANCES = [{"district": "Arboga och Sala valkrets", "variance": 0.02467553276718474},
{"district": "Aska, Dals och Bobergs domsagas valkrets", "variance": 0.03653260695401379},
{"district": "Askers och Sköllersta häraders valkrets", "variance": 0.012497997115846822},
{"district": "Askims och Sävedals häraders valkrets", "variance": 0.03064412754366287},
{"district": "Askims samt Västra och Östra Hisings häraders valkrets", "variance": 0.012497997115846822},
{"district": "Aspelands och Handbörds domsagas valkrets", "variance": 0.04806921967633393},
{"district": "Bara härads valkrets", "variance": 0.02467553276718474},
{"district": "Bara och Torna häraders valkrets", "variance": 0.00628905624098702},
{"district": "Bergsjö och Delsbo tingslags valkrets", "variance": 0.006289056240987021},
{"district": "Björkekinds, Östkinds, Lösings, Bråbo och Memmings domsagas valkrets", "variance": 0.04234097099823746},
{"district": "Blekinge läns och Kristianstads läns valkrets", "variance": 0.8392885755487904},
{"district": "Blekinge läns valkrets", "variance": 4.116327511616728},
{"district": "Bollnäs domsagas valkrets", "variance": 0.024675532767184743},
{"district": "Borås valkrets", "variance": 0.018626822624579396},
{"district": "Borås, Alingsås och Ulricehamns valkrets", "variance": 0.03653260695401379},
{"district": "Boteå, Säbrå, Nora och Gudmundrå tingslags valkrets", "variance": 0.018626822624579396},
{"district": "Bräkne domsagas valkrets", "variance": 0.02467553276718475},
{"district": "Dalarnas läns valkrets", "variance": 16.872616567857715},
{"district": "Danderyds, Åkers och Värmdö skeppslags valkrets", "variance": 0.012497997115846822},
{"district": "Degerfors, Lycksele och Åsele tingslags valkrets", "variance": 0.00628905624098702},
{"district": "Edsbergs, Grimstens och Hardemo häraders valkrets", "variance": 0.04234097099823746},
{"district": "Edsbergs, Lekebergs, Grimstens och Hardemo häraders valkrets", "variance": 0.012497997115846822},
{"district": "Eksjö, Vimmerby och Västerviks valkrets", "variance": 0.024675532767184736},
{"district": "Enköpings, Södertälje, Norrtälje, Vaxholms, Öregrunds, Östhammars och Sigtuna valkrets", "variance": 0.012497997115846822},
{"district": "Enångers och Forsa tingslags valkrets", "variance": 0.018626822624579396},
{"district": "Eskilstuna och Strängnäs valkrets", "variance": 0.03064412754366287},
{"district": "Eskilstuna och Torshälla valkrets", "variance": 0.012497997115846822},
{"district": "Eskilstuna valkrets", "variance": 0.012497997115846822},
{"district": "Falu domsagas norra tingslags valkrets", "variance": 0.006289056240987021},
{"district": "Falu domsagas södra tingslags valkrets", "variance": 0.006289056240987021},
{"district": "Falu domsagas valkrets", "variance": 0.018626822624579396},
{"district": "Falu, Hedemora och Säters valkrets", "variance": 0.04234097099823746},
{"district": "Finspånga läns domsagas valkrets", "variance": 0.04234097099823745},
{"district": "Fjäre och Viske domsagas valkrets", "variance": 0.012497997115846819},
{"district": "Fjäre och Viske häraders valkrets", "variance": 0.05371735298830316},
{"district": "Flundre, Väne och Bjärke domsagas valkrets", "variance": 0.05928537093414517},
{"district": "Frosta domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Fryksdals domsagas nedre tingslags valkrets", "variance": 0.024675532767184736},
{"district": "Fryksdals domsagas valkrets", "variance": 0.024675532767184736},
{"district": "Fryksdals domsagas övre tingslags valkrets", "variance": 0.018626822624579396},
{"district": "Fyrstadskretsen", "variance": 23.27131068738983},
{"district": "Färentuna och Sollentuna häraders valkrets", "variance": 0.006289056240987021},
{"district": "Färnebo härads valkrets", "variance": 0.03653260695401379},
{"district": "Färs domsagas valkrets", "variance": 0.024675532767184736},
{"district": "Gagnefs och Rättviks tingslags valkrets", "variance": 0.00628905624098702},
{"district": "Gamla Norberg, Norrbo, Vagnsbro och Skinnskattebergs domsaga", "variance": 0.00628905624098702},
{"district": "Gillbergs och Näs häraders valkrets", "variance": 0.00628905624098702},
{"district": "Gotlands läns norra domsagas valkrets", "variance": 0.018626822624579396},
{"district": "Gotlands läns södra domsagas valkrets", "variance": 0.03653260695401379},
{"district": "Gotlands läns valkrets", "variance": 0.6404422368210223},
{"district": "Grangärde, Norrbärke och Söderbärke tingslags valkrets", "variance": 0.012497997115846822},
{"district": "Gudhems och Kåkinds domsagas valkrets", "variance": 0.018626822624579393},
{"district": "Gällivare domsagas valkrets", "variance": 0.006289056240987021},
{"district": "Gärds och Albo domsagas valkrets", "variance": 0.024675532767184736},
{"district": "Gästriklands valkrets", "variance": 0.12401858676494153},
{"district": "Gästriklands västra tingslags valkrets", "variance": 0.02467553276718474},
{"district": "Gästriklands östra tingslags valkrets", "variance": 0.03653260695401379},
{"district": "Gävle valkrets", "variance": 0.09549751642365008},
{"district": "Gävleborgs läns med Gävle valkrets", "variance": 0.006289056240987018},
{"district": "Gävleborgs läns valkrets", "variance": 14.834161192116648},
{"district": "Göteborgs kommun", "variance": 0.012497997115846822},
{"district": "Göteborgs kommuns valkrets", "variance": 32.25977407466753},
{"district": "Göteborgs och Bohus län", "variance": 0.0062890562409870215},
{"district": "Göteborgs och Bohus läns landstingsområdes valkrets", "variance": 0.07194359878224642},
{"district": "Göteborgs och Bohus läns norra valkrets", "variance": 0.10435026438070821},
{"district": "Göteborgs och Bohus läns södra valkrets", "variance": 0.12401858676494153},
{"district": "Göteborgs och Bohus läns valkrets", "variance": 0.006289056240987018},
{"district": "Göteborgs stads valkrets", "variance": 0.29326229770870055},
{"district": "Hallands läns valkrets", "variance": 11.93803076430059},
{"district": "Halmstads och Tönnersjö häraders valkrets", "variance": 0.018626822624579393},
{"district": "Halmstads och Ängelholms valkrets", "variance": 0.018626822624579396},
{"district": "Halmstads stads valkrets", "variance": 0.012497997115846822},
{"district": "Halmstads valkrets", "variance": 0.012497997115846822},
{"district": "Halmstads, Varbergs, Laholms, Falkenbergs och Kungsbacka valkrets", "variance": 0.012497997115846822},
{"district": "Hammarkinds härads med Stegeborgs skärgårds och Skärkinds härads domsagas valkrets", "variance": 0.00628905624098702},
{"district": "Hammarkinds och Skärkinds domsagas valkrets", "variance": 0.03653260695401379},
{"district": "Hammerdals, Lits och Offerdals tingslags valkrets", "variance": 0.00628905624098702},
{"district": "Harjagers och Rönnebergs häraders valkrets", "variance": 0.04234097099823746},
{"district": "Hedemora domsagas valkrets", "variance": 0.018626822624579396},
{"district": "Helsingborgs och Ängelholms valkrets", "variance": 0.018626822624579396},
{"district": "Helsingborgs valkrets", "variance": 0.05499919884633872},
{"district": "Helsingborgs, Landskrona och Lunds valkrets", "variance": 0.05596058323986542},
{"district": "Herrestads och Ljunits häraders valkrets", "variance": 0.012497997115846822},
{"district": "Hille och Valbo tingslag", "variance": 0.00628905624098702},
{"district": "Himle härads valkrets", "variance": 0.04234097099823744},
{"district": "Hälsinglands norra valkrets", "variance": 0.14232494792501202},
{"district": "Hälsinglands södra valkrets", "variance": 0.06265021631148852},
{"district": "Härjedalens domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Härnösands och Örnsköldsviks valkrets", "variance": 0.018626822624579396},
{"district": "Härnösands och Östersunds valkrets", "variance": 0.012497997115846822},
{"district": "Härnösands, Umeå och Skellefteå valkrets", "variance": 0.024675532767184736},
{"district": "Härnösands, Umeå, Luleå och Piteå valkrets", "variance": 0.024675532767184736},
{"district": "Härnösands, Umeå, Skellefteå, Piteå, Luleå och Haparanda valkrets", "variance": 0.00628905624098702},
{"district": "Höks härads valkrets", "variance": 0.018626822624579396},
{"district": "Ingelstads och Järrestads domsagas valkrets", "variance": 0.018626822624579393},
{"district": "Inlands domsagas valkrets", "variance": 0.03064412754366287},
{"district": "Jämtlands läns norra valkrets", "variance": 0.09297388239064253},
{"district": "Jämtlands läns södra valkrets", "variance": 0.08031565454254125},
{"district": "Jämtlands läns valkrets", "variance": 3.0719435987822457},
{"district": "Jämtlands norra domsagas valkrets", "variance": 0.04234097099823746},
{"district": "Jämtlands västra domsagas valkrets", "variance": 0.04234097099823745},
{"district": "Jämtlands östra domsagas valkrets", "variance": 0.012497997115846822},
{"district": "Jönköpings läns valkrets", "variance": 17.739785290818777},
{"district": "Jönköpings läns västra valkrets", "variance": 0.14232494792501202},
{"district": "Jönköpings läns östra valkrets", "variance": 0.09870213106873899},
{"district": "Jönköpings stads valkrets", "variance": 0.07018106072744752},
{"district": "Jönåkers härads valkrets", "variance": 0.03064412754366287},
{"district": "Jönåkers, Rönö och Hölebo häraders valkrets", "variance": 0.012497997115846822},
{"district": "Jösse domsagas valkrets", "variance": 0.03064412754366287},
{"district": "Kalix domsagas valkrets", "variance": 0.04806921967633392},
{"district": "Kalmar läns norra och södra landstingsområdens och Gotlands läns valkrets", "variance": 0.44127543662874535},
{"district": "Kalmar läns norra och södra landstingsområdens samt Gotlands läns valkrets", "variance": 0.006289056240987018},
{"district": "Kalmar läns norra valkrets", "variance": 0.3442156705656145},
{"district": "Kalmar läns södra valkrets", "variance": 0.7175532767184746},
{"district": "Kalmar läns valkrets", "variance": 9.485659349463226},
{"district": "Kalmar valkrets", "variance": 0.05928537093414517},
{"district": "Karlshamns och Sölvesborgs valkrets", "variance": 0.03653260695401379},
{"district": "Karlshamns, Sölvesborgs och Ronneby valkrets", "variance": 0.03064412754366287},
{"district": "Karlskrona valkrets", "variance": 0.07018106072744752},
{"district": "Karlstads och Filipstads valkrets", "variance": 0.03064412754366287},
{"district": "Karlstads valkrets", "variance": 0.012497997115846822},
{"district": "Kinda och Ydre domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Kinds härads valkrets", "variance": 0.018626822624579393},
{"district": "Kinds och Redvägs domsagas valkrets", "variance": 0.018626822624579396},
{"district": "Kinnefjärdings, Kinne och Kållands domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Konga härads valkrets", "variance": 0.03064412754366287},
{"district": "Kopparbergs läns norra valkrets", "variance": 0.08716551834641886},
{"district": "Kopparbergs läns valkrets", "variance": 0.1208139721198526},
{"district": "Kopparbergs läns västra valkrets", "variance": 0.1605511937189553},
{"district": "Kopparbergs läns östra valkrets", "variance": 0.08031565454254125},
{"district": "Kristianstads läns nordvästra valkrets", "variance": 0.11248197404262136},
{"district": "Kristianstads läns sydöstra valkrets", "variance": 0.12401858676494154},
{"district": "Kristianstads läns valkrets", "variance": 0.080756289056241},
{"district": "Kristianstads och Simrishamns valkrets", "variance": 0.03064412754366287},
{"district": "Kristianstads valkrets", "variance": 0.024675532767184743},
{"district": "Kristinehamns och Filipstads valkrets", "variance": 0.006289056240987021},
{"district": "Kristinehamns, Askersunds, Nora och Lindesbergs valkrets", "variance": 0.04234097099823744},
{"district": "Kristinehamns, Filipstads och Askersunds valkrets", "variance": 0.012497997115846822},
{"district": "Kronobergs läns och Hallands läns valkrets", "variance": 0.6245793943278322},
{"district": "Kronobergs läns valkrets", "variance": 4.955936548630026},
{"district": "Kronobergs läns västra valkrets", "variance": 0.04330235539176414},
{"district": "Kronobergs läns östra valkrets", "variance": 0.11829033808684503},
{"district": "Kullings härads valkrets", "variance": 0.00628905624098702},
{"district": "Kumla och Sundbo häraders valkrets", "variance": 0.07018106072744754},
{"district": "Köpings, Nora, Lindesbergs och Enköpings valkrets", "variance": 0.012497997115846822},
{"district": "Laholms, Falkenbergs, Varbergs och Kungsbacka valkrets", "variance": 0.024675532767184736},
{"district": "Landskrona valkrets", "variance": 0.04806921967633392},
{"district": "Lane och Stångenäs härads valkrets", "variance": 0.024675532767184743},
{"district": "Leksands tingslags valkrets", "variance": 0.012497997115846822},
{"district": "Lidköpings, Falköpings och Hjo valkrets", "variance": 0.03653260695401379},
{"district": "Lidköpings, Skara och Hjo valkrets", "variance": 0.03064412754366287},
{"district": "Lindes domsagas valkrets", "variance": 0.04234097099823746},
{"district": "Linköpings valkrets", "variance": 0.04806921967633393},
{"district": "Listers domsagas valkrets", "variance": 0.018626822624579393},
{"district": "Livgedingets domsagas valkrets", "variance": 0.00628905624098702},
{"district": "Ljustorps, Sköns, Indals och Selångers domsagas valkrets", "variance": 0.012497997115846822},
{"district": "Ljustorps, Sköns, Indals och Selångers tingslags valkrets", "variance": 0.00628905624098702},
{"district": "Luggude domsagas norra valkrets", "variance": 0.03653260695401379},
{"district": "Luggude domsagas södra valkrets", "variance": 0.018626822624579396},
{"district": "Luggude domsagas valkrets", "variance": 0.00628905624098702},
{"district": "Luleå domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Luleå och Haparanda valkrets", "variance": 0.018626822624579396},
{"district": "Luleå, Piteå och Haparanda valkrets", "variance": 0.012497997115846822},
{"district": "Luleå, Umeå, Piteå, Haparanda och Skellefteå valkrets", "variance": 0.018626822624579396},
{"district": "Lunds valkrets", "variance": 0.04234097099823745},
{"district": "Lysings och Göstrings domsagas valkrets", "variance": 0.04234097099823745},
{"district": "Malmö kommun", "variance": 0.012497997115846822},
{"district": "Malmö kommuns valkrets", "variance": 7.113924050632911},
{"district": "Malmö stads valkrets", "variance": 0.018626822624579396},
{"district": "Malmö, Helsingborgs, Landskrona och Lunds valkrets", "variance": 0.018626822624579396},
{"district": "Malmöhus läns mellersta valkrets", "variance": 0.18029963146931577},
{"district": "Malmöhus läns norra valkrets", "variance": 0.6859477647812846},
{"district": "Malmöhus läns södra valkrets", "variance": 1.1958019548149328},
{"district": "Malmöhus läns valkrets", "variance": 9.295785931741708},
{"district": "Malmöhus läns valkrets med Malmö och Helsingborg", "variance": 0.006289056240987018},
{"district": "Mariestads, Skara och Skövde valkrets", "variance": 0.04806921967633392},
{"district": "Mariestads, Skövde och Falköpings valkrets", "variance": 0.03064412754366287},
{"district": "Marks härads valkrets", "variance": 0.04806921967633392},
{"district": "Marstrands, Kungälvs, Alingsås och Ulricehamns valkrets", "variance": 0.024675532767184736},
{"district": "Medelpads valkrets", "variance": 0.13667681461304276},
{"district": "Medelpads västra domsagas valkrets", "variance": 0.03064412754366287},
{"district": "Medelpads östra domsagas valkrets", "variance": 0.012497997115846822},
{"district": "Medelstads domsagas valkrets", "variance": 0.03064412754366287},
{"district": "Mellansysslets domsagas valkrets", "variance": 0.05371735298830316},
{"district": "Mellersta Roslags domsagas valkrets", "variance": 0.012497997115846822},
{"district": "Mellersta Värends domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Mora, Sofia Magdalena och Vänjans, Orsa, Älvdals samt Särna och Idre tingslags valkrets", "variance": 0.00628905624098702},
{"district": "Nedansiljans domsagas valkrets", "variance": 0.00628905624098702},
{"district": "Njurunda, Indals och Ljustorps tingslags valkrets", "variance": 0.024675532767184736},
{"district": "Nora domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Nordals, Sundals och Valbo häraders valkrets", "variance": 0.006289056240987021},
{"district": "Nordmalings och Bjurholms samt Degerfors tingslags valkrets", "variance": 0.006289056240987021},
{"district": "Nordmalings och Bjurholms, Degerfors, Lycksele och Åsele tingslags valkrets", "variance": 0.00628905624098702},
{"district": "Nordmarks domsagas valkrets", "variance": 0.04234097099823744},
{"district": "Norra Hälsinglands domsagas valkrets", "variance": 0.03653260695401379},
{"district": "Norra Möre och Stranda domsagas valkrets", "variance": 0.018626822624579393},
{"district": "Norra Roslags domsagas valkrets", "variance": 0.024675532767184736},
{"district": "Norra Tjusts härads valkrets", "variance": 0.02467553276718474},
{"district": "Norra och Södra Vedbo domsagas tingslag", "variance": 0.00628905624098702},
{"district": "Norra och Södra Vedbo domsagas valkrets", "variance": 0.03653260695401379},
{"district": "Norra Ångermanlands domsagas valkrets", "variance": 0.018626822624579396},
{"district": "Norra Åsbo domsagas valkrets", "variance": 0.04806921967633394},
{"district": "Norra Åsbo härads valkrets", "variance": 0.00628905624098702},
{"district": "Norrbottens läns norra valkrets", "variance": 0.1732094215670566},
{"district": "Norrbottens läns södra valkrets", "variance": 0.06861881108796668},
{"district": "Norrbottens läns valkrets", "variance": 11.147131869892647},
{"district": "Norrbottens norra domsagas valkrets", "variance": 0.018626822624579396},
{"district": "Norrbottens södra domsagas norra valkrets", "variance": 0.00628905624098702},
{"district": "Norrbottens södra domsagas södra valkrets", "variance": 0.00628905624098702},
{"district": "Norrköpings och Linköpings valkrets", "variance": 0.09870213106873899},
{"district": "Norrköpings valkrets", "variance": 0.09549751642365006},
{"district": "Norrvidinge och Kinnevalds häraders valkrets", "variance": 0.00628905624098702},
{"district": "Norrvikens domsagas valkrets", "variance": 0.05371735298830316},
{"district": "Norsjö och Malå tingslags valkrets", "variance": 0.006289056240987021},
{"district": "Norunda och Örbyhus häraders valkrets", "variance": 0.024675532767184736},
{"district": "Nyköpings, Strängnäs, Mariefreds och Trosa valkrets", "variance": 0.00628905624098702},
{"district": "Nyköpings, Torshälla, Mariefreds, Trosa och Enköpings valkrets", "variance": 0.012497997115846819},
{"district": "Nyköpings, Torshälla, Strängnäs, Mariefreds och Trosa valkrets", "variance": 0.018626822624579396},
{"district": "Nätra och Nordingrå domsagas valkrets", "variance": 0.05499919884633872},
{"district": "Nås och Malungs domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Ockelbo och Hamrånge samt Hille och Valbo tingslags valkrets", "variance": 0.00628905624098702},
{"district": "Ockelbo och Hamrånge tingslag", "variance": 0.00628905624098702},
{"district": "Olands härads valkrets", "variance": 0.04806921967633392},
{"district": "Olands och Norunda häraders valkrets", "variance": 0.006289056240987021},
{"district": "Onsjö härads valkrets", "variance": 0.04234097099823745},
{"district": "Oppunda härads valkrets", "variance": 0.03653260695401379},
{"district": "Oppunda och Villåttinge häraders valkrets", "variance": 0.012497997115846822},
{"district": "Orusts och Tjörns domsagas valkrets", "variance": 0.03653260695401379},
{"district": "Oskarshamns, Vimmerby och Borgholms valkrets", "variance": 0.006289056240987021},
{"district": "Ovansiljans domsagas valkrets", "variance": 0.04234097099823746},
{"district": "Ovansjö, Torsåkers och Årsunda samt Hedesunda och Österfärnebo tingslags valkrets", "variance": 0.00628905624098702},
{"district": "Oxie härads valkrets", "variance": 0.012497997115846822},
{"district": "Piteå domsagas valkrets", "variance": 0.04806921967633394},
{"district": "Ragunda, Revsunds, Brunflo och Rödöns tingslags valkrets", "variance": 0.012497997115846822},
{"district": "Redvägs härads valkrets", "variance": 0.02467553276718474},
{"district": "Risinge, Hällestads och Tjällmo domsagas valkrets", "variance": 0.00628905624098702},
{"district": "Rönö, Hölebo och Daga häraders valkrets", "variance": 0.02467553276718474},
{"district": "Selebo, Åkers och Daga häraders valkrets", "variance": 0.018626822624579396},
{"district": "Sevede och Tunaläns domsagas valkrets", "variance": 0.04806921967633393},
{"district": "Sjuhundra, Lyhundra, Frötuna och Länna samt Bro och Vätö domsagas valkrets", "variance": 0.00628905624098702},
{"district": "Själevads och Arnäs domsagas valkrets", "variance": 0.024675532767184736},
{"district": "Skaraborgs läns norra valkrets", "variance": 0.1873097260054478},
{"district": "Skaraborgs läns södra valkrets", "variance": 0.11248197404262139},
{"district": "Skaraborgs läns valkrets", "variance": 8.401858676494149},
{"district": "Skellefteå tingslags valkrets", "variance": 0.006289056240987021},
{"district": "Skytts härads valkrets", "variance": 0.012497997115846822},
{"district": "Skytts och Oxie domsagas valkrets", "variance": 0.012497997115846822},
{"district": "Skåne läns norra och östra valkrets", "variance": 12.934505688190995},
{"district": "Skåne läns södra valkrets", "variance": 10.661312289697165},
{"district": "Skåne läns västra valkrets", "variance": 5.9405543983336},
{"district": "Skånings, Vilske och Valle domsagas valkrets", "variance": 0.024675532767184736},
{"district": "Sköns tingslags valkrets", "variance": 0.018626822624579396},
{"district": "Snevringe, Siende, Tuhundra o Yttertjurbo domsagas valkrets", "variance": 0.00628905624098702},
{"district": "Sollefteå och Ramsele tingslags valkrets", "variance": 0.043302355391764136},
{"district": "Sotholms och Öknebo häraders valkrets", "variance": 0.006289056240987021},
{"district": "Stockholms kommun", "variance": 0.006289056240987019},
{"district": "Stockholms kommuns valkrets", "variance": 115.27579714789299},
{"district": "Stockholms läns landstingskommuns valkrets", "variance": 0.006289056240987019},
{"district": "Stockholms läns norra valkrets", "variance": 0.0745072904983176},
{"district": "Stockholms läns och Uppsala läns valkrets", "variance": 0.9709982374619455},
{"district": "Stockholms läns södra valkrets", "variance": 0.29069860599262937},
{"district": "Stockholms läns valkrets", "variance": 169.07819259734015},
{"district": "Stockholms läns västra domsagas valkrets", "variance": 0.03064412754366287},
{"district": "Stockholms stads andra valkrets", "variance": 0.006289056240987021},
{"district": "Stockholms stads valkrets", "variance": 0.5597260054478448},
{"district": "Strömstads, Lysekils, Marstrands, Kungälvs och Åmåls valkrets", "variance": 0.006289056240987021},
{"district": "Sundals härads valkrets", "variance": 0.03653260695401379},
{"district": "Sundsvalls och Östersunds valkrets", "variance": 0.018626822624579396},
{"district": "Sundsvalls valkrets", "variance": 0.05928537093414517},
{"district": "Sunnerbo domsagas valkrets", "variance": 0.018626822624579396},
{"district": "Sunnerbo domsagas västra valkrets", "variance": 0.03653260695401379},
{"district": "Sunnerbo domsagas östra valkrets", "variance": 0.018626822624579396},
{"district": "Svartlösa härads valkrets", "variance": 0.006289056240987021},
{"district": "Sydöstra Hälsinglands domsagas valkrets", "variance": 0.018626822624579396},
{"district": "Sävedals domsagas valkrets", "variance": 0.00628905624098702},
{"district": "Sävedals härads valkrets", "variance": 0.006289056240987021},
{"district": "Söderhamns och Hudiksvalls valkrets", "variance": 0.03064412754366287},
{"district": "Söderhamns valkrets", "variance": 0.03064412754366287},
{"district": "Södermanlands läns mindre städers valkrets", "variance": 0.006289056240987021},
{"district": "Södermanlands läns norra valkrets", "variance": 0.09297388239064253},
{"district": "Södermanlands läns och Västmanlands läns valkrets", "variance": 0.9252123057202372},
{"district": "Södermanlands läns södra valkrets", "variance": 0.08716551834641886},
{"district": "Södermanlands läns valkrets", "variance": 12.023273513859964},
{"district": "Södersysslets domsagas valkrets", "variance": 0.04234097099823746},
{"district": "Södertälje valkrets", "variance": 0.006289056240987021},
{"district": "Södertälje, Norrtälje, Vaxholms, Öregrunds, Östhammars och Sigtuna valkrets", "variance": 0.05371735298830316},
{"district": "Södertörns domsagas valkrets", "variance": 0.07550873257490787},
{"district": "Södra Hälsinglands domsagas valkrets", "variance": 0.012497997115846822},
{"district": "Södra Jämtlands domsagas valkrets", "variance": 0.024675532767184736},
{"district": "Södra Möre domsagas västra valkrets", "variance": 0.03064412754366287},
{"district": "Södra Möre domsagas östra valkrets", "variance": 0.018626822624579393},
{"district": "Södra Roslags domsagas valkrets", "variance": 0.03064412754366287},
{"district": "Södra Tjusts härads valkrets", "variance": 0.018626822624579396},
{"district": "Södra Åsbo och Bjäre domsagas valkrets", "variance": 0.04234097099823744},
{"district": "Torna härads valkrets", "variance": 0.04806921967633393},
{"district": "Torneå domsagas valkrets", "variance": 0.03653260695401379},
{"district": "Torps, Tuna och Njurunda tingslags valkrets", "variance": 0.03064412754366287},
{"district": "Trelleborgs, Skanör-Falsterbo, Simrishamns och Ängelholms valkrets", "variance": 0.018626822624579396},
{"district": "Tunge, Sörbygdens och Sotenäs häraders valkrets", "variance": 0.048069219676333916},
{"district": "Tveta härads valkrets", "variance": 0.018626822624579396},
{"district": "Tveta, Vista och Mo domsagas valkrets", "variance": 0.018626822624579396},
{"district": "Tössbo och Vedbo domsagas valkrets", "variance": 0.03653260695401379},
{"district": "Uddevalla och Strömstads valkrets", "variance": 0.018626822624579396},
{"district": "Uddevalla valkrets", "variance": 0.006289056240987021},
{"district": "Uddevalla, Strömstads och Marstrands valkrets", "variance": 0.00628905624098702},
{"district": "Uddevalla, Strömstads, Marstrands och Kungälvs valkrets", "variance": 0.04234097099823744},
{"district": "Umeå tingslags valkrets", "variance": 0.03653260695401379},
{"district": "Umeå, Nordmalings och Bjurholms tingslags valkrets", "variance": 0.018626822624579396},
{"district": "Umeå, Skellefteå och Piteå valkrets", "variance": 0.012497997115846822},
{"district": "Uppsala läns mellersta domsagas valkrets", "variance": 0.03064412754366287},
{"district": "Uppsala läns norra domsagas tingslag", "variance": 0.00628905624098702},
{"district": "Uppsala läns norra domsagas valkrets", "variance": 0.00628905624098702},
{"district": "Uppsala läns södra domsagas valkrets", "variance": 0.018626822624579396},
{"district": "Uppsala läns valkrets", "variance": 15.630347700688992},
{"district": "Uppsala valkrets", "variance": 0.06477327351385996},
{"district": "Uppvidinge härads valkrets", "variance": 0.03653260695401379},
{"district": "Vadsbo norra domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Vadsbo södra domsagas valkrets", "variance": 0.06072744752443517},
{"district": "Vadstena, Skänninge, Söderköpings, Motala och Gränna valkrets", "variance": 0.024675532767184736},
{"district": "Vadstena, Söderköpings, Skänninge och Gränna valkrets", "variance": 0.012497997115846822},
{"district": "Vadstena, Söderköpings, Skänninge, Motala, Gränna och Askersunds valkrets", "variance": 0.006289056240987021},
{"district": "Valbo och Nordals häraders valkrets", "variance": 0.04330235539176415},
{"district": "Vartofta och Frökinds domsagas valkrets", "variance": 0.024675532767184736},
{"district": "Vaxholms, Norrtälje, Östhammars, Öregrunds och Sigtuna valkrets", "variance": 0.006289056240987021},
{"district": "Vedens och Bollebygds härads valkrets", "variance": 0.03064412754366287},
{"district": "Vemmenhögs härads valkrets", "variance": 0.018626822624579396},
{"district": "Vemmenhögs, Ljunits och Herrestads domsagas valkrets", "variance": 0.006289056240987021},
{"district": "Vifolka, Valkebo och Gullbergs domsagas valkrets", "variance": 0.024675532767184736},
{"district": "Villands härads valkrets", "variance": 0.03064412754366288},
{"district": "Villåttinge härads valkrets", "variance": 0.04234097099823745},
{"district": "Visby och Borgholms valkrets", "variance": 0.012497997115846822},
{"district": "Visby stads valkrets", "variance": 0.00628905624098702},
{"district": "Visby valkrets", "variance": 0.024675532767184736},
{"district": "Vista och Mo häraders valkrets", "variance": 0.012497997115846822},
{"district": "Vänersborgs och Åmåls valkrets", "variance": 0.024675532767184736},
{"district": "Vänersborgs, Alingsås och Ulricehamns valkrets", "variance": 0.006289056240987021},
{"district": "Vänersborgs, Åmåls och Kungälvs valkrets", "variance": 0.006289056240987021},
{"district": "Värmlands läns norra valkrets", "variance": 0.06861881108796668},
{"district": "Värmlands läns valkrets", "variance": 13.809325428617207},
{"district": "Värmlands läns västra valkrets", "variance": 0.1065934946322705},
{"district": "Värmlands läns östra valkrets", "variance": 0.061849062650216315},
{"district": "Västbo härads valkrets", "variance": 0.04919083480211505},
{"district": "Väster- och Öster-Rekarne häraders valkrets", "variance": 0.04806921967633394},
{"district": "Västerbergslags domsagas valkrets", "variance": 0.03653260695401379},
{"district": "Västerbottens läns norra valkrets", "variance": 0.06265021631148852},
{"district": "Västerbottens läns och Norrbottens läns valkrets", "variance": 1.0335282807242432},
{"district": "Västerbottens läns södra valkrets", "variance": 0.11248197404262136},
{"district": "Västerbottens läns valkrets", "variance": 10.664036212145486},
{"district": "Västerbottens mellersta domsagas valkrets", "variance": 0.03653260695401379},
{"district": "Västerbottens norra domsagas valkrets", "variance": 0.04806921967633392},
{"district": "Västerbottens södra domsagas valkrets", "variance": 0.012497997115846822},
{"district": "Västerbottens västra domsagas valkrets", "variance": 0.04234097099823745},
{"district": "Västernorrlands läns och Jämtlands läns valkrets", "variance": 0.967312930620093},
{"district": "Västernorrlands läns valkrets", "variance": 12.333480211504565},
{"district": "Västerviks och Eksjö valkrets", "variance": 0.018626822624579396},
{"district": "Västerviks och Oskarshamns valkrets", "variance": 0.018626822624579396},
{"district": "Västerviks valkrets", "variance": 0.006289056240987021},
{"district": "Västerviks, Oskarshamns och Borgholms valkrets", "variance": 0.00628905624098702},
{"district": "Västerås och Köpings valkrets", "variance": 0.03064412754366287},
{"district": "Västerås valkrets", "variance": 0.02467553276718474},
{"district": "Västerås, Köpings och Enköpings valkrets", "variance": 0.024675532767184736},
{"district": "Västmanlands läns norra domsagas valkrets", "variance": 0.04806921967633392},
{"district": "Västmanlands läns södra domsagas valkrets", "variance": 0.06477327351385996},
{"district": "Västmanlands läns valkrets", "variance": 12.353509053036369},
{"district": "Västmanlands läns västra domsagas valkrets", "variance": 0.05928537093414516},
{"district": "Västmanlands läns västra valkrets", "variance": 0.06265021631148852},
{"district": "Västmanlands läns östra domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Västmanlands läns östra valkrets", "variance": 0.07450729049831759},
{"district": "Västra Göinge domsagas valkrets", "variance": 0.018626822624579393},
{"district": "Västra Götalands läns norra valkrets", "variance": 5.6465310046466906},
{"district": "Västra Götalands läns södra valkrets", "variance": 4.860318859157186},
{"district": "Västra Götalands läns västra valkrets", "variance": 14.471438871975645},
{"district": "Västra Götalands läns östra valkrets", "variance": 4.844576189713188},
{"district": "Västra Hälsinglands domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Västra Värends domsagas valkrets", "variance": 0.024675532767184736},
{"district": "Västra härads domsagas valkrets", "variance": 0.024675532767184736},
{"district": "Västra och Östra Hisings häraders valkrets", "variance": 0.02467553276718474},
{"district": "Västra och Östra Hisings, Askims och Sävedals domsagas valkrets", "variance": 0.00628905624098702},
{"district": "Vättle och Ale häraders valkrets", "variance": 0.00628905624098702},
{"district": "Vättle, Ale och Kullings domsagas valkrets", "variance": 0.05371735298830316},
{"district": "Växjö och Eksjö valkrets", "variance": 0.006289056240987021},
{"district": "Växjö och Oskarshamns valkrets", "variance": 0.024675532767184736},
{"district": "Växjö valkrets", "variance": 0.02467553276718474},
{"district": "Växjö, Eksjö och Vimmerby valkrets", "variance": 0.012497997115846822},
{"district": "Växjö, Eksjö, Vimmerby och Borgholms valkrets", "variance": 0.00628905624098702},
{"district": "Ystads valkrets", "variance": 0.012497997115846822},
{"district": "Ystads, Skanör-Falsterbo och Trelleborgs valkrets", "variance": 0.03653260695401379},
{"district": "http://www.wikidata.org/.well-known/genid/20608529079cf9b7b33bf0278e3eebd4", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/322d651bb5e3e3840cde2f9491f9f2c2", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/3ba14e1f6bb0710eed70c4640fc5f89d", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/3fb34eee98729fe7810f9a83deb34076", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/4b4faaf3802b7d070ba6684af64b68e7", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/64413215d0e950459541f354be70a9a0", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/6f8ec0e3fc59d1b8ecd98a178b9bc5ac", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/7cf1ccf3337567d7c27362f1bbb0c1d4", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/9c5e0c8c47da1abe1b770d2a871bf543", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/ab87261552eba8446adad02376c37ab3", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/bb649dc27a6efc73e9d523267af2a95e", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/bdbdb708f68e1f411eaf316733bf6139", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/f0d5203116b836e4c66d3d0240b36f32", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/f1617a1d4962b6e6c6dd1eca3ea84ca3", "variance": 0.006289056240987019},
{"district": "http://www.wikidata.org/.well-known/genid/f59a429583fd1999cf77a4cf0e72353b", "variance": 0.006289056240987019},
{"district": "Älvdals och Nyeds domsagas valkrets", "variance": 0.03064412754366287},
{"district": "Älvsborgs läns mellersta valkrets", "variance": 0.15338086845056884},
{"district": "Älvsborgs läns norra valkrets", "variance": 5.307643005928536},
{"district": "Älvsborgs läns södra valkrets", "variance": 0.030644127543662875},
{"district": "Älvsborgs läns valkrets", "variance": 1.497997115846819},
{"district": "Åkerbo och Skinnskattebergs domsagas valkrets", "variance": 0.00628905624098702},
{"district": "Åkerbo, Bankekinds och Hanekinds domsagas valkrets", "variance": 0.04806921967633393},
{"district": "Åkerbo, Bankekinds och Hanekinds tingslag", "variance": 0.006289056240987021},
{"district": "Åkers och Selebo häraders valkrets", "variance": 0.006289056240987021},
{"district": "Ångermanlands mellersta domsagas valkrets", "variance": 0.05499919884633872},
{"district": "Ångermanlands norra valkrets", "variance": 0.06861881108796668},
{"district": "Ångermanlands södra domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Ångermanlands södra valkrets", "variance": 0.14789296587085404},
{"district": "Ångermanlands västra domsagas valkrets", "variance": 0.02467553276718474},
{"district": "Årstads och Faurås häraders valkrets", "variance": 0.03653260695401379},
{"district": "Ås och Gäsene domsagas valkrets", "variance": 0.04234097099823745},
{"district": "Åse, Viste, Barne och Laske domsagas valkrets", "variance": 0.04806921967633394},
{"district": "Ölands domsagas valkrets", "variance": 0.018626822624579396},
{"district": "Ölme, Visnums och Väse häraders valkrets", "variance": 0.02467553276718474},
{"district": "Örbyhus härads valkrets", "variance": 0.006289056240987021},
{"district": "Örebro kommun", "variance": 0.0062890562409870215},
{"district": "Örebro läns norra valkrets", "variance": 0.16311488543502642},
{"district": "Örebro läns södra valkrets", "variance": 0.14232494792501202},
{"district": "Örebro läns valkrets", "variance": 15.833840730652142},
{"district": "Örebro och Glanshammars häraders valkrets", "variance": 0.02467553276718474},
{"district": "Örebro valkrets", "variance": 0.04806921967633393},
{"district": "Östbo härads valkrets", "variance": 0.04234097099823745},
{"district": "Östergötlands läns med Norrköpings valkrets", "variance": 0.030644127543662875},
{"district": "Östergötlands läns norra valkrets", "variance": 0.11136035891684026},
{"district": "Östergötlands läns södra valkrets", "variance": 0.14232494792501202},
{"district": "Östergötlands läns valkrets", "variance": 26.88819900656946},
{"district": "Östersunds och Hudiksvalls valkrets", "variance": 0.03653260695401379},
{"district": "Östra Göinge härads valkrets", "variance": 0.024675532767184736},
{"district": "Östra härads domsagas valkrets, Blekinge län", "variance": 0.018626822624579396},
{"district": "Östra härads domsagas valkrets, Jönköpings län", "variance": 0.024675532767184736}
]



     

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
    

    
    def test_constituency_completion_by_start_year(self):
        """ Test if MP do have a constituency, and if the constituency is listed in the data. """
        
        
        all_years, incomplete_years = self.get_constituency_completion_by_start_year(self.members)
    
        plt.figure(figsize=(12, 6))
        plt.plot([entry['year'] for entry in all_years], [float(entry['completion_rate'].strip('%')) for entry in all_years], marker='o', label='Current Data')
        plt.plot([entry['year'] for entry in self.REFERENCE_COVERAGE], [float(entry['completion_rate'].strip('%')) for entry in self.REFERENCE_COVERAGE], marker='x', label='Reference Data')
        plt.xlabel('Start Year')
        plt.ylabel('Completion Rate')
        plt.title('Constituency Completion Rate by Start Year')
        plt.legend()
        plt.gca().xaxis.set_major_locator(ticker.MultipleLocator(10)) # Un tick tous les 10 ans
        plt.xticks(rotation=45) 
        plt.tight_layout()
        plt.savefig("test/result/constituency_completion_by_year.png")
        REFERENCE = {d['year']: d for d in self.REFERENCE_COVERAGE}
        failures = 0

        for entry in all_years:
            current_rate = float(entry['completion_rate'].strip('%')) / 100
            ref_entry = REFERENCE.get(entry['year'])
            if ref_entry is None:
                continue
            ref_rate = float(REFERENCE[entry['year']]['completion_rate'].strip('%')) / 100
            if current_rate < (ref_rate - 0.0001):
                msg = f"Year {entry['year']}: {entry['completion_rate']} (ref: {REFERENCE[entry['year']]['completion_rate']})"
                failures += 1
                logger.error(msg)
        
        self.assertEqual(failures, 0, f"All years should have a completion rate at least as good as the reference. Failures: {failures}")
        #self.REFERENCE_COVERAGE = all_years #for dynamic non decreasing reference
    
   
    def test_MP_per_district_per_year(self):
        """ Tests the coherence of the data based on the computation of empirical variance"""

        members = self.members
        unique_districts = members['district'].dropna().unique()

    
        districts_tries = sorted(unique_districts)

        # 3. Print the number of unique constituencies 
        print(f"Number of unique constituencies : {len(districts_tries)}")
        print("-" * 30)
        
        df_counts = self.get_MP_per_district_per_year(members)
        pivot_counts = df_counts.pivot(index='year', columns='district', values='mp_count').fillna(0)
        for district in pivot_counts.columns:
            plt.figure(figsize=(12, 6))
            plt.plot(pivot_counts.index, pivot_counts[district], marker='o', label=district)
            plt.xlabel('Year')
            plt.ylabel('Number of MPs')
            plt.title(f'Number of MPs in {district} Over Time')
            plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.gca().xaxis.set_major_locator(ticker.MultipleLocator(10)) # Un tick tous les 10 ans
            plt.xticks(rotation=45)
            plt.tight_layout()
            safe_district_name = re.sub(r'[^a-zA-Z0-9]', '_', district)
            plt.savefig(f"test/result/mp_per_district_over_time_{safe_district_name}.png")

        districts_variance = pivot_counts.var(axis=0, ddof=0)
        reference = {d['district']: d['variance'] for d in self.REFERENCE_VARIANCES}
        failures = 0
        numer = 0
        for district, var in districts_variance.items():
            numer += 1
            if var > reference.get(district, 0.0) + 1e-4:  # Using the lookup for variance thresholds
                failures += 1
                logger.error(f"District {district} variance should be below {reference.get(district, 0.0)}.")  
        self.assertEqual(failures, 0, f"All districts should have a variance of MP count per year below reference. Failures: {failures}")             
        self.assertLessEqual(len(unique_districts), CONSTITUENCY_COUNT_THRESHOLD, f"The number of unique constituencies should be less than {CONSTITUENCY_COUNT_THRESHOLD}. Found: {len(unique_districts)}")

if __name__ == '__main__':
    unittest.main()
