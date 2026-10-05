"""Known interval scores, temporal separation, frozen settings and count support."""

import csv
import json
import math
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bike_sharing import intervals
from bike_sharing.calibration import (
    IntervalBand,
    IntervalSpec,
    interval_metrics,
    make_interval,
    residual_quantile,
    residual_scale,
)
from bike_sharing.data import DemandDataset, Observation, load_dataset
from bike_sharing.interval_cli import main
from bike_sharing.intervals import (
    FrozenIntervalSelection,
    evaluate_interval_test,
    evaluate_interval_validation,
    read_interval_selection,
)
from bike_sharing.splits import StudySplit
from bike_sharing.study import FrozenSelection, read_selection

START = datetime(2012, 1, 1)
SPLIT = StudySplit(datetime(2012, 1, 8), datetime(2012, 1, 12), datetime(2012, 1, 15))


@pytest.fixture
def dataset() -> DemandDataset:
    return DemandDataset(
        tuple(Observation(START + timedelta(hours=h), 50 + 8 * (h % 24)) for h in range(14 * 24)),
        "a" * 64,
        "synthetic.csv",
    )


def test_empirical_rank_rounding_and_support() -> None:
    assert residual_quantile(list(range(1, 20)), 0.95) == 19
    assert residual_quantile([4, 1, 3, 2], 0.5) == 3
    with pytest.raises(ValueError, match="not enough"):
        residual_quantile(list(range(18)), 0.95)
    for scores in ([], [-1.0], [math.nan], [math.inf]):
        with pytest.raises(ValueError, match="calibration scores"):
            residual_quantile(scores, 0.9)
    for level in (0, 1, math.nan, True):
        with pytest.raises(ValueError, match="level"):
            residual_quantile([1.0] * 30, level)
    assert make_interval(0.5, 1.0) == IntervalBand(0, 2)
    assert make_interval(4.0, 1.25) == IntervalBand(1, 7)
    assert make_interval(0.0, 0.0) == IntervalBand(0, 0)
    for value in (-1.0, math.nan, math.inf):
        with pytest.raises(ValueError):
            residual_scale(value)
        with pytest.raises(ValueError):
            make_interval(1.0, value)
    with pytest.raises(ValueError, match="not finite"):
        make_interval(1e308, 1e308)
    for lower, upper in ((-1, 2), (3, 1), (True, 2), (0, 1.5)):
        with pytest.raises(ValueError, match="bounds"):
            IntervalBand(lower, upper)  # type: ignore[arg-type]


def test_interval_score_penalizes_both_tails_and_includes_endpoints() -> None:
    bands = [IntervalBand(1, 3)] * 4
    result = interval_metrics([0, 1, 3, 5], bands, 0.8)
    assert result["empirical_coverage"] == 0.5
    assert result["mean_width"] == 2
    assert result["below_lower"] == result["above_upper"] == 1
    assert result["mean_interval_score"] == pytest.approx(9.5)
    for actual, bounds in (([], []), ([1], []), ([-1], bands[:1]), ([True], bands[:1])):
        with pytest.raises(ValueError):
            interval_metrics(actual, bounds, 0.9)
    with pytest.raises(ValueError):
        interval_metrics([1], bands[:1], 1)


def test_specification_validation_and_manifest_identity() -> None:
    spec = IntervalSpec()
    assert IntervalSpec.from_dict(spec.to_dict()) == spec
    assert len(spec.sha256) == 64
    for levels in ((), (0.9, 0.8), (0.9, 0.9), (0.0,), (1.0,), (True,), (math.nan,)):
        with pytest.raises(ValueError):
            IntervalSpec(levels=levels)
    for value in (0, -1, True):
        with pytest.raises(ValueError):
            IntervalSpec(calibration_folds=value)
        with pytest.raises(ValueError):
            IntervalSpec(minimum_observations=value)
    invalid_specs: tuple[object, ...] = (
        [],
        {},
        {**spec.to_dict(), "scale": "changed"},
        {**spec.to_dict(), "calibration_folds": None},
    )
    for data in invalid_specs:
        with pytest.raises(ValueError):
            IntervalSpec.from_dict(data)


