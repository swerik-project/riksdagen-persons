# Riksdagen Persons: Quality Estimates

This directory contains code and data related to estimating the quality of the Riksdagen Persons metadata corpus, along with the estimates themselves.

## What's here?

### `./`

Python code used to estimate various quality dimensions.

- `qe_mp-coverage.py` : Estimates coverage of MPs over time.
- `qe_check-riksdagen-party-distribution.py` : Computes party distribution snapshots and compares them against the gold standard data.


Support files

- `README.md` : this file
- `__init__.py` : used for building the documentation


### `data/`

Contains data necessary to run the quality estimation code. The sources of the data inside these files are the following:

- `gold-standard-party-distribution.csv` : Ground truth data derived from official Riksdag registers, containing party affiliations and member counts per year. This dataset serves as the **gold standard** for the party distribution quality checks.


### `docs/`

Contains explanation and justifications for each quality dimension.


### `estimates/`

Contains versioned output of quality estimations.

### `plot/`

Contains code for generating plots from the estimate results
