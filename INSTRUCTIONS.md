# Meridian — Project Instructions
## Financial Document Intelligence & RAG Architecture Benchmarking System

> **Note for new sessions:** Read this file first, then read all existing files in the project before writing anything new. Start with `config.py` and `data/evaluation/facts.py` to understand the structure already in place.

---

## One-Line Description
Benchmarks 8 RAG architectures on 125 SEC filings (2020–2024) across 5 companies, measuring faithfulness, relevancy, precision, recall, and latency on 325 hand-labeled financial Q&A pairs spanning COVID impact, supply chain disruption, and AI investment cycles.

---

## Business Problem
Financial analysts spend hours manually searching 10-K and 10-Q filings to answer questions about revenue trends, risk factors, segment performance, and cross-company comparisons. Meridian automates that retrieval and systematically evaluates which RAG architecture performs best for each question type.

---

## Corpus

```python
COMPANIES = ["Apple", "Microsoft", "Google", "Amazon", "Meta"]
YEARS     = [2020, 2021, 2022, 2023, 2024]

CIK_MAP = {
    "Apple":     "0000320193",
    "Microsoft": "0000789019",
    "Google":    "0001652044",
    "Amazon":    "0001018724",
    "Meta":      "0001326801",
}

# Document breakdown
# 10-K : 5 companies × 5 years = 25 annual filings
# 10-Q : 5 companies × 5 years × 3 quarters = 75 quarterly filings
# Total: 100 documents
# Estimated chunks: ~160,000–180,000
```

### Fiscal Year Awareness — Critical

| Company | FY End | Example |
|---|---|---|
| Apple | September | FY2024 = Oct 2023 – Sep 2024, filed Oct 2024 |
| Microsoft | June | FY2024 = Jul 2023 – Jun 2024, filed Jul 2024 |
| Google | December | FY2024 = Jan – Dec 2024 |
| Amazon | December | FY2024 = Jan – Dec 2024 |
| Meta | December | FY2024 = Jan – Dec 2024 |

Every chunk must carry both `fiscal_year` and `calendar_year_filed` in its metadata. Temporal and comparative queries will silently return wrong results if fiscal year mapping is wrong.

### Source
SEC EDGAR full-text search API (free, no auth required).

---

## Project Structure

