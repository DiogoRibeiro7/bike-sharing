"""Protect evidence from changed data, false joins and incorrect field conversions."""

import csv
import json
from pathlib import Path

import pytest

from bike_sharing.audit import LOCAL_COLUMNS, UCI_COLUMNS, audit_dataset, main

LOCAL_ROWS = [
    ["1/1/2011", "4", "0", "0", "6", "0", "1", "36.6", "37.4", "81", "0", "3", "13", "16"],
    ["1/1/2011", "4", "2", "0", "6", "0", "1", "34.9", "35.6", "80", "6", "5", "27", "32"],
]
UCI_ROWS = [
    [
        "1",
        "2011-01-01",
        "1",
        "0",
        "1",
        "0",
        "0",
        "6",
        "0",
        "1",
        "0.24",
        "0.2879",
        "0.81",
        "0",
        "3",
        "13",
        "16",
    ],
    [
        "2",
        "2011-01-01",
        "1",
        "0",
        "1",
        "2",
        "0",
        "6",
        "0",
        "1",
        "0.22",
        "0.2727",
        "0.8",
        "0.0896",
        "5",
        "27",
        "32",
    ],
]


def write_csv(path: Path, columns: tuple[str, ...], rows: list[list[str]]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)


@pytest.fixture
def inputs(tmp_path: Path) -> tuple[Path, Path]:
    local, upstream = tmp_path / "bike.csv", tmp_path / "hour.csv"
    write_csv(local, LOCAL_COLUMNS, LOCAL_ROWS)
    write_csv(upstream, UCI_COLUMNS, UCI_ROWS)
    return local, upstream


def test_reconcile_reordered_rows_and_preserve_missing_hours(inputs: tuple[Path, Path]) -> None:
    local, upstream = inputs
    write_csv(upstream, UCI_COLUMNS, list(reversed(UCI_ROWS)))
    report = audit_dataset(local, upstream)
    facts = report["local"]
    comparison = report["uci_comparison"]
    assert isinstance(facts, dict) and isinstance(comparison, dict)
    assert facts["coverage"]["absent_calendar_hours"] == 1
    assert facts["missing_cells"] == facts["zero_rental_rows"] == 0
    assert comparison["timestamp_sets_identical"]
    assert comparison["matched_rows_by_field"]["Temperature F"] == 2
    assert comparison["matched_rows_by_field"]["Wind Speed"] == 2
    assert audit_dataset(local)["uci_comparison"] is None


def test_season_is_calendar_rule_not_fixed_recode(inputs: tuple[Path, Path]) -> None:
    local, upstream = inputs
    row, original = LOCAL_ROWS[0].copy(), UCI_ROWS[0].copy()
    row[0], row[1], row[4], row[5] = "3/1/2011", "1", "2", "1"
    original[1], original[4], original[7], original[8] = "2011-03-01", "3", "2", "1"
    write_csv(local, LOCAL_COLUMNS, [row])
    write_csv(upstream, UCI_COLUMNS, [original])
    comparison = audit_dataset(local, upstream)["uci_comparison"]
    assert isinstance(comparison, dict)
    assert comparison["simple_season_recode_disagreements"] == 1


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("season", "3", None),
        ("temp", "0.25", "Temperature F"),
        ("cnt", "17", "Total Users"),
        ("hr", "1", "timestamp sets"),
        ("atemp", "NaN", "finite"),
    ],
)
def test_changed_source_detected(
    inputs: tuple[Path, Path], column: str, value: str, message: str | None
) -> None:
    local, upstream = inputs
    rows = [row.copy() for row in UCI_ROWS]
    rows[0][UCI_COLUMNS.index(column)] = value
    write_csv(upstream, UCI_COLUMNS, rows)
    if message is None:
        # Season is explicitly derived from month, rather than copied from UCI.
        assert audit_dataset(local, upstream)["uci_comparison"] is not None
    else:
        with pytest.raises(ValueError, match=message):
            audit_dataset(local, upstream)


def test_reject_duplicate_or_missing_source_rows(inputs: tuple[Path, Path]) -> None:
    local, upstream = inputs
    write_csv(upstream, UCI_COLUMNS, [UCI_ROWS[0], UCI_ROWS[0]])
    with pytest.raises(ValueError, match="duplicate timestamps"):
        audit_dataset(local, upstream)
    write_csv(upstream, UCI_COLUMNS, UCI_ROWS[:1])
    with pytest.raises(ValueError, match="timestamp sets"):
        audit_dataset(local, upstream)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("Season", "3", "month-based"),
        ("Weather Type", "5", "integer range"),
        ("Day of the Week", "0", "Sunday=0"),
        ("Working Day", "1", "contradicts"),
        ("Wind Speed", "-1", "nonnegative"),
        ("Temperature F", "Infinity", "finite"),
        ("Temperature F", "invalid", None),
        ("Humidity", "", "missing or extra"),
    ],
)
def test_reject_invalid_local_fields(
    inputs: tuple[Path, Path], column: str, value: str, message: str | None
) -> None:
    local, _ = inputs
    row = LOCAL_ROWS[0].copy()
    row[LOCAL_COLUMNS.index(column)] = value
    write_csv(local, LOCAL_COLUMNS, [row])
    with pytest.raises((ValueError, ArithmeticError), match=message):
        audit_dataset(local)


def test_require_upstream_schema_and_nonempty_file(inputs: tuple[Path, Path]) -> None:
    local, upstream = inputs
    write_csv(upstream, UCI_COLUMNS[:-1], [UCI_ROWS[0][:-1]])
    with pytest.raises(ValueError, match="column order"):
        audit_dataset(local, upstream)
    write_csv(upstream, UCI_COLUMNS, [])
    with pytest.raises(ValueError, match="no observations"):
        audit_dataset(local, upstream)
    write_csv(upstream, UCI_COLUMNS, [UCI_ROWS[0][:-1]])
    with pytest.raises(ValueError, match="missing or extra"):
        audit_dataset(local, upstream)


def test_cli_checks_evidence_offline_and_with_source(
    inputs: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    local, upstream = inputs
    evidence = local.parent / "evidence.json"
    evidence.write_text(json.dumps(audit_dataset(local, upstream)))
    args = ["--data", str(local), "--check", str(evidence)]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["uci_comparison"] is None
    assert main([*args, "--upstream", str(upstream)]) == 0
    assert json.loads(capsys.readouterr().out)["uci_comparison"]["observations"] == 2
    evidence.write_text("{}")
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert "differs from saved evidence" in capsys.readouterr().err


def test_committed_local_evidence_matches_historical_bytes() -> None:
    root = Path(__file__).resolve().parents[1]
    evidence = json.loads((root / "benchmarks/data-audit.json").read_text())
    assert audit_dataset(root / "bike.csv")["local"] == evidence["local"]
