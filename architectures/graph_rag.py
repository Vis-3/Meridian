"""
Meridian — Architecture 6: Graph RAG.

Combines a Neo4j knowledge graph with vector retrieval.

Query classification:
  - "entity" queries (mention a specific company + metric/topic) →
    Cypher traversal first, then vector augmentation
  - "text" queries → vector-only (hybrid search)

If Neo4j is unreachable, falls back to hybrid retrieval gracefully.

Requires: Neo4j running + graph/loader.py executed once.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from architectures.base import BaseArchitecture
from retrieval import hybrid
from retrieval.reranker import rerank
from llm.generator import generate as llm_generate
from config import (
    COLLECTION_NAMES, TOP_K_RETRIEVAL, TOP_K_RERANK,
    NEO4J_URL, NEO4J_USER, NEO4J_PASSWORD, COMPANIES,
)

log = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase as _GDB
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False


# ---------------------------------------------------------------------------
# Neo4j connection (singleton, lazy)
# ---------------------------------------------------------------------------

_driver = None


def _get_driver():
    global _driver
    if not _NEO4J_AVAILABLE:
        return None
    if _driver is None:
        try:
            _driver = _GDB.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))
            _driver.verify_connectivity()
        except Exception as e:
            log.warning(f"Neo4j unavailable: {e} — graph_rag will use vector-only fallback")
            _driver = None
    return _driver


# ---------------------------------------------------------------------------
# Query classifier
# ---------------------------------------------------------------------------

_COMPANY_RE = re.compile(
    r"\b(" + "|".join(COMPANIES) + r")\b", re.IGNORECASE
)

_ENTITY_KEYWORDS = {
    "revenue", "sales", "profit", "income", "expense", "r&d",
    "margin", "azure", "aws", "cloud", "iphone", "search", "advertising",
    "segment", "division",
}


def _classify_query(question: str) -> str:
    """Return 'entity' if question names a company + metric, else 'text'."""
    q_lower = question.lower()
    has_company = bool(_COMPANY_RE.search(question))
    has_entity  = any(kw in q_lower for kw in _ENTITY_KEYWORDS)
    return "entity" if (has_company and has_entity) else "text"


# ---------------------------------------------------------------------------
# Cypher queries
# ---------------------------------------------------------------------------

def _cypher_entity_query(
    question: str,
    driver,
    companies: list[str] | None = None,
    fiscal_years: list[int] | None = None,
) -> tuple[list[dict], str]:
    """
    Run a Cypher query to find relevant documents via the graph.
    Returns (graph_result_metas, cypher_string).
    """
    # Extract company from question if not supplied
    if not companies:
        m = _COMPANY_RE.search(question)
        companies = [m.group(0).capitalize()] if m else COMPANIES[:3]

    # Build dynamic Cypher
    company_filter = " OR ".join(f"c.name = '{co}'" for co in companies)
    year_filter = ""
    if fiscal_years:
        year_filter = f" AND d.fiscal_year IN {fiscal_years}"

    cypher = f"""
    MATCH (c:Company)-[:FILED]->(d:Document)-[:HAS_SECTION]->(s:Section)
    WHERE ({company_filter}){year_filter}
    RETURN c.name AS company, d.fiscal_year AS fiscal_year,
           d.document_type AS document_type, d.quarter AS quarter,
           d.id AS doc_id, collect(DISTINCT s.name) AS sections
    ORDER BY d.fiscal_year DESC
    LIMIT 5
    """

    try:
        with driver.session() as sess:
            records = sess.run(cypher).data()
        return records, cypher.strip()
    except Exception as e:
        log.warning(f"Cypher query failed: {e}")
        return [], cypher.strip()


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------

class GraphRAG(BaseArchitecture):
    name = "graph_rag"

    def __init__(
        self,
        collection_name: str = COLLECTION_NAMES["fixed"],
        bm25_name: str = "fixed",
        top_k_retrieve: int = TOP_K_RETRIEVAL,
        top_k_rerank: int = TOP_K_RERANK,
    ):
        self.collection_name = collection_name
        self.bm25_name       = bm25_name
        self.top_k_retrieve  = top_k_retrieve
        self.top_k_rerank    = top_k_rerank
        self._last_cypher:       str        = ""
        self._last_graph_results: list[dict] = []
        self._neo4j_active:       bool       = False

        driver = _get_driver()
        self._neo4j_active = driver is not None

    def retrieve(
        self,
        question: str,
        companies: list[str] | None = None,
        fiscal_years: list[int] | None = None,
        sections: list[str] | None = None,
        **_,
    ) -> list[dict]:
        driver      = _get_driver()
        query_type  = _classify_query(question)
        graph_metas: list[dict] = []

        log.debug("[GraphRAG] query_type=%s  neo4j=%s", query_type, 'up' if driver else 'down (fallback)')

        if query_type == "entity" and driver:
            graph_metas, cypher = _cypher_entity_query(
                question, driver, companies, fiscal_years
            )
            self._last_cypher        = cypher
            self._last_graph_results = graph_metas
            log.debug("[GraphRAG] Cypher: %s", cypher.splitlines()[0])
            log.debug("[GraphRAG] Graph results: %d doc(s)", len(graph_metas))

            # Use graph-identified docs to scope vector retrieval
            if graph_metas:
                companies    = companies or list({r["company"]     for r in graph_metas})
                fiscal_years = fiscal_years or list({r["fiscal_year"] for r in graph_metas})
        else:
            self._last_cypher        = ""
            self._last_graph_results = []

        # Vector retrieval (always runs — graph narrows the filter)
        chunks = hybrid.search(
            question,
            collection_name=self.collection_name,
            bm25_name=self.bm25_name,
            top_k=self.top_k_retrieve,
            companies=companies,
            fiscal_years=fiscal_years,
            sections=sections,
        )

        return rerank(question, chunks, top_k=self.top_k_rerank)

    def generate(self, question: str, chunks: list[dict]) -> dict:
        result = llm_generate(question, chunks)
        result["architecture_name"] = self.name
        result["graph_results"]     = self._last_graph_results
        result["cypher_used"]       = self._last_cypher
        return result

    def run(self, question_id: str, question: str, **kwargs) -> dict:
        out = super().run(question_id, question, **kwargs)
        out["graph_results"] = self._last_graph_results
        out["cypher_used"]   = self._last_cypher
        return out


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    arch = GraphRAG()
    q   = "What was Microsoft Azure cloud revenue?"
    out = arch.run("smoke_graph_001", q)

    graph_results = out.get("graph_results")
    assert graph_results is not None, "graph_results key must exist"
    assert out["answer"], "answer must not be empty"

    print(f"\nArchitecture  : {out['architecture_name']}")
    print(f"Neo4j active  : {arch._neo4j_active}")
    print(f"Graph results : {len(graph_results)}")
    if out.get("cypher_used"):
        print(f"Cypher used:\n{out['cypher_used']}")
    print(f"Latency       : {out['latency_ms']} ms")
    print(f"Tokens        : {out['tokens_used']}")
    print(f"\nAnswer:\n{out['answer']}")
    print("\nSmoke test PASSED")
