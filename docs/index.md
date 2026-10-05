# Bike Sharing Forecasting

This case study develops a reproducible workflow for forecasting aggregate
hourly rentals and evaluating the decisions those forecasts might support.

The maintained implementation compares four interpretable candidates using weekly
expanding-window validation, with a separately frozen final temporal test. Data provenance,
per-fold errors, coefficient diagnostics and source identities are recorded.
Empirical prediction intervals use only past out-of-sample errors for calibration,
with coverage, width and interval-score diagnostics. An asymmetric-cost planning
study compares workload policies across explicit assumed cost scenarios.
Everything needed for the run is local after installation.

```bash
poetry install --with dev,docs
poetry run bike-sharing --output results/validation.json
poetry run bike-sharing-intervals --output results/interval-validation.json
poetry run bike-sharing-planning --output results/planning-validation.json
poetry run mkdocs serve
```

Read the [three-way workflow](splits.md) and [forecasting protocol](methodology.md) before interpreting the
[baseline results](results.md). The [data contract](data.md) describes verified
properties, row-level UCI reconciliation and remaining provenance limitations.
The [candidate specification](models.md) explains the statistical models.
The [interval study](intervals.md) explains calibration, count bounds and why
aggregate coverage does not imply reliable coverage in every demand regime.
The [planning study](planning.md) connects forecast uncertainty to a decision and
documents the gap between proxy losses and operational evidence.
The [API](api.md) documents the Python interfaces. The [legacy audit](legacy-audit.md) explains the original notebook's
evaluation limitations.

The [final assessment](final-results.md) reports increased point error, interval
undercoverage and a planning advantage that does not persist at equal costs.
Read the [decision brief](assets/decision-brief.pdf) for the stakeholder summary.

The [six-issue roadmap](https://github.com/DiogoRibeiro7/bike-sharing/issues)
ends with a small benchmark, uncertainty analysis, one planning study and a
LaTeX decision brief. All six deliverables are complete. The documentation is
live and [v1.0.0 is published](https://github.com/DiogoRibeiro7/bike-sharing/releases/tag/v1.0.0).
See the [verified publication record](reproduction.md#github-pages-and-release-status).
