"""Tests for evaluation/metrics.py — uses mock_result fixture, no RAGAS calls."""

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.metrics import (
    compute_all, latency_stats, faithfulness_pass_rate,
    citation_accuracy, by_question_type, keyword_hit_rate_summary,
    total_cost,
)


def _make_result(**overrides):
    base = {
        "question_id":        "q001",
        "architecture_name":  "naive",
        "faithfulness":       0.8,
        "answer_relevancy":   0.85,
        "context_precision":  0.75,
        "context_recall":     0.70,
        "answer_correctness": 0.80,
        "latency_ms":         4000.0,
        "tokens_used":        1200,
        "estimated_cost_usd": 0.00024,
        "keyword_hit_rate":   None,
        "question_type":      "simple_factual",
        "difficulty":         "easy",
        "covid_related":      False,
        "companies":          ["Apple"],
        "years":              [2023],
        "n_citations":        3,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# compute_all
# ---------------------------------------------------------------------------

def test_compute_all_returns_architecture_name(mock_result):
    summary = compute_all([mock_result])
    assert summary["architecture"] == mock_result["architecture_name"]


def test_compute_all_empty_returns_error():
    summary = compute_all([])
    assert "error" in summary


def test_compute_all_has_required_keys(mock_result):
    summary = compute_all([mock_result])
    for key in ("architecture", "n_questions", "overall", "by_question_type"):
        assert key in summary, f"compute_all missing key: {key}"


# ---------------------------------------------------------------------------
# latency_stats
# ---------------------------------------------------------------------------

def test_latency_stats_ordering():
    results = [_make_result(latency_ms=v) for v in [100, 500, 1000, 5000, 9000]]
    stats = latency_stats(results)
    assert stats["p50"] <= stats["p95"] <= stats["p99"], \
        "P50 <= P95 <= P99 must hold"


def test_latency_stats_empty():
    stats = latency_stats([])
    assert stats["p50"] == 0.0
    assert stats["p95"] == 0.0
    assert stats["p99"] == 0.0


# ---------------------------------------------------------------------------
# faithfulness_pass_rate
# ---------------------------------------------------------------------------

def test_faithfulness_pass_rate_all_pass():
    results = [_make_result(faithfulness=0.9) for _ in range(5)]
    assert faithfulness_pass_rate(results) == 1.0


def test_faithfulness_pass_rate_none_pass():
    results = [_make_result(faithfulness=0.1) for _ in range(5)]
    assert faithfulness_pass_rate(results) == 0.0


def test_faithfulness_pass_rate_half():
    results = (
        [_make_result(faithfulness=0.9) for _ in range(5)] +
        [_make_result(faithfulness=0.1) for _ in range(5)]
    )
    rate = faithfulness_pass_rate(results)
    assert abs(rate - 0.5) < 0.01


# ---------------------------------------------------------------------------
# citation_accuracy
# ---------------------------------------------------------------------------

def test_citation_accuracy_all_have_citations():
    results = [_make_result(n_citations=3) for _ in range(4)]
    assert citation_accuracy(results) == 1.0


def test_citation_accuracy_none_have_citations():
    results = [_make_result(n_citations=0) for _ in range(4)]
    assert citation_accuracy(results) == 0.0


# ---------------------------------------------------------------------------
# by_question_type
# ---------------------------------------------------------------------------

def test_by_question_type_has_all_types(mock_result):
    all_types = ["simple_factual", "numerical_reasoning", "temporal",
                 "comparative", "multi_hop", "risk_qualitative"]
    results = [_make_result(question_type=t) for t in all_types]
    breakdown = by_question_type(results)
    for t in all_types:
        assert t in breakdown, f"by_question_type missing type: {t}"


# ---------------------------------------------------------------------------
# keyword_hit_rate
# ---------------------------------------------------------------------------

def test_keyword_hit_rate_only_for_risk_qualitative():
    results = [
        _make_result(question_type="simple_factual", keyword_hit_rate=0.9),
        _make_result(question_type="risk_qualitative", keyword_hit_rate=0.75),
        _make_result(question_type="risk_qualitative", keyword_hit_rate=0.85),
    ]
    summary = keyword_hit_rate_summary(results)
    # Only the risk_qualitative entries should count
    assert summary["n"] == 2
    assert abs(summary["mean_keyword_hit_rate"] - 0.80) < 0.01


def test_keyword_hit_rate_empty_when_no_qualitative():
    results = [_make_result(question_type="simple_factual", keyword_hit_rate=0.9)]
    summary = keyword_hit_rate_summary(results)
    assert summary == {}


# ---------------------------------------------------------------------------
# total_cost
# ---------------------------------------------------------------------------

def test_total_cost_equals_sum():
    costs = [0.001, 0.002, 0.003]
    results = [_make_result(estimated_cost_usd=c) for c in costs]
    totals = total_cost(results)
    assert abs(totals["total_usd"] - sum(costs)) < 1e-6
