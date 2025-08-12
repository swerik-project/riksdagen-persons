# MP Coverage

## Summary

We want to know that we have the correct number of MPs in the metadata for each parliament year and chamber.


## What is the problem

It's straightforward to add known information to a database, but less so to estimate information that is missing. In this case we want to make sure that we have enough MPs per parliament year and chamber, but also not too many. Since there are a fixed number of seats in the parliament, we have a fixed baseline against which we can check that we have an adequate number of MPs for each day of conducted parliament business.


## Estimation procedure

An extensive list of MPs and their mandate periods have been compiled using Wikidata, Riksdagen Öppna data, and Biografi Banden with the help of students at Uppsala University and experts at the Riksdagenbibliotek.

For each parliament day (date for which there is a Record), this dimension checks the number of MPs with an overlapping mandate and compares that number with the baseline number of MPs who should have been sitting in the parliament.


## The code
