"""Sequential residual calibration and explicit, saved-procedure final evaluation."""

import json
import platform
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path

from bike_sharing.calibration import (
    DEFAULT_INTERVAL_SPEC,
    IntervalBand,
    IntervalSpec,
    interval_metrics,
    make_interval,
    residual_quantile,
    residual_scale,
)
from bike_sharing.data import DemandDataset, Observation, coverage
from bike_sharing.models import CANDIDATES, forecast_model, model_configuration
from bike_sharing.rolling import Fold, calendar_folds, count_metrics
from bike_sharing.splits import DEFAULT_SPLIT, StudySplit, partition_dataset
from bike_sharing.study import FrozenSelection, parse_selection, validate_selection_identity


@dataclass(frozen=True, slots=True)
class FrozenIntervalSelection:
    """Bind a point procedure and interval policy; final testing cannot reselect either."""

    point: FrozenSelection
    spec: IntervalSpec = DEFAULT_INTERVAL_SPEC

    def __post_init__(self) -> None:
        if not isinstance(self.point, FrozenSelection) or self.point.protocol != "rolling_origin":
            raise ValueError("intervals require a rolling-origin point selection")
        if not isinstance(self.spec, IntervalSpec):
            raise TypeError("spec must be an IntervalSpec")

    def to_dict(self) -> dict[str, object]:
        """Serialize the complete decision, including the interval configuration hash."""
        return {
            "schema_version": "1.0",
            "point_selection": self.point.to_dict(),
            "interval_specification": self.spec.to_dict(),
            "interval_sha256": self.spec.sha256,
        }


def read_interval_selection(path: Path) -> FrozenIntervalSelection:
    """Read only a validation interval report and reject unsupported or changed settings."""
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("stage") != "interval_validation":
        raise ValueError("selection input must be an interval validation report")
    data = payload.get("interval_selection")
    expected = {"schema_version", "point_selection", "interval_specification", "interval_sha256"}
    if not isinstance(data, dict) or set(data) != expected or data.get("schema_version") != "1.0":
        raise ValueError("invalid interval selection schema")
    spec = IntervalSpec.from_dict(data["interval_specification"])
    if data["interval_sha256"] != spec.sha256:
        raise ValueError("interval configuration hash differs from its specification")
    return FrozenIntervalSelection(parse_selection(data["point_selection"]), spec)


@dataclass(frozen=True, slots=True)
class _Residual:
    timestamp: datetime
    score: float


@dataclass(frozen=True, slots=True)
class _ForecastRow:
    timestamp: datetime
    origin: datetime
    actual: int
    prediction: float
    bands: tuple[IntervalBand, ...]

    @property
    def lead_day(self) -> int:
        return (self.timestamp - self.origin) // timedelta(hours=24) + 1

    @property
    def regime(self) -> str:
        # Descriptive thresholds are fixed before the run and never use observed demand.
        return "low" if self.prediction < 100 else "medium" if self.prediction < 300 else "high"


def _score_intervals(rows: Sequence[_ForecastRow], spec: IntervalSpec) -> dict[str, object]:
    return {
        str(level): interval_metrics(
            [row.actual for row in rows], [row.bands[index] for row in rows], level
        )
        for index, level in enumerate(spec.levels)
    }


def _summarize(rows: Sequence[_ForecastRow], spec: IntervalSpec) -> dict[str, object]:
    return {
        "point": count_metrics([row.actual for row in rows], [row.prediction for row in rows]),
        "intervals": _score_intervals(rows, spec),
        "by_lead_day": {
            str(day): _score_intervals([row for row in rows if row.lead_day == day], spec)
            for day in sorted({row.lead_day for row in rows})
        },
        "by_predicted_demand": {
            regime: _score_intervals([row for row in rows if row.regime == regime], spec)
            for regime in ("low", "medium", "high")
            if any(row.regime == regime for row in rows)
        },
    }


def _window_data(
    dataset: DemandDataset, fold: Fold
) -> tuple[tuple[Observation, ...], tuple[Observation, ...]]:
    training = tuple(item for item in dataset.observations if item.timestamp < fold.origin)
    held_out = tuple(
        item for item in dataset.observations if fold.origin <= item.timestamp < fold.end
    )
    return training, held_out


