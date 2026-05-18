from __future__ import annotations

"""
Meridian — Composite scoring system.

Four composite scores per architecture:

  Score 1 — Quality Score
      Weighted combination of reliable metrics.
      numerical_accuracy: 0.35  (most reliable, domain-specific)
      faithfulness_proxy: 0.30  (answer grounding in retrieved chunks)
      citation_coverage:  0.20  (correct source attribution)
      keyword_hit_rate:   0.15  (domain vocabulary coverage)

  Score 2 — Efficiency Score  (quality per unit latency)
      quality / log10(retrieval_p50_ms + 1)
      log10 dampens extreme latency differences (fusion 40s vs naive 66ms)

  Score 3 — Cost-Quality Score  (quality per dollar)
      quality / (avg_cost / min_cost)
      Penalises architectures that cost proportionally more for same quality.
      Note: costs are tightly clustered ($0.10-0.13 per 1000 q); differences
      are small but included for completeness. BERTScore excluded — not
      computed in current pipeline (bert_score package absent).

  Score 4 — Production Score  (quality + speed + cost, normalised)
      quality_norm = quality / max(quality)
      speed_norm   = 1 - (p50_ms / max(p50_ms))
      cost_norm    = 1 - (avg_cost / max(avg_cost))
      production   = 0.50 * quality_norm + 0.30 * speed_norm + 0.20 * cost_norm

Usage:
    python evaluation/composite_score.py
    python evaluation/composite_score.py --architectures naive hybrid fusion
    python evaluation/composite_score.py --save
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RESULTS_DIR

METRICS_FILE = RESULTS_DIR / "reliable_metrics.json"

QUALITY_WEIGHTS = {
    "numerical_accuracy": 0.35,
    "faithfulness_proxy": 0.30,
    "citation_coverage":  0.20,
    "keyword_hit_rate":   0.15,
}

QUESTION_TYPES = [
    "simple_factual", "numerical_reasoning", "temporal",
    "comparative", "multi_hop", "risk_qualitative",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_metrics() -> dict:
    if not METRICS_FILE.exists():
        raise FileNotFoundError(
            f"reliable_metrics.json not found at {METRICS_FILE}\n"
            "Run: python evaluation/metrics_reliable.py --no-bert"
        )
    return json.loads(METRICS_FILE.read_text(encoding="utf-8"))


def _load_latency_cost(arch: str) -> tuple[float, float]:
    """Return (retrieval_p50_ms, avg_cost_per_query_usd) from result file."""
    p = RESULTS_DIR / f"{arch}.json"
    if not p.exists():
        return None, None
    data = json.loads(p.read_text(encoding="utf-8"))
    ret_vals = sorted(
        r["latency_breakdown"]["retrieval_ms"]
        for r in data if r.get("latency_breakdown")
    )
    costs = [r["estimated_cost_usd"] for r in data if "estimated_cost_usd" in r]
    if not ret_vals:
        return None, None
    p50 = ret_vals[len(ret_vals) // 2]
    avg_cost = sum(costs) / len(costs) if costs else 0.0
    return p50, avg_cost


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def _quality_score(overall: dict) -> float | None:
    """Weighted quality score from overall metrics dict."""
    total_w, total_v = 0.0, 0.0
    for metric, weight in QUALITY_WEIGHTS.items():
        v = overall.get(metric)
        if v is not None:
            total_v += weight * v
            total_w += weight
    if total_w == 0:
        return None
    # Re-normalise weights if some metrics are missing
    return round(total_v / total_w, 4)


def _quality_score_type(type_data: dict) -> float | None:
    total_w, total_v = 0.0, 0.0
    for metric, weight in QUALITY_WEIGHTS.items():
        v = type_data.get(metric)
        if v is not None:
            total_v += weight * v
            total_w += weight
    if total_w == 0:
        return None
    return round(total_v / total_w, 4)


def compute_scores(
    architectures: list[str],
    metrics_data: dict,
) -> dict[str, dict]:
    """
    Returns {arch: {quality, efficiency, cost_quality, production,
                    p50_ms, avg_cost, per_type_quality}}
    """
    arch_data = metrics_data.get("architectures", {})

    # First pass — gather raw values
    raw: dict[str, dict] = {}
    for arch in architectures:
        if arch not in arch_data:
            continue
        overall = arch_data[arch].get("overall", {})
        p50, avg_cost = _load_latency_cost(arch)
        if p50 is None:
            continue

        q = _quality_score(overall)
        if q is None:
            continue

        per_type = {}
        for qtype in QUESTION_TYPES:
            td = arch_data[arch].get("by_question_type", {}).get(qtype, {})
            per_type[qtype] = _quality_score_type(td)

        raw[arch] = {
            "quality":    q,
            "p50_ms":     p50,
            "avg_cost":   avg_cost,
            "per_type":   per_type,
        }

    if not raw:
        return {}

    # Normalisation denominators (overall)
    max_quality  = max(v["quality"]  for v in raw.values())
    max_p50      = max(v["p50_ms"]   for v in raw.values())
    max_cost     = max(v["avg_cost"] for v in raw.values())
    min_cost     = min(v["avg_cost"] for v in raw.values())

    # Per-type max quality (for production normalisation per type)
    max_quality_per_type: dict[str, float] = {}
    for qtype in QUESTION_TYPES:
        vals = [r["per_type"].get(qtype) for r in raw.values() if r["per_type"].get(qtype) is not None]
        max_quality_per_type[qtype] = max(vals) if vals else 1.0

    scores: dict[str, dict] = {}
    for arch, r in raw.items():
        q     = r["quality"]
        p50   = r["p50_ms"]
        cost  = r["avg_cost"]

        cost_ratio = (cost / min_cost) if min_cost > 0 else 1.0
        spd_norm   = 1 - (p50 / max_p50)
        cost_norm  = 1 - (cost / max_cost) if max_cost > 0 else 1.0

        # Score 2: efficiency  (quality per log-latency)
        efficiency = round(q / math.log10(p50 + 1), 4)

        # Score 3: cost-quality  (quality penalised by relative cost)
        cost_quality = round(q / cost_ratio, 4)

        # Score 4: production (normalised multi-dimension)
        q_norm    = q / max_quality
        production = round(0.50 * q_norm + 0.30 * spd_norm + 0.20 * cost_norm, 4)

        # Per-type all 4 scores (latency/cost same as overall — arch-level property)
        per_type_scores: dict[str, dict] = {}
        for qtype in QUESTION_TYPES:
            tq = r["per_type"].get(qtype)
            if tq is None:
                per_type_scores[qtype] = {}
                continue
            t_eff  = round(tq / math.log10(p50 + 1), 4)
            t_cq   = round(tq / cost_ratio, 4)
            max_tq = max_quality_per_type.get(qtype, 1.0)
            t_prod = round(0.50 * (tq / max_tq) + 0.30 * spd_norm + 0.20 * cost_norm, 4)
            per_type_scores[qtype] = {
                "quality":      round(tq, 4),
                "efficiency":   t_eff,
                "cost_quality": t_cq,
                "production":   t_prod,
            }

        scores[arch] = {
            "quality":          q,
            "efficiency":       efficiency,
            "cost_quality":     cost_quality,
            "production":       production,
            "p50_ms":           p50,
            "avg_cost_usd":     cost,
            "per_type_quality": r["per_type"],
            "per_type_scores":  per_type_scores,
        }

    return scores


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def _rank(scores: dict, key: str) -> list[tuple[str, float]]:
    return sorted(
        [(a, s[key]) for a, s in scores.items() if s.get(key) is not None],
        key=lambda x: x[1], reverse=True,
    )


def print_report(scores: dict) -> None:
    archs = list(scores.keys())
    sep = "=" * 78

    print(f"\n{sep}")
    print("  COMPOSITE SCORES")
    print(sep)
    print(f"  {'Architecture':<20}  {'Quality':>8}  {'Efficiency':>10}  {'CostQual':>9}  {'Production':>10}  {'P50 ms':>8}  {'$/q':>8}")
    print(f"  {'-'*20}  {'-'*8}  {'-'*10}  {'-'*9}  {'-'*10}  {'-'*8}  {'-'*8}")

    # Determine column winners for highlighting
    winners = {
        k: _rank(scores, k)[0][0]
        for k in ("quality", "efficiency", "cost_quality", "production")
    }

    for arch in _rank(scores, "quality"):
        arch = arch[0]
        s = scores[arch]
        def cell(k):
            v = s.get(k)
            marker = " *" if winners.get(k) == arch else "  "
            return f"{v:.4f}{marker}" if v is not None else "    --  "

        print(
            f"  {arch:<20}  {cell('quality'):>10}  {cell('efficiency'):>12}  "
            f"{cell('cost_quality'):>11}  {cell('production'):>12}  "
            f"{s['p50_ms']:>8.0f}  {s['avg_cost_usd']*1000:>7.4f}m"
        )

    print(f"\n  * = best in column   $/q shown in milli-dollars (x1000)")

    # Winner by scenario
    print(f"\n{sep}")
    print("  WINNER BY SCENARIO")
    print(sep)
    scenarios = [
        ("Best pure quality",    "quality"),
        ("Best efficiency",      "efficiency"),
        ("Best cost-quality",    "cost_quality"),
        ("Best for production",  "production"),
    ]
    for label, key in scenarios:
        ranked = _rank(scores, key)
        if ranked:
            arch, val = ranked[0]
            print(f"  {label:<25}  {arch:<16}  ({val:.4f})")

    # Per-type all 4 scores
    score_keys = [
        ("quality",      "QUALITY SCORE"),
        ("efficiency",   "EFFICIENCY SCORE"),
        ("cost_quality", "COST-QUALITY SCORE"),
        ("production",   "PRODUCTION SCORE"),
    ]

    for score_key, score_label in score_keys:
        print(f"\n{sep}")
        print(f"  PER-TYPE {score_label} (all architectures)")
        print(sep)
        header = f"  {'Type':<22}"
        for a in archs:
            header += f"  {a[:8]:>8}"
        header += "  BEST"
        print(header)
        print(f"  {'-'*22}" + "  " + "  ".join(["-"*8]*len(archs)) + "  " + "-"*12)

        for qtype in QUESTION_TYPES:
            type_vals = {
                a: scores[a]["per_type_scores"].get(qtype, {}).get(score_key)
                for a in archs
            }
            valid = {a: v for a, v in type_vals.items() if v is not None}
            best_val  = max(valid.values()) if valid else None
            best_arch = max(valid, key=valid.get) if valid else "--"
            row = f"  {qtype:<22}"
            for a in archs:
                v = type_vals.get(a)
                if v is None:
                    row += f"  {'  --':>8}"
                elif v == best_val:
                    row += f"  {f'*{v:.3f}*':>8}"
                else:
                    row += f"  {f' {v:.3f} ':>8}"
            row += f"  {best_arch}"
            print(row)

        # Winner summary row
        print(f"  {'-'*22}" + "  " + "  ".join(["-"*8]*len(archs)) + "  " + "-"*12)
        overall_vals = {a: scores[a].get(score_key) for a in archs}
        ov = {a: v for a, v in overall_vals.items() if v is not None}
        best_o = max(ov, key=ov.get) if ov else "--"
        best_ov = ov.get(best_o)
        row = f"  {'OVERALL':<22}"
        for a in archs:
            v = overall_vals.get(a)
            if v is None:
                row += f"  {'  --':>8}"
            elif v == best_ov:
                row += f"  {f'*{v:.3f}*':>8}"
            else:
                row += f"  {f' {v:.3f} ':>8}"
        row += f"  {best_o}"
        print(row)

    print(f"\n{sep}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Meridian composite scoring")
    parser.add_argument(
        "--architectures", "-a", nargs="+", metavar="ARCH",
        default=None,
        help="Architectures to include (default: all in reliable_metrics.json).",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save scores to data/evaluation/results/composite_scores.json",
    )
    args = parser.parse_args()

    metrics_data = _load_metrics()
    available = list(metrics_data.get("architectures", {}).keys())

    archs = args.architectures if args.architectures else available
    missing = [a for a in archs if a not in available]
    if missing:
        print(f"Warning: not in reliable_metrics.json: {missing}", file=sys.stderr)
        archs = [a for a in archs if a not in missing]

    if not archs:
        raise SystemExit("No architectures to score.")

    scores = compute_scores(archs, metrics_data)
    print_report(scores)

    if args.save:
        out = RESULTS_DIR / "composite_scores.json"
        out.write_text(json.dumps(scores, indent=2), encoding="utf-8")
        print(f"Saved -> {out}")


if __name__ == "__main__":
    main()
