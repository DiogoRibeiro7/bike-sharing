"""Verify calendar lags, count models and the information boundary at every origin."""

import csv
import json
import math
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean

import numpy as np
import pytest
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import PoissonRegressor

from bike_sharing import rolling
from bike_sharing.cli import main
from bike_sharing.data import DemandDataset, Observation
from bike_sharing.models import (
    FEATURE_NAMES,
    Forecast,
    calendar_features,
    forecast_model,
)
from bike_sharing.rolling import _evaluate_period, calendar_folds, count_metrics
from bike_sharing.splits import DEFAULT_SPLIT, StudySplit
from bike_sharing.study import (
    evaluate_test,
    read_selection,
    select_rolling_on_validation,
)

START = datetime(2012, 1, 1)
SPLIT = StudySplit(
    START + timedelta(days=14), START + timedelta(days=28), START + timedelta(days=42)
)


@pytest.fixture
def dataset() -> DemandDataset:
    return DemandDataset(
        tuple(Observation(START + timedelta(hours=h), 10 + h % 168) for h in range(42 * 24)),
        "a" * 64,
        "synthetic.csv",
    )


def test_calendar_encoding_is_fixed_and_coefficients_reconstruct_forecasts(
    dataset: DemandDataset,
) -> None:
    times = [SPLIT.validation_start + timedelta(hours=h) for h in range(24)]
    features = calendar_features(times)
    assert features.shape == (24, 57)
    np.testing.assert_array_equal(features[0], calendar_features(times[:1])[0])
    assert features[1, FEATURE_NAMES.index("hour_01")] == 1
    assert features[1, FEATURE_NAMES.index("weekend_hour_01")] == 1
    assert calendar_features([]).shape == (0, 57)
    training = dataset.observations[:336]
    fitted = forecast_model("poisson_calendar", training, times, origin=SPLIT.validation_start)
    coefficients = fitted.details["coefficients"]
    assert isinstance(coefficients, dict)
    intercept = fitted.details["intercept"]
    assert isinstance(intercept, float)
    reconstructed = np.exp(
        features @ np.array([coefficients[name] for name in FEATURE_NAMES]) + intercept
    )
    np.testing.assert_allclose(fitted.values, reconstructed, rtol=1e-12)
    assert all(math.isfinite(value) and value > 0 for value in fitted.values)


def test_poisson_constant_and_all_zero_histories(dataset: DemandDataset) -> None:
    for count in (0, 8):
        training = tuple(replace(item, count=count) for item in dataset.observations[:336])
        result = forecast_model(
            "poisson_calendar", training, [SPLIT.validation_start], origin=SPLIT.validation_start
        )
        assert result.values == pytest.approx((float(count),))
    assert result.details["fit_status"] == "constant_training"


def test_seasonal_naive_uses_calendar_lags_and_repeats_without_future_actuals(
    dataset: DemandDataset,
) -> None:
    training = tuple(
        replace(item, count=index) for index, item in enumerate(dataset.observations[:336])
    )
    times = [SPLIT.validation_start + timedelta(hours=h) for h in (0, 1, 168, 336)]
    result = forecast_model("seasonal_naive", training, times, origin=SPLIT.validation_start)
    assert result.values == (168.0, 169.0, 168.0, 168.0)
    missing = training[:168] + training[169:]
    result = forecast_model("seasonal_naive", missing, times, origin=SPLIT.validation_start)
    mean = fmean(item.count for item in missing)
    assert result.values == (mean, 169.0, mean, mean)
    assert result.details["missing_lag_fallbacks"] == 3


