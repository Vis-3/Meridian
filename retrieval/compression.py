from __future__ import annotations

"""
Meridian — Context compression for numerical and factual questions.

Filters retrieved chunk text to sentences most likely to contain the answer,
reducing LLM context noise without making any API calls.

Strategy by question type:
  numerical_reasoning  — keep sentences containing numbers, $, %, or financial keywords
  simple_factual       — keep sentences containing numbers or the query's key nouns
  all others           — return chunks unchanged
"""

import re
from typing import Literal

# Sentences shorter than this after stripping are dropped
_MIN_SENTENCE_LEN = 15

# Financial keywords that signal a sentence is worth keeping
_FINANCIAL_TRIGGERS = re.compile(
    r"""
    \$                          # dollar sign
    | \d+\.?\d*\s*[BMKbmk](?:illion|n)? # number + scale suffix
    | \d+\.?\d*\s*%             # percentage
    | \b(?:
        revenue | income | profit | loss | margin | sales | expense |
        earnings | cost | spend | capex | cash | debt | equity |
        billion | million | thousand | fiscal | quarter | annual |
        grew | declined | increased | decreased | rose | fell |
        employees | headcount | workforce
      )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _split_sentences(text: str) -> list[str]:
    """Split on sentence boundaries, preserving decimal numbers."""
    # Don't split on decimals (e.g. "$41.2B") or abbreviations
    parts = re.split(r'(?<=[^0-9A-Z])[.!?]\s+(?=[A-Z\$\d])', text)
    return [p.strip() for p in parts if len(p.strip()) >= _MIN_SENTENCE_LEN]


def compress_chunk(chunk: dict, question_type: str, question: str = "") -> dict:
    """
    Return a copy of chunk with text filtered to relevant sentences.
    Returns the original chunk unchanged if compression yields nothing useful.
    """
    if question_type not in ("numerical_reasoning", "simple_factual"):
        return chunk

    text = chunk.get("text", "")
    if not text:
        return chunk

    sentences = _split_sentences(text)
    if not sentences:
        return chunk

    # Keep sentences that contain financial signals
    kept = [s for s in sentences if _FINANCIAL_TRIGGERS.search(s)]

    # Fallback: if compression removed everything, keep original
    if not kept:
        return chunk

    # If compression keeps >90% of the text it added no value — skip
    compressed_text = " ".join(kept)
    if len(compressed_text) >= 0.9 * len(text):
        return chunk

    result = dict(chunk)
    result["text"] = compressed_text
    result["_compressed"] = True
    return result


def compress_chunks(
    chunks: list[dict],
    question_type: str,
    question: str = "",
) -> list[dict]:
    """
    Apply per-chunk compression and return the filtered list.
    Chunks from facts_lookup (score=1.0, section='Verified Financial Facts')
    are never compressed.
    """
    out = []
    for c in chunks:
        if c.get("section") == "Verified Financial Facts":
            out.append(c)
        else:
            out.append(compress_chunk(c, question_type, question))
    return out
