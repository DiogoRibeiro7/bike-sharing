# Reproduction and publication

## Exact study environment

Use Python 3.12 and Poetry 2.5.1. The lockfile specifies the numerical and
documentation dependencies; no network is used for the statistical study after
installation. The CSV is repository data, not part of the wheel.

```bash
poetry install --with dev,docs
poetry check --lock
poetry run pytest --cov=bike_sharing --cov-report=term-missing
poetry run python scripts/reproduce_release.py
poetry run python scripts/build_tables.py
poetry run mkdocs build --strict
poetry build
```

The replay checks source and validation-artifact hashes from
`benchmarks/release-v1/freeze-manifest.json`, reads the saved selections, and
recomputes the three final reports. Exact structure and non-floating values must
match; floating results use relative tolerance `1e-6` and absolute tolerance
`1e-8`. Runtime and environment details are recorded but excluded from numerical
comparison. Outputs go to `results/release-reproduction`; the committed reports
are never overwritten. Historical validation studies are reproduced by tests.

The final quarter has now been inspected. Replays verify an existing result;
they do not provide a new untouched holdout. Any later model improvement is a
new exploratory study and needs new evaluation data before a fresh final claim.

## Recorded evidence

The `benchmarks/release-v1` directory contains point, interval and planning
validation reports, their corresponding test reports, and the pre-evaluation
freeze manifest. Earlier versioned benchmarks remain unchanged. Release-version
validation selections match the earlier choices and configurations, with only
package-version metadata refreshed before test scoring.

The freeze manifest records the development commit, UTC freeze time, Python
source hashes and hashes of the validation artifacts. It is an auditable record,
not proof that a public historical dataset was never inspected by a human.

To reproduce each explicit final command separately:

```bash
poetry run bike-sharing --stage test \
  --selection benchmarks/release-v1/point-validation.json --output results/point-test.json
poetry run bike-sharing-intervals --stage test \
  --selection benchmarks/release-v1/interval-validation.json --output results/interval-test.json
poetry run bike-sharing-planning --stage test \
  --selection benchmarks/release-v1/planning-validation.json --output results/planning-test.json
```

## LaTeX brief and tables

The [decision brief](assets/decision-brief.pdf) is compiled from
`brief/decision-brief.tex`. `scripts/build_tables.py` derives its three tables
and matching Markdown tables from the committed JSON evidence.

With a LaTeX installation containing `geometry`, `booktabs`, `hyperref` and
Latin Modern fonts:

```bash
poetry run python scripts/build_tables.py
cd brief
pdflatex -interaction=nonstopmode -halt-on-error decision-brief.tex
pdflatex -interaction=nonstopmode -halt-on-error decision-brief.tex
```

CI compiles the brief and uploads it as an artifact. The PDF bundled with the
site was rendered and visually checked during preparation. PDF byte identity is
not expected across LaTeX versions and build timestamps; numerical tables are
checked exactly. The mathematical procedure's source hashes are checked before
replaying final evidence.

## GitHub Pages and release status

The case study was published on **5 October 2026**:

- [Documentation site](https://diogoribeiro7.github.io/bike-sharing/)
- [Final assessment](https://diogoribeiro7.github.io/bike-sharing/final-results/)
- [v1.0.0 release and attached distributions](https://github.com/DiogoRibeiro7/bike-sharing/releases/tag/v1.0.0)
- [Successful publication run](https://github.com/DiogoRibeiro7/bike-sharing/actions/runs/37277134068)

The release targets reviewed commit `3543f54d04d9d74d34b5b1e1bea8eba4b482e3bc`
and contains the Python wheel, source distribution and decision brief. The live
homepage, final-results page and PDF returned HTTP 200 during verification. The
published PDF matched the reviewed repository artifact byte for byte (SHA-256
`2a10aec1e18eb620f0bb1231608315bb71b2054618b8453973366b38cc870ad3`).
The six-item v1 roadmap is complete.

For a fork, enable **Settings → Pages → Build and deployment → Source → GitHub
Actions** before using the publication workflow. This repository is already
configured and deployed. No local publication commands are needed.

After a successful CI push run on reviewed `master`, **Publish case study**
installs a fresh locked environment, replays evidence, builds the site and
packages, deploys Pages, checks the live index and only then creates `v1.0.0`
with the distributions and brief attached. A manual rerun is available from the
Actions UI on `master`; no local publication commands are required. An existing
release is left unchanged. PR runs build and verify but do not publish.

The published tag and assets are retained as the release record. Later
metadata/documentation changes can update the live site without replacing
v1.0.0 assets or rerunning model selection. New scientific work requires a
separate scope and fresh assessment data.
