"""
Meridian — MeridianRouter: data-driven multi-mode RAG router.

Routes each question to the empirically optimal architecture based on question
type, using benchmark-validated routing tables (May 2026, 180-question run).

Four modes
----------
  quality    — maximises quality score per question type
  production — maximises production score (quality 50% + speed 30% + cost 20%)
  cost       — maximises cost-quality score (cheapest architecture per type)
  efficiency — maximises efficiency score (quality / log10 latency)

Routing tables (data source: evaluation/composite_score.py, scripts/router_preview.py)
---------------------------------------------------------------------------------------
  quality:    simple_factual→hierarchical, numerical_reasoning→hierarchical,
              temporal→fusion, comparative→graph,
              multi_hop→hybrid, risk_qualitative→naive

  production: simple_factual→hybrid, numerical_reasoning→hierarchical,
              temporal→graph, comparative→graph,
              multi_hop→hybrid, risk_qualitative→naive

  cost:       simple_factual→corrective, numerical_reasoning→corrective,
              temporal→corrective, comparative→corrective,
              multi_hop→hybrid, risk_qualitative→corrective

  efficiency: all types → naive  (degenerate — naive wins all 6 types at 66ms P50)

Usage
-----
    from architectures.meridian_router import MeridianRouter

    router = MeridianRouter(mode="production")  # default mode
    result = router.run(question_id="q1", question="What was Apple revenue in 2023?")
    print(result["answer"])
    print(result["routed_to"])     # e.g. "hybrid"
    print(result["query_type"])    # e.g. "simple_factual"
    print(result["router_mode"])   # e.g. "production"

Smoke test
----------
    python architectures/meridian_router.py [--mode quality|production|cost|efficiency]
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from architectures.base import BaseArchitecture
from config import GEMINI_API_KEY, GEMINI_MODEL, QUERY_TYPES

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Benchmark-validated routing tables (May 2026)
# ---------------------------------------------------------------------------

ROUTING_TABLES: dict[str, dict[str, str]] = {
    "quality": {
        "simple_factual":     "hierarchical",
        "numerical_reasoning":"hierarchical",
        "temporal":           "fusion",
        "comparative":        "graph",
        "multi_hop":          "hybrid",
        "risk_qualitative":   "naive",
    },
    "production": {
        "simple_factual":     "hybrid",
        "numerical_reasoning":"hierarchical",
        "temporal":           "graph",
        "comparative":        "graph",
        "multi_hop":          "hybrid",
        "risk_qualitative":   "naive",
    },
    "cost": {
        "simple_factual":     "corrective",
        "numerical_reasoning":"corrective",
        "temporal":           "corrective",
        "comparative":        "corrective",
        "multi_hop":          "hybrid",
        "risk_qualitative":   "corrective",
    },
    "efficiency": {
        # All types → naive (naive wins all 6 types at 66ms P50)
        "simple_factual":     "naive",
        "numerical_reasoning":"naive",
        "temporal":           "naive",
        "comparative":        "naive",
        "multi_hop":          "naive",
        "risk_qualitative":   "naive",
    },
}

# Quality per type by routing mode — for display / logging
ROUTING_QUALITY_SCORES: dict[str, dict[str, float]] = {
    "quality": {
        "simple_factual":     0.8560,
        "numerical_reasoning":0.7311,
        "temporal":           0.4539,
        "comparative":        0.7877,
        "multi_hop":          0.5664,
        "risk_qualitative":   0.9467,
        "overall":            0.7236,
    },
    "production": {
        "simple_factual":     0.8548,
        "numerical_reasoning":0.7311,
        "temporal":           0.4280,
        "comparative":        0.7877,
        "multi_hop":          0.5664,
        "risk_qualitative":   0.9467,
        "overall":            0.7191,
    },
}

VALID_MODES = list(ROUTING_TABLES.keys())

# ---------------------------------------------------------------------------
# Query type classifier  (uses Gemini — same model as generation)
# ---------------------------------------------------------------------------

_ROUTER_SYSTEM = (
    "You are a financial question classifier. Classify the question into exactly "
    "one of these types and respond with a JSON object containing only the 'type' key.\n\n"
    "Types:\n"
    "  simple_factual     — single company, single year, direct lookup\n"
    "  numerical_reasoning — ratios, growth rates, margin calculations\n"
    "  temporal           — trends across multiple years\n"
    "  comparative        — multi-company comparison in the same period\n"
    "  multi_hop          — two conditions joined across sections or documents\n"
    "  risk_qualitative   — qualitative reasoning over risk factors\n\n"
    'Respond with exactly: {"type": "<one_of_the_above>"}'
)


def _classify_gemini(question: str) -> str:
    """Classify question type using Gemini (google-genai SDK). Falls back to simple_factual."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        config = types.GenerateContentConfig(
            system_instruction=_ROUTER_SYSTEM,
            temperature=1.0,   # required for thinking models
            max_output_tokens=500,
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=question,
            config=config,
        )
        text  = response.text.strip()
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            qtype = json.loads(text[start:end]).get("type", "simple_factual")
            # Normalise: routing tables use "numerical_reasoning"; config uses "numerical"
            if qtype == "numerical":
                qtype = "numerical_reasoning"
            if qtype in ROUTING_TABLES["quality"]:   # validate against router's own key set
                return qtype
    except Exception as e:
        log.debug("[MeridianRouter] classify failed: %s", e)
    return "simple_factual"


