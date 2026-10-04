"""Validation-only baseline selection and an explicit frozen-selection final test."""

import json
import platform
import re
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from bike_sharing.data import DemandDataset, coverage
from bike_sharing.forecasting import error_metrics, evaluate, forecast_baselines
from bike_sharing.splits import DEFAULT_SPLIT, StudySplit, partition_dataset

BASELINES = ("training_mean", "hour_of_week_mean")


@dataclass(frozen=True, slots=True)
class FrozenSelection:
    """A baseline choice bound to a dataset, split and package version.

    This is an explicit experiment artifact, not a tamper-proof access control.
    Selection must be made on validation; test outcomes never choose the model.
    """

    model: str
    dataset_sha256: str
    split: StudySplit
    package_version: str

    def __post_init__(self) -> None:
        if self.model not in BASELINES:
            raise ValueError(f"model must be one of {BASELINES}")
        if not isinstance(self.dataset_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.dataset_sha256
        ):
            raise ValueError("dataset_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(self.split, StudySplit):
            raise TypeError("split must be a StudySplit")
        if not isinstance(self.package_version, str) or not self.package_version:
            raise ValueError("package_version must be a nonempty string")

    def to_dict(self) -> dict[str, str]:
        """Serialize the exact settings needed to refit and evaluate one baseline."""
        return {
            "schema_version": "1.0",
            "model": self.model,
            "dataset_sha256": self.dataset_sha256,
            "package_version": self.package_version,
            "selection_metric": "validation_mae",
            **self.split.to_dict(),
        }


def select_on_validation(
    dataset: DemandDataset, split: StudySplit = DEFAULT_SPLIT
) -> dict[str, object]:
    """Compare both baselines using validation MAE and save the choice, never test scores.

    Both fits use only the initial training partition and remain frozen throughout
    validation. MAE ties prefer training_mean, the simpler candidate. This first
    protocol is fixed-origin; rolling-origin comparisons remain on the roadmap.
    """
    partitions = partition_dataset(dataset, split)
    horizon = int((split.test_start - split.validation_start).total_seconds() // 3600)
    report = evaluate(dataset, split.validation_start, horizon, split=split)
    timestamps = tuple(item.timestamp for item in partitions.validation)
    predictions = forecast_baselines(partitions.training, timestamps)
    actual = tuple(item.count for item in partitions.validation)
    # Use only validation errors. Test labels are not passed to fitting or selection.
    scores = {model: error_metrics(actual, predictions[model])["mae"] for model in BASELINES}
    chosen = min(BASELINES, key=lambda model: scores[model])
    selection = FrozenSelection(chosen, dataset.sha256, split, version("bike-sharing-forecast"))
    report["stage"] = "validation"
    report["selection"] = selection.to_dict()
    report["selection_rule"] = "minimum_validation_mae; ties_prefer_training_mean"
    report["test_scored"] = False
    return report


def read_selection(path: Path) -> FrozenSelection:
    """Load a selection embedded in a validation report; reject malformed artifacts."""
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("stage") != "validation":
        raise ValueError("selection input must be a validation report")
    data = payload.get("selection")
    expected = {
        "schema_version",
        "model",
        "dataset_sha256",
        "package_version",
        "selection_metric",
        "validation_start",
        "test_start",
        "test_end",
    }
    if (
        not isinstance(data, dict)
        or set(data) != expected
        or not all(isinstance(value, str) for value in data.values())
    ):
        raise ValueError("validation report contains an invalid selection schema")
    if data["schema_version"] != "1.0" or data["selection_metric"] != "validation_mae":
        raise ValueError("unsupported selection schema or metric")
    split = StudySplit(
        *(
            datetime.fromisoformat(data[key])
            for key in ("validation_start", "test_start", "test_end")
        )
    )
    return FrozenSelection(data["model"], data["dataset_sha256"], split, data["package_version"])


def evaluate_test(dataset: DemandDataset, selection: FrozenSelection) -> dict[str, object]:
    """Refit the chosen baseline on train + validation, then score only that test forecast.

    The model and boundaries come from the saved selection, never from test
    performance. The refit is frozen for the complete test partition. This
    function must only be used after the modelling approach has been finalized.
    """
    if dataset.sha256 != selection.dataset_sha256:
        raise ValueError("dataset checksum differs from the frozen selection")
    if version("bike-sharing-forecast") != selection.package_version:
        raise ValueError("package version differs from the frozen selection; revalidate first")
    partitions = partition_dataset(dataset, selection.split)
    training = partitions.training + partitions.validation
    timestamps = tuple(item.timestamp for item in partitions.test)
    prediction = forecast_baselines(training, timestamps)[selection.model]
    actual = tuple(item.count for item in partitions.test)
    horizon = int((selection.split.test_end - selection.split.test_start).total_seconds() // 3600)
    return {
        "schema_version": "1.0",
        "stage": "test",
        "selection": selection.to_dict(),
        "package_version": selection.package_version,
        "python_version": platform.python_version(),
        "dataset": {"source_name": dataset.source_name, "sha256": dataset.sha256},
        "protocol": {
            "name": "frozen_selection_final_test",
            "refit_on": "training_plus_validation",
            "training": coverage(training),
            "cutoff_inclusive": selection.split.test_start.isoformat(),
            "end_exclusive": selection.split.test_end.isoformat(),
            "horizon_hours": horizon,
            "evaluation_observations": len(partitions.test),
            "absent_evaluation_hours": horizon - len(partitions.test),
            "refit_during_horizon": False,
            "features": ["weekday", "hour"],
            "missing_hours": "excluded_from_scoring_not_imputed",
        },
        "metrics": {selection.model: error_metrics(actual, prediction)},
    }
