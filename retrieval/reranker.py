"""
Meridian — Cross-encoder reranker (BAAI/bge-reranker-base).

Takes the top-k results from hybrid/dense/sparse retrieval and reranks
them with a cross-encoder that scores (query, passage) jointly — more
accurate than bi-encoder similarity but too slow to use over the full corpus.

Standard two-stage pattern:
  1. Retrieval (fast, approximate)  →  top-20 candidates
  2. Reranking (slow, precise)      →  top-5 for the LLM
"""

from __future__ import annotations

import logging
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RERANKER_MODEL, TOP_K_RERANK

log = logging.getLogger(__name__)

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        log.info(f"Loading reranker: {RERANKER_MODEL}")
        _reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
    return _reranker


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = TOP_K_RERANK,
) -> list[dict]:
    """
    Rerank candidates with a cross-encoder. Returns top_k results sorted
    by reranker score descending.

    Each candidate must have a "text" key.
    Adds "rerank_score" to each returned result.
    """
    if not candidates:
        return []

    reranker = _get_reranker()

    pairs  = [(query, c["text"]) for c in candidates]
    scores = reranker.predict(pairs)

    ranked = sorted(
        zip(scores, candidates),
        key=lambda x: x[0],
        reverse=True,
    )[:top_k]

    results = []
    for score, candidate in ranked:
        entry = dict(candidate)
        entry["rerank_score"] = float(score)
        results.append(entry)

    return results


def retrieve_and_rerank(
    query: str,
    retriever_fn,
    retriever_kwargs: dict,
    top_k_retrieve: int = 20,
    top_k_rerank: int = TOP_K_RERANK,
) -> list[dict]:
    """
    Convenience wrapper: call retriever_fn, then rerank results.

    Usage:
        results = retrieve_and_rerank(
            query="What were Apple's revenue drivers in FY2023?",
            retriever_fn=hybrid.search,
            retriever_kwargs={"collection_name": "meridian_fixed",
                              "bm25_name": "fixed",
                              "companies": ["Apple"],
                              "fiscal_years": [2023]},
        )
    """
    candidates = retriever_fn(query=query, top_k=top_k_retrieve, **retriever_kwargs)
    return rerank(query, candidates, top_k=top_k_rerank)
