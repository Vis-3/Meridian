"""
Meridian — Results Analyzer
==============================
Loads all per-architecture result files from data/evaluation/results/,
computes the full metrics summary for each, and produces:
  1. A comparison table (architectures × metrics) printed to stdout.
  2. data/evaluation/results/comparison.json — all summaries in one file.

Usage:
    python evaluation/results_analyzer.py
    python evaluation/results_analyzer.py --format markdown
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from config import RESULTS_DIR
from evaluation.metrics import compute_all, _RAGAS_KEYS

# Architectures in display order
_ARCH_ORDER = [
    "naive",
    "hybrid",
    "fusion",
    "hierarchical",
    "corrective",
    "graph",
    "agentic",
    "full_system",
]

# Top-level metrics shown in the comparison table
_TABLE_METRICS = [
    ("faithfulness",         "Faithful"),
    ("answer_relevancy",     "Relevancy"),
    ("context_precision",    "Ctx Prec"),
    ("context_recall",       "Ctx Recall"),
    ("answer_correctness",   "Correctness"),
    ("citation_accuracy",    "Cite Acc"),
    ("faithfulness_pass_rate", "Faith>=0.7"),
]


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_all_results() -> dict[str, list[dict]]:
    """Load every {arch}.json from RESULTS_DIR. Skip comparison.json."""
    all_results: dict[str, list[dict]] = {}
    for path in sorted(RESULTS_DIR.glob("*.json")):
        if path.stem == "comparison":
            continue
        with open(path, encoding="utf-8") as f:
            all_results[path.stem] = json.load(f)
    return all_results


# ---------------------------------------------------------------------------
# Comparison table
# ---------------------------------------------------------------------------

def _fmt(val: object, width: int = 8) -> str:
    if isinstance(val, float):
        return f"{val:.4f}".rjust(width)
    if val is None:
        return "  --  ".rjust(width)
    return str(val).rjust(width)


def print_comparison_table(
    summaries: dict[str, dict],
    fmt: str = "plain",
) -> None:
    """Print architecture × metric comparison table."""
    arch_names = [a for a in _ARCH_ORDER if a in summaries]

    col_w   = 12
    metric_w = 10

    if fmt == "markdown":
        # Header
        header = "| Architecture |" + "".join(
            f" {label:<{metric_w}} |" for _, label in _TABLE_METRICS
        ) + " Lat P50ms |"
        sep = "|" + "|".join(["-" * (col_w + 2)] + ["-" * (metric_w + 2)] * len(_TABLE_METRICS) + ["-" * 11]) + "|"
        print(header)
        print(sep)
        for arch in arch_names:
            s = summaries[arch]["overall"]
            row = f"| {arch:<{col_w}} |"
            for key, _ in _TABLE_METRICS:
                row += f" {s.get(key, 0.0):.4f}     |"
            row += f" {s['latency_ms']['p50']:>8.1f} |"
            print(row)
    else:
        # Plain text table
        header = f"{'Architecture':<{col_w}}"
        for _, label in _TABLE_METRICS:
            header += f"  {label:>{metric_w}}"
        header += f"  {'LatP50ms':>{metric_w}}"
        print("\n" + "=" * len(header))
        print(header)
        print("=" * len(header))
        for arch in arch_names:
            s   = summaries[arch]["overall"]
            row = f"{arch:<{col_w}}"
            for key, _ in _TABLE_METRICS:
                row += _fmt(s.get(key), metric_w + 2)
            row += _fmt(s["latency_ms"]["p50"], metric_w + 2)
            print(row)
        print("=" * len(header))


def print_type_breakdown(summaries: dict[str, dict]) -> None:
    """Print faithfulness score per question type per architecture."""
    arch_names = [a for a in _ARCH_ORDER if a in summaries]
    types      = [
        "simple_factual", "numerical_reasoning", "temporal",
        "comparative", "multi_hop", "risk_qualitative",
    ]
    col_w = 22
    arch_w = 10

    print(f"\n{'Question type':<{col_w}}" + "".join(f"  {a[:arch_w]:>{arch_w}}" for a in arch_names))
    print("-" * (col_w + len(arch_names) * (arch_w + 2)))
    for t in types:
        row = f"{t:<{col_w}}"
        for arch in arch_names:
            val = summaries[arch].get("by_question_type", {}).get(t, {}).get("faithfulness")
            row += _fmt(val, arch_w + 2)
        print(row)


def print_covid_comparison(summaries: dict[str, dict]) -> None:
    """Print faithfulness: covid vs non-covid per architecture."""
    arch_names = [a for a in _ARCH_ORDER if a in summaries]
    print("\nCOVID vs non-COVID faithfulness:")
    print(f"  {'Architecture':<14}  {'COVID':>8}  {'Non-COVID':>10}")
    print("  " + "-" * 36)
    for arch in arch_names:
        covid_f = (
            summaries[arch].get("by_covid", {}).get("covid", {}).get("faithfulness", 0.0)
        )
        nc_f = (
            summaries[arch].get("by_covid", {}).get("non_covid", {}).get("faithfulness", 0.0)
        )
        print(f"  {arch:<14}  {covid_f:>8.4f}  {nc_f:>10.4f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Meridian results comparison")
    parser.add_argument(
        "--format", "-f",
        choices=["plain", "markdown"],
        default="plain",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Write comparison.json to this path (default: RESULTS_DIR/comparison.json)",
    )
    args = parser.parse_args()

    all_results = load_all_results()
    if not all_results:
        print(f"No result files found in {RESULTS_DIR}. Run ragas_runner.py first.")
        sys.exit(1)

    # Compute summaries
    summaries: dict[str, dict] = {
        arch: compute_all(results)
        for arch, results in all_results.items()
    }

    # Print tables
    print_comparison_table(summaries, fmt=args.format)
    print_type_breakdown(summaries)
    print_covid_comparison(summaries)

    # Write combined JSON
    out_path = Path(args.output) if args.output else RESULTS_DIR / "comparison.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)
    print(f"\nWrote comparison -> {out_path}")


if __name__ == "__main__":
    main()
