"""Training-only calendar baselines and a fixed-origin evaluation protocol."""

import math
import platform
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timedelta
from importlib.metadata import version
from statistics import fmean

from bike_sharing.data import (
    DemandDataset,
    Observation,
    coverage,
    validate_observations,
    validate_timestamp,
)
from bike_sharing.splits import DEFAULT_SPLIT, StudySplit


def forecast_baselines(
    training: Sequence[Observation], timestamps: Sequence[datetime]
) -> dict[str, tuple[float, ...]]:
    """Fit means on training counts and predict future calendar timestamps only.

    The weekly profile pools all training values for each weekday/hour pair.
    Unseen pairs fall back to the training mean. Evaluation outcomes are absent
    from this interface, so neither model can condition on them.
    """
    validate_observations(training)
    if not timestamps:
        raise ValueError("at least one prediction timestamp is required")
    for timestamp in timestamps:
        validate_timestamp(timestamp)
        if timestamp <= training[-1].timestamp:
            raise ValueError("prediction timestamps must follow all training observations")
    overall = fmean(item.count for item in training)
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for item in training:
        buckets[(item.timestamp.weekday(), item.timestamp.hour)].append(item.count)
    means = {key: fmean(counts) for key, counts in buckets.items()}
    return {
        "training_mean": tuple(overall for _ in timestamps),
        "hour_of_week_mean": tuple(
            means.get((timestamp.weekday(), timestamp.hour), overall) for timestamp in timestamps
        ),
    }


def error_metrics(actual: Sequence[int], predicted: Sequence[float]) -> dict[str, float]:
    """Return MAE and RMSE in hourly rentals, validating finite nonnegative inputs."""
    if not actual or len(actual) != len(predicted):
        raise ValueError("actual and predicted must have equal, nonzero lengths")
    if any(type(value) is not int or value < 0 for value in actual):
        raise ValueError("actual values must be nonnegative integer counts")
    if any(not math.isfinite(value) or value < 0 for value in predicted):
        raise ValueError("predictions must be finite and nonnegative")
    errors = [forecast - observed for observed, forecast in zip(actual, predicted, strict=True)]
    return {
        "mae": fmean(abs(error) for error in errors),
        "rmse": math.sqrt(fmean(error**2 for error in errors)),
    }


def evaluate(
    dataset: DemandDataset,
    cutoff: datetime,
    horizon_hours: int = 168,
    *,
    split: StudySplit = DEFAULT_SPLIT,
) -> dict[str, object]:
    """Evaluate a validation-only window [cutoff, cutoff + horizon_hours).

    Training contains every observed timestamp strictly before cutoff. Outcomes
    during the horizon are used only for scoring. Missing timestamps are counted
    and excluded from scoring; no zero-rental observations are invented.
    """
    split.validate_window(cutoff, horizon_hours)
    validate_observations(dataset.observations)
    end = cutoff + timedelta(hours=horizon_hours)
    data_end = dataset.observations[-1].timestamp + timedelta(hours=1)
    if cutoff <= dataset.observations[0].timestamp or end > data_end:
        raise ValueError(
            "the full evaluation window must fit after training and within the dataset"
        )
    training = tuple(item for item in dataset.observations if item.timestamp < cutoff)
    testing = tuple(item for item in dataset.observations if cutoff <= item.timestamp < end)
    if not testing:
        raise ValueError("evaluation window has no observed outcomes")
    timestamps = tuple(item.timestamp for item in testing)
    predictions = forecast_baselines(training, timestamps)
    actual = tuple(item.count for item in testing)
    return {
        "schema_version": "1.0",
        "stage": "validation_diagnostic",
        "study_split": split.to_dict(),
        "package_version": version("bike-sharing-forecast"),
        "python_version": platform.python_version(),
        "dataset": {
            "source_name": dataset.source_name,
            "sha256": dataset.sha256,
            **coverage(dataset.observations),
        },
        "protocol": {
            "name": "fixed_origin_calendar_baselines",
            "cutoff_inclusive": cutoff.isoformat(),
            "end_exclusive": end.isoformat(),
            "horizon_hours": horizon_hours,
            "training": coverage(training),
            "evaluation_observations": len(testing),
            "absent_evaluation_hours": horizon_hours - len(testing),
            "features": ["weekday", "hour"],
            "refit_during_horizon": False,
            "unseen_weekly_bucket": "training_mean",
            "missing_hours": "excluded_from_scoring_not_imputed",
            "target": "observed_aggregate_hourly_rentals",
        },
        "metrics": {name: error_metrics(actual, values) for name, values in predictions.items()},
    }
