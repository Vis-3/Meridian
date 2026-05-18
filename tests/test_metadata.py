"""Tests for ingestion/metadata.py — pure Python, no external calls."""

import re
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from ingestion.metadata import parse_filename, resolve_period, build_chunk_metadata

CHUNK_ID_RE = re.compile(r'^[a-z0-9_]+$')   # only lowercase, digits, underscore


# ---------------------------------------------------------------------------
# parse_filename
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,expected", [
    ("apple_2024_10k.pdf",        {"company": "Apple",     "fiscal_year": 2024, "document_type": "10-K", "quarter": None}),
    ("apple_2024_10k.htm",        {"company": "Apple",     "fiscal_year": 2024, "document_type": "10-K", "quarter": None}),
    ("microsoft_2023_q2_10q.htm", {"company": "Microsoft", "fiscal_year": 2023, "document_type": "10-Q", "quarter": "Q2"}),
    ("google_2021_q3_10q.htm",    {"company": "Google",    "fiscal_year": 2021, "document_type": "10-Q", "quarter": "Q3"}),
    ("amazon_2020_10k.htm",       {"company": "Amazon",    "fiscal_year": 2020, "document_type": "10-K", "quarter": None}),
    ("meta_2022_q1_10q.htm",      {"company": "Meta",      "fiscal_year": 2022, "document_type": "10-Q", "quarter": "Q1"}),
])
def test_parse_filename(filename, expected):
    result = parse_filename(filename)
    assert result is not None, f"parse_filename returned None for '{filename}'"
    for key, val in expected.items():
        assert result[key] == val, f"{filename}: {key} expected {val}, got {result[key]}"


def test_parse_filename_invalid_returns_none():
    assert parse_filename("random_file.txt") is None
    assert parse_filename("") is None
    assert parse_filename("unknown_2023_10k.htm") is None


# ---------------------------------------------------------------------------
# resolve_period — Apple fiscal year ends September
# ---------------------------------------------------------------------------

def test_apple_fiscal_year_end_september():
    period = resolve_period("Apple", 2023)
    # Apple FY2023 ends in September 2023
    assert period["period_end_date"].startswith("2023-09"), \
        f"Apple FY2023 should end in Sep 2023, got {period['period_end_date']}"


def test_microsoft_fiscal_year_end_june():
    period = resolve_period("Microsoft", 2023)
    assert period["period_end_date"].startswith("2023-06"), \
        f"Microsoft FY2023 should end in Jun 2023, got {period['period_end_date']}"


def test_google_calendar_year():
    period = resolve_period("Google", 2023)
    assert period["period_end_date"] == "2023-12-31"


def test_resolve_period_returns_required_keys():
    period = resolve_period("Apple", 2023)
    for key in ("fiscal_year", "calendar_year_filed", "period_start_date", "period_end_date"):
        assert key in period, f"resolve_period missing key: {key}"


# ---------------------------------------------------------------------------
# build_chunk_metadata
# ---------------------------------------------------------------------------

FILE_META = {
    "company":             "Apple",
    "fiscal_year":         2023,
    "calendar_year_filed": 2023,
    "document_type":       "10-K",
    "quarter":             None,
    "period_start_date":   "2022-09-29",
    "period_end_date":     "2023-09-28",
}


def test_build_chunk_metadata_required_fields():
    meta = build_chunk_metadata(
        file_meta=FILE_META,
        section="Item 7",
        page_range=[20, 21],
        chunk_index=0,
        document_path="apple_2023_10k.htm",
    )
    required = [
        "chunk_id", "company", "fiscal_year", "document_type",
        "section", "page_range", "document_path", "parent_id",
    ]
    for field in required:
        assert field in meta, f"build_chunk_metadata missing field: {field}"


def test_chunk_id_no_spaces_or_special_chars():
    meta = build_chunk_metadata(
        file_meta=FILE_META,
        section="Item 1A",
        page_range=[5, 6],
        chunk_index=3,
        document_path="apple_2023_10k.htm",
    )
    chunk_id = meta["chunk_id"]
    assert CHUNK_ID_RE.match(chunk_id), \
        f"chunk_id '{chunk_id}' contains invalid characters"


def test_chunk_id_includes_quarter_when_present():
    meta_with_q = {**FILE_META, "quarter": "Q2"}
    meta = build_chunk_metadata(
        file_meta=meta_with_q,
        section="Item 1",
        page_range=[1, 2],
        chunk_index=0,
        document_path="apple_2023_q2_10q.htm",
    )
    assert "q2" in meta["chunk_id"], \
        f"chunk_id should include quarter: {meta['chunk_id']}"


def test_parent_id_is_none_by_default():
    meta = build_chunk_metadata(
        file_meta=FILE_META,
        section="Item 7",
        page_range=[20, 21],
        chunk_index=0,
        document_path="apple_2023_10k.htm",
    )
    assert meta["parent_id"] is None


def test_parent_id_set_when_provided():
    meta = build_chunk_metadata(
        file_meta=FILE_META,
        section="Item 7",
        page_range=[20, 21],
        chunk_index=5,
        document_path="apple_2023_10k.htm",
        parent_id="apple_2023_10k_item7_chunk_0001",
    )
    assert meta["parent_id"] == "apple_2023_10k_item7_chunk_0001"
