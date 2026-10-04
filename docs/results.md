# Baseline results

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
