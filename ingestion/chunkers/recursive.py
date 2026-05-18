"""
Recursive character splitting.

Tries separators in order: paragraph break → newline → sentence end → space → character.
Falls back to the next separator only if the current split produces chunks
larger than the target size. Preserves logical structure better than fixed chunking.

Strength: respects paragraph and sentence boundaries when possible.
Weakness: chunk sizes still vary, overlap is approximate.
"""

from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import FIXED_CHUNK_SIZE, FIXED_OVERLAP, RECURSIVE_SEPARATORS
from ingestion.metadata import build_chunk_metadata


def _split_with_separator(text: str, separator: str) -> list[str]:
    if separator:
        parts = text.split(separator)
    else:
        parts = list(text)
    return [p for p in parts if p.strip()]


def _merge_splits(splits: list[str], chunk_size: int,
                  overlap: int, separator: str) -> list[str]:
    """
    Merge short splits into target-size chunks with overlap.
    Measures size in characters (×5 ≈ tokens for English).
    """
    char_limit = chunk_size * 5
    overlap_chars = overlap * 5

    chunks = []
    current = ""

    for split in splits:
        candidate = (current + separator + split).strip() if current else split
        if len(candidate) <= char_limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
                # Start next chunk with overlap from end of current
                overlap_text = current[-overlap_chars:] if len(current) > overlap_chars else current
                current = (overlap_text + separator + split).strip()
            else:
                # Single split is already too large — keep it as-is
                chunks.append(split)
                current = ""

    if current:
        chunks.append(current)

    return chunks


def _recursive_split(text: str, separators: list[str],
                     chunk_size: int, overlap: int) -> list[str]:
    char_limit = chunk_size * 5

    if len(text) <= char_limit or not separators:
        return [text] if text.strip() else []

    sep = separators[0]
    remaining = separators[1:]

    splits = _split_with_separator(text, sep)
    good, too_large = [], []

    for s in splits:
        if len(s) <= char_limit:
            good.append(s)
        else:
            # Recurse into too-large splits with the next separator
            good.extend(_recursive_split(s, remaining, chunk_size, overlap))

    return _merge_splits(good, chunk_size, overlap, sep)


def chunk_text(
    text: str,
    file_meta: dict,
    section: str,
    page_range: list[int],
    document_path: str,
    chunk_size: int = FIXED_CHUNK_SIZE,
    overlap: int = FIXED_OVERLAP,
    separators: list[str] = RECURSIVE_SEPARATORS,
) -> list[dict]:
    raw_chunks = _recursive_split(text, separators, chunk_size, overlap)
    chunks = []
    for idx, chunk_text_str in enumerate(raw_chunks):
        meta = build_chunk_metadata(
            file_meta=file_meta,
            section=section,
            page_range=page_range,
            chunk_index=idx,
            document_path=document_path,
        )
        chunks.append({"text": chunk_text_str, "metadata": meta})
    return chunks


def chunk_document(extracted_doc: dict) -> list[dict]:
    file_meta = extracted_doc["metadata"]
    doc_path  = extracted_doc["source_filename"]
    all_chunks = []

    for section, content in extracted_doc["sections"].items():
        text  = content.get("text", "").strip()
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
