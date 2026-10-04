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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the baseline study; return 2 for invalid input or inaccessible files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("bike.csv"), help="legacy CSV path")
    parser.add_argument(
        "--cutoff", default="2012-07-01", help="naive ISO timestamp; training is earlier"
    )
    parser.add_argument(
        "--horizon-hours", type=int, default=168, help="fixed forecast horizon (default: 168)"
    )
    parser.add_argument("--output", type=Path, help="write JSON here, or print it to stdout")
    args = parser.parse_args(argv)
    try:
        if args.output is not None and args.output.resolve() == args.data.resolve():
            raise ValueError("output must not overwrite the input dataset")
        report = evaluate(
            load_dataset(args.data), datetime.fromisoformat(args.cutoff), args.horizon_hours
        )
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
