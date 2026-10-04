# Roadmap to v1.0

Goal: one reproducible, statistically defensible case study that connects
aggregate rental forecasts to an explicit planning decision.

| Order | Issue | Deliverable | Status |
| --- | --- | --- | --- |
| 1 | [#1](https://github.com/DiogoRibeiro7/bike-sharing/issues/1) | Typed package, validated loader, fixed-origin baselines and CI | Completed in PR #7 |
| 2 | [#2](https://github.com/DiogoRibeiro7/bike-sharing/issues/2) | Data lineage, units, license and calendar audit | Numeric reconciliation complete; remaining lineage and unit uncertainties documented |
| 3 | [#3](https://github.com/DiogoRibeiro7/bike-sharing/issues/3) | Interpretable models and rolling-origin comparisons | Completed: four candidates, weekly expanding folds, frozen protocol and per-fold evidence |
| 4 | [#4](https://github.com/DiogoRibeiro7/bike-sharing/issues/4) | Forecast intervals and calibration assessment | Planned |
| 5 | [#5](https://github.com/DiogoRibeiro7/bike-sharing/issues/5) | Asymmetric-cost planning study | Planned |
| 6 | [#6](https://github.com/DiogoRibeiro7/bike-sharing/issues/6) | Documentation site, LaTeX brief and verified v1.0 release | Planned |

Each implementation is reviewed through a pull request. This repository's
existing default branch is `master`; PRs currently target it. A branch rename
requires coordinating repository settings and is not part of the baseline.

## Completion boundary

The release is finished when a clean checkout reproduces the documented
benchmark and one decision study, all numerical claims have committed evidence,
the data audit is resolved, and the LaTeX brief explains conclusions and limits.

Live deployment, dashboards, station-level rebalancing, additional datasets and
an expanding collection of algorithms are outside v1.0. The final quarter of
2012 is reserved for final evaluation; development comparisons must precede it.

## Current limitations

The current selection run compares four fixed candidates on weekly expanding
folds in July–September. Poisson calendar is selected by pooled MAE, although
seasonal-naive wins in 8 of 14 folds. Train/validation/test boundaries and the
selected refit cadence are enforced. The real test period remains unscored.

The next step is interval estimation and calibration (#4), followed by the
planning study (#5). Interval and decision choices must be frozen before final
testing. The current point forecasts do not quantify uncertainty or establish
operational savings. Upstream lineage and unit uncertainties remain documented
in the completed data audit (#2).
