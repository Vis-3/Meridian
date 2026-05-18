"""
Meridian — Offline script: build parent-child semantic chunk index.

Three modes:

  Combined (local, ~2-3 hrs CPU):
      python scripts/build_semantic_index.py

  Export (Kaggle GPU, ~10-20 min):
      python scripts/build_semantic_index.py --export vectors.pkl
      Computes all embeddings and saves them to a pickle file.
      No Qdrant required. Copy the output file back locally.

  Import (local, ~1 min):
      python scripts/build_semantic_index.py --import-file vectors.pkl
      Reads the pickle produced by --export and upserts to local Qdrant.
      No GPU required.

Strategy:
  1. Semantic chunker splits each section at cosine similarity valleys
     between adjacent sentences → coherent parent passages.
  2. Each semantic parent is split into 256-token child chunks for
     retrieval precision.
  3. Children carry parent_id → hybrid_rag._lookup_parent_text() expands
     retrieved children back to the full semantic parent for the LLM.
  4. Both parents and children are embedded with bge-large-en-v1.5
     and stored in Qdrant collection "meridian_semantic".

Crash-safe: checkpoint file tracks completed stems.
Restart after a crash — already-processed docs are skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import (
    PROCESSED_DIR,
    COLLECTION_NAMES,
    EMBEDDING_MODEL,
    EMBEDDING_DIM,
    QDRANT_URL,
    CHILD_CHUNK_SIZE,
    FIXED_OVERLAP,
)
from ingestion.chunkers.semantic import chunk_document as semantic_chunk_document

SEMANTIC_COLLECTION = COLLECTION_NAMES["semantic"]
CHECKPOINT_FILE     = ROOT / "data" / "indexes" / "semantic_index_checkpoint.json"
UPSERT_BATCH        = 64


# ---------------------------------------------------------------------------
# Child splitter
# ---------------------------------------------------------------------------

def _split_into_children(
    parent_text: str,
    parent_meta: dict,
    child_size: int = CHILD_CHUNK_SIZE,
    overlap: int = FIXED_OVERLAP // 2,
) -> list[dict]:
    """Split a semantic parent into fixed-size child chunks with parent_id."""
    tokens = parent_text.split()
    children = []
    start = 0
    idx   = 0

    while start < len(tokens):
        end        = min(start + child_size, len(tokens))
        child_text = " ".join(tokens[start:end])
        child_meta = {
            **parent_meta,
            "chunk_id":  f"{parent_meta['chunk_id']}_child_{idx:04d}",
            "parent_id": parent_meta["chunk_id"],
        }
        children.append({"text": child_text, "metadata": child_meta})
        idx += 1
        if end == len(tokens):
            break
        start += child_size - overlap

    return children


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _chunk_id_to_point_id(chunk_id: str) -> int:
    return int(hashlib.sha256(chunk_id.encode()).hexdigest()[:15], 16)


def _load_model(embedding_model: str):
    import torch
    from sentence_transformers import SentenceTransformer
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading {embedding_model} on {device} ...")
    model = SentenceTransformer(embedding_model, device=device, trust_remote_code=False)
    model.max_seq_length = 512
    return model, device


def _build_records(docs: list[Path], model, *, limit: int | None = None) -> list[dict]:
    """
    Chunk and embed all docs. Returns a flat list of record dicts:
      { "point_id": int, "vector": list[float], "payload": dict }
    """
    if limit:
        docs = docs[:limit]

    records: list[dict] = []
    t0 = time.perf_counter()

    for i, doc_path in enumerate(docs, 1):
        doc            = json.loads(doc_path.read_text(encoding="utf-8"))
        parents        = semantic_chunk_document(doc)
        doc_records    = []

        for parent in parents:
            p_text = parent["text"].strip()
            p_meta = parent["metadata"]
            if not p_text:
                continue

            # Collect texts to batch-encode (parent + all children)
            children = _split_into_children(p_text, p_meta)
            all_chunks = [{"text": p_text, "metadata": p_meta}] + children

            texts = [c["text"] for c in all_chunks]
            vecs  = model.encode(
                texts,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            for chunk, vec in zip(all_chunks, vecs):
                doc_records.append({
                    "point_id": _chunk_id_to_point_id(chunk["metadata"]["chunk_id"]),
                    "vector":   vec.tolist(),
                    "payload":  {**chunk["metadata"], "text": chunk["text"]},
                })

        records.extend(doc_records)

        elapsed = time.perf_counter() - t0
        rate    = i / elapsed
        eta_s   = (len(docs) - i) / rate if rate > 0 else 0
        print(
            f"  [{i:3d}/{len(docs)}] {doc_path.stem:<40}  "
            f"points={len(doc_records):4d}  "
            f"elapsed={elapsed/60:.1f}m  eta={eta_s/60:.1f}m"
        )

    return records


# ---------------------------------------------------------------------------
# Qdrant helpers
# ---------------------------------------------------------------------------

def _ensure_collection(client, dim: int) -> None:
    from qdrant_client.models import Distance, VectorParams
    existing = {c.name for c in client.get_collections().collections}
    if SEMANTIC_COLLECTION not in existing:
        client.create_collection(
            collection_name=SEMANTIC_COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"Created collection: {SEMANTIC_COLLECTION}")
    else:
        print(f"Collection exists:  {SEMANTIC_COLLECTION}")


def _upsert_records(client, records: list[dict]) -> None:
    from qdrant_client.models import PointStruct
    for i in range(0, len(records), UPSERT_BATCH):
        batch = records[i : i + UPSERT_BATCH]
        client.upsert(
            collection_name=SEMANTIC_COLLECTION,
            points=[
                PointStruct(id=r["point_id"], vector=r["vector"], payload=r["payload"])
                for r in batch
            ],
        )


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _load_checkpoint() -> set[str]:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CHECKPOINT_FILE.exists():
        return set(json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8")).get("completed", []))
    return set()


def _save_checkpoint(completed: set[str]) -> None:
    CHECKPOINT_FILE.write_text(
        json.dumps({"completed": sorted(completed)}, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Mode: combined (default)
# ---------------------------------------------------------------------------

def run_combined(docs: list[Path], model, limit: int | None) -> None:
    from qdrant_client import QdrantClient
    dim    = EMBEDDING_DIM[EMBEDDING_MODEL]
    client = QdrantClient(url=QDRANT_URL, prefer_grpc=False)
    _ensure_collection(client, dim)

    completed = _load_checkpoint()
    pending   = [d for d in docs if d.stem not in completed]
    if limit:
        pending = pending[:limit]

    print(f"Docs to process: {len(pending)}  (skipping {len(docs) - len(pending)} already done)")

    for i, doc_path in enumerate(pending, 1):
        doc     = json.loads(doc_path.read_text(encoding="utf-8"))
        parents = semantic_chunk_document(doc)
        points  = []
        t0      = time.perf_counter()

        for parent in parents:
            p_text = parent["text"].strip()
            p_meta = parent["metadata"]
            if not p_text:
                continue
            children   = _split_into_children(p_text, p_meta)
            all_chunks = [{"text": p_text, "metadata": p_meta}] + children
            texts      = [c["text"] for c in all_chunks]
            vecs       = model.encode(texts, batch_size=32,
                                      normalize_embeddings=True,
                                      show_progress_bar=False)
            for chunk, vec in zip(all_chunks, vecs):
                from qdrant_client.models import PointStruct
                points.append(PointStruct(
                    id      = _chunk_id_to_point_id(chunk["metadata"]["chunk_id"]),
                    vector  = vec.tolist(),
                    payload = {**chunk["metadata"], "text": chunk["text"]},
                ))

        _upsert_records(client, [
            {"point_id": p.id, "vector": p.vector, "payload": p.payload}
            for p in points
        ])
        completed.add(doc_path.stem)
        _save_checkpoint(completed)

        elapsed = time.perf_counter() - t0
        total_done = len(completed)
        print(f"  [{i:3d}/{len(pending)}] {doc_path.stem:<40}  points={len(points):4d}  {elapsed:.1f}s")

    count = client.count(collection_name=SEMANTIC_COLLECTION, exact=True).count
    print(f"\nDone. {SEMANTIC_COLLECTION}: {count} total points.")


# ---------------------------------------------------------------------------
# Mode: --export (Kaggle)
# ---------------------------------------------------------------------------

def run_export(docs: list[Path], model, out_path: Path, limit: int | None) -> None:
    print(f"Export mode — output: {out_path}")
    records = _build_records(docs, model, limit=limit)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump(records, f, protocol=pickle.HIGHEST_PROTOCOL)
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"\nSaved {len(records)} records to {out_path}  ({size_mb:.1f} MB)")
    print("Copy this file back locally, then run:")
    print(f"  python scripts/build_semantic_index.py --import-file {out_path.name}")


# ---------------------------------------------------------------------------
# Mode: --import-file (local, after Kaggle export)
# ---------------------------------------------------------------------------

def run_import(import_path: Path) -> None:
    from qdrant_client import QdrantClient
    print(f"Import mode — reading {import_path} ...")
    with open(import_path, "rb") as f:
        records: list[dict] = pickle.load(f)
    print(f"Loaded {len(records)} records.")

    dim    = EMBEDDING_DIM[EMBEDDING_MODEL]
    client = QdrantClient(url=QDRANT_URL, prefer_grpc=False)
    _ensure_collection(client, dim)

    t0 = time.perf_counter()
    _upsert_records(client, records)
    elapsed = time.perf_counter() - t0

    count = client.count(collection_name=SEMANTIC_COLLECTION, exact=True).count
    print(f"Upserted {len(records)} points in {elapsed:.1f}s.")
    print(f"{SEMANTIC_COLLECTION}: {count} total points.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build meridian_semantic Qdrant collection.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local all-in-one (slow on CPU):
  python scripts/build_semantic_index.py

  # Step 1 — run on Kaggle GPU, saves vectors.pkl:
  python scripts/build_semantic_index.py --export vectors.pkl

  # Step 2 — run locally after copying vectors.pkl back:
  python scripts/build_semantic_index.py --import-file vectors.pkl

  # Quick test (first 3 docs):
  python scripts/build_semantic_index.py --limit 3
        """,
    )
    parser.add_argument("--export",      metavar="FILE",
                        help="Embed all docs and save vectors to FILE (no Qdrant needed).")
    parser.add_argument("--import-file", metavar="FILE", dest="import_file",
                        help="Load a previously exported FILE and upsert to Qdrant.")
    parser.add_argument("--limit",       type=int, default=None, metavar="N",
                        help="Process only the first N documents.")
    args = parser.parse_args()

    if args.import_file:
        run_import(Path(args.import_file))
        return

    docs = sorted(PROCESSED_DIR.glob("*.json"))
    print(f"Found {len(docs)} documents in {PROCESSED_DIR}")

    model, device = _load_model(EMBEDDING_MODEL)

    if args.export:
        run_export(docs, model, Path(args.export), limit=args.limit)
    else:
        run_combined(docs, model, limit=args.limit)


if __name__ == "__main__":
    main()
