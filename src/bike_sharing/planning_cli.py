"""Run the planning scenario study; real final testing is an explicit separate action."""

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from bike_sharing.data import load_dataset
from bike_sharing.planning import (
    evaluate_planning_test,
    evaluate_planning_validation,
    read_planning_selection,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Write validation evidence by default, or test only policies saved by validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("bike.csv"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--stage", choices=("validation", "test"), default="validation")
    parser.add_argument("--selection", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output is not None and any(
            args.output.resolve() == p.resolve()
            for p in (args.data, args.selection)
            if p is not None
        ):
            raise ValueError("output must not overwrite input data or selection")
        if args.stage == "test":
            if args.selection is None:
                raise ValueError("test requires a saved planning --selection")
            report = evaluate_planning_test(
                load_dataset(args.data), read_planning_selection(args.selection)
            )
        else:
            if args.selection is not None:
                raise ValueError("--selection is only valid for test")
            report = evaluate_planning_validation(load_dataset(args.data))
        output = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is None:
            print(output, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
    except (OSError, ValueError, csv.Error, OverflowError) as exc:
        print(f"bike-sharing-planning: {exc}", file=sys.stderr)
        return 2
    return 0
