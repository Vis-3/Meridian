from __future__ import annotations

"""
Meridian — RAGAS scoring pass over saved generation results.

Loads existing {arch}.json result files produced by run_batch_evaluation.py
and runs RAGAS metrics on the saved answers + retrieved chunks.
Designed to run as a slow overnight pass after fast batch generation is done.

Usage:
    python scripts/score_saved_results.py
    python scripts/score_saved_results.py --architecture naive
    python scripts/score_saved_results.py --sample 50
    python scripts/score_saved_results.py --metrics faithfulness context_precision

Default metrics: faithfulness, answer_relevancy, context_precision, context_recall
answer_correctness excluded by default — requires 4+ LLM calls/sample and
consistently times out against Gemini 2.5 models.

Checkpoints after every question so crashes don't lose progress.
Skips questions already scored (ragas_scored=True) unless --rescore passed.
"""

import sys
import os
os.environ["PYTHONUTF8"] = "1"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

import argparse
import json
import logging
import random
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import (
    RESULTS_DIR,
    GEMINI_API_KEY,
    GEMINI_RAGAS_MODEL,
)
from evaluation.ragas_runner import ARCHITECTURE_REGISTRY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

AVAILABLE_METRICS = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "answer_correctness",
]
DEFAULT_METRICS = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
]
RAGAS_TIMEOUT = 180   # seconds per metric per batch


# ---------------------------------------------------------------------------
# RAGAS setup
# ---------------------------------------------------------------------------

def _build_ragas_components():
    from langchain_google_genai import ChatGoogleGenerativeAI
    from ragas.llms import LangchainLLMWrapper
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    llm = LangchainLLMWrapper(ChatGoogleGenerativeAI(
        model=GEMINI_RAGAS_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0,
    ))
    embed = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    )
    return llm, embed


def _get_metric_objects(metric_names: list[str], llm, embed):
    from ragas.metrics import (
        faithfulness, answer_relevancy,
        context_precision, context_recall, answer_correctness,
    )
    registry = {
        "faithfulness":       faithfulness,
        "answer_relevancy":   answer_relevancy,
        "context_precision":  context_precision,
        "context_recall":     context_recall,
        "answer_correctness": answer_correctness,
    }
    objects = []
    for name in metric_names:
        m = registry[name]
        m.llm = llm
        if hasattr(m, "embeddings"):
            m.embeddings = embed
        objects.append((name, m))
    return objects


# ---------------------------------------------------------------------------
# Score one question against one metric
# ---------------------------------------------------------------------------

def _score_one(question_text: str, answer: str, contexts: list[str],
               ground_truth: str, metric_name: str, metric_obj,
               llm, embed) -> float | None:
    from ragas import evaluate, RunConfig
    from datasets import Dataset

    ds = Dataset.from_list([{
        "question":    question_text,
        "answer":      answer,
        "contexts":    contexts,
        "ground_truth": ground_truth or "",
    }])

    try:
        result = evaluate(
            ds,
            metrics=[metric_obj],
            llm=llm,
            embeddings=embed,
            run_config=RunConfig(timeout=RAGAS_TIMEOUT, max_retries=1, max_wait=20),
        )
        scores = result.scores   # list[dict]
        if scores and metric_name in scores[0]:
            val = scores[0][metric_name]
            if val is not None and str(val) != "nan":
                return float(val)
    except Exception as e:
        log.warning("    %s failed: %s", metric_name, str(e)[:80])
    return None


# ---------------------------------------------------------------------------
# Stratified sample
# ---------------------------------------------------------------------------

def _stratified_sample(results: list[dict], n: int) -> list[int]:
    """Return indices of N results sampled proportionally by question_type."""
    from collections import defaultdict
    by_type: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(results):
        by_type[r.get("question_type", "unknown")].append(i)

    total = len(results)
    sampled: list[int] = []
    for qtype, idxs in by_type.items():
        k = max(1, round(n * len(idxs) / total))
        sampled.extend(random.sample(idxs, min(k, len(idxs))))

    # Trim or top-up to exactly N
    random.shuffle(sampled)
    if len(sampled) > n:
        sampled = sampled[:n]
    elif len(sampled) < n:
        remaining = [i for i in range(total) if i not in set(sampled)]
        random.shuffle(remaining)
        sampled.extend(remaining[: n - len(sampled)])

    return sorted(sampled)


# ---------------------------------------------------------------------------
# Score one architecture
# ---------------------------------------------------------------------------

