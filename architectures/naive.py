"""
Meridian — Architecture 1: Naive RAG.

Dense retrieval only (no reranker, no query expansion).
Uses the existing fixed-chunk Qdrant index (meridian_fixed).
Baseline to compare all other architectures against.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from architectures.base import BaseArchitecture
from retrieval import dense
from llm.generator import generate as llm_generate
from config import COLLECTION_NAMES, TOP_K_RERANK


class NaiveRAG(BaseArchitecture):
    name = "naive"

    def __init__(
        self,
        collection_name: str = COLLECTION_NAMES["fixed"],
        top_k: int = TOP_K_RERANK,
    ):
        self.collection_name = collection_name
        self.top_k = top_k

    def retrieve(
        self,
        question: str,
        companies: list[str] | None = None,
        fiscal_years: list[int] | None = None,
        sections: list[str] | None = None,
        **_,
    ) -> list[dict]:
        return dense.search(
            question,
            self.collection_name,
            top_k=self.top_k,
            companies=companies,
            fiscal_years=fiscal_years,
            sections=sections,
        )

    def generate(self, question: str, chunks: list[dict]) -> dict:
        result = llm_generate(question, chunks)
        result["architecture_name"] = self.name
        return result


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    arch = NaiveRAG()
    q   = "What was Apple revenue 2023?"
    out = arch.run("smoke_naive_001", q)

    assert out["answer"], "answer must not be empty"
    assert len(out["citations"]) > 0, "must have at least one citation"

    print(f"\nArchitecture : {out['architecture_name']}")
    print(f"Latency      : {out['latency_ms']} ms")
    print(f"Tokens       : {out['tokens_used']}")
    print(f"Citations    : {len(out['citations'])}")
    print(f"\nAnswer:\n{out['answer']}")
    print(f"\nFirst citation:")
    c = out["citations"][0]
    print(f"  [{c['company']} FY{c['year']} {c['section']}]")
    print(f"  {c['text'][:120]}")
    print("\nSmoke test PASSED")
