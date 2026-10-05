# Roadmap to v1.0

Completed on 5 October 2026: one reproducible statistical case study connecting
aggregate rental forecasts to an explicit planning decision.

- [Live documentation](https://diogoribeiro7.github.io/bike-sharing/)
- [v1.0.0 release](https://github.com/DiogoRibeiro7/bike-sharing/releases/tag/v1.0.0)
- [Verified publication run](https://github.com/DiogoRibeiro7/bike-sharing/actions/runs/37277134068)

| Order | Issue | Deliverable | Status |
| --- | --- | --- | --- |
| 1 | [#1](https://github.com/DiogoRibeiro7/bike-sharing/issues/1) | Typed package, validated loader, fixed-origin baselines and CI | Completed in PR #7 |
| 2 | [#2](https://github.com/DiogoRibeiro7/bike-sharing/issues/2) | Data lineage, units, license and calendar audit | Numeric reconciliation complete; remaining lineage and unit uncertainties documented |
| 3 | [#3](https://github.com/DiogoRibeiro7/bike-sharing/issues/3) | Interpretable models and rolling-origin comparisons | Completed: four candidates, weekly expanding folds, frozen protocol and per-fold evidence |
| 4 | [#4](https://github.com/DiogoRibeiro7/bike-sharing/issues/4) | Forecast intervals and calibration assessment | Completed: temporal residual calibration, count intervals, coverage/width/score diagnostics and frozen-test procedure |
| 5 | [#5](https://github.com/DiogoRibeiro7/bike-sharing/issues/5) | Asymmetric-cost planning study | Completed: explicit proxy loss, six cost scenarios, five policies, frozen selections and reproducible validation evidence |
| 6 | [#6](https://github.com/DiogoRibeiro7/bike-sharing/issues/6) | Documentation site, LaTeX brief and verified v1.0 release | Completed: live Pages site, LaTeX/PDF brief and verified v1.0.0 release |

Each implementation is reviewed through a pull request. This repository's
existing default branch is `master`; PRs currently target it. A branch rename
requires coordinating repository settings and is not part of the baseline.

## Completion boundary

The release met its completion boundary: a fresh environment reproduces the
frozen final reports, numerical claims have committed evidence, the data audit's
unresolved qualifications are explicit, and the brief explains findings and
limits. CI, deployment, live-site checks and release publication passed.

Operational model deployment, dashboards, station-level rebalancing, additional
datasets and an expanding collection of algorithms are outside v1.0. The final
quarter of 2012 was used for the frozen final evaluation and is now consumed.
New method development needs a separate evaluation design and new final evidence.

## Current limitations

The current selection run compares four fixed candidates on weekly expanding
folds in July–September. Poisson calendar is selected by pooled MAE, although
seasonal-naive wins in 8 of 14 folds. Train/validation/test boundaries and the
selected refit cadence are enforced. The frozen final assessment is now recorded;
the test quarter cannot serve as a fresh holdout for later development.

Empirical intervals now quantify recent forecast error. Poisson's nominal 90%
bands cover 90.4% overall but 86.4% at high predicted demand; no universal or
conditional coverage guarantee is claimed. The planning study (#5) now compares
five policies at six assumed cost ratios.
The residual-adjusted Poisson policy is selected in every scenario, without
claims of operational savings. The final assessment shows 85.19% coverage at the
nominal 90% level and a loss of the planning advantage at equal costs. The brief
reports these adverse findings. The planned modernization is complete; these
limitations are part of the published evidence, not an open-ended development
backlog.
Upstream lineage and unit uncertainties remain documented in the completed data
audit (#2).
