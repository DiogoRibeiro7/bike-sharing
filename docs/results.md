# Validation results

## Weekly expanding-window comparison

Package 0.3.0 compares four pre-specified candidates across July–September 2012:
13 full 168-hour folds and a final 24-hour fold, covering all **2,208 observed
hours** with no gaps. The first fit uses 13,003 observations before July;
later fits also use earlier validation observations. October–December is unscored.

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
naive can also repeat an unusual previous week. Neither method produces calibrated
intervals, estimates lost rentals or establishes operational savings.

The Poisson log-linear time term can extrapolate poorly, and the validation
quarter covers only one part of the annual cycle. Model choice remains provisional until the
uncertainty/planning work is frozen and one final test is run. The historical
notebook's full-data exploration also prevents a claim that nobody has ever
looked at these outcomes.

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
