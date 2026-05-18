"""
Meridian — Dense retriever (semantic search via Qdrant + sentence-transformers).

Embeds query with BAAI/bge-large-en-v1.5, searches the Qdrant collection,
and returns the top-k chunks with metadata.

Supports metadata filtering by company, fiscal_year, document_type, section
so temporal and comparative queries hit only the right documents.
"""

import logging
import hashlib
from typing import Any, Optional

import torch

from sentence_transformers import SentenceTransformer

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue, MatchAny,
)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    QDRANT_URL, EMBEDDING_MODEL, EMBEDDING_DIM,
    TOP_K_RETRIEVAL, COLLECTION_NAMES,
)

log = logging.getLogger(__name__)

_model = None
_client: Optional[QdrantClient]        = None


def _get_model():
    global _model

    if _model is None:
        import os
        #import torch

        # Windows / OpenMP stability fixes
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        os.environ["OMP_NUM_THREADS"] = "1"

        

        device = "cuda" if torch.cuda.is_available() else "cpu"

        print(f"Initializing SentenceTransformer on {device}...", flush=True)

        _model = SentenceTransformer(
            EMBEDDING_MODEL,
            device=device,
            trust_remote_code=False,
        )

        _model.max_seq_length = 512

        print("SentenceTransformer initialized.", flush=True)

    return _model

def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL, prefer_grpc=False)
    return _client


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------

def ensure_collection(collection_name: str, dim: Optional[int] = None) -> None:
    """Create the Qdrant collection if it doesn't exist."""
    client = _get_client()
    dim    = dim or EMBEDDING_DIM[EMBEDDING_MODEL]
    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        log.info(f"Created Qdrant collection: {collection_name}")
    else:
        log.debug(f"Collection already exists: {collection_name}")


def collection_count(collection_name: str) -> int:
    """Return number of points in a collection (0 if collection missing)."""
    try:
        return _get_client().count(collection_name=collection_name, exact=True).count
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def index_chunks(
    chunks: list[dict],
    collection_name: str,
    batch_size: int = 64,
) -> None:
    """
    Embed and upsert a list of chunk dicts into Qdrant.
    Each chunk must have {"text": str, "metadata": dict}.
    chunk_id from metadata is used as the Qdrant point ID (hashed to int).
    """
    client = _get_client()
    model  = _get_model()
    ensure_collection(collection_name)

    texts = [c["text"] for c in chunks]
    metas = [c["metadata"] for c in chunks]

    log.info(f"Embedding {len(chunks)} chunks for {collection_name}...")

    for i in range(0, len(chunks), batch_size):
        batch_texts = texts[i: i + batch_size]
        batch_metas = metas[i: i + batch_size]
        batch_num   = i // batch_size + 1
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        print(f"  Embedding batch {batch_num}/{total_batches}  ({i+1}-{min(i+batch_size, len(chunks))} of {len(chunks)} chunks)", flush=True)

        embeddings = model.encode(
            batch_texts,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        points = []
        for j, (emb, meta, text) in enumerate(
            zip(embeddings, batch_metas, batch_texts)
        ):
            # Qdrant requires integer IDs — hash the chunk_id string
            point_id = int(hashlib.sha256(meta["chunk_id"].encode()).hexdigest()[:16],16)
            points.append(PointStruct(
                id=point_id,
                vector=emb.tolist(),
                payload={**meta, "text": text},
            ))

        client.upsert(collection_name=collection_name, points=points)
        log.debug(f"  Upserted batch {i // batch_size + 1}")

    log.info(f"Indexed {len(chunks)} chunks into {collection_name}")


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------

def _build_filter(
    companies: Optional[list[str]] = None,
    fiscal_years: Optional[list[int]] = None,
    document_type: Optional[str] = None,
    sections: Optional[list[str]] = None,
) -> Optional[Filter]:
    """Build a Qdrant metadata filter from optional constraints."""
    conditions = []

    if companies:
        conditions.append(FieldCondition(
            key="company", match=MatchAny(any=companies)
        ))
    if fiscal_years:
        conditions.append(FieldCondition(
            key="fiscal_year", match=MatchAny(any=fiscal_years)
        ))
    if document_type:
        conditions.append(FieldCondition(
            key="document_type", match=MatchValue(value=document_type)
        ))
    if sections:
        conditions.append(FieldCondition(
            key="section", match=MatchAny(any=sections)
        ))

    if not conditions:
        return None

    from qdrant_client.models import Filter as QFilter, FieldCondition as FC
    return QFilter(must=conditions)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search(
    query: str,
    collection_name: str,
    top_k: int = TOP_K_RETRIEVAL,
    companies: Optional[list[str]] = None,
    fiscal_years: Optional[list[int]] = None,
    document_type: Optional[str] = None,
    sections: Optional[list[str]] = None,
) -> list[dict]:
    """
    Embed query and return top-k results from Qdrant.

    Returns list of dicts:
      { "text", "score", "chunk_id", "company", "fiscal_year",
        "section", "document_type", "page_range", ... }
    """
    client = _get_client()
    model  = _get_model()

    query_vec = model.encode(query, normalize_embeddings=True).tolist()
    filt      = _build_filter(companies, fiscal_years, document_type, sections)

    response = client.query_points(
        collection_name=collection_name,
        query=query_vec,
        limit=top_k,
        query_filter=filt,
        with_payload=True,
    )

    results = []
    for hit in response.points:
        payload = hit.payload or {}
        results.append({
            "text":          payload.get("text", ""),
            "score":         hit.score,
            "chunk_id":      payload.get("chunk_id", ""),
            "company":       payload.get("company", ""),
            "fiscal_year":   payload.get("fiscal_year"),
            "section":       payload.get("section", ""),
            "document_type": payload.get("document_type", ""),
            "document_path": payload.get("document_path", ""),
            "page_range":    payload.get("page_range", []),
        })

    return results
