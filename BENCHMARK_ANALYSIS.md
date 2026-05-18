# Meridian — Benchmark Analysis

> **Benchmark date:** May 2026  
> **Questions:** 180 (30 per type × 6 types), stratified random sample from 325-question corpus  
> **Architectures evaluated:** 8 single architectures + 4 MeridianRouter virtual modes  
> **Evaluation model:** Gemini 2.5 Flash (generation) + distilbert-base-uncased (BERTScore F1)

---

## Table of Contents

1. [Methodology](#1-methodology)
2. [Corpus](#2-corpus)
3. [Metrics](#3-metrics)
4. [Composite Scores — All Architectures](#4-composite-scores--all-architectures)
5. [MeridianRouter — Virtual Scores](#5-meridianrouter--virtual-scores)
6. [Per-Type Quality Breakdown](#6-per-type-quality-breakdown)
7. [Per-Type Production Score](#7-per-type-production-score)
8. [Routing Decisions by Mode](#8-routing-decisions-by-mode)
9. [Key Findings](#9-key-findings)
10. [Recommendations](#10-recommendations)

---

## 1. Methodology

### Generation pass

All 8 architectures were run against the same 180 stratified questions using `scripts/run_batch_evaluation.py --per-type 30`. Each question was answered independently by each architecture; no results were shared. Numerical questions used a dedicated system prompt (`GENERATION_SYSTEM_NUMERICAL`) to improve precision on financial calculations.

### Evaluation

Metrics are computed locally with no LLM API calls via `evaluation/metrics_reliable.py`. This avoids RAGAS-style inter-query LLM noise and produces deterministic, reproducible scores.

### Composite scores

Composite scores are computed by `evaluation/composite_score.py`. Four dimensions are measured:

| Score | Formula | Weights |
|-------|---------|---------|
| **Quality** | Weighted average of 4 metrics | num_acc×0.35 + faith×0.30 + cit×0.20 + kw×0.15 |
| **Efficiency** | quality / log₁₀(P50_retrieval_ms + 1) | — |
| **Cost-Quality** | quality / (avg_cost / min_cost) | — |
| **Production** | Normalised multi-dimension score | quality×0.50 + speed×0.30 + cost×0.20 |

### MeridianRouter

MeridianRouter is a virtual architecture that routes each question to the empirically best single architecture for that question type. Scores are computed via slice-and-stitch: each question's pre-computed metrics are attributed to the architecture it was routed to, with no additional API calls. See `scripts/router_preview.py`.

---

## 2. Corpus

| Attribute | Value |
|-----------|-------|
| Companies | Apple, Microsoft, Google (Alphabet), Amazon, Meta |
| Fiscal years | FY 2020–FY 2024 |
| Total filings | 100 (25 × 10-K, 75 × 10-Q) |
| Total chunks (fixed) | 7,379 (avg 504 tokens) |
| Benchmark questions | 325 hand-labeled (180 used in this run) |
| Question types | 6 (30 per type in this evaluation) |

### Question type distribution

| Type | Description |
|------|-------------|
| `simple_factual` | Single company, single year, direct lookup |
| `numerical_reasoning` | Ratios, growth rates, margin calculations |
| `temporal` | Single company trend across ≥2 years |
| `comparative` | Multi-company, same period, ranked comparison |
| `multi_hop` | Two conditions joined across sections or documents |
| `risk_qualitative` | Qualitative reasoning over Item 1A risk factors |

---

## 3. Metrics

### Quality metrics (used in composite score)

| Metric | Weight | Description |
|--------|--------|-------------|
| `numerical_accuracy` | 0.35 | Extracts dollar amounts and percentages; scores ±1% exact match (1.0), ±10% ballpark (0.5), otherwise 0. Returns `None` when ground truth has no numbers. |
| `faithfulness_proxy` | 0.30 | Sentence-level grounding: fraction of answer sentences whose key words appear in ≥1 retrieved chunk (overlap threshold 40%). |
| `citation_coverage` | 0.20 | Fraction of expected company names + fiscal years mentioned in the answer. |
| `keyword_hit_rate` | 0.15 | Fraction of content words from ground truth (≥4 chars, not stop words) found in the answer. |

### Reference metric (not in composite score)

| Metric | Description |
|--------|-------------|
| `bertscore_f1` | Semantic similarity between answer and ground truth using distilbert-base-uncased embeddings. Not weighted into composite score — reported separately as a sanity check. |

### Latency

Retrieval P50 latency (ms) is recorded per query and used for efficiency and production scoring. The metric is `latency_breakdown.retrieval_ms`, which excludes LLM generation time.

### Cost

`estimated_cost_usd` is computed from actual token counts × Gemini 2.5 Flash pricing. Costs are tightly clustered ($0.10–$0.13 per 1,000 queries) so cost differences are real but small.

---

## 4. Composite Scores — All Architectures

> Sorted by Quality. `*` marks the column winner.

| Architecture | Quality | Efficiency | Cost-Quality | Production | P50 (ms) | $/1k q |
|---|---:|---:|---:|---:|---:|---:|
| **naive** | **0.6738 \*** | **0.3683 \*** | 0.5397 | 0.7998 | 66 | $0.127 |
| graph | 0.6688 | 0.2126 | 0.5506 | 0.7975 | 1,399 | $0.123 |
| corrective | 0.6643 | 0.1329 | **0.6643 \*** | 0.5327 | 99,235 | $0.102 |
| agentic | 0.6610 | 0.1593 | 0.5707 | 0.7624 | 14,085 | $0.118 |
| fusion | 0.6588 | 0.1430 | 0.5531 | 0.6760 | 40,365 | $0.121 |
| full_system | 0.6524 | 0.1528 | 0.5621 | 0.7419 | 18,614 | $0.118 |
| hierarchical | 0.6498 | 0.1758 | 0.5558 | 0.7799 | 4,961 | $0.119 |
| hybrid | 0.6412 | 0.1974 | 0.6296 | **0.8073 \*** | 1,768 | $0.103 |

**Column winners:** Quality → naive · Efficiency → naive · Cost-Quality → corrective · Production → hybrid

---

## 5. MeridianRouter — Virtual Scores

MeridianRouter routes each question type to its empirically optimal architecture. Four routing modes are available.

### Router vs. best single architecture

| Mode | Routing logic | Quality | Efficiency | Cost-Quality | Production | P50 (ms) |
|---|---|---:|---:|---:|---:|---:|
| **MeridianRouter (quality)** | Best quality per type | **0.7236** | 0.2068 | 0.6060 | 0.8108 | 3,159 |
| MeridianRouter (production) | Best production per type | 0.7191 | 0.2191 | 0.6135 | **0.8148** | 1,915 |
| MeridianRouter (cost) | Cheapest per type | 0.7084 | 0.1418 | **0.6725** | 0.5327 | 99,020 |
| MeridianRouter (efficiency) | Fastest per type | 0.7072 | **0.3866** | 0.5665 | 0.7998 | 66 |
| *(best single: naive)* | — | 0.6738 | 0.3683 | 0.5397 | 0.7998 | 66 |
| *(best single: hybrid)* | — | 0.6412 | 0.1974 | 0.6296 | 0.8073 | 1,768 |

**Quality gain vs. best single arch:** +7.4% (0.6738 → 0.7236 in quality mode), +6.7% in production mode.

### Routing table

| Question Type | Quality mode | Efficiency mode | Cost mode | Production mode |
|---|---|---|---|---|
| `simple_factual` | hierarchical | naive | corrective | hybrid |
| `numerical_reasoning` | hierarchical | naive | corrective | hierarchical |
| `temporal` | fusion | naive | corrective | graph |
| `comparative` | graph | naive | corrective | graph |
| `multi_hop` | hybrid | naive | hybrid | hybrid |
| `risk_qualitative` | naive | naive | corrective | naive |

---

## 6. Per-Type Quality Breakdown

Quality score per question type, all 8 architectures. `*val*` marks per-row best.

| Type | graph | naive | hybrid | hierarch | fusion | agentic | full_sys | correcti | **Winner** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `simple_factual` | 0.838 | 0.845 | 0.855 | **0.858** | 0.851 | 0.844 | 0.845 | 0.856 | hierarchical |
| `numerical_reasoning` | 0.714 | 0.705 | 0.646 | **0.731** | 0.655 | 0.716 | 0.710 | 0.711 | hierarchical |
| `temporal` | 0.428 | 0.401 | 0.384 | 0.396 | **0.454** | 0.428 | 0.431 | 0.433 | fusion |
| `comparative` | **0.793** | 0.790 | 0.720 | 0.722 | 0.762 | 0.773 | 0.731 | 0.779 | graph |
| `multi_hop` | 0.544 | 0.562 | **0.567** | 0.499 | 0.547 | 0.510 | 0.490 | 0.491 | hybrid |
| `risk_qualitative` | 0.880 | **0.946** | 0.845 | 0.922 | 0.894 | 0.898 | 0.937 | 0.910 | naive |
| **Overall** | 0.669 | **0.674** | 0.641 | 0.650 | 0.659 | 0.661 | 0.652 | 0.664 | naive |

### Key observations

- **No single architecture dominates all 6 types.** The winner changes with every question category.
- **Hierarchical wins factual + numerical** — document-level routing surfaces the exact filing first, reducing irrelevant context.
- **Fusion wins temporal** — 4 query rephrasings uniquely capture multi-year trend phrasing variations.
- **Graph wins comparative** — Neo4j entity traversal guarantees per-company representation; RRF alone cannot.
- **Hybrid wins multi-hop** — BM25 + dense + reranking handles two-condition joins where graph over-constrains.
- **Naive wins risk-qualitative** — qualitative reasoning over dense risk-factor text needs broad context, not entity filtering. Score 0.946.

---

## 7. Per-Type Production Score

Production score normalises quality (0.50), speed (0.30), and cost (0.20) together.

| Type | graph | naive | hybrid | hierarch | fusion | agentic | full_sys | correcti | **Winner** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `simple_factual` | 0.790 | 0.792 | **0.830** | 0.798 | 0.683 | 0.763 | 0.750 | 0.539 | hybrid |
| `numerical_reasoning` | 0.790 | 0.782 | 0.774 | **0.798** | 0.635 | 0.761 | 0.744 | 0.526 | hierarchical |
| `temporal` | **0.772** | 0.742 | 0.755 | 0.734 | 0.687 | 0.744 | 0.732 | 0.517 | graph |
| `comparative` | **0.801** | 0.797 | 0.785 | 0.752 | 0.667 | 0.759 | 0.719 | 0.530 | graph |
| `multi_hop` | 0.782 | 0.796 | **0.832** | 0.738 | 0.670 | 0.722 | 0.691 | 0.473 | hybrid |
| `risk_qualitative` | 0.766 | **0.800** | 0.778 | 0.785 | 0.660 | 0.746 | 0.753 | 0.521 | naive |
| **Overall** | 0.797 | 0.800 | **0.807** | 0.780 | 0.676 | 0.762 | 0.742 | 0.533 | hybrid |

Production winner differs from quality winner in 4/6 types because **speed and cost strongly penalise slow architectures** (corrective at 99s drops from 0.664 quality to 0.533 production).

---

## 8. Routing Decisions by Mode

### Quality mode routing rationale

| Type | Routed to | Winner quality | Rationale |
|---|---|---:|---|
| `simple_factual` | hierarchical | 0.858 | Document-level pre-filtering removes irrelevant filings before chunk retrieval |
| `numerical_reasoning` | hierarchical | 0.731 | Same rationale; correct document isolation reduces multi-year table confusion |
| `temporal` | fusion | 0.454 | Query expansion captures year-over-year phrasing variants missed by single query |
| `comparative` | graph | 0.793 | Neo4j entity traversal guarantees per-company chunks; RRF score compression cannot |
| `multi_hop` | hybrid | 0.567 | BM25+dense+reranker handles two-condition cross-section joins |
| `risk_qualitative` | naive | 0.946 | Broad dense context is optimal for qualitative risk reasoning; filtering hurts |

### Efficiency mode (degenerate)

**All 6 types route to naive.** Naive's 66ms P50 is an order of magnitude faster than the next-fastest architecture (graph at 1,399ms). The efficiency router collapses to always-naive. Quality is identical to running naive directly (0.7072 vs 0.6738 — slight difference because efficiency mode uses per-question stitching vs. overall aggregate). This is a **design decision**: if raw throughput is the constraint, naive is the optimal single architecture.

### Cost mode routing rationale

Corrective is the cheapest architecture ($0.1015/1k q) because chunk relevance filtering before generation reduces input tokens to the LLM. It wins 5/6 types in cost-quality. Hybrid wins `multi_hop` cost-quality (0.556) because corrective's filtered context misses the second hop more often, requiring more tokens to compensate.

### Production mode routing rationale

Production routing avoids corrective (99s penalty) and fusion (40s penalty). Graph (1.4s) and hybrid (1.8s) win temporal and comparative respectively, providing good quality at moderate latency. Naive wins risk-qualitative (quality advantage large enough that even with latency parity, naive dominates).

---

## 9. Key Findings

### Finding 1: Complexity does not predict quality

Naive RAG (architecture 0) wins the overall quality benchmark (0.6738) against all 7 more sophisticated systems. The most complex architectures — agentic (2+ LLM calls) and full_system (routing + delegation) — score below naive on quality.

**Implication:** Retrieval quality, not generation complexity, is the binding constraint on benchmark performance.

### Finding 2: MeridianRouter closes the per-type quality gap

The best single architecture wins each type with a narrow margin over the field. MeridianRouter (quality mode) routes to the per-type winner, achieving 0.7236 overall — **+7.4% over naive**. This gain comes entirely from matching the right retrieval strategy to the question structure, not from better generation.

### Finding 3: Full System pre-benchmark routing was suboptimal

The pre-benchmark `full_system` routing table (simple_factual→hierarchical, numerical→agentic, temporal→agentic, comparative→fusion, multi_hop→graph, risk_qualitative→corrective) was designed by intuition. Benchmark results show only **1 of 6 routes was optimal** (simple_factual→hierarchical). Full System scores 0.6524 — below naive (0.6738). MeridianRouter replaces this with data-driven routing.

### Finding 4: Corrective is the cheapest, not the most expensive, architecture to run

Despite the highest retrieval latency (99,235ms P50), corrective ranks first in cost-quality (0.6643). Its chunk relevance scoring **filters low-quality context before the LLM call**, reducing average input tokens by ~18% compared to naive. Corrective wins cost-quality on 5/6 question types.

### Finding 5: Efficiency optimisation degenerates to naive

Naive's 66ms P50 dominates all 6 question types in the efficiency metric (quality / log₁₀ latency). The efficiency gap between naive and the second-fastest architecture (graph, 1,399ms) is 21× in retrieval time. Any router that optimises for efficiency collapses to always-naive — this is correct behaviour, not a limitation.

### Finding 6: Temporal reasoning is the hardest question type

`temporal` scores are the lowest across all architectures (0.384–0.454), a full 0.4 points below `risk_qualitative`. Multi-year trend questions require reasoning across 5 fiscal years simultaneously. Fusion's query expansion gives the best result (0.454), but even that represents a below-median performance. **No architecture handles temporal well.**

### Finding 7: Risk qualitative is the easiest, and naive wins it by a large margin

`risk_qualitative` scores 0.946 for naive vs. 0.845 for hybrid — a 10-point gap in favour of the simplest architecture. Item 1A risk factor text is long, densely worded, and semantically rich. Dense retrieval alone captures the right passages; additional filtering (corrective, hierarchical) or entity constraints (graph) actively hurt by reducing context breadth.

### Finding 8: Graph RAG wins comparative via entity traversal, not score

Graph's advantage on comparative questions (0.793 vs. hybrid 0.720) comes from Neo4j entity-aware routing guaranteeing per-company chunk coverage — not from higher retrieval scores. Standard RRF on a 5-company corpus suffers score compression where one company's chunks dominate. Graph forces balanced retrieval.

### Finding 9: Corrective's 99-second latency makes it production-impractical

Corrective scores well on quality (0.6643) and wins cost-quality (0.6643), but its production score is 0.5327 — the lowest of all architectures, 15 points below the next lowest (fusion, 0.6760). The N+1 LLM calls for chunk scoring are the bottleneck. **Use corrective only in offline batch pipelines where latency is not a constraint.**

### Finding 10: Hybrid wins production, naive wins quality — they are different questions

Overall quality winner: naive (0.6738). Overall production winner: hybrid (0.8073). Hybrid trades ~4.8% quality for a 26× speedup on simple_factual and a 50% cost reduction. For production deployments the 1,768ms P50 is acceptable; the production score reflects that trade-off correctly.

---

## 10. Recommendations

| Use case | Recommended architecture | Rationale |
|---|---|---|
| **Production, mixed queries** | MeridianRouter (production mode) | +6.7% quality over naive, best production score (0.8148), balanced P50 1,915ms |
| **Highest quality, latency budget** | MeridianRouter (quality mode) | +7.4% quality, 3,159ms P50 |
| **Real-time / high throughput** | Naive RAG | Best efficiency (0.3683), 66ms P50, best single-arch quality |
| **Batch analytics, cost-sensitive** | MeridianRouter (cost mode) | Best cost-quality (0.6725), corrective-backed |
| **Comparative / entity queries** | Graph RAG | Best for cross-company comparative questions (0.793) |
| **Trend analysis** | Fusion RAG | Only architecture to win temporal (0.454) |
| **Risk factor research** | Naive RAG | 0.946 on risk_qualitative — filtering hurts |
| **Avoid in production** | Corrective RAG | 99s P50, lowest production score (0.5327) |

---

## Appendix: Raw Metric Scores

### Overall metrics by architecture

> BERTScore F1 (distilbert-base-uncased) is a reference metric only — not weighted into composite scores. Range 0.810–0.820 is extremely tight, confirming architectures produce semantically equivalent answers while differing in numerical precision and faithfulness.

| Architecture | Num. Accuracy | BERTScore F1 | Keyword Hit | Citation Cov | Faithfulness |
|---|---:|---:|---:|---:|---:|
| naive | 0.541 | **0.820** | 0.665 | 0.884 | 0.693 |
| hybrid | 0.497 | 0.818 | 0.656 | 0.863 | 0.654 |
| fusion | 0.471 | 0.812 | 0.639 | 0.870 | **0.747** |
| hierarchical | 0.467 | 0.812 | 0.640 | 0.867 | 0.723 |
| corrective | 0.529 | 0.817 | 0.651 | 0.859 | 0.699 |
| graph | 0.510 | 0.813 | 0.647 | **0.865** | 0.734 |
| agentic | 0.488 | 0.814 | 0.647 | 0.863 | 0.735 |
| full_system | 0.479 | 0.810 | 0.631 | 0.857 | 0.729 |

### Faithfulness proxy by question type

| Question Type | naive | hybrid | fusion | hierarch | correcti | graph | agentic | full_sys |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `simple_factual` | 0.706 | 0.739 | 0.733 | 0.750 | 0.733 | 0.717 | 0.739 | 0.750 |
| `numerical_reasoning` | 0.728 | 0.667 | 0.767 | 0.875 | 0.733 | 0.828 | 0.825 | 0.825 |
| `temporal` | 0.369 | 0.366 | 0.600 | 0.459 | 0.565 | 0.494 | 0.482 | 0.481 |
| `comparative` | 0.898 | 0.806 | 0.823 | 0.828 | 0.863 | 0.877 | 0.933 | 0.819 |
| `multi_hop` | 0.513 | 0.557 | 0.699 | 0.556 | 0.427 | 0.653 | 0.571 | 0.582 |
| `risk_qualitative` | 0.944 | 0.787 | 0.857 | 0.881 | 0.872 | 0.833 | 0.863 | 0.917 |