def score_architecture(
    arch_name: str,
    metric_names: list[str],
    sample: int | None,
    rescore: bool,
) -> None:
    result_path = RESULTS_DIR / f"{arch_name}.json"
    if not result_path.exists():
        log.warning("No results file for %s — skipping", arch_name)
        return

    with open(result_path, encoding="utf-8") as f:
        results: list[dict] = json.load(f)

    log.info("\n%s\n  Scoring: %s  (%d results)\n%s",
             "="*60, arch_name, len(results), "="*60)

    # Determine which indices to score
    scoreable = [
        i for i, r in enumerate(results)
        if r.get("citations")
        and r.get("answer")
        and not str(r.get("answer", "")).startswith("[")
        and (rescore or not r.get("ragas_scored"))
    ]
    if not scoreable:
        log.info("  Nothing to score (all already scored or no valid answers).")
        return

    if sample and sample < len(scoreable):
        log.info("  Sampling %d of %d scoreable questions ...", sample, len(scoreable))
        scoreable_results = [results[i] for i in scoreable]
        sampled_local = _stratified_sample(scoreable_results, sample)
        scoreable = [scoreable[j] for j in sampled_local]

    log.info("  Scoring %d questions on metrics: %s", len(scoreable), metric_names)

    # Build RAGAS components once
    llm, embed = _build_ragas_components()
    metric_objects = _get_metric_objects(metric_names, llm, embed)

    total = len(scoreable)
    t_wall = time.perf_counter()

    for seq, idx in enumerate(scoreable, 1):
        r = results[idx]
        qid = r.get("question_id", idx)
        log.info("  [%d/%d] Q%s ...", seq, total, qid)

        contexts = [c.get("text", "") for c in r.get("citations", []) if c.get("text")]
        if not contexts:
            log.warning("    No context text — skipping Q%s", qid)
            continue

        any_scored = False
        for metric_name, metric_obj in metric_objects:
            t0 = time.perf_counter()
            val = _score_one(
                question_text=r["question"],
                answer=r["answer"],
                contexts=contexts,
                ground_truth=r.get("ground_truth") or "",
                metric_name=metric_name,
                metric_obj=metric_obj,
                llm=llm,
                embed=embed,
            )
            elapsed = time.perf_counter() - t0
            results[idx][metric_name] = val
            status = f"{val:.3f}" if val is not None else "FAILED"
            log.info("    %s: %s  (%.0fs)", metric_name, status, elapsed)
            if val is not None:
                any_scored = True

        if any_scored:
            results[idx]["ragas_scored"] = True

        # Checkpoint after every question
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    wall_elapsed = time.perf_counter() - t_wall
    scored_count = sum(1 for i in scoreable if results[i].get("ragas_scored"))
    log.info("  Done: %d/%d scored in %.1f min", scored_count, total, wall_elapsed / 60)

    # Print per-metric averages
    for metric_name in metric_names:
        vals = [results[i][metric_name] for i in scoreable
                if isinstance(results[i].get(metric_name), float)]
        avg = round(sum(vals) / len(vals), 3) if vals else None
        log.info("  avg %-22s %s  (n=%d)", metric_name,
                 f"{avg:.3f}" if avg is not None else "  --", len(vals))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    if not GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY not set — add to .env")

    parser = argparse.ArgumentParser(
        description="Score saved Meridian results with RAGAS (overnight pass)"
    )
    parser.add_argument(
        "--architecture", "-a",
        nargs="+",
        default=["all"],
        choices=list(ARCHITECTURE_REGISTRY) + ["all"],
        metavar="ARCH",
        help="One or more architectures to score, or 'all' (default).",
    )
    parser.add_argument(
        "--sample", type=int, default=None, metavar="N",
        help="Score only N stratified questions per architecture (default: all).",
    )
    parser.add_argument(
        "--metrics", nargs="+",
        default=DEFAULT_METRICS,
        choices=AVAILABLE_METRICS,
        metavar="METRIC",
        help=f"Metrics to compute. Default: {' '.join(DEFAULT_METRICS)}",
    )
    parser.add_argument(
        "--rescore", action="store_true",
        help="Re-score questions already marked ragas_scored=True.",
    )
    args = parser.parse_args()

    if args.architecture == ["all"]:
        arch_names = list(ARCHITECTURE_REGISTRY)
    else:
        arch_names = args.architecture

    log.info("Metrics: %s", args.metrics)
    log.info("Sample:  %s", args.sample or "all")
    log.info("Archs:   %s", arch_names)

    for arch_name in arch_names:
        score_architecture(
            arch_name=arch_name,
            metric_names=args.metrics,
            sample=args.sample,
            rescore=args.rescore,
        )

    log.info("Scoring complete.")


if __name__ == "__main__":
    main()
