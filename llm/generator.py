"""
Meridian — LLM answer generator.

Takes a query + retrieved chunks → calls Ollama → returns a structured
response dict with answer, citations, token counts, and latency.

The prompt is designed for financial document Q&A:
- Instructs the model to answer only from provided context
- Asks for specific citations (company, year, section)
- Refuses to speculate beyond the evidence
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
    OLLAMA_BASE_URL, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS,
    COST_PER_1K_INPUT_TOKENS, COST_PER_1K_OUTPUT_TOKENS,
    USE_GROQ, USE_GEMINI,
)
from llm.prompts import GENERATION_SYSTEM as _SYSTEM_PROMPT, GENERATION_USER_TEMPLATE as _USER_TEMPLATE

log = logging.getLogger(__name__)


def _format_context(chunks: list[dict], max_chunks: int = 5) -> str:
    """Format retrieved chunks into a numbered context block."""
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
    model: str = LLM_MODEL,
    temperature: float = LLM_TEMPERATURE,
    max_tokens: int = LLM_MAX_TOKENS,
    system_prompt: str | None = None,
) -> dict:
    if USE_GROQ:
        from llm.groq_client import generate as groq_generate
        return groq_generate(query, chunks, temperature=temperature, max_tokens=max_tokens, system_prompt=system_prompt)
    if USE_GEMINI:
        from llm.gemini_client import generate as gemini_generate
        return gemini_generate(query, chunks, temperature=temperature, max_tokens=max_tokens, system_prompt=system_prompt)
    """
    Generate an answer for `query` grounded in `chunks`.

    Returns:
      {
        "answer":             str,
        "citations":          list[dict],   # the chunks used as context
        "tokens_used":        int,
        "estimated_cost_usd": float,
        "latency_ms":         float,
        "model":              str,
        "architecture_name":  str,          # filled in by architecture layer
      }
    """
    t0 = time.perf_counter()

    context  = _format_context(chunks)
    user_msg = _USER_TEMPLATE.format(context=context, question=query)

    payload = {
        "model":   model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log.error(f"Ollama request failed: {e}")
        return {
            "answer":             f"[LLM ERROR] {e}",
            "citations":          chunks,
            "tokens_used":        0,
            "estimated_cost_usd": 0.0,
            "latency_ms":         round((time.perf_counter() - t0) * 1000, 1),
            "model":              model,
            "architecture_name":  "unknown",
        }

    answer = data.get("message", {}).get("content", "").strip()

    # Ollama reports prompt_eval_count + eval_count for token usage
    prompt_tokens = data.get("prompt_eval_count", 0)
    output_tokens = data.get("eval_count", 0)
    total_tokens  = prompt_tokens + output_tokens
    cost = (prompt_tokens / 1000 * COST_PER_1K_INPUT_TOKENS +
            output_tokens / 1000 * COST_PER_1K_OUTPUT_TOKENS)

    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "answer":             answer,
        "citations":          chunks,
        "tokens_used":        total_tokens,
        "estimated_cost_usd": round(cost, 6),
        "latency_ms":         latency_ms,
        "model":              model,
        "architecture_name":  "unknown",
    }
