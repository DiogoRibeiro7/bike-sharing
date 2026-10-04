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

The default cutoff is 2012-07-01 00:00 and the horizon is 168 calendar hours.
This is one fixed-origin weekly diagnostic, not seven daily refits and not
rolling one-step evaluation. MAE is the average absolute error; RMSE is the
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

The July run is a development diagnostic selected to exercise the workflow. It
is not used to claim a universally best model. Upcoming model selection and
calibration use earlier temporal folds, with the final quarter of 2012 reserved
for the final study. The CLI permits other periods, so maintaining that holdout
is a study-governance rule rather than an enforced software boundary.

Before interpreting broader performance, complete the data audit and
rolling-origin comparison in issues #2 and #3. Cost and uncertainty claims
require the later roadmap work.
