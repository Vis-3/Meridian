from __future__ import annotations

"""
Meridian — Gemini Batch Evaluation Runner
==========================================
Runs the full 325-question benchmark against all 8 architectures using
Gemini Flash 2.0 for generation. All LLM calls are fired concurrently
(controlled by --concurrency), so total runtime is ~minutes not hours.

Workflow per architecture:
  1. Retrieve chunks locally (Qdrant + BM25 + Neo4j as applicable)
  2. Format prompts from retrieved chunks
  3. Fire all prompts to Gemini concurrently  ← the speed gain
  4. Assemble results, compute keyword hit rate
  5. Save to data/evaluation/results/{arch}.json

Usage:
    python scripts/run_batch_evaluation.py
    python scripts/run_batch_evaluation.py --architecture naive
    python scripts/run_batch_evaluation.py --smoke 10
    python scripts/run_batch_evaluation.py --concurrency 30

Requirements:
    pip install google-generativeai
    GEMINI_API_KEY in .env (or environment)
    DEPLOYMENT=gemini in .env (or environment)

Rate limits (Gemini Flash 2.0 pay-as-you-go):
    2000 RPM — default --concurrency 20 stays well under this.

Estimated runtime:
    All 8 architectures × 325 questions = 2600 LLM calls
    At 20 concurrent, ~3s avg latency → ~7 minutes total.
"""

#from __future__ import annotations
import sys
import os
os.environ["PYTHONUTF8"] = "1"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path
import sys

import os
os.environ["PYTHONUTF8"] = "1"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import (
    EVAL_DIR,
    RESULTS_DIR,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_GENERATION_MODEL,
    GEMINI_RAGAS_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
)
from evaluation.ragas_runner import ARCHITECTURE_REGISTRY
from llm.prompts import GENERATION_SYSTEM as _SYSTEM_PROMPT, GENERATION_USER_TEMPLATE as _USER_TEMPLATE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Gemini Flash 2.0 pricing
_COST_IN_PER_1M  = 0.075
_COST_OUT_PER_1M = 0.300

RAGAS_METRICS = [
    "faithfulness", "answer_relevancy",
    "context_precision", "context_recall", "answer_correctness",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_questions(
    smoke: int | None,
    question_types: list[str] | None = None,
    per_type: int | None = None,
) -> list[dict]:
    path = EVAL_DIR / "questions.json"
    if not path.exists():
        raise FileNotFoundError(f"questions.json not found at {path}")
    with open(path, encoding="utf-8") as f:
        qs = json.load(f)
    if question_types:
        qs = [q for q in qs if q.get("type") in question_types]
    if per_type:
        from collections import defaultdict
        buckets: dict[str, list] = defaultdict(list)
        for q in qs:
            buckets[q.get("type", "")].append(q)
        qs = [q for bucket in buckets.values() for q in bucket[:per_type]]
    return qs[:smoke] if smoke else qs


def _load_arch(arch_name: str):
    module_path, class_name = ARCHITECTURE_REGISTRY[arch_name].rsplit(":", 1)
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)()


def _format_context(chunks: list[dict], max_chunks: int = 5) -> str:
    lines = []
    for i, chunk in enumerate(chunks[:max_chunks], 1):
        text = chunk.get("text", "").strip()[:800]
        lines.append(
            f"[{i}] {chunk.get('company','')} FY{chunk.get('fiscal_year','')} "
            f"{chunk.get('section','')}:\n{text}"
        )
    return "\n\n".join(lines)


def _safe_avg(results: list[dict], key: str) -> float | None:
    vals = [r[key] for r in results if isinstance(r.get(key), (int, float))]
    return round(sum(vals) / len(vals), 3) if vals else None


def _fmt(val: float | None) -> str:
    return f"{val:.3f}" if val is not None else "  --"


