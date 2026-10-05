# Asymmetric-cost planning study

This study connects forecasts to an explicit decision: choose an hourly workload
planning target before observing rentals. It is a scenario analysis of a proxy
loss, not an estimate of financial returns or a station inventory policy.

## Decision and assumptions

For each future hour, choose a nonnegative real target `a`, measured in
rental-equivalent workload units. The observed hourly rental count is `y`.
Targets remain fixed for the 168-hour forecast horizon. Fractional targets are
allowed because they represent a continuous planning allowance, not a number of
bikes or staff. There is no capacity cap, integer constraint, ramp constraint,
inter-hour coupling or requirement to conserve inventory.

The assumed loss is:

```text
L(y, a; r) = r * max(y - a, 0) + max(a - y, 0)
```

Overprediction costs one normalized unit per excess unit of target. The ratio
`r` is the underprediction cost relative to that unit. Scenarios are fixed at
`r = 0.25, 0.5, 1, 2, 4, 9`. These values are assumptions, not estimates from the
CSV, monetary amounts or statements about the operator's preferences. Multiplying
both unit costs by the same positive constant rescales losses without changing
the preferred action. At `r = 1`, this loss is absolute error.

The scenario grid, policy set, calibration window and quantile rule were fixed
before running this planning benchmark. Each scenario is reported separately;
there is no data-driven choice of the economically correct cost ratio.

## Policies and the quantile decision

Four policies use the existing training-mean, hour-of-week-mean, seasonal-naive
and Poisson-calendar point forecasts directly as targets. They ignore the cost
ratio when choosing a target, providing simple decision baselines.

A fifth policy, `poisson_residual_quantile`, adjusts Poisson's target according
to the cost ratio. Poisson was the MAE-selected reference in the preceding
validation study. Its choice therefore already used this quarter: the planning
comparison is developmental, not an independent assessment of model selection.
We do not search over additional models or residual-window lengths.

