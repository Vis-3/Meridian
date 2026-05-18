"""
Meridian -- Full benchmark runner.

Runs one or more architectures sequentially against the 325-question set,
saving per-architecture JSON results and printing a live summary.

Usage:
    python scripts/run_all_evaluations.py
    python scripts/run_all_evaluations.py --architectures naive hybrid fusion
    python scripts/run_all_evaluations.py --sample 20
    python scripts/run_all_evaluations.py --architectures naive --sample 10
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import EVAL_DIR, RESULTS_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Canonical run order
ARCH_ORDER = [
    "naive",
    "hybrid",
    "fusion",
    "corrective",
    "graph",
    "agentic",
    "full_system",
    "hierarchical",
]

SAMPLE_SEED = 42


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_questions(sample: int | None) -> list[dict]:
    path = EVAL_DIR / "questions.json"
    if not path.exists():
        raise FileNotFoundError(
            f"questions.json not found at {path}. "
            "Run data/evaluation/generate_questions.py first."
        )
    questions = json.loads(path.read_text(encoding="utf-8"))
    if sample:
        rng = random.Random(SAMPLE_SEED)
        # Stratified: sample proportionally across question types
        by_type: dict[str, list] = {}
        for q in questions:
            by_type.setdefault(q["type"], []).append(q)
        selected: list[dict] = []
        per_type = max(1, sample // len(by_type))
        for qtype, qs in by_type.items():
            chosen = rng.sample(qs, min(per_type, len(qs)))
            selected.extend(chosen)
        # Top up to exactly `sample` if rounding left us short
        pool = [q for q in questions if q not in selected]
        rng.shuffle(pool)
        selected.extend(pool[: max(0, sample - len(selected))])
        questions = selected[:sample]
        log.info("Sampled %d questions (seed=%d)", len(questions), SAMPLE_SEED)
    return questions


def _avg(results: list[dict], key: str) -> float:
    vals = [r[key] for r in results if isinstance(r.get(key), (int, float))]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def _avg_or_none(results: list[dict], key: str) -> float | None:
    vals = [r[key] for r in results if isinstance(r.get(key), (int, float))]
    return round(sum(vals) / len(vals), 3) if vals else None


def _fmt(val: float | None) -> str:
    return f"{val:.3f}" if val is not None else "  --"


def _print_summary(arch: str, results: list[dict], elapsed_s: float) -> None:
    mins  = elapsed_s / 60
    faith = _avg_or_none(results, "faithfulness")
    relev = _avg_or_none(results, "answer_relevancy")
    prec  = _avg_or_none(results, "context_precision")
    rec   = _avg_or_none(results, "context_recall")
    corr  = _avg_or_none(results, "answer_correctness")
    lat   = _avg(results, "latency_ms")
    cost  = sum(r.get("estimated_cost_usd", 0.0) for r in results)

    sep = "-" * 60
    print(f"\n{sep}")
    print(f"  {arch.upper()} -- {len(results)} questions  ({mins:.1f} min)")
    print(f"  Faithfulness:      {_fmt(faith)}")
    print(f"  Answer relevancy:  {_fmt(relev)}")
    print(f"  Context precision: {_fmt(prec)}")
    print(f"  Context recall:    {_fmt(rec)}")
    print(f"  Answer correctness:{_fmt(corr)}")
    print(f"  Avg latency:       {lat:.0f} ms")
    print(f"  Total cost:        ${cost:.4f}")
    print(sep)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_all(arch_names: list[str], questions: list[dict]) -> dict[str, list[dict]]:
    from evaluation.ragas_runner import run_architecture

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_results: dict[str, list[dict]] = {}
    total = len(arch_names)

    for idx, arch in enumerate(arch_names, 1):
        print(f"\n{'='*60}")
        print(f"  Running {arch}... ({idx}/{total})")
        print(f"{'='*60}")

        t0 = time.perf_counter()
        error_log = RESULTS_DIR / f"{arch}_error.log"

        try:
            results = run_architecture(arch, questions)
            elapsed = time.perf_counter() - t0
            all_results[arch] = results
            _print_summary(arch, results, elapsed)
        except Exception:
            elapsed = time.perf_counter() - t0
            tb = traceback.format_exc()
            log.error("%s FAILED after %.1fs -- logged to %s", arch, elapsed, error_log)
            error_log.write_text(
                f"Architecture: {arch}\nElapsed: {elapsed:.1f}s\n\n{tb}",
                encoding="utf-8",
            )
            print(f"\n  [ERROR] {arch} failed. See {error_log}")
            all_results[arch] = []

    return all_results


def _print_overall(all_results: dict[str, list[dict]], wall_s: float) -> None:
    print(f"\n{'='*60}")
    print("  BENCHMARK COMPLETE")
    print(f"  Total time: {wall_s/60:.1f} min")
    print(f"{'='*60}")
    print(f"  {'Architecture':<16} {'N':>4}  {'Faith':>6}  {'Relev':>6}  {'Corr':>6}  {'P99ms':>8}")
    print(f"  {'-'*16} {'-'*4}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*8}")
    for arch, results in all_results.items():
        if not results:
            print(f"  {arch:<16} {'FAILED':>4}")
            continue
        lats = sorted(r.get("latency_ms", 0) for r in results)
        p99 = lats[int(len(lats) * 0.99)] if lats else 0
        print(
            f"  {arch:<16} {len(results):>4}  "
            f"{_fmt(_avg_or_none(results, 'faithfulness')):>6}  "
            f"{_fmt(_avg_or_none(results, 'answer_relevancy')):>6}  "
            f"{_fmt(_avg_or_none(results, 'answer_correctness')):>6}  "
            f"{p99:>8.0f}"
        )
    print(f"{'='*60}\n")

    # Save combined summary
    summary_path = RESULTS_DIR / "benchmark_summary.json"
    summary = {
        arch: {
            "n_questions":         len(results),
            "faithfulness":        _avg_or_none(results, "faithfulness"),
            "answer_relevancy":    _avg_or_none(results, "answer_relevancy"),
            "context_precision":   _avg_or_none(results, "context_precision"),
            "context_recall":      _avg_or_none(results, "context_recall"),
            "answer_correctness":  _avg_or_none(results, "answer_correctness"),
            "avg_latency_ms":      _avg(results, "latency_ms"),
            "total_cost_usd":      round(sum(r.get("estimated_cost_usd", 0) for r in results), 4),
        }
        for arch, results in all_results.items()
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"  Summary saved to: {summary_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Meridian full benchmark runner")
    parser.add_argument(
        "--architectures", "-a",
        nargs="+",
        choices=ARCH_ORDER,
        default=None,
        metavar="ARCH",
        help="Architectures to run (default: all in canonical order).",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        metavar="N",
        help="Run N stratified-random questions per architecture (SEED=42).",
    )
    args = parser.parse_args()

    arch_names = args.architectures or ARCH_ORDER
    # Preserve canonical order even if user specified out of order
    arch_names = [a for a in ARCH_ORDER if a in arch_names]

    questions = _load_questions(args.sample)
    log.info("Loaded %d questions", len(questions))
    log.info("Architectures: %s", arch_names)

    t0 = time.perf_counter()
    all_results = run_all(arch_names, questions)
    _print_overall(all_results, time.perf_counter() - t0)


if __name__ == "__main__":
    main()