def test_forecast_boundaries_and_solver_failures(
    dataset: DemandDataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    train = dataset.observations[:336]
    with pytest.raises(ValueError, match="unknown model"):
        forecast_model("unknown", train, [SPLIT.validation_start], origin=SPLIT.validation_start)
    with pytest.raises(ValueError, match="precede"):
        forecast_model(
            "seasonal_naive", train, [SPLIT.validation_start], origin=train[-1].timestamp
        )
    with pytest.raises(ValueError, match="at least one"):
        forecast_model("seasonal_naive", train, [], origin=SPLIT.validation_start)
    with pytest.raises(ValueError, match="at or after"):
        forecast_model("poisson_calendar", train, [START], origin=SPLIT.validation_start)

    def fail(*args: object, **kwargs: object) -> None:
        raise ConvergenceWarning("synthetic nonconvergence")

    monkeypatch.setattr(PoissonRegressor, "fit", fail)
    with pytest.raises(ValueError, match="Poisson fitting/prediction failed"):
        forecast_model(
            "poisson_calendar", train, [SPLIT.validation_start], origin=SPLIT.validation_start
        )


def test_count_metrics_include_zero_outcomes_and_zero_predictions() -> None:
    result = count_metrics([0, 2], [1.0, 1.0])
    assert result["mae"] == result["rmse"] == 1
    assert result["mean_poisson_deviance"] == pytest.approx(2 * math.log(2))
    zero = count_metrics([2], [0.0])
    assert zero["mae"] == zero["rmse"] == 2
    assert zero["mean_poisson_deviance"] == pytest.approx(2 * (2 * math.log(2 / 1e-9) - 2 + 1e-9))


def test_folds_cover_validation_only_and_include_short_tail() -> None:
    folds = calendar_folds(DEFAULT_SPLIT.validation_start, DEFAULT_SPLIT.test_start)
    assert len(folds) == 14
    assert folds[-1].end == DEFAULT_SPLIT.test_start
    assert folds[-1].end - folds[-1].origin == timedelta(hours=24)
    assert all(left.end == right.origin for left, right in zip(folds, folds[1:], strict=False))
    for horizon in (0, -1, True):
        with pytest.raises(ValueError, match="positive integer"):
            calendar_folds(START, SPLIT.test_start, horizon)
    with pytest.raises(ValueError, match="precede"):
        calendar_folds(START, START)


def test_pooling_weights_observations_not_fold_means() -> None:
    counts = [1, 1, 1, 1, 3, 3, 9]
    dataset = DemandDataset(
        tuple(Observation(START + timedelta(hours=i), y) for i, y in enumerate(counts)),
        "a" * 64,
        "tiny.csv",
    )
    report = _evaluate_period(
        dataset, START + timedelta(hours=4), START + timedelta(hours=7), 2, ("training_mean",)
    )
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["training_mean"] == count_metrics([3, 3, 9], [1.0, 1.0, 10 / 6])
    assert metrics["training_mean"]["mae"] != pytest.approx((2 + (9 - 10 / 6)) / 2)


def test_gap_accounting_and_empty_folds(dataset: DemandDataset) -> None:
    observations = tuple(
        item
        for item in dataset.observations
        if not SPLIT.validation_start <= item.timestamp < SPLIT.validation_start + timedelta(days=7)
    )
    sparse = replace(dataset, observations=observations)
    report = _evaluate_period(
        sparse, SPLIT.validation_start, SPLIT.test_start, 168, ("seasonal_naive",)
    )
    folds = report["folds"]
    assert isinstance(folds, list)
    assert folds[0]["status"] == "no_observations"
    assert folds[0]["metrics"] == {}
    assert report["absent_evaluation_hours"] == 168
    assert folds[1]["fit_diagnostics"]["seasonal_naive"]["missing_lag_fallbacks"] == 168
    with pytest.raises(ValueError, match="no observed outcomes"):
        _evaluate_period(
            sparse,
            SPLIT.validation_start,
            SPLIT.validation_start + timedelta(days=7),
            168,
            ("training_mean",),
        )
    with pytest.raises(ValueError, match="known candidates"):
        _evaluate_period(dataset, SPLIT.validation_start, SPLIT.test_start, 168, ("bad",))
    with pytest.raises(ValueError, match="within the dataset"):
        _evaluate_period(dataset, START, SPLIT.test_start, 168, ("training_mean",))


def test_selection_ignores_test_labels_and_each_fit_sees_only_its_prefix(
    dataset: DemandDataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rolling, "perf_counter", lambda: 0.0)
    calls: list[tuple[datetime, datetime]] = []
    predictions: list[tuple[float, ...]] = []

    def spy(
        model: str, training: Sequence[Observation], times: Sequence[datetime], *, origin: datetime
    ) -> Forecast:
        calls.append((training[-1].timestamp, origin))
        result = forecast_model(model, training, times, origin=origin)
        predictions.append(result.values)
        return result

    monkeypatch.setattr(rolling, "forecast_model", spy)
    first = select_rolling_on_validation(dataset, SPLIT)
    assert all(last < origin < SPLIT.test_start for last, origin in calls)
    first_predictions = predictions.copy()
    changed = replace(
        dataset,
        observations=tuple(
            replace(item, count=1_000_000) if item.timestamp >= SPLIT.test_start else item
            for item in dataset.observations
        ),
    )
    assert select_rolling_on_validation(changed, SPLIT) == first
    assert first["test_scored"] is False
    # Change the second validation fold: first-fold predictions cannot change.
    changed_validation = replace(
        dataset,
        observations=tuple(
            replace(item, count=999)
            if item.timestamp >= SPLIT.validation_start + timedelta(days=7)
            else item
            for item in dataset.observations
        ),
    )
    predictions.clear()
    select_rolling_on_validation(changed_validation, SPLIT)
    assert predictions[:4] == first_predictions[:4]


def test_tie_order_and_rolling_final_refit_contract(dataset: DemandDataset, tmp_path: Path) -> None:
    constant = replace(
        dataset, observations=tuple(replace(item, count=8) for item in dataset.observations)
    )
    report = select_rolling_on_validation(constant, SPLIT)
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(report))
    selection = read_selection(path)
    assert selection.model == "training_mean"
    assert selection.protocol == "rolling_origin" and selection.horizon_hours == 168
    # Earlier test outcomes enter the next scheduled refit, never the first fit.
    changed = replace(
        constant,
        observations=tuple(
            replace(item, count=80)
            if SPLIT.test_start <= item.timestamp < SPLIT.test_start + timedelta(days=7)
            else item
            for item in constant.observations
        ),
    )
    final = evaluate_test(changed, selection)
    folds = final["folds"]
    assert isinstance(folds, list)
    assert set(folds[0]["metrics"]) == {"training_mean"}
    assert folds[0]["metrics"]["training_mean"]["mae"] == 72
    assert folds[1]["metrics"]["training_mean"]["mae"] == pytest.approx(14.4)
    assert folds[0]["training"]["last_timestamp"] < folds[0]["origin"]
    assert final["selection"] == report["selection"]
    with pytest.raises(ValueError, match="configuration differs"):
        evaluate_test(dataset, replace(selection, configuration_sha256="b" * 64))
    for kwargs in ({"protocol": "bad"}, {"horizon_hours": 0}, {"configuration_sha256": "invalid"}):
        with pytest.raises(ValueError):
            replace(selection, **kwargs)
    legacy = {
        key: value
        for key, value in selection.to_dict().items()
        if key not in {"protocol", "horizon_hours", "configuration_sha256"}
    }
    legacy["schema_version"] = "1.0"
    path.write_text(json.dumps({"stage": "validation", "selection": legacy}))
    assert read_selection(path).protocol == "fixed_origin"