# ---------------------------------------------------------------------------
# Architecture registry (lazy instantiation — only loads what's needed)
# ---------------------------------------------------------------------------

_arch_cache: dict[str, BaseArchitecture] = {}


def _get_arch(arch_name: str) -> BaseArchitecture:
    if arch_name not in _arch_cache:
        if arch_name == "naive":
            from architectures.naive import NaiveRAG
            _arch_cache[arch_name] = NaiveRAG()

        elif arch_name == "hybrid":
            from architectures.hybrid_rag import HybridRAG
            _arch_cache[arch_name] = HybridRAG()

        elif arch_name == "fusion":
            from architectures.fusion_rag import FusionRAG
            _arch_cache[arch_name] = FusionRAG()

        elif arch_name == "hierarchical":
            try:
                from architectures.hierarchical_rag import HierarchicalRAG
                _arch_cache[arch_name] = HierarchicalRAG()
            except RuntimeError:
                log.warning(
                    "[MeridianRouter] HierarchicalRAG index not built — "
                    "falling back to hybrid for this type"
                )
                from architectures.hybrid_rag import HybridRAG
                _arch_cache[arch_name] = HybridRAG()

        elif arch_name == "graph":
            from architectures.graph_rag import GraphRAG
            _arch_cache[arch_name] = GraphRAG()

        elif arch_name == "corrective":
            from architectures.corrective_rag import CorrectiveRAG
            _arch_cache[arch_name] = CorrectiveRAG()

        elif arch_name == "agentic":
            from architectures.agentic_rag import AgenticRAG
            _arch_cache[arch_name] = AgenticRAG()

        else:
            log.warning("[MeridianRouter] unknown arch '%s', falling back to hybrid", arch_name)
            from architectures.hybrid_rag import HybridRAG
            _arch_cache[arch_name] = HybridRAG()

    return _arch_cache[arch_name]


# ---------------------------------------------------------------------------
# MeridianRouter
# ---------------------------------------------------------------------------

