# Bike Sharing Forecasting

Reproducible forecasting of aggregate hourly bike rentals, with explicit
forecast-time information and chronological evaluation.

This project is being modernized from a 2020 exploratory notebook into a small
statistical case study. The maintained implementation provides a typed
CSV loader, two transparent calendar baselines, a three-way temporal split,
validation-only selection and explicit final testing. Broader model comparison, uncertainty and planning-cost evaluation
are tracked in the [roadmap](ROADMAP.md).

## Run the baseline

Use **Python 3.12** and **Poetry 2.5.1** from the repository root:

```bash
poetry install --with dev,docs
poetry run bike-sharing --output results/validation.json
```

The runtime package uses only the Python standard library. The bundled CSV is
read locally; the analysis makes no network requests. The CSV is repository
data and is not included in the Python wheel.

The default study enforces these half-open calendar partitions:

| Partition | Period | Role |
| --- | --- | --- |
| Training | Before July 2012 | Fit the candidate baselines |
| Validation | July through September 2012 | Select the candidate with the lowest MAE |
| Test | October through December 2012 | Final evaluation after model choice is frozen |

The default command compares both baselines on all **2,208 validation hours**.
It saves the selected model, dataset checksum, split boundaries and package
version in the validation report. No test performance is computed. Ties prefer
the simpler training-mean baseline. Both candidate fits are frozen at July 1;
rolling-origin comparisons remain planned work.

For a shorter diagnostic within validation:

```bash
poetry run bike-sharing --data bike.csv \
  --cutoff 2012-07-01 --horizon-hours 168 --output results/baseline.json
```

Diagnostic windows cannot enter the test period and do not create model-selection
artifacts. Once the modelling approach is finalized, a separate command refits
the saved model on training plus validation and scores only that model on test:

```bash
poetry run bike-sharing --stage test --selection results/validation.json \
  --output results/final-test.json
```

That command requires matching data and package versions and rejects boundary
overrides. **The real test period has not been scored in this modernization.**
The final-test path is checked with synthetic data in CI. See the
[three-way workflow](docs/splits.md), [methods](docs/methodology.md) and
[recorded validation results](docs/results.md).

Across July–September, the hour-of-week baseline produces MAE **126.621** and
RMSE **169.783** rentals/hour; the training mean produces MAE **197.829** and RMSE
**260.650**. These validation results select a baseline, not a deployment model.

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
