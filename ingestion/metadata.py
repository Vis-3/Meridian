"""
Meridian — metadata resolution and chunk metadata builder.

Handles fiscal year offsets:
  Apple     → FY ends September  → FY2024 covers Oct 2023 – Sep 2024
  Microsoft → FY ends June       → FY2024 covers Jul 2023 – Jun 2024
  Others    → calendar year      → FY2024 covers Jan 2024 – Dec 2024

Every chunk carries a standardised metadata dict so retrieval filters
work correctly for temporal and comparative queries.
"""

import re
import uuid
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import COMPANIES, FISCAL_YEAR_END_MONTH

# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------

_FILENAME_RE = re.compile(
    r"^(?P<company>[a-z]+)_(?P<year>\d{4})_(?P<quarter>q\d_)?(?P<doctype>10k|10q)\.(pdf|htm)$",
    re.IGNORECASE,
)

_COMPANY_NORM = {c.lower(): c for c in COMPANIES}


def parse_filename(filename: str) -> Optional[dict]:
    """
    Parse a Meridian-standard filename into its components.

    Examples:
      apple_2024_10k.pdf        → company=Apple, year=2024, doctype=10-K, quarter=None
      microsoft_2023_q2_10q.pdf → company=Microsoft, year=2023, doctype=10-Q, quarter=Q2
    """
    m = _FILENAME_RE.match(filename)
    if not m:
        return None

    company_raw = m.group("company").lower()
    company = _COMPANY_NORM.get(company_raw)
    if company is None:
        return None

    fiscal_year = int(m.group("year"))
    quarter_raw = m.group("quarter")
    quarter = quarter_raw.strip("_").upper() if quarter_raw else None
    doctype = "10-K" if m.group("doctype").lower() == "10k" else "10-Q"

    return {
        "company":       company,
        "fiscal_year":   fiscal_year,
        "document_type": doctype,
        "quarter":       quarter,
    }


# ---------------------------------------------------------------------------
# Fiscal year resolver
# ---------------------------------------------------------------------------

def resolve_period(company: str, fiscal_year: int,
                   quarter: Optional[str] = None) -> dict:
    """
    Returns the exact calendar period a filing covers.

    Returns:
      {
        fiscal_year:          int,
        calendar_year_filed:  int,
        period_start_date:    str,   # ISO-8601
        period_end_date:      str,   # ISO-8601
      }
    """
    end_month = FISCAL_YEAR_END_MONTH[company]

    if end_month == 12:
        # Calendar-year company
        if quarter is None:
            # 10-K: full calendar year
            return {
                "fiscal_year":         fiscal_year,
                "calendar_year_filed": fiscal_year + 1,
                "period_start_date":   f"{fiscal_year}-01-01",
                "period_end_date":     f"{fiscal_year}-12-31",
            }
        else:
            q_num = int(quarter[1])
            q_starts = {1: f"{fiscal_year}-01-01",
                        2: f"{fiscal_year}-04-01",
                        3: f"{fiscal_year}-07-01"}
            q_ends   = {1: f"{fiscal_year}-03-31",
                        2: f"{fiscal_year}-06-30",
                        3: f"{fiscal_year}-09-30"}
            return {
                "fiscal_year":         fiscal_year,
                "calendar_year_filed": fiscal_year,
                "period_start_date":   q_starts[q_num],
                "period_end_date":     q_ends[q_num],
            }

    elif end_month == 9:
        # Apple: FY ends September
        prev = fiscal_year - 1
        if quarter is None:
            return {
                "fiscal_year":         fiscal_year,
                "calendar_year_filed": fiscal_year,
                "period_start_date":   f"{prev}-09-29",   # approx fiscal start
                "period_end_date":     f"{fiscal_year}-09-28",
            }
        else:
            q_num = int(quarter[1])
            q_map = {
                1: (f"{prev}-10-01",      f"{prev}-12-31"),
                2: (f"{fiscal_year}-01-01", f"{fiscal_year}-03-31"),
                3: (f"{fiscal_year}-04-01", f"{fiscal_year}-06-30"),
            }
            start, end = q_map.get(q_num, (f"{fiscal_year}-01-01", f"{fiscal_year}-03-31"))
            return {
                "fiscal_year":         fiscal_year,
                "calendar_year_filed": fiscal_year,
                "period_start_date":   start,
                "period_end_date":     end,
            }

    elif end_month == 6:
        # Microsoft: FY ends June
        prev = fiscal_year - 1
        if quarter is None:
            return {
                "fiscal_year":         fiscal_year,
                "calendar_year_filed": fiscal_year,
                "period_start_date":   f"{prev}-07-01",
                "period_end_date":     f"{fiscal_year}-06-30",
            }
        else:
            q_num = int(quarter[1])
            q_map = {
                1: (f"{prev}-07-01",      f"{prev}-09-30"),
                2: (f"{prev}-10-01",      f"{prev}-12-31"),
                3: (f"{fiscal_year}-01-01", f"{fiscal_year}-03-31"),
            }
            start, end = q_map.get(q_num, (f"{fiscal_year}-01-01", f"{fiscal_year}-03-31"))
            return {
                "fiscal_year":         fiscal_year,
                "calendar_year_filed": fiscal_year,
                "period_start_date":   start,
                "period_end_date":     end,
            }

    # Fallback
    return {
        "fiscal_year":         fiscal_year,
        "calendar_year_filed": fiscal_year,
        "period_start_date":   f"{fiscal_year}-01-01",
        "period_end_date":     f"{fiscal_year}-12-31",
    }


# ---------------------------------------------------------------------------
# File-level metadata builder
# ---------------------------------------------------------------------------

def build_file_metadata(parsed: dict) -> dict:
    """Build the full metadata dict for a document from its parsed filename info."""
    period = resolve_period(
        parsed["company"],
        parsed["fiscal_year"],
        parsed.get("quarter"),
    )
    return {
        "company":             parsed["company"],
        "fiscal_year":         parsed["fiscal_year"],
        "calendar_year_filed": period["calendar_year_filed"],
        "document_type":       parsed["document_type"],
        "quarter":             parsed.get("quarter"),
        "period_start_date":   period["period_start_date"],
        "period_end_date":     period["period_end_date"],
    }


# ---------------------------------------------------------------------------
# Chunk metadata builder
# ---------------------------------------------------------------------------

def build_chunk_metadata(
    file_meta: dict,
    section: str,
    page_range: list[int],
    chunk_index: int,
    document_path: str,
    parent_id: Optional[str] = None,
) -> dict:
    """
    Build the per-chunk metadata dict.
    Every chunk in every retriever carries this exact schema.
    """
    quarter_part = f"_{file_meta['quarter'].lower()}" if file_meta.get('quarter') else ""
    chunk_id = (
        f"{file_meta['company'].lower()}_"
        f"{file_meta['fiscal_year']}"
        f"{quarter_part}_"
        f"{file_meta['document_type'].replace('-', '').lower()}_"
        f"{section.replace(' ', '').lower()}_"
        f"chunk_{chunk_index:04d}"
    )

    return {
        "chunk_id":            chunk_id,
        "parent_id":           parent_id,
        "company":             file_meta["company"],
        "fiscal_year":         file_meta["fiscal_year"],
        "calendar_year_filed": file_meta["calendar_year_filed"],
        "document_type":       file_meta["document_type"],
        "quarter":             file_meta.get("quarter"),
        "period_start_date":   file_meta["period_start_date"],
        "period_end_date":     file_meta["period_end_date"],
        "section":             section,
        "page_range":          page_range,
        "document_path":       document_path,
    }
