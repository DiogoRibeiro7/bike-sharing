# Training, validation and test

The study uses chronological partitions. Every boundary is inclusive on the
left and exclusive on the right; no row belongs to two partitions.

| Partition | Default boundaries | Used for |
| --- | --- | --- |
| Training | Dataset start to 2012-07-01 | Candidate fitting |
| Validation | 2012-07-01 to 2012-10-01 | Model choice using MAE |
| Test | 2012-10-01 to 2013-01-01 | Final assessment of the frozen choice |

## Development

```bash
poetry run bike-sharing --output results/validation.json
```

This fits the two calendar baselines on training and scores their frozen
forecasts over validation. The lowest validation MAE wins; ties prefer the
training mean. The report records the selected model, exact source checksum,
study boundaries and package version. The test partition is never scored by
this command. Reading and validating a CSV is distinct from using its test
outcomes for model fitting or selection.

The initial protocol is fixed-origin. It does not yet perform rolling-origin
model selection, hyperparameter tuning or interval calibration. Those extensions
must keep all model-selection decisions before the test boundary.

## Short diagnostic

```bash
poetry run bike-sharing --cutoff 2012-07-01 --horizon-hours 168
```

The whole requested window must lie in validation. A window ending exactly at
October 1 is allowed; one including the observation at October 1 is rejected.
If the cutoff is later within validation, earlier validation observations may
join the fitting history for that diagnostic. Such a report cannot be used as
a frozen selection: the full validation command creates that artifact.

## Final assessment after development

```bash
poetry run bike-sharing --stage test --selection results/validation.json \
  --output results/final-test.json
```

The selected baseline is refitted on training plus validation observations,
then held fixed for the complete test quarter. Only that model's test metrics
are returned. The command rejects missing selection artifacts, different source
checksums, different package versions and boundary overrides. Regenerate a
validation report after changing code version or source data.

**This project's real October–December outcomes have not been scored in the
modernization workflow.** CI tests this path with synthetic data. Do not use the
test command to decide what to improve next while claiming the test remains
untouched. Saved JSON is editable, and the software cannot establish that a
human has never previously inspected a test outcome.

## Custom studies

Supply `--validation-start`, `--test-start` and `--test-end` to the validation
command, or construct `StudySplit` in Python. Boundaries must be ordered and
fall on naive whole hours. All three partitions must have observations and the
source must span the requested study end. Later observations outside that end
are ignored. Custom boundaries are saved with the model choice and cannot be
overridden by the final-test command.

For the bundled portfolio study, retain the defaults so the historical final
quarter remains reserved. Missing hours are counted rather than filled with
zeros, including at partition boundaries.
