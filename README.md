# Bike Sharing Forecasting

Reproducible forecasting of aggregate hourly bike rentals, with explicit
forecast-time information and chronological evaluation.

This project is being modernized from a 2020 exploratory notebook into a small
statistical case study. The first maintained release candidate provides a typed
CSV loader, two transparent calendar baselines, a command-line report and
automated checks. Model comparison, uncertainty and planning-cost evaluation
are tracked in the [roadmap](ROADMAP.md).

## Run the baseline

Use **Python 3.12** and **Poetry 2.5.1** from the repository root:

```bash
poetry install --with dev,docs
poetry run bike-sharing --output results/baseline.json
```

The runtime package uses only the Python standard library. The bundled CSV is
read locally; the analysis makes no network requests. The CSV is repository
data and is not included in the Python wheel.

The default study trains on observations before **2012-07-01 00:00**, then makes
one frozen forecast for the next **168 calendar hours**. Only weekday and hour
are used. The report includes MAE, RMSE, the input SHA-256, software versions,
split boundaries and missing-hour counts.

```bash
poetry run bike-sharing --data bike.csv \
  --cutoff 2012-07-01 --horizon-hours 168 --output results/baseline.json
```

The initial run is a development diagnostic. It is not a rolling day-ahead
benchmark or a claim of deployment readiness. The final quarter of 2012 is
reserved by the study plan for subsequent final evaluation; the general CLI
does not enforce that research policy. See [methods](docs/methodology.md) and
[recorded results](docs/results.md).

In this 168-observation diagnostic, the hour-of-week baseline produces MAE
**98.371** and RMSE **134.834** rentals/hour; the constant training mean produces
MAE **164.513** and RMSE **205.256**. These are measured results for one development
week, with broader validation still on the roadmap.

## What the models do

| Baseline | Prediction | Training information |
| --- | --- | --- |
| Training mean | One constant rental count | Mean of all training counts |
| Hour-of-week mean | Mean for the forecast weekday/hour | Matching training hours; global mean for an unseen pair |

Neither model uses future weather or the contemporaneous casual/registered
counts that sum to the target. Missing timestamps are reported and excluded
from scoring, never converted into zero rentals.

## Data and interpretation

The historical `bike.csv` contains **17,379 observations** from 2011-01-01 to
2012-12-31, with **165 absent hours** relative to a naive hourly calendar.
The maintained loader validates count totals and timestamps, sorts records and
rejects duplicates. Its field contract is documented in [data](docs/data.md).

The exact upstream source, derivative transformations, timezone and data
redistribution terms still require the [provenance audit](https://github.com/DiogoRibeiro7/bike-sharing/issues/2).
The software license does not establish a separate data license.

Observed rentals do not identify unconstrained demand, lost rentals or station
inventory. Future planning studies will label cost assumptions explicitly.

## Development

```bash
poetry check --lock
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy
poetry run pytest --cov=bike_sharing --cov-report=term-missing
poetry run mkdocs build --strict
poetry build
```

Tests check known numerical results, temporal boundaries, malformed data,
missing hours and invariance of predictions to held-out outcomes.

Install local commit checks with `poetry run pre-commit install`.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the pull-request workflow.

## Documentation and history

- [Documentation](docs/index.md): methodology, data, API and baseline results.
- [Roadmap](ROADMAP.md): six issues defining the v1.0 completion boundary.
- [Historical notebook audit](docs/legacy-audit.md): why old model scores are not
  evidence for the maintained forecasting protocol.

The original notebook and CSV are retained unchanged for provenance. The
notebook is outside the maintained package, lint and execution checks.

## License

Software: Apache License 2.0; see [LICENSE](LICENSE).
