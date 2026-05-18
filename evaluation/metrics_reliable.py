from __future__ import annotations

"""
Meridian — Reliable evaluation metrics (no LLM API calls).

Five metrics computed purely locally:
  1. numerical_accuracy  — extract & compare numbers vs ground truth
  2. bertscore_f1        — BERTScore F1 between answer and ground truth
  3. keyword_hit_rate    — key terms from ground truth found in answer
  4. citation_coverage   — expected company/year mentioned in answer
  5. faithfulness_proxy  — lexical grounding of answer in retrieved chunks

Reads existing result JSON files; never modifies them.

Usage:
    python evaluation/metrics_reliable.py
    python evaluation/metrics_reliable.py --architecture naive hybrid
    python evaluation/metrics_reliable.py --no-bert
    python evaluation/metrics_reliable.py --no-bert --architecture all
"""

import sys
import os
os.environ["PYTHONUTF8"] = "1"

import argparse
import datetime
import json
import re
import string
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from config import RESULTS_DIR

ARCH_ORDER = [
    "naive", "hybrid", "fusion", "hierarchical",
    "corrective", "graph", "agentic", "full_system",
]

_STOP = {
    "a","an","the","in","on","of","to","for","is","was","were","are","be",
    "been","being","it","its","that","this","with","and","or","but","from",
    "by","at","as","had","has","have","their","they","them","which","who",
    "what","how","when","where","will","would","could","should","not","no",
    "do","did","does","also","than","more","less","most","least","both","all",
    "each","some","any","into","over","under","about","through","between",
    "during","after","before","since","until","while","per","total","net",
    "fiscal","year","fy","quarter","annual","billion","million","thousand",
    "dollars","usd","approximately","reported","including","following",
    "company","companies","inc","corp","llc","ltd",
}


# ---------------------------------------------------------------------------
# Number extraction helpers
# ---------------------------------------------------------------------------

def _extract_dollar_billions(text: str) -> list[float]:
    """Extract all dollar amounts, normalised to billions USD."""
    nums: list[float] = []
    text_l = text.lower()

    # $X.X trillion / T
    for m in re.finditer(r'\$\s*([\d,]+\.?\d*)\s*t(?:rillion)?', text_l):
        nums.append(float(m.group(1).replace(",", "")) * 1_000)

    # $X.X billion / B / bn
    for m in re.finditer(r'\$\s*([\d,]+\.?\d*)\s*(?:b(?:illion|n)?)', text_l):
        nums.append(float(m.group(1).replace(",", "")))

    # $X.X million / M
    for m in re.finditer(r'\$\s*([\d,]+\.?\d*)\s*(?:m(?:illion)?)', text_l):
        nums.append(float(m.group(1).replace(",", "")) / 1_000)

    # $XX,XXX (raw millions written out, e.g. "$394,328" in SEC filings)
    for m in re.finditer(r'\$\s*([\d]{2,3},[\d]{3})(?!\s*(?:m|b|t|k))', text_l):
        val = float(m.group(1).replace(",", "")) / 1_000
        nums.append(val)

    # bare X.XB / X.X billion after a currency word
    for m in re.finditer(r'(?:revenue|income|profit|sales|spend|capex|cost)'
                         r'[^$\d]{0,30}([\d]+\.?\d*)\s*(?:b(?:illion|n)?)', text_l):
        nums.append(float(m.group(1)))

    return nums


def _extract_percentages(text: str) -> list[float]:
    """Extract percentage values (strip the % sign, return as floats)."""
    return [float(m.group(1)) for m in re.finditer(r'([\d]+\.?\d*)\s*%', text)]


def _best_match(answer_vals: list[float], truth_vals: list[float]) -> float:
    """
    Return best score across all (answer, truth) pairs.
      1.0  if |a - t| / t <= 0.01   (exact, ±1%)
      0.5  if |a - t| / t <= 0.10   (ballpark, ±10%)
      0.0  otherwise
    """
    if not answer_vals or not truth_vals:
        return 0.0
    best = 0.0
    for a in answer_vals:
        for t in truth_vals:
            if t == 0:
                continue
            rel = abs(a - t) / abs(t)
            if rel <= 0.01:
                return 1.0
            elif rel <= 0.10:
                best = max(best, 0.5)
    return best


def numerical_accuracy(answer: str, ground_truth: str) -> float | None:
    """
    Compare numbers in answer vs ground truth.
    Returns None if ground truth contains no numbers (metric not applicable).
    """
    gt_dollars = _extract_dollar_billions(ground_truth)
    gt_pcts    = _extract_percentages(ground_truth)

    if not gt_dollars and not gt_pcts:
        return None   # no numerical ground truth to compare against

    ans_dollars = _extract_dollar_billions(answer)
    ans_pcts    = _extract_percentages(answer)

    dollar_score = _best_match(ans_dollars, gt_dollars) if gt_dollars else None
    pct_score    = _best_match(ans_pcts,    gt_pcts)    if gt_pcts    else None

    scores = [s for s in [dollar_score, pct_score] if s is not None]
    return round(sum(scores) / len(scores), 3) if scores else 0.0


