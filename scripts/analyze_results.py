from __future__ import annotations

"""
Meridian — per-question-type RAGAS breakdown.

Loads scored evaluation JSONs, groups by question_type, computes per-type
averages for each architecture, prints comparison tables, saves
data/evaluation/results/per_type_analysis.json.

Usage:
    python scripts/analyze_results.py
    python scripts/analyze_results.py --metric faithfulness
    python scripts/analyze_results.py --metric context_recall
"""

import sys
import os
os.environ["PYTHONUTF8"] = "1"

import argparse
import json
import datetime
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import RESULTS_DIR

ARCH_ORDER = [
    "naive", "hybrid", "fusion", "hierarchical",
    "corrective", "graph", "agentic", "full_system",
]
ARCH_SHORT = {
    "naive": "naive", "hybrid": "hybrid", "fusion": "fusion",
    "hierarchical": "hier", "corrective": "corr",
    "graph": "graph", "agentic": "agent", "full_system": "full",
}
QTYPE_ORDER = [
    "simple_factual", "numerical_reasoning", "temporal",
    "comparative", "multi_hop", "risk_qualitative",
]
METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_scored() -> dict[str, list[dict]]:
    data: dict[str, list[dict]] = {}
    for arch in ARCH_ORDER:
        path = RESULTS_DIR / f"{arch}.json"
        if not path.exists():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        scored = [r for r in rows if r.get("ragas_scored")]
        if scored:
            data[arch] = scored
    return data


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _avg(rows: list[dict], metric: str) -> float | None:
    vals = [r[metric] for r in rows if isinstance(r.get(metric), (int, float))]
    return round(sum(vals) / len(vals), 3) if vals else None


def build_analysis(data: dict[str, list[dict]]) -> dict:
    # Collect all question types present in the data
    all_qtypes: set[str] = set()
    for rows in data.values():
        for r in rows:
            qt = r.get("question_type")
            if qt:
                all_qtypes.add(qt)
    qtypes = [q for q in QTYPE_ORDER if q in all_qtypes] + sorted(all_qtypes - set(QTYPE_ORDER))
    archs  = [a for a in ARCH_ORDER if a in data]

    by_type: dict[str, dict[str, dict]] = {}
    for qtype in qtypes:
        by_type[qtype] = {}
        for arch in archs:
            rows = [r for r in data[arch] if r.get("question_type") == qtype]
            if not rows:
                continue
            entry = {"n": len(rows)}
            for m in METRICS:
                entry[m] = _avg(rows, m)
            by_type[qtype][arch] = entry

    # Best architecture per (question_type, metric)
    best_per_type: dict[str, dict[str, dict]] = {}
    for qtype in qtypes:
        best_per_type[qtype] = {}
        for metric in METRICS:
            best_arch, best_val = None, -1.0
            for arch, entry in by_type[qtype].items():
                v = entry.get(metric)
                if v is not None and v > best_val:
                    best_val, best_arch = v, arch
            if best_arch:
                best_per_type[qtype][metric] = {"arch": best_arch, "score": best_val}

    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "metrics": METRICS,
        "question_types": qtypes,
        "architectures": archs,
        "by_type": by_type,
        "best_per_type": best_per_type,
    }


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def _cell(val: float | None, width: int = 6) -> str:
    if val is None:
        return "—".center(width)
    return f"{val:.3f}".center(width)


def print_table(analysis: dict, metric: str) -> None:
    qtypes = analysis["question_types"]
    archs  = analysis["architectures"]
    by_type = analysis["by_type"]
    best    = analysis["best_per_type"]

    shorts = [ARCH_SHORT.get(a, a[:5]) for a in archs]
    col_w  = 7
    qtype_w = 18

    header = f"{'Question Type':<{qtype_w}}" + "".join(s.center(col_w) for s in shorts) + "  Best"
    sep    = "-" * len(header)

    print(f"\n{'='*60}")
    print(f"  Metric: {metric}")
    print(f"{'='*60}")
    print(header)
    print(sep)

    for qtype in qtypes:
        row = f"{qtype:<{qtype_w}}"
        for arch in archs:
            val = by_type.get(qtype, {}).get(arch, {}).get(metric)
            row += _cell(val, col_w)
        b = best.get(qtype, {}).get(metric)
        row += f"  {ARCH_SHORT.get(b['arch'], b['arch'])} ({b['score']:.3f})" if b else ""
        print(row)

    print()


def print_winners(analysis: dict) -> None:
    print(f"\n{'='*60}")
    print("  Best architecture per question type (faithfulness)")
    print(f"{'='*60}")
    for qtype in analysis["question_types"]:
        b = analysis["best_per_type"].get(qtype, {}).get("faithfulness")
        if b:
            print(f"  Best for {qtype:<22}: {b['arch']:<14} ({b['score']:.3f})")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Per-question-type RAGAS breakdown")
    parser.add_argument(
        "--metric", default="faithfulness",
        choices=METRICS,
        help="Primary metric to display in the comparison table.",
    )
    parser.add_argument(
        "--all-metrics", action="store_true",
        help="Print a table for every metric.",
    )
    args = parser.parse_args()

    data = load_scored()
    if not data:
        print("No scored results found. Run score_saved_results.py first.")
        sys.exit(1)

    scored_counts = {a: len(rows) for a, rows in data.items()}
    print(f"\nLoaded scored results: { {a: n for a, n in scored_counts.items()} }")

    analysis = build_analysis(data)

    metrics_to_print = METRICS if args.all_metrics else [args.metric]
    for m in metrics_to_print:
        print_table(analysis, m)

    print_winners(analysis)

    # Save JSON
    out_path = RESULTS_DIR / "per_type_analysis.json"
    out_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    main()
