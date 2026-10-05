# Python API

Install the package and its locked numerical dependencies through Poetry before
importing it. The package includes a `py.typed` marker and uses strict mypy.

```python
from pathlib import Path

from bike_sharing import load_dataset, select_rolling_on_validation

dataset = load_dataset(Path("bike.csv"))
report = select_rolling_on_validation(dataset)
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

## `select_rolling_on_validation(dataset, split=StudySplit(), *, horizon_hours=168)`

Compare the four fixed candidates across expanding training prefixes. Disjoint
calendar horizons cover validation exactly, with a shortened final fold. Return
per-fold and pooled MAE/RMSE/deviance, runtime, coefficient diagnostics and the
selection. Outcomes in test never enter any fitting prefix or metric.
The selection minimizes pooled MAE with the documented candidate tie order.

## `forecast_model(model, training, timestamps, *, origin) -> Forecast`

Available from `bike_sharing.models`. Require strictly ordered, nonempty training
observations before the origin and nonempty prediction timestamps at or after it.
Return `Forecast.values` and JSON-compatible fit `details`. Unknown candidates,
invalid boundaries, nonconvergence and nonfinite forecasts raise `ValueError`.
Seasonal-naive repeats the week preceding the origin, never later actuals.

`calendar_features(timestamps)` returns a NumPy float64 matrix with 57 fixed
calendar features in `FEATURE_NAMES` order. Its definition is independent of
the data's outcomes. See the [model specification](models.md).

## `calendar_folds(start, end, horizon_hours=168)` and `count_metrics(actual, predicted)`

Available from `bike_sharing.rolling`. Folds tile an ordered interval of naive
whole hours without overlap, including its partial tail. Count metrics extend
MAE/RMSE with mean Poisson deviance, applying the documented `1e-9` prediction
floor only to deviance. Invalid lengths, negative counts or nonfinite forecasts
are rejected.

## `read_selection(path: Path) -> FrozenSelection`

Parse the selection embedded in a full validation report. Reject diagnostics,
final-test reports, invalid fields, unknown models and unsupported schemas.
Schema 2 records model, dataset SHA-256, boundaries, package version, protocol,
horizon and configuration hash. Schema 1 is read as a historical fixed-origin
selection; the package-version check still applies before final testing.

## `evaluate_test(dataset, selection)`

Require matching dataset, package and model-configuration identities. Return
only the selected model's errors, using its frozen procedure: either one
whole-quarter fit or expanding fits at the saved cadence. A rolling test may
use earlier test observations at later scheduled origins, without reselecting
model or settings. CI exercises this API on synthetic data; the real test
period was evaluated after development choices were frozen; see [final results](final-results.md).

## Command line

`bike-sharing` defaults to rolling validation selection, printing JSON to
standard output unless `--output` is provided. `--fold-hours` changes the rolling
cadence; `--protocol fixed` retains the two-mean fixed-origin comparison.
`--cutoff` selects a diagnostic instead and cannot be combined with protocol or
fold options. `--stage test --selection REPORT` enables final testing with saved
settings; protocol, cadence, boundary and diagnostic overrides are rejected.
It returns status 2 with a concise diagnostic for invalid inputs or file errors.
The output path cannot equal the input data or saved selection path. Parent output directories are
created as needed. Use `bike-sharing --help` for the supported flags.

## Interval calibration API

Import these interfaces from `bike_sharing.calibration` and
`bike_sharing.intervals`:

```python
from bike_sharing.calibration import IntervalSpec
from bike_sharing.intervals import evaluate_interval_validation

