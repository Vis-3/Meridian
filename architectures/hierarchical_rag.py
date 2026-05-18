"""
Meridian — Architecture 4: Hierarchical RAG.

Requires the summary index to be pre-built:
    python scripts/build_summary_index.py   (run once, ~50 min)

Two-level retrieval at query time:
  Level 1 — Embed query → search "meridian_summaries" → top-3 documents.
  Level 2 — Hybrid search on "meridian_fixed" filtered to those 3 documents only.
             Rerank → top-5.

No LLM calls at retrieval time. Fast after index is built.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

from architectures.base import BaseArchitecture
from retrieval import hybrid
from retrieval.reranker import rerank
from llm.generator import generate as llm_generate
from config import (
    COLLECTION_NAMES, TOP_K_RERANK, QDRANT_URL, EMBEDDING_MODEL,
)

log = logging.getLogger(__name__)

SUMMARY_COLLECTION = "meridian_summaries"
CHUNK_COLLECTION   = COLLECTION_NAMES["fixed"]

_client: QdrantClient | None = None
_model:  SentenceTransformer | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL, prefer_grpc=False)
    return _client


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        os.environ["OMP_NUM_THREADS"] = "1"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = SentenceTransformer(EMBEDDING_MODEL, device=device, trust_remote_code=False)
        _model.max_seq_length = 512
    return _model


def _summary_count() -> int:
    try:
        return _get_client().count(
            collection_name=SUMMARY_COLLECTION, exact=True
        ).count
    except Exception:
        return 0


class HierarchicalRAG(BaseArchitecture):
    name = "hierarchical_rag"

    def __init__(
        self,
        top_k_docs: int = 3,
        top_k_chunks_per_doc: int = 7,
        top_k_rerank: int = TOP_K_RERANK,
    ):
        self.top_k_docs           = top_k_docs
        self.top_k_chunks_per_doc = top_k_chunks_per_doc
        self.top_k_rerank         = top_k_rerank
        self._last_selected_docs: list[dict] = []

        n = _summary_count()
        if n == 0:
            raise RuntimeError(
                "Summary index is empty. "
                "Run: python scripts/build_summary_index.py"
            )
        log.info(f"Summary index has {n} documents.")

    def _search_summaries(self, question: str) -> list[dict]:
        vec  = _get_model().encode(question, normalize_embeddings=True).tolist()
        resp = _get_client().query_points(
            collection_name=SUMMARY_COLLECTION,
            query=vec,
            limit=self.top_k_docs,
            with_payload=True,
        )
        return [hit.payload for hit in resp.points]

    def retrieve(
        self,
        question: str,
        companies: list[str] | None = None,
        fiscal_years: list[int] | None = None,
        sections: list[str] | None = None,
        **_,
    ) -> list[dict]:
        # Level 1: document selection via summary index
        top_docs = self._search_summaries(question)

        # Respect caller-supplied filters; fall back to full selection if nothing matches
        if companies:
            filtered = [d for d in top_docs if d.get("company") in companies]
            top_docs = filtered or top_docs
        if fiscal_years:
            filtered = [d for d in top_docs if d.get("fiscal_year") in fiscal_years]
            top_docs = filtered or top_docs

        self._last_selected_docs = top_docs
        log.debug("[HierarchicalRAG] Selected %d documents", len(top_docs))
        if os.getenv("DEBUG"):
            for d in top_docs:
                print(f"    - {d.get('label', d.get('stem', '?'))}")

        # Level 2: chunk retrieval scoped to selected documents
        all_chunks: list[dict] = []
        seen: set[str] = set()

        for doc in top_docs:
            chunks = hybrid.search(
                question,
                collection_name=CHUNK_COLLECTION,
                top_k=self.top_k_chunks_per_doc,
                companies=[doc["company"]] if doc.get("company") else None,
                fiscal_years=[doc["fiscal_year"]] if doc.get("fiscal_year") else None,
                document_type=doc.get("document_type") or None,
                sections=sections,
            )
            for c in chunks:
                cid = c["chunk_id"]
                if cid not in seen:
                    seen.add(cid)
                    all_chunks.append(c)

        return rerank(question, all_chunks, top_k=self.top_k_rerank)

    def generate(self, question: str, chunks: list[dict]) -> dict:
        result = llm_generate(question, chunks)
        result["architecture_name"] = self.name
        return result


# ---------------------------------------------------------------------------
# Smoke test  (requires summary index — run build_summary_index.py first)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        arch = HierarchicalRAG()
    except RuntimeError as e:
        print(f"\nERROR: {e}")
        print("Run: python scripts/build_summary_index.py")
        sys.exit(1)

    q   = "What was Apple revenue 2023?"
    out = arch.run("smoke_hier_001", q)

    assert arch._last_selected_docs, "must select at least one document"
    assert out["answer"], "answer must not be empty"
    assert len(out["citations"]) > 0, "must have citations"

    print(f"\nArchitecture : {out['architecture_name']}")
    print(f"Documents selected:")
    for d in arch._last_selected_docs:
        print(f"  - {d.get('label', '?')}")
    print(f"Latency      : {out['latency_ms']} ms")
    print(f"Tokens       : {out['tokens_used']}")
    print(f"\nAnswer:\n{out['answer']}")
    print("\nSmoke test PASSED")
