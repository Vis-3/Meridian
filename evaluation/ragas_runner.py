from __future__ import annotations

import sys
import os
os.environ["PYTHONUTF8"] = "1"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

"""
Meridian — RAGAS Evaluation Runner
====================================
Runs a RAGAS evaluation pass for one or all architectures against the
325-question benchmark set in data/evaluation/questions.json.

Usage:
    python evaluation/ragas_runner.py --architecture naive
    python evaluation/ragas_runner.py --architecture all
    python evaluation/ragas_runner.py --architecture naive --smoke 10

Output:
    data/evaluation/results/{architecture_name}.json

Each result file is a list of per-question result dicts matching the
schema documented in INSTRUCTIONS.md, plus RAGAS metric scores.
"""

import argparse
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
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from config import (
    EVAL_DIR,
    RESULTS_DIR,
    FAITHFULNESS_THRESHOLD,
    RETRIEVAL_RELEVANCE_THRESHOLD,
    COST_PER_1K_INPUT_TOKENS,
    COST_PER_1K_OUTPUT_TOKENS,
)

logger = logging.getLogger(__name__)

# Architecture registry — populated when architectures/ is built (Phase 7).
# Each value is a callable that returns a RAGArchitecture instance.
# Imported lazily so this module is importable without GPU/Qdrant running.
ARCHITECTURE_REGISTRY: dict[str, str] = {
    "naive":         "architectures.naive:NaiveRAG",
    "hybrid":        "architectures.hybrid_rag:HybridRAG",
    "fusion":        "architectures.fusion_rag:FusionRAG",
    "hierarchical":  "architectures.hierarchical_rag:HierarchicalRAG",
    "corrective":    "architectures.corrective_rag:CorrectiveRAG",
    "graph":         "architectures.graph_rag:GraphRAG",
    "agentic":       "architectures.agentic_rag:AgenticRAG",
    "full_system":   "architectures.full_system:FullSystem",
}

# RAGAS metrics we collect per question
RAGAS_METRICS = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "answer_correctness",
]


# ---------------------------------------------------------------------------
# RAGAS dataset builder
# ---------------------------------------------------------------------------

def _build_ragas_sample(question: dict, arch_response: dict) -> dict:
    """
    Assemble one RAGAS Sample from a question dict and an architecture response.

    architecture response schema (from base.py):
      answer, citations, faithfulness, relevancy,
      latency_ms, tokens_used, architecture_name
    """
    retrieved_contexts = [
        c.get("text", c.get("content", ""))
        for c in arch_response.get("citations", [])
    ]
    return {
        "question":           question["question"],
        "answer":             arch_response["answer"],
        "contexts":           retrieved_contexts,
        "ground_truth":       question.get("ground_truth") or "",
        # pass-through metadata for post-hoc breakdown
        "_question_id":       question["id"],
        "_question_type":     question["type"],
        "_difficulty":        question["difficulty"],
        "_covid_related":     question["covid_related"],
        "_companies":         question["companies"],
        "_years":             question["years"],
    }


# ---------------------------------------------------------------------------
# Score one question
# ---------------------------------------------------------------------------

