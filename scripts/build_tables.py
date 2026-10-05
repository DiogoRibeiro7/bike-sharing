"""Generate Markdown and LaTeX tables directly from committed frozen evidence."""

import json
from pathlib import Path
from typing import Any

ROOT = Path("benchmarks/release-v1")


def read(name: str) -> Any:
    """Load one committed JSON run report."""
    return json.loads((ROOT / f"{name}.json").read_text())


def table(headers: list[str], rows: list[list[str]], name: str) -> None:
    """Write the same numeric rows to documentation and the LaTeX brief."""
    markdown = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    markdown.extend("| " + " | ".join(row) + " |" for row in rows)
    rendered = "\n".join(markdown) + "\n"
    Path(f"docs/assets/generated/{name}.md").write_text(rendered)
    final_page = Path("docs/final-results.md")
    if final_page.exists():
        assert rendered.strip() in final_page.read_text(), f"Stale final-results table: {name}"
    tex = [r"\begin{tabular}{" + "l" + "r" * (len(headers) - 1) + "}", r"\toprule"]
    for index, row in enumerate([headers, *rows]):
        tex.append(" & ".join(cell.replace("%", r"\%") for cell in row) + r" \\")
        if index == 0:
            tex.append(r"\midrule")
    tex.extend([r"\bottomrule", r"\end{tabular}"])
    Path(f"brief/{name}.tex").write_text("\n".join(tex) + "\n")


def main() -> None:
    """Refresh the three compact result tables without rerunning or selecting models."""
    Path("brief").mkdir(exist_ok=True)
    Path("docs/assets/generated").mkdir(parents=True, exist_ok=True)
    val = read("point-validation")["metrics"]["poisson_calendar"]
    test = read("point-test")["metrics"]["poisson_calendar"]
    table(
        ["Period", "Hours", "MAE", "RMSE"],
        [
            ["Validation", "2,208", f"{val['mae']:.3f}", f"{val['rmse']:.3f}"],
            ["Final test", "2,168", f"{test['mae']:.3f}", f"{test['rmse']:.3f}"],
        ],
        "point-results",
    )
    val = read("interval-validation")["metrics"]["poisson_calendar"]["intervals"]
    test = read("interval-test")["metrics"]["poisson_calendar"]["intervals"]
    table(
        ["Nominal", "Validation", "Final test", "Test width"],
        [
            [
                f"{float(level):.0%}",
                f"{val[level]['empirical_coverage']:.2%}",
                f"{test[level]['empirical_coverage']:.2%}",
                f"{test[level]['mean_width']:.3f}",
            ]
            for level in ("0.8", "0.9", "0.95")
        ],
        "interval-results",
    )
    val = read("planning-validation")["metrics"]
    test = read("planning-test")["metrics"]
    table(
        ["Cost ratio", "Validation cost", "Test cost", "Test target"],
        [
            [
                f"{float(r):g}",
                f"{val[r]['poisson_residual_quantile']['mean_cost']:.3f}",
                f"{test[r]['poisson_residual_quantile']['mean_cost']:.3f}",
                f"{test[r]['poisson_residual_quantile']['mean_action']:.3f}",
            ]
            for r in ("0.25", "0.5", "1.0", "2.0", "4.0", "9.0")
        ],
        "planning-results",
    )


if __name__ == "__main__":
    main()
