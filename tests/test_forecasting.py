"""Check the statistical contract, data failures and CLI against small known examples."""

import csv
import json
import math
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from bike_sharing.cli import main
from bike_sharing.data import DemandDataset, Observation, coverage, load_dataset
from bike_sharing.forecasting import error_metrics, evaluate, forecast_baselines


@pytest.fixture
def dataset() -> DemandDataset:
    """Two weeks whose outcome is exactly the hour-of-week index."""
    start = datetime(2012, 1, 1)
    times = [start + timedelta(hours=hour) for hour in range(336)]
    records = tuple(Observation(time, time.weekday() * 24 + time.hour) for time in times)
    return DemandDataset(records, "synthetic", "fixture.csv")


@pytest.fixture
def write_csv(tmp_path: Path) -> Callable[[str], Path]:
    """Write CSV content, including legacy carriage-return line endings."""

    def write(body: str) -> Path:
        path = tmp_path / "input.csv"
        path.write_bytes(body.encode("utf-8"))
        return path

    return write


HEADER = "Date,Hour,Total Users,Casual Users,Registered Users\r"


def test_loader_sorts_checks_identity_and_preserves_gaps(write_csv: Callable[[str], Path]) -> None:
    path = write_csv(HEADER + "1/1/2012,2,5,2,3\r1/1/2012,0,3,1,2\r")
    before = path.read_bytes()
    result = load_dataset(path)
    assert [item.count for item in result.observations] == [3, 5]
    assert coverage(result.observations)["absent_calendar_hours"] == 1
    assert len(result.sha256) == 64
    assert path.read_bytes() == before
    path.write_bytes(before.replace(b",5,2,3", b",6,3,3"))
    assert load_dataset(path).sha256 != result.sha256


