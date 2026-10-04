"""Interpretable candidates with an explicit forecast-origin information boundary."""

import math
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import fmean

import numpy as np
from numpy.typing import NDArray
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import PoissonRegressor
from threadpoolctl import threadpool_limits

from bike_sharing.data import Observation, validate_observations, validate_timestamp
from bike_sharing.forecasting import forecast_baselines

# Ordered before seeing validation scores; the order also breaks exact MAE ties.
CANDIDATES = ("training_mean", "hour_of_week_mean", "seasonal_naive", "poisson_calendar")
POISSON_ALPHA = 0.1
POISSON_MAX_ITER = 300
POISSON_TOL = 1e-8
FEATURE_NAMES = (
    *(f"hour_{hour:02d}" for hour in range(1, 24)),
    *(f"weekday_{day}" for day in range(1, 7)),
    *(f"weekend_hour_{hour:02d}" for hour in range(1, 24)),
    "annual_sin_1",
    "annual_cos_1",
    "annual_sin_2",
    "annual_cos_2",
    "trend_years",
)


def model_configuration() -> dict[str, object]:
    """Return fixed settings, not a grid chosen after inspecting validation errors."""
    return {
        "candidate_tie_order": list(CANDIDATES),
        "seasonal_naive": {"period_hours": 168, "missing_lag": "training_mean"},
        "poisson_calendar": {
            "alpha": POISSON_ALPHA,
            "solver": "newton-cholesky",
            "max_iter": POISSON_MAX_ITER,
            "tol": POISSON_TOL,
            "fit_intercept": True,
            "feature_names": list(FEATURE_NAMES),
            "encoding": "fixed_calendar_basis_v1",
            "annual_period_days": 365.25,
            "epoch": "2011-01-01T00:00:00",
            "scaling": "none",
            "threads": 1,
            "all_zero_training": "constant_zero",
            "constant_positive_training": "analytic_intercept",
        },
    }


def calendar_features(timestamps: Sequence[datetime]) -> NDArray[np.float64]:
    """Encode known calendars without learning categories or scaling from future data.

    References are hour 00 and Monday. Weekend interactions allow a different
    hourly shape; annual harmonics and a linear time term describe slow changes.
    """
    rows: list[list[float]] = []
    for timestamp in timestamps:
        validate_timestamp(timestamp)
        years = (timestamp - datetime(2011, 1, 1)).total_seconds() / (365.25 * 86400)
        angle = 2 * math.pi * years
        rows.append(
            [
                *(float(timestamp.hour == hour) for hour in range(1, 24)),
                *(float(timestamp.weekday() == day) for day in range(1, 7)),
                *(
                    float(timestamp.weekday() >= 5 and timestamp.hour == hour)
                    for hour in range(1, 24)
                ),
                math.sin(angle),
                math.cos(angle),
                math.sin(2 * angle),
                math.cos(2 * angle),
                years,
            ]
        )
    return np.asarray(rows, dtype=np.float64).reshape(len(rows), len(FEATURE_NAMES))


@dataclass(frozen=True, slots=True)
class Forecast:
    """Predictions and fit diagnostics; no evaluation outcomes are accepted by fitting."""

    values: tuple[float, ...]
    details: dict[str, object]


def forecast_model(
    model: str, training: Sequence[Observation], timestamps: Sequence[datetime], *, origin: datetime
) -> Forecast:
    """Fit one candidate strictly before origin and freeze it over the supplied horizon."""
    if model not in CANDIDATES:
        raise ValueError(f"unknown model: {model}")
    validate_timestamp(origin)
    validate_observations(training)
    if training[-1].timestamp >= origin:
        raise ValueError("training observations must precede the forecast origin")
    if not timestamps:
        raise ValueError("at least one prediction timestamp is required")
    for timestamp in timestamps:
        validate_timestamp(timestamp)
        if timestamp < origin:
            raise ValueError("prediction timestamps must be at or after the forecast origin")
    if model == "training_mean":
        mean = fmean(item.count for item in training)
        return Forecast((mean,) * len(timestamps), {})
    if model == "hour_of_week_mean":
        return Forecast(forecast_baselines(training, timestamps)[model], {})
    if model == "seasonal_naive":
        history = {item.timestamp: float(item.count) for item in training}
        fallback = fmean(history.values())
        week = timedelta(hours=168)
        anchors = [
            timestamp - ((timestamp - origin) // week + 1) * week for timestamp in timestamps
        ]
        # Always copy from the week preceding origin, even for horizons longer than a week.
        return Forecast(
            tuple(history.get(anchor, fallback) for anchor in anchors),
            {"missing_lag_fallbacks": sum(anchor not in history for anchor in anchors)},
        )
    if not any(item.count for item in training):
        # The finite-intercept Poisson MLE does not exist when all outcomes are zero.
        return Forecast((0.0,) * len(timestamps), {"fit_status": "all_zero_training"})
    if all(item.count == training[0].count for item in training):
        # This is the exact penalized optimum; avoid a line search at machine-zero gradient.
        constant = float(training[0].count)
        return Forecast(
            (constant,) * len(timestamps),
            {
                "fit_status": "constant_training",
                "iterations": 0,
                "intercept": math.log(constant),
                "coefficients": dict.fromkeys(FEATURE_NAMES, 0.0),
            },
        )
    estimator = PoissonRegressor(
        alpha=POISSON_ALPHA,
        solver="newton-cholesky",
        max_iter=POISSON_MAX_ITER,
        tol=POISSON_TOL,
        fit_intercept=True,
        warm_start=False,
    )
    features = calendar_features([item.timestamp for item in training])
    outcomes = np.asarray([item.count for item in training], dtype=np.float64)
    try:
        with threadpool_limits(limits=1), warnings.catch_warnings(), np.errstate(over="raise"):
            warnings.simplefilter("error", ConvergenceWarning)
            estimator.fit(features, outcomes)
            predictions = tuple(
                float(value) for value in estimator.predict(calendar_features(timestamps))
            )
    except (ConvergenceWarning, FloatingPointError) as exc:
        raise ValueError(f"Poisson fitting/prediction failed: {exc}") from exc
    if any(not math.isfinite(value) or value <= 0 for value in predictions):
        raise ValueError("Poisson predictions must be finite and positive")
    return Forecast(
        predictions,
        {
            "fit_status": "converged",
            "iterations": int(estimator.n_iter_),
            "intercept": float(estimator.intercept_),
            "coefficients": {
                name: float(value)
                for name, value in zip(FEATURE_NAMES, estimator.coef_, strict=True)
            },
        },
    )