def test_rolling_cli_and_final_protocol_overrides(
    dataset: DemandDataset, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, artifact = tmp_path / "data.csv", tmp_path / "validation.json"
    with source.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Date", "Hour", "Total Users", "Casual Users", "Registered Users"])
        for item in dataset.observations:
            writer.writerow(
                [
                    item.timestamp.strftime("%m/%d/%Y"),
                    item.timestamp.hour,
                    item.count,
                    0,
                    item.count,
                ]
            )
    args = [
        "--data",
        str(source),
        "--validation-start",
        SPLIT.validation_start.isoformat(),
        "--test-start",
        SPLIT.test_start.isoformat(),
        "--test-end",
        SPLIT.test_end.isoformat(),
    ]
    assert main([*args, "--output", str(artifact)]) == 0
    assert read_selection(artifact).protocol == "rolling_origin"
    for extra in (
        ["--protocol", "fixed", "--fold-hours", "24"],
        ["--cutoff", SPLIT.validation_start.isoformat(), "--protocol", "rolling"],
        ["--fold-hours", "0"],
    ):
        assert main([*args, *extra]) == 2
    for extra in (["--protocol", "rolling"], ["--fold-hours", "24"]):
        assert (
            main(["--data", str(source), "--stage", "test", "--selection", str(artifact), *extra])
            == 2
        )
    assert "overrides are forbidden" in capsys.readouterr().err
    assert main(["--data", str(source), "--stage", "test", "--selection", str(artifact)]) == 0
    assert json.loads(capsys.readouterr().out)["stage"] == "test"


def test_committed_validation_benchmark_reproduces_without_scoring_test() -> None:
    """Check scientific outputs across platforms; wall-clock timings are not assertions."""
    from bike_sharing.data import load_dataset

    root = Path(__file__).resolve().parents[1]
    expected = json.loads((root / "benchmarks/rolling-validation-2012-q3.json").read_text())
    actual = select_rolling_on_validation(load_dataset(root / "bike.csv"))
    historical_selection = expected["selection"]
    historical_selection["package_version"] = actual["package_version"]
    assert actual["selection"] == historical_selection
    assert actual["protocol"] == expected["protocol"]
    assert actual["test_scored"] is False
    assert actual["evaluation_observations"] == 2208
    actual_folds = actual["folds"]
    actual_metrics = actual["metrics"]
    assert isinstance(actual_folds, list) and isinstance(actual_metrics, dict)
    for observed, recorded in zip(actual_folds, expected["folds"], strict=True):
        assert observed["origin"] == recorded["origin"]
        assert observed["training"] == recorded["training"]
        for model, metrics in observed["metrics"].items():
            assert metrics == pytest.approx(recorded["metrics"][model], rel=1e-6, abs=1e-8)
    for model, metrics in actual_metrics.items():
        assert metrics == pytest.approx(expected["metrics"][model], rel=1e-6, abs=1e-8)
