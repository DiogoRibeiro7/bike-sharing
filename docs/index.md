# Bike Sharing Forecasting

This case study develops a reproducible workflow for forecasting aggregate
hourly rentals and evaluating the decisions those forecasts might support.

The maintained implementation compares four interpretable candidates using weekly
expanding-window validation, while reserving a final temporal test. Data provenance,
per-fold errors, coefficient diagnostics and source identities are recorded.
Empirical prediction intervals use only past out-of-sample errors for calibration,
with coverage, width and interval-score diagnostics.
Everything needed for the run is local after installation.

```bash
poetry install --with dev,docs
poetry run bike-sharing --output results/validation.json
poetry run bike-sharing-intervals --output results/interval-validation.json
poetry run mkdocs serve
```

Read the [three-way workflow](splits.md) and [forecasting protocol](methodology.md) before interpreting the
[baseline results](results.md). The [data contract](data.md) describes verified
properties, row-level UCI reconciliation and remaining provenance limitations.
The [candidate specification](models.md) explains the statistical models.
The [interval study](intervals.md) explains calibration, count bounds and why
aggregate coverage does not imply reliable coverage in every demand regime.
The [API](api.md) documents the Python interfaces. The [legacy audit](legacy-audit.md) explains the original notebook's
evaluation limitations.

The [six-issue roadmap](https://github.com/DiogoRibeiro7/bike-sharing/issues)
ends with a small benchmark, uncertainty analysis, one planning study and a
LaTeX decision brief. Hosted documentation is planned in issue #6; no live site
is claimed yet.
