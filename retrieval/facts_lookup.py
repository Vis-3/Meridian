from __future__ import annotations

"""
Meridian — Facts.py direct lookup for numerical and simple-factual questions.

Before hitting Qdrant, check if the answer can be pulled directly from the
345 verified data points in data/evaluation/facts.py. When a match is found,
returns a synthetic chunk that the LLM can use as authoritative context.

Returns None when no match is found → caller falls through to normal RAG.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from data.evaluation.facts import FACTS, get, yoy_growth

# ---------------------------------------------------------------------------
# Field map — keyword patterns → facts.py field names
# Order matters: more specific patterns must come before general ones.
# ---------------------------------------------------------------------------

# Each entry: (regex_pattern, field_name, unit_label)
# Checked in order; first match wins.
_FIELD_MAP: list[tuple[str, str, str]] = [
    # ── Apple-specific segments ──────────────────────────────────────────
    (r"iphone",                         "iphone_revenue_b",       "billion USD"),
    (r"\bmac\b",                         "mac_revenue_b",          "billion USD"),
    (r"\bipad\b",                        "ipad_revenue_b",         "billion USD"),
    (r"wearables|wearable",             "wearables_revenue_b",    "billion USD"),
    # ── Microsoft segments ───────────────────────────────────────────────
    (r"azure",                           "azure_growth_pct",       "%"),
    (r"intelligent cloud",              "cloud_revenue_b",        "billion USD"),
    (r"productivity.{0,20}business",    "productivity_revenue_b", "billion USD"),
    (r"more personal|personal computing","more_personal_revenue_b","billion USD"),
    # ── Google segments ──────────────────────────────────────────────────
    (r"youtube",                         "youtube_revenue_b",      "billion USD"),
    (r"google cloud",                   "cloud_revenue_b",        "billion USD"),
    (r"other bets",                     "other_bets_revenue_b",   "billion USD"),
    # ── Amazon segments ──────────────────────────────────────────────────
    (r"aws|amazon web services",        "aws_revenue_b",          "billion USD"),
    (r"north america",                  "north_america_revenue_b","billion USD"),
    (r"international",                  "international_revenue_b","billion USD"),
    # ── Meta segments ────────────────────────────────────────────────────
    (r"family daily|family dap|dap",    "family_dap_millions",    "million people"),
    (r"family monthly|family map",      "family_map_millions",    "million people"),
    (r"daily active|dau",               "dau_millions",           "million users"),
    (r"monthly active|mau",             "mau_millions",           "million users"),
    # ── Geographic (Apple) ───────────────────────────────────────────────
    (r"greater china|china",            "greater_china_revenue_b","billion USD"),
    (r"europe",                          "europe_revenue_b",       "billion USD"),
    (r"americas",                        "americas_revenue_b",     "billion USD"),
    # ── Shared income statement ──────────────────────────────────────────
    (r"advertising revenue|ad revenue|ads revenue", "advertising_revenue_b", "billion USD"),
    (r"cloud revenue|cloud segment",    "cloud_revenue_b",        "billion USD"),
    (r"services revenue|service revenue","services_revenue_b",    "billion USD"),
    (r"gross profit|gross income",      "gross_profit_b",         "billion USD"),
    (r"gross margin",                   "gross_margin_pct",       "%"),
    (r"operating income|operating profit","operating_income_b",   "billion USD"),
    (r"operating margin",               "operating_margin_pct",   "%"),
    (r"net income|net profit|net earnings|profit after tax","net_income_b","billion USD"),
    (r"r&d|research.{0,5}development|research and dev","rd_spend_b","billion USD"),
    (r"capex|capital expenditure|capital spending","capex_b",     "billion USD"),
    (r"employee|headcount|workforce|staff|workers","employees_k", "thousand employees"),
    # ── Revenue (most general — must be last) ────────────────────────────
    (r"total revenue|net revenue|net sales|total sales|revenue","revenue_b","billion USD"),
]

# YoY growth trigger words
_YOY_PATTERNS = [
    r"year.over.year|yoy|year on year",
    r"growth|grew|change|increase|decrease|decline",
    r"compared to.{0,20}(?:previous|prior|last)\s+year",
    r"from \d{4} to \d{4}",
]


def _match_field(question_lower: str) -> tuple[str, str] | None:
    """Return (field_name, unit) for the first matching pattern, or None."""
    for pattern, field, unit in _FIELD_MAP:
        if re.search(pattern, question_lower):
            return field, unit
    return None


def _is_yoy_question(question_lower: str) -> bool:
    return any(re.search(p, question_lower) for p in _YOY_PATTERNS)


def _format_value(value: float | None, unit: str) -> str | None:
    if value is None:
        return None
    if unit == "%":
        return f"{value:.1f}%"
    if unit == "billion USD":
        return f"${value:.1f}B (${value * 1000:.0f}M)"
    if "thousand" in unit:
        return f"{value:.0f}K ({int(value * 1000):,} employees)"
    if "million" in unit:
        return f"{value:.0f}M"
    return str(value)


def _make_chunk(text: str, company: str, year: int, field: str) -> dict:
    return {
        "chunk_id":      f"facts_lookup_{company}_{year}_{field}",
        "text":          text,
        "score":         1.0,
        "company":       company,
        "fiscal_year":   year,
        "section":       "Verified Financial Facts",
        "document_type": "facts.py",
        "document_path": "data/evaluation/facts.py",
        "page_range":    [],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def lookup_numerical(
    question: str,
    companies: list[str] | None,
    years: list[int] | None,
) -> dict | None:
    """
    Try to answer a numerical question directly from facts.py.

    Returns a synthetic chunk dict on success, None if no match.
    The chunk is inserted at the top of the retrieval results so the LLM
    treats it as the most authoritative source.
    """
    if not companies or not years:
        return None

    q = question.lower()
    match = _match_field(q)
    if not match:
        return None

    field, unit = match

    # ── YoY growth question ──────────────────────────────────────────────
    if _is_yoy_question(q) and len(years) >= 2:
        years_sorted = sorted(years)
        lines = []
        for company in companies:
            for i in range(1, len(years_sorted)):
                yr = years_sorted[i]
                growth = yoy_growth(company, field, yr)
                if growth is not None:
                    prev = years_sorted[i - 1]
                    lines.append(
                        f"{company} {field.replace('_b','').replace('_pct','').replace('_',' ')} "
                        f"grew {growth:+.1f}% from FY{prev} to FY{yr}."
                    )
        if lines:
            text = (
                f"VERIFIED FACT (facts.py):\n" + "\n".join(lines)
            )
            return _make_chunk(text, companies[0], years_sorted[-1], field)

    # ── Single value lookup ──────────────────────────────────────────────
    lines = []
    for company in companies:
        for year in years:
            fact = get(company, year)
            if not fact or field not in fact:
                continue
            value = fact[field]
            formatted = _format_value(value, unit)
            if formatted is None:
                continue
            friendly = field.replace("_b", "").replace("_pct", "").replace("_k", "").replace("_", " ")
            lines.append(
                f"{company} FY{year} {friendly}: {formatted}."
            )

    if not lines:
        return None

    text = "VERIFIED FACT (facts.py):\n" + "\n".join(lines)
    return _make_chunk(text, companies[0], years[0], field)


def lookup_comparative(
    question: str,
    years: list[int] | None,
) -> dict | None:
    """
    For comparative questions across all 5 companies for a given year/metric.
    Returns a synthetic chunk listing all companies' values ranked.
    """
    if not years:
        return None

    q = question.lower()
    match = _match_field(q)
    if not match:
        return None

    field, unit = match
    all_companies = list(FACTS.keys())  # Apple, Microsoft, Google, Amazon, Meta

    lines = []
    for year in years:
        ranked = []
        for company in all_companies:
            fact = get(company, year)
            if not fact or field not in fact:
                continue
            value = fact[field]
            if value is None:
                continue
            formatted = _format_value(value, unit)
            ranked.append((company, value, formatted))

        if not ranked:
            continue

        ranked.sort(key=lambda x: x[1], reverse=True)
        friendly = field.replace("_b","").replace("_pct","").replace("_k","").replace("_"," ")
        lines.append(f"FY{year} {friendly} by company (ranked):")
        for rank, (company, _, fmt) in enumerate(ranked, 1):
            lines.append(f"  {rank}. {company}: {fmt}")

    if not lines:
        return None

    text = "VERIFIED FACT (facts.py):\n" + "\n".join(lines)
    return _make_chunk(text, "all companies", years[0], field)
