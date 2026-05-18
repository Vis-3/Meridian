"""
Meridian — Hybrid retriever (dense + sparse via Reciprocal Rank Fusion).

Runs dense (Qdrant) and sparse (BM25) searches in parallel, then fuses
the ranked lists using RRF. RRF is rank-based — no score normalisation
needed, which makes it robust to the different score scales of cosine
similarity vs BM25.

RRF formula:  score(d) = sum_r  1 / (k + rank_r(d))
where k=60 is the standard constant that dampens the impact of top ranks.
"""

from __future__ import annotations

import logging
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    TOP_K_RETRIEVAL, TOP_K_RERANK,
    RRF_K,
    HYBRID_DENSE_WEIGHT, HYBRID_SPARSE_WEIGHT,
    COLLECTION_NAMES,
)
from retrieval import dense, sparse

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Query expansion — SEC filings use specific terminology that diverges from
# natural language queries (e.g. Apple says "net sales" not "revenue").
# Expanding the query covers both vocabularies without touching the index.
# ---------------------------------------------------------------------------

_SYNONYMS: dict[str, list[str]] = {
    "revenue":   ["net sales", "total sales", "total net sales"],
    "r&d":       ["research and development", "research & development"],
    "profit":    ["income", "earnings", "net income"],
    "employees": ["headcount", "full-time equivalent", "fte", "full time equivalent"],
    "cloud":     ["intelligent cloud", "aws", "google cloud", "azure", "amazon web services"],
    "expense":   ["cost", "costs", "spending", "expenditure"],
    "growth":    ["increase", "increased", "grew", "expansion"],
}


def expand_query(query: str) -> list[str]:
    """Return up to 4 query variants covering SEC filing terminology."""
    variants = [query]
    q_lower = query.lower()
    for term, synonyms in _SYNONYMS.items():
        if term in q_lower:
            for syn in synonyms[:2]:
                variant = q_lower.replace(term, syn)
                if variant not in variants:
                    variants.append(variant)
        if len(variants) >= 4:
            break
    return variants[:4]


# ---------------------------------------------------------------------------
# RRF fusion
# ---------------------------------------------------------------------------

def _rrf_fuse(
    dense_results: list[dict],
    sparse_results: list[dict],
    k: int = RRF_K,
    dense_weight: float = HYBRID_DENSE_WEIGHT,
    sparse_weight: float = HYBRID_SPARSE_WEIGHT,
) -> list[dict]:
    """
    Fuse two ranked lists with weighted RRF.

    Each result is identified by chunk_id. Results absent from one list
    are treated as having rank = infinity (contributing 0 to that list's
    RRF score).
    """
    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}

    for rank, result in enumerate(dense_results, start=1):
        cid = result["chunk_id"]
        scores[cid]   = scores.get(cid, 0.0) + dense_weight / (k + rank)
        payloads[cid] = result

    for rank, result in enumerate(sparse_results, start=1):
        cid = result["chunk_id"]
        scores[cid]   = scores.get(cid, 0.0) + sparse_weight / (k + rank)
        if cid not in payloads:
            payloads[cid] = result

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for cid, rrf_score in fused:
        entry = dict(payloads[cid])
        entry["score"]      = rrf_score
        entry["rrf_score"]  = rrf_score
        results.append(entry)

    return results


def _rrf_fuse_multi(
    ranked_lists: list[list[dict]],
    k: int = RRF_K,
) -> list[dict]:
    """
    Fuse an arbitrary number of ranked lists with equal-weight RRF.
    Used when query expansion produces multiple dense+sparse list pairs.
    """
    scores: dict[str, float]  = {}
    payloads: dict[str, dict] = {}
    weight = 1.0 / len(ranked_lists)

    for ranked in ranked_lists:
        for rank, result in enumerate(ranked, start=1):
            cid = result["chunk_id"]
            scores[cid]   = scores.get(cid, 0.0) + weight / (k + rank)
            if cid not in payloads:
                payloads[cid] = result

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for cid, rrf_score in fused:
        entry = dict(payloads[cid])
        entry["score"]     = rrf_score
        entry["rrf_score"] = rrf_score
        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Public search interface
# ---------------------------------------------------------------------------

def search(
    query: str,
    collection_name: str = COLLECTION_NAMES["fixed"],
    bm25_name: str = "fixed",
    top_k: int = TOP_K_RETRIEVAL,
    companies: Optional[list[str]] = None,
    fiscal_years: Optional[list[int]] = None,
    document_type: Optional[str] = None,
    sections: Optional[list[str]] = None,
) -> list[dict]:
    """
    Hybrid search: dense + sparse → RRF fusion → top_k results.

    Args:
        query:           Natural language query string.
        collection_name: Qdrant collection for dense search.
        bm25_name:       BM25 index name for sparse search.
        top_k:           Number of results to return after fusion.
        companies:       Optional company filter (e.g. ["Apple", "Google"]).
        fiscal_years:    Optional year filter (e.g. [2022, 2023]).
        document_type:   Optional doc type filter ("10-K" or "10-Q").
        sections:        Optional section filter (e.g. ["Item 1A"]).
    """
    filter_kwargs = dict(
        companies=companies,
        fiscal_years=fiscal_years,
        document_type=document_type,
        sections=sections,
    )

    # Fetch more than top_k from each so fusion has enough overlap to work with
    fetch_k = min(top_k * 2, TOP_K_RETRIEVAL)

    variants = expand_query(query)
    log.debug(f"Query variants ({len(variants)}): {variants}")

    # Collect one dense+sparse pair per variant, then do a single multi-list RRF
    all_ranked_lists: list[list[dict]] = []
    bm25_available = True

    for variant in variants:
        d_res = dense.search(variant, collection_name, top_k=fetch_k, **filter_kwargs)
        all_ranked_lists.append(d_res)

        if bm25_available:
            try:
                s_res = sparse.search(variant, bm25_name, top_k=fetch_k, **filter_kwargs)
                all_ranked_lists.append(s_res)
            except RuntimeError:
                log.warning("BM25 index not available, using dense-only retrieval")
                bm25_available = False

    if len(all_ranked_lists) == 1:
        # Only one dense list (no BM25, no expansion matched)
        return all_ranked_lists[0][:top_k]

    fused = _rrf_fuse_multi(all_ranked_lists)
    return fused[:top_k]


def search_balanced(
    query: str,
    companies: list[str],
    fiscal_years: Optional[list[int]] = None,
    top_k_per_company: int = 3,
    collection_name: str = COLLECTION_NAMES["fixed"],
    bm25_name: str = "fixed",
    document_type: Optional[str] = None,
    sections: Optional[list[str]] = None,
) -> list[dict]:
    """
    Comparative retrieval: run hybrid search per company independently,
    then merge. Guarantees representation from every requested company
    even when one company's filing language is semantically further from
    the query than others (e.g. "R&D expense" vs Microsoft's phrasing).
    """
    seen: set[str] = set()
    merged: list[dict] = []

    for company in companies:
        results = search(
            query,
            collection_name=collection_name,
            bm25_name=bm25_name,
            top_k=top_k_per_company,
            companies=[company],
            fiscal_years=fiscal_years,
            document_type=document_type,
            sections=sections,
        )
        for r in results:
            cid = r["chunk_id"]
            if cid not in seen:
                seen.add(cid)
                merged.append(r)

    return merged