report = evaluate_interval_validation(dataset, spec=IntervalSpec())
```

`IntervalSpec(levels=(0.8, 0.9, 0.95), calibration_folds=4,
minimum_observations=30)` is frozen and validates ordered, unique levels and
positive integer support settings. `to_dict()` records the complete fixed rule;
`sha256` identifies it. `IntervalBand(lower, upper)` requires ordered nonnegative
integer bounds. `residual_quantile(scores, level)` uses the documented empirical
rank and rejects inadequate support. `make_interval(prediction, quantile)` applies
scaling, clipping and outward rounding. `interval_metrics(actual, bands, level)`
returns inclusive coverage, width, interval score and tail-miss counts. Invalid
values or empty scoring inputs raise `ValueError`.

`evaluate_interval_validation(dataset, split=StudySplit(), *, horizon_hours=168,
spec=IntervalSpec())` compares all four candidates and returns
`stage="interval_validation"`, `test_scored=false`, warmup/calibration evidence,
pooled/fold/group scores and an `interval_selection` manifest. It requires enough
history before the calibration window and enough past residuals at each scored
origin. The point-model selection rule remains pooled validation MAE.

`FrozenIntervalSelection(point, spec=IntervalSpec())` combines a rolling
`FrozenSelection` with the interval policy. `read_interval_selection(path)` reads
only interval-validation reports and rejects unsupported specifications or hash
mismatches. `evaluate_interval_test(dataset, selection)` checks identities and
evaluates only the saved procedure. See [temporal calibration](intervals.md) for
update timing and the absence of theoretical coverage guarantees.

`bike-sharing-intervals` defaults to validation. `--fold-hours` and
`--calibration-folds` configure development studies; the latter counts complete
forecast horizons. `--stage test --selection REPORT` requires a saved interval
report and rejects cadence, calibration and boundary overrides. Point-only
reports cannot authorize interval testing. Data/output flags, input-overwrite
protection and exit status 2 on errors follow the point CLI's contract. Use
`bike-sharing-intervals --help` for all flags.

## Planning API

`bike_sharing.planning.evaluate_planning_validation(dataset, split=StudySplit(),
*, horizon_hours=168)` compares the five fixed policies at all six fixed cost
ratios. It returns per-fold and pooled cost components, calibration metadata and
one selected policy per scenario. The output stage is `planning_validation` and
`test_scored` is false. The default is the same weekly validation study.

`cost_metrics(actual, actions, ratio)` returns mean normalized cost, separate
mean underprediction/excess, mean action and underprediction frequency.
`actual` contains nonnegative integer counts; `actions` contains finite nonnegative
continuous targets. Inputs must have equal nonzero lengths and `ratio` must be
positive and finite. `signed_quantile(scores, ratio)` and
`workload_action(prediction, adjustment)` expose the empirical decision rule.
Invalid support or values raise `ValueError`.

`FrozenPlanningSelection(reference, policies)` binds a rolling Poisson reference
identity to one valid policy for every fixed ratio, in `COST_RATIOS` order.
`read_planning_selection(path)` reads only planning-validation reports and checks
the configuration and hash. `evaluate_planning_test(dataset, selection)` verifies
data/software/model identities and evaluates only the saved scenario policies.
It refits and updates calibration on the saved schedule without reselecting.

`bike-sharing-planning` writes validation JSON by default. `--data` and `--output`
control paths. The explicit `--stage test --selection REPORT` path requires a
saved planning report; cost and cadence overrides are not exposed. Output cannot
overwrite data or the selection. Invalid inputs return status 2. See the
[planning protocol](planning.md) for assumptions and the frozen real test assessment.

## Data audit

`bike_sharing.audit.audit_dataset(path, upstream=None)` validates the historical
14-column schema and returns deterministic coverage and identity evidence. With
a separately supplied UCI `hour.csv`, it reconciles all rows by timestamp and
checks every recovered field relationship. A mismatch raises `ValueError`;
invalid decimal text may raise `decimal.InvalidOperation`.

`python -m bike_sharing.audit --check benchmarks/data-audit.json` verifies the
local evidence offline. Add `--upstream PATH` for the full comparison. The audit
CLI prints JSON and returns status 2 on invalid data or differing evidence.
It never downloads data or computes forecasting metrics. See the
[data audit](data.md) for the distinction between numeric correspondence and
verified historical lineage.
