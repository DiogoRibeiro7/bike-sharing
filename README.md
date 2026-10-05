# Bike Sharing Forecasting

Reproducible forecasting of aggregate hourly bike rentals, with explicit
forecast-time information and chronological evaluation.

This project is being modernized from a 2020 exploratory notebook into a small
statistical case study. It provides a typed CSV loader, four interpretable
forecasting candidates, a verified data audit and chronological model selection.
Empirical forecast intervals include temporal calibration and coverage diagnostics.
An asymmetric-cost study connects forecasts to an explicit workload decision.
The frozen final assessment and a LaTeX decision brief are complete. Publication
of the documentation site and v1.0 release is prepared for reviewed `master`;
see the [roadmap](ROADMAP.md) for the remaining publication check.

## Final findings and reproduction

The frozen October–December assessment covers **2,168 observed hours** and
40 missing hours. Poisson MAE is **61.378 rentals/hour**. Nominal 90% interval
coverage falls to **85.19% overall** and **74.81% at high predicted demand**.
At equal planning costs, the adjusted policy's final loss is **62.766**, so its
small validation advantage over the point forecast does not persist. These
results do not establish operational readiness or financial savings.

Read the [final assessment](docs/final-results.md) and
[two-page decision brief](docs/assets/decision-brief.pdf).
To verify the saved procedures after installing the locked environment:

```bash
poetry run python scripts/reproduce_release.py
```

The [reproduction guide](docs/reproduction.md) covers the source/selection hashes,
LaTeX tables, documentation and release workflow. This test quarter is now
consumed; a replay is a reproducibility check, not a fresh holdout.

## Run the validation study

Use **Python 3.12** and **Poetry 2.5.1** from the repository root:

```bash
poetry install --with dev,docs
poetry run bike-sharing --output results/validation.json
```

Poetry locks NumPy, scikit-learn and the numerical dependencies. The bundled CSV
is read locally; the analysis makes no network requests. The CSV is repository
data and is not included in the Python wheel.

The default study enforces these half-open calendar partitions:

| Partition | Period | Role |
| --- | --- | --- |
| Training | Before July 2012 | Initial fitting history |
| Validation | July through September 2012 | Weekly comparisons and selection by pooled MAE |
| Test | October through December 2012 | Final evaluation after model choice is frozen |

The default compares four candidates on **14 expanding-window folds**, covering
all **2,208 validation hours**. Each fit uses only observations before its origin;
forecasts stay fixed for 168 hours, with a final 24-hour fold. Earlier validation
observations can enter later training histories once available.

The report saves the selected model, data checksum, boundaries, model-configuration
hash, package version and refit cadence. No test performance is computed.
The original two-mean, whole-quarter comparison is available with `--protocol fixed`.

For a shorter diagnostic within validation:

```bash
poetry run bike-sharing --data bike.csv \
  --cutoff 2012-07-01 --horizon-hours 168 --output results/baseline.json
```

Diagnostics compare the original two means, remain within validation and do not
create selections. Once development is complete, a separate command evaluates
only the selected model using its saved forecasting and refit procedure:

```bash
poetry run bike-sharing --stage test --selection results/validation.json \
  --output results/final-test.json
```

That command requires matching data, package and configuration identities and
rejects protocol, cadence and boundary overrides. **The frozen final assessment
is now recorded**, with no retuning after inspecting the test quarter. CI checks
synthetic contracts and reproduces the recorded final evidence. See the
[three-way workflow](docs/splits.md), [methods](docs/methodology.md) and
[recorded validation results](docs/results.md).

The current rolling comparison selects **Poisson calendar**, with MAE **53.268**
and RMSE **83.215** rentals/hour. Seasonal-naive gives MAE **55.998** and wins in
8 of the 14 individual folds. These are validation results, not deployment or
final-test evidence. See [per-fold results and limitations](docs/results.md).

## Evaluate forecast intervals

```bash
poetry run bike-sharing-intervals --output results/interval-validation.json
```

Intervals at 80%, 90% and 95% use the preceding four weeks of out-of-sample
forecast errors. Calibration updates only after each forecast horizon ends.
The report includes coverage, width and interval score by forecast lead and
predicted rental level, with nonnegative integer bounds.

Poisson's nominal 90% intervals cover **90.4%** of validation observations with
mean width **204.6 rentals**, but only **86.4%** in the high predicted-demand
group. Aggregate coverage hides meaningful weaknesses. These are empirical,
post-selection diagnostics with no guaranteed coverage under temporal dependence
or demand shifts. See the [interval method](docs/intervals.md) and
[complete validation evidence](docs/results.md#empirical-forecast-intervals).
This validation command does not score test outcomes; the separate frozen final
assessment is now recorded.

## Compare planning policies

```bash
poetry run bike-sharing-planning --output results/planning-validation.json
```

The decision is a continuous hourly workload target measured in rental-equivalent
units. Six assumed under/overprediction cost ratios compare the four point
policies with a Poisson policy adjusted by past signed residual quantiles.
The latter has the lowest validation cost in all six scenarios: at ratio 9,
mean normalized loss is **115.067**, versus **215.418** for the Poisson point
policy. These are scenario losses, not realised savings. Costs are assumed;
aggregate rentals cannot substantiate staffing, inventory or station rebalancing
recommendations. See the [planning method and sensitivity tables](docs/planning.md).
Policy selection uses validation only, and each scenario's choice is saved for
the explicit final assessment.

## Forecasting candidates

| Model | Prediction and training information |
| --- | --- |
| Training mean | Mean of all available training counts |
| Hour-of-week mean | Training mean for each weekday/hour; global fallback |
| Seasonal-naive | Repeat the last observed calendar week; missing lag uses training mean |
| Poisson calendar | Penalized log-link regression with hour, weekday, weekend interactions, annual harmonics and trend |

The [model specification](docs/models.md) explains features, fixed settings and
coefficient interpretation. No candidate uses future observed weather or the
casual/registered counts that reveal the contemporaneous target. Missing hours
are counted and excluded from scoring, never converted into zero rentals.

## Data and interpretation

The historical `bike.csv` contains **17,379 observations** from 2011-01-01 to
2012-12-31, with **165 absent hours** relative to a naive hourly calendar.
The maintained loader validates count totals and timestamps, sorts records and
rejects duplicates. Its field contract is documented in [data](docs/data.md).

A [reproducible audit](docs/data.md) matches every timestamp and rental count
to UCI’s hourly Bike Sharing dataset and explains every local field numerically.
It records upstream CC BY 4.0 attribution, month-based season coding and a
legacy temperature rescaling. The intermediary history, physical temperature
interpretation, wind-speed unit and timezone remain unresolved.

Verify the committed local evidence without network access:

```bash
poetry run python -m bike_sharing.audit --check benchmarks/data-audit.json
```

Observed rentals do not identify unconstrained demand, lost rentals or station
inventory. The planning study labels its cost assumptions and proxy decision explicitly.

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

- [Documentation](docs/index.md): methodology, data, API and validation results.
- [Roadmap](ROADMAP.md): six issues defining the v1.0 completion boundary.
- [Historical notebook audit](docs/legacy-audit.md): why old model scores are not
  evidence for the maintained forecasting protocol.

The original notebook and CSV are retained unchanged for provenance. The
notebook is outside the maintained package, lint and execution checks.

## License

Software: Apache License 2.0; see [LICENSE](LICENSE).
Data: UCI source attribution, CC BY 4.0 terms and derivative qualifications are
recorded in [DATA_LICENSE.md](DATA_LICENSE.md).