def _keyword_hit_rate(question: dict, answer: str, chunks: list[dict]) -> float | None:
    if question["type"] != "risk_qualitative" or not question.get("keywords"):
        return None
    combined = answer.lower() + " " + " ".join(
        c.get("text", "").lower() for c in chunks
    )
    hits = sum(1 for kw in question["keywords"] if kw.lower() in combined)
    return round(hits / len(question["keywords"]), 3)


# ---------------------------------------------------------------------------
# Phase 1: retrieve for all questions (local, fast)
# ---------------------------------------------------------------------------

def retrieve_all(
    arch,
    arch_name: str,
    questions: list[dict],
) -> list[dict]:
    """
    Run retrieve() for every question, passing company/year filters so
    architectures that support pre-filtering (hybrid, fusion, corrective,
    graph) return targeted results rather than corpus-wide candidates.

    Also applies:
      - facts_lookup: injects verified facts.py chunk for numerical/factual Qs
      - compression:  strips non-numerical sentences for numerical Qs

    Returns list of records: {key, question, chunks, prompt, system_prompt}.
    """
    from retrieval.facts_lookup import lookup_numerical, lookup_comparative
    from retrieval.compression import compress_chunks
    from llm.prompts import GENERATION_SYSTEM_NUMERICAL

    _NUMERICAL_TYPES = {"numerical_reasoning", "simple_factual"}
    _COMPARATIVE_TYPES = {"comparative"}

    records = []
    total_q = len(questions)
    log.info("  Retrieving %d questions for %s ...", total_q, arch_name)
    t0 = time.perf_counter()
    n_failed = 0

    for i, q in enumerate(questions):
        # Extract filter hints present on every question
        companies    = q.get("companies") or None      # list[str] | None
        fiscal_years = q.get("years") or None          # list[int] | None
        qtype        = q.get("type", "")

        q_t0 = time.perf_counter()
        try:
            chunks = arch.retrieve(
                q["question"],
                companies=companies,
                fiscal_years=fiscal_years,
            )
        except TypeError:
            # Architecture's retrieve() doesn't accept these kwargs — call bare
            try:
                chunks = arch.retrieve(q["question"])
            except Exception as exc:
                log.warning("  retrieve() failed %s/%s: %s", arch_name, q["id"], exc)
                chunks = []
                n_failed += 1
        except Exception as exc:
            log.warning("  retrieve() failed %s/%s: %s", arch_name, q["id"], exc)
            chunks = []
            n_failed += 1
        retrieval_ms = round((time.perf_counter() - q_t0) * 1000, 1)

        # ── Facts lookup ─────────────────────────────────────────────────
        facts_chunk = None
        if qtype in _NUMERICAL_TYPES:
            facts_chunk = lookup_numerical(q["question"], companies or [], fiscal_years or [])
        elif qtype in _COMPARATIVE_TYPES:
            facts_chunk = lookup_comparative(q["question"], fiscal_years or [])

        if facts_chunk:
            chunks = [facts_chunk] + [c for c in chunks if c.get("chunk_id") != facts_chunk["chunk_id"]]

        # ── Context compression ──────────────────────────────────────────
        if qtype in _NUMERICAL_TYPES:
            chunks = compress_chunks(chunks, qtype, q["question"])

        # ── Prompt selection ─────────────────────────────────────────────
        sys_prompt = GENERATION_SYSTEM_NUMERICAL if (facts_chunk and qtype in _NUMERICAL_TYPES) else None

        context = _format_context(chunks)
        prompt  = _USER_TEMPLATE.format(context=context, question=q["question"])

        records.append({
            "key":           f"{arch_name}::{q['id']}",
            "question":      q,
            "chunks":        chunks,
            "prompt":        prompt,
            "system_prompt": sys_prompt,
            "retrieval_ms":  retrieval_ms,
        })

        done = i + 1
        if done % 25 == 0 or done == total_q:
            elapsed = time.perf_counter() - t0
            rate    = done / elapsed
            eta_s   = (total_q - done) / rate if rate else 0
            log.info(
                "  [%d/%d] %.0f%% — %.0fms/q — eta %.1f min",
                done, total_q,
                100 * done / total_q,
                elapsed / done * 1000,
                eta_s / 60,
            )

    elapsed = time.perf_counter() - t0
    log.info(
        "  Retrieval done: %.1fs  (%.0fms/q)%s",
        elapsed,
        elapsed / len(questions) * 1000,
        f"  [{n_failed} failed]" if n_failed else "",
    )
    return records


