# Meridian Engineering Log

Chronological record of significant issues encountered during development and how each was resolved.

---

## Issue 001 — SEC EDGAR downloader returning wrong results
**Date:** 2026-05  
**Phase:** Data ingestion  
**Symptom:** EFTS search API returning random matches instead of targeted 10-K filings for specific companies.  
**Root cause:** EFTS search endpoint is designed for full-text search, not targeted filing lookup. Wrong API for the job.  
**Solution:** Switched to Submissions API (`data.sec.gov/submissions/CIK{}.json`) which returns structured filing history per company. Parse filing index to get exact document URLs.  
**Impact:** 100/100 filings downloaded correctly.  
**Lesson:** SEC EDGAR has multiple APIs with different purposes. Submissions API is the correct endpoint for programmatic filing retrieval.

---

## Issue 002 — SEC filings are HTML not PDF
**Date:** 2026-05  
**Phase:** Data ingestion  
**Symptom:** Downloader saving .pdf extension but files were actually HTML. Extractor (PDF-only) failing.  
**Root cause:** SEC EDGAR primary documents are filed as .htm. PDF versions exist but are not the primary filing and have inconsistent availability.  
**Solution:** Updated downloader to save .htm files with correct extension. Updated extractor to detect file extension and route to HTML parser (BeautifulSoup) vs PDF parser (PyMuPDF).  
**Impact:** All 100 documents extracted successfully.  
**Lesson:** Always verify actual file format before building a parsing pipeline. File extensions in URLs are not always reliable.

---

## Issue 003 — Item 1A missing from corpus stats (false alarm)
**Date:** 2026-05  
**Phase:** Corpus validation  
**Symptom:** `corpus_stats.py` reported Item 1A coverage 0/100 (0.0%). Risk Factors section apparently missing from all 100 documents.  
**Root cause:** Bug in `corpus_stats.py` section matching logic, not in the extractor. The matching loop checked `"Item 1A".startswith("Item 1")` which evaluated True, counting all Item 1A sections as Item 1 and breaking before reaching the Item 1A check. TARGET_SECTIONS list was ordered shortest-first.  
**Solution:** Reordered TARGET_SECTIONS longest-first (`["Item 1A", "Item 1", "Item 7", "Item 8"]`) so specific patterns match before general ones.  
**Impact:** Item 1A confirmed 100% coverage (avg 11,654 words per document).  
**Lesson:** Validate the validator. A stats script reporting zero coverage should trigger investigation of the script before assuming the data is wrong. String prefix matching on overlapping keys requires length-ordered matching.

---

## Issue 004 — Retrieval missing Apple revenue figure
**Date:** 2026-05  
**Phase:** Retrieval audit  
**Symptom:** Test 1 failed — query "Apple total revenue fiscal year 2023" did not return the chunk containing $383,285M in top-1 across dense, sparse, and hybrid retrieval.  
**Root cause:** Apple's 10-K uses "net sales" not "revenue". Semantic gap between query language and filing terminology caused the correct chunk to rank outside top-1.  
**Solution:** Implemented pre-retrieval synonym expansion dict mapping common financial query terms to SEC filing terminology. `"revenue"` → `["net sales", "total sales", "total net sales"]`. Up to 4 query variants fused via multi-list RRF.  
**Impact:** Test 1 passed. Synonym expansion also improved Test 3 Microsoft R&D retrieval.  
**Lesson:** Financial domain has strict terminology. SEC filings use specific accounting terms that differ from natural language queries. Domain-specific synonym expansion is necessary, not optional.

---

## Issue 005 — Microsoft missing from comparative R&D retrieval
**Date:** 2026-05  
**Phase:** Retrieval audit  
**Symptom:** Test 3 failed — comparative query for R&D expense across all 5 companies returned Google, Apple, Amazon, and Meta but not Microsoft in top-10 results.  
**Root cause:** Score compression in RRF (all scores ~0.015). Microsoft R&D chunks exist (58 confirmed in index) but lose to Google/Apple chunks with marginally better embedding similarity on the specific query phrasing.  
**Solution:** Implemented `hybrid_search_balanced()` — retrieves top-k per company independently then merges. Guarantees representation from every company for comparative queries. Documented as ADR-001.  
**Impact:** Test 3 passed. Balanced retrieval used for all comparative and multi_hop question types.  
**Lesson:** Standard RRF on multi-company queries can silently miss companies. Score compression at the RRF output layer hides per-company retrieval failures. Per-company retrieval is the correct design for comparative questions.

