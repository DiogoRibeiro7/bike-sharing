"""Scenario-based workload planning under asymmetric error costs.

Costs are assumptions in normalized units. Observed rentals are a workload proxy,
not unconstrained demand, inventory requirements or evidence of realised savings.
"""

import hashlib
import json
import math
import platform
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from importlib.metadata import version
from pathlib import Path
from statistics import fmean

from bike_sharing.calibration import residual_scale
from bike_sharing.data import DemandDataset, coverage
from bike_sharing.models import CANDIDATES, forecast_model
from bike_sharing.rolling import calendar_folds
from bike_sharing.splits import DEFAULT_SPLIT, StudySplit, partition_dataset
from bike_sharing.study import FrozenSelection, parse_selection, validate_selection_identity

COST_RATIOS = (0.25, 0.5, 1.0, 2.0, 4.0, 9.0)
POLICIES = (*CANDIDATES, "poisson_residual_quantile")
CALIBRATION_FOLDS = 4
MINIMUM_RESIDUALS = 30


def planning_configuration() -> dict[str, object]:
    """Record the pre-specified decision, scenarios and policy definitions."""
    return {
        "method": "aggregate_workload_asymmetric_loss_v1",
        "decision": "continuous_nonnegative_hourly_rental_equivalent_workload",
        "cost_units": "assumed_normalized_units_not_currency",
        "overprediction_cost": 1.0,
        "underprediction_costs": list(COST_RATIOS),
        "policies": list(POLICIES),
        "reference_model": "poisson_calendar",
        "calibration_folds": CALIBRATION_FOLDS,
        "minimum_residuals": MINIMUM_RESIDUALS,
        "residual": "(actual-prediction)/sqrt(max(prediction,1))",
        "quantile_rank": "ceil(n*ratio/(1+ratio)); one_based",
        "action": "max(0,prediction+sqrt(max(prediction,1))*signed_quantile)",
        "rounding": "none_continuous_workload",
        "selection": "minimum_pooled_validation_cost_per_ratio; ties_follow_policy_order",
    }


def planning_digest() -> str:
    """Identify the complete scenario and decision specification."""
    return hashlib.sha256(json.dumps(planning_configuration(), sort_keys=True).encode()).hexdigest()


def cost_metrics(
    actual: Sequence[int], actions: Sequence[float], ratio: float
) -> dict[str, float | int]:
    """Score r*(y-a)+ + (a-y)+, including separate shortage/excess components."""
    if not actual or len(actual) != len(actions):
        raise ValueError("actual and actions must have equal nonzero lengths")
    if any(type(y) is not int or y < 0 for y in actual):
        raise ValueError("actual must contain nonnegative integer counts")
    if any(not math.isfinite(a) or a < 0 for a in actions):
        raise ValueError("actions must be finite and nonnegative")
    if type(ratio) not in (int, float) or not math.isfinite(ratio) or ratio <= 0:
        raise ValueError("cost ratio must be finite and positive")
    under = fmean(max(y - a, 0.0) for y, a in zip(actual, actions, strict=True))
    over = fmean(max(a - y, 0.0) for y, a in zip(actual, actions, strict=True))
    return {
        "observations": len(actual),
        "mean_cost": ratio * under + over,
        "mean_underprediction": under,
        "mean_overprediction": over,
        "mean_action": fmean(actions),
        "underprediction_fraction": fmean(y > a for y, a in zip(actual, actions, strict=True)),
    }


def signed_quantile(scores: Sequence[float], ratio: float) -> float:
    """Minimize empirical asymmetric loss with the lower empirical quantile.

    Unlike the interval rank, this is ceil(n*tau), tau=r/(1+r). It is an
    empirical decision rule, with no conditional-distribution validity claim.
    """
    if not scores or any(not math.isfinite(s) for s in scores):
        raise ValueError("residual scores must be nonempty and finite")
    if type(ratio) not in (int, float) or not math.isfinite(ratio) or ratio <= 0:
        raise ValueError("cost ratio must be finite and positive")
    r = Decimal(str(ratio))
    rank = int((Decimal(len(scores)) * r / (1 + r)).to_integral_value(rounding=ROUND_CEILING))
    return sorted(scores)[rank - 1]


def workload_action(prediction: float, adjustment: float) -> float:
    """Transform a signed standardized residual quantile into a workload target."""
    scale = residual_scale(prediction)
    if not math.isfinite(adjustment):
        raise ValueError("adjustment must be finite")
    action = prediction + scale * adjustment
    if not math.isfinite(action):
        raise ValueError("action must be finite")
    return max(0.0, action)