# ---------------------------------------------------------------------------
# Phase 2: batch generate via Gemini (async, fast)
# ---------------------------------------------------------------------------

async def batch_generate(
    prompt_records: dict[str, tuple[str, str | None]],
    max_concurrent: int,
) -> dict[str, tuple[str, dict, float]]:
    """
    Fire all prompts concurrently. Returns {key: (answer, usage, generation_ms)}.

    prompt_records: {key: (prompt_text, system_prompt_or_None)}
      - When system_prompt is None, uses the default _SYSTEM_PROMPT.
      - When system_prompt is set (e.g. GENERATION_SYSTEM_NUMERICAL), uses that instead.
    """
    from google import genai
    from google.genai import types

    client    = genai.Client(api_key=GEMINI_API_KEY)
    semaphore = asyncio.Semaphore(max_concurrent)
    results    = {}
    done_count = 0
    total      = len(prompt_records)
    t0         = time.perf_counter()

    def _make_config(sys_prompt: str | None) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=sys_prompt or _SYSTEM_PROMPT,
            temperature=LLM_TEMPERATURE,
            max_output_tokens=LLM_MAX_TOKENS,
        )

    async def _one(key: str, prompt: str, sys_prompt: str | None):
        nonlocal done_count
        config = _make_config(sys_prompt)
        delay  = 2.0
        for attempt in range(5):
            async with semaphore:
                try:
                    _t_req = time.perf_counter()
                    resp   = await client.aio.models.generate_content(
                        model=GEMINI_GENERATION_MODEL, contents=prompt, config=config,
                    )
                    gen_ms = round((time.perf_counter() - _t_req) * 1000, 1)
                    usage  = resp.usage_metadata
                    answer = resp.text.strip()
                    results[key] = (answer, {
                        "input_tokens":  getattr(usage, "prompt_token_count", 0) or 0,
                        "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
                    }, gen_ms)
                    done_count += 1
                    if done_count % 100 == 0 or done_count == total:
                        elapsed = time.perf_counter() - t0
                        rate    = done_count / elapsed
                        eta     = (total - done_count) / rate if rate else 0
                        log.info("  Gemini: %d/%d  (%.0f/min  eta=%.1fm)",
                                 done_count, total, rate * 60, eta / 60)
                    return
                except Exception as e:
                    err = str(e)
                    is_rate = "429" in err or "quota" in err.lower() or "exhausted" in err.lower()
                    if is_rate or attempt < 4:
                        wait = delay * (2 ** attempt)
                        if is_rate:
                            log.warning("  Rate limit — waiting %.0fs", wait)
                        await asyncio.sleep(wait)
                    else:
                        log.error("  Failed %s: %s", key, e)
                        results[key] = (f"[LLM ERROR] {e}",
                                        {"input_tokens": 0, "output_tokens": 0}, 0.0)
                        done_count += 1
                        return

    await asyncio.gather(*[_one(k, p, s) for k, (p, s) in prompt_records.items()])
    return results


# ---------------------------------------------------------------------------
# Phase 3: assemble results
# ---------------------------------------------------------------------------