```
Meridian/
├── data/
│   ├── raw/                        # raw PDFs from SEC EDGAR
│   ├── processed/                  # extracted text, tables, chunks
│   ├── indexes/                    # persisted BM25 indexes
│   └── evaluation/
│       ├── facts.py                # verified financial facts table
│       ├── generate_questions.py   # generates questions.json
│       ├── questions.json          # 325 hand-labeled Q&A pairs
│       └── results/                # RAGAS results per architecture
├── ingestion/
│   ├── downloader.py               # SEC EDGAR PDF downloader + S3 upload
│   ├── s3_client.py                # AWS S3 boto3 wrapper
│   ├── extractor.py                # PySpark parallel PDF extraction + benchmark
│   ├── metadata.py                 # fiscal year resolver + chunk metadata builder
│   └── chunkers/
│       ├── fixed.py                # 512-token fixed chunking, 50-token overlap
│       ├── semantic.py             # sentence-transformers cosine similarity chunking
│       ├── recursive.py            # recursive character splitting
│       └── parent_child.py         # 256-token retrieval / 1024-token return
├── retrieval/
│   ├── dense.py                    # sentence-transformers embeddings + Qdrant
│   ├── sparse.py                   # BM25 via rank_bm25
│   ├── hybrid.py                   # RRF fusion of BM25 + dense
│   ├── reranker.py                 # BGE cross-encoder reranker
│   └── graph/
│       ├── builder.py              # entity + relationship extraction → Neo4j
│       ├── queries.py              # Cypher query templates
│       └── hybrid_graph.py         # merge graph results + vector chunks
├── architectures/
│   ├── base.py                     # abstract RAGArchitecture class
│   ├── naive.py                    # Level 0 — fixed chunks + dense only
│   ├── hybrid_rag.py               # Level 1 — semantic + BM25+dense + reranker
│   ├── fusion_rag.py               # Level 2 — 4 query variants + RRF merge
│   ├── hierarchical_rag.py         # Level 3 — summary index + chunk index
│   ├── corrective_rag.py           # Level 4 — CRAG with retrieval evaluator
│   ├── graph_rag.py                # Level 5 — Neo4j + vector hybrid
│   ├── agentic_rag.py              # Level 6 — LangGraph state machine
│   └── full_system.py              # Level 7 — best architecture per query type
├── evaluation/
│   ├── ragas_runner.py             # runs RAGAS on all architectures
│   ├── metrics.py                  # latency P50/P95/P99, cost, citation accuracy
│   └── results_analyzer.py         # comparison tables + charts
├── graph/
│   ├── schema.py                   # Neo4j node/relationship definitions
│   ├── extractor.py                # NER (spaCy) + LLM relationship extraction
│   └── loader.py                   # idempotent bulk load to Neo4j
├── agents/
│   ├── langgraph_agent.py          # LangGraph state machine (Level 6)
│   ├── tools.py                    # all retrieval tools the agent can call
│   ├── router.py                   # query classifier
│   └── reflector.py                # faithfulness check + re-retrieval loop
├── llm/
│   ├── ollama_client.py            # Llama 3.1 8B via Ollama
│   ├── prompts.py                  # ALL prompt templates (never inline elsewhere)
│   └── generator.py                # generation with citation tracking
├── monitoring/
│   ├── prometheus_metrics.py       # custom Prometheus metrics
│   └── grafana/
│       ├── dashboards/             # Grafana dashboard JSON
│       └── provisioning/           # datasource config
├── dashboard/
│   └── app.py                      # Streamlit — 4 tabs
├── tests/
│   ├── test_chunkers.py
│   ├── test_metadata_resolver.py
│   ├── test_retrieval.py
│   ├── test_ragas_runner.py
│   └── test_graph.py
├── .github/
│   └── workflows/
│       └── ci.yml                  # GitHub Actions CI pipeline
├── logs/                           # runtime logs + extraction_benchmark.json
├── config.py                       # ALL paths, thresholds, model names
├── docker-compose.yml              # Qdrant + Neo4j + Ollama + app + Prometheus + Grafana
├── requirements.txt
├── INSTRUCTIONS.md                 # this file
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| PDF extraction | PyMuPDF (fitz) — NOT pdfplumber |
| Parallel processing | PySpark (`local[*]`) |
| Cloud storage | AWS S3 (boto3) — free tier 12 months |
| Embeddings | sentence-transformers: `all-MiniLM-L6-v2` (chunking), `BAAI/bge-large-en-v1.5` (retrieval) |
| Sparse retrieval | rank_bm25 |
| Vector store | Qdrant (Docker) |
| Graph DB | Neo4j (Docker) |
| Re-ranker | BAAI/bge-reranker-base |
| LLM | Llama 3.1 8B via Ollama (local, no API key) |
| Agent framework | LangGraph |
| Evaluation | RAGAS |
| NER | spaCy `en_core_web_trf` + LLM for relationships |
| Dashboard | Streamlit |
| Monitoring | Prometheus + Grafana |
| Testing | pytest |
| CI | GitHub Actions |
| Orchestration | Docker Compose |

---

## AWS S3 Storage Layout

```
s3://meridian-raw/
  {company}/{year}/{doctype}/{filename.pdf}
  e.g. Apple/2024/10-K/apple_2024_10k.pdf

s3://meridian-processed/
  {company}/{year}/{doctype}/{filename.json}
  e.g. Apple/2024/10-K/apple_2024_10k.json