@pytest.mark.parametrize(
    "body, message",
    [
        ("", "header"),
        ("Date,Date\n", "unique"),
        ("Date,Hour\n", "missing required"),
        (HEADER, "no observations"),
        (HEADER + "bad,1,3,1,2\r", "row 2"),
        (HEADER + "1/1/2012,24,3,1,2\r", "Hour"),
        (HEADER + "1/1/2012,1,3.5,1,2\r", "row 2"),
        (HEADER + "1/1/2012,1,-1,0,-1\r", "nonnegative"),
        (HEADER + "1/1/2012,1,4,1,2\r", "must equal"),
        (HEADER + "1/1/2012,1,3,1\r", "number of fields"),
        (HEADER + "1/1/2012,1,3,1,2,extra\r", "number of fields"),
        (HEADER + "1/1/2012,1,3,1,2\r1/1/2012,1,3,1,2\r", "duplicate timestamp"),
    ],
)
def test_loader_rejects_invalid_data(
    write_csv: Callable[[str], Path], body: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        load_dataset(write_csv(body))


def test_observation_contract() -> None:
    with pytest.raises(TypeError, match="integer"):
        Observation(datetime(2012, 1, 1), True)
    with pytest.raises(ValueError, match="nonnegative"):
        Observation(datetime(2012, 1, 1), -1)
    with pytest.raises(ValueError, match="timezone-naive"):
        Observation(datetime(2012, 1, 1, tzinfo=UTC), 1)
    with pytest.raises(ValueError, match="exact hour"):
        Observation(datetime(2012, 1, 1, 0, 30), 1)
    with pytest.raises(TypeError, match="datetime"):
        Observation("2012-01-01", 1)  # type: ignore[arg-type]


def test_known_weekly_pattern_and_global_mean(dataset: DemandDataset) -> None:
    training, test = dataset.observations[:168], dataset.observations[168:]
    prediction = forecast_baselines(training, [item.timestamp for item in test])
    assert prediction["training_mean"] == (83.5,) * 168
    assert prediction["hour_of_week_mean"] == tuple(float(item.count) for item in test)
    assert error_metrics([item.count for item in test], prediction["hour_of_week_mean"]) == {
        "mae": 0.0,
        "rmse": 0.0,
    }


def test_unseen_weekly_bucket_uses_training_mean() -> None:
    prediction = forecast_baselines(
        [Observation(datetime(2012, 1, 1), 2), Observation(datetime(2012, 1, 1, 1), 6)],
        [datetime(2012, 1, 1, 2)],
    )
    assert prediction["hour_of_week_mean"] == (4.0,)


def test_changing_held_out_counts_cannot_change_predictions(dataset: DemandDataset) -> None:
    cutoff = datetime(2012, 1, 8)
    altered = replace(
        dataset,
        observations=tuple(
            replace(item, count=item.count + 10000) if item.timestamp >= cutoff else item
            for item in dataset.observations
        ),
    )
    forecasts = [
        forecast_baselines(
            [item for item in data.observations if item.timestamp < cutoff],
            [item.timestamp for item in data.observations if item.timestamp >= cutoff],
        )
        for data in (dataset, altered)
    ]
    assert forecasts[0] == forecasts[1]
    original_report = evaluate(dataset, cutoff)
    altered_report = evaluate(altered, cutoff)
    assert original_report["protocol"] == altered_report["protocol"]
    assert original_report["metrics"] != altered_report["metrics"]


def test_evaluation_cutoff_end_and_missing_hour_accounting(dataset: DemandDataset) -> None:
    cutoff = datetime(2012, 1, 8)
    reduced = replace(
        dataset,
        observations=tuple(
            item for item in dataset.observations if item.timestamp != cutoff + timedelta(hours=1)
        ),
    )
    report = evaluate(reduced, cutoff, 24)
    protocol = report["protocol"]
    assert isinstance(protocol, dict)
    assert protocol["evaluation_observations"] == 23
    assert protocol["absent_evaluation_hours"] == 1
    assert protocol["end_exclusive"] == "2012-01-09T00:00:00"
    assert protocol["training"]["last_timestamp"] == "2012-01-07T23:00:00"
    assert protocol["training"]["observations"] == 168


@pytest.mark.parametrize("horizon", [0, -1, True])
def test_invalid_horizon(dataset: DemandDataset, horizon: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        evaluate(dataset, datetime(2012, 1, 8), horizon)


def test_empty_outside_or_unsorted_evaluation(dataset: DemandDataset) -> None:
    with pytest.raises(ValueError, match="within the dataset"):
        evaluate(dataset, datetime(2012, 1, 14), 48)
    with pytest.raises(ValueError, match="after training"):
        evaluate(dataset, datetime(2012, 1, 1), 24)
    sparse = replace(dataset, observations=(dataset.observations[0], dataset.observations[-1]))
    with pytest.raises(ValueError, match="no observed outcomes"):
        evaluate(sparse, datetime(2012, 1, 8), 24)
    with pytest.raises(ValueError, match="at least one observation"):
        forecast_baselines([], [datetime(2012, 1, 8)])
    with pytest.raises(ValueError, match="strictly increasing"):
        forecast_baselines(dataset.observations[::-1], [datetime(2012, 1, 15)])
    with pytest.raises(ValueError, match="prediction timestamp"):
        forecast_baselines(dataset.observations, [])
    with pytest.raises(ValueError, match="follow all training"):
        forecast_baselines(dataset.observations, [datetime(2012, 1, 8)])


def test_metric_values_and_failures() -> None:
    assert error_metrics([1, 5], [1.0, 1.0]) == {"mae": 2.0, "rmse": math.sqrt(8)}
    invalid_cases: list[tuple[list[int], list[float]]] = [
        ([], []),
        ([1], []),
        ([-1], [1.0]),
        ([True], [1.0]),
        ([1], [float("nan")]),
        ([1], [-1.0]),
    ]
    for actual, predicted in invalid_cases:
        with pytest.raises(ValueError):
            error_metrics(actual, predicted)


def test_cli_report_and_error_paths(
    dataset: DemandDataset, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "data.csv"
    with path.open("w", newline="") as stream:
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
    args = ["--data", str(path), "--cutoff", "2012-01-08"]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["metrics"]["hour_of_week_mean"]["mae"] == 0
    output = tmp_path / "nested" / "report.json"
    assert main([*args, "--output", str(output)]) == 0
    assert json.loads(output.read_text()) == report
    assert main([*args, "--output", str(path)]) == 2
    assert "must not overwrite" in capsys.readouterr().err
    assert main([*args, "--cutoff", "invalid"]) == 2
    assert main([*args, "--data", str(tmp_path / "absent.csv")]) == 2
    assert main([*args, "--output", str(path / "report.json")]) == 2
