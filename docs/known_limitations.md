# Known Limitations

## Retrieval

**1. Score compression in RRF**  
All hybrid scores cluster near 0.015 on cross-company queries. RRF rank fusion normalizes absolute scores away, so small embedding distance differences dominate ranking. Mitigation: balanced retrieval for comparative queries.

**2. SEC filing terminology mismatch**  
Apple uses "net sales", Microsoft uses "research and development", Amazon uses "technology and infrastructure" for R&D. Natural language queries using standard financial terms fail to surface the correct chunks without synonym expansion. Mitigation: synonym expansion dict (12 terms covered).

**3. Table chunking**  
Financial tables in Item 8 are extracted as text but chunk boundaries may split mid-table. Numbers that span multiple rows may not appear in a single chunk. Known impact: simple factual queries on exact figures may retrieve adjacent context rather than the number itself.

**10. Chunk count imbalance** — Meta has 3.2× more chunks than Apple (2,446 vs 763) due to Meta's 10-K being the largest document (76,907 words vs Apple's average ~18,000 words for annual filings). This creates a retrieval bias: comparative queries without company filters will over-retrieve Meta chunks. Mitigation: `hybrid_search_balanced()` enforces per-company top-k for comparative question types.

**4. 10-Q vs 10-K depth**  
Quarterly filings are shorter and contain less narrative than annual filings. Retrieval may prefer 10-Q chunks for some queries even when 10-K chunks are more authoritative.

## Graph RAG

**5. Azure revenue not separately disclosed**  
Microsoft reports Azure as a growth percentage only, not as an absolute revenue figure. Graph and vector retrieval correctly return "cannot find explicit figure" — this is accurate, not a retrieval failure.

**6. Graph populated from extracted text**  
Entity and relationship extraction uses keyword matching against `KEY_TOPICS`. Coverage is limited to the 14 predefined topics. Named entities outside this list (e.g. specific product names, executive names) are not represented in the graph.

## Evaluation

**7. Risk qualitative ground truths are placeholders**  
50 qualitative questions have `ground_truth=None`. RAGAS `answer_correctness` cannot be computed for these. Faithfulness, relevancy, and `keyword_hit_rate` are computed instead. `answer_correctness` is reported as null.

**8. Ollama cold start**  
First query per session incurs model load time (~20s). Benchmark latency figures reflect a warm model (subsequent queries). Cold start latency is documented in `smoke_test_summary.json` and excluded from P50/P95/P99 calculations.

**9. Local LLM ceiling**  
llama3.1:8b has lower reasoning capability than GPT-4 or Claude 3.5. RAGAS scores are relative comparisons between architectures on the same LLM — not absolute quality benchmarks against production systems. Architecture ranking is expected to hold across stronger models; absolute scores will improve.
