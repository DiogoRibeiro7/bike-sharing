# Training, validation and test

Every partition is inclusive on the left and exclusive on the right.

| Partition | Default boundaries | Role |
| --- | --- | --- |
| Training | Dataset start to 2012-07-01 | Initial fitting history |
| Validation | 2012-07-01 to 2012-10-01 | Compare fixed candidate procedures and select by MAE |
| Test | 2012-10-01 to 2013-01-01 | Final assessment after development is complete |

## Development

```bash
poetry run bike-sharing --output results/validation.json
```

The default uses 168-hour expanding-window folds, with a short final fold when
needed. Four candidates are fitted afresh before each origin. Earlier validation
observations can enter later fitting histories once available; a fold never
uses its own or later outcomes to fit its predictions. All candidate definitions
are fixed beforehand. The lowest pooled validation MAE wins.

The saved selection records the model, data checksum, boundaries, package
version, configuration hash and refit cadence. Reading or validating the source
CSV is distinct from fitting to or scoring its test outcomes. The command never
scores the test partition.

To retain the historical two-baseline, whole-quarter frozen comparison:

```bash
poetry run bike-sharing --protocol fixed --output results/fixed-validation.json
```

## Short diagnostic

```bash
poetry run bike-sharing --cutoff 2012-07-01 --horizon-hours 168
```

Diagnostics still compare only the original two means. Their entire window
must stay inside validation, and they cannot create a final-test selection.
`--cutoff` cannot be combined with `--protocol` or `--fold-hours`.

## Final assessment after development

```bash
poetry run bike-sharing --stage test --selection results/validation.json \
  --output results/final-test.json
```

Only the selected model is evaluated. A rolling selection uses its saved cadence:
first fit on training plus validation, then refit at later test origins using
only observations available before each origin. The forecasting procedure stays
fixed; earlier test counts can update coefficients at those scheduled times.
A fixed-origin selection instead freezes one refit for the complete quarter.

The command rejects missing/invalid selection artifacts, different data or
package/configuration identities, and overrides to boundaries, horizon or
protocol. Schema 1 historical selections can be read as fixed-origin selections,
but their old package version prevents execution under 0.3.0 until revalidated.

**The real October–December outcomes have not been scored in this modernization.**
CI uses synthetic data for final-test checks. Once real test errors are inspected,
do not use them for further tuning while still calling them untouched holdout
results. The current report is provisional model selection, not final evidence
for deployment.

## Custom studies

Use `--validation-start`, `--test-start`, `--test-end` and, for rolling validation,
`--fold-hours`, or the typed `StudySplit` API. Boundaries must be ordered naive
whole hours; the cadence must be a positive integer. All three partitions need
observations and the source must span the study end. A fold that would cross the
validation/test boundary is shortened to that boundary. Later source rows
outside the study are ignored.

For this portfolio study retain the defaults. Alternative horizons or feature
choices require a separately documented development experiment. Model selection,
interval calibration and later planning choices must finish before final testing.