def assemble_results(
    records: list[dict],
    answers: dict[str, tuple[str, dict, float]],
    arch_name: str,
) -> list[dict]:
    out = []
    for rec in records:
        q      = rec["question"]
        key    = rec["key"]
        chunks = rec["chunks"]
        answer, usage, gen_ms = answers.get(
            key, ("[MISSING]", {"input_tokens": 0, "output_tokens": 0}, 0.0)
        )

        in_tok       = usage["input_tokens"]
        out_tok      = usage["output_tokens"]
        retrieval_ms = rec.get("retrieval_ms", 0.0)
        cost         = (in_tok / 1_000_000 * _COST_IN_PER_1M +
                        out_tok / 1_000_000 * _COST_OUT_PER_1M)

        out.append({
            # identity
            "question_id":        q["id"],
            "question_type":      q["type"],
            "difficulty":         q["difficulty"],
            "covid_related":      q["covid_related"],
            "companies":          q["companies"],
            "years":              q["years"],
            "architecture_name":  arch_name,
            # Q&A
            "question":           q["question"],
            "ground_truth":       q.get("ground_truth"),
            "answer":             answer,
            # retrieval — full chunk text preserved for RAGAS scoring pass
            "citations":          chunks,
            "n_citations":        len(chunks),
            # RAGAS — populated by score_saved_results.py
            "ragas_scored":       False,
            **{m: None for m in RAGAS_METRICS},
            # latency breakdown (generation_ms is per-request wall clock in concurrent mode)
            "latency_breakdown": {
                "retrieval_ms":   retrieval_ms,
                "generation_ms":  gen_ms,
                "total_ms":       round(retrieval_ms + gen_ms, 1),
            },
            # faithfulness_proxy: agentic self-check score if available, else None
            "faithfulness_proxy": None,
            # cost / perf
            "tokens_used":        in_tok + out_tok,
            "estimated_cost_usd": round(cost, 6),
            "keyword_hit_rate":   _keyword_hit_rate(q, answer, chunks),
            "generation_model":   GEMINI_GENERATION_MODEL,
        })
    return out


# ---------------------------------------------------------------------------
# Optional: RAGAS scoring pass via Gemini + langchain_google_genai
# ---------------------------------------------------------------------------

