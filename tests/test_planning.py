"""Decision loss, quantile optimality, temporal separation and frozen testing."""

import json
import math
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bike_sharing import planning
from bike_sharing.data import DemandDataset, Observation, load_dataset
from bike_sharing.models import Forecast, forecast_model
from bike_sharing.planning import (
    COST_RATIOS,
    POLICIES,
    FrozenPlanningSelection,
    cost_metrics,
    evaluate_planning_test,
    evaluate_planning_validation,
    read_planning_selection,
    signed_quantile,
    workload_action,
)
from bike_sharing.planning_cli import main
from bike_sharing.splits import StudySplit

START = datetime(2012, 1, 1)
SPLIT = StudySplit(datetime(2012, 1, 8), datetime(2012, 1, 12), datetime(2012, 1, 15))


@pytest.fixture
def dataset() -> DemandDataset:
    return DemandDataset(
        tuple(Observation(START + timedelta(hours=h), 50 + 8 * (h % 24)) for h in range(14 * 24)),
        "a" * 64,
        "synthetic.csv",
    )


def test_asymmetric_cost_components_and_invalid_inputs() -> None:
    m = cost_metrics([0, 10, 20], [5.0, 10.0, 15.0], 4.0)
    assert m["mean_cost"] == pytest.approx(25 / 3)
    assert m["mean_underprediction"] == m["mean_overprediction"] == pytest.approx(5 / 3)
    assert m["mean_action"] == 10 and m["underprediction_fraction"] == pytest.approx(1 / 3)
    for ratio in (0.0, -1.0, math.nan, math.inf, True):
        with pytest.raises(ValueError):
            cost_metrics([1], [1.0], ratio)
        with pytest.raises(ValueError):
            signed_quantile([0.0], ratio)
    for actual, actions in (
        ([], []),
        ([1], []),
        ([-1], [1.0]),
        ([True], [1.0]),
        ([1], [-1.0]),
        ([1], [math.inf]),
    ):
        with pytest.raises(ValueError):
            cost_metrics(actual, actions, 1.0)


def test_quantile_minimizes_empirical_loss_and_actions_increase_with_ratio() -> None:
    # A discrete, skewed distribution provides a known optimum, including ties.
    outcomes = [0, 0, 2, 10, 30]
    for r in COST_RATIOS:
        q = signed_quantile(outcomes, r)
        achieved = cost_metrics(outcomes, [q] * len(outcomes), r)["mean_cost"]
        for a in range(31):
            assert (
                achieved
                <= cost_metrics(outcomes, [float(a)] * len(outcomes), r)["mean_cost"] + 1e-12
            )
    assert signed_quantile([-5.0, -2.0, 3.0, 9.0], 1.0) == -2.0
    assert signed_quantile([0.0, 1.0, 2.0], 0.5) == 0.0
    actions = [
        workload_action(4.0, signed_quantile([-5.0, -2.0, 3.0, 9.0], r)) for r in COST_RATIOS
    ]
    assert actions == sorted(actions) and actions[0] == 0.0
    for scores in ([], [math.nan], [math.inf]):
        with pytest.raises(ValueError):
            signed_quantile(scores, 1.0)
    for mean, adjust in ((-1.0, 0.0), (1.0, math.nan), (1e308, 1e308)):
        with pytest.raises(ValueError):
            workload_action(mean, adjust)


def test_constant_series_has_zero_cost_and_deterministic_ties(dataset: DemandDataset) -> None:
    constant = replace(
        dataset, observations=tuple(replace(o, count=8) for o in dataset.observations)
    )
    report = evaluate_planning_validation(constant, SPLIT, horizon_hours=24)
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    for policies in metrics.values():
        assert set(policies) == set(POLICIES)
        assert all(m["mean_cost"] == 0 for m in policies.values())
    selected = report["planning_selection"]
    assert isinstance(selected, dict)
    assert set(selected["policies"].values()) == {"training_mean"}


def test_future_outcomes_cannot_change_current_actions_or_calibration(
    dataset: DemandDataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[float, float]] = []
    origins: list[datetime] = []

    def capture(mean: float, adjust: float) -> float:
        calls.append((mean, adjust))
        return workload_action(mean, adjust)

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

    monkeypatch.setattr(planning, "workload_action", capture)
    monkeypatch.setattr(planning, "forecast_model", spy)
    report = evaluate_planning_validation(dataset, SPLIT, horizon_hours=24)
    original = calls.copy()
    future = replace(
        dataset,
        observations=tuple(
            replace(o, count=99999) if o.timestamp >= SPLIT.test_start else o
            for o in dataset.observations
        ),
    )
    assert evaluate_planning_validation(future, SPLIT, horizon_hours=24) == report
    changed = replace(
        dataset,
        observations=tuple(
            replace(o, count=o.count + 100)
            if SPLIT.validation_start <= o.timestamp < SPLIT.validation_start + timedelta(days=1)
            else o
            for o in dataset.observations
        ),
    )
    calls.clear()
    revised = evaluate_planning_validation(changed, SPLIT, horizon_hours=24)
    assert calls[: 24 * 6] == original[: 24 * 6]
    old, new = report["folds"], revised["folds"]
    assert isinstance(old, list) and isinstance(new, list)
    assert old[0]["signed_quantiles"] == new[0]["signed_quantiles"]
    assert old[1]["signed_quantiles"] != new[1]["signed_quantiles"]
    for fold in old:
        assert fold["last_calibration_timestamp"] < fold["origin"]
        assert fold["calibration_observations"] == 96
    assert min(origins) == SPLIT.validation_start - timedelta(days=4)
    assert max(origins) < SPLIT.test_start and report["test_scored"] is False


