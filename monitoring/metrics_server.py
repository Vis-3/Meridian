"""
Meridian — Prometheus metrics server.

Exposes /metrics on port 8000 for Prometheus scraping.
Import record_query() from other modules to instrument architecture runs.

Run standalone:
    python monitoring/metrics_server.py
"""

import time

from prometheus_client import (
    Counter, Histogram, Gauge, start_http_server,
)

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

QUERIES_TOTAL = Counter(
    "meridian_queries_total",
    "Total queries processed",
    ["architecture", "question_type"],
)

RETRIEVAL_CALLS = Counter(
    "meridian_retrieval_calls_total",
    "Total retrieval calls",
    ["retriever_type"],  # dense / sparse / hybrid / graph
)

FAITHFULNESS_FAILURES = Counter(
    "meridian_faithfulness_failures_total",
    "Queries failing faithfulness check",
    ["architecture"],
)

RERETRIEVAL_TOTAL = Counter(
    "meridian_reretrieval_total",
    "Re-retrieval attempts triggered",
    ["architecture"],
)

# ---------------------------------------------------------------------------
# Histograms
# ---------------------------------------------------------------------------

QUERY_LATENCY = Histogram(
    "meridian_query_latency_ms",
    "End-to-end query latency in ms",
    ["architecture"],
    buckets=[100, 500, 1_000, 5_000, 10_000, 30_000, 60_000, 120_000],
)

FAITHFULNESS_SCORE = Histogram(
    "meridian_faithfulness_score",
    "RAGAS faithfulness scores",
    ["architecture", "question_type"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

TOKENS_USED = Histogram(
    "meridian_tokens_used",
    "Tokens used per query",
    ["architecture"],
    buckets=[100, 500, 1_000, 2_000, 5_000, 10_000],
)

COST_PER_QUERY = Histogram(
    "meridian_cost_per_query_usd",
    "Estimated cost per query in USD",
    ["architecture"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1],
)

# ---------------------------------------------------------------------------
# Gauges
# ---------------------------------------------------------------------------

LAST_EVAL_FAITHFULNESS = Gauge(
    "meridian_last_eval_faithfulness",
    "Faithfulness score from last evaluation run",
    ["architecture"],
)

QDRANT_COLLECTION_SIZE = Gauge(
    "meridian_qdrant_chunks_total",
    "Total chunks in Qdrant collection",
    ["collection"],
)

NEO4J_NODE_COUNT = Gauge(
    "meridian_neo4j_nodes_total",
    "Total nodes in Neo4j graph",
    ["node_type"],
)


# ---------------------------------------------------------------------------
# Public instrumentation function
# ---------------------------------------------------------------------------

def record_query(
    architecture: str,
    question_type: str,
    latency_ms: float,
    faithfulness: float,
    tokens: int,
    cost_usd: float = 0.0,
    faithfulness_threshold: float = 0.7,
) -> None:
    """Call this after each architecture.run() to update all metrics."""
    QUERIES_TOTAL.labels(
        architecture=architecture,
        question_type=question_type,
    ).inc()

    QUERY_LATENCY.labels(architecture=architecture).observe(latency_ms)

    FAITHFULNESS_SCORE.labels(
        architecture=architecture,
        question_type=question_type,
    ).observe(faithfulness)

    TOKENS_USED.labels(architecture=architecture).observe(tokens)

    COST_PER_QUERY.labels(architecture=architecture).observe(cost_usd)

    if faithfulness < faithfulness_threshold:
        FAITHFULNESS_FAILURES.labels(architecture=architecture).inc()


def update_collection_size(collection: str, count: int) -> None:
    QDRANT_COLLECTION_SIZE.labels(collection=collection).set(count)


def update_neo4j_counts(node_counts: dict[str, int]) -> None:
    for node_type, count in node_counts.items():
        NEO4J_NODE_COUNT.labels(node_type=node_type).set(count)


def update_last_faithfulness(architecture: str, score: float) -> None:
    LAST_EVAL_FAITHFULNESS.labels(architecture=architecture).set(score)


# ---------------------------------------------------------------------------
# Standalone server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = 8000
    start_http_server(port)
    print(f"Meridian metrics server running on :{port}/metrics")
    print("Press Ctrl+C to stop.")
    while True:
        time.sleep(1)
