"""
Meridian -- FastAPI backend.

Exposes:
  GET /health   -- service health check (used by nginx + GitHub Actions deploy)
  GET /metrics  -- Prometheus scrape (proxied from monitoring/metrics_server.py)

Run:
    uvicorn api.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel

from config import QDRANT_URL, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, USE_GROQ

app = FastAPI(title="Meridian API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dependency probes
# ---------------------------------------------------------------------------

def _probe_qdrant() -> tuple[str, int]:
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(
            url=QDRANT_URL,
            check_compatibility=False,
            prefer_grpc=False,
            timeout=10,
        )
        client.get_collections()
        try:
            count = client.count("meridian_fixed", exact=True).count
        except Exception:
            count = -1
        return "connected", count
    except Exception as e:
        return f"error: {e}", -1


def _probe_neo4j() -> tuple[str, int]:
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), connection_timeout=5
        )
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS c")
            count = result.single()["c"]
        driver.close()
        return "connected", count
    except Exception as e:
        return f"error: {e}", -1


def _probe_llm() -> str:
    import os
    deployment = os.getenv("DEPLOYMENT", "local").lower()
    if deployment == "gemini":
        return "gemini"
    if USE_GROQ or deployment == "oracle":
        return "groq"
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return "ollama" if resp.ok else "ollama-unreachable"
    except Exception:
        return "ollama-unreachable"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    qdrant_status, chunk_count = _probe_qdrant()
    neo4j_status, node_count   = _probe_neo4j()
    llm_status                 = _probe_llm()

    overall = "ok" if (
        "connected" in qdrant_status
        and "connected" in neo4j_status
        and llm_status not in ("ollama-unreachable",)
    ) else "degraded"

    return {
        "status":    overall,
        "qdrant":    qdrant_status,
        "neo4j":     neo4j_status,
        "llm":       llm_status,
        "chunks":    chunk_count,
        "neo4j_nodes": node_count,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }


@app.get("/")
def root() -> dict:
    return {"service": "Meridian RAG API", "docs": "/docs", "health": "/health"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class QueryRecord(BaseModel):
    architecture: str
    question_type: str = "unknown"
    latency_ms: float = 0.0
    faithfulness: float = 0.0
    tokens: int = 0
    cost_usd: float = 0.0


@app.post("/record")
def record(q: QueryRecord) -> dict:
    from monitoring.metrics_server import record_query
    record_query(
        architecture=q.architecture,
        question_type=q.question_type,
        latency_ms=q.latency_ms,
        faithfulness=q.faithfulness,
        tokens=q.tokens,
        cost_usd=q.cost_usd,
    )
    return {"status": "ok"}
