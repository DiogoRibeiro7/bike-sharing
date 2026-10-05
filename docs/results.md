# Validation results

## Weekly expanding-window comparison

Package 0.3.0 compares four pre-specified candidates across July–September 2012:
13 full 168-hour folds and a final 24-hour fold, covering all **2,208 observed
hours** with no gaps. The first fit uses 13,003 observations before July;
later fits also use earlier validation observations. October–December was
unscored during selection; see the subsequent
[final assessment](final-results.md).

| Model | MAE | RMSE | Mean Poisson deviance | Fit + predict seconds |
| --- | ---: | ---: | ---: | ---: |
| Training mean | 195.665 | 256.864 | 257.409 | 0.024 |
| Hour-of-week mean | 119.397 | 160.396 | 77.291 | 0.057 |
| Seasonal-naive | 55.998 | 97.892 | 30.522 | 0.028 |
| Poisson calendar | 53.268 | 83.215 | 20.718 | 2.239 |

MAE and RMSE are in rentals/hour. The selected model is **Poisson calendar**,
according to pooled validation MAE. Its MAE is about 4.9% below seasonal-naive.
The [committed report](https://github.com/DiogoRibeiro7/bike-sharing/blob/master/benchmarks/rolling-validation-2012-q3.json)
contains full precision, each fold's training coverage and coefficients, dependency
versions, timing and the frozen selection. The configuration was set before this
run and was not tuned to make Poisson win.

```bash
poetry run bike-sharing --output results/validation.json
```

Times are measured fit/predict wall time from one run, excluding loading and
scoring; they are machine-dependent. The numerical benchmark is checked in CI,
with tolerance for floating-point differences. Timing is not part of that gate.

## Per-fold MAE and failure cases

| Origin | Training mean | Hour-of-week mean | Seasonal-naive | Poisson calendar |
| --- | ---: | ---: | ---: | ---: |
| 2012-07-01 | 164.513 | 98.371 | 66.887 | 86.056 |
| 2012-07-08 | 188.043 | 114.708 | 78.107 | 56.757 |
| 2012-07-15 | 163.943 | 88.305 | 64.435 | 67.420 |
| 2012-07-22 | 202.964 | 131.051 | 61.065 | 43.208 |
| 2012-07-29 | 198.501 | 124.804 | 28.113 | 39.564 |
| 2012-08-05 | 186.757 | 111.425 | 37.292 | 47.478 |
| 2012-08-12 | 205.103 | 125.966 | 43.042 | 35.191 |
| 2012-08-19 | 184.076 | 111.973 | 54.929 | 47.027 |
| 2012-08-26 | 195.155 | 113.746 | 44.417 | 46.468 |
| 2012-09-02 | 185.659 | 109.409 | 74.232 | 65.520 |
| 2012-09-09 | 232.970 | 153.428 | 81.792 | 51.257 |
| 2012-09-16 | 207.907 | 128.469 | 48.119 | 55.283 |
| 2012-09-23 | 226.006 | 141.286 | 46.851 | 50.726 |
| 2012-09-30 | 210.042 | 113.930 | 46.833 | 56.931 |

September 30 is the 24-hour final fold. Seasonal-naive has lower MAE than Poisson
in **8 of the 14 folds**, including that shorter fold. It is a close alternative,
not a uniformly inferior model. Poisson's advantage is in pooled hourly loss,
not the number of folds won; no significance claim is made from these dependent
folds.

Poisson's largest fold MAE occurs at the July 1 origin, where it underperforms
seasonal-naive. This calendar model omits holiday effects, weather and disruptions;
these are limitations, not established causes of a particular residual. Seasonal
naive can also repeat an unusual previous week. Point forecasts alone do not
quantify uncertainty; the empirical interval extension below assesses forecast
error without estimating lost rentals or establishing operational savings.

The Poisson log-linear time term can extrapolate poorly, and the validation
quarter covers only one part of the annual cycle. Model choice was frozen before the final
assessment; the reported held-out evidence does not establish operational readiness. The historical
notebook's full-data exploration also prevents a claim that nobody has ever
looked at these outcomes.

## Empirical forecast intervals

Package 0.4.0 applies the pre-specified [residual-calibration rule](intervals.md)
to the same 2,208 validation hours. Initial calibration uses June 3–July 1;
each subsequent origin uses only the previous 672 hours of out-of-sample errors.
All three levels and all four candidates are recorded. Point forecasts and MAE
selection reproduce the 0.3.0 comparison; Poisson calendar remains selected.

| Model | Nominal | Coverage | Mean width | Mean interval score |
| --- | ---: | ---: | ---: | ---: |
| Training mean | 80% | 79.48% | 480.522 | 832.551 |
| Training mean | 90% | 89.45% | 622.478 | 906.011 |
| Training mean | 95% | 94.52% | 740.717 | 935.065 |
| Hour-of-week mean | 80% | 79.89% | 289.744 | 420.867 |
| Hour-of-week mean | 90% | 89.31% | 340.162 | 455.380 |
| Hour-of-week mean | 95% | 94.38% | 375.185 | 476.127 |
| Seasonal-naive | 80% | 80.16% | 148.610 | 332.726 |
| Seasonal-naive | 90% | 89.13% | 239.502 | 467.428 |
| Seasonal-naive | 95% | 93.93% | 343.204 | 607.479 |
| Poisson calendar | 80% | 81.25% | 147.343 | 262.818 |
| Poisson calendar | 90% | 90.44% | 204.579 | 345.376 |
| Poisson calendar | 95% | 94.75% | 273.525 | 438.924 |

Widths are in hourly rental counts; lower interval scores are better. These
figures include clipping at zero and outward integer rounding. Pooled coverage
is close to the nominal levels, but it does not establish conditional calibration.
At 90%, Poisson misses **161 observations below** the lower bound and **50 above**
the upper bound: the misses are not balanced between tails.

### Selected model by predicted demand

The following Poisson summaries use the nominal 90% level. Groups use predictions
known at forecast time, not realized rentals.

| Predicted rentals/hour | Hours | Coverage | Mean width | Mean interval score |
| --- | ---: | ---: | ---: | ---: |
| Below 100 | 500 | 99.20% | 72.044 | 75.124 |
| 100 to below 300 | 679 | 90.13% | 182.689 | 260.303 |
| 300 or more | 1,029 | 86.39% | 283.424 | 532.831 |

Low predicted demand is overcovered at 99.2%, while high predicted demand has
only 86.4% coverage. The pooled square-root scaling leaves substantial variation
across rental levels. No regime-specific recalibration was added after seeing
these results.

### Selected model by forecast lead

| Lead day | Hours | Coverage at 90% | Mean width | Mean interval score |
| --- | ---: | ---: | ---: | ---: |
| 1 | 336 | 86.61% | 200.848 | 403.051 |
| 2 | 312 | 90.71% | 201.487 | 338.218 |
| 3 | 312 | 91.67% | 206.138 | 329.279 |
| 4 | 312 | 89.42% | 203.038 | 375.218 |
| 5 | 312 | 94.87% | 207.622 | 253.647 |
| 6 | 312 | 94.55% | 207.442 | 295.647 |
| 7 | 312 | 85.58% | 205.766 | 418.138 |

Day 1 includes the short final fold. Because every full horizon starts on Sunday,
lead day is confounded with weekday in this study; these figures cannot isolate
a causal effect of forecast distance. Coverage ranges from 85.6% to 94.9% and
does not decline monotonically with lead time.

The [complete interval report](https://github.com/DiogoRibeiro7/bike-sharing/blob/master/benchmarks/interval-validation-2012-q3.json)
contains every fold, calibration quantile and group at every level, together with
the frozen procedure. Reproduce it with:

```bash
poetry run bike-sharing-intervals --output results/interval-validation.json
```

These are dependent, post-selection validation diagnostics from one quarter.
No exchangeability, universal coverage or independent final-evidence claim is
made. Choices were frozen before the now-recorded [final assessment](final-results.md).
See the [method and limitations](intervals.md).

## Asymmetric-cost planning

The [planning study](planning.md) reports five policies at six assumed cost ratios
on the same validation quarter. The signed-residual Poisson policy is selected
at every ratio. At equal costs, mean loss is 52.328 versus 53.268 for the point
forecast; at ratio 9, it is 115.067 versus 215.418. Higher targets trade less
underprediction for more excess. These are assumed proxy losses, not financial
savings, and are selected on validation. The planning report preserves per-fold
costs and all selected procedures; the separate [final assessment](final-results.md)
is now recorded.

## Historical fixed-origin results

The following 0.2.0 result uses the same 2,208 validation observations but fits
only once before July. It answers a different forecast question from weekly
refitting and is preserved as historical evidence.

| Model | MAE | RMSE |
| --- | ---: | ---: |
| Training mean | 197.829 | 260.650 |
| Hour-of-week mean | 126.621 | 169.783 |

The original report remains in `benchmarks/validation-2012-q3.json`.
To reproduce its numerical metrics under the current version:

```bash
poetry run bike-sharing --protocol fixed --output results/fixed-validation.json
```

Package and selection-schema metadata differ after the upgrade. The earlier
one-week diagnostic remains in `benchmarks/baseline-2012-07-01.json`: MAE
164.513 for the training mean and 98.371 for the hour-of-week mean.
