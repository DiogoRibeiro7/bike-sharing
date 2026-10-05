# Forecasting protocol

## Target and available information

The target is the observed aggregate rental count at each recorded hourly
calendar timestamp. It is not unconstrained demand, unserved requests or station
inventory. At origin `c`, fitting uses only observed timestamps strictly before
`c`. Predictions cover `[c, c + H hours)` and remain fixed over that horizon.

Calendar timestamps are known ahead of time. The seasonal-naive model also
uses rental counts from the calendar week preceding the origin. Future observed
weather, casual/registered component counts and observations arriving inside
the forecast horizon are excluded. No data-fitted preprocessing sees future
rows. Feature definitions and model parameters are documented in
[the candidate specification](models.md).

## Rolling validation

The default command compares four candidates on July–September 2012 using
expanding training histories and disjoint 168-hour horizons. Origins start at
2012-07-01 and advance by 168 hours. A final 24-hour fold on September 30 includes
the remainder: **14 folds and 2,208 scored observations**. Every origin and its
training coverage appear in the saved report.

At each new origin, earlier validation observations have become available and
may join training. Outcomes within the current horizon cannot enter its fit.
The model configurations remain fixed throughout. There is no hyperparameter
search, future-weather experiment or test-driven choice.

The selected candidate has the lowest **pooled validation MAE**. Each observed
hour receives equal weight, including the short final fold. Exact ties follow
this fixed order: training mean, hour-of-week mean, seasonal-naive, Poisson.

## Metrics and missing hours

MAE is mean absolute error; RMSE is the square root of mean squared error, both
in rentals/hour. Aggregate RMSE is calculated from all squared errors, rather
than by averaging fold RMSEs.

Mean Poisson deviance adds a count-appropriate comparison. Each observation
contributes `2 * (y * log(y / mean) - y + mean)`, with the logarithmic term zero
when `y=0`. Predictions are floored at `1e-9` **for deviance only**. This gives
finite, explicitly floor-dependent penalties when a baseline predicts zero;
MAE/RMSE use the original predictions. Selection uses MAE, not this auxiliary
metric. Deviance does not assert that the observed process is Poisson.

The [interval procedure](intervals.md) adds rolling calibration from past
out-of-sample forecast errors. Its coverage, width and interval score are reported
separately; they do not change the pooled-MAE point-model selection rule.

Missing timestamps remain absent and are excluded from scoring, never filled
with zero rentals. A completely empty fold is recorded as `no_observations`,
with no fit or score; its entire horizon contributes to gap accounting. An
entirely empty evaluation period is rejected. No such empty folds occur in the
recorded validation quarter. All calendar arithmetic is timezone-naive because
source timezone/daylight-saving aggregation remains unresolved.

## Frozen selection and final testing

The [three-way split](splits.md) reserves October–December. The validation
artifact binds model, dataset checksum, package version, split boundaries,
protocol, forecast horizon/refit cadence and a hash of the fixed configuration.
Only the selected model is evaluated by the explicit test command.

For rolling selections, final testing repeats the same expanding-window policy.
The first fit uses training plus validation; later scheduled test origins can
use earlier test observations that are then available. Model identity, feature
set, penalty and cadence remain frozen. This is sequential out-of-sample
assessment of a fixed forecasting procedure, not a single quarter-ahead forecast.
Changing the procedure after seeing test errors would consume the holdout.

The real test quarter remains **unscored** in modernization and CI. Synthetic
data checks the final-test implementation. Editable JSON and public functions
are safeguards against accidental misuse, not evidence that a human has never
inspected those outcomes.

## Historical fixed-origin mode

`--protocol fixed` retains the original two-mean comparison, trained before
July and frozen for the entire validation quarter. Its saved selection keeps
that same whole-quarter behavior at final testing. `--cutoff` with
`--horizon-hours` produces a validation-only diagnostic without a selection.

These answer different forecast questions from weekly refitting. The historical
0.1/0.2 reports are preserved and must not be ranked directly against the rolling
results as if horizon and update policy were identical.

## Reproducibility and runtime

Reports include data identity, package/dependency versions, model settings,
fold-level metrics, fit diagnostics and pooled metrics. There are no random
steps. Numerical results are regression-checked with a small floating-point
tolerance; cross-platform bit identity is not required.

Per-model runtime measures feature construction, fitting and prediction inside
each fold. It excludes data loading, partition construction, scoring and process
startup. Timings vary with hardware and load, and are not asserted in tests or
used for selection. This is one measured run, not a hardware speed benchmark.