def test_gaps_short_folds_and_insufficient_history(dataset: DemandDataset) -> None:
    sparse = replace(
        dataset,
        observations=tuple(
            o
            for o in dataset.observations
            if not SPLIT.validation_start
            <= o.timestamp
            < SPLIT.validation_start + timedelta(days=1)
        ),
    )
    report = evaluate_planning_validation(
        sparse, replace(SPLIT, test_start=SPLIT.test_start - timedelta(hours=12)), horizon_hours=24
    )
    folds = report["folds"]
    assert isinstance(folds, list)
    assert folds[0]["status"] == "no_observations" and folds[0]["absent_hours"] == 24
    assert folds[-1]["observations"] == 12 and report["observations"] == 60
    with pytest.raises(ValueError, match="earlier fitting"):
        evaluate_planning_validation(dataset, SPLIT, horizon_hours=48)
    no_calibration = replace(
        dataset,
        observations=tuple(
            o
            for o in dataset.observations
            if not datetime(2012, 1, 4) <= o.timestamp < SPLIT.validation_start
        ),
    )
    with pytest.raises(ValueError, match="insufficient"):
        evaluate_planning_validation(no_calibration, SPLIT, horizon_hours=24)


def test_saved_policies_only_are_evaluated_on_synthetic_test(
    dataset: DemandDataset, tmp_path: Path
) -> None:
    report = evaluate_planning_validation(dataset, SPLIT, horizon_hours=24)
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(report))
    selection = read_planning_selection(path)
    # Exercise both residual and point-only saved choices, without running a real test.
    for policies in (
        ("poisson_residual_quantile",) * 6,
        ("training_mean",) * 6,
        selection.policies,
    ):
        selected = replace(selection, policies=policies)
        result = evaluate_planning_test(dataset, selected)
        metrics = result["metrics"]
        assert isinstance(metrics, dict)
        for r, p in zip(COST_RATIOS, policies, strict=True):
            assert set(metrics[str(r)]) == {p}
        assert result["planning_selection"] == selected.to_dict()
        assert result["selection_frozen"] is True
    with pytest.raises(ValueError, match="checksum"):
        evaluate_planning_test(replace(dataset, sha256="b" * 64), selection)
    with pytest.raises(ValueError, match="version"):
        evaluate_planning_test(
            dataset,
            replace(selection, reference=replace(selection.reference, package_version="0.0.0")),
        )
    with pytest.raises(ValueError):
        FrozenPlanningSelection(
            replace(selection.reference, model="training_mean"), selection.policies
        )
    with pytest.raises(ValueError):
        FrozenPlanningSelection(selection.reference, ("unknown",) * 6)
    bad: tuple[object, ...] = (
        [],
        {},
        {"stage": "planning_test"},
        {**report, "planning_selection": {}},
        {**report, "planning_selection": {**selection.to_dict(), "configuration_sha256": "bad"}},
        {**report, "planning_selection": {**selection.to_dict(), "policies": {}}},
    )
    for payload in bad:
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError):
            read_planning_selection(path)


def test_cli_uses_explicit_test_gate_and_protects_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    dataset: DemandDataset,
) -> None:
    report = evaluate_planning_validation(dataset, SPLIT, horizon_hours=24)
    monkeypatch.setattr("bike_sharing.planning_cli.load_dataset", lambda _: dataset)
    monkeypatch.setattr("bike_sharing.planning_cli.evaluate_planning_validation", lambda _: report)
    output = tmp_path / "nested" / "selection.json"
    assert main(["--output", str(output)]) == 0
    assert main(["--stage", "test", "--selection", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["stage"] == "planning_test"
    for args in (
        ["--stage", "test"],
        ["--selection", str(output)],
        ["--data", str(output), "--output", str(output)],
        ["--stage", "test", "--selection", str(output), "--output", str(output)],
    ):
        assert main(args) == 2


def test_committed_planning_evidence_reproduces_without_test() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = json.loads((root / "benchmarks/planning-validation-2012-q3.json").read_text())
    actual = evaluate_planning_validation(load_dataset(root / "bike.csv"))
    assert actual["planning_selection"] == expected["planning_selection"]
    assert actual["protocol"] == expected["protocol"]
    assert actual["test_scored"] is False
    metrics = actual["metrics"]
    assert isinstance(metrics, dict)
    for ratio, policies in metrics.items():
        for policy, m in policies.items():
            assert m == pytest.approx(expected["metrics"][ratio][policy], rel=1e-6, abs=1e-8)