For a specified outcome distribution, expected asymmetric loss is minimized at
a quantile with level `tau = r / (1 + r)`. At a continuity point, its derivative
with respect to the target is `(1 + r) * F(a) - r`; the zero gives that level.
For a discrete distribution, choose the first point where the cumulative
probability reaches `tau`. This is the critical-fractile decision underlying the
[newsvendor loss](https://ocw.mit.edu/courses/15-772j-d-lab-supply-chains-fall-2014/6952be57b43aa185119c6f114908bcc5_MIT15_772JF14_Newsboy.pdf).
Here we apply the loss to a workload proxy, without asserting an inventory model.

The residual policy constructs an empirical distribution from past errors:

```text
s(mu) = sqrt(max(mu, 1))
z = (y - mu) / s(mu)
k = ceil(n * r / (1 + r))
a = max(0, current_mu + s(current_mu) * sorted(z)[k - 1])
```

These are **signed** out-of-sample residuals. The empirical order statistic uses
`ceil(n * tau)`, without interpolation; ties use the lower quantile. This differs
from the adjusted rank for the absolute-residual intervals. Applying the scale,
shift and zero clipping to the residual distribution gives nonnegative proxy
outcomes; the action minimizes asymmetric loss under that empirical distribution.
It need not minimize loss under the true future distribution. No count rounding
is applied to the continuous workload decision.

Do not use an upper bound from a central 90% prediction interval as a 90th
percentile decision by default. The preceding interval study pools absolute
errors; it does not estimate a one-sided signed residual distribution. This
planning rule recalculates signed residuals using the same temporal principle.

## Temporal evaluation and selection

At the first validation origin, July 1, residual calibration uses four preceding
weekly forecasts spanning June 3–July 1. Each forecast is fitted strictly before
its origin. At every subsequent origin, calibration uses residual timestamps in
`[origin - 672 hours, origin)`, with at least 30 observed residuals. Calibration
observations may enter later expanding point fits, but their recorded errors
always come from the original out-of-sample forecast.

All actions for the horizon are determined before its outcomes enter the next
calibration window. Validation remains July–September, with 13 full weekly folds
and the final 24-hour fold. Missing hours are excluded from fitting/scoring and
residual calibration, never replaced with zeros. Empty folds are recorded, and
a subsequent scored fold must still satisfy calibration support. Every observed
hour has equal weight in pooled cost.

For each fixed ratio, select the policy with the lowest pooled validation cost.
Exact ties follow the four-model order above, followed by the residual policy.
The saved manifest records all six choices, data identity, point-model settings,
package version, boundaries, cadence and a hash of the planning configuration.
The nested `reference_point` describes the Poisson reference and shared point
configuration; the separate `policies` map contains the actual cost-based choices.

## Reproduce the evidence

```bash
poetry run bike-sharing-planning --output results/planning-validation.json
```

The [committed report](https://github.com/DiogoRibeiro7/bike-sharing/blob/master/benchmarks/planning-validation-2012-q3.json)
records all policies and scenarios, per-fold and pooled costs, mean targets,
underprediction/excess amounts, underprediction frequencies, calibration counts
and quantiles. Software and source identities are included. The result tables
below are derived from that report. No real final-test outcomes are scored.

## Validation cost sensitivity

Mean normalized loss per observed hour; lower is better within each row.
Costs across different rows use different penalties and should not be ranked
as if they represented a common business objective. All rows cover 2,208 hours.

| Under/over cost ratio | Training mean | Hour-of-week | Seasonal-naive | Poisson point | Poisson residual quantile |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.25 | 80.018 | 31.911 | 33.898 | 38.066 | 25.385 |
| 0.5 | 118.567 | 61.073 | 41.264 | 43.133 | 36.897 |
| 1 | 195.665 | 119.397 | 55.998 | 53.268 | 52.328 |
| 2 | 349.863 | 236.045 | 85.465 | 73.536 | 71.368 |
| 4 | 658.257 | 469.341 | 144.399 | 114.074 | 90.937 |
| 9 | 1429.244 | 1052.582 | 291.733 | 215.418 | 115.067 |

The residual policy has the lowest pooled validation cost in all six scenarios.
Its advantage over the Poisson point policy is small at equal costs (52.328
versus 53.268), but larger when underprediction costs nine times as much
(115.067 versus 215.418). These are differences in the assumed loss on historical
rentals, not realised savings. No significance or future-superiority claim is made.

## How the selected targets change

| Ratio | Quantile level | Mean target | Mean underprediction | Mean excess | Hours below observed rentals |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.25 | 0.200 | 238.593 | 60.116 | 10.356 | 83.61% |
| 0.5 | 0.333 | 257.208 | 45.361 | 14.217 | 71.88% |
| 1 | 0.500 | 277.514 | 31.583 | 20.745 | 55.98% |
| 2 | 0.667 | 299.830 | 19.964 | 31.440 | 39.49% |
| 4 | 0.800 | 324.962 | 10.865 | 47.475 | 24.91% |
| 9 | 0.900 | 349.898 | 5.352 | 66.898 | 12.95% |

Higher underprediction penalties raise targets and reduce underprediction, while
increasing excess. At ratio 9, the policy still falls below observed rentals in
12.95% of validation hours; the nominal quantile level is 90%. This is not a
guaranteed service level. Serial dependence, distribution shifts and imperfect
scaling can make the recent residual distribution a poor future approximation.

## What this supports—and what remains unknown

The study shows how an explicit loss changes a decision and how to assess that
decision chronologically. A stakeholder must supply defensible costs before
choosing a scenario. Cost sensitivity is more informative than declaring one
forecast universally best from its MAE alone.

Aggregate rentals cannot reveal unmet requests, stockouts, bicycle availability,
station origins/destinations, travel times or rebalancing feasibility. The target
is a proxy workload allowance: it does not prescribe bikes, staffing headcount
or staffing hours. Missing rental observations may also be informative.
Observed rental counts reflect the historical system and are not necessarily
the outcomes that would occur after changing its capacity or service.

Before an operational recommendation, obtain station/inventory and unmet-demand
data, an explicit mapping from workload to resources, validated marginal costs,
capacity and temporal constraints, and a design for measuring intervention effects.
This benchmark cannot identify causal benefits or realised financial savings.

The same validation quarter informed point-model choice, interval diagnostics
and planning development. Policy-selection costs are optimistically selected
developmental evidence. No independence-based confidence interval is reported.
The summer/early-autumn period does not establish robustness over an annual cycle.

## Final assessment after development

```bash
poetry run bike-sharing-planning --stage test \
  --selection results/planning-validation.json --output results/planning-test.json
```

Run this only after all study choices are frozen. Each scenario evaluates only
its saved policy. The CLI exposes no test-time cost, policy or cadence overrides.
Data, software and configuration identities must match. If needed, initial
calibration is replayed over four horizons aligned to the first test origin.
Later test counts may update fits and residuals only at the saved weekly cadence;
they never reselect a policy. Point-only selected policies require no residual
calibration. The frozen real test assessment is now recorded in
[final results](final-results.md); synthetic tests exercise both paths. At equal
costs the selected policy loses its validation advantage. It was not reselected.

Package 0.5.0 preserves historical point and interval artifacts and reproduces
their numerical results; only package-version selection metadata is refreshed.
No new dependencies are introduced.