def _score_question(
    question: dict,
    architecture,
) -> dict:
    """
    Run one question through the architecture, then score with RAGAS.
    Returns a fully-populated result dict.
    """
    t0 = time.perf_counter()

    try:
        response = architecture.run(question["id"], question["question"])
    except Exception as exc:
        logger.error("Architecture raised on question %s: %s", question["id"], exc)
        response = {
            "answer":            f"[ERROR] {exc}",
            "citations":         [],
            "faithfulness":      0.0,
            "relevancy":         0.0,
            "latency_ms":        0.0,
            "tokens_used":       0,
            "architecture_name": getattr(architecture, "name", "unknown"),
        }

    wall_ms = (time.perf_counter() - t0) * 1_000

    # RAGAS scoring — oracle (Groq) or gemini deployment only
    from config import DEPLOYMENT
    ragas_scored = False
    ragas_scores: dict[str, float | None] = {k: None for k in RAGAS_METRICS}

    if DEPLOYMENT in ("oracle", "gemini"):
        try:
            from ragas import evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
                answer_correctness,
            )
            from datasets import Dataset
            from ragas.llms import LangchainLLMWrapper
            from ragas.embeddings import LangchainEmbeddingsWrapper

            if DEPLOYMENT == "gemini":
                from langchain_google_genai import ChatGoogleGenerativeAI
                from config import GEMINI_API_KEY, GEMINI_RAGAS_MODEL
                _llm = LangchainLLMWrapper(ChatGoogleGenerativeAI(
                    model=GEMINI_RAGAS_MODEL,
                    google_api_key=GEMINI_API_KEY,
                    temperature=0,
                ))
                # Local embeddings — avoids Google Embeddings API v1beta incompatibility
                from langchain_community.embeddings import HuggingFaceEmbeddings
                _embed = LangchainEmbeddingsWrapper(
                    HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
                )
            else:  # oracle — Groq + local embeddings
                from langchain_openai import ChatOpenAI, OpenAIEmbeddings
                from config import GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL
                _llm = LangchainLLMWrapper(ChatOpenAI(
                    model=GROQ_MODEL,
                    api_key=GROQ_API_KEY,
                    base_url=GROQ_BASE_URL,
                    temperature=0,
                ))
                _embed = LangchainEmbeddingsWrapper(
                    OpenAIEmbeddings(model="text-embedding-3-small")
                )

            sample = _build_ragas_sample(question, response)
            ds = Dataset.from_list([{
                "question":    sample["question"],
                "answer":      sample["answer"],
                "contexts":    sample["contexts"],
                "ground_truth":sample["ground_truth"],
            }])
            from ragas import RunConfig
            result = evaluate(
                ds,
                metrics=[
                    faithfulness,
                    answer_relevancy,
                    context_precision,
                    context_recall,
                    answer_correctness,
                ],
                llm=_llm,
                embeddings=_embed,
                run_config=RunConfig(timeout=180, max_retries=2, max_wait=30),
            )
            # result.scores is list[dict] — one dict per sample
            row = result.scores[0] if result.scores else {}
            ragas_scores = {k: float(row[k]) for k in RAGAS_METRICS if k in row}
            ragas_scored = True
        except Exception as exc:
            logger.warning("RAGAS scoring failed for %s: %s", question["id"], exc)
            ragas_scores = {k: None for k in RAGAS_METRICS}
    else:
        logger.debug("RAGAS skipped for %s (local deployment)", question["id"])

    # Keyword hit rate for risk_qualitative questions
    keyword_hit_rate: float | None = None
    if question["type"] == "risk_qualitative" and question.get("keywords"):
        answer_lower = response["answer"].lower()
        context_text = " ".join(
            c.get("text", c.get("content", "")).lower()
            for c in response.get("citations", [])
        )
        combined = answer_lower + " " + context_text
        hits = sum(1 for kw in question["keywords"] if kw.lower() in combined)
        keyword_hit_rate = round(hits / len(question["keywords"]), 3)

    tokens = response.get("tokens_used", 0)
    cost   = (tokens / 1_000) * (COST_PER_1K_INPUT_TOKENS + COST_PER_1K_OUTPUT_TOKENS)

    return {
        # identity
        "question_id":        question["id"],
        "question_type":      question["type"],
        "difficulty":         question["difficulty"],
        "covid_related":      question["covid_related"],
        "companies":          question["companies"],
        "years":              question["years"],
        "architecture_name":  response.get("architecture_name", architecture.name),
        # the question and answer
        "question":           question["question"],
        "ground_truth":       question.get("ground_truth"),
        "answer":             response["answer"],
        # retrieval
        "citations":          response.get("citations", []),
        "n_citations":        len(response.get("citations", [])),
        # RAGAS metrics (None = not scored; 0.0 = scored zero)
        "ragas_scored":       ragas_scored,
        **ragas_scores,
        # latency
        "latency_ms":         round(wall_ms, 1),
        "tokens_used":        tokens,
        "estimated_cost_usd": round(cost, 6),
        # extras
        "keyword_hit_rate":   keyword_hit_rate,
    }


# ---------------------------------------------------------------------------
# Run one architecture
# ---------------------------------------------------------------------------

def run_architecture(
    arch_name: str,
    questions: list[dict],
    *,
    smoke: int | None = None,
) -> list[dict]:
    """
    Evaluate one architecture on the full question set (or a smoke subset).
    Writes incremental results to disk every 25 questions so a crash
    doesn't lose everything.

    Returns list of per-question result dicts.
    """
    # Lazy import so the module is usable without all GPU deps loaded
    module_path, class_name = ARCHITECTURE_REGISTRY[arch_name].rsplit(":", 1)
    import importlib
    mod   = importlib.import_module(module_path)
    arch  = getattr(mod, class_name)()

    eval_set = questions[:smoke] if smoke else questions
    results:  list[dict] = []

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{arch_name}.json"
    checkpoint_every = 25

    logger.info("Starting %s on %d questions", arch_name, len(eval_set))

    for i, question in enumerate(eval_set, start=1):
        result = _score_question(question, arch)
        results.append(result)

        if i % checkpoint_every == 0:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info("  [%d/%d] checkpoint saved", i, len(eval_set))

    # Final write
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info("Done: %s  ->  %s", arch_name, out_path)
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _load_questions(smoke: int | None) -> list[dict]:
    path = EVAL_DIR / "questions.json"
    if not path.exists():
        raise FileNotFoundError(
            f"questions.json not found at {path}. "
            "Run data/evaluation/generate_questions.py first."
        )
    with open(path, encoding="utf-8") as f:
        questions = json.load(f)
    if smoke:
        # Stratified sample: take first `smoke` questions preserving type order
        questions = questions[:smoke]
    return questions


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Meridian RAGAS evaluation runner")
    parser.add_argument(
        "--architecture", "-a",
        required=True,
        choices=list(ARCHITECTURE_REGISTRY) + ["all"],
        help="Architecture to evaluate, or 'all' to run every architecture sequentially.",
    )
    parser.add_argument(
        "--smoke",
        type=int,
        default=None,
        metavar="N",
        help="Evaluate on only the first N questions (CI smoke test).",
    )
    args = parser.parse_args()

    questions = _load_questions(args.smoke)
    logger.info("Loaded %d questions", len(questions))

    arch_names = (
        list(ARCHITECTURE_REGISTRY)
        if args.architecture == "all"
        else [args.architecture]
    )

    for arch_name in arch_names:
        run_architecture(arch_name, questions, smoke=None)  # already sliced above

    logger.info("Evaluation complete.")


if __name__ == "__main__":
    main()
