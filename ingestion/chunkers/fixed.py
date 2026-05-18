"""
Fixed-size chunking — 512 tokens, 50-token overlap.

Simplest strategy: split text into equal-size windows.
Used by the naive (Level 0) architecture as the baseline.
Weakness: may split mid-sentence, mid-table, or mid-paragraph.
"""

from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import FIXED_CHUNK_SIZE, FIXED_OVERLAP
from ingestion.metadata import build_chunk_metadata


def _tokenize(text: str) -> list[str]:
    """Whitespace tokenisation — fast, no model needed."""
    return text.split()


def _detokenize(tokens: list[str]) -> str:
    return " ".join(tokens)


def chunk_text(
    text: str,
    file_meta: dict,
    section: str,
    page_range: list[int],
    document_path: str,
    chunk_size: int = FIXED_CHUNK_SIZE,
    overlap: int = FIXED_OVERLAP,
) -> list[dict]:
    """
    Split text into fixed-size token windows with overlap.

    Returns a list of chunk dicts:
      { "text": str, "metadata": dict }
    """
    tokens = _tokenize(text)
    if not tokens:
        return []

    chunks = []
    start = 0
    idx = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text_str = _detokenize(chunk_tokens)

        meta = build_chunk_metadata(
            file_meta=file_meta,
            section=section,
            page_range=page_range,
            chunk_index=idx,
            document_path=document_path,
        )

        chunks.append({"text": chunk_text_str, "metadata": meta})
        idx += 1

        if end == len(tokens):
            break
        start += chunk_size - overlap

    return chunks


def chunk_document(extracted_doc: dict) -> list[dict]:
    """Chunk all sections of an extracted document."""
    file_meta = extracted_doc["metadata"]
    doc_path  = extracted_doc["source_filename"]
    all_chunks = []

    for section, content in extracted_doc["sections"].items():
        text = content.get("text", "").strip()
        pages = content.get("pages", [])
        if not text:
            continue
        chunks = chunk_text(
            text=text,
            file_meta=file_meta,
            section=section,
            page_range=pages,
            document_path=doc_path,
        )
        all_chunks.extend(chunks)

    return all_chunks
