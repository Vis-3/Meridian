"""
Meridian — Architecture 2: Hybrid RAG with reranking and parent-child lookup.

Pipeline:
  1. hybrid.search() with synonym expansion → top_k=20 candidates
  2. BGE reranker → top_k=5
  3. Parent-child lookup: swap child chunk text for parent chunk text before
     sending to LLM (gives more context per retrieved passage).
     Falls back to child text when parent_id is None (fixed-chunk index).

Collection: meridian_semantic if populated, else meridian_fixed.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from architectures.base import BaseArchitecture
from retrieval import hybrid, dense
from retrieval.reranker import rerank
from llm.generator import generate as llm_generate
from config import COLLECTION_NAMES, TOP_K_RETRIEVAL, TOP_K_RERANK

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from config import QDRANT_URL


def _pick_collection() -> str:
    """Use semantic collection if it has chunks, else fall back to fixed."""
    client = QdrantClient(url=QDRANT_URL, prefer_grpc=False)
    try:
        count = client.count(
            collection_name=COLLECTION_NAMES["semantic"], exact=True
        ).count
        if count > 0:
            return COLLECTION_NAMES["semantic"]
    except Exception:
        pass
    return COLLECTION_NAMES["fixed"]


def _lookup_parent_text(
    chunk: dict,
    client: QdrantClient,
    collection_name: str,
) -> str:
    """
    Return parent chunk text if parent_id is set, else return child text.
    Parent chunks give the LLM broader context than the 256-token child.
    """
    parent_id = chunk.get("parent_id")
    if not parent_id:
        return chunk.get("text", "")

    try:
        results, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(must=[
                FieldCondition(key="chunk_id", match=MatchValue(value=parent_id))
            ]),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if results:
            return results[0].payload.get("text", chunk.get("text", ""))
    except Exception:
        pass

    return chunk.get("text", "")


class HybridRAG(BaseArchitecture):
    name = "hybrid_rag"

    def __init__(
        self,
        collection_name: str | None = None,
        bm25_name: str = "fixed",
        top_k_retrieve: int = TOP_K_RETRIEVAL,
        top_k_rerank: int = TOP_K_RERANK,
    ):
        self.collection_name = collection_name or _pick_collection()
        self.bm25_name       = bm25_name
        self.top_k_retrieve  = top_k_retrieve
        self.top_k_rerank    = top_k_rerank
        self._qdrant         = QdrantClient(url=QDRANT_URL, prefer_grpc=False)

    def retrieve(
        self,
        question: str,
        companies: list[str] | None = None,
        fiscal_years: list[int] | None = None,
        sections: list[str] | None = None,
        **_,
    ) -> list[dict]:
        # Step 1: hybrid search with synonym expansion → 20 candidates
        candidates = hybrid.search(
            question,
            collection_name=self.collection_name,
            bm25_name=self.bm25_name,
            top_k=self.top_k_retrieve,
            companies=companies,
            fiscal_years=fiscal_years,
            sections=sections,
        )

        # Step 2: BGE reranker → top-5
        reranked = rerank(question, candidates, top_k=self.top_k_rerank)

        # Step 3: Parent-child lookup — swap child text for parent text
        for chunk in reranked:
            parent_text = _lookup_parent_text(chunk, self._qdrant, self.collection_name)
            chunk["text"] = parent_text

        return reranked

    def generate(self, question: str, chunks: list[dict]) -> dict:
        result = llm_generate(question, chunks)
        result["architecture_name"] = self.name
        return result


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    naive_arch  = __import__("architectures.naive", fromlist=["NaiveRAG"]).NaiveRAG()
    hybrid_arch = HybridRAG()

    q = "What was Apple revenue 2023?"

    naive_out  = naive_arch.run("smoke_naive_ref",   q)
    hybrid_out = hybrid_arch.run("smoke_hybrid_001", q)

    assert hybrid_out["answer"], "answer must not be empty"
    assert len(hybrid_out["citations"]) > 0, "must have citations"

    # Citations should differ (different chunks / reranked order)
    naive_ids  = {c["chunk_id"] for c in naive_out["citations"]}
    hybrid_ids = {c["chunk_id"] for c in hybrid_out["citations"]}
    citations_differ = naive_ids != hybrid_ids

    print(f"\nArchitecture  : {hybrid_out['architecture_name']}")
    print(f"Collection    : {hybrid_arch.collection_name}")
    print(f"Latency       : {hybrid_out['latency_ms']} ms")
    print(f"Tokens        : {hybrid_out['tokens_used']}")
    print(f"Citations     : {len(hybrid_out['citations'])}")
    print(f"Differs from naive: {citations_differ}")
    print(f"\nAnswer:\n{hybrid_out['answer']}")
    print(f"\nFirst citation:")
    c = hybrid_out["citations"][0]
    print(f"  [{c['company']} FY{c['year']} {c['section']}]")
    print(f"  {c['text'][:120]}")
    print(f"\nSmoke test PASSED  (citations differ = {citations_differ})")
