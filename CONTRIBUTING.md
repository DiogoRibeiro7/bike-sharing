# Contributing

Use Python 3.12 and Poetry 2.5.1. Install the committed environment with
`poetry install --with dev,docs`; do not regenerate the lockfile for unrelated edits.

Choose an existing roadmap issue, work on a short-lived branch and open a PR
against the current default branch, `master`. Include the problem, resulting
behaviour, validation evidence and any limitations. Do not push directly to
the default branch or merge your own proposed changes through automation.

Run the development commands in the README before opening a PR. Public Python
interfaces need type hints and docstrings. Validate input at public boundaries;
use comments to explain statistical assumptions and non-obvious implementation choices.

Add tests for temporal leakage, statistical contracts, numerical correctness
and failure cases when behaviour changes. Do not introduce outcome-dependent
feature selection or fit preprocessing on the evaluation period.

Keep the historical dataset and notebook unchanged. Document any source,
transformation or licensing evidence in the data audit. An upstream dataset's
terms are not inferred from this repository's Apache software license.

Method changes need a documented forecast horizon and feature-availability
contract. Report unfavourable results and do not tune against the final temporal
holdout. No Prophet dependency is used in this project.

## Frozen release evidence

The October–December quarter is now consumed. Report later changes as a new
exploratory study; do not retune on these outcomes and describe them as an
untouched final test. Preserve `benchmarks/release-v1` and its source/selection
hashes. Any replacement study needs separately named evidence and an explicit
new evaluation design.

Run `poetry run python scripts/reproduce_release.py` to check the frozen reports,
and `poetry run python scripts/build_tables.py` before editing the brief. Compile
LaTeX twice and visually check the PDF after substantive layout/text changes.
Keep publication status accurate: a prepared workflow is not a verified live
site or tag. Publication runs only from reviewed `master`, after CI succeeds.
