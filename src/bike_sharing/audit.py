"""Reconcile the historical derivative with UCI without fetching or changing data."""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from bike_sharing.data import coverage, load_dataset

LOCAL_COLUMNS = (
    "Date",
    "Season",
    "Hour",
    "Holiday",
    "Day of the Week",
    "Working Day",
    "Weather Type",
    "Temperature F",
    "Temperature Feels F",
    "Humidity",
    "Wind Speed",
    "Casual Users",
    "Registered Users",
    "Total Users",
)
UCI_COLUMNS = (
    "instant",
    "dteday",
    "season",
    "yr",
    "mnth",
    "hr",
    "holiday",
    "weekday",
    "workingday",
    "weathersit",
    "temp",
    "atemp",
    "hum",
    "windspeed",
    "casual",
    "registered",
    "cnt",
)
DIRECT_FIELDS = {
    "Hour": "hr",
    "Holiday": "holiday",
    "Day of the Week": "weekday",
    "Working Day": "workingday",
    "Weather Type": "weathersit",
    "Casual Users": "casual",
    "Registered Users": "registered",
    "Total Users": "cnt",
}


def _table(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    reader = csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"), newline=""), strict=True)
    if next(reader, []) != list(columns):
        raise ValueError(f"{path.name}: audit requires the exact documented column order")
    rows = []
    for values in reader:
        if len(values) != len(columns) or any(not value.strip() for value in values):
            raise ValueError(f"{path.name}: row {reader.line_num} has missing or extra fields")
        rows.append(dict(zip(columns, values, strict=True)))
    if not rows:
        raise ValueError(f"{path.name}: no observations")
    return rows


def _timestamp(row: dict[str, str], *, uci: bool = False) -> datetime:
    date, hour, fmt = ("dteday", "hr", "%Y-%m-%d") if uci else ("Date", "Hour", "%m/%d/%Y")
    return datetime.strptime(row[date], fmt).replace(hour=int(row[hour]))


def _number(row: dict[str, str], name: str) -> Decimal:
    value = Decimal(row[name])
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


def _season(month: int) -> int:
    return ((month - 3) % 12) // 3 + 1


def _local_audit(path: Path) -> dict[str, object]:
    dataset = load_dataset(path)
    rows = _table(path, LOCAL_COLUMNS)
    for row in rows:
        timestamp = _timestamp(row)
        for name, lower, upper in (
            ("Season", 1, 4),
            ("Holiday", 0, 1),
            ("Day of the Week", 0, 6),
            ("Working Day", 0, 1),
            ("Weather Type", 1, 4),
            ("Humidity", 0, 100),
        ):
            value = _number(row, name)
            if value != int(value) or not lower <= value <= upper:
                raise ValueError(f"{name} is outside its integer range")
        for name in ("Temperature F", "Temperature Feels F", "Wind Speed"):
            _number(row, name)
        if _number(row, "Wind Speed") < 0:
            raise ValueError("Wind Speed must be nonnegative")
        if int(row["Season"]) != _season(timestamp.month):
            raise ValueError("Season does not match the documented month-based coding")
        if int(row["Day of the Week"]) != (timestamp.weekday() + 1) % 7:
            raise ValueError("Day of the Week does not match Date (Sunday=0)")
        working = int(timestamp.weekday() < 5 and row["Holiday"] == "0")
        if int(row["Working Day"]) != working:
            raise ValueError("Working Day contradicts weekday/holiday")
    times = {item.timestamp for item in dataset.observations}
    first, last = min(times), max(times)
    missing = []
    timestamp = first
    while timestamp <= last:
        if timestamp not in times:
            missing.append(timestamp)
        timestamp += timedelta(hours=1)
    return {
        "sha256": dataset.sha256,
        "bytes": path.stat().st_size,
        "columns": list(LOCAL_COLUMNS),
        "coverage": coverage(dataset.observations),
        "absent_hours_by_month": dict(
            sorted(Counter(t.strftime("%Y-%m") for t in missing).items())
        ),
        "observations_by_year": dict(sorted(Counter(str(t.year) for t in times).items())),
        "zero_rental_rows": sum(item.count == 0 for item in dataset.observations),
        "count_totals_consistent": True,
        "calendar_fields_consistent": True,
        "missing_cells": 0,
        "duplicate_timestamps": 0,
    }


def _compare(local: Path, upstream: Path) -> dict[str, object]:
    local_rows = {_timestamp(row): row for row in _table(local, LOCAL_COLUMNS)}
    rows = _table(upstream, UCI_COLUMNS)
    uci_rows = {_timestamp(row, uci=True): row for row in rows}
    if len(uci_rows) != len(rows):
        raise ValueError("UCI data contains duplicate timestamps")
    if local_rows.keys() != uci_rows.keys():
        raise ValueError("Local and UCI timestamp sets differ")
    matches: Counter[str] = Counter()
    season_recode_disagreements = 0
    for timestamp, row in local_rows.items():
        source = uci_rows[timestamp]
        expected = {name: _number(source, field) for name, field in DIRECT_FIELDS.items()}
        # These are recovered numeric relationships, not claims of physical correctness.
        temp = _number(source, "temp")
        expected.update(
            {
                "Season": Decimal(_season(timestamp.month)),
                "Temperature F": (
                    Decimal("17.6") + Decimal("84.6") * (temp - Decimal("0.02")) / Decimal("0.98")
                ).quantize(Decimal("0.1")),
                "Temperature Feels F": (
                    Decimal("3.2") + Decimal("118.8") * _number(source, "atemp")
                ).quantize(Decimal("0.1")),
                "Humidity": Decimal(100) * _number(source, "hum"),
                "Wind Speed": (Decimal(67) * _number(source, "windspeed")).quantize(Decimal(1)),
            }
        )
        for name, value in expected.items():
            if _number(row, name) != value:
                raise ValueError(f"{timestamp.isoformat()}: {name} differs from recovered UCI rule")
            matches[name] += 1
        season_recode_disagreements += int(
            int(row["Season"]) != (int(source["season"]) + 2) % 4 + 1
        )
    return {
        "sha256": hashlib.sha256(upstream.read_bytes()).hexdigest(),
        "bytes": upstream.stat().st_size,
        "observations": len(rows),
        "timestamp_sets_identical": True,
        "matched_rows_by_field": dict(sorted(matches.items())),
        "simple_season_recode_disagreements": season_recode_disagreements,
        "numeric_reconciliation_complete": True,
    }


def audit_dataset(path: Path, upstream: Path | None = None) -> dict[str, object]:
    """Validate local fields and optionally reconcile every row to UCI hour.csv.

    Fail on a mismatch. No forecast or model-selection metric is calculated.
    Source history, licensing and physical units require the accompanying prose.
    """
    return {
        "schema_version": 1,
        "local": _local_audit(path),
        "uci_comparison": _compare(path, upstream) if upstream is not None else None,
    }


def main(argv: list[str] | None = None) -> int:
    """Print deterministic audit JSON, optionally checking committed evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("bike.csv"))
    parser.add_argument(
        "--upstream", type=Path, help="Optional, separately downloaded UCI hour.csv"
    )
    parser.add_argument(
        "--check", type=Path, help="Compare against a saved audit (local only offline)"
    )
    args = parser.parse_args(argv)
    try:
        report = audit_dataset(args.data, args.upstream)
        if args.check is not None:
            expected = json.loads(args.check.read_text(encoding="utf-8"))
            keys = (
                ("schema_version", "local", "uci_comparison")
                if args.upstream
                else (
                    "schema_version",
                    "local",
                )
            )
            if not isinstance(expected, dict) or any(
                report[key] != expected.get(key) for key in keys
            ):
                raise ValueError("Audit differs from saved evidence")
    except (OSError, ValueError, csv.Error, ArithmeticError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
