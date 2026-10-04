# Baseline results

## Full validation partition

Package 0.2.0 compares both baselines across all 2,208 observed validation hours
from July through September 2012, using 13,003 training observations before July.
There are no absent calendar hours in validation. Both models remain frozen
throughout that quarter.

| Model | Validation MAE (rentals/hour) | Validation RMSE (rentals/hour) |
| --- | ---: | ---: |
| Training mean | 197.829 | 260.650 |
| Hour-of-week mean | 126.621 | 169.783 |

The hour-of-week mean is selected by validation MAE. The exact report and frozen
selection are committed in `benchmarks/validation-2012-q3.json`.

```bash
poetry run bike-sharing --output results/validation.json
```

These are selection results, not final-test results. October–December remains
unscored. Both candidates are basic calendar models; further models and
rolling-origin validation are still on the roadmap.

## Historical one-week diagnostic

The initial fixed-origin development run uses all observations before
2012-07-01 and forecasts the next 168 calendar hours. Its generated JSON report
is recorded in `benchmarks/baseline-2012-07-01.json` at the repository root.

```bash
poetry run bike-sharing --cutoff 2012-07-01 --horizon-hours 168 \
  --output results/baseline.json
```

The verified run uses 13,003 training observations and 168 evaluation
observations, with no absent calendar hours in the evaluation window.

| Model | MAE (rentals/hour) | RMSE (rentals/hour) |
| --- | ---: | ---: |
| Training mean | 164.513 | 205.256 |
| Hour-of-week mean | 98.371 | 134.834 |

The weekly profile captures part of the calendar pattern and has lower errors
on this particular week. These numbers were generated with package 0.1.0 and
Python 3.12.14. The committed JSON retains full precision, the data checksum,
boundaries and protocol settings. The software commit containing that artifact
identifies the exact implementation used.

One week cannot establish performance over an entire year. These baselines
ignore evolving demand, weather and seasonality beyond the weekly calendar.
The comparison supports workflow validation; it does not establish operational
savings or a recommended deployment model.