```

Local disk is used only for Qdrant and Neo4j persistence.

---

## Chunk Metadata Schema

Every chunk in every retriever carries this exact dict:

```python
{
    "chunk_id":            "apple_2024_10k_item1a_chunk_0047",
    "parent_id":           "apple_2024_10k_item1a_parent_0012",  # None if not parent-child
    "company":             "Apple",
    "fiscal_year":         2024,
    "calendar_year_filed": 2024,
    "document_type":       "10-K",    # or "10-Q"
    "quarter":             None,       # "Q1"/"Q2"/"Q3" for 10-Q, None for 10-K
    "period_start_date":   "2023-09-29",
    "period_end_date":     "2024-09-28",
    "section":             "Item 1A",
    "page_range":          [14, 28],
    "document_path":       "apple_2024_10k.pdf",
}
```

---

## Question Set — 325 Questions

### Distribution

| Type | Count | Description |
|---|---|---|
| `simple_factual` | 50 | Single company, single year, direct lookup |
| `numerical_reasoning` | 50 | Requires computing ratios, growth rates, margins |
| `temporal` | 60 | Single company, all 5 years, trend analysis |
| `comparative` | 60 | Multiple companies, same period, ranked comparison |
| `multi_hop` | 55 | Two conditions joined across sections or documents |
| `risk_qualitative` | 50 | Qualitative reasoning over risk factors and MD&A |
| **Total** | **325** | ~30 tagged `covid_related: true` across all types |

### Question JSON Schema

```json
{
    "id":                "temporal_023",
    "type":              "temporal",
    "question":          "How did Apple's gross margin evolve from 2020 to 2024?",
    "ground_truth":      "Apple's gross margin improved from 38.2% in FY2020 to 46.2% in FY2024...",
    "companies":         ["Apple"],
    "years":             [2020, 2021, 2022, 2023, 2024],
    "requires_table":    true,
    "requires_multi_hop":false,
    "requires_graph":    false,
    "covid_related":     false,
    "difficulty":        "medium",
    "sections_needed":   ["Item 8", "Item 7"]
}
```

### Generation Rules
- Import all facts from `data/evaluation/facts.py`
- Import qualitative ground truths from `data/evaluation/qualitative_ground_truths.py`
- Use `yoy_growth(company, metric, year)` and `covid_delta(company, metric)` helpers
- Skip any template where required fact field is `None` or missing — no unknown ground truths
- `Meta FY2024 family_map_millions` is `None` by design — skip templates using it for FY2024
- Print progress every 50 questions
- Difficulty: single lookup = easy, one computation = medium, two conditions or trend = hard
- **COVID bump rule:** any question with `covid_related=True` gets difficulty bumped one level (easy→medium, medium→hard)
- **Shuffle before trim:** shuffle within each type before trimming to the cap — ensures random sample, not alphabetical
- **Qualitative ground truths:** stored as placeholders in `qualitative_ground_truths.py`, filled after document extraction. Format:
  ```python
  {
    "id": "Q1_Apple_2021",
    "ground_truth_placeholder": "Look for: semiconductor shortages, COVID disruptions, Asia-Pacific manufacturing, single-source suppliers in Item 1A",
    "ground_truth": None   # filled after doc extraction
  }
  ```
- The generator asserts `ground_truth is None` ONLY for qualitative placeholder entries — all other types must have real ground truths

### End-of-Generation Validation (assert all of these)
```python
assert len(questions) == 325
assert all(
    q["ground_truth"] is not None
    for q in questions
    if q["type"] != "risk_qualitative"
)
# Print breakdown:
# - count per type          (6 rows)
# - count per company       (5 rows)
# - count per year          (5 rows)
# - count per difficulty    (3 rows)
# - covid_related count
# - requires_graph count
# - requires_table count
```

---

## All 8 RAG Architectures

### Base Class (mandatory interface)

```python
from abc import ABC, abstractmethod

class RAGArchitecture(ABC):
    name:        str
    description: str

    @abstractmethod
    def retrieve(self, query: str, filters: dict) -> list[dict]:
        pass

    @abstractmethod
    def generate(self, query: str, chunks: list[dict]) -> dict:
        # must return: answer, citations, confidence, tokens_used, latency_ms
        pass

    def query(self, question: str) -> dict:
        # standardised response schema — see below
        pass