---

## Issue 006 — Windows encoding crash in results_analyzer
**Date:** 2026-05  
**Phase:** Evaluation framework  
**Symptom:** `results_analyzer.py` crashed on Windows with encoding error on two characters: `≥` (Unicode ≥) and `—` (em-dash).  
**Root cause:** Windows default console encoding cp1252 cannot represent these Unicode characters. Linux/Mac default UTF-8 handles them fine.  
**Solution:** Replaced `≥` with `>=` and `—` with `--` in all print statements. Added UTF-8 encoding fix step to GitHub Actions Windows runner.  
**Impact:** All 91 tests passing on both Ubuntu and Windows in CI matrix.  
**Lesson:** Develop with cross-platform encoding in mind. Unicode characters in print statements work on Mac/Linux but silently break on Windows. The CI matrix catches this before production.

---

## Issue 007 — Hierarchical RAG requires 50-minute offline build
**Date:** 2026-05  
**Phase:** Architecture implementation  
**Symptom:** Hierarchical RAG smoke test would have required generating LLM summaries for 100 documents inline — estimated 50 minutes blocking the test run.  
**Root cause:** Hierarchical RAG design requires one summary per document as an offline index. Generating summaries at query time defeats the purpose of the architecture.  
**Solution:** Split into offline build script (`scripts/build_summary_index.py`, checkpointed every 10 docs) and online query (reads from pre-built `meridian_summaries` Qdrant collection). Crash-safe: restarts skip already-summarized documents.  
**Impact:** Zero generation overhead at query time. Summary index built once, reused for all queries.  
**Lesson:** Distinguish between index build time and query time costs early in architecture design. Offline preprocessing is always preferable to inline generation for static corpora.

---

## Issue 008 — Chunk count imbalance across companies
**Date:** 2026-05  
**Phase:** Corpus validation  
**Symptom:** Meta has 2,446 chunks vs Apple's 763 — a 3.2× difference. Risk: comparative queries without explicit company filters over-retrieve Meta content.  
**Root cause:** Meta's FY2024 10-K is 76,907 words (largest document in corpus) vs Apple's average ~18,000 words for annual filings. Meta files more verbose disclosures.  
**Solution:** `hybrid_search_balanced()` enforces per-company top-k for comparative question types, preventing chunk-count bias from affecting results. Documented in `known_limitations.md`.  
**Impact:** Comparative retrieval balanced. Limitation documented for benchmark interpretation.  
**Lesson:** Corpus imbalance is a retrieval bias source that's invisible without explicit measurement. Always compute per-source chunk distribution before building retrieval on top of it.

---

## Issue 009 — Agentic re-retrieval triggered on comparative query
**Date:** 2026-05  
**Phase:** Architecture smoke testing  
**Symptom:** During agentic smoke test, comparative R&D query failed faithfulness check on first attempt (faithfulness_proxy=0.60, threshold=0.70). Re-retrieval triggered automatically.  
**Root cause:** First retrieval returned chunks with insufficient cross-company coverage. Generated answer contained claims not fully supported by retrieved context.  
**Solution:** Re-retrieval with broader query scope succeeded (faithfulness_proxy=1.00). Max 2 retries cap prevents infinite loops on genuinely unanswerable questions.  
**Impact:** System self-corrected without human intervention. Retry mechanism working as designed.  
**Lesson:** Self-correcting RAG loops are worth the implementation complexity. A single retry recovered a failed faithfulness check on a genuinely hard query type. Cap retries to prevent runaway costs.

---

## Issue 010 — Graph RAG Neo4j container not running
**Date:** 2026-05  
**Phase:** Architecture smoke testing  
**Symptom:** `graph_rag` smoke test showed `neo4j_active=False`, `graph_results=0`. Architecture silently fell back to vector retrieval.  
**Root cause:** Neo4j Docker container was not running at time of first smoke test. No `docker-compose.yml` existed — Qdrant had been started manually in a prior session.  
**Solution:** Created `docker-compose.yml` covering both Qdrant and Neo4j. Ran `docker compose up neo4j -d`, waited for healthy status, ran `graph/loader.py` to populate graph, re-ran smoke test. `neo4j_active=True`, `graph_results=5`.  
**Impact:** Graph RAG fully operational. Fallback behavior (vector-only when Neo4j is down) confirmed working as designed per ADR-004.  
**Lesson:** Always verify external service dependencies are running before smoke testing components that depend on them. Graceful fallback is correct design but can mask infrastructure issues during development.

