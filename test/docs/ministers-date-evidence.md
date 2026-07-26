# Ministers Date Evidence Test

## Summary

Checks that minister start and end dates that have been manually reviewed by Fredrik from Sveriges Regeringar. 

The test reads `test/data/ministers-date-evidence.csv`. Each row is a boundary observation for one person and role: either a `START` date or an `END` date. The test then verifies that `data/minister.csv` contains at least one row with the same `person_id`, `role`, and observed boundary date.

This is intentionally boundary-based rather than full-row-based because `minister.csv` can store the same portfolio across multiple government rows.

Year-only evidence, such as `1858`, is accepted against a more precise date in `minister.csv`, such as `1858-04-07`.
