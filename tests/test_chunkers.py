"""Tests for ingestion/chunkers — no LLM, no disk I/O beyond imports."""

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from config import FIXED_CHUNK_SIZE, CHILD_CHUNK_SIZE, PARENT_CHUNK_SIZE

# Shared sample data
SAMPLE_TEXT = " ".join([f"word{i}" for i in range(2000)])  # 2000 whitespace tokens

SAMPLE_FILE_META = {
    "company":             "Apple",
    "fiscal_year":         2023,
    "calendar_year_filed": 2023,
    "document_type":       "10-K",
    "quarter":             None,
    "period_start_date":   "2022-09-29",
    "period_end_date":     "2023-09-28",
}

SAMPLE_SECTION   = "Item 7"
SAMPLE_PAGES     = [20, 21]
SAMPLE_DOC_PATH  = "apple_2023_10k.htm"

REQUIRED_META_FIELDS = [
    "chunk_id", "company", "fiscal_year", "section",
    "document_type", "page_range", "document_path",
]


# ---------------------------------------------------------------------------
# Fixed chunker
# ---------------------------------------------------------------------------

def test_fixed_chunk_size_within_limit():
    from ingestion.chunkers.fixed import chunk_text
    chunks = chunk_text(SAMPLE_TEXT, SAMPLE_FILE_META, SAMPLE_SECTION,
                        SAMPLE_PAGES, SAMPLE_DOC_PATH)
    for c in chunks:
        token_count = len(c["text"].split())
        assert token_count <= FIXED_CHUNK_SIZE + 10, \
            f"Fixed chunk too large: {token_count} tokens"


def test_fixed_chunk_metadata_fields():
    from ingestion.chunkers.fixed import chunk_text
    chunks = chunk_text(SAMPLE_TEXT, SAMPLE_FILE_META, SAMPLE_SECTION,
                        SAMPLE_PAGES, SAMPLE_DOC_PATH)
    assert len(chunks) > 0
    for c in chunks:
        meta = c["metadata"]
        for field in REQUIRED_META_FIELDS:
            assert field in meta, f"Fixed chunk missing metadata field: {field}"


def test_fixed_chunk_returns_list_of_dicts():
    from ingestion.chunkers.fixed import chunk_text
    chunks = chunk_text(SAMPLE_TEXT, SAMPLE_FILE_META, SAMPLE_SECTION,
                        SAMPLE_PAGES, SAMPLE_DOC_PATH)
    assert isinstance(chunks, list)
    assert all(isinstance(c, dict) for c in chunks)
    assert all("text" in c and "metadata" in c for c in chunks)


def test_fixed_chunk_ids_are_unique():
    from ingestion.chunkers.fixed import chunk_text
    chunks = chunk_text(SAMPLE_TEXT, SAMPLE_FILE_META, SAMPLE_SECTION,
                        SAMPLE_PAGES, SAMPLE_DOC_PATH)
    ids = [c["metadata"]["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids)), "Duplicate chunk IDs in fixed chunker"


# ---------------------------------------------------------------------------
# Recursive chunker
# ---------------------------------------------------------------------------

def test_recursive_chunk_schema():
    from ingestion.chunkers.recursive import chunk_text
    chunks = chunk_text(SAMPLE_TEXT, SAMPLE_FILE_META, SAMPLE_SECTION,
                        SAMPLE_PAGES, SAMPLE_DOC_PATH)
    assert isinstance(chunks, list)
    assert len(chunks) > 0
    for c in chunks:
        assert "text" in c
        assert "metadata" in c
        meta = c["metadata"]
        for field in REQUIRED_META_FIELDS:
            assert field in meta, f"Recursive chunk missing field: {field}"


# ---------------------------------------------------------------------------
# Parent-child chunker
# ---------------------------------------------------------------------------

def test_parent_child_returns_tuple():
    from ingestion.chunkers.parent_child import chunk_text
    result = chunk_text(SAMPLE_TEXT, SAMPLE_FILE_META, SAMPLE_SECTION,
                        SAMPLE_PAGES, SAMPLE_DOC_PATH)
    assert isinstance(result, tuple)
    parents, children = result
    assert isinstance(parents, list)
    assert isinstance(children, list)


def test_parent_child_children_have_parent_id():
    from ingestion.chunkers.parent_child import chunk_text
    parents, children = chunk_text(SAMPLE_TEXT, SAMPLE_FILE_META, SAMPLE_SECTION,
                                   SAMPLE_PAGES, SAMPLE_DOC_PATH)
    assert len(children) > 0
    for child in children:
        assert child["metadata"]["parent_id"] is not None, \
            "Every child chunk must have a parent_id"


def test_parent_child_parent_ids_exist_in_parents():
    from ingestion.chunkers.parent_child import chunk_text
    parents, children = chunk_text(SAMPLE_TEXT, SAMPLE_FILE_META, SAMPLE_SECTION,
                                   SAMPLE_PAGES, SAMPLE_DOC_PATH)
    parent_ids = {p["metadata"]["chunk_id"] for p in parents}
    for child in children:
        pid = child["metadata"]["parent_id"]
        assert pid in parent_ids, \
            f"Child parent_id '{pid}' not found in parents list"


def test_parent_child_child_size_within_limit():
    from ingestion.chunkers.parent_child import chunk_text
    _, children = chunk_text(SAMPLE_TEXT, SAMPLE_FILE_META, SAMPLE_SECTION,
                             SAMPLE_PAGES, SAMPLE_DOC_PATH)
    for child in children:
        token_count = len(child["text"].split())
        assert token_count <= CHILD_CHUNK_SIZE + 10, \
            f"Child chunk too large: {token_count} tokens"


def test_parent_child_parent_size_within_limit():
    from ingestion.chunkers.parent_child import chunk_text
    parents, _ = chunk_text(SAMPLE_TEXT, SAMPLE_FILE_META, SAMPLE_SECTION,
                            SAMPLE_PAGES, SAMPLE_DOC_PATH)
    for parent in parents:
        token_count = len(parent["text"].split())
        assert token_count <= PARENT_CHUNK_SIZE + 10, \
            f"Parent chunk too large: {token_count} tokens"
