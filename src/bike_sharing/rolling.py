"""Expanding-window evaluation with disjoint calendar horizons and pooled metrics."""

import math
import platform
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib.metadata import version
from statistics import fmean
from time import perf_counter

from bike_sharing.data import DemandDataset, coverage, validate_observations, validate_timestamp
from bike_sharing.forecasting import error_metrics
from bike_sharing.models import CANDIDATES, forecast_model, model_configuration

DEVIANCE_FLOOR = 1e-9


@dataclass(frozen=True, slots=True)
class Fold:
    """One inclusive origin and exclusive horizon end; a final fold may be shorter."""

    origin: datetime
    end: datetime


def calendar_folds(start: datetime, end: datetime, horizon_hours: int = 168) -> tuple[Fold, ...]:
    """Tile a naive calendar interval exactly, with no overlaps or omitted final hours."""
    validate_timestamp(start)
    validate_timestamp(end)
    if type(horizon_hours) is not int or horizon_hours <= 0:
        raise ValueError("horizon_hours must be a positive integer")
    if start >= end:
        raise ValueError("fold start must precede end")
    folds = []
    origin = start
    while origin < end:
        stop = min(origin + timedelta(hours=horizon_hours), end)
        folds.append(Fold(origin, stop))
        origin = stop
    return tuple(folds)


def count_metrics(actual: Sequence[int], predicted: Sequence[float]) -> dict[str, float]:
    """Add mean Poisson deviance, flooring predictions for this metric only.

    Zero actual counts contribute 2*mu. The floor makes zero baseline predictions
    comparable without changing MAE/RMSE or silently dropping difficult cases.
    """
    metrics = error_metrics(actual, predicted)
    terms = []
    for observed, forecast in zip(actual, predicted, strict=True):
        mean = max(forecast, DEVIANCE_FLOOR)
        term = mean - observed
        if observed:
            term += observed * (math.log(observed) - math.log(mean))
        terms.append(max(0.0, 2 * term))
    return {**metrics, "mean_poisson_deviance": fmean(terms)}


def _evaluate_period(
    dataset: DemandDataset,
    start: datetime,
    end: datetime,
    horizon_hours: int,
    models: tuple[str, ...],
) -> dict[str, object]:
    """Shared engine; public study functions enforce validation or saved-test boundaries."""
    validate_observations(dataset.observations)
    folds = calendar_folds(start, end, horizon_hours)
    if (
        not models
        or len(set(models)) != len(models)
        or any(model not in CANDIDATES for model in models)
    ):
        raise ValueError("models must be a nonempty set of known candidates")
    if start <= dataset.observations[0].timestamp or end > dataset.observations[
        -1
    ].timestamp + timedelta(hours=1):
        raise ValueError("evaluation period must fit after training and within the dataset")
    actual: list[int] = []
    predictions: dict[str, list[float]] = {model: [] for model in models}
    runtime = dict.fromkeys(models, 0.0)
    reports: list[dict[str, object]] = []
    for fold in folds:
        training = tuple(item for item in dataset.observations if item.timestamp < fold.origin)
        held_out = tuple(
            item for item in dataset.observations if fold.origin <= item.timestamp < fold.end
        )
        hours = int((fold.end - fold.origin).total_seconds() // 3600)
        metrics: dict[str, dict[str, float]] = {}
        details: dict[str, dict[str, object]] = {}
        elapsed: dict[str, float] = {}
        if held_out:
            timestamps = tuple(item.timestamp for item in held_out)
            outcomes = tuple(item.count for item in held_out)
            actual.extend(outcomes)
            for model in models:
                began = perf_counter()
                result = forecast_model(model, training, timestamps, origin=fold.origin)
                elapsed[model] = perf_counter() - began
                runtime[model] += elapsed[model]
                predictions[model].extend(result.values)
                metrics[model] = count_metrics(outcomes, result.values)
                details[model] = result.details
        reports.append(
            {
                "origin": fold.origin.isoformat(),
                "end_exclusive": fold.end.isoformat(),
                "horizon_hours": hours,
                "training": coverage(training),
                "evaluation_observations": len(held_out),
                "absent_evaluation_hours": hours - len(held_out),
                "status": "scored" if held_out else "no_observations",
                "metrics": metrics,
                "fit_diagnostics": details,
                "fit_predict_seconds": elapsed,
            }
        )
    if not actual:
        raise ValueError("evaluation period has no observed outcomes")
    return {
        "schema_version": "2.0",
        "package_version": version("bike-sharing-forecast"),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "dependencies": {
                name: version(name) for name in ("numpy", "scipy", "scikit-learn", "threadpoolctl")
            },
        },
        "dataset": {"source_name": dataset.source_name, "sha256": dataset.sha256},
        "protocol": {
            "name": "expanding_window",
            "horizon_hours": horizon_hours,
            "step_hours": horizon_hours,
            "start": start.isoformat(),
            "end_exclusive": end.isoformat(),
            "partial_final_fold": "included",
            "refit_at_each_origin": True,
            "refit_during_horizon": False,
            "aggregation": "pooled_observed_hours",
            "missing_hours": "excluded_from_scoring_not_imputed",
            "poisson_deviance_floor": DEVIANCE_FLOOR,
            "configuration": model_configuration(),
            "models_evaluated": list(models),
        },
        "folds": reports,
        "evaluation_observations": len(actual),
        "absent_evaluation_hours": int((end - start).total_seconds() // 3600) - len(actual),
        "metrics": {model: count_metrics(actual, predictions[model]) for model in models},
        "fit_predict_seconds": runtime,
    }
