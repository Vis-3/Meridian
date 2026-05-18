"""
Meridian — Index builder.

Reads every processed JSON from data/processed/, chunks each document with
the fixed-size chunker, then:
  1. Upserts embeddings into the Qdrant 'meridian_fixed' collection.
  2. Builds and saves a BM25 index to data/indexes/fixed_bm25.pkl.

Usage:
    python retrieval/build_index.py
    python retrieval/build_index.py --smoke 5   # first 5 docs only
"""

from __future__ import annotations


# Initialize CUDA before gRPC loads its native libs — prevents DLL conflict on Windows


import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from config import PROCESSED_DIR, COLLECTION_NAMES

from ingestion.chunkers.fixed import chunk_text as fixed_chunk

from retrieval import dense




from retrieval import sparse



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_processed_docs(smoke: int | None = None) -> list[dict]:
    paths = sorted(PROCESSED_DIR.glob("*.json"))
    if smoke:
        paths = paths[:smoke]
    docs = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            docs.append(json.load(f))
    log.info(f"Loaded {len(docs)} processed documents")
    return docs


def chunk_all(docs: list[dict]) -> list[dict]:
    """Chunk every section of every document with the fixed chunker."""
    all_chunks: list[dict] = []
    for doc in docs:
        file_meta  = doc["metadata"]
        doc_path   = doc["source_filename"]
        for section, content in doc["sections"].items():
            text  = content.get("text", "").strip()
            pages = content.get("pages", [1])
            if not text:
                continue
            chunks = fixed_chunk(text, file_meta, section, pages, doc_path)
            all_chunks.extend(chunks)

    log.info(f"Total chunks: {len(all_chunks)}")
    return all_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Qdrant + BM25 indexes")
    parser.add_argument("--smoke", type=int, default=None,
                        help="Only index first N documents (for testing)")
    parser.add_argument("--skip-dense",  action="store_true",
                        help="Skip Qdrant embedding (BM25 only)")
    parser.add_argument("--skip-sparse", action="store_true",
                        help="Skip BM25 index (Qdrant only)")
    args = parser.parse_args()

    docs   = load_processed_docs(args.smoke)
    chunks = chunk_all(docs)

    collection = COLLECTION_NAMES["fixed"]

    if not args.skip_dense:
        # Load model first, before any Qdrant calls, to avoid gRPC/CUDA DLL conflict
        
        dense._get_model()
        

        log.info(f"Indexing into Qdrant collection: {collection}")
        dense.ensure_collection(collection)
        existing = dense.collection_count(collection)
        if existing > 0:
            log.info(f"  Collection already has {existing} points — upserting (safe to re-run)")
        dense.index_chunks(chunks, collection)
        log.info(f"Qdrant: {dense.collection_count(collection)} points in {collection}")

    if not args.skip_sparse:
        log.info("Building BM25 index...")
        sparse.index_chunks(chunks, name="fixed")
        log.info("BM25 index saved to data/indexes/fixed_bm25.pkl")

    log.info("Index build complete.")


if __name__ == "__main__":
    main()