# Forecast intervals and calibration

The interval study adds empirical uncertainty bands to all four point candidates.
It retains the weekly forecast origins, expanding fits and pooled-MAE selection
rule. These are **prediction intervals for observed hourly rentals**, not
confidence intervals for a mean or estimates of unconstrained demand.

## Temporal separation

For the default first validation origin, the roles are:

| Period | Role |
| --- | --- |
| Before 2012-06-03 | Initial history for the first calibration forecast |
| 2012-06-03 to 2012-07-01 | Four weekly out-of-sample residual blocks for initial calibration |
| 2012-07-01 to 2012-10-01 | Validation forecasts and interval assessment |
| 2012-10-01 to 2013-01-01 | Reserved final evaluation |

Every calibration residual comes from a forecast fitted strictly before its
origin. At a validation origin `c`, calibration uses only residual timestamps in
`[c - 672 hours, c)`. The point model is refitted on all observations before `c`,
and the interval quantiles are frozen for the complete next 168 hours. Once that
horizon has ended, its errors may enter the next calibration window. A shortened
last horizon stops at the validation/test boundary.

Calibration is a separate, trailing **out-of-sample error window**. It is not a
permanently excluded fitting partition: counts from earlier calibration or
validation horizons can enter later expanding point-model fits. Their recorded
residuals always use the forecasts originally issued before those counts were
available. Fitting the current model on a calibration count and then using its
in-sample error would violate this procedure.

## Fixed interval rule

The following choices were set before running this interval benchmark: four
complete forecast horizons of calibration history, levels 0.80/0.90/0.95, at
least 30 observed residuals, square-root scaling and the grouping thresholds
below. No window length, scale or coverage level was selected from interval
results. Point-model design and selection had already used this validation
quarter; the interval evidence is therefore developmental.

For a point prediction `mu`, use `s(mu) = sqrt(max(mu, 1))`. Each previous
out-of-sample observation supplies score `abs(y - mu) / s(mu)`. At level `p`,
sort the `n` calibration scores and take the one-based order statistic
`k = ceil((n + 1) * p)`. The rank uses decimal arithmetic to avoid floating-point
rounding at exact integers. Insufficient observations, including `k > n`, cause
an error; the rank is never silently capped or interpolated.

For the resulting score quantile `q`, the inclusive count bounds are:

```text
lower = floor(max(0, mu - q * s(mu)))
upper = ceil(mu + q * s(mu))
```

Clipping preserves nonnegative support. Rounding goes outward to preserve all
integer counts contained by the unrounded interval. Zero-width bands are allowed
when the errors and predictions permit them. The square-root scale is a fixed
variance-stabilizing heuristic; it does not impose a Poisson observation law.
The residual distribution, rather than a fitted Poisson distribution, supplies
the radius. The rule is symmetric before clipping and can handle skewness poorly.

Missing hours supply neither residuals nor scores and are never filled with zero.
The report records gaps in warmup and evaluation folds. A completely empty
evaluation fold is recorded without forecasting; the next nonempty fold must
still satisfy calibration support. Data must include fitting observations before
the first calibration origin. With a custom horizon `H`, the default window is
`4 * H` hours, not necessarily four weeks.

## What is measured

Each level reports inclusive empirical coverage, mean width, mean interval score
and counts below/above the bounds. For nominal miscoverage `alpha = 1 - p`, the
interval score for observation `y` and bounds `[l, u]` is:

```text
(u - l) + 2 / alpha * (max(l - y, 0) + max(y - u, 0))
```

Lower scores are better: width penalizes excessively broad intervals and missed
observations incur a distance penalty. This is the interval score described by
[Gneiting and Raftery (2007)](https://doi.org/10.1198/016214506000001437).
Coverage alone is insufficient because broad bands can cover almost everything.

Metrics pool observed hours, with separate summaries by forecast lead day and
predicted rental level. Day `d` contains elapsed calendar hours
`[24*(d-1), 24*d)` after the origin; gaps never shift this assignment. Fixed
prediction-based groups are low (`mu < 100`), medium (`100 <= mu < 300`) and high
(`mu >= 300`). These descriptive thresholds are not fitted or based on future
outcomes. Group sizes are reported; empty groups are omitted. Grouping does not
change the interval rule and does not establish conditional coverage.

## Assumptions and limitations

Recent standardized errors must be informative about the next horizon for this
rule to work well. Serial dependence, seasonality, holidays, omitted weather,
changing model fits and demand shifts can break that approximation. A single
four-week pooled quantile also hides differences by lead time and demand level.
Observed coverage should be inspected alongside width and tail imbalance.

**There is no finite-sample or universal coverage guarantee.** The empirical
rank adjustment does not make these changing-model, dependent residuals
exchangeable. This is neither split conformal prediction nor EnbPI.
[Xu and Xie (2021)](https://proceedings.mlr.press/v139/xu21h.html) develop a distinct
time-series interval method with assumptions and theoretical results; those
results do not transfer to this implementation.

All four candidates are reported. The point candidate is still selected only by
pooled validation MAE. Coverage for that chosen candidate is a **post-selection
validation diagnostic**, not independent evidence of calibrated deployment
performance. No binomial independence-based confidence bands or significance
claims are attached to these dependent hourly indicators. Only one summer/early
autumn quarter is assessed. Rental intervals do not estimate lost rentals,
station capacity or the distribution of unconstrained demand.

## Reproduction and final evaluation

```bash
poetry run bike-sharing-intervals --output results/interval-validation.json
```

The [committed report](https://github.com/DiogoRibeiro7/bike-sharing/blob/master/benchmarks/interval-validation-2012-q3.json)
contains warmup origins, each calibration window, counts and quantiles, all
fold/pooled/grouped scores, source/software identities and the frozen point and
interval specification. [Recorded results](results.md#empirical-forecast-intervals)
summarize the evidence. CI reproduces this validation report and checks known
synthetic scores, constant-series behavior, gap handling and invariance of
predictions to current/future outcomes.

Only after all development, including the planning study, is complete:

```bash
poetry run bike-sharing-intervals --stage test \
  --selection results/interval-validation.json --output results/interval-test.json
```

This explicit command evaluates only the saved point model and interval policy.
The data checksum, package version, point-configuration hash and interval hash
must match. Test-time boundary/cadence/calibration overrides are rejected.
Before the first test origin, calibration forecasts are replayed over the four
preceding horizons aligned to that origin, using only earlier data. They need
not share the validation-origin grid. At subsequent test origins, earlier test
counts may update fits and calibration on the saved schedule. No model or method
is reselected. This is sequential testing of a frozen procedure.

The frozen real test assessment is now recorded in [final results](final-results.md),
including interval undercoverage. Synthetic data still checks the final-test
contract; replays verify the existing result without creating a new holdout. The version 0.3.0 point benchmark is retained unchanged; version
0.4.0 reproduces its point metrics and protocol, with updated package metadata.
Old selections need a fresh validation run under the current package before
final testing.