@dataclass(frozen=True, slots=True)
class FrozenPlanningSelection:
    """Bind one validation-chosen policy per fixed cost scenario to a data identity."""

    reference: FrozenSelection
    policies: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            self.reference.protocol != "rolling_origin"
            or self.reference.model != "poisson_calendar"
        ):
            raise ValueError("reference must be a rolling Poisson selection")
        if (
            not isinstance(self.policies, tuple)
            or len(self.policies) != len(COST_RATIOS)
            or any(p not in POLICIES for p in self.policies)
        ):
            raise ValueError("one known policy is required for each fixed cost ratio")

    def to_dict(self) -> dict[str, object]:
        """Serialize identities, policy choices and the fixed planning configuration."""
        return {
            "schema_version": "1.0",
            "reference_point": self.reference.to_dict(),
            "policies": dict(zip(map(str, COST_RATIOS), self.policies, strict=True)),
            "configuration": planning_configuration(),
            "configuration_sha256": planning_digest(),
        }


def read_planning_selection(path: Path) -> FrozenPlanningSelection:
    """Read only planning-validation reports; reject altered or unsupported settings."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("stage") != "planning_validation":
        raise ValueError("selection must come from a planning validation report")
    data = payload.get("planning_selection")
    if not isinstance(data, dict) or set(data) != {
        "schema_version",
        "reference_point",
        "policies",
        "configuration",
        "configuration_sha256",
    }:
        raise ValueError("invalid planning selection schema")
    if (
        data["schema_version"] != "1.0"
        or data["configuration"] != planning_configuration()
        or data["configuration_sha256"] != planning_digest()
    ):
        raise ValueError("planning configuration differs; revalidate first")
    choices = data["policies"]
    if not isinstance(choices, dict) or set(choices) != set(map(str, COST_RATIOS)):
        raise ValueError("invalid scenario policy choices")
    return FrozenPlanningSelection(
        parse_selection(data["reference_point"]), tuple(choices[str(r)] for r in COST_RATIOS)
    )


def _evaluate_planning(
    dataset: DemandDataset,
    start: datetime,
    end: datetime,
    horizon: int,
    choices: dict[float, tuple[str, ...]],
) -> dict[str, object]:
    folds = calendar_folds(start, end, horizon)
    window = timedelta(hours=horizon * CALIBRATION_FOLDS)
    needs_residuals = any("poisson_residual_quantile" in p for p in choices.values())
    active = {p for policies in choices.values() for p in policies}
    models = tuple(
        m for m in CANDIDATES if m in active or (m == "poisson_calendar" and needs_residuals)
    )
    residuals: list[tuple[datetime, float]] = []
    warmup: list[dict[str, object]] = []
    if needs_residuals:
        if dataset.observations[0].timestamp >= start - window:
            raise ValueError("calibration needs earlier fitting history")
        for fold in calendar_folds(start - window, start, horizon):
            training = tuple(o for o in dataset.observations if o.timestamp < fold.origin)
            held = tuple(o for o in dataset.observations if fold.origin <= o.timestamp < fold.end)
            if held:
                pred = forecast_model(
                    "poisson_calendar", training, [o.timestamp for o in held], origin=fold.origin
                )
                residuals.extend(
                    (o.timestamp, (o.count - mu) / residual_scale(mu))
                    for o, mu in zip(held, pred.values, strict=True)
                )
            warmup.append(
                {
                    "origin": fold.origin.isoformat(),
                    "end_exclusive": fold.end.isoformat(),
                    "training": coverage(training),
                    "observations": len(held),
                    "absent_hours": horizon - len(held),
                }
            )
    actual: list[int] = []
    actions: dict[float, dict[str, list[float]]] = {
        r: {p: [] for p in policies} for r, policies in choices.items()
    }
    reports: list[dict[str, object]] = []
    for fold in folds:
        training = tuple(o for o in dataset.observations if o.timestamp < fold.origin)
        held = tuple(o for o in dataset.observations if fold.origin <= o.timestamp < fold.end)
        residuals = [(t, s) for t, s in residuals if fold.origin - window <= t < fold.origin]
        calibration_count = len(residuals)
        last_residual = residuals[-1][0].isoformat() if residuals else None
        metrics: dict[str, object] = {}
        quantiles: dict[str, float] = {}
        if held:
            if needs_residuals and len(residuals) < MINIMUM_RESIDUALS:
                raise ValueError("insufficient past calibration residuals")
            predictions = {
                m: forecast_model(
                    m, training, [o.timestamp for o in held], origin=fold.origin
                ).values
                for m in models
            }
            y = [o.count for o in held]
            actual.extend(y)
            for ratio, policies in choices.items():
                fold_metrics: dict[str, object] = {}
                if "poisson_residual_quantile" in policies:
                    quantiles[str(ratio)] = signed_quantile([s for _, s in residuals], ratio)
                for policy in policies:
                    a = (
                        [
                            workload_action(mu, quantiles[str(ratio)])
                            for mu in predictions["poisson_calendar"]
                        ]
                        if policy == "poisson_residual_quantile"
                        else list(predictions[policy])
                    )
                    actions[ratio][policy].extend(a)
                    fold_metrics[policy] = cost_metrics(y, a, ratio)
                metrics[str(ratio)] = fold_metrics
            # Current-horizon outcomes enter calibration only after every action is fixed.
            if needs_residuals:
                residuals.extend(
                    (o.timestamp, (o.count - mu) / residual_scale(mu))
                    for o, mu in zip(held, predictions["poisson_calendar"], strict=True)
                )
        reports.append(
            {
                "origin": fold.origin.isoformat(),
                "end_exclusive": fold.end.isoformat(),
                "training": coverage(training),
                "observations": len(held),
                "absent_hours": int((fold.end - fold.origin).total_seconds() / 3600) - len(held),
                "status": "scored" if held else "no_observations",
                "calibration_start": (fold.origin - window).isoformat()
                if needs_residuals
                else None,
                "calibration_end_exclusive": fold.origin.isoformat() if needs_residuals else None,
                "calibration_observations": calibration_count,
                "last_calibration_timestamp": last_residual,
                "signed_quantiles": quantiles,
                "metrics": metrics,
            }
        )
    if not actual:
        raise ValueError("evaluation requires observed outcomes")
    return {
        "schema_version": "1.0",
        "package_version": version("bike-sharing-forecast"),
        "environment": {
            "python": platform.python_version(),
            "dependencies": {
                n: version(n) for n in ("numpy", "scipy", "scikit-learn", "threadpoolctl")
            },
        },
        "dataset": {"sha256": dataset.sha256, "source_name": dataset.source_name},
        "configuration": planning_configuration(),
        "protocol": {
            "start": start.isoformat(),
            "end_exclusive": end.isoformat(),
            "horizon_hours": horizon,
            "fit": "expanding_prefix_before_origin",
            "calibration": "past_out_of_sample_errors_only",
            "missing_hours": "excluded_never_zero_filled",
            "aggregation": "pooled_observed_hours",
        },
        "warmup_folds": warmup,
        "folds": reports,
        "observations": len(actual),
        "metrics": {
            str(r): {p: cost_metrics(actual, a, r) for p, a in policies.items()}
            for r, policies in actions.items()
        },
    }


def evaluate_planning_validation(
    dataset: DemandDataset, split: StudySplit = DEFAULT_SPLIT, *, horizon_hours: int = 168
) -> dict[str, object]:
    """Compare fixed policies and select per assumed cost ratio using validation only."""
    partition_dataset(dataset, split)
    report = _evaluate_planning(
        dataset,
        split.validation_start,
        split.test_start,
        horizon_hours,
        {r: POLICIES for r in COST_RATIOS},
    )
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    policies = tuple(
        min(POLICIES, key=lambda p: metrics[str(r)][p]["mean_cost"]) for r in COST_RATIOS
    )
    reference = FrozenSelection(
        "poisson_calendar",
        dataset.sha256,
        split,
        version("bike-sharing-forecast"),
        "rolling_origin",
        horizon_hours,
    )
    report.update(
        {
            "stage": "planning_validation",
            "test_scored": False,
            "planning_selection": FrozenPlanningSelection(reference, policies).to_dict(),
            "selection_evidence": "developmental_not_independent_final_assessment",
        }
    )
    return report


def evaluate_planning_test(
    dataset: DemandDataset, selection: FrozenPlanningSelection
) -> dict[str, object]:
    """Assess only each saved policy; earlier test counts update on the frozen schedule."""
    reference = selection.reference
    validate_selection_identity(dataset, reference)
    partition_dataset(dataset, reference.split)
    report = _evaluate_planning(
        dataset,
        reference.split.test_start,
        reference.split.test_end,
        reference.horizon_hours,
        {r: (p,) for r, p in zip(COST_RATIOS, selection.policies, strict=True)},
    )
    report.update(
        {
            "stage": "planning_test",
            "selection_frozen": True,
            "planning_selection": selection.to_dict(),
        }
    )
    return report