def _evaluate_intervals(
    dataset: DemandDataset,
    start: datetime,
    end: datetime,
    horizon_hours: int,
    models: tuple[str, ...],
    spec: IntervalSpec,
) -> dict[str, object]:
    # Validate the cadence before constructing the calibration lookback.
    folds = calendar_folds(start, end, horizon_hours)
    window = timedelta(hours=horizon_hours * spec.calibration_folds)
    calibration_start = start - window
    if dataset.observations[0].timestamp >= calibration_start:
        raise ValueError("initial calibration period needs earlier model-fitting observations")
    residuals: dict[str, list[_Residual]] = {model: [] for model in models}
    warmup: list[dict[str, object]] = []
    for fold in calendar_folds(calibration_start, start, horizon_hours):
        training, held_out = _window_data(dataset, fold)
        if held_out:
            for model in models:
                forecasts = forecast_model(
                    model, training, [item.timestamp for item in held_out], origin=fold.origin
                )
                residuals[model].extend(
                    _Residual(item.timestamp, abs(item.count - mean) / residual_scale(mean))
                    for item, mean in zip(held_out, forecasts.values, strict=True)
                )
        warmup.append(
            {
                "origin": fold.origin.isoformat(),
                "end_exclusive": fold.end.isoformat(),
                "training": coverage(training),
                "observations": len(held_out),
                "absent_hours": horizon_hours - len(held_out),
            }
        )
    all_rows: dict[str, list[_ForecastRow]] = {model: [] for model in models}
    reports: list[dict[str, object]] = []
    for fold in folds:
        training, held_out = _window_data(dataset, fold)
        hours = int((fold.end - fold.origin).total_seconds() // 3600)
        calibrators: dict[str, object] = {}
        metrics: dict[str, object] = {}
        for model in models:
            past = [
                item
                for item in residuals[model]
                if fold.origin - window <= item.timestamp < fold.origin
            ]
            residuals[model] = past
            if not held_out:
                continue
            if len(past) < spec.minimum_observations:
                raise ValueError(
                    f"{model} at {fold.origin.isoformat()}: insufficient calibration observations"
                )
            quantiles = tuple(
                residual_quantile([item.score for item in past], level) for level in spec.levels
            )
            calibrators[model] = {
                "observations": len(past),
                "last_residual_timestamp": past[-1].timestamp.isoformat(),
                "quantiles": {
                    str(level): value for level, value in zip(spec.levels, quantiles, strict=True)
                },
            }
            predictions = forecast_model(
                model, training, [item.timestamp for item in held_out], origin=fold.origin
            )
            # Construct all intervals before adding any outcome from this forecast horizon.
            rows = [
                _ForecastRow(
                    item.timestamp,
                    fold.origin,
                    item.count,
                    mean,
                    tuple(make_interval(mean, q) for q in quantiles),
                )
                for item, mean in zip(held_out, predictions.values, strict=True)
            ]
            all_rows[model].extend(rows)
            metrics[model] = _score_intervals(rows, spec)
            residuals[model].extend(
                _Residual(
                    row.timestamp, abs(row.actual - row.prediction) / residual_scale(row.prediction)
                )
                for row in rows
            )
        reports.append(
            {
                "origin": fold.origin.isoformat(),
                "end_exclusive": fold.end.isoformat(),
                "training": coverage(training),
                "horizon_hours": hours,
                "observations": len(held_out),
                "absent_hours": hours - len(held_out),
                "status": "scored" if held_out else "no_observations",
                "calibration_start": (fold.origin - window).isoformat(),
                "calibration_end_exclusive": fold.origin.isoformat(),
                "calibrators": calibrators,
                "metrics": metrics,
            }
        )
    observations = len(all_rows[models[0]])
    if not observations:
        raise ValueError("interval evaluation period has no observed outcomes")
    return {
        "schema_version": "1.0",
        "package_version": version("bike-sharing-forecast"),
        "environment": {
            "python": platform.python_version(),
            "dependencies": {
                name: version(name) for name in ("numpy", "scipy", "scikit-learn", "threadpoolctl")
            },
        },
        "dataset": {"sha256": dataset.sha256, "source_name": dataset.source_name},
        "protocol": {
            "name": "rolling_empirical_residual_intervals",
            "start": start.isoformat(),
            "end_exclusive": end.isoformat(),
            "horizon_hours": horizon_hours,
            "calibration_window_hours": horizon_hours * spec.calibration_folds,
            "initial_calibration_start": calibration_start.isoformat(),
            "initial_calibration_end_exclusive": start.isoformat(),
            "calibration_residuals": "out_of_sample_forecasts_only",
            "calibration_updates": "only_after_complete_horizon",
            "point_fit": "expanding_prefix_before_each_origin",
            "models_evaluated": list(models),
            "point_configuration": model_configuration(),
            "interval_specification": spec.to_dict(),
            "aggregation": "pooled_observed_hours",
            "missing_hours": "excluded_never_zero_filled",
        },
        "warmup_folds": warmup,
        "folds": reports,
        "observations": observations,
        "absent_hours": int((end - start).total_seconds() // 3600) - observations,
        "metrics": {model: _summarize(all_rows[model], spec) for model in models},
    }


def evaluate_interval_validation(
    dataset: DemandDataset,
    split: StudySplit = DEFAULT_SPLIT,
    *,
    horizon_hours: int = 168,
    spec: IntervalSpec = DEFAULT_INTERVAL_SPEC,
) -> dict[str, object]:
    """Assess all fixed candidates and the pre-specified interval policy on validation.

    Select the point model by the original pooled MAE rule. Interval coverage is
    developmental evidence, not independent post-selection or final-test evidence.
    """
    partition_dataset(dataset, split)
    report = _evaluate_intervals(
        dataset, split.validation_start, split.test_start, horizon_hours, CANDIDATES, spec
    )
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    chosen = min(CANDIDATES, key=lambda model: metrics[model]["point"]["mae"])
    point = FrozenSelection(
        chosen,
        dataset.sha256,
        split,
        version("bike-sharing-forecast"),
        "rolling_origin",
        horizon_hours,
    )
    report.update(
        {
            "stage": "interval_validation",
            "test_scored": False,
            "interval_selection": FrozenIntervalSelection(point, spec).to_dict(),
            "selection_rule": "minimum_pooled_validation_mae; interval_settings_prespecified",
            "coverage_is_post_selection_diagnostic": True,
        }
    )
    return report


def evaluate_interval_test(
    dataset: DemandDataset, selection: FrozenIntervalSelection
) -> dict[str, object]:
    """Run only the saved procedure on test, after all development choices are frozen."""
    point = selection.point
    validate_selection_identity(dataset, point)
    partition_dataset(dataset, point.split)
    report = _evaluate_intervals(
        dataset,
        point.split.test_start,
        point.split.test_end,
        point.horizon_hours,
        (point.model,),
        selection.spec,
    )
    report.update(
        {
            "stage": "interval_test",
            "interval_selection": selection.to_dict(),
            "selection_frozen": True,
        }
    )
    return report