def test_constant_series_has_exact_zero_width_coverage(dataset: DemandDataset) -> None:
    constant = replace(
        dataset, observations=tuple(replace(item, count=8) for item in dataset.observations)
    )
    report = evaluate_interval_validation(constant, SPLIT, horizon_hours=24)
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    for model in metrics.values():
        for values in model["intervals"].values():
            assert values["empirical_coverage"] == 1
            assert values["mean_width"] == values["mean_interval_score"] == 0
    selection = report["interval_selection"]
    assert isinstance(selection, dict)
    assert selection["point_selection"]["model"] == "training_mean"


def test_calibration_and_point_predictions_cannot_see_current_or_future_outcomes(
    dataset: DemandDataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[float, float]] = []

    def capture(mean: float, quantile: float) -> IntervalBand:
        calls.append((mean, quantile))
        return make_interval(mean, quantile)

    monkeypatch.setattr(intervals, "make_interval", capture)
    report = evaluate_interval_validation(dataset, SPLIT, horizon_hours=24)
    first_calls = calls.copy()
    changed_test = replace(
        dataset,
        observations=tuple(
            replace(item, count=99999) if item.timestamp >= SPLIT.test_start else item
            for item in dataset.observations
        ),
    )
    assert evaluate_interval_validation(changed_test, SPLIT, horizon_hours=24) == report
    changed_validation = replace(
        dataset,
        observations=tuple(
            replace(item, count=item.count + 100)
            if SPLIT.validation_start <= item.timestamp < SPLIT.validation_start + timedelta(days=1)
            else item
            for item in dataset.observations
        ),
    )
    calls.clear()
    changed = evaluate_interval_validation(changed_validation, SPLIT, horizon_hours=24)
    assert calls[: 24 * 4 * 3] == first_calls[: 24 * 4 * 3]
    old_folds, new_folds = report["folds"], changed["folds"]
    assert isinstance(old_folds, list) and isinstance(new_folds, list)
    assert old_folds[0]["calibrators"] == new_folds[0]["calibrators"]
    assert old_folds[1]["calibrators"] != new_folds[1]["calibrators"]
    for fold in old_folds:
        assert fold["calibration_end_exclusive"] == fold["origin"]
        assert fold["training"]["last_timestamp"] < fold["origin"]
        for calibrator in fold["calibrators"].values():
            assert calibrator["last_residual_timestamp"] < fold["origin"]
            assert calibrator["observations"] == 96
    assert report["test_scored"] is False


