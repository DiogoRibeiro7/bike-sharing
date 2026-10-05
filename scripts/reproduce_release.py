"""Replay frozen v1 evidence and compare numerical results without changing choices.

Run from the repository root. Outputs go to results/release-reproduction;
committed evidence is never overwritten. Replays are reproducibility checks,
not fresh independent holdouts or an opportunity to retune the procedure.
"""

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from bike_sharing.data import load_dataset
from bike_sharing.intervals import evaluate_interval_test, read_interval_selection
from bike_sharing.planning import evaluate_planning_test, read_planning_selection
from bike_sharing.study import evaluate_test, read_selection

EVIDENCE = Path("benchmarks/release-v1")
OUTPUT = Path("results/release-reproduction")


def compare(actual: Any, expected: Any, path: str = "report") -> None:
    """Compare exact structure with tolerance only for floating-point numerics."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), path
        for key in expected:
            # Runtime and local dependency patch versions are recorded, not statistical claims.
            if key not in {"environment", "runtime_seconds", "fit_predict_seconds"}:
                compare(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), path
        for index, (a, e) in enumerate(zip(actual, expected, strict=True)):
            compare(a, e, f"{path}[{index}]")
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-8), path
    else:
        assert actual == expected, path


def main() -> None:
    """Verify frozen source/selection hashes, replay all three saved test procedures."""
    manifest = json.loads((EVIDENCE / "freeze-manifest.json").read_text())
    for name, digest in manifest["source_sha256"].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
    for name, digest in manifest["validation_artifact_sha256"].items():
        assert hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest() == digest, name
    data = load_dataset(Path("bike.csv"))
    reports = {
        "point-test.json": evaluate_test(data, read_selection(EVIDENCE / "point-validation.json")),
        "interval-test.json": evaluate_interval_test(
            data, read_interval_selection(EVIDENCE / "interval-validation.json")
        ),
        "planning-test.json": evaluate_planning_test(
            data, read_planning_selection(EVIDENCE / "planning-validation.json")
        ),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, report in reports.items():
        expected = json.loads((EVIDENCE / name).read_text())
        compare(report, expected, name)
        (OUTPUT / name).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"Reproduced {name}")


if __name__ == "__main__":
    main()
