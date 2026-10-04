"""Command-line entry point for a reproducible baseline report."""

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from bike_sharing.data import load_dataset
from bike_sharing.forecasting import evaluate
from bike_sharing.splits import DEFAULT_SPLIT, StudySplit
from bike_sharing.study import evaluate_test, read_selection, select_on_validation


def main(argv: Sequence[str] | None = None) -> int:
    """Run the baseline study; return 2 for invalid input or inaccessible files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("bike.csv"), help="legacy CSV path")
    parser.add_argument("--stage", choices=("validation", "test"), default="validation")
    parser.add_argument("--selection", type=Path, help="saved validation report; required for test")
    parser.add_argument(
        "--validation-start", help="override validation boundary for a custom study"
    )
    parser.add_argument("--test-start", help="override test boundary for a custom study")
    parser.add_argument("--test-end", help="override exclusive study end")
    parser.add_argument(
        "--cutoff", help="optional validation diagnostic cutoff; does not produce a selection"
    )
    parser.add_argument(
        "--horizon-hours", type=int, help="diagnostic horizon; requires --cutoff (default: 168)"
    )
    parser.add_argument("--output", type=Path, help="write JSON here, or print it to stdout")
    args = parser.parse_args(argv)
    try:
        if args.output is not None and args.output.resolve() == args.data.resolve():
            raise ValueError("output must not overwrite the input dataset")
        if (
            args.selection is not None
            and args.output is not None
            and args.selection.resolve() == args.output.resolve()
        ):
            raise ValueError("output must not overwrite the frozen selection")
        overrides = (
            args.validation_start,
            args.test_start,
            args.test_end,
            args.cutoff,
            args.horizon_hours,
        )
        if args.stage == "test":
            if args.selection is None:
                raise ValueError("test evaluation requires --selection from a validation run")
            if any(value is not None for value in overrides):
                raise ValueError(
                    "test boundaries and model are frozen by --selection; overrides are forbidden"
                )
            report = evaluate_test(load_dataset(args.data), read_selection(args.selection))
        else:
            if args.selection is not None:
                raise ValueError("--selection is only valid with --stage test")
            split = StudySplit(
                datetime.fromisoformat(args.validation_start)
                if args.validation_start is not None
                else DEFAULT_SPLIT.validation_start,
                datetime.fromisoformat(args.test_start)
                if args.test_start is not None
                else DEFAULT_SPLIT.test_start,
                datetime.fromisoformat(args.test_end)
                if args.test_end is not None
                else DEFAULT_SPLIT.test_end,
            )
            dataset = load_dataset(args.data)
            if args.cutoff is not None:
                horizon = 168 if args.horizon_hours is None else args.horizon_hours
                report = evaluate(
                    dataset, datetime.fromisoformat(args.cutoff), horizon, split=split
                )
            else:
                if args.horizon_hours is not None:
                    raise ValueError("--horizon-hours requires --cutoff")
                report = select_on_validation(dataset, split)
        serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is None:
            print(serialized, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized, encoding="utf-8")
    except (OSError, ValueError, csv.Error, OverflowError) as exc:
        print(f"bike-sharing: {exc}", file=sys.stderr)
        return 2
    return 0
