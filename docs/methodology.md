# Forecasting protocol

## Estimand and information

The target is the observed number of rentals in an hourly aggregate. It is not
unconstrained demand: rental counts alone cannot reveal unserved requests,
station capacity or bike shortages.

At a cutoff `c`, the training set contains observed timestamps strictly before
`c`. Prediction timestamps lie in `[c, c + H hours)`. Both baseline fits remain
frozen for that entire horizon. Outcomes arriving during it never update a model.

Weekday and hour are known from the calendar. Future observed weather is not
assumed known. Casual and registered counts are forbidden predictors because
they sum to the contemporaneous target. The initial implementation does not
use holidays, trend, lags or any weather columns.

## Baselines

The training-mean baseline predicts the arithmetic mean of all training
counts. The hour-of-week baseline predicts the arithmetic mean of training
counts sharing the forecast timestamp's weekday and hour. An unobserved
weekday/hour pair falls back to the global training mean.

These are deliberately transparent reference models. Pooling the entire
training history ignores changing demand levels and seasonal effects beyond
the weekly cycle. Predictions are nonnegative real-valued expectations and
are not rounded before scoring.

## Evaluation

The default selection run fits before 2012-07-01 00:00 and forecasts the entire
validation partition through 2012-09-30 23:00: 2,208 calendar hours.
This is a fixed-origin quarterly comparison, not a rolling day-ahead forecast.
An explicit `--cutoff` requests a shorter validation diagnostic, with a default
168-hour horizon. MAE is the average absolute error; RMSE is the
square root of the average squared error. Both have units of rentals per hour.
Each observed evaluation hour receives equal weight.

Absent calendar hours are not scored or filled. The requested window must fit
inside the observed dataset's overall span and contain at least one outcome.
Missing hours, including gaps at a requested window boundary, are counted
against the entire requested horizon. These are naive calendar counts; the
dataset's timezone and daylight-saving treatment have not been verified.

No random seed is needed: the baselines contain no random steps. The JSON report
records the input checksum, package/Python versions, boundaries, row counts,
features, fallback and missing-hour policies. The same data and software
produce the same report; cross-version floating-point identity is not promised.

## Development and final evaluation

The [three-way workflow](splits.md) separates training, validation and test.
Model selection minimizes validation MAE; ties prefer the training mean. The
real test period is not evaluated during development or CI. Diagnostic windows
must remain within validation, including their end boundary.

Final testing is explicit and requires a saved validation selection. Its model,
boundaries, dataset checksum and package version are frozen. The selected
baseline is refitted on all training and validation observations and held fixed
through the test quarter; only its test errors are reported. Later adaptive or
rolling test protocols will need their own documented selection contract.

These safeguards prevent accidental test use through the development workflow.
They do not prevent deliberate manifest editing, custom code or repeated final
test runs. Once test results are inspected, they must not guide further tuning
while still being presented as an untouched final evaluation.

Before interpreting broader performance, complete the data audit and
rolling-origin comparison in issues #2 and #3. Cost and uncertainty claims
require the later roadmap work.