def score_ragas(results: list[dict]) -> list[dict]:
    """
    Score faithfulness, relevancy, correctness via RAGAS using Gemini.
    Requires: pip install langchain-google-genai ragas datasets
    """
    try:
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness, answer_relevancy,
            context_precision, context_recall, answer_correctness,
        )
        from datasets import Dataset
        from langchain_google_genai import ChatGoogleGenerativeAI
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
    except ImportError as e:
        log.warning("RAGAS deps not installed (%s) — skipping RAGAS scoring", e)
        return results

    _llm = LangchainLLMWrapper(ChatGoogleGenerativeAI(
        model=GEMINI_RAGAS_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0,
    ))
    # Local embeddings — avoids Google Embeddings API version incompatibility
    # all-MiniLM-L6-v2 is already used by the retrieval pipeline
    from langchain_community.embeddings import HuggingFaceEmbeddings
    _embed = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    )
    for m in [faithfulness, answer_relevancy, context_precision,
              context_recall, answer_correctness]:
        m.llm = _llm
        if hasattr(m, "embeddings"):
            m.embeddings = _embed

    # Build dataset — skip results with empty context
    scored_idx = [
        i for i, r in enumerate(results)
        if r["citations"] and r["answer"] and not r["answer"].startswith("[")
    ]
    if not scored_idx:
        return results

    ds = Dataset.from_list([{
        "question":    results[i]["question"],
        "answer":      results[i]["answer"],
        "contexts":    [c.get("text", "") for c in results[i]["citations"]],
        "ground_truth": results[i].get("ground_truth") or "",
    } for i in scored_idx])

    from ragas import RunConfig
    run_cfg = RunConfig(timeout=180, max_retries=2, max_wait=30)
    metric_objects = [
        ("faithfulness",       faithfulness),
        ("answer_relevancy",   answer_relevancy),
        ("context_precision",  context_precision),
        ("context_recall",     context_recall),
        ("answer_correctness", answer_correctness),
    ]

    log.info("Starting RAGAS evaluation on %d samples ...", len(scored_idx))
    per_metric_scores: dict[str, list] = {}

    for metric_name, metric_obj in metric_objects:
        log.info("  Running %s ...", metric_name)
        import time as _time; _t0 = _time.perf_counter()
        try:
            result = evaluate(
                ds,
                metrics=[metric_obj],
                llm=_llm,
                embeddings=_embed,
                run_config=run_cfg,
            )
            elapsed = _time.perf_counter() - _t0
            col = result.scores  # list[dict]
            per_metric_scores[metric_name] = [row.get(metric_name) for row in col]
            log.info("  %s done (%.1fs)", metric_name, elapsed)
        except Exception as e:
            elapsed = _time.perf_counter() - _t0
            log.warning("  %s FAILED (%.1fs): %s", metric_name, elapsed, e)
            per_metric_scores[metric_name] = [None] * len(scored_idx)

    log.info("RAGAS evaluation complete.")

    for j, i in enumerate(scored_idx):
        any_scored = False
        for metric_name in RAGAS_METRICS:
            vals = per_metric_scores.get(metric_name, [])
            if j < len(vals) and vals[j] is not None:
                results[i][metric_name] = float(vals[j])
                any_scored = True
        if any_scored:
            results[i]["ragas_scored"] = True

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_architecture_async(
    arch_name: str,
    questions: list[dict],
    max_concurrent: int,
    run_ragas: bool,
    args_append: bool = False,
) -> list[dict]:
    log.info("\n%s\n  Architecture: %s\n%s", "="*56, arch_name, "="*56)
    arch = _load_arch(arch_name)

    # Phase 1: retrieve (local)
    records = retrieve_all(arch, arch_name, questions)

    # Phase 2: batch generate (Gemini)
    # Each record carries its own system_prompt (numerical questions get the few-shot prompt)
    prompt_records = {r["key"]: (r["prompt"], r.get("system_prompt")) for r in records}
    n_numerical = sum(1 for r in records if r.get("system_prompt") is not None)
    log.info("  Submitting %d prompts to Gemini (%d with numerical prompt) ...",
             len(prompt_records), n_numerical)
    answers = await batch_generate(prompt_records, max_concurrent)

    # Phase 3: assemble
    results = assemble_results(records, answers, arch_name)

    # Phase 4: optional RAGAS
    if run_ragas:
        log.info("  Scoring RAGAS ...")
        results = score_ragas(results)

    # Save — merge into existing file if --append, otherwise overwrite
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{arch_name}.json"
    if args_append and out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        existing_ids = {r["question_id"] for r in existing}
        new_results = [r for r in results if r["question_id"] not in existing_ids]
        merged = existing + new_results
        log.info("  Appending %d new questions to %d existing (total %d)",
                 len(new_results), len(existing), len(merged))
        results = merged
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log.info("  Saved -> %s", out_path)

    total_cost = sum(r["estimated_cost_usd"] for r in results)
    log.info("  Cost: $%.4f  (%d questions)", total_cost, len(results))
    return results


