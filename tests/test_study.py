"""Check the three-way protocol without revealing the real final-test outcomes."""

import csv
import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bike_sharing.cli import main
from bike_sharing.data import DemandDataset, Observation
from bike_sharing.forecasting import evaluate
from bike_sharing.splits import StudySplit, partition_dataset
from bike_sharing.study import FrozenSelection, evaluate_test, read_selection, select_on_validation

SPLIT = StudySplit(datetime(2012, 1, 8), datetime(2012, 1, 15), datetime(2012, 1, 22))


@pytest.fixture
def dataset() -> DemandDataset:
    times = [datetime(2012, 1, 1) + timedelta(hours=hour) for hour in range(504)]
    return DemandDataset(
        tuple(Observation(time, time.weekday() * 24 + time.hour) for time in times),
        "a" * 64,
        "synthetic.csv",
    )


def selection_from_report(report: dict[str, object], path: Path) -> FrozenSelection:
    """Exercise the persisted manifest rather than constructing a chosen model by hand."""
    path.write_text(json.dumps(report), encoding="utf-8")
    return read_selection(path)


def test_disjoint_complete_partitions_and_half_open_boundaries(dataset: DemandDataset) -> None:
    parts = partition_dataset(dataset, SPLIT)
    assert len(parts.training) == len(parts.validation) == len(parts.test) == 168
    assert parts.training + parts.validation + parts.test == dataset.observations
    assert parts.validation[0].timestamp == SPLIT.validation_start
    assert parts.test[0].timestamp == SPLIT.test_start
    extra = replace(dataset, observations=dataset.observations + (Observation(SPLIT.test_end, 1),))
    assert partition_dataset(extra, SPLIT) == parts


def test_invalid_splits_and_empty_or_truncated_partitions(dataset: DemandDataset) -> None:
    with pytest.raises(ValueError, match="split boundaries"):
        StudySplit(SPLIT.test_start, SPLIT.validation_start, SPLIT.test_end)
    with pytest.raises(ValueError, match="span the requested test_end"):
        partition_dataset(replace(dataset, observations=dataset.observations[:-1]), SPLIT)
    for start, end in [(0, 168), (168, 336), (336, 504)]:
        remaining = dataset.observations[:start] + dataset.observations[end:]
        # A post-study observation establishes source span even with an empty test partition.
        remaining += (Observation(SPLIT.test_end, 1),)
        with pytest.raises(ValueError, match="all contain observations"):
            partition_dataset(replace(dataset, observations=remaining), SPLIT)


def test_development_cannot_cross_test_boundary(dataset: DemandDataset) -> None:
    with pytest.raises(ValueError, match="validation partition"):
        evaluate(dataset, SPLIT.test_start, 24, split=SPLIT)
    with pytest.raises(ValueError, match="validation partition"):
        evaluate(dataset, SPLIT.test_start - timedelta(hours=1), 2, split=SPLIT)
    assert (
        evaluate(dataset, SPLIT.test_start - timedelta(hours=1), 1, split=SPLIT)["stage"]
        == "validation_diagnostic"
    )
    with pytest.raises(ValueError, match="within the dataset"):
        evaluate(
            replace(dataset, observations=dataset.observations[:180]),
            SPLIT.validation_start,
            24,
            split=SPLIT,
        )


def test_selection_ignores_test_outcomes(dataset: DemandDataset) -> None:
    changed = replace(
        dataset,
        observations=tuple(
            replace(item, count=1_000_000) if item.timestamp >= SPLIT.test_start else item
            for item in dataset.observations
        ),
    )
    original_report = select_on_validation(dataset, SPLIT)
    assert select_on_validation(changed, SPLIT) == original_report
    assert original_report["test_scored"] is False
    assert original_report["stage"] == "validation"
    assert isinstance(original_report["selection"], dict)
    assert original_report["selection"]["model"] == "hour_of_week_mean"


def test_ties_prefer_the_simpler_baseline(dataset: DemandDataset) -> None:
    constant = replace(
        dataset, observations=tuple(replace(item, count=7) for item in dataset.observations)
    )
    report = select_on_validation(constant, SPLIT)
    assert isinstance(report["selection"], dict)
    assert report["selection"]["model"] == "training_mean"


