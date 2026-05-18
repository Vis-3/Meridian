"""
Meridian — Custom Metrics
==========================
Latency percentiles, citation accuracy, cost totals, and per-slice breakdowns
on top of the raw per-question result dicts produced by ragas_runner.py.

All thresholds come from config.py — no magic numbers here.

Usage (standalone):
    python evaluation/metrics.py data/evaluation/results/naive.json

Usage (imported):
    from evaluation.metrics import compute_all
    summary = compute_all(results)          # results = list[dict] from ragas_runner
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean, median, quantiles
from typing import Any

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from config import FAITHFULNESS_THRESHOLD, RETRIEVAL_RELEVANCE_THRESHOLD

# RAGAS metric keys present in every result dict
_RAGAS_KEYS = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "answer_correctness",
]

# Question types in the benchmark
_TYPES = [
    "simple_factual",
    "numerical_reasoning",
    "temporal",
    "comparative",
    "multi_hop",
    "risk_qualitative",
]

_DIFFICULTIES = ["easy", "medium", "hard"]


# ---------------------------------------------------------------------------
# Percentile helpers
# ---------------------------------------------------------------------------

def _percentiles(values: list[float]) -> dict[str, float]:
    """Return P50, P95, P99 for a list of floats. Empty list → all zeros."""
    if not values:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    sorted_v = sorted(values)
    n = len(sorted_v)
    def _p(pct: float) -> float:
        idx = (pct / 100) * (n - 1)
        lo, hi = int(idx), min(int(idx) + 1, n - 1)
        return round(sorted_v[lo] + (idx - lo) * (sorted_v[hi] - sorted_v[lo]), 2)
    return {"p50": _p(50), "p95": _p(95), "p99": _p(99)}


def _safe_mean(values: list[float]) -> float:
    return round(mean(values), 4) if values else 0.0


# ---------------------------------------------------------------------------
# Citation accuracy
# ---------------------------------------------------------------------------

def citation_accuracy(results: list[dict]) -> float:
    """
    Fraction of questions where at least one citation was returned.
    A question with citations=[] scores 0; anything else scores 1.
    Averaged across all results.

    A full citation-level check (does every claim trace to a chunk?)
    requires an LLM judge and is deferred to the faithfulness score.
    This is the lightweight structural check.
    """
    if not results:
        return 0.0
    hits = sum(1 for r in results if r.get("n_citations", 0) > 0)
    return round(hits / len(results), 4)


# ---------------------------------------------------------------------------
# Latency
# ---------------------------------------------------------------------------

def latency_stats(results: list[dict]) -> dict[str, Any]:
    """P50/P95/P99 latency in ms, plus mean."""
    values = [r["latency_ms"] for r in results if "latency_ms" in r]
    pcts   = _percentiles(values)
    return {**pcts, "mean": _safe_mean(values)}


# ---------------------------------------------------------------------------
# Per-slice breakdowns
# ---------------------------------------------------------------------------

def _slice_metrics(results: list[dict], key: str, values: list) -> dict[str, dict]:
    """
    For each value in `values`, filter results to that slice and compute
    mean RAGAS scores + latency stats.
    """
    out: dict[str, dict] = {}
    for v in values:
        subset = [r for r in results if r.get(key) == v]
        if not subset:
            continue
        ragas_means = {
            k: _safe_mean([r[k] for r in subset if k in r])
            for k in _RAGAS_KEYS
        }
        out[str(v)] = {
            "n":          len(subset),
            **ragas_means,
            "latency_ms": latency_stats(subset),
            "citation_accuracy": citation_accuracy(subset),
        }
    return out


def by_question_type(results: list[dict]) -> dict[str, dict]:
    return _slice_metrics(results, "question_type", _TYPES)


def by_difficulty(results: list[dict]) -> dict[str, dict]:
    return _slice_metrics(results, "difficulty", _DIFFICULTIES)


def by_covid(results: list[dict]) -> dict[str, dict]:
    return {
        "covid":     _slice_metrics([r for r in results if r.get("covid_related")],
                                    "covid_related", [True]).get("True", {}),
        "non_covid": _slice_metrics([r for r in results if not r.get("covid_related")],
                                    "covid_related", [False]).get("False", {}),
    }


def by_company(results: list[dict]) -> dict[str, dict]:
    """
    Breaks down by company.  A question referencing multiple companies
    contributes to each company's slice.
    """
    from config import COMPANIES
    out: dict[str, dict] = {}
    for company in COMPANIES:
        subset = [r for r in results if company in r.get("companies", [])]
        if not subset:
            continue
        ragas_means = {
            k: _safe_mean([r[k] for r in subset if k in r])
            for k in _RAGAS_KEYS
        }
        out[company] = {
            "n":          len(subset),
            **ragas_means,
            "latency_ms": latency_stats(subset),
            "citation_accuracy": citation_accuracy(subset),
        }
    return out


def by_year(results: list[dict]) -> dict[str, dict]:
    """Breakdown by fiscal year."""
    from config import YEARS
    out: dict[str, dict] = {}
    for year in YEARS:
        subset = [r for r in results if year in r.get("years", [])]
        if not subset:
            continue
        ragas_means = {
            k: _safe_mean([r[k] for r in subset if k in r])
            for k in _RAGAS_KEYS
        }
        out[str(year)] = {
            "n":          len(subset),
            **ragas_means,
            "latency_ms": latency_stats(subset),
        }
    return out


# ---------------------------------------------------------------------------
# Faithfulness threshold pass rate
# ---------------------------------------------------------------------------

def faithfulness_pass_rate(results: list[dict]) -> float:
    """Fraction of questions scoring >= FAITHFULNESS_THRESHOLD."""
    scored = [r for r in results if "faithfulness" in r]
    if not scored:
        return 0.0
    passed = sum(1 for r in scored if r["faithfulness"] >= FAITHFULNESS_THRESHOLD)
    return round(passed / len(scored), 4)


def relevancy_pass_rate(results: list[dict]) -> float:
    """Fraction of questions scoring >= RETRIEVAL_RELEVANCE_THRESHOLD on answer_relevancy."""
    scored = [r for r in results if "answer_relevancy" in r]
    if not scored:
        return 0.0
    passed = sum(
        1 for r in scored
        if r["answer_relevancy"] >= RETRIEVAL_RELEVANCE_THRESHOLD
    )
    return round(passed / len(scored), 4)


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------

def total_cost(results: list[dict]) -> dict[str, float]:
    costs = [r.get("estimated_cost_usd", 0.0) for r in results]
    return {
        "total_usd": round(sum(costs), 4),
        "mean_usd":  round(_safe_mean(costs), 6),
    }


# ---------------------------------------------------------------------------
# Keyword hit rate (risk_qualitative only)
# ---------------------------------------------------------------------------

def keyword_hit_rate_summary(results: list[dict]) -> dict[str, float]:
    """Mean keyword hit rate for risk_qualitative questions."""
    rq = [
        r["keyword_hit_rate"]
        for r in results
        if r.get("question_type") == "risk_qualitative"
        and r.get("keyword_hit_rate") is not None
    ]
    if not rq:
        return {}
    return {"mean_keyword_hit_rate": _safe_mean(rq), "n": len(rq)}


# ---------------------------------------------------------------------------
# Master summary
# ---------------------------------------------------------------------------

def compute_all(results: list[dict]) -> dict[str, Any]:
    """
    Compute every metric for a list of per-question results.
    Returns a single nested dict suitable for JSON serialisation.
    """
    if not results:
        return {"error": "no results"}

    arch_name = results[0].get("architecture_name", "unknown")
    n         = len(results)

    overall_ragas = {
        k: _safe_mean([r[k] for r in results if k in r])
        for k in _RAGAS_KEYS
    }

    return {
        "architecture":          arch_name,
        "n_questions":           n,
        "overall": {
            **overall_ragas,
            "faithfulness_pass_rate":  faithfulness_pass_rate(results),
            "relevancy_pass_rate":     relevancy_pass_rate(results),
            "citation_accuracy":       citation_accuracy(results),
            "latency_ms":              latency_stats(results),
            "cost":                    total_cost(results),
        },
        "by_question_type":      by_question_type(results),
        "by_difficulty":         by_difficulty(results),
        "by_covid":              by_covid(results),
        "by_company":            by_company(results),
        "by_year":               by_year(results),
        "keyword_hit_rate":      keyword_hit_rate_summary(results),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python evaluation/metrics.py <results_file.json>")
        sys.exit(1)

    path    = Path(sys.argv[1])
    results = _load(path)
    summary = compute_all(results)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
