# Bike Sharing Forecasting

This case study develops a reproducible workflow for forecasting aggregate
hourly rentals and evaluating the decisions those forecasts might support.

The maintained implementation currently provides two calendar baselines,
validated CSV loading and fixed-origin evaluation. Everything needed for that
run is local to the repository after installation.

```bash
poetry install --with dev,docs
poetry run bike-sharing --output results/baseline.json
poetry run mkdocs serve
```

Read the [forecasting protocol](methodology.md) before interpreting the
[baseline results](results.md). The [data contract](data.md) describes verified
properties and unresolved provenance. The [API](api.md) documents the Python
interfaces. The [legacy audit](legacy-audit.md) explains the original notebook's
evaluation limitations.

The [six-issue roadmap](https://github.com/DiogoRibeiro7/bike-sharing/issues)
ends with a small benchmark, uncertainty analysis, one planning study and a
LaTeX decision brief. Hosted documentation is planned in issue #6; no live site
is claimed yet.
