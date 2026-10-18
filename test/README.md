# Data Tests

This directory contains Python `unittest` checks for the published tables under
[`../data/`](../data/), together with reference inputs and synthetic regression
tests. Some legacy tests also check quality and coverage baselines.

## Running Tests

Run tests from the repository root, with the dependencies used by the relevant
job in [the CI workflow](../.github/workflows/push.yml) installed. For example:

```sh
python -m unittest test.csvw_metadata test.sort_order
python -m unittest \
  test.committee_integrity \
  test.test_committee_integrity_regressions \
  test.test_committee_mandate_regressions
```

These examples are not the full CI suite. Use explicit module names as CI does:
many existing files do not match the default `unittest` discovery pattern.

## Documentation

The authoritative documentation of each integrity guarantee belongs in its test
function's docstring, starting with `Guarantee:`, as required by
[Decision 0021](https://github.com/swerik-project/the-swedish-parliament-corpus/blob/dev/docs/decisions/decision-0021_writing-data-integrity-tests.md).
This README describes how to run and navigate the tests, not their individual
guarantees.

## Directories

### `data/`

Contains reference inputs used by tests, including manually checked dates,
protected person IDs, coverage baselines and sort-order configuration. Not every
test needs a reference file: synthetic regressions build their inputs in memory.

### `docs/`

Contains legacy test documentation. Do not add or maintain separate integrity
guarantee documentation here; move useful content into the relevant test file
before removing the legacy document.

### `result/` and `results/`

Contain diagnostic outputs, not test inputs. `result/` includes a few tracked
legacy outputs; no files under `results/` are currently tracked. Some tests write
diagnostics to these paths, while others use a configured output directory.
Logging and assertion messages identify failures; not every test writes a file.
