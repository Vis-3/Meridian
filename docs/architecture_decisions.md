# Architecture Decisions

## ADR-001: Balanced Retrieval for Comparative Queries
**Date:** 2026-05  
**Status:** Implemented

**Context:** Standard hybrid retrieval on comparative queries missed Microsoft R&D chunks despite 58 relevant chunks existing in the index. Score compression in RRF (all scores ~0.015) caused Google/Apple chunks to outrank Microsoft because their filing language happened to be closer to the query phrasing.

**Decision:** Implement `hybrid_search_balanced()` — retrieve top-k per company independently, then merge. Guarantees all-company representation for comparative and multi-hop queries.

**Consequence:** Higher retrieval cost (N × top-k calls vs 1). Acceptable for comparative queries which are explicitly multi-company by design.

---

## ADR-002: Synonym Expansion Before Retrieval
**Date:** 2026-05  
**Status:** Implemented

**Context:** Apple uses "net sales" not "revenue" in 10-K filings. Query "Apple total revenue 2023" failed to rank the correct chunk top-1 on both dense and sparse retrieval. The chunk existed — the ranking failed due to vocabulary mismatch between natural query language and SEC filing terminology.

**Decision:** Pre-retrieval synonym expansion dict mapping common financial query terms to SEC filing terminology. Terms: revenue→net sales, R&D→research and development, profit→income/earnings, employees→headcount/FTE.

**Consequence:** Query expansion increases retrieval calls (up to 4 variants). Tradeoff: recall improvement outweighs latency cost for the financial domain.

---

## ADR-003: Hierarchical Summary Index Built Offline
**Date:** 2026-05  
**Status:** Implemented

**Context:** Hierarchical RAG requires one LLM summary per document. 100 documents × 30s = ~50 mins one-time cost. Generating summaries inline at query time is unacceptable for a benchmarking system.

**Decision:** Build summary index offline via `scripts/build_summary_index.py` with checkpointing every 10 docs. Query time reads from pre-built `meridian_summaries` Qdrant collection — zero generation overhead at query time.

**Consequence:** One-time setup cost. Summary quality bounded by Ollama llama3.1:8b. Acceptable for benchmarking purposes.

---

## ADR-004: Graph RAG Falls Back to Vector on Neo4j Failure
**Date:** 2026-05  
**Status:** Implemented

**Context:** Neo4j may be unavailable (container down, connection timeout). Hard failure would break a benchmark run mid-way through 325 questions.

**Decision:** `graph_rag.py` detects Neo4j connection at init. If unavailable: logs warning, sets `neo4j_active=False`, falls back to hybrid vector retrieval. Result schema is unchanged.

**Consequence:** graph_rag result is indistinguishable from hybrid_rag when Neo4j is down. Logged in result JSON so benchmark analysis can flag affected results.

---

## ADR-005: CRAG Web Search Flagged, Not Executed
**Date:** 2026-05  
**Status:** Implemented

**Context:** Corrective RAG calls for web search when all retrieved chunks score below 0.5 threshold. No web search API is configured in this environment.

**Decision:** When all chunks fall below threshold, set `needs_web_search=True` in the result JSON and proceed with the lowest-scoring chunks rather than failing. Logged clearly.

**Consequence:** CRAG performance is understated in cases where web search would have helped. Documented limitation.

---

## ADR-006: Agentic Re-retrieval Capped at 2 Retries
**Date:** 2026-05  
**Status:** Implemented

**Context:** The faithfulness check can fail repeatedly if retrieval quality is fundamentally poor for a query. Unlimited retries would cause infinite loops on hard questions.

**Decision:** Max 2 retries. After 2 failed faithfulness checks, return the best answer from available chunks with `low_confidence=True` flag in result.

**Consequence:** Some agentic answers marked `low_confidence`. Acceptable — better than hanging or crashing.
