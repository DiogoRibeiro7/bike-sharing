# Interpretable forecasting candidates

All candidates predict observed aggregate hourly rentals. Fitting accepts only
observations strictly before an explicit origin and future calendar timestamps.
It cannot accept the evaluation counts or observed future weather. The four
candidates and all settings below were fixed before the rolling validation run;
this comparison does not search over penalties, feature sets or horizons.

## Reference means

`training_mean` predicts the mean of all available training counts.
`hour_of_week_mean` uses the corresponding weekday/hour mean, with the training
mean as fallback for an unseen pair. Both expand their history at each origin.
Pooling a long history can lag a change in the rental level.

## Seasonal-naive

`seasonal_naive` copies the same calendar hour from the week preceding the
origin. For a forecast longer than seven days, that last week repeats; outcomes
inside the horizon never replace it. Lags are timestamp lookups, not 168-row
shifts, so absent hours cannot move the calendar alignment.

A missing reference hour falls back to the current training mean. Each fold
reports how many forecasts used this fallback. This is distinct from treating
an absent hour as a zero. Seasonal-naive adapts quickly to a recent level but
also repeats unusual events in the reference week and cannot anticipate new ones.

## Penalized Poisson calendar model

`poisson_calendar` uses a log link: `mean = exp(intercept + features @ coefficients)`.
The 57 deterministic calendar features are:

| Terms | Number | Reference or definition |
| --- | ---: | --- |
| Hour indicators | 23 | Hour 00 omitted |
| Weekday indicators | 6 | Monday omitted |
| Weekend × hour interactions | 23 | Different weekend hourly shape, relative to hour 00 |
| Annual Fourier terms | 4 | Sine/cosine at frequencies 1 and 2 |
| Linear time | 1 | Years since 2011-01-01, with 365.25 days per year |

The intercept is fitted separately. The encoding is defined independently of
observed outcomes; there is no learned category discovery, imputation or scaling.
Each origin fits a fresh model on its own training prefix. There is no warm start.

The implementation uses scikit-learn's
[PoissonRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.PoissonRegressor.html)
with L2 penalty `alpha=0.1`, `solver="newton-cholesky"`, `max_iter=300` and
`tol=1e-8`. Numerical thread pools are limited to one thread for consistent small
matrix workloads. The committed Poetry lock identifies the numerical libraries.
An optimization warning or invalid forecast fails the run; failed folds are not
silently dropped from model selection.

A constant positive training series has the exact solution of zero coefficients
and intercept equal to the log of that constant. We calculate it directly to
avoid numerical line-search failures at a stationary point. An all-zero training
series uses the limiting zero-mean prediction and records that special case.

Every fold records its intercept, named coefficients and iteration count.
For a unit increase in a feature, holding the others fixed, `exp(coefficient)`
is the fitted multiplier on the mean. Hour comparisons on weekends must include
the relevant interaction term. These are penalized predictive associations,
not causal effects or unpenalized significance tests.

## Limits

The model omits holidays, weather and disruptions. Its log-linear trend can
extrapolate poorly, and smooth annual terms cannot describe every seasonal
change. A Poisson working model for the mean does not establish equality of
conditional mean and variance or justify Poisson prediction intervals. Serial
dependence and overdispersion still need assessment in the uncertainty work.
No uncertainty or operational savings claim follows from this benchmark.

The [results](results.md) include cases where the simpler seasonal-naive model
has lower errors. The [forecasting protocol](methodology.md) defines exactly
when information becomes available and how model selection is performed.