# ---------------------------------------------------------------------------
# Keyword hit rate
# ---------------------------------------------------------------------------

def _keywords_from_ground_truth(ground_truth: str) -> list[str]:
    """Extract meaningful content words from ground truth."""
    tokens = re.findall(r"[a-zA-Z0-9']+", ground_truth.lower())
    return [
        t for t in tokens
        if len(t) >= 4 and t not in _STOP and not t.isdigit()
    ]


def keyword_hit_rate(answer: str, ground_truth: str) -> float | None:
    """Fraction of ground-truth keywords found in the answer (case-insensitive)."""
    kws = _keywords_from_ground_truth(ground_truth)
    if not kws:
        return None
    answer_l = answer.lower()
    hits = sum(1 for k in kws if k in answer_l)
    return round(hits / len(kws), 3)


# ---------------------------------------------------------------------------
# Citation coverage
# ---------------------------------------------------------------------------

def citation_coverage(answer: str, companies: list[str], years: list[int]) -> float:
    """
    Fraction of expected companies + years mentioned anywhere in the answer.
    Score = hits / (len(companies) + len(years)), or 0 if both lists empty.
    """
    if not companies and not years:
        return 0.0
    answer_l = answer.lower()
    total = len(companies) + len(years)
    hits = sum(1 for c in companies if c.lower() in answer_l)
    hits += sum(1 for y in years if str(y) in answer)
    return round(hits / total, 3)


# ---------------------------------------------------------------------------
# Faithfulness proxy — lexical grounding in retrieved chunks
# ---------------------------------------------------------------------------

def _word_set(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if len(t) >= 4 and t not in _STOP}


def faithfulness_proxy(answer: str, citations: list[dict]) -> float | None:
    """
    Sentence-level grounding: fraction of answer sentences whose key words
    appear in at least one retrieved chunk.
    Returns None if no citations (metric not applicable).
    """
    if not citations:
        return None

    chunk_words = set()
    for c in citations:
        chunk_words |= _word_set(c.get("text", ""))

    # Split answer into sentences
    sentences = [s.strip() for s in re.split(r'[.!?]', answer) if len(s.strip()) > 20]
    if not sentences:
        return None

    grounded = 0
    for sent in sentences:
        sent_words = _word_set(sent)
        if not sent_words:
            continue
        overlap = len(sent_words & chunk_words) / len(sent_words)
        if overlap >= 0.4:   # ≥40% of sentence key words present in chunks
            grounded += 1

    return round(grounded / len(sentences), 3)


# ---------------------------------------------------------------------------
# BERTScore (batched)
# ---------------------------------------------------------------------------

