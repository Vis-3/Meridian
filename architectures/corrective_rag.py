"""
Meridian — Architecture 5: Corrective RAG (CRAG).

Pipeline:
  1. hybrid.search() retrieval → top-20 candidates.
  2. LLM relevance evaluator: scores each chunk 0.0-1.0 against the question.
  3. Chunks below THRESHOLD (0.5) are filtered out.
  4. If ALL chunks score below threshold → flag needs_web_search=True,
     use the best available chunks anyway (no actual web call — logged for audit).
  5. Generate answer from surviving chunks.

Insight: retrieval is imperfect; a cheap LLM relevance pass catches off-topic
chunks before they pollute the context window and degrade faithfulness.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from architectures.base import BaseArchitecture
from retrieval import hybrid
from retrieval.reranker import rerank
from llm.generator import generate as llm_generate
from llm.prompts import (
    RETRIEVAL_EVALUATOR_SYSTEM as _EVAL_SYSTEM,
    RETRIEVAL_EVALUATOR_USER_TEMPLATE as _EVAL_USER,
)
from config import (
    COLLECTION_NAMES, TOP_K_RETRIEVAL, TOP_K_RERANK,
    OLLAMA_BASE_URL, LLM_MODEL, RETRIEVAL_RELEVANCE_THRESHOLD,
)

log = logging.getLogger(__name__)


def _score_chunk(question: str, chunk_text: str, model: str = LLM_MODEL) -> float:
    """Ask the LLM to score chunk relevance 0.0-1.0. Returns 0.5 on error."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _EVAL_SYSTEM},
            {"role": "user",   "content": _EVAL_USER.format(
                question=question,
                passage=chunk_text[:600],
            )},
        ],
        "stream":  False,
        "options": {"temperature": 0.0, "num_predict": 20},
    }
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=30
        )
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "").strip()
        # Extract JSON from response
        start = content.find("{")
        end   = content.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(content[start:end])
            score = float(data.get("score", 0.5))
            return max(0.0, min(1.0, score))
    except Exception as e:
        log.debug(f"Relevance scoring failed: {e}")
    return 0.5  # safe default


class CorrectiveRAG(BaseArchitecture):
    name = "corrective_rag"

    def __init__(
        self,
        collection_name: str = COLLECTION_NAMES["fixed"],
        bm25_name: str = "fixed",
        top_k_retrieve: int = TOP_K_RETRIEVAL,
        top_k_rerank: int = TOP_K_RERANK,
        relevance_threshold: float = RETRIEVAL_RELEVANCE_THRESHOLD,
    ):
        self.collection_name      = collection_name
        self.bm25_name            = bm25_name
        self.top_k_retrieve       = top_k_retrieve
        self.top_k_rerank         = top_k_rerank
        self.relevance_threshold  = relevance_threshold
        self._last_scores: list[tuple[float, str]] = []
        self.needs_web_search     = False

    def retrieve(
        self,
        question: str,
        companies: list[str] | None = None,
        fiscal_years: list[int] | None = None,
        sections: list[str] | None = None,
        **_,
    ) -> list[dict]:
        self.needs_web_search = False

        # Step 1: hybrid retrieval
        candidates = hybrid.search(
            question,
            collection_name=self.collection_name,
            bm25_name=self.bm25_name,
            top_k=self.top_k_retrieve,
            companies=companies,
            fiscal_years=fiscal_years,
            sections=sections,
        )

        # Step 2: LLM relevance evaluation
        log.debug("[CRAG] Scoring %d chunks for relevance...", len(candidates))
        scored: list[tuple[float, dict]] = []
        self._last_scores = []

        for chunk in candidates:
            score = _score_chunk(question, chunk.get("text", ""))
            scored.append((score, chunk))
            self._last_scores.append((score, chunk.get("chunk_id", "")))
            if os.getenv("DEBUG"):
                company = chunk.get("company", "?")
                year    = chunk.get("fiscal_year", "?")
                section = chunk.get("section", "?")
                print(f"    score={score:.2f}  [{company} FY{year} {section}]")

        # Step 3: filter below threshold
        passing = [(s, c) for s, c in scored if s >= self.relevance_threshold]

        if not passing:
            # All chunks below threshold — flag and use best available
            self.needs_web_search = True
            log.warning(
                "All %d chunks below threshold %.2f. needs_web_search=True. Using top chunks anyway.",
                len(scored), self.relevance_threshold,
            )
            passing = sorted(scored, key=lambda x: x[0], reverse=True)[:self.top_k_rerank]

        filtered_chunks = [c for _, c in passing]

        # Step 4: rerank the surviving chunks
        return rerank(question, filtered_chunks, top_k=self.top_k_rerank)

    def generate(self, question: str, chunks: list[dict]) -> dict:
        result = llm_generate(question, chunks)
        result["architecture_name"] = self.name
        result["needs_web_search"]  = self.needs_web_search
        return result

    def run(self, question_id: str, question: str, **kwargs) -> dict:
        out = super().run(question_id, question, **kwargs)
        out["needs_web_search"] = self.needs_web_search
        return out


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    arch = CorrectiveRAG()
    q   = "What was Apple revenue 2023?"
    out = arch.run("smoke_crag_001", q)

    scores = arch._last_scores
    assert len(scores) > 0, "must return at least one relevance score"

    print(f"\nArchitecture    : {out['architecture_name']}")
    print(f"Chunks scored   : {len(scores)}")
    print(f"Needs web search: {out.get('needs_web_search', False)}")
    print(f"Latency         : {out['latency_ms']} ms")
    print(f"Tokens          : {out['tokens_used']}")
    print(f"\nAnswer:\n{out['answer']}")
    print("\nSmoke test PASSED")