def test_calibration_observations_are_out_of_sample(
    dataset: DemandDataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Sequence

    from bike_sharing.models import Forecast, forecast_model

    origins: list[datetime] = []

    def spy(
        model: str,
        training: Sequence[Observation],
        timestamps: Sequence[datetime],
        *,
        origin: datetime,
    ) -> Forecast:
        assert training[-1].timestamp < origin <= min(timestamps)
        assert max(timestamps) < origin + timedelta(hours=24)
        origins.append(origin)
        return forecast_model(model, training, timestamps, origin=origin)

    monkeypatch.setattr(intervals, "forecast_model", spy)
    evaluate_interval_validation(dataset, SPLIT, horizon_hours=24)
    assert min(origins) == SPLIT.validation_start - timedelta(days=4)
    assert max(origins) < SPLIT.test_start


def test_missing_hours_partial_folds_and_insufficient_calibration(dataset: DemandDataset) -> None:
    split = replace(SPLIT, test_start=SPLIT.test_start - timedelta(hours=12))
    absent = SPLIT.validation_start
    sparse = replace(
        dataset,
        observations=tuple(
            item
            for item in dataset.observations
            if not absent <= item.timestamp < absent + timedelta(days=1)
        ),
    )
    report = evaluate_interval_validation(sparse, split, horizon_hours=24)
    folds = report["folds"]
    assert isinstance(folds, list)
    assert folds[0]["status"] == "no_observations" and folds[0]["metrics"] == {}
    assert report["absent_hours"] == 24
    assert folds[-1]["horizon_hours"] == 12
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    for model in metrics.values():
        assert model["intervals"]["0.9"]["observations"] == 60
    with pytest.raises(ValueError, match="insufficient calibration"):
        evaluate_interval_validation(
            dataset, SPLIT, horizon_hours=24, spec=IntervalSpec(minimum_observations=97)
        )
    with pytest.raises(ValueError, match="earlier model-fitting"):
        evaluate_interval_validation(dataset, SPLIT, horizon_hours=48)
    # Missing initial warmup hours are counted rather than made into residuals of zero.
    missing_warmup = replace(
        dataset,
        observations=tuple(
            item
            for item in dataset.observations
            if not datetime(2012, 1, 4) <= item.timestamp < datetime(2012, 1, 5)
        ),
    )
    result = evaluate_interval_validation(missing_warmup, SPLIT, horizon_hours=24)
    warmup = result["warmup_folds"]
    assert isinstance(warmup, list)
    assert warmup[0]["observations"] == 0 and warmup[0]["absent_hours"] == 24


def test_saved_interval_procedure_and_synthetic_final_test(
    dataset: DemandDataset, tmp_path: Path
) -> None:
    path = tmp_path / "intervals.json"
    report = evaluate_interval_validation(dataset, SPLIT, horizon_hours=24)
    path.write_text(json.dumps(report))
    selected = read_interval_selection(path)
    assert selected.point.protocol == "rolling_origin"
    with pytest.raises(ValueError, match="validation report"):
        read_selection(path)
    final = evaluate_interval_test(dataset, selected)
    assert final["stage"] == "interval_test"
    assert final["interval_selection"] == report["interval_selection"]
    metrics = final["metrics"]
    assert isinstance(metrics, dict) and set(metrics) == {selected.point.model}
    with pytest.raises(ValueError, match="checksum differs"):
        evaluate_interval_test(replace(dataset, sha256="b" * 64), selected)
    with pytest.raises(ValueError, match="version differs"):
        evaluate_interval_test(
            dataset, replace(selected, point=replace(selected.point, package_version="0.0.0"))
        )
    with pytest.raises(ValueError, match="rolling-origin"):
        FrozenIntervalSelection(FrozenSelection("training_mean", "a" * 64, SPLIT, "0.4.0"))
    with pytest.raises(TypeError, match="IntervalSpec"):
        FrozenIntervalSelection(selected.point, "bad")  # type: ignore[arg-type]
    invalid_reports: tuple[object, ...] = (
        [],
        {},
        final,
        {**report, "interval_selection": {}},
        {**report, "interval_selection": {**selected.to_dict(), "interval_sha256": "bad"}},
    )
    for payload in invalid_reports:
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError):
            read_interval_selection(path)


def test_interval_cli_preserves_inputs_and_frozen_settings(
    dataset: DemandDataset, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, output = tmp_path / "data.csv", tmp_path / "nested" / "intervals.json"
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
    common = ["--data", str(source)]
    study = [
        "--validation-start",
        SPLIT.validation_start.isoformat(),
        "--test-start",
        SPLIT.test_start.isoformat(),
        "--test-end",
        SPLIT.test_end.isoformat(),
        "--fold-hours",
        "24",
    ]
    assert main([*common, *study, "--output", str(output)]) == 0
    assert main([*common, "--stage", "test", "--selection", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["stage"] == "interval_test"
    for extra in (
        ["--stage", "test"],
        ["--selection", str(output)],
        ["--output", str(source)],
        ["--stage", "test", "--selection", str(output), "--output", str(output)],
        ["--stage", "test", "--selection", str(output), "--calibration-folds", "3"],
    ):
        assert main([*common, *extra]) == 2
    assert main([*common, *study, "--calibration-folds", "0"]) == 2


def test_empirical_interval_evidence_reproduces_without_final_testing() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = json.loads((root / "benchmarks/interval-validation-2012-q3.json").read_text())
    actual = evaluate_interval_validation(load_dataset(root / "bike.csv"))
    assert actual["interval_selection"] == expected["interval_selection"]
    assert actual["protocol"] == expected["protocol"]
    assert actual["test_scored"] is False
    metrics = actual["metrics"]
    assert isinstance(metrics, dict)
    for model, result in metrics.items():
        recorded = expected["metrics"][model]
        assert result["point"] == pytest.approx(recorded["point"], rel=1e-6, abs=1e-8)
        for level, values in result["intervals"].items():
            assert values == pytest.approx(recorded["intervals"][level], rel=1e-6, abs=1e-8)
        for grouping in ("by_lead_day", "by_predicted_demand"):
            for group, levels in result[grouping].items():
                for level, values in levels.items():
                    assert values == pytest.approx(
                        recorded[grouping][group][level], rel=1e-6, abs=1e-8
                    )