def compute_bertscore(
    answers: list[str],
    ground_truths: list[str],
    model_type: str = "distilbert-base-uncased",
) -> list[float]:
    """Return per-pair F1 BERTScore. Falls back to [] on import error."""
    try:
        from bert_score import score as _bert_score
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _, _, F1 = _bert_score(
            answers, ground_truths,
            model_type=model_type,
            lang="en",
            device=device,
            verbose=False,
        )
        return [round(float(f), 3) for f in F1]
    except Exception as e:
        print(f"  [BERTScore] failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Per-question scoring
# ---------------------------------------------------------------------------

def score_result(r: dict) -> dict[str, float | None]:
    answer       = r.get("answer", "") or ""
    ground_truth = r.get("ground_truth", "") or ""
    companies    = r.get("companies", []) or []
    years        = r.get("years", []) or []
    citations    = r.get("citations", []) or []

    # Use pre-computed faithfulness_proxy from agentic if available
    fp = r.get("faithfulness_proxy")
    if fp is None:
        fp = faithfulness_proxy(answer, citations)

    return {
        "numerical_accuracy": numerical_accuracy(answer, ground_truth),
        "keyword_hit_rate":   keyword_hit_rate(answer, ground_truth),
        "citation_coverage":  citation_coverage(answer, companies, years),
        "faithfulness_proxy": fp,
        # bertscore_f1 filled in batch after this loop
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _mean(vals: list) -> float | None:
    v = [x for x in vals if isinstance(x, (int, float))]
    return round(sum(v) / len(v), 3) if v else None


def _fmt(v) -> str:
    return f"{v:.3f}" if isinstance(v, float) else "  — "


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_results(archs: list[str]) -> dict[str, list[dict]]:
    data: dict[str, list[dict]] = {}
    for arch in archs:
        path = RESULTS_DIR / f"{arch}.json"
        if not path.exists():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        if rows:
            data[arch] = rows
    return data


def run(archs: list[str], use_bert: bool, bert_model: str) -> dict:
    data = load_results(archs)
    if not data:
        print("No result files found.")
        sys.exit(1)

    print(f"\nArchitectures: {list(data.keys())}")
    print(f"BERTScore: {'enabled (' + bert_model + ')' if use_bert else 'disabled'}\n")

    results_out: dict[str, dict] = {}

    for arch, rows in data.items():
        print(f"  Scoring {arch} ({len(rows)} questions)...", end=" ", flush=True)

        per_q: list[dict] = []
        for r in rows:
            scores = score_result(r)
            scores["question_id"]   = r.get("question_id")
            scores["question_type"] = r.get("question_type")
            per_q.append(scores)

        # BERTScore — batch all questions with valid ground truth
        bert_scores: list[float | None] = [None] * len(rows)
        if use_bert:
            idx_valid = [
                i for i, r in enumerate(rows)
                if r.get("answer") and r.get("ground_truth")
            ]
            if idx_valid:
                answers_b = [rows[i]["answer"]       for i in idx_valid]
                truths_b  = [rows[i]["ground_truth"] for i in idx_valid]
                f1s = compute_bertscore(answers_b, truths_b, bert_model)
                if f1s and len(f1s) == len(idx_valid):
                    for j, i in enumerate(idx_valid):
                        bert_scores[i] = f1s[j]
        for i, s in enumerate(bert_scores):
            per_q[i]["bertscore_f1"] = s

        # Aggregate
        agg = {
            "n": len(rows),
            "numerical_accuracy":  _mean([q["numerical_accuracy"]  for q in per_q]),
            "bertscore_f1":        _mean([q["bertscore_f1"]        for q in per_q]),
            "keyword_hit_rate":    _mean([q["keyword_hit_rate"]     for q in per_q]),
            "citation_coverage":   _mean([q["citation_coverage"]    for q in per_q]),
            "faithfulness_proxy":  _mean([q["faithfulness_proxy"]   for q in per_q]),
        }

        # By question type
        qtypes = sorted({q["question_type"] for q in per_q if q["question_type"]})
        by_type: dict[str, dict] = {}
        for qt in qtypes:
            subset = [q for q in per_q if q.get("question_type") == qt]
            by_type[qt] = {
                "n": len(subset),
                "numerical_accuracy": _mean([q["numerical_accuracy"]  for q in subset]),
                "bertscore_f1":       _mean([q["bertscore_f1"]        for q in subset]),
                "keyword_hit_rate":   _mean([q["keyword_hit_rate"]     for q in subset]),
                "citation_coverage":  _mean([q["citation_coverage"]    for q in subset]),
                "faithfulness_proxy": _mean([q["faithfulness_proxy"]   for q in subset]),
            }

        results_out[arch] = {"overall": agg, "by_question_type": by_type, "per_question": per_q}
        print("done")

    return results_out


def print_table(results_out: dict) -> None:
    archs   = list(results_out.keys())
    metrics = ["numerical_accuracy", "bertscore_f1",
               "keyword_hit_rate", "citation_coverage", "faithfulness_proxy"]
    short   = ["NumAcc", "BERT-F1", "KwHit", "Cit.Cov", "Faith.P"]

    col_w = 9
    arch_w = 14

    print(f"\n{'='*70}")
    print("  Reliable Metrics — Architecture Comparison")
    print(f"{'='*70}")
    header = f"{'Architecture':<{arch_w}}" + "".join(s.center(col_w) for s in short)
    print(header)
    print("-" * len(header))

    for arch in archs:
        agg = results_out[arch]["overall"]
        row = f"{arch:<{arch_w}}"
        for m in metrics:
            row += _fmt(agg.get(m)).center(col_w)
        print(row)

    print(f"\n{'='*70}")
    print("  By Question Type  (faithfulness proxy)")
    print(f"{'='*70}")

    all_qtypes: set[str] = set()
    for v in results_out.values():
        all_qtypes |= set(v["by_question_type"].keys())
    qtypes = sorted(all_qtypes)

    qtype_w = 22
    header2 = f"{'Question Type':<{qtype_w}}" + "".join(a[:col_w-1].center(col_w) for a in archs)
    print(header2)
    print("-" * len(header2))
    for qt in qtypes:
        row = f"{qt:<{qtype_w}}"
        for arch in archs:
            v = results_out[arch]["by_question_type"].get(qt, {}).get("faithfulness_proxy")
            row += _fmt(v).center(col_w)
        print(row)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reliable (no-API) evaluation metrics")
    parser.add_argument(
        "--architecture", "-a", nargs="+",
        default=["all"],
        choices=ARCH_ORDER + ["all"],
        metavar="ARCH",
        help="Architectures to score (default: all).",
    )
    parser.add_argument(
        "--no-bert", action="store_true",
        help="Skip BERTScore (saves ~2 min, no GPU needed).",
    )
    parser.add_argument(
        "--bert-model", default="distilbert-base-uncased",
        help="HuggingFace model for BERTScore (default: distilbert-base-uncased).",
    )
    args = parser.parse_args()

    archs    = ARCH_ORDER if args.architecture == ["all"] else args.architecture
    use_bert = not args.no_bert

    results_out = run(archs, use_bert, args.bert_model)

    print_table(results_out)

    out: dict = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "bert_model": args.bert_model if use_bert else None,
        "architectures": {
            arch: {
                "overall": v["overall"],
                "by_question_type": v["by_question_type"],
                "per_question": v["per_question"],
            }
            for arch, v in results_out.items()
        },
    }
    out_path = RESULTS_DIR / "reliable_metrics.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    main()