```

### Standardised Response Schema

Every architecture, every query returns:

```python
{
    "answer":           str,
    "citations":        list[dict],
    "faithfulness":     float,    # 0-1
    "relevancy":        float,    # 0-1
    "latency_ms":       float,
    "tokens_used":      int,
    "architecture_name":str,
}
```

### Architecture Levels

| Level | Name | Key Feature |
|---|---|---|
| 0 | `naive.py` | Fixed chunks + dense retrieval only |
| 1 | `hybrid_rag.py` | Semantic chunks + BM25+dense hybrid + BGE reranker + parent-child return |
| 2 | `fusion_rag.py` | 4 LLM query variants + RRF merge across all result sets |
| 3 | `hierarchical_rag.py` | Document summary index → filter chunk retrieval to top-3 docs |
| 4 | `corrective_rag.py` | CRAG — LLM scores each chunk 0-1, filters low-relevance, optional web fallback |
| 5 | `graph_rag.py` | Query classifier → Neo4j Cypher OR vector retrieval → merged context |
| 6 | `agentic_rag.py` | LangGraph state machine with classify→plan→retrieve→compress→generate→check loop |
| 7 | `full_system.py` | Routes each query type to its best architecture |

### Query Type → Best Architecture Routing (Level 7)

```python
BEST_ARCH_PER_TYPE = {
    "simple_factual":   "hierarchical",
    "numerical":        "agentic",
    "temporal":         "agentic",
    "comparative":      "fusion",
    "multi_hop":        "graph",
    "risk_qualitative": "corrective",
}
```

---

## LangGraph Agent State (Level 6)

```python
class AgentState(TypedDict):
    query:             str
    query_type:        str       # simple/temporal/comparative/multi_hop/numerical/risk
    plan:              list[str]
    retrieved_chunks:  list
    graph_results:     dict
    draft_answer:      str
    faithfulness_score:float
    retry_count:       int
    final_answer:      str
    citations:         list
    tokens_used:       int
    latency_ms:        float
```

### Agent Nodes and Edges

```
classify_query → plan_retrieval
plan_retrieval → retrieve_vector / retrieve_graph / retrieve_multi_doc / calculate
retrieve → compress_context → generate_answer
generate_answer → check_faithfulness
check_faithfulness → END (score ≥ 0.7)
                   → re_retrieve (score < 0.7, max 2 retries)
re_retrieve → generate_answer
```

---

## Neo4j Graph Schema

```cypher
// Nodes
(:Company), (:Segment), (:Metric), (:RiskFactor), (:Executive), (:Year), (:Section), (:Topic)

// Relationships
(Company)-[:HAS_SEGMENT]->(Segment)
(Company)-[:REPORTED]->(Metric)-[:IN_YEAR]->(Year)
(Company)-[:FLAGGED_RISK]->(RiskFactor)-[:IN_YEAR]->(Year)
(Company)-[:HAS_EXECUTIVE]->(Executive)
(Metric)-[:BELONGS_TO]->(Section)
(Company)-[:PEER_OF]->(Company)
(Metric)-[:CHANGED_FROM]->(Metric)
(RiskFactor)-[:ESCALATED_IN]->(Year)
(Company)-[:MENTIONED_TOPIC {frequency: int, sentiment: float}]->(Topic)-[:IN_YEAR]->(Year)
```

### Key Topics Tracked for Temporal Analysis

```python
KEY_TOPICS = [
    "artificial intelligence", "machine learning", "cloud",
    "supply chain", "COVID", "pandemic", "inflation",
    "interest rate", "regulation", "competition",
    "layoffs", "restructuring", "efficiency",
]
```

---

## Retrieval Configuration

```python
TOP_K_RETRIEVAL = 20   # initial retrieval
TOP_K_RERANK    = 5    # after reranking
RRF_K           = 60   # reciprocal rank fusion constant

HYBRID_DENSE_WEIGHT  = 0.6
HYBRID_SPARSE_WEIGHT = 0.4