---

## Issue 011 — Naive RAG wrong year from financial table
**Date:** 2026-05  
**Phase:** Initial evaluation  
**Symptom:** Naive RAG returned $23.2B for Meta FY2023 net income (correct: $39.1B). Retrieved chunk contained a multi-year comparison table with both figures.  
**Root cause:** Dense financial tables present multiple years in the same chunk. Naive RAG has no mechanism to identify which column corresponds to which year. LLM parsed wrong column from the table.  
**Solution:** This is a known limitation of naive RAG on tabular financial data. Higher architectures (hybrid with reranker, corrective, graph) handle this better by filtering chunks and providing more targeted context.  
**Expected impact on benchmark:** Naive RAG will score lower on numerical_reasoning questions involving multi-year comparison tables. This is a genuine architectural weakness, not a data or retrieval bug. Documents the core value of the benchmark.  
**Lesson:** Financial tables require special handling. Chunk boundaries that preserve single-year context would reduce this error. Documented in known_limitations.md as limitation 3 (table chunking).

---

## Issue 012 — meridian_semantic collection never built
**Date:** 2026-05  
**Phase:** Evaluation run  
**Symptom:** hybrid_rag initialization logged 404 for meridian_semantic collection. Hybrid fell back to meridian_fixed (fixed chunking).  
**Root cause:** build_semantic_index.py was never created or run. Only fixed chunking index was built during ingestion setup.  
**Impact:** hybrid_rag and naive_rag use identical chunk index. Hybrid's advantage comes only from BM25+dense fusion and reranking, not semantic chunking.  
**Solution:** Create and run scripts/build_semantic_index.py after current evaluation completes. Re-run hybrid evaluation after semantic index is built.  
**Lesson:** Validate all index dependencies before starting evaluation run. Add index existence check to architecture __init__ that fails loudly rather than silently falling back.

---

## Issue 016 — Gemini model availability varies by account
**Date:** 2026-05
**Phase:** Evaluation setup
**Symptom:** gemini-2.0-flash, gemini-2.0-flash-lite, gemini-2.0-flash-001 all return 404 NOT_FOUND.
Listed in model catalog but not available to new users.
**Root cause:** Google restricts older Gemini 2.0 models to existing users. New accounts only get 2.5+ models.
**Solution:** Test all candidate models with a live generate_content call before hardcoding in config.
Selected gemini-2.5-flash-lite for RAGAS scoring — confirmed working, non-thinking, fast.
**Lesson:** Always test model availability programmatically. Model catalog listing does not guarantee access.

---

## Issue 017 — Windows cp1252 encoding breaks RAGAS Unicode output
**Date:** 2026-05
**Phase:** RAGAS evaluation
**Symptom:** charmap codec can't encode character '→' (→ arrow) in RAGAS intermediate output. All RAGAS metric jobs fail with encoding error on Windows.
**Root cause:** RAGAS writes intermediate results containing Unicode characters. Windows default encoding cp1252 cannot represent U+2192 and similar characters.
**Solution:** Force UTF-8 via PYTHONUTF8=1 environment variable and explicit stdout/stderr reconfiguration at the top of run_batch_evaluation.py and ragas_runner.py. Also added PYTHONUTF8=1 to .env and ci.yml.
**Lesson:** Set PYTHONUTF8=1 globally for any Python project using Unicode on Windows. Third-party libraries (RAGAS, rich, tqdm) routinely use Unicode in output — cp1252 will silently break them.

---

## Issue 018 — Neo4j Aura free tier hibernates and rejects SSL connections
**Date:** 2026-05
**Phase:** Batch evaluation re-run
**Symptom:** Graph RAG returned `neo4j_active=False` during batch evaluation. Connection error: "Unable to retrieve routing information" with SSL verification failure.
**Root cause:** Neo4j Aura free tier hibernates after ~3 days of inactivity. URI was `neo4j+s://` which uses strict SSL verification. After waking the instance via the Aura console, the SSL cert chain still rejected the connection.
**Solution:** Changed URI scheme from `neo4j+s://` to `neo4j+ssc://` in `.env`. The `+ssc` scheme disables SSL certificate verification while still using an encrypted channel.
**Impact:** Graph RAG reconnected successfully. Neo4j populated: 401 nodes, 1,498 relationships.
**Lesson:** Aura free tier hibernation is silent and appears as a network error, not a "database paused" error. Always wake the Aura instance via the web console before running evaluations. `neo4j+ssc` is appropriate for development; production should use proper cert management.

