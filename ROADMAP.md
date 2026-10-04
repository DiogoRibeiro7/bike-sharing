# Roadmap to v1.0

Goal: one reproducible, statistically defensible case study that connects
aggregate rental forecasts to an explicit planning decision.

| Order | Issue | Deliverable | Status |
| --- | --- | --- | --- |
| 1 | [#1](https://github.com/DiogoRibeiro7/bike-sharing/issues/1) | Typed package, validated loader, fixed-origin baselines and CI | Implemented in this PR; pending merge |
| 2 | [#2](https://github.com/DiogoRibeiro7/bike-sharing/issues/2) | Data lineage, units, license and calendar audit | Planned |
| 3 | [#3](https://github.com/DiogoRibeiro7/bike-sharing/issues/3) | Interpretable models and rolling-origin comparisons | Planned |
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

The initial July 2012 diagnostic uses one frozen one-week horizon and two
calendar means. It does not establish annual performance, quantify uncertainty,
measure operational savings or resolve the dataset's upstream provenance.
