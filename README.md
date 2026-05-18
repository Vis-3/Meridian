# Meridian

![CI](https://github.com/sansk/meridian/actions/workflows/ci.yml/badge.svg)
![Uptime](https://img.shields.io/badge/uptime-monitoring-blue)

Benchmarks 8 RAG architectures on 100 SEC filings (2020–2024) across 5 companies, measuring numerical accuracy, faithfulness, citation coverage, and keyword hit rate on 325 hand-labeled financial Q&A pairs spanning COVID impact, supply chain disruption, and AI investment cycles.

---

## Benchmark Results (May 2026)

> 180 questions · 30 per type × 6 types · Gemini 2.5 Flash · `evaluation/composite_score.py`  
> Full analysis: [`BENCHMARK_ANALYSIS.md`](BENCHMARK_ANALYSIS.md)

### Single Architecture Results

| # | Architecture | Quality ↑ | Efficiency ↑ | Cost-Quality ↑ | Production ↑ | P50 (ms) |
|---|---|---:|---:|---:|---:|---:|
| 0 | Naive | **0.6738** | **0.3683** | 0.5397 | 0.7998 | 66 |
| 5 | Graph | 0.6688 | 0.2126 | 0.5506 | 0.7975 | 1,399 |
| 4 | Corrective | 0.6643 | 0.1329 | **0.6643** | 0.5327 | 99,235 |
| 6 | Agentic | 0.6610 | 0.1593 | 0.5707 | 0.7624 | 14,085 |
| 2 | Fusion | 0.6588 | 0.1430 | 0.5531 | 0.6760 | 40,365 |
| 7 | Full System | 0.6524 | 0.1528 | 0.5621 | 0.7419 | 18,614 |
| 3 | Hierarchical | 0.6498 | 0.1758 | 0.5558 | 0.7799 | 4,961 |
| 1 | Hybrid | 0.6412 | 0.1974 | 0.6296 | **0.8073** | 1,768 |

### MeridianRouter — Virtual Scores

MeridianRouter routes each question type to its empirically optimal architecture. No new API calls — scores computed via slice-and-stitch from existing results.

| Mode | Quality ↑ | Efficiency ↑ | Cost-Quality ↑ | Production ↑ | P50 (ms) | vs. best single |
|---|---:|---:|---:|---:|---:|---|
| Quality | **0.7236** | 0.2068 | 0.6060 | 0.8108 | 3,159 | +7.4% quality |
| Production | 0.7191 | 0.2191 | 0.6135 | **0.8148** | 1,915 | **+1.0% prod** |
| Cost | 0.7084 | 0.1418 | **0.6725** | 0.5327 | 99,020 | +1.2% cost-qual |
| Efficiency | 0.7072 | **0.3866** | 0.5665 | 0.7998 | 66 | ≡ naive |

### Per-Type Quality Winners

| Question Type | Best Architecture | Quality Score | Runner-up |
|---|---|---:|---|
| `simple_factual` | Hierarchical | 0.858 | Corrective (0.856) |
| `numerical_reasoning` | Hierarchical | 0.731 | Agentic (0.716) |
| `temporal` | Fusion | 0.454 | Corrective (0.433) |
| `comparative` | Graph | 0.793 | Naive (0.790) |
| `multi_hop` | Hybrid | 0.567 | Naive (0.562) |
| `risk_qualitative` | Naive | **0.946** | Full System (0.937) |

### Key Findings

1. **Complexity ≠ quality** — Naive RAG wins overall quality (0.6738) against all 7 more sophisticated systems.
2. **MeridianRouter** achieves +7.4% quality (0.7236) by routing to the per-type optimal architecture.
3. **Full System underperforms** (0.6524) because its pre-benchmark intuition routing was correct on only 1/6 types. MeridianRouter replaces it with data-driven routing.
4. **Corrective wins cost-quality** (0.6643) despite being the slowest (99s P50) — chunk filtering reduces LLM input tokens by ~18%.
5. **Temporal is the hardest type** (0.384–0.454) — no architecture handles multi-year trend reasoning well.
6. **Naive wins risk-qualitative at 0.946** — filtering hurts for dense qualitative text; broad dense retrieval is optimal.

---

## Corpus

| Metric                  | Value                                                   |
|-------------------------|---------------------------------------------------------|
| Companies               | Apple, Microsoft, Google (Alphabet), Amazon, Meta       |
| Years                   | FY 2020 – FY 2024                                       |
| Total documents         | 100 (25 x 10-K, 75 x 10-Q)                             |
| Documents per company   | 20 (1 x 10-K + 3 x 10-Q per year)                      |
| Total sections          | 400 (Item 1, 1A, 7, 8 — 100% coverage)                 |
| Total chunks (fixed)    | 7,379 (avg 504 tokens)                                  |
| Semantic index          | 208,861 parent-level passages                           |
| Avg words per document  | 33,638                                                  |
| Largest document        | meta_2024_10k (76,907 words)                            |
| Evaluation questions    | 325 (6 types, hand-labeled ground truths)               |

### Question Distribution

| Type                  | Count | Description                                              |
|-----------------------|------:|----------------------------------------------------------|
| `simple_factual`      |    50 | Single company, single year, direct lookup               |
| `numerical_reasoning` |    50 | Ratios, growth rates, margin calculations                |
| `temporal`            |    60 | Single company trend across all 5 years                  |
| `comparative`         |    60 | Multi-company, same period, ranked comparison            |
| `multi_hop`           |    55 | Two conditions joined across sections or documents       |
| `risk_qualitative`    |    50 | Qualitative reasoning over Item 1A risk factors          |
| **Total**             | **325** |                                                        |

---

## Quickstart (Local)

### Prerequisites
- Docker Desktop
- Python 3.11+
- 16 GB RAM (Neo4j + Qdrant + models)

### 1. Start services

```bash
docker compose up -d
# Qdrant :6333  |  Neo4j :7474/:7687  |  Prometheus :9090  |  Grafana :3000
```

### 2. Install Python dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set GEMINI_API_KEY and DEPLOYMENT=gemini
```

### 4. Run batch evaluation (generation pass)

```bash
# All architectures, 30 questions per type (180 total)
python scripts/run_batch_evaluation.py --per-type 30 --no-ragas

# Specific architectures only
python scripts/run_batch_evaluation.py -a naive hybrid --per-type 30 --no-ragas
```

### 5. Compute metrics and composite scores

```bash
# Reliable metrics (BERTScore F1 + 4 other metrics, no API calls)
python evaluation/metrics_reliable.py

# Composite scores (4 dimensions per architecture)
python evaluation/composite_score.py --save

# MeridianRouter virtual scores
python scripts/router_preview.py
```

### 6. Run MeridianRouter

```bash
python architectures/meridian_router.py --mode production
```

### 7. Open dashboard

```bash
streamlit run dashboard/app.py
# Open http://localhost:8501
```

---

## GCP Deployment

### On the VM (first time)

```bash
git clone https://github.com/sansk/meridian.git ~/meridian
cd ~/meridian
cp .env.example .env
nano .env   # set GEMINI_API_KEY, GRAFANA_PASSWORD, NEO4J_PASSWORD

docker compose -f deployment/oracle/docker-compose.oracle.yml up -d --build
```

### Verify

```bash
curl http://GCP_HOST/health
# {"status": "ok", ...}
```

### Services behind Nginx

| Path        | Service             |
|-------------|---------------------|
| `/`         | Streamlit dashboard |
| `/api/`     | FastAPI health API  |
| `/grafana/` | Grafana dashboards  |

### GitHub Actions auto-deploy

Add these three secrets in **Settings > Secrets > Actions**:

| Secret        | Value                          |
|---------------|--------------------------------|
| `GCP_HOST`    | VM external IP                 |
| `GCP_USER`    | SSH username (e.g. `ubuntu`)   |
| `GCP_SSH_KEY` | Full PEM private key content   |

Every push to `main` SSHes into the VM, pulls, and redeploys automatically.

---

## Grafana

Grafana auto-provisions on first start — no manual import needed.

- `monitoring/grafana/provisioning/datasources/prometheus.yml` — wires Prometheus
- `monitoring/grafana/provisioning/dashboards/dashboards.yml` — registers dashboard folder
- `monitoring/grafana/dashboards/meridian.json` — Meridian dashboard

Default: `admin` / `GRAFANA_PASSWORD` from `.env` (default `admin`).

**Dashboard panels:** Query rate by architecture · P99 latency · Faithfulness score distribution · Faithfulness pass rate · Re-retrieval rate · Qdrant collection size · Neo4j node count · Cost per query

---

## Full Build Pipeline

```bash
# 1. Download SEC filings from EDGAR
python ingestion/downloader.py

# 2. Extract text + tables (PySpark parallel, ~6x speedup)
python ingestion/extractor.py

# 3. Build Qdrant fixed-chunk index
python scripts/build_index.py

# 4. Build semantic index (run on Kaggle GPU for speed)
python scripts/build_semantic_index.py

# 5. Build Neo4j graph
python graph/loader.py

# 6. Generate benchmark questions
python data/evaluation/generate_questions.py

# 7. Generation pass (all 8 architectures, 325 questions)
python scripts/run_batch_evaluation.py --no-ragas

# 8. RAGAS scoring pass (overnight)
python scripts/score_saved_results.py
```

---

## PySpark Extraction Benchmark

| Mode        | Time    | Speedup |
|-------------|---------|---------|
| Sequential  | ~847s   | 1x      |
| PySpark     | ~134s   | ~6.3x   |

Logged to `logs/extraction_benchmark.json`.

---

## Tests

```bash
pytest tests/ -v --tb=short
```

| File                        | What it tests                                          |
|-----------------------------|--------------------------------------------------------|
| `test_chunkers.py`          | Chunk sizes within bounds, metadata on every chunk     |
| `test_metadata_resolver.py` | Fiscal year mapping (Apple FY2024 = Oct 2023–Sep 2024) |
| `test_retrieval.py`         | top-k returns exactly k results, scores in [0, 1]      |
| `test_ragas_runner.py`      | All metric scores in valid range, no null answers      |
| `test_graph.py`             | Neo4j queries return expected node types               |

---

## Limitations

See [`docs/known_limitations.md`](docs/known_limitations.md). Key items:

- **Fiscal year misalignment**: Apple's FY ends in September — cross-company "same year" comparisons require careful year mapping
- **10-Q vs 10-K depth**: Quarterly filings have abbreviated risk sections; multi-hop questions requiring Item 1A depth should prefer 10-K routing
- **LLM numerical ceiling**: Gemini 2.5 Flash makes arithmetic errors on multi-step calculations; `numerical_reasoning` questions have the highest error rate
- **RAGAS `answer_correctness`**: Excluded from default scoring (4+ LLM calls per sample, consistently times out against Gemini 2.5 models)

---

## Engineering Log

[`docs/engineering_log.md`](docs/engineering_log.md) — running record of decisions, issues, and fixes. Notable entries:

- **Issue 016**: Gemini model availability varies by account type (gemini-2.0-* returns 404 for new accounts)
- **Issue 017**: Windows cp1252 encoding breaks RAGAS Unicode output — fixed with `PYTHONUTF8=1`

---

## Project Structure

```
Meridian/
├── architectures/        9 RAG implementations (naive → meridian_router)
│   └── meridian_router.py  Data-driven router with 4 modes (NEW)
├── data/evaluation/      325 questions, facts table, qualitative ground truths
│   └── results/          Per-architecture JSON results + composite_scores.json
├── deployment/oracle/    Docker Compose, Nginx, Dockerfiles (GCP / Oracle)
├── docs/                 Engineering log, known limitations, architecture decisions
├── evaluation/           Reliable metrics (5 metrics, no LLM API), composite scoring
│   ├── metrics_reliable.py   num_acc + bertscore_f1 + keyword_hit + cit_cov + faithfulness
│   └── composite_score.py    4 composite scores (quality/efficiency/cost/production)
├── ingestion/            Downloader, PySpark extractor, chunkers
├── monitoring/           Prometheus metrics, Grafana dashboard + provisioning
├── retrieval/            Dense, sparse, hybrid, graph retrievers
├── scripts/              Batch evaluation (--per-type N, multi-arch), router_preview
├── tests/                pytest suite (5 test files)
├── dashboard/            Streamlit app (4 tabs: Ask, Compare, Benchmark, Explorer)
└── BENCHMARK_ANALYSIS.md Full benchmark analysis with methodology and findings
```