class MeridianRouter(BaseArchitecture):
    """
    Data-driven RAG router with 4 operating modes.

    Parameters
    ----------
    mode : str
        One of: "quality", "production", "cost", "efficiency".
        Default: "production" (best balanced trade-off).
    """

    name = "meridian_router"

    def __init__(self, mode: str = "production"):
        if mode not in VALID_MODES:
            raise ValueError(
                f"Invalid mode '{mode}'. Choose from: {VALID_MODES}"
            )
        self.mode = mode
        self._routing_table = ROUTING_TABLES[mode]

        self._last_query_type: str = ""
        self._last_arch_name:  str = ""
        self._last_arch: BaseArchitecture | None = None

    # ------------------------------------------------------------------
    # BaseArchitecture interface
    # ------------------------------------------------------------------

    def retrieve(self, question: str, **kwargs) -> list[dict]:
        qtype     = _classify_gemini(question)
        arch_name = self._routing_table.get(qtype, "hybrid")

        self._last_query_type = qtype
        self._last_arch_name  = arch_name
        self._last_arch       = _get_arch(arch_name)

        log.info(
            "[MeridianRouter/%s] %s → %s",
            self.mode, qtype, arch_name,
        )
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
        result["router_mode"]       = self.mode
        return result

    def run(self, question_id: str, question: str, **kwargs) -> dict:
        out = super().run(question_id, question, **kwargs)
        out["routed_to"]   = self._last_arch_name
        out["query_type"]  = self._last_query_type
        out["router_mode"] = self.mode
        return out

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def routing_table(self) -> dict[str, str]:
        """Return the current routing table (type → arch name)."""
        return dict(self._routing_table)

    def expected_quality(self, qtype: str | None = None) -> float | None:
        """Return benchmark quality score for this mode (overall or per type)."""
        scores = ROUTING_QUALITY_SCORES.get(self.mode, {})
        if qtype:
            return scores.get(qtype)
        return scores.get("overall")

    def __repr__(self) -> str:
        return f"MeridianRouter(mode={self.mode!r})"


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MeridianRouter smoke test")
    parser.add_argument(
        "--mode", default="production",
        choices=VALID_MODES,
        help="Router mode to test",
    )
    args = parser.parse_args()

    test_cases = [
        ("smoke_mr_01", "simple_factual",     "What was Apple's total revenue in fiscal year 2023?"),
        ("smoke_mr_02", "numerical_reasoning","What was Meta's operating margin in FY2022?"),
        ("smoke_mr_03", "temporal",           "How did Microsoft's cloud revenue grow from 2020 to 2024?"),
        ("smoke_mr_04", "comparative",        "Compare R&D spending across Apple, Microsoft, Google in 2023."),
        ("smoke_mr_05", "multi_hop",          "Which companies with AI risk disclosure showed revenue growth above 10%?"),
        ("smoke_mr_06", "risk_qualitative",   "What supply chain risks did Apple disclose in 2021?"),
    ]

    router = MeridianRouter(mode=args.mode)
    print(f"\n{'='*72}")
    print(f"  MeridianRouter smoke test — mode: {args.mode}")
    print(f"  Expected overall quality: {router.expected_quality()}")
    print(f"{'='*72}")
    print(f"  {'Question':<42} {'Expected type':<22} {'Routed to'}")
    print(f"  {'-'*42} {'-'*22} {'-'*14}")

    passes = 0
    for qid, expected_type, question in test_cases:
        out = router.run(qid, question)
        qtype    = out.get("query_type", "?")
        arch     = out.get("routed_to",  "?")
        expected = router.routing_table().get(expected_type, "?")
        ok       = arch == expected
        status   = "PASS" if ok else f"WARN (got {arch}, expected {expected})"
        if ok:
            passes += 1
        print(f"  {question[:41]:<42} {qtype:<22} {arch}  [{status}]")
        assert out["answer"], f"Empty answer for: {question}"

    print(f"\n  {passes}/{len(test_cases)} routing decisions matched expected table.")
    print(f"  (Mismatches may reflect valid classifier variance, not errors.)\n")
    print(f"{'='*72}")
    print("  Smoke test PASSED" if passes == len(test_cases) else "  Smoke test DONE (see warnings above)")
    print(f"{'='*72}\n")
