"""Empirical residual intervals and count-support scoring, without coverage guarantees."""

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from statistics import fmean


@dataclass(frozen=True, slots=True)
class IntervalSpec:
    """Fixed calibration policy; a window contains this many complete forecast horizons."""

    levels: tuple[float, ...] = (0.8, 0.9, 0.95)
    calibration_folds: int = 4
    minimum_observations: int = 30

    def __post_init__(self) -> None:
        if not isinstance(self.levels, tuple) or not self.levels:
            raise ValueError("levels must be a nonempty tuple")
        if any(
            type(level) not in (int, float) or not math.isfinite(level) or not 0 < level < 1
            for level in self.levels
        ):
            raise ValueError("coverage levels must be finite numbers strictly between zero and one")
        if tuple(sorted(set(self.levels))) != self.levels:
            raise ValueError("coverage levels must be unique and increasing")
        for name, value in (
            ("calibration_folds", self.calibration_folds),
            ("minimum_observations", self.minimum_observations),
        ):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")

    def to_dict(self) -> dict[str, object]:
        """Record every interval-method choice independently of the point-model settings."""
        return {
            "method": "rolling_scaled_absolute_residual_v1",
            "levels": list(self.levels),
            "calibration_folds": self.calibration_folds,
            "minimum_observations": self.minimum_observations,
            "scale": "sqrt(max(prediction, 1))",
            "quantile_rank": "ceil((n+1)*level)",
            "bounds": "floor(max(0,mean-radius)),ceil(mean+radius)",
            "predicted_demand_thresholds": [100, 300],
            "lead_group_hours": 24,
            "update": "after_complete_forecast_horizon",
            "coverage_guarantee": False,
        }

    @property
    def sha256(self) -> str:
        """Fingerprint the complete interval configuration."""
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()

    @classmethod
    def from_dict(cls, data: object) -> "IntervalSpec":
        """Reject malformed manifests and changes to unsupported method details."""
        if not isinstance(data, dict) or not isinstance(data.get("levels"), list):
            raise ValueError("invalid interval specification")
        folds, minimum = data.get("calibration_folds"), data.get("minimum_observations")
        if type(folds) is not int or type(minimum) is not int:
            raise ValueError("calibration counts must be integers")
        spec = cls(tuple(data["levels"]), folds, minimum)
        if data != spec.to_dict():
            raise ValueError("unsupported interval specification")
        return spec


DEFAULT_INTERVAL_SPEC = IntervalSpec()


def residual_scale(prediction: float) -> float:
    """Use a fixed square-root scale; this does not assume a Poisson distribution."""
    if not math.isfinite(prediction) or prediction < 0:
        raise ValueError("prediction must be finite and nonnegative")
    return math.sqrt(max(prediction, 1.0))


def residual_quantile(scores: Sequence[float], level: float) -> float:
    """Return the conservative empirical order statistic, never interpolate or cap rank.

    The rank adjustment alone does not confer conformal validity on dependent,
    changing-model forecast errors. Insufficient finite support raises an error.
    """
    if type(level) not in (int, float) or not math.isfinite(level) or not 0 < level < 1:
        raise ValueError("level must be strictly between zero and one")
    if not scores or any(not math.isfinite(value) or value < 0 for value in scores):
        raise ValueError("calibration scores must be nonempty, finite and nonnegative")
    rank = int(
        (Decimal(len(scores) + 1) * Decimal(str(level))).to_integral_value(rounding=ROUND_CEILING)
    )
    if rank > len(scores):
        raise ValueError("not enough calibration observations for the requested coverage level")
    return sorted(scores)[rank - 1]


@dataclass(frozen=True, slots=True)
class IntervalBand:
    """Inclusive integer bounds on a nonnegative rental count."""

    lower: int
    upper: int

    def __post_init__(self) -> None:
        if (
            type(self.lower) is not int
            or type(self.upper) is not int
            or not 0 <= self.lower <= self.upper
        ):
            raise ValueError("interval bounds must be ordered nonnegative integers")


def make_interval(prediction: float, quantile: float) -> IntervalBand:
    """Apply the calibrated radius, clip at zero and round bounds outward."""
    scale = residual_scale(prediction)
    if not math.isfinite(quantile) or quantile < 0:
        raise ValueError("quantile must be finite and nonnegative")
    radius = quantile * scale
    if not math.isfinite(prediction + radius):
        raise ValueError("interval endpoint is not finite")
    return IntervalBand(math.floor(max(0.0, prediction - radius)), math.ceil(prediction + radius))


def interval_metrics(
    actual: Sequence[int], bands: Sequence[IntervalBand], level: float
) -> dict[str, float | int]:
    """Report inclusive coverage, width and the negatively oriented interval score."""
    if not actual or len(actual) != len(bands):
        raise ValueError("actual and intervals must have equal nonzero lengths")
    if any(type(value) is not int or value < 0 for value in actual):
        raise ValueError("actual values must be nonnegative integer counts")
    if type(level) not in (int, float) or not math.isfinite(level) or not 0 < level < 1:
        raise ValueError("level must be strictly between zero and one")
    below = sum(value < band.lower for value, band in zip(actual, bands, strict=True))
    above = sum(value > band.upper for value, band in zip(actual, bands, strict=True))
    scores = [
        band.upper
        - band.lower
        + 2 / (1 - level) * (max(band.lower - value, 0) + max(value - band.upper, 0))
        for value, band in zip(actual, bands, strict=True)
    ]
    return {
        "nominal_coverage": level,
        "observations": len(actual),
        "empirical_coverage": 1 - (below + above) / len(actual),
        "mean_width": fmean(band.upper - band.lower for band in bands),
        "mean_interval_score": fmean(scores),
        "below_lower": below,
        "above_upper": above,
    }
