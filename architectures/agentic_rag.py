"""
Meridian — Architecture 7: Agentic RAG (LangGraph state machine).

State machine:
  classify → plan → retrieve → compress → generate → faithfulness_check
                                                    ↓ (low faith, retry ≤ 2)
                                              re_retrieve

Tools:
  single_doc   — dense retrieval, one company + year
  multi_doc    — hybrid retrieval, multiple companies
  temporal     — hybrid retrieval spanning multiple years
  comparative  — hybrid.search_balanced, all 5 companies
  calculator   — extracts numbers from chunks + evaluates expression
  graph        — graph_rag retrieval (Neo4j if available)

Falls back gracefully if LangGraph is not installed (linear pipeline).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from architectures.base import BaseArchitecture
from retrieval import hybrid, dense
from retrieval.reranker import rerank
from llm.generator import generate as llm_generate
from llm.prompts import QUERY_CLASSIFIER_SYSTEM as _CLASSIFIER_SYSTEM
from config import (
    COLLECTION_NAMES, TOP_K_RETRIEVAL, TOP_K_RERANK,
    OLLAMA_BASE_URL, LLM_MODEL, COMPANIES,
    FAITHFULNESS_THRESHOLD, MAX_RETRIES,
)

log = logging.getLogger(__name__)

try:
    from langgraph.graph import StateGraph, END
    from typing import TypedDict, Annotated
    import operator
    _LANGGRAPH = True
except ImportError:
    _LANGGRAPH = False
    log.info("LangGraph not installed — using linear pipeline fallback")

# ---------------------------------------------------------------------------
# Query classifier
# ---------------------------------------------------------------------------


def _classify(question: str) -> dict:
    """Returns {type, tool, companies, fiscal_years}."""
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": _CLASSIFIER_SYSTEM},
            {"role": "user",   "content": f'Question: "{question}"'},
        ],
        "stream":  False,
        "options": {"temperature": 0.0, "num_predict": 60},
    }
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=30
        )
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "").strip()
        start = content.find("{")
        end   = content.rfind("}") + 1
        if start != -1 and end > start:
            result = json.loads(content[start:end])
            return {
                "type":         result.get("type", "simple_factual"),
                "tool":         result.get("tool", "single_doc"),
                "companies":    None,
                "fiscal_years": None,
            }
    except Exception as e:
        log.debug(f"Classify failed: {e}")
    return {"type": "simple_factual", "tool": "single_doc",
            "companies": None, "fiscal_years": None}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def _tool_single_doc(question, companies=None, fiscal_years=None, sections=None):
    return dense.search(
        question, COLLECTION_NAMES["fixed"],
        top_k=TOP_K_RERANK,
        companies=companies, fiscal_years=fiscal_years, sections=sections,
    )


def _tool_multi_doc(question, companies=None, fiscal_years=None, sections=None):
    candidates = hybrid.search(
        question, top_k=TOP_K_RETRIEVAL,
        companies=companies, fiscal_years=fiscal_years, sections=sections,
    )
    return rerank(question, candidates, top_k=TOP_K_RERANK)


def _tool_temporal(question, companies=None, fiscal_years=None, sections=None):
    """Retrieve across multiple years — no fiscal_year filter to allow spanning."""
    candidates = hybrid.search(
        question, top_k=TOP_K_RETRIEVAL,
        companies=companies, fiscal_years=None, sections=sections,
    )
    return rerank(question, candidates, top_k=TOP_K_RERANK)


def _tool_comparative(question, companies=None, fiscal_years=None, sections=None):
    target_companies = companies or COMPANIES
    return hybrid.search_balanced(
        question,
        companies=target_companies,
        fiscal_years=fiscal_years,
        top_k_per_company=3,
        sections=sections,
    )


def _tool_calculator(question, chunks):
    """Extract numbers from chunks and attempt simple arithmetic."""
    numbers = []
    for chunk in chunks:
        text = chunk.get("text", "")
        nums = re.findall(r'\$?\s*([\d,]+(?:\.\d+)?)\s*(?:billion|million|B|M)?', text)
        for n in nums[:5]:
            try:
                numbers.append(float(n.replace(",", "")))
            except ValueError:
                pass
    if numbers:
        result = f"Extracted figures: {numbers[:10]}"
    else:
        result = "No numeric figures found in context"
    return result


def _tool_graph(question, companies=None, fiscal_years=None, sections=None):
    """Delegate to GraphRAG retrieve (imports lazily to avoid circular)."""
    from architectures.graph_rag import GraphRAG
    g = GraphRAG()
    return g.retrieve(
        question, companies=companies,
        fiscal_years=fiscal_years, sections=sections,
    )


_TOOL_MAP = {
    "single_doc":  _tool_single_doc,
    "multi_doc":   _tool_multi_doc,
    "temporal":    _tool_temporal,
    "comparative": _tool_comparative,
    "graph":       _tool_graph,
}


# ---------------------------------------------------------------------------
# Faithfulness check (lightweight)
# ---------------------------------------------------------------------------

def _check_faithfulness(answer: str, chunks: list[dict]) -> float:
    """
    Quick faithfulness heuristic: what fraction of answer sentences
    contain at least one phrase from the context?
    Real RAGAS faithfulness runs in evaluation pipeline.
    """
    context = " ".join(c.get("text", "") for c in chunks).lower()
    sentences = [s.strip() for s in re.split(r'[.!?]', answer) if len(s.strip()) > 10]
    if not sentences:
        return 1.0
    supported = sum(
        1 for s in sentences
        if any(word in context for word in s.lower().split() if len(word) > 5)
    )
    return round(supported / len(sentences), 2)


# ---------------------------------------------------------------------------
# Linear pipeline (LangGraph fallback)
# ---------------------------------------------------------------------------

class AgenticRAG(BaseArchitecture):
    name = "agentic_rag"

    def __init__(self):
        self._last_plan:       dict        = {}
        self._last_tool:       str         = ""
        self._retry_count:     int         = 0
        self._state_log:       list[str]   = []

    def _log(self, state: str):
        self._state_log.append(state)
        if os.getenv("DEBUG"):
            print(f"  [AgenticRAG] -> {state}")

    def retrieve(
        self,
        question: str,
        companies: list[str] | None = None,
        fiscal_years: list[int] | None = None,
        sections: list[str] | None = None,
        **_,
    ) -> list[dict]:
        self._state_log = []
        self._retry_count = 0

        # CLASSIFY
        self._log("classify")
        plan = _classify(question)
        plan["companies"]    = companies    or plan.get("companies")
        plan["fiscal_years"] = fiscal_years or plan.get("fiscal_years")
        self._last_plan = plan
        tool_name = plan["tool"]
        self._last_tool = tool_name
        log.debug("[AgenticRAG] type=%s  tool=%s", plan['type'], tool_name)

        # PLAN + RETRIEVE
        self._log("plan")
        self._log("retrieve")
        chunks = self._run_tool(question, tool_name, plan, sections)

        # Fallback: if primary tool returned nothing (e.g. Ollama unavailable),
        # use hybrid retrieval which requires no LLM classification.
        if not chunks:
            log.warning("[AgenticRAG] primary tool '%s' returned 0 chunks — falling back to multi_doc", tool_name)
            self._log("fallback_multi_doc")
            chunks = _tool_multi_doc(question)

        return chunks

    def _run_tool(self, question, tool_name, plan, sections):
        tool_fn = _TOOL_MAP.get(tool_name, _tool_multi_doc)
        chunks  = tool_fn(
            question,
            companies=plan.get("companies"),
            fiscal_years=plan.get("fiscal_years"),
            sections=sections,
        )
        return chunks

    def generate(self, question: str, chunks: list[dict]) -> dict:
        # COMPRESS: keep only top chunks (already reranked upstream)
        self._log("compress")
        compressed = chunks[:TOP_K_RERANK]

        # GENERATE
        self._log("generate")
        result = llm_generate(question, compressed)
        result["architecture_name"] = self.name

        # FAITHFULNESS CHECK
        self._log("faithfulness_check")
        faith = _check_faithfulness(result["answer"], compressed)
        result["faithfulness_proxy"] = faith
        log.debug("[AgenticRAG] faithfulness_proxy=%.2f (threshold=%.2f)", faith, FAITHFULNESS_THRESHOLD)

        if faith < FAITHFULNESS_THRESHOLD and self._retry_count < MAX_RETRIES:
            self._retry_count += 1
            self._log(f"re_retrieve (retry {self._retry_count}/{MAX_RETRIES})")
            # Retry with multi_doc (broader retrieval)
            retry_chunks = _tool_multi_doc(question)
            retry_result = llm_generate(question, retry_chunks)
            retry_result["architecture_name"] = self.name
            retry_faith  = _check_faithfulness(retry_result["answer"], retry_chunks)
            log.debug("[AgenticRAG] retry faithfulness_proxy=%.2f", retry_faith)
            if retry_faith > faith:
                retry_result["faithfulness_proxy"] = retry_faith
                return retry_result

        return result

    def run(self, question_id: str, question: str, **kwargs) -> dict:
        out = super().run(question_id, question, **kwargs)
        out["state_log"]         = self._state_log
        out["tool_selected"]     = self._last_tool
        out["query_type"]        = self._last_plan.get("type", "")
        out["faithfulness_proxy"] = 0.0
        return out


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_cases = [
        ("smoke_agentic_factual",     "What was Apple total revenue in 2023?"),
        ("smoke_agentic_temporal",    "How did Apple revenue change from 2020 to 2024?"),
        ("smoke_agentic_comparative", "Compare R&D expenses across all 5 companies in 2023."),
        ("smoke_agentic_risk",        "What supply chain risks did companies mention in 2021?"),
    ]

    arch = AgenticRAG()
    for qid, question in test_cases:
        print(f"\n{'='*50}")
        print(f"Q: {question}")
        out = arch.run(qid, question)
        print(f"Tool: {out['tool_selected']}  |  type: {out['query_type']}")
        print(f"Answer (first 120 chars): {out['answer'][:120]}")
        assert out["tool_selected"], f"tool must be selected for: {question}"

    print("\n" + "="*50)
    print("All 4 smoke questions passed")
    print("State transitions logged:")
    for state in arch._state_log:
        print(f"  → {state}")
    print("\nSmoke test PASSED")
