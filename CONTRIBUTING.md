# How to contribute?

## Quick start

1. Clone or fork the repository
	- clone the repository if your user has write access in the SWERIK organization
	- otherwise create a fork
2. Create a new branch from the current `dev` branch
3. Make edits, commit and push
	- watch github actions and if all the tests that run pass, proceed to (4)
4. Open Pull Request
	- if any significant amount of time has passed since creating your fork/branch, it's advisable to fetch the most recent changes from our upstream dev branch before opening a pull request.
	- Pull requests should be opened into the `dev` branch. Any PR into main will be automatically rejected.
	- if all automated tests pass at the pull request phase, we manually evaluate a sample of edits and decide how to proceed with merging 
	

## Good to observe

### Evaluation of edits

When deciding whether to merge a PR, we evaluate a sample of edits, which means we rely on git diffs to see proposed changes to the repository. There are some things to keep in mind in order to make evaluation of the proposal as straightforward as possible:
 - Check that your software isn't rewriting end-line characters or replacing tabs with spaces or spaces with tabs. This will cause a diff to show that every line is edited and your PR to be rejected.
 - Formatting and sorting: use `pyriksdagen.io.write_tei` to write xml documents, carefully observe column sort order in csv files (to be documented). Changes to sort order and formatting obfuscate substantive changes in a PR.
 - Isolate types of edits: It's generally better to have one pull request per proposed change so that the edits can be evaluated. If one would, for example, add mandate periods to `member_of_parliament.csv` and at the same time merge consecutive mandates into a single row, it becomes more difficult to evaluate the additions, particularly if two types of changes occur disproportionately. We strongly recommend incoming PRs address a single issue. 