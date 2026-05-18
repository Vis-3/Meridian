"""
Meridian — Offline script: build document-level summary index.

Run ONCE before using hierarchical_rag:
    python scripts/build_summary_index.py

Steps:
  1. Load each processed JSON from data/processed/
  2. Generate a 3-5 sentence LLM summary per document
  3. Checkpoint to data/summaries/{stem}.json (skip on restart)
  4. Embed summaries and upsert to Qdrant: "meridian_summaries"

Progress is printed every 10 documents.
Estimated runtime: ~50 min on Ollama llama3.1:8b (100 docs).
"""

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import torch
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

from config import (
    PROCESSED_DIR, EMBEDDING_MODEL, EMBEDDING_DIM,
    OLLAMA_BASE_URL, LLM_MODEL, QDRANT_URL,
)

SUMMARY_COLLECTION = "meridian_summaries"
CHECKPOINT_DIR     = Path(__file__).parent.parent / "data" / "summaries"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

_SUMMARY_PROMPT = (
    "Summarize this SEC filing in 3-5 sentences. "
    "Include: company name, fiscal year, document type (10-K or 10-Q), "
    "key financial figures mentioned (revenue, profit, R&D spend, etc.), "
    "and main topics covered (risks, business segments, MD&A highlights)."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _llm_summarise(doc_label: str, sample_text: str) -> str:
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": _SUMMARY_PROMPT},
            {"role": "user",   "content":
                f"Document: {doc_label}\n\nExcerpt:\n{sample_text[:3000]}\n\nSummary:"},
        ],
        "stream":  False,
        "options": {"temperature": 0.1, "num_predict": 250},
    }
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=90
    )
    resp.raise_for_status()
    return resp.json().get("message", {}).get("content", "").strip()


def _checkpoint_path(stem: str) -> Path:
    return CHECKPOINT_DIR / f"{stem}.json"


def _load_checkpoint(stem: str) -> dict | None:
    p = _checkpoint_path(stem)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _save_checkpoint(stem: str, data: dict) -> None:
    _checkpoint_path(stem).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _ensure_collection(client: QdrantClient, dim: int) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if SUMMARY_COLLECTION not in existing:
        client.create_collection(
            collection_name=SUMMARY_COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"Created Qdrant collection: {SUMMARY_COLLECTION}")


def _already_in_qdrant(client: QdrantClient, point_id: int) -> bool:
    try:
        results = client.retrieve(
            collection_name=SUMMARY_COLLECTION,
            ids=[point_id],
            with_payload=False,
            with_vectors=False,
        )
        return len(results) > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    docs = sorted(PROCESSED_DIR.glob("*.json"))
    total = len(docs)
    print(f"Found {total} processed documents in {PROCESSED_DIR}")

    # Init model + client
    import os
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["OMP_NUM_THREADS"] = "1"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading embedding model on {device}...")
    model  = SentenceTransformer(EMBEDDING_MODEL, device=device, trust_remote_code=False)
    model.max_seq_length = 512
    client = QdrantClient(url=QDRANT_URL, prefer_grpc=False)
    dim    = EMBEDDING_DIM[EMBEDDING_MODEL]
    _ensure_collection(client, dim)

    pending_points: list[PointStruct] = []
    skipped = done = 0

    for i, doc_path in enumerate(docs, 1):
        stem = doc_path.stem  # e.g. "apple_2023_10k"

        # Load doc
        doc = json.loads(doc_path.read_text(encoding="utf-8"))
        meta     = doc.get("metadata", {})
        company  = doc.get("company",       meta.get("company", ""))
        year     = doc.get("fiscal_year",   meta.get("fiscal_year"))
        dtype    = doc.get("document_type", meta.get("document_type", ""))
        quarter  = doc.get("quarter",       meta.get("quarter"))
        q_part   = f" {quarter}" if quarter else ""
        label    = f"{company} FY{year}{q_part} {dtype}"

        point_id = int(hashlib.sha256(stem.encode()).hexdigest()[:16], 16)

        # Skip if already in Qdrant
        if _already_in_qdrant(client, point_id):
            skipped += 1
            if i % 10 == 0 or i == total:
                print(f"  Progress: {i}/{total}  (skipped={skipped}, done={done})")
            continue

        # Check local checkpoint
        ckpt = _load_checkpoint(stem)
        if ckpt:
            summary = ckpt["summary"]
        else:
            # Build sample text: first 1000 chars per section
            sections = doc.get("sections", {})
            sample_parts = []
            for sec_name, sec_content in sections.items():
                text = sec_content.get("text", "").strip()
                if text:
                    sample_parts.append(f"[{sec_name}] {text[:1000]}")
            sample_text = "\n\n".join(sample_parts)

            try:
                summary = _llm_summarise(label, sample_text)
            except Exception as e:
                print(f"  [WARN] LLM failed for {label}: {e} — using excerpt")
                summary = sample_text[:400]

            _save_checkpoint(stem, {
                "stem":          stem,
                "label":         label,
                "company":       company,
                "fiscal_year":   year,
                "document_type": dtype,
                "quarter":       quarter,
                "summary":       summary,
            })

        # Embed + queue for upsert
        vec = model.encode(summary, normalize_embeddings=True).tolist()
        pending_points.append(PointStruct(
            id=point_id,
            vector=vec,
            payload={
                "stem":          stem,
                "label":         label,
                "company":       company,
                "fiscal_year":   year,
                "document_type": dtype,
                "quarter":       quarter,
                "document_path": stem,  # used by hierarchical_rag to filter chunks
                "summary":       summary,
            },
        ))
        done += 1

        # Flush to Qdrant every 10 docs
        if len(pending_points) >= 10:
            client.upsert(collection_name=SUMMARY_COLLECTION, points=pending_points)
            pending_points.clear()
            print(f"  Summarized {i}/{total}  (skipped={skipped}, done={done})")

    # Final flush
    if pending_points:
        client.upsert(collection_name=SUMMARY_COLLECTION, points=pending_points)

    total_in_collection = client.count(
        collection_name=SUMMARY_COLLECTION, exact=True
    ).count
    print(f"\nDone. {SUMMARY_COLLECTION} now has {total_in_collection} document summaries.")
    print(f"Checkpoints saved to: {CHECKPOINT_DIR}")


if __name__ == "__main__":
    main()
