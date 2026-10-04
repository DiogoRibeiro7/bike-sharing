"""Validation-only model selection and final testing under the saved forecast procedure."""

import hashlib
import json
import platform
import re
from dataclasses import dataclass, field
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from bike_sharing.data import DemandDataset, coverage
from bike_sharing.forecasting import error_metrics, evaluate, forecast_baselines
from bike_sharing.models import CANDIDATES, model_configuration
from bike_sharing.rolling import _evaluate_period
from bike_sharing.splits import DEFAULT_SPLIT, StudySplit, partition_dataset

BASELINES = ("training_mean", "hour_of_week_mean")


def configuration_digest() -> str:
    """Bind selections to the fixed candidate definitions, including penalty and features."""
    encoded = json.dumps(model_configuration(), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class FrozenSelection:
    """A model and refit policy bound to a dataset, split, configuration and version.

    This is an explicit experiment artifact, not a tamper-proof access control.
    Selection must be made on validation; test outcomes never choose the model.
    """

    model: str
    dataset_sha256: str
    split: StudySplit
    package_version: str
    protocol: str = "fixed_origin"
    horizon_hours: int = 168
    configuration_sha256: str = field(default_factory=configuration_digest)

    def __post_init__(self) -> None:
        if self.protocol not in ("fixed_origin", "rolling_origin"):
            raise ValueError("unsupported selection protocol")
        allowed = CANDIDATES if self.protocol == "rolling_origin" else BASELINES
        if self.model not in allowed:
            raise ValueError(f"model must be one of {allowed}")
        if type(self.horizon_hours) is not int or self.horizon_hours <= 0:
            raise ValueError("horizon_hours must be a positive integer")
        if not isinstance(self.configuration_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.configuration_sha256
        ):
            raise ValueError("configuration_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(self.dataset_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.dataset_sha256
        ):
            raise ValueError("dataset_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(self.split, StudySplit):
            raise TypeError("split must be a StudySplit")
        if not isinstance(self.package_version, str) or not self.package_version:
            raise ValueError("package_version must be a nonempty string")

    def to_dict(self) -> dict[str, str]:
        """Serialize the settings needed to refit and evaluate one forecasting procedure."""
        return {
            "schema_version": "2.0",
            "model": self.model,
            "protocol": self.protocol,
            "horizon_hours": str(self.horizon_hours),
            "configuration_sha256": self.configuration_sha256,
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
    protocol is fixed-origin; select_rolling_on_validation provides weekly refits.
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


def select_rolling_on_validation(
    dataset: DemandDataset, split: StudySplit = DEFAULT_SPLIT, *, horizon_hours: int = 168
) -> dict[str, object]:
    """Select among fixed candidates by pooled validation MAE, never final-test errors.

    Prior validation observations may enter later fitting histories once available.
    No hyperparameter search is performed; each fit and forecast is origin-specific.
    """
    partition_dataset(dataset, split)
    report = _evaluate_period(
        dataset, split.validation_start, split.test_start, horizon_hours, CANDIDATES
    )
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    chosen = min(CANDIDATES, key=lambda model: metrics[model]["mae"])
    selection = FrozenSelection(
        chosen,
        dataset.sha256,
        split,
        version("bike-sharing-forecast"),
        "rolling_origin",
        horizon_hours,
    )
    report.update(
        {
            "stage": "validation",
            "study_split": split.to_dict(),
            "test_scored": False,
            "selection": selection.to_dict(),
            "selection_rule": "minimum_pooled_validation_mae; exact_ties_use_candidate_order",
        }
    )
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
    if isinstance(data, dict) and data.get("schema_version") == "2.0":
        expected |= {"protocol", "horizon_hours", "configuration_sha256"}
    if (
        not isinstance(data, dict)
        or set(data) != expected
        or not all(isinstance(value, str) for value in data.values())
    ):
        raise ValueError("validation report contains an invalid selection schema")
    if data["schema_version"] not in ("1.0", "2.0") or data["selection_metric"] != "validation_mae":
        raise ValueError("unsupported selection schema or metric")
    split = StudySplit(
        *(
            datetime.fromisoformat(data[key])
            for key in ("validation_start", "test_start", "test_end")
        )
    )
    if data["schema_version"] == "1.0":
        return FrozenSelection(
            data["model"], data["dataset_sha256"], split, data["package_version"]
        )
    return FrozenSelection(
        data["model"],
        data["dataset_sha256"],
        split,
        data["package_version"],
        data["protocol"],
        int(data["horizon_hours"]),
        data["configuration_sha256"],
    )


def evaluate_test(dataset: DemandDataset, selection: FrozenSelection) -> dict[str, object]:
    """Evaluate only the chosen model using its saved fixed or rolling test procedure.

    The model and boundaries come from the saved selection, never from test
    performance. Fixed-origin selections freeze the refit for the full quarter;
    rolling selections refit at the saved cadence using only then-available
    outcomes. Use this function only after the modelling approach is finalized.
    """
    if dataset.sha256 != selection.dataset_sha256:
        raise ValueError("dataset checksum differs from the frozen selection")
    if version("bike-sharing-forecast") != selection.package_version:
        raise ValueError("package version differs from the frozen selection; revalidate first")
    if selection.configuration_sha256 != configuration_digest():
        raise ValueError("model configuration differs from the frozen selection; revalidate first")
    partitions = partition_dataset(dataset, selection.split)
    if selection.protocol == "rolling_origin":
        report = _evaluate_period(
            dataset,
            selection.split.test_start,
            selection.split.test_end,
            selection.horizon_hours,
            (selection.model,),
        )
        report.update({"stage": "test", "selection": selection.to_dict(), "selection_frozen": True})
        return report
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