async def main_async(args) -> None:
    if not GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY is not set. Add it to .env and set DEPLOYMENT=gemini")

    qtypes = args.question_types if args.question_types else None
    questions = _load_questions(args.smoke, question_types=qtypes, per_type=args.per_type)
    if qtypes:
        log.info("Loaded %d questions (types: %s)", len(questions), qtypes)
    else:
        log.info("Loaded %d questions", len(questions))

    arch_names = (
        list(ARCHITECTURE_REGISTRY) if args.architecture == ["all"]
        else args.architecture
    )

    wall_t0    = time.perf_counter()
    all_costs   = {}
    all_results = {}

    for arch_name in arch_names:
        results = await run_architecture_async(
            arch_name, questions,
            max_concurrent=args.concurrency,
            run_ragas=args.ragas,
            args_append=args.append,
        )
        all_results[arch_name] = results
        all_costs[arch_name]   = sum(r["estimated_cost_usd"] for r in results)

    wall_elapsed = time.perf_counter() - wall_t0

    # Save combined summary
    summary = {
        arch: {
            "n_questions":        len(all_results[arch]),
            "keyword_hit_rate":   _safe_avg(all_results[arch], "keyword_hit_rate"),
            "faithfulness":       _safe_avg(all_results[arch], "faithfulness"),
            "answer_relevancy":   _safe_avg(all_results[arch], "answer_relevancy"),
            "answer_correctness": _safe_avg(all_results[arch], "answer_correctness"),
            "total_cost_usd":     all_costs[arch],
            "model":              GEMINI_GENERATION_MODEL,
        }
        for arch in arch_names
    }
    summary_path = RESULTS_DIR / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Print table
    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  BATCH EVALUATION COMPLETE — {wall_elapsed/60:.1f} min   gen={GEMINI_GENERATION_MODEL}  ragas={GEMINI_RAGAS_MODEL}")
    print(sep)
    print(f"  {'Architecture':<20} {'N':>4}  {'KwHit':>6}  {'Faith':>6}  {'Corr':>6}  {'Cost':>8}")
    print(f"  {'-'*20} {'-'*4}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*8}")
    total_cost = 0.0
    for arch in arch_names:
        res = all_results[arch]
        kw   = _safe_avg(res, "keyword_hit_rate")
        fa   = _safe_avg(res, "faithfulness")
        co   = _safe_avg(res, "answer_correctness")
        cost = all_costs[arch]
        total_cost += cost
        print(
            f"  {arch:<20} {len(res):>4}  "
            f"{_fmt(kw):>6}  {_fmt(fa):>6}  {_fmt(co):>6}  "
            f"${cost:>7.4f}"
        )
    print(f"  {'-'*20} {'-'*4}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*8}")
    print(f"  {'TOTAL':<20} {'':>4}  {'':>6}  {'':>6}  {'':>6}  ${total_cost:>7.4f}")
    print(sep)
    print(f"  Summary -> {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Meridian batch evaluation via Gemini Flash 2.0"
    )
    parser.add_argument(
        "--architecture", "-a",
        nargs="+",
        default=["all"],
        choices=list(ARCHITECTURE_REGISTRY) + ["all"],
        metavar="ARCH",
        help="One or more architectures to run, or 'all' (default: all).",
    )
    parser.add_argument(
        "--question-types", "-t", nargs="+", metavar="TYPE",
        choices=["simple_factual","numerical_reasoning","temporal",
                 "comparative","multi_hop","risk_qualitative"],
        help="Only evaluate questions of these types (default: all types).",
    )
    parser.add_argument(
        "--append", action="store_true",
        help="Merge new results into existing result files instead of overwriting.",
    )
    parser.add_argument(
        "--smoke", "--sample", type=int, default=None, metavar="N",
        help="Evaluate on first N questions only (--sample is an alias).",
    )
    parser.add_argument(
        "--per-type", type=int, default=None, metavar="N",
        help="Limit to first N questions per question type (e.g. --per-type 30).",
    )
    parser.add_argument(
        "--concurrency", type=int, default=20, metavar="N",
        help="Max concurrent Gemini requests (default 20; raise to 50 on paid tier).",
    )
    parser.add_argument(
        "--ragas", action="store_true",
        help="Run RAGAS scoring after generation (slow — use score_saved_results.py instead).",
    )
    parser.add_argument(
        "--no-ragas", action="store_true", dest="no_ragas",
        help="Explicitly skip RAGAS (default behaviour; provided for clarity).",
    )
    args = parser.parse_args()
    if args.no_ragas:
        args.ragas = False
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
