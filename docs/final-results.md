# Final held-out assessment

The October–December 2012 quarter was scored on 5 October 2026, after the
forecast, interval and planning procedures were frozen. No modelling settings
were changed after inspecting these outcomes. The final dataset contains
**2,168 observed hours and 40 absent hours** across 14 weekly origins, including
a final 24-hour horizon. Missing hours are excluded, never filled with zeros.

Only the selected Poisson point model, its fixed interval rule and the saved
planning policy for each assumed cost ratio were evaluated. Earlier test
observations can enter later scheduled fits and residual windows. This is
sequential assessment of fixed procedures, not a new model-selection exercise.

## Point error

| Period | Hours | MAE | RMSE |
| --- | --- | --- | --- |
| Validation | 2,208 | 53.268 | 83.215 |
| Final test | 2,168 | 61.378 | 95.811 |

MAE and RMSE are in rentals/hour. Errors are larger in the final quarter than
in validation. Seasonal and observation differences mean the change cannot be
attributed to one specific cause from this comparison alone. Final Poisson
deviance is 36.066. No test ranking of the unselected candidates was performed.

## Interval coverage

| Nominal | Validation | Final test | Test width |
| --- | --- | --- | --- |
| 80% | 81.25% | 75.69% | 150.273 |
| 90% | 90.44% | 85.19% | 207.771 |
| 95% | 94.75% | 91.42% | 267.424 |

All nominal levels under-cover. At 90%, there are 249 observations below the
lower bound and 72 above the upper bound. Mean interval score is 404.616.
Coverage is **97.83%** for low, **84.40%** for medium and **74.81%** for high
predicted demand, with 599, 910 and 659 observations respectively. Those groups
were defined before the run. The overall result hides a material weakness at
higher rental levels. No recalibration or subgroup rule was added after this
finding. The full report also includes lead-day and per-fold diagnostics.

These empirical intervals have no universal coverage guarantee. The final
shortfall argues against treating them as reliable conditional service bands.
It does not invalidate the temporal evaluation: an unfavourable frozen result
is evidence that the study was allowed to fail.

## Planning under assumed costs

The same signed-residual Poisson policy was selected in all six validation
scenarios. Only those saved policy choices were scored on test.

| Cost ratio | Validation cost | Test cost | Test target |
| --- | --- | --- | --- |
| 0.25 | 25.385 | 33.017 | 185.639 |
| 0.5 | 36.897 | 45.849 | 205.390 |
| 1 | 52.328 | 62.766 | 229.198 |
| 2 | 71.368 | 81.273 | 253.693 |
| 4 | 90.937 | 102.194 | 275.921 |
| 9 | 115.067 | 127.825 | 301.594 |

Loss is in normalized assumed cost units per observed hour. Mean target is a
continuous rental-equivalent workload allowance. The rows represent different
preferences, not measured operator costs, money or inventory requirements.

At equal costs, the selected adjusted policy has test loss **62.766**, compared
with MAE **61.378** for the independently frozen point procedure. Its small
validation advantage therefore does not persist at that ratio. This comparison
uses the two already-frozen assessments; it does not trigger policy reselection.
At ratio 9, the adjusted target remains below observed rentals in **10.10%** of
test hours. Neither figure establishes operational savings or a guaranteed
service level.

## Interpretation and evidence

The case study demonstrates audited data, explicit forecast-time information,
chronological selection, uncertainty assessment and a transparent decision loss.
It also documents limits: poorer final coverage, a planning advantage that does
not persist at equal costs, one dataset and a historical full-data notebook.
The results alone do not justify deployment, lost-demand estimates, staffing
quantities or station rebalancing.

Read the [two-page decision brief](assets/decision-brief.pdf),
[reproduction instructions](reproduction.md) and
[committed run evidence](https://github.com/DiogoRibeiro7/bike-sharing/tree/master/benchmarks/release-v1).
The earlier [validation results](results.md) remain part of the development
record. This final quarter is now consumed: future method changes require new
assessment data for an independent final claim.
