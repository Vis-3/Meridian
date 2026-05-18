"""
Meridian — Architecture 8: Full System Router.

Query classifier routes each question to the optimal architecture:

  simple_factual  → HierarchicalRAG  (doc-level routing, fast)
  numerical       → AgenticRAG       (calculator tool)
  temporal        → AgenticRAG       (temporal tool, no year filter)
  comparative     → FusionRAG        (multi-variant + balanced retrieval)
  multi_hop       → GraphRAG         (Neo4j + vector)
  risk_qualitative→ CorrectiveRAG    (hybrid + relevance filter)

Falls back gracefully: if HierarchicalRAG index not built, routes simple_factual
to HybridRAG instead.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from architectures.base import BaseArchitecture
from llm.prompts import QUERY_ROUTER_SYSTEM as _ROUTER_SYSTEM
from config import OLLAMA_BASE_URL, LLM_MODEL, BEST_ARCH_PER_TYPE, QUERY_TYPES

log = logging.getLogger(__name__)


def _classify_query(question: str) -> str:
    """Returns one of QUERY_TYPES. Defaults to simple_factual on failure."""
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": _ROUTER_SYSTEM},
            {"role": "user",   "content": f'Question: "{question}"'},
        ],
        "stream":  False,
        "options": {"temperature": 0.0, "num_predict": 30},
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
            qtype = json.loads(content[start:end]).get("type", "simple_factual")
            if qtype in QUERY_TYPES:
                return qtype
    except Exception as e:
        log.debug(f"Router classify failed: {e}")
    return "simple_factual"


# ---------------------------------------------------------------------------
# Architecture registry (lazy instantiation)
# ---------------------------------------------------------------------------

_arch_cache: dict[str, BaseArchitecture] = {}


def _get_arch(arch_name: str) -> BaseArchitecture:
    if arch_name not in _arch_cache:
        if arch_name == "hierarchical":
            try:
                from architectures.hierarchical_rag import HierarchicalRAG
                _arch_cache[arch_name] = HierarchicalRAG()
            except RuntimeError:
                log.warning("HierarchicalRAG index not built — routing simple_factual to hybrid_rag")
                from architectures.hybrid_rag import HybridRAG
                _arch_cache[arch_name] = HybridRAG()

        elif arch_name == "agentic":
            from architectures.agentic_rag import AgenticRAG
            _arch_cache[arch_name] = AgenticRAG()

        elif arch_name == "fusion":
            from architectures.fusion_rag import FusionRAG
            _arch_cache[arch_name] = FusionRAG()

        elif arch_name == "graph":
            from architectures.graph_rag import GraphRAG
            _arch_cache[arch_name] = GraphRAG()

        elif arch_name == "corrective":
            from architectures.corrective_rag import CorrectiveRAG
            _arch_cache[arch_name] = CorrectiveRAG()

        else:  # fallback
            from architectures.hybrid_rag import HybridRAG
            _arch_cache[arch_name] = HybridRAG()

    return _arch_cache[arch_name]


# ---------------------------------------------------------------------------
# Full System architecture
# ---------------------------------------------------------------------------

class FullSystem(BaseArchitecture):
    name = "full_system"

    def __init__(self):
        self._last_query_type: str            = ""
        self._last_arch_name:  str            = ""
        self._last_arch:       BaseArchitecture | None = None

    def retrieve(self, question: str, **kwargs) -> list[dict]:
        qtype     = _classify_query(question)
        arch_name = BEST_ARCH_PER_TYPE.get(qtype, "hybrid_rag")

        self._last_query_type = qtype
        self._last_arch_name  = arch_name
        self._last_arch       = _get_arch(arch_name)

        log.debug("[FullSystem] query_type=%s -> architecture=%s", qtype, arch_name)
        return self._last_arch.retrieve(question, **kwargs)

    def generate(self, question: str, chunks: list[dict]) -> dict:
        if self._last_arch:
            result = self._last_arch.generate(question, chunks)
        else:
            from llm.generator import generate as llm_generate
            result = llm_generate(question, chunks)
        result["architecture_name"] = self.name
        result["routed_to"]         = self._last_arch_name
        result["query_type"]        = self._last_query_type
        return result

    def run(self, question_id: str, question: str, **kwargs) -> dict:
        out = super().run(question_id, question, **kwargs)
        out["routed_to"]   = self._last_arch_name
        out["query_type"]  = self._last_query_type
        return out


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_cases = [
        ("smoke_fs_01", "What was Apple total revenue in fiscal year 2023?"),
        ("smoke_fs_02", "What is Apple's revenue minus cost of sales in 2023?"),
        ("smoke_fs_03", "How did Meta revenue grow from 2020 to 2024?"),
        ("smoke_fs_04", "Compare R&D spending across Apple Microsoft Google Amazon Meta in 2023."),
        ("smoke_fs_05", "How did Apple's supply chain strategy change after the COVID pandemic?"),
        ("smoke_fs_06", "What were the main risk factors for tech companies in 2021?"),
    ]

    router = FullSystem()
    print(f"{'='*60}")
    print(f"{'Question':<45} {'Type':<18} {'Architecture'}")
    print(f"{'='*60}")

    for qid, question in test_cases:
        out = router.run(qid, question)
        qtype    = out.get("query_type",  "?")
        arch     = out.get("routed_to",   "?")
        print(f"{question[:44]:<45} {qtype:<18} {arch}")
        assert out["answer"], f"empty answer for: {question}"

    print(f"\n{'='*60}")
    print("All 6 routing smoke tests passed.")
    print("\nSmoke test PASSED")