# RRF formula: score = Σ 1 / (rank + 60)
```

---

## Qdrant Collections

```python
COLLECTION_NAMES = {
    "fixed":                  "meridian_fixed",
    "semantic":               "meridian_semantic",
    "recursive":              "meridian_recursive",
    "hierarchical_chunks":    "meridian_hier_chunks",
    "hierarchical_summaries": "meridian_hier_summaries",
}
```

All collections must support metadata filters on: `company`, `fiscal_year`, `document_type`, `section`.

---

## All Prompts — must live in `llm/prompts.py`

Key prompts required:

```python
QUERY_VARIANT_PROMPT       # generates 4 query variants (FusionRAG)
RELATIONSHIP_EXTRACTION_PROMPT  # LLM extracts graph triples
GENERATION_PROMPT          # main RAG generation with citation instruction
FAITHFULNESS_CHECK_PROMPT  # inline faithfulness check
RETRIEVAL_EVALUATOR_PROMPT # CRAG chunk scoring (0.0–1.0)
QUERY_CLASSIFIER_PROMPT    # classifies query into 6 types
SUMMARY_PROMPT             # generates document summary for hierarchical index
COMPRESSION_PROMPT         # removes irrelevant sentences from context
```

**Rule: No prompt text anywhere except `llm/prompts.py`.**

---

## Evaluation Framework

### RAGAS Metrics (per question, per architecture)

- `faithfulness` — claims traceable to retrieved context
- `answer_relevancy` — answer addresses the question
- `context_precision` — relevant chunks ranked higher
- `context_recall` — ground truth information retrieved
- `answer_correctness` — matches ground truth
- `latency_ms` — wall clock time
- `estimated_cost` — tokens × $0.0002/1K

### Custom Metrics

- `citation_accuracy` — every claim in answer traces to a chunk
- Latency: P50 / P95 / P99 across all questions
- Breakdown by question type and difficulty

### Results Files

```
data/evaluation/results/{architecture_name}.json
```

Every architecture runs on the identical 325-question set — no cherry-picking.

---

## Monitoring

### Prometheus (port 8000)

```python
METRIC_QUERY_LATENCY   = "meridian_query_latency_seconds"   # histogram
METRIC_TOKENS_USED     = "meridian_tokens_used_total"        # counter
METRIC_RETRIEVAL_COUNT = "meridian_retrieval_count_total"    # counter
METRIC_FAITHFULNESS    = "meridian_faithfulness_score"       # histogram
METRIC_QUERIES_TOTAL   = "meridian_queries_total"            # counter, labeled by architecture
```

Qdrant exposes built-in Prometheus metrics at `:6333/metrics`.
Neo4j exposes metrics via the Prometheus plugin.

### Grafana Dashboard Panels

- Architecture comparison (live, not pre-computed)
- Query latency histogram
- Faithfulness score distribution
- Queries per architecture counter
- Qdrant vector store size

---

## Docker Compose Services

```yaml
services:
  qdrant:      # port 6333
  neo4j:       # ports 7474, 7687 — password: meridian123
  ollama:      # port 11434 — GPU if available
  app:         # port 8501 — Streamlit dashboard
  prometheus:  # port 9090
  grafana:     # port 3000
