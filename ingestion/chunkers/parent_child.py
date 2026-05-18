"""
Parent-child chunking.

Child chunks (256 tokens) are indexed and retrieved — small = more precise retrieval.
Parent chunks (1024 tokens) are returned to the LLM — large = more context for generation.

This is a key insight: retrieval precision and generation context are competing goals.
Smaller chunks score better in retrieval; larger chunks give the LLM more context.
Parent-child solves both simultaneously.

Flow:
  1. Split text into parent chunks (1024 tokens).
  2. For each parent, split further into child chunks (256 tokens).
  3. Each child carries a parent_id linking back to its parent.
  4. Retrieval finds children; response uses parent text.
"""

from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PARENT_CHUNK_SIZE, CHILD_CHUNK_SIZE, FIXED_OVERLAP
from ingestion.metadata import build_chunk_metadata


def _token_split(text: str, size: int, overlap: int) -> list[str]:
    tokens = text.split()
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + size, len(tokens))
        chunks.append(" ".join(tokens[start:end]))
        if end == len(tokens):
            break
        start += size - overlap
    return chunks


def chunk_text(
    text: str,
    file_meta: dict,
    section: str,
    page_range: list[int],
    document_path: str,
    parent_size: int = PARENT_CHUNK_SIZE,
    child_size: int = CHILD_CHUNK_SIZE,
    overlap: int = FIXED_OVERLAP,
) -> tuple[list[dict], list[dict]]:
    """
    Returns (parents, children).

    Parents: large chunks with full context.
    Children: small chunks with parent_id; these get embedded and stored in Qdrant.
    """
    parent_texts = _token_split(text, parent_size, overlap)
    parents, children = [], []

    for p_idx, p_text in enumerate(parent_texts):
        parent_meta = build_chunk_metadata(
            file_meta=file_meta,
            section=section,
            page_range=page_range,
            chunk_index=p_idx,
            document_path=document_path,
        )
        parent_id = parent_meta["chunk_id"]
        parents.append({"text": p_text, "metadata": parent_meta})

        child_texts = _token_split(p_text, child_size, overlap // 2)
        for c_idx, c_text in enumerate(child_texts):
            child_meta = build_chunk_metadata(
                file_meta=file_meta,
                section=section,
                page_range=page_range,
                chunk_index=p_idx * 1000 + c_idx,  # unique index
                document_path=document_path,
                parent_id=parent_id,
            )
            children.append({"text": c_text, "metadata": child_meta})

    return parents, children


def chunk_document(extracted_doc: dict) -> tuple[list[dict], list[dict]]:
    """Returns (all_parents, all_children) across all sections."""
    file_meta = extracted_doc["metadata"]
    doc_path  = extracted_doc["source_filename"]
    all_parents, all_children = [], []

    for section, content in extracted_doc["sections"].items():
        text  = content.get("text", "").strip()
        pages = content.get("pages", [])
        if not text:
            continue
        parents, children = chunk_text(
            text=text,
            file_meta=file_meta,
            section=section,
            page_range=pages,
            document_path=doc_path,
        )
        all_parents.extend(parents)
        all_children.extend(children)

    return all_parents, all_children