---

## Issue 019 — Corrective RAG wins cost-quality despite being the slowest architecture
**Date:** 2026-05
**Phase:** Benchmark analysis
**Symptom / Surprise:** Expected corrective to score poorly on cost-quality due to N+1 LLM calls for chunk scoring. Instead, corrective had the lowest cost per query ($0.1015/1k vs naive $0.1267/1k) and won cost-quality (0.6643) on 5/6 question types.
**Root cause:** Corrective's chunk relevance scoring **filters low-quality chunks before the generation step**. This reduces average LLM input tokens by approximately 18% compared to naive, which passes all retrieved chunks verbatim. The N+1 scoring calls use short prompts (classify relevance) while the generation call benefits from the reduced context.
**Impact:** Corrective is the recommended architecture for batch/offline pipelines where latency is not a constraint. Its production score (0.5327) is lowest due to 99s P50 retrieval, but cost-quality (0.6643) is highest.
**Lesson:** Context filtering that reduces LLM input tokens can more than offset the cost of additional classification calls, especially when the classification prompt is much shorter than the generation prompt.

---

## Issue 020 — Efficiency router degenerates to always-naive
**Date:** 2026-05
**Phase:** MeridianRouter design
**Symptom:** MeridianRouter (efficiency mode) routing table shows all 6 question types routing to naive.
**Root cause:** Naive's 66ms P50 retrieval latency is 21× faster than the next-fastest architecture (graph, 1,399ms) and 1,504× faster than the slowest (corrective, 99,235ms). The efficiency metric (quality / log10(P50+1)) gives naive a score of 0.3683 vs. 0.2126 for graph — an insurmountable gap. No other architecture can win any type on this metric.
**Design decision:** This degeneracy is documented and intentional. Running MeridianRouter (efficiency mode) is equivalent to running naive directly. The mode is retained in the API for completeness and for future use if faster architectures are added to the benchmark.
**Lesson:** Multi-dimension optimisation can degenerate to a single-dimension winner when one dimension has extreme range. The efficiency metric as formulated rewards the lowest-latency architecture regardless of quality differences.

---

## Issue 021 — Full System pre-benchmark routing was suboptimal
**Date:** 2026-05
**Phase:** Benchmark analysis
**Symptom:** Full System (Architecture 7) scores 0.6524 quality — lower than naive (0.6738) despite having access to all architectures.
**Root cause:** Full System routing table was designed by intuition before running any benchmarks: numerical→agentic, temporal→agentic, comparative→fusion, multi_hop→graph, risk_qualitative→corrective. Benchmark results show only **1 of 6 routes was optimal** (simple_factual→hierarchical). Specifically: numerical should be hierarchical (not agentic), temporal should be fusion (not agentic), comparative should be graph (not fusion), multi_hop should be hybrid (not graph), risk_qualitative should be naive (not corrective).
**Solution:** Created `architectures/meridian_router.py` with benchmark-validated routing tables and 4 operating modes. Updated `config.py` `BEST_ARCH_PER_TYPE` is unchanged (used by full_system only); meridian_router uses its own validated tables.
**Lesson:** Intuition-based routing is unreliable. Run the benchmark first, then derive the routing table from empirical per-type winners.

---

## Issue 022 — BERTScore fails with system Python (transformers 4.57.x)
**Date:** 2026-05
**Phase:** Metrics evaluation
**Symptom:** `bert_score` package (0.3.13) throws `ModuleNotFoundError: Could not find DistilBertModel` when run with the system Python (transformers 4.57.6). BERTScore produces `None` for all architectures.
**Root cause:** `transformers 4.57.x` restructured internal model loading. The `bert_score` package was built against an older transformers API. Running against the system Python (which has 4.57.6) triggers the incompatibility. The venv has a compatible transformers version.
**Solution:** Always run evaluation scripts with `venv/Scripts/python.exe` (not bare `python`). `venv/Scripts/python.exe evaluation/metrics_reliable.py` works correctly.
**BERTScore results:** Tightly clustered (0.810–0.820) across all 8 architectures. Confirms architectures produce semantically equivalent answers; BERTScore is treated as a reference metric, not included in composite score weights.
**Lesson:** Always specify the venv interpreter for all evaluation runs. Add a check in the batch script that warns if the venv is not active.