def test_final_refit_uses_validation_but_never_test_labels(
    dataset: DemandDataset, tmp_path: Path
) -> None:
    adjusted = replace(
        dataset,
        observations=tuple(
            replace(item, count=item.count + 20)
            if SPLIT.validation_start <= item.timestamp < SPLIT.test_start
            else item
            for item in dataset.observations
        ),
    )
    selection = selection_from_report(
        select_on_validation(adjusted, SPLIT), tmp_path / "selection.json"
    )
    assert selection.model == "hour_of_week_mean"
    result = evaluate_test(adjusted, selection)
    assert result["metrics"] == {"hour_of_week_mean": {"mae": 10.0, "rmse": 10.0}}
    assert isinstance(result["protocol"], dict)
    assert result["protocol"]["training"]["observations"] == 336
    assert result["protocol"]["refit_during_horizon"] is False
    # Changing test labels changes scoring, not the selected model or refit protocol.
    altered_test = replace(
        adjusted,
        observations=tuple(
            replace(item, count=item.count + 200) if item.timestamp >= SPLIT.test_start else item
            for item in adjusted.observations
        ),
    )
    changed_result = evaluate_test(altered_test, selection)
    assert changed_result["selection"] == result["selection"]
    assert changed_result["protocol"] == result["protocol"]
    assert changed_result["metrics"] == {"hour_of_week_mean": {"mae": 190.0, "rmse": 190.0}}


def test_frozen_selection_binds_data_version_and_gap_counts(
    dataset: DemandDataset, tmp_path: Path
) -> None:
    selection = selection_from_report(
        select_on_validation(dataset, SPLIT), tmp_path / "selection.json"
    )
    with pytest.raises(ValueError, match="checksum differs"):
        evaluate_test(replace(dataset, sha256="b" * 64), selection)
    with pytest.raises(ValueError, match="version differs"):
        evaluate_test(dataset, replace(selection, package_version="0.0.0"))
    missing = replace(
        dataset,
        observations=tuple(
            item for item in dataset.observations if item.timestamp != SPLIT.test_start
        ),
    )
    report = evaluate_test(missing, selection)
    assert isinstance(report["protocol"], dict)
    assert report["protocol"]["absent_evaluation_hours"] == 1


def test_selection_artifact_validation(dataset: DemandDataset, tmp_path: Path) -> None:
    path = tmp_path / "selection.json"
    for payload in [[], {}, {"stage": "test"}, {"stage": "validation", "selection": {}}]:
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError):
            read_selection(path)
    report = select_on_validation(dataset, SPLIT)
    selection = selection_from_report(report, path)
    for field, value in [
        ("schema_version", "99"),
        ("selection_metric", "test_mae"),
        ("model", "unsupported"),
        ("dataset_sha256", "bad"),
        ("package_version", ""),
        ("test_start", "bad-date"),
    ]:
        path.write_text(
            json.dumps({"stage": "validation", "selection": {**selection.to_dict(), field: value}})
        )
        with pytest.raises(ValueError):
            read_selection(path)
    with pytest.raises(TypeError, match="StudySplit"):
        FrozenSelection("training_mean", "a" * 64, "invalid", "0.2.0")  # type: ignore[arg-type]


def test_cli_validation_and_explicit_final_test(
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
    custom = [
        "--validation-start",
        "2012-01-08",
        "--test-start",
        "2012-01-15",
        "--test-end",
        "2012-01-22",
    ]
    common = ["--data", str(source)]
    assert main([*common, *custom, "--output", str(artifact)]) == 0
    assert read_selection(artifact).model == "hour_of_week_mean"
    assert main([*common, "--stage", "test", "--selection", str(artifact)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["stage"] == "test"
    assert result["metrics"] == {"hour_of_week_mean": {"mae": 0.0, "rmse": 0.0}}
    for args in [
        ["--stage", "test"],
        ["--stage", "test", "--selection", str(artifact), "--test-start", "2012-01-16"],
        ["--stage", "test", "--selection", str(artifact), "--output", str(artifact)],
        ["--selection", str(artifact)],
        ["--horizon-hours", "24"],
    ]:
        assert (
            main(
                [*common, *custom, *args] if args == ["--horizon-hours", "24"] else [*common, *args]
            )
            == 2
        )
