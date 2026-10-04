"""Command-line entry point for temporal interval calibration and evaluation."""

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from bike_sharing.calibration import IntervalSpec
from bike_sharing.data import load_dataset
from bike_sharing.intervals import (
    evaluate_interval_test,
    evaluate_interval_validation,
    read_interval_selection,
)
from bike_sharing.splits import DEFAULT_SPLIT, StudySplit


def main(argv: Sequence[str] | None = None) -> int:
    """Validate intervals by default; require a saved interval selection for final test."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("bike.csv"))
    parser.add_argument("--stage", choices=("validation", "test"), default="validation")
    parser.add_argument(
        "--selection", type=Path, help="saved interval validation report; only for test"
    )
    parser.add_argument("--fold-hours", type=int, help="forecast cadence (default: 168)")
    parser.add_argument(
        "--calibration-folds", type=int, help="preceding full horizons (default: 4)"
    )
    parser.add_argument("--validation-start")
    parser.add_argument("--test-start")
    parser.add_argument("--test-end")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output is not None and any(
            args.output.resolve() == path.resolve()
            for path in (args.data, args.selection)
            if path is not None
        ):
            raise ValueError("output must not overwrite the input dataset or frozen selection")
        overrides = (
            args.fold_hours,
            args.calibration_folds,
            args.validation_start,
            args.test_start,
            args.test_end,
        )
        if args.stage == "test":
            if args.selection is None:
                raise ValueError(
                    "test evaluation requires --selection from an interval validation run"
                )
            if any(value is not None for value in overrides):
                raise ValueError("test settings are frozen; overrides are forbidden")
            report = evaluate_interval_test(
                load_dataset(args.data), read_interval_selection(args.selection)
            )
        else:
            if args.selection is not None:
                raise ValueError("--selection is only valid with --stage test")
            split = StudySplit(
                *(
                    datetime.fromisoformat(value) if value is not None else default
                    for value, default in zip(
                        (args.validation_start, args.test_start, args.test_end),
                        (
                            DEFAULT_SPLIT.validation_start,
                            DEFAULT_SPLIT.test_start,
                            DEFAULT_SPLIT.test_end,
                        ),
                        strict=True,
                    )
                )
            )
            spec = IntervalSpec(
                calibration_folds=4 if args.calibration_folds is None else args.calibration_folds
            )
            report = evaluate_interval_validation(
                load_dataset(args.data),
                split,
                horizon_hours=168 if args.fold_hours is None else args.fold_hours,
                spec=spec,
            )
        serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is None:
            print(serialized, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized, encoding="utf-8")
    except (OSError, ValueError, csv.Error, OverflowError) as exc:
        print(f"bike-sharing-intervals: {exc}", file=sys.stderr)
        return 2
    return 0