```

Start everything: `docker compose up`

---

## pytest Test Suite

| File | What it tests |
|---|---|
| `test_chunkers.py` | Chunk sizes within bounds, metadata present on every chunk |
| `test_metadata_resolver.py` | Apple FY2024 → period Oct 2023–Sep 2024; Microsoft FY2024 → Jul 2023–Jun 2024 |
| `test_retrieval.py` | top-k returns exactly k results, scores in [0, 1] |
| `test_ragas_runner.py` | All metric scores in valid range, no null answers |
| `test_graph.py` | Neo4j queries return expected node types |

---

## GitHub Actions CI

Trigger: every push to `main`

Steps:
1. Install dependencies
2. Run `pytest`
3. Run RAGAS smoke test on 10 questions
4. Validate Neo4j schema
5. Report pass/fail + badge in README

---

## PySpark Extraction Benchmark

`ingestion/extractor.py` runs sequential extraction first (baseline timer), then PySpark extraction (all cores in parallel), logs:

```json
{
    "n_documents":        125,
    "sequential_seconds": 847.3,
    "spark_seconds":      134.2,
    "speedup":            6.31,
    "timestamp":          "2025-05-15T10:22:00"
}
```

Output written to `logs/extraction_benchmark.json`. Speedup reported in README.

---

## Critical Implementation Rules

1. Every architecture inherits from `architectures/base.py` — no exceptions
2. Every query returns the identical response schema: `{answer, citations, faithfulness, relevancy, latency_ms, tokens_used, architecture_name}`
3. Metadata filters must work on every retrieval call — temporal and comparative queries depend on this
4. RAGAS evaluation runs on the identical 325-question set for every architecture — no cherry-picking
5. All prompts in `llm/prompts.py` — never inline prompt text in architecture files
6. All thresholds in `config.py` — never hardcode numbers in pipeline code
7. Log every retrieval call: query, architecture, chunks retrieved, scores, latency
8. Graph extractor must be idempotent — running twice produces the same Neo4j state
9. `docker compose up` must start all services with one command
10. Fiscal year metadata must be resolved before any retrieval runs — `ingestion/metadata.py` handles this
11. `family_map_millions` for Meta FY2024 is `None` by design — skip question templates that require it for FY2024

---

## Build Order — Strictly Follow This Sequence

```
Phase 1 — Data Foundation          ✅ COMPLETE
  config.py
  ingestion/downloader.py + s3_client.py
  ingestion/extractor.py (PySpark)
  ingestion/metadata.py
  ingestion/chunkers/ (all 4)

Phase 2 — Facts + Question Set     ← START HERE
  data/evaluation/facts.py         ✅ COMPLETE (approved)
  data/evaluation/generate_questions.py
  data/evaluation/questions.json

Phase 3 — Evaluation Framework
  evaluation/ragas_runner.py
  evaluation/metrics.py
  evaluation/results_analyzer.py

Phase 4 — Retrieval Components
  retrieval/dense.py
  retrieval/sparse.py
  retrieval/hybrid.py
  retrieval/reranker.py

Phase 5 — Graph Layer
  graph/schema.py
  graph/extractor.py
  graph/loader.py
  retrieval/graph/queries.py
  retrieval/graph/hybrid_graph.py

Phase 6 — LLM Layer
  llm/ollama_client.py
  llm/prompts.py
  llm/generator.py

Phase 7 — All 8 Architectures
  architectures/base.py
  architectures/naive.py
  architectures/hybrid_rag.py
  architectures/fusion_rag.py
  architectures/hierarchical_rag.py
  architectures/corrective_rag.py
  architectures/graph_rag.py
  architectures/agentic_rag.py
  architectures/full_system.py

Phase 8 — Agents
  agents/langgraph_agent.py
  agents/tools.py
  agents/router.py
  agents/reflector.py

Phase 9 — Dashboard
  dashboard/app.py (4 tabs)

Phase 10 — Monitoring
  monitoring/prometheus_metrics.py
  monitoring/grafana/dashboards/meridian.json
  monitoring/grafana/provisioning/datasources/prometheus.yml

Phase 11 — Tests
  tests/test_chunkers.py
  tests/test_metadata_resolver.py
  tests/test_retrieval.py
  tests/test_ragas_runner.py
  tests/test_graph.py

Phase 12 — Deployment
  docker-compose.yml
  requirements.txt
  .github/workflows/ci.yml
  README.md
```

---

## README Must Include

- Architecture comparison table (8 architectures × 6 metrics)
- COVID-specific findings: which architecture handles temporal COVID questions best
- Topic frequency visualization: AI mention surge 2020–2024
- Corpus statistics: 100 documents, 325 questions, 5 companies, 5 years
- PySpark speedup: sequential vs parallel extraction benchmark result
- Build instructions: `docker compose up` → `python ingestion/downloader.py` → `python ingestion/extractor.py` → `python data/evaluation/generate_questions.py` → `python evaluation/ragas_runner.py --architecture all`
- Example queries with expected behavior per architecture
- CI badge
- Limitations: fiscal year misalignment, 10-Q vs 10-K depth difference, LLM numerical reasoning ceiling

---

*Project renamed from FinRAG → Meridian. Location: `C:/Users/sansk/Documents/Spring-26/Meridian`*
