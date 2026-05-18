"""
Meridian — Sparse retriever (BM25 keyword search).

Builds a BM25 index over all chunks for a given collection, persists it
to disk under data/indexes/, and supports filtered search by metadata.

BM25 is the backbone of traditional IR and complements dense retrieval:
it excels at exact-match terms (ticker symbols, product names, numbers)
that dense embeddings often smooth over.
"""

from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import INDEX_DIR, TOP_K_RETRIEVAL

log = logging.getLogger(__name__)

INDEX_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# BM25 wrapper
# ---------------------------------------------------------------------------

class BM25Index:
    """
    Thin wrapper around rank_bm25.BM25Okapi that stores the original
    chunk list for result reconstruction and supports metadata filtering.
    """

    def __init__(self) -> None:
        self._bm25  = None
        self._chunks: list[dict] = []

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, chunks: list[dict]) -> None:
        """Build the index from a list of {"text": str, "metadata": dict} dicts."""
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            raise ImportError("Install rank-bm25: pip install rank-bm25")

        self._chunks = chunks
        tokenized = [c["text"].lower().split() for c in chunks]
        self._bm25  = BM25Okapi(tokenized)
        log.info(f"BM25 index built: {len(chunks)} chunks")

    # ------------------------------------------------------------------
    # Persist
    # ------------------------------------------------------------------

    def save(self, name: str) -> Path:
        path = INDEX_DIR / f"{name}_bm25.pkl"
        with open(path, "wb") as f:
            pickle.dump({"bm25": self._bm25, "chunks": self._chunks}, f)
        log.info(f"BM25 index saved: {path}")
        return path

    def load(self, name: str) -> bool:
        path = INDEX_DIR / f"{name}_bm25.pkl"
        if not path.exists():
            return False
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._bm25  = data["bm25"]
        self._chunks = data["chunks"]
        log.info(f"BM25 index loaded: {path}  ({len(self._chunks)} chunks)")
        return True

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = TOP_K_RETRIEVAL,
        companies: Optional[list[str]] = None,
        fiscal_years: Optional[list[int]] = None,
        document_type: Optional[str] = None,
        sections: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        BM25 search with optional metadata pre-filtering.
        Returns list of result dicts matching the dense retriever schema.
        """
        if self._bm25 is None:
            raise RuntimeError("BM25 index not built or loaded.")

        # Pre-filter chunks by metadata
        candidates = self._chunks
        if companies:
            candidates = [c for c in candidates
                          if c["metadata"].get("company") in companies]
        if fiscal_years:
            candidates = [c for c in candidates
                          if c["metadata"].get("fiscal_year") in fiscal_years]
        if document_type:
            candidates = [c for c in candidates
                          if c["metadata"].get("document_type") == document_type]
        if sections:
            candidates = [c for c in candidates
                          if c["metadata"].get("section") in sections]

        if not candidates:
            return []

        # Score against filtered subset by rebuilding a sub-index
        # For large corpora, pre-filtering then re-scoring is faster than
        # scoring all and post-filtering.
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            raise ImportError("Install rank-bm25: pip install rank-bm25")

        tokenized = [c["text"].lower().split() for c in candidates]
        sub_bm25  = BM25Okapi(tokenized)

        query_tokens = query.lower().split()
        scores       = sub_bm25.get_scores(query_tokens)

        # Sort by score descending, take top_k
        ranked = sorted(
            zip(scores, candidates),
            key=lambda x: x[0],
            reverse=True,
        )[:top_k]

        results = []
        for score, chunk in ranked:
            meta = chunk["metadata"]
            results.append({
                "text":          chunk["text"],
                "score":         float(score),
                "chunk_id":      meta.get("chunk_id", ""),
                "company":       meta.get("company", ""),
                "fiscal_year":   meta.get("fiscal_year"),
                "section":       meta.get("section", ""),
                "document_type": meta.get("document_type", ""),
                "document_path": meta.get("document_path", ""),
                "page_range":    meta.get("page_range", []),
            })

        return results


# ---------------------------------------------------------------------------
# Module-level singleton registry
# ---------------------------------------------------------------------------

_indexes: dict[str, BM25Index] = {}


def get_index(name: str) -> BM25Index:
    """Return cached BM25Index for `name`, loading from disk if needed."""
    if name not in _indexes:
        idx = BM25Index()
        if not idx.load(name):
            raise RuntimeError(
                f"BM25 index '{name}' not found. Run index_chunks() first."
            )
        _indexes[name] = idx
    return _indexes[name]


def index_chunks(chunks: list[dict], name: str) -> BM25Index:
    """Build, save, and cache a BM25 index for `name`."""
    idx = BM25Index()
    idx.build(chunks)
    idx.save(name)
    _indexes[name] = idx
    return idx


def search(
    query: str,
    name: str,
    top_k: int = TOP_K_RETRIEVAL,
    companies: Optional[list[str]] = None,
    fiscal_years: Optional[list[int]] = None,
    document_type: Optional[str] = None,
    sections: Optional[list[str]] = None,
) -> list[dict]:
    """Convenience wrapper: load index by name and search."""
    return get_index(name).search(
        query, top_k=top_k,
        companies=companies, fiscal_years=fiscal_years,
        document_type=document_type, sections=sections,
    )
