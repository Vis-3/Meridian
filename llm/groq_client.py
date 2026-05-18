"""
Meridian -- Groq inference client.

Drop-in replacement for llm/generator.py when DEPLOYMENT=oracle.
Uses Groq's OpenAI-compatible API with llama-3.1-8b-instant by default.
Interface is identical to llm.generator.generate().
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL,
    LLM_TEMPERATURE, LLM_MAX_TOKENS,
    COST_PER_1K_INPUT_TOKENS, COST_PER_1K_OUTPUT_TOKENS,
)

log = logging.getLogger(__name__)

# Groq pricing is ~$0.05/1M tokens for llama-3.1-8b — close enough to local estimate
_GROQ_COST_IN  = 0.00005   # $/1K input tokens
_GROQ_COST_OUT = 0.00008   # $/1K output tokens

_SYSTEM_PROMPT = """You are a financial analyst assistant with access to SEC filings \
(10-K annual reports and 10-Q quarterly reports) from Apple, Microsoft, Google, Amazon, and Meta.

Rules:
1. Answer ONLY using the provided context passages. Do not use prior knowledge.
2. If the context does not contain enough information, say so explicitly.
3. For numerical claims, quote the exact figure from the context.
4. Keep answers concise and factual."""

_USER_TEMPLATE = """Context passages:
{context}

Question: {question}

Answer based strictly on the context above. If relevant, cite the company, fiscal year, and section."""


def _format_context(chunks: list[dict], max_chunks: int = 5) -> str:
    lines = []
    for i, chunk in enumerate(chunks[:max_chunks], 1):
        company = chunk.get("company", "")
        year    = chunk.get("fiscal_year", "")
        section = chunk.get("section", "")
        text    = chunk.get("text", "").strip()[:800]
        lines.append(f"[{i}] {company} FY{year} {section}:\n{text}")
    return "\n\n".join(lines)


def generate(
    query: str,
    chunks: list[dict],
    model: str = GROQ_MODEL,
    temperature: float = LLM_TEMPERATURE,
    max_tokens: int = LLM_MAX_TOKENS,
) -> dict:
    """Generate an answer via Groq API. Same return schema as llm.generator.generate()."""
    if not GROQ_API_KEY:
        log.error("GROQ_API_KEY not set — cannot use oracle mode")
        return {
            "answer":             "[ERROR] GROQ_API_KEY not configured",
            "citations":          chunks,
            "tokens_used":        0,
            "estimated_cost_usd": 0.0,
            "latency_ms":         0.0,
            "model":              model,
            "architecture_name":  "unknown",
        }

    t0 = time.perf_counter()

    context  = _format_context(chunks)
    user_msg = _USER_TEMPLATE.format(context=context, question=query)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        "temperature": temperature,
        "max_tokens":  max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }

    try:
        resp = requests.post(
            f"{GROQ_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log.error("Groq request failed: %s", e)
        return {
            "answer":             f"[LLM ERROR] {e}",
            "citations":          chunks,
            "tokens_used":        0,
            "estimated_cost_usd": 0.0,
            "latency_ms":         round((time.perf_counter() - t0) * 1000, 1),
            "model":              model,
            "architecture_name":  "unknown",
        }

    answer         = data["choices"][0]["message"]["content"].strip()
    prompt_tokens  = data.get("usage", {}).get("prompt_tokens", 0)
    output_tokens  = data.get("usage", {}).get("completion_tokens", 0)
    total_tokens   = prompt_tokens + output_tokens
    cost           = (prompt_tokens / 1000 * _GROQ_COST_IN +
                      output_tokens / 1000 * _GROQ_COST_OUT)

    return {
        "answer":             answer,
        "citations":          chunks,
        "tokens_used":        total_tokens,
        "estimated_cost_usd": round(cost, 6),
        "latency_ms":         round((time.perf_counter() - t0) * 1000, 1),
        "model":              model,
        "architecture_name":  "unknown",
    }
