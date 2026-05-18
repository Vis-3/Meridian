"""
Semantic chunking — split where cosine similarity between adjacent sentences drops below threshold.

Strategy: embed each sentence, compute similarity between consecutive pairs,
split at similarity valleys. Produces chunks that are semantically coherent
rather than arbitrarily sized.

Strength: chunks never split mid-argument.
Weakness: slower (requires embedding every sentence), can produce very uneven chunk sizes.
"""

from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import EMBEDDING_MODEL_FAST, SEMANTIC_THRESHOLD
from ingestion.metadata import build_chunk_metadata

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # Use fast model for chunking — quality model reserved for retrieval
        _model = SentenceTransformer(EMBEDDING_MODEL_FAST)
    return _model


def _split_sentences(text: str) -> list[str]:
    """Naive sentence splitter — avoids pulling in spaCy just for this."""
    import re
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def chunk_text(
    text: str,
    file_meta: dict,
    section: str,
    page_range: list[int],
    document_path: str,
    threshold: float = SEMANTIC_THRESHOLD,
) -> list[dict]:
    """
    Split text into semantically coherent chunks.

    A new chunk begins when cosine similarity between adjacent sentences
    drops below `threshold`.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return []

    model = _get_model()
    embeddings = model.encode(sentences, show_progress_bar=False,
                              convert_to_numpy=True)

    # Identify split points
    boundaries = [0]
    for i in range(1, len(sentences)):
        sim = _cosine(embeddings[i - 1], embeddings[i])
        if sim < threshold:
            boundaries.append(i)
    boundaries.append(len(sentences))

    chunks = []
    for idx, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
        chunk_sentences = sentences[start:end]
        chunk_text_str  = " ".join(chunk_sentences)

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
