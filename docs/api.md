# Python API

Install the package through Poetry before importing it. It has no third-party
runtime dependencies and includes a `py.typed` marker.

```python
from datetime import datetime
from pathlib import Path

from bike_sharing import evaluate, load_dataset

dataset = load_dataset(Path("bike.csv"))
report = evaluate(dataset, cutoff=datetime(2012, 7, 1), horizon_hours=168)
print(report["metrics"])
```

## `Observation(timestamp: datetime, count: int)`

Frozen record. The timestamp must be timezone-naive and on an exact hour;
the count must be a nonnegative integer, excluding booleans. Invalid types
raise `TypeError`; invalid values raise `ValueError`.

## `DemandDataset(observations, sha256, source_name)`

Frozen record of a tuple of observations and source identity. Prefer
`load_dataset` to constructing it manually. Evaluation requires nonempty,
unique and strictly increasing observations. Manually constructed datasets
are responsible for truthful source metadata.

## `load_dataset(path: Path) -> DemandDataset`

Read bytes once, compute their SHA-256 and validate the [CSV contract](data.md).
Return records sorted chronologically. I/O errors remain `OSError` subclasses;
schema/value failures raise `ValueError` with the row number when available.
Malformed CSV can raise `csv.Error`.

## `forecast_baselines(training, timestamps)`

Accept training observations and future timestamps as sequences. Return a
dictionary mapping `training_mean` and `hour_of_week_mean` to tuples of floats
in the supplied timestamp order. Every prediction time must follow the last
training observation. Empty inputs raise `ValueError`. No evaluation outcomes
are accepted by this interface.

## `evaluate(dataset, cutoff, horizon_hours=168, *, split=StudySplit())`

Return a validation diagnostic with software versions, `study_split`, `dataset`,
`protocol` and `metrics`. The half-open window must be wholly within validation;
training timestamps are strictly before cutoff. A nonpositive/noninteger
horizon, empty evaluation, window beyond dataset coverage or test-period
crossing raises `ValueError`. A diagnostic does not produce a selection. See the
[protocol](methodology.md) for feature availability and gap handling.

## `StudySplit(validation_start, test_start, test_end)`

Frozen, ordered, timezone-naive hourly boundaries. Defaults are July 1, October 1
and January 1, 2013. `partition_dataset(dataset, split)` returns disjoint
`training`, `validation` and `test` tuples, each required to contain observations.
The source must span the requested study end; observations at or after that end
are outside the study. No outcome metrics are computed by partitioning.

## `select_on_validation(dataset, split=StudySplit())`

Fit on training, compare both frozen baselines across validation and return a
report with `stage="validation"`, `test_scored=false` and a `selection` artifact.
The lowest validation MAE wins; ties prefer `training_mean`.

## `read_selection(path: Path) -> FrozenSelection`

Parse the selection embedded in a full validation report. Reject diagnostics,
final-test reports, invalid fields, unknown models and unsupported schemas.
The selection records model, dataset SHA-256, boundaries and package version.

## `evaluate_test(dataset, selection)`

Require matching dataset and package versions, refit on training plus validation,
and return only the chosen model's errors across the test partition. The model
stays frozen throughout test. This API is exercised on synthetic data in CI;
the real test period remains unscored until development is complete.

## Command line

`bike-sharing` defaults to full validation selection, printing JSON to standard
output unless `--output` is provided. `--cutoff` selects a diagnostic instead.
`--stage test --selection REPORT` enables final testing with saved boundaries;
boundary or diagnostic overrides are rejected in this mode.
It returns status 2 with a concise diagnostic for invalid inputs or file errors.
The output path cannot equal the input data or saved selection path. Parent output directories are
created as needed. Use `bike-sharing --help` for the supported flags.
