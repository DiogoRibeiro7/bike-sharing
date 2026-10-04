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

## `evaluate(dataset, cutoff, horizon_hours=168)`

Return a JSON-serializable report with `schema_version`, software versions,
`dataset`, `protocol` and `metrics`. The window is half-open; training timestamps
are strictly before cutoff. A nonpositive/noninteger horizon, empty evaluation
or a window beyond dataset coverage raises `ValueError`. See the
[protocol](methodology.md) for feature availability and gap handling.

## Command line

`bike-sharing` prints JSON to standard output unless `--output` is provided.
It returns status 2 with a concise diagnostic for invalid inputs or file errors.
The output path cannot equal the input path. Parent output directories are
created as needed. Use `bike-sharing --help` for the supported flags.
