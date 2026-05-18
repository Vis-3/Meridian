"""
Meridian — Architecture 3: RAG Fusion.

Pipeline:
  1. LLM generates 4 query variants (rephrased perspectives on the question).
  2. Run hybrid search independently for each variant → 4 ranked lists.
  3. Fuse all 4 lists with RRF (multi-list variant from hybrid.py).
  4. BGE reranker on merged set → top-5.

Insight: different phrasings surface different relevant chunks; RRF promotes
chunks that appear consistently across multiple perspectives.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from architectures.base import BaseArchitecture
from retrieval import hybrid
from retrieval.reranker import rerank
from retrieval.hybrid import _rrf_fuse_multi
from llm.generator import generate as llm_generate
from llm.prompts import (
    QUERY_VARIANT_SYSTEM as _VARIANT_SYSTEM,
    QUERY_VARIANT_USER_TEMPLATE as _VARIANT_USER,
)
from config import (
    COLLECTION_NAMES, TOP_K_RETRIEVAL, TOP_K_RERANK,
    OLLAMA_BASE_URL, LLM_MODEL,
)

log = logging.getLogger(__name__)


def _generate_variants(question: str, model: str = LLM_MODEL) -> list[str]:
    """Ask the LLM to produce 4 rephrasings. Falls back to rule-based if LLM fails."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _VARIANT_SYSTEM},
            {"role": "user",   "content": _VARIANT_USER.format(question=question)},
        ],
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 256},
    }
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=60
        )
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "").strip()

        # Extract JSON array from response (LLM may wrap in markdown)
        start = content.find("[")
        end   = content.rfind("]") + 1
        if start != -1 and end > start:
            variants = json.loads(content[start:end])
            if isinstance(variants, list) and len(variants) >= 2:
                # Deduplicate and cap at 4; ensure original is not already included
                seen = {question.lower()}
                unique = []
                for v in variants:
                    if isinstance(v, str) and v.lower() not in seen:
                        seen.add(v.lower())
                        unique.append(v)
                    if len(unique) == 4:
                        break
                return unique if unique else _rule_based_variants(question)
    except Exception as e:
        log.warning(f"LLM variant generation failed: {e}")

    return _rule_based_variants(question)


def _rule_based_variants(question: str) -> list[str]:
    """Deterministic fallback variants using synonym substitution."""
    substitutions = [
        ("revenue",  "net sales"),
        ("revenue",  "total sales"),
        ("expense",  "cost"),
        ("profit",   "income"),
        ("R&D",      "research and development"),
        ("employees","headcount"),
    ]
    variants = []
    q_lower = question.lower()
    for old, new in substitutions:
        if old.lower() in q_lower:
            variants.append(q_lower.replace(old.lower(), new))
        if len(variants) == 3:
            break
    while len(variants) < 3:
        variants.append(question + f" annual report {['financial', 'SEC filing', '10-K'][len(variants)]}")
    return variants[:3]  # original is prepended in retrieve()


class FusionRAG(BaseArchitecture):
    name = "fusion_rag"

    def __init__(
        self,
        collection_name: str | None = None,
        bm25_name: str = "fixed",
        top_k_per_variant: int = 10,
        top_k_rerank: int = TOP_K_RERANK,
    ):
        self.collection_name   = collection_name or COLLECTION_NAMES["fixed"]
        self.bm25_name         = bm25_name
        self.top_k_per_variant = top_k_per_variant
        self.top_k_rerank      = top_k_rerank
        self._last_variants: list[str] = []

    def retrieve(
        self,
        question: str,
        companies: list[str] | None = None,
        fiscal_years: list[int] | None = None,
        sections: list[str] | None = None,
        **_,
    ) -> list[dict]:
        filter_kwargs = dict(
            collection_name=self.collection_name,
            bm25_name=self.bm25_name,
            top_k=self.top_k_per_variant,
            companies=companies,
            fiscal_years=fiscal_years,
            sections=sections,
        )

        # Step 1: generate 4 LLM variants; always include the original first
        llm_variants = _generate_variants(question)
        all_variants = [question] + llm_variants
        self._last_variants = all_variants
        log.debug("[FusionRAG] %d query variants generated", len(all_variants))
        if os.getenv("DEBUG"):
            for i, v in enumerate(all_variants, 1):
                print(f"    {i}. {v}")

        # Step 2: retrieve for each variant independently
        ranked_lists: list[list[dict]] = []
        for variant in all_variants:
            results = hybrid.search(variant, **filter_kwargs)
            ranked_lists.append(results)

        # Step 3: RRF merge across all variant lists
        fused = _rrf_fuse_multi(ranked_lists)

        # Step 4: BGE reranker on merged set → top-5
        reranked = rerank(question, fused, top_k=self.top_k_rerank)
        return reranked

    def generate(self, question: str, chunks: list[dict]) -> dict:
        result = llm_generate(question, chunks)
        result["architecture_name"] = self.name
        return result


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    arch = FusionRAG()
    q   = "What was Apple revenue 2023?"
    out = arch.run("smoke_fusion_001", q)

    variants = arch._last_variants
    assert len(variants) >= 2, "must have at least 2 variants"
    assert len(set(variants)) == len(variants), "all variants must be distinct strings"

    print(f"\nArchitecture : {out['architecture_name']}")
    print(f"Variants     : {len(variants)} (all distinct: {len(set(variants)) == len(variants)})")
    print(f"Latency      : {out['latency_ms']} ms")
    print(f"Tokens       : {out['tokens_used']}")
    print(f"Citations    : {len(out['citations'])}")
    print(f"\nAnswer:\n{out['answer']}")
    print("\nSmoke test PASSED")
