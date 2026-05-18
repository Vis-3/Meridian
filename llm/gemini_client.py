"""
Meridian — Gemini generation client (google-genai SDK).

Drop-in replacement for llm/generator.py when DEPLOYMENT=gemini.
Interface is identical to llm.generator.generate() and llm.groq_client.generate().

Also exposes async batch generation used by scripts/run_batch_evaluation.py.
"""

from __future__ import annotations

import asyncio
import logging
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
)

log = logging.getLogger(__name__)

_COST_IN_PER_1M  = 0.075   # $/1M input tokens  (Gemini Flash 2.0)
_COST_OUT_PER_1M = 0.300   # $/1M output tokens

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


def _make_client():
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


def _make_config():
    from google.genai import types
    return types.GenerateContentConfig(
        system_instruction=_SYSTEM_PROMPT,
        temperature=LLM_TEMPERATURE,
        max_output_tokens=LLM_MAX_TOKENS,
    )


# ---------------------------------------------------------------------------
# Sync generate — called by architecture.generate() via llm/generator.py
# ---------------------------------------------------------------------------

def generate(
    query: str,
    chunks: list[dict],
    system_prompt: str | None = None,
    **_,
) -> dict:
    """Synchronous Gemini generation. Same return schema as llm.generator.generate()."""
    if not GEMINI_API_KEY:
        return _error_response(chunks, "[ERROR] GEMINI_API_KEY not configured", 0.0)

    t0      = time.perf_counter()
    context = _format_context(chunks)
    prompt  = _USER_TEMPLATE.format(context=context, question=query)

    from google.genai import types
    config = types.GenerateContentConfig(
        system_instruction=system_prompt or _SYSTEM_PROMPT,
        temperature=LLM_TEMPERATURE,
        max_output_tokens=LLM_MAX_TOKENS,
    )

    try:
        client   = _make_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
        answer  = response.text.strip()
        usage   = response.usage_metadata
        in_tok  = getattr(usage, "prompt_token_count", 0) or 0
        out_tok = getattr(usage, "candidates_token_count", 0) or 0
    except Exception as e:
        log.error("Gemini request failed: %s", e)
        return _error_response(chunks, f"[LLM ERROR] {e}", time.perf_counter() - t0)

    cost = (in_tok / 1_000_000 * _COST_IN_PER_1M +
            out_tok / 1_000_000 * _COST_OUT_PER_1M)

    return {
        "answer":             answer,
        "citations":          chunks,
        "tokens_used":        in_tok + out_tok,
        "estimated_cost_usd": round(cost, 6),
        "latency_ms":         round((time.perf_counter() - t0) * 1000, 1),
        "model":              GEMINI_MODEL,
        "architecture_name":  "unknown",
    }


# ---------------------------------------------------------------------------
# Async batch generate — used by scripts/run_batch_evaluation.py
# ---------------------------------------------------------------------------

async def batch_generate_async(
    prompts: dict[str, str],
    max_concurrent: int = 20,
) -> dict[str, tuple[str, dict]]:
    """
    Generate answers for many prompts concurrently.

    Args:
        prompts:        {key: prompt_text}
        max_concurrent: max simultaneous in-flight requests

    Returns:
        {key: (answer_text, usage_dict)}
    """
    from google import genai
    from google.genai import types

    client    = genai.Client(api_key=GEMINI_API_KEY)
    config    = types.GenerateContentConfig(
        system_instruction=_SYSTEM_PROMPT,
        temperature=LLM_TEMPERATURE,
        max_output_tokens=LLM_MAX_TOKENS,
    )
    semaphore = asyncio.Semaphore(max_concurrent)
    results   = {}
    done      = 0
    total     = len(prompts)
    t0        = time.perf_counter()

    async def _one(key: str, prompt: str) -> None:
        nonlocal done
        delay = 2.0
        for attempt in range(5):
            async with semaphore:
                try:
                    response = await client.aio.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=prompt,
                        config=config,
                    )
                    usage   = response.usage_metadata
                    results[key] = (
                        response.text.strip(),
                        {
                            "input_tokens":  getattr(usage, "prompt_token_count", 0) or 0,
                            "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
                        },
                    )
                    done += 1
                    if done % 100 == 0 or done == total:
                        elapsed = time.perf_counter() - t0
                        rate    = done / elapsed
                        eta     = (total - done) / rate if rate else 0
                        log.info("  Gemini: %d/%d  (%.0f/min  eta=%.1fm)",
                                 done, total, rate * 60, eta / 60)
                    return
                except Exception as e:
                    err = str(e)
                    is_rate_limit = "429" in err or "quota" in err.lower() or "exhausted" in err.lower()
                    if is_rate_limit or attempt < 4:
                        wait = delay * (2 ** attempt)
                        if is_rate_limit:
                            log.warning("  Rate limit — waiting %.0fs (attempt %d)", wait, attempt + 1)
                        await asyncio.sleep(wait)
                    else:
                        log.error("  Failed %s after 5 attempts: %s", key, e)
                        results[key] = (f"[LLM ERROR] {e}", {"input_tokens": 0, "output_tokens": 0})
                        done += 1
                        return

    await asyncio.gather(*[_one(k, p) for k, p in prompts.items()])
    return results


def _error_response(chunks: list[dict], message: str, elapsed_s: float) -> dict:
    return {
        "answer":             message,
        "citations":          chunks,
        "tokens_used":        0,
        "estimated_cost_usd": 0.0,
        "latency_ms":         round(elapsed_s * 1000, 1),
        "model":              GEMINI_MODEL,
        "architecture_name":  "unknown",
    }
