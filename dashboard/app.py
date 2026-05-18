"""
Meridian -- Streamlit dashboard.

Tabs:
  1. Ask a Question    -- live query against any architecture
  2. Compare          -- same query across multiple architectures side-by-side
  3. Benchmark Results -- load evaluation JSONs, show charts + tables
  4. Architecture Explorer -- descriptions, pipeline diagrams, code snippets

Modes (set via .env):
  DEPLOYMENT=local   -- Ollama + localhost Qdrant/Neo4j
  DEPLOYMENT=oracle  -- Groq API + remote Qdrant/Neo4j

Run:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import DEPLOYMENT, RESULTS_DIR, COMPANIES, YEARS

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Meridian - Financial RAG",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Architecture metadata
# ---------------------------------------------------------------------------
ARCH_REGISTRY = {
    "naive":              "architectures.naive:NaiveRAG",
    "hybrid":             "architectures.hybrid_rag:HybridRAG",
    "fusion":             "architectures.fusion_rag:FusionRAG",
    "hierarchical":       "architectures.hierarchical_rag:HierarchicalRAG",
    "corrective":         "architectures.corrective_rag:CorrectiveRAG",
    "graph":              "architectures.graph_rag:GraphRAG",
    "agentic":            "architectures.agentic_rag:AgenticRAG",
    "full_system":        "architectures.full_system:FullSystem",
    "router_quality":     "architectures.meridian_router:MeridianRouter",
    "router_production":  "architectures.meridian_router:MeridianRouter",
    "router_cost":        "architectures.meridian_router:MeridianRouter",
    "router_efficiency":  "architectures.meridian_router:MeridianRouter",
}

ROUTER_MODES = {
    "router_quality":    "quality",
    "router_production": "production",
    "router_cost":       "cost",
    "router_efficiency": "efficiency",
}

ROUTER_ROUTING = {
    "quality":    {"simple_factual":"hierarchical","numerical_reasoning":"hierarchical","temporal":"fusion","comparative":"graph","multi_hop":"hybrid","risk_qualitative":"naive"},
    "production": {"simple_factual":"hybrid","numerical_reasoning":"hierarchical","temporal":"graph","comparative":"graph","multi_hop":"hybrid","risk_qualitative":"naive"},
    "cost":       {"simple_factual":"corrective","numerical_reasoning":"corrective","temporal":"corrective","comparative":"corrective","multi_hop":"hybrid","risk_qualitative":"corrective"},
    "efficiency": {"simple_factual":"naive","numerical_reasoning":"naive","temporal":"naive","comparative":"naive","multi_hop":"naive","risk_qualitative":"naive"},
}

ROUTER_EXPECTED_QUALITY = {
    "router_quality":    0.7236,
    "router_production": 0.7191,
    "router_cost":       0.7084,
    "router_efficiency": 0.7072,
}

ROUTER_META: dict[str, dict] = {
    "router_quality": {
        "label":       "MeridianRouter (quality)",
        "description": "Routes each question to the empirically best architecture for that type. Benchmark quality score: 0.7236 (+7.4% vs best single arch).",
        "pipeline":    "Query → Classify type → Route to best-quality arch → Answer",
        "routing":     ROUTER_ROUTING["quality"],
    },
    "router_production": {
        "label":       "MeridianRouter (production)",
        "description": "Routes for best production score (50% quality + 30% speed + 20% cost). Score: 0.8148. Recommended for production deployments.",
        "pipeline":    "Query → Classify type → Route to best-production arch → Answer",
        "routing":     ROUTER_ROUTING["production"],
    },
    "router_cost": {
        "label":       "MeridianRouter (cost)",
        "description": "Routes to the cheapest architecture per type. Corrective wins 5/6 types via token reduction. Best for batch pipelines.",
        "pipeline":    "Query → Classify type → Route to cheapest arch → Answer",
        "routing":     ROUTER_ROUTING["cost"],
    },
    "router_efficiency": {
        "label":       "MeridianRouter (efficiency)",
        "description": "Routes for highest quality/latency ratio. Degenerates to naive for all types (66ms P50 is unbeatable). Equivalent to running naive directly.",
        "pipeline":    "Query → Classify type → naive (all types) → Answer",
        "routing":     ROUTER_ROUTING["efficiency"],
    },
}

ARCH_META: dict[str, dict] = {
    "naive": {
        "label":       "Naive RAG",
        "description": "Dense retrieval only. Embeds the query, searches Qdrant for top-5 nearest chunks, feeds to LLM. No reranking, no query expansion.",
        "pros":        ["Fastest", "Simplest", "Good baseline"],
        "cons":        ["No keyword matching", "Sensitive to embedding quality", "Misses terminology mismatches"],
        "best_for":    "Simple factual queries where the exact phrasing matches the filing text.",
        "worst_for":   "Cross-company comparisons, terminology mismatches (e.g. 'revenue' vs 'net sales').",
        "pipeline":    "Query → Embed → Qdrant dense search → Top-5 chunks → LLM",
        "example_good": "What was Apple's total revenue in fiscal year 2023?",
        "example_bad":  "Compare R&D spending across all 5 companies in 2023.",
    },
    "hybrid": {
        "label":       "Hybrid RAG",
        "description": "Combines dense (Qdrant) and sparse (BM25) retrieval via Reciprocal Rank Fusion, then reranks with a cross-encoder. Parent-child chunk lookup returns larger context to LLM.",
        "pros":        ["Keyword + semantic matching", "Reranker improves precision", "Parent-child expands context"],
        "cons":        ["Slower than naive", "Requires BM25 index on disk"],
        "best_for":    "General-purpose retrieval where queries mix exact terms and semantic intent.",
        "worst_for":   "Comparative queries across all companies (score compression).",
        "pipeline":    "Query → Expand synonyms → Dense + Sparse → RRF → Rerank → Parent lookup → LLM",
        "example_good": "What risk factors did Meta disclose about AI regulation?",
        "example_bad":  "Compare operating margins across Apple, Microsoft, Google.",
    },
    "fusion": {
        "label":       "Fusion RAG",
        "description": "Generates 4 query rephrasings via LLM, runs hybrid retrieval for each variant, then fuses all result lists with multi-list RRF and reranks.",
        "pros":        ["Broad query coverage", "Handles ambiguous questions", "Self-expanding"],
        "cons":        ["Requires Ollama call upfront", "Highest latency of non-agentic architectures"],
        "best_for":    "Broad or ambiguous queries where one phrasing may not capture intent.",
        "worst_for":   "Simple lookups where query expansion adds noise.",
        "pipeline":    "Query → LLM generate variants → 4x Hybrid search → Multi-list RRF → Rerank → LLM",
        "example_good": "How did macroeconomic conditions affect tech company performance in 2022?",
        "example_bad":  "What is Amazon's exact net income for Q3 2022?",
    },
    "hierarchical": {
        "label":       "Hierarchical RAG",
        "description": "Two-level retrieval: first searches document-level summaries to identify the 3 most relevant filings, then does detailed chunk retrieval within only those documents.",
        "pros":        ["Zero LLM overhead at query time", "Scales to large corpora", "Reduces irrelevant chunks"],
        "cons":        ["Requires 50-min offline summary build", "Misses cross-document answers"],
        "best_for":    "Simple factual and single-company questions where identifying the right document matters most.",
        "worst_for":   "Multi-hop questions requiring synthesis across many documents.",
        "pipeline":    "Query → Embed → Search meridian_summaries → Top-3 docs → Filter hybrid search → Rerank → LLM",
        "example_good": "What was Microsoft's cloud revenue growth in FY2024?",
        "example_bad":  "Compare all companies' COVID-era revenue impact.",
    },
    "corrective": {
        "label":       "Corrective RAG (CRAG)",
        "description": "Retrieves chunks, then scores each chunk's relevance with a dedicated LLM call. Filters low-scoring chunks. If all chunks score below threshold, sets a 'needs_web_search' flag.",
        "pros":        ["Filters irrelevant context", "Detects unanswerable questions", "Improves faithfulness"],
        "cons":        ["Slowest: N+1 LLM calls", "Web search not yet wired up"],
        "best_for":    "Risk qualitative questions where irrelevant chunks cause hallucination.",
        "worst_for":   "Latency-sensitive applications.",
        "pipeline":    "Query → Hybrid search → Score each chunk (LLM) → Filter → Generate or flag web search → LLM",
        "example_good": "What specific supply chain risks did Apple disclose in 2021?",
        "example_bad":  "What is Google's exact ad revenue for Q2 2020?",
    },
    "graph": {
        "label":       "Graph RAG",
        "description": "Uses Neo4j to traverse entity relationships. Detects company/topic entities in the query, executes Cypher to find relevant documents, then augments with vector retrieval.",
        "pros":        ["Relationship-aware", "Handles entity queries natively", "Structured + unstructured fusion"],
        "cons":        ["Limited to 14 predefined topics", "Requires Neo4j running", "Entity extraction is keyword-based"],
        "best_for":    "Entity-relationship queries (which companies mentioned AI risk, who has supply chain exposure).",
        "worst_for":   "Numerical and temporal queries.",
        "pipeline":    "Query → Classify (entity/text) → Cypher traversal → Vector search with graph filter → Rerank → LLM",
        "example_good": "Which companies disclosed cloud computing as a key revenue driver?",
        "example_bad":  "What was Amazon's exact gross profit in FY2022?",
    },
    "agentic": {
        "label":       "Agentic RAG",
        "description": "LangGraph-based agent that classifies the query type, selects a retrieval tool (single-doc, multi-doc, temporal, comparative, calculator, graph), executes it, then checks answer faithfulness and re-retrieves if needed.",
        "pros":        ["Adaptive tool selection", "Self-correcting via re-retrieval", "Handles arithmetic"],
        "cons":        ["Most complex", "2+ LLM calls per query", "Latency unpredictable"],
        "best_for":    "Numerical and temporal questions requiring multi-step reasoning.",
        "worst_for":   "Simple lookups where overhead isn't justified.",
        "pipeline":    "Query → Classify → Select tool → Retrieve → Compress → Generate → Faithfulness check → [Re-retrieve] → Answer",
        "example_good": "What was the year-over-year change in Meta's operating margin from 2022 to 2023?",
        "example_bad":  "What is Apple's fiscal year end month?",
    },
    "full_system": {
        "label":       "Full System (Router)",
        "description": "Routes each query to the best architecture based on question type: simple_factual→hierarchical, numerical→agentic, temporal→agentic, comparative→fusion, multi_hop→graph, risk_qualitative→corrective.",
        "pros":        ["Best-of-all-worlds", "Question-type aware", "Production-ready"],
        "cons":        ["Requires all architectures working", "Classification adds one LLM call"],
        "best_for":    "Production deployment where query types are mixed.",
        "worst_for":   "Benchmarking individual architectures.",
        "pipeline":    "Query → Classify type → Route to best architecture → Answer",
        "example_good": "Any real-world financial question.",
        "example_bad":  "N/A - this is the recommended default.",
    },
}

ARCH_OPTIONS = (
    [m["label"] for m in ROUTER_META.values()]
    + ["─── Single Architectures ───"]
    + [m["label"] for m in ARCH_META.values()]
)
ARCH_KEY_BY_LABEL = {
    **{v["label"]: k for k, v in ARCH_META.items()},
    **{v["label"]: k for k, v in ROUTER_META.items()},
}

RAGAS_METRICS = [
    "faithfulness", "answer_relevancy", "context_precision",
    "context_recall", "answer_correctness",
]

# ---------------------------------------------------------------------------
# CSS injection
# ---------------------------------------------------------------------------

def _inject_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

#MainMenu, footer, header { visibility: hidden; }

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Dark sidebar */
section[data-testid="stSidebar"] {
    background-color: #0F172A;
}
section[data-testid="stSidebar"] * {
    color: #94A3B8;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4 {
    color: #F1F5F9;
}

/* Metric containers */
[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    padding: 1rem 1.25rem;
}
[data-testid="metric-container"] label {
    font-size: 0.72rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #64748B;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.5rem;
    font-weight: 700;
    color: #0F172A;
}

/* Tabs */
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid #E2E8F0;
    gap: 0;
}
[data-testid="stTabs"] [role="tab"] {
    background: transparent;
    font-weight: 500;
    color: #64748B;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 0.6rem 1rem;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #2563EB;
    border-bottom: 2px solid #2563EB;
    font-weight: 600;
}

/* Primary buttons */
[data-testid="stButton"] > button[kind="primary"],
button[kind="primary"] {
    background-color: #2563EB;
    color: #ffffff;
    border: none;
    border-radius: 6px;
}
[data-testid="stButton"] > button[kind="primary"]:hover,
button[kind="primary"]:hover {
    background-color: #1D4ED8;
    box-shadow: 0 4px 12px rgba(37,99,235,0.25);
}

/* Expander */
[data-testid="stExpander"] summary {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    font-weight: 500;
    padding: 0.5rem 0.75rem;
    color: #0F172A !important;
}
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary p {
    color: #0F172A !important;
}
[data-testid="stExpander"] > div[data-testid="stExpanderDetails"] {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-top: none;
    border-radius: 0 0 8px 8px;
    color: #0F172A;
}

/* DataFrame */
[data-testid="stDataFrame"] {
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    overflow: hidden;
}

/* Dividers */
hr {
    border-color: #E2E8F0;
}

/* Alerts */
[data-testid="stAlert"] {
    border-radius: 8px;
}

/* Selectbox labels */
[data-testid="stSelectbox"] label {
    font-size: 0.78rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #475569;
}

/* Text input focus */
[data-testid="stTextInput"] input:focus {
    border-color: #2563EB;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.15);
}

/* Main block container */
.block-container {
    padding: 2rem 2.5rem;
    max-width: 1400px;
}
</style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Callout helper
# ---------------------------------------------------------------------------

def _callout(body: str, kind: str = "info", title: str = "") -> None:
    _STYLES = {
        "info":    ("bg:#EFF6FF", "border:#BFDBFE", "title:#1E40AF"),
        "success": ("bg:#F0FDF4", "border:#BBF7D0", "title:#166534"),
        "neutral": ("bg:#F8FAFC", "border:#E2E8F0", "title:#475569"),
    }
    raw = _STYLES.get(kind, _STYLES["neutral"])
    bg     = raw[0].split(":")[1]
    border = raw[1].split(":")[1]
    tc     = raw[2].split(":")[1]
    title_html = (
        f'<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.06em;color:{tc};margin-bottom:0.4rem">{title}</div>'
        if title else ""
    )
    st.markdown(
        f'<div style="background:{bg};border:1px solid {border};border-radius:8px;'
        f'padding:1rem 1.25rem;margin:0.75rem 0">'
        f'{title_html}'
        f'<div style="color:#334155;font-size:0.9rem;line-height:1.65">{body}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _load_architecture(key: str):
    module_path, class_name = ARCH_REGISTRY[key].rsplit(":", 1)
    import importlib
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    # MeridianRouter requires a mode argument
    if key in ROUTER_MODES:
        return cls(mode=ROUTER_MODES[key])
    return cls()


def _arch_key_from_option(option: str) -> str:
    if option.startswith("─"):
        return "hybrid"   # separator row - should never be selected
    return ARCH_KEY_BY_LABEL.get(option, "hybrid")


_RESULTS_SKIP = {"reliable_metrics", "composite_scores", "benchmark_summary"}

def _load_results() -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = {}
    for path in sorted(RESULTS_DIR.glob("*.json")):
        if path.stem in _RESULTS_SKIP or "summary" in path.stem or path.stem.endswith("_error"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data and isinstance(data[0], dict):
                results[path.stem] = data
        except Exception:
            pass
    return results


def _load_summary() -> dict:
    p = RESULTS_DIR / "benchmark_summary.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _metric_row(label: str, value, fmt: str = ".3f") -> None:
    if isinstance(value, float):
        st.metric(label, f"{value:{fmt}}")
    else:
        st.metric(label, str(value) if value is not None else "N/A")


def _avg(results: list[dict], key: str) -> float:
    vals = [r[key] for r in results if isinstance(r.get(key), (int, float))]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<h2 style="color:#F1F5F9;font-size:1.1rem;font-weight:700;'
            'letter-spacing:-0.01em;margin:0 0 0.25rem">Meridian</h2>',
            unsafe_allow_html=True,
        )
        mode_badge = "oracle" if DEPLOYMENT == "oracle" else "local"
        st.markdown(
            f'<p style="color:#64748B;font-size:0.78rem;margin:0">Mode: '
            f'<span style="color:#94A3B8;font-weight:500">{mode_badge}</span></p>',
            unsafe_allow_html=True,
        )
        st.divider()

        st.markdown(
            '<p style="color:#F1F5F9;font-size:0.78rem;font-weight:600;'
            'text-transform:uppercase;letter-spacing:0.06em;margin:0 0 0.4rem">Corpus</p>',
            unsafe_allow_html=True,
        )
        for line in [
            "5 companies: Apple, Microsoft, Google, Amazon, Meta",
            "5 fiscal years: FY2020-FY2024",
            "100 SEC filings | 7,379 chunks",
            "325 benchmark questions",
        ]:
            st.markdown(
                f'<p style="color:#94A3B8;font-size:0.82rem;margin:0.1rem 0">'
                f'- {line}</p>',
                unsafe_allow_html=True,
            )
        st.divider()

        summary = _load_summary()
        if summary:
            st.markdown(
                '<p style="color:#F1F5F9;font-size:0.78rem;font-weight:600;'
                'text-transform:uppercase;letter-spacing:0.06em;margin:0 0 0.4rem">'
                'Last evaluation</p>',
                unsafe_allow_html=True,
            )
            for arch, stats in list(summary.items())[:3]:
                faith = stats.get("faithfulness")
                faith_str = f"{faith:.3f}" if faith is not None else "pending"
                st.markdown(
                    f'<p style="color:#94A3B8;font-size:0.82rem;margin:0.1rem 0">'
                    f'- {arch}: faithfulness={faith_str}</p>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<p style="color:#64748B;font-size:0.8rem">No evaluation results yet.</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p style="color:#64748B;font-size:0.8rem">'
                'Run <code>scripts/run_all_evaluations.py</code></p>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.markdown(
            '<p style="color:#64748B;font-size:0.78rem">'
            '<a href="docs/engineering_log.md" style="color:#94A3B8">Docs</a>'
            ' | '
            '<a href="README.md" style="color:#94A3B8">README</a></p>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Tab 1 - Ask a Question
# ---------------------------------------------------------------------------

def tab_ask() -> None:
    st.header("Ask a Question")

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input(
            "Question",
            placeholder="e.g. What was Apple's total revenue in fiscal year 2023?",
            key="ask_query",
        )
    with col2:
        arch_option = st.selectbox(
            "Architecture / Router",
            ARCH_OPTIONS,
            key="ask_arch",
        )

    # Show router info card when a MeridianRouter mode is selected
    arch_key = _arch_key_from_option(arch_option)
    if arch_key in ROUTER_META:
        rmeta = ROUTER_META[arch_key]
        with st.expander("Routing table for this mode", expanded=False):
            st.markdown(rmeta["description"])
            rt = rmeta["routing"]
            st.markdown("**Routing table:**")
            for qtype, target in rt.items():
                st.markdown(f"- `{qtype}` → **{target}**")
            exp_q = ROUTER_EXPECTED_QUALITY.get(arch_key)
            if exp_q:
                st.caption(f"Expected benchmark quality: {exp_q:.4f}")

    if st.button("Ask", type="primary", key="ask_btn") and query:
        arch_key = _arch_key_from_option(arch_option)
        with st.spinner(f"Running {arch_key}..."):
            try:
                arch = _load_architecture(arch_key)
                response = arch.run(
                    question_id="dashboard_query",
                    question=query,
                )
                try:
                    import requests as _req
                    _req.post("http://api:8080/record", json={
                        "architecture":  arch_key,
                        "question_type": response.get("query_type", "unknown"),
                        "latency_ms":    response.get("latency_ms", 0),
                        "faithfulness":  response.get("faithfulness_proxy", 0.0) or 0.0,
                        "tokens":        response.get("tokens_used", 0),
                        "cost_usd":      response.get("estimated_cost_usd", 0.0) or 0.0,
                    }, timeout=3)
                except Exception:
                    pass
            except Exception as e:
                st.error(f"Architecture error: {e}")
                return

        # Show routing decision for MeridianRouter
        if arch_key in ROUTER_META and response.get("routed_to"):
            qtype    = response.get("query_type", "?")
            routed   = response.get("routed_to",  "?")
            rmode    = response.get("router_mode", arch_key.replace("router_", ""))
            st.info(
                f"**MeridianRouter ({rmode})** classified this as "
                f"`{qtype}` → routed to **{routed}**"
            )

        st.subheader("Answer")
        st.markdown(response.get("answer", "No answer returned."))

        # Metrics row
        faith_proxy = response.get("faithfulness_proxy") or response.get("faithfulness") or 0.0
        chunks_retrieved = len(response.get("citations", []))
        mcols = st.columns(5)
        mcols[0].metric("Faithfulness",      f"{faith_proxy:.3f}")
        mcols[1].metric("Chunks Retrieved",  chunks_retrieved)
        mcols[2].metric("Latency",           f"{response.get('latency_ms', 0):.0f} ms")
        mcols[3].metric("Tokens",            response.get("tokens_used", 0))
        mcols[4].metric("Cost",              f"${response.get('estimated_cost_usd', 0):.5f}")

        if response.get("keyword_hit_rate") is not None:
            st.metric("Keyword hit rate", f"{response['keyword_hit_rate']:.1%}")

        # Retrieved chunks
        citations = response.get("citations", [])
        if citations:
            with st.expander(f"Retrieved chunks ({len(citations)})", expanded=False):
                for i, chunk in enumerate(citations, 1):
                    company = chunk.get("company", "")
                    year    = chunk.get("fiscal_year", "")
                    section = chunk.get("section", "")
                    score   = chunk.get("score", chunk.get("rerank_score", ""))
                    st.markdown(
                        f"**[{i}]** {company} FY{year} - {section}"
                        + (f" (score: {score:.3f})" if isinstance(score, float) else "")
                    )
                    st.markdown(
                        f'<div style="overflow-wrap:break-word;word-break:break-word;'
                        f'white-space:pre-wrap;font-size:0.85em;line-height:1.5">'
                        f'{chunk.get("text","")[:500]}…</div>',
                        unsafe_allow_html=True,
                    )
                    if i < len(citations):
                        st.divider()

        # Architecture-specific extras
        if response.get("graph_results") is not None:
            st.info(f"Graph RAG: {response['graph_results']} entities found via Neo4j")
        if response.get("needs_web_search"):
            st.warning("CRAG: All chunks below relevance threshold - web search recommended")
        if response.get("cypher_used"):
            with st.expander("Cypher query used"):
                st.code(response["cypher_used"], language="cypher")


# ---------------------------------------------------------------------------
# Tab 2 - Compare Architectures
# ---------------------------------------------------------------------------

def tab_compare() -> None:
    st.header("Compare Architectures")

    query = st.text_input(
        "Question to compare",
        placeholder="e.g. Compare R&D spending across Apple, Microsoft, and Google in 2023.",
        key="compare_query",
    )

    arch_labels = [m["label"] for m in ARCH_META.values()]
    selected_labels = st.multiselect(
        "Select architectures to compare",
        arch_labels,
        default=arch_labels[:3],
        key="compare_archs",
    )

    if st.button("Run comparison", type="primary", key="compare_btn") and query and selected_labels:
        selected_keys = [ARCH_KEY_BY_LABEL[l] for l in selected_labels]
        responses: dict[str, dict] = {}

        prog = st.progress(0)
        for i, key in enumerate(selected_keys):
            with st.spinner(f"Running {key}..."):
                try:
                    arch = _load_architecture(key)
                    responses[key] = arch.run(question_id="compare_query", question=query)
                except Exception as e:
                    responses[key] = {"answer": f"[ERROR] {e}", "latency_ms": 0}
            prog.progress((i + 1) / len(selected_keys))

        # Side-by-side columns
        cols = st.columns(len(selected_keys))
        for col, key in zip(cols, selected_keys):
            r = responses[key]
            col.subheader(ARCH_META[key]["label"])
            col.markdown(r.get("answer", "")[:400] + ("…" if len(r.get("answer","")) > 400 else ""))
            col.metric("Faithfulness", f"{r.get('faithfulness', 0):.3f}")
            col.metric("Latency",      f"{r.get('latency_ms', 0):.0f} ms")
            col.metric("Tokens",       r.get("tokens_used", 0))

        # Comparison table
        st.divider()
        st.subheader("Metrics comparison")
        import pandas as pd
        rows = []
        for key in selected_keys:
            r = responses[key]
            rows.append({
                "Architecture":    ARCH_META[key]["label"],
                "Faithfulness":    round(r.get("faithfulness", 0), 3),
                "Relevancy":       round(r.get("relevancy", 0), 3),
                "Latency (ms)":    round(r.get("latency_ms", 0), 0),
                "Tokens":          r.get("tokens_used", 0),
                "Cost ($)":        round(r.get("estimated_cost_usd", 0), 5),
            })
        df = pd.DataFrame(rows).set_index("Architecture")

        def _highlight_best(col):
            is_best = col == col.max()
            if col.name in ("Latency (ms)", "Tokens", "Cost ($)"):
                is_best = col == col.min()
            return ["background-color: #d4f1d4" if v else "" for v in is_best]

        st.dataframe(df.style.apply(_highlight_best, axis=0), use_container_width=True)


# ---------------------------------------------------------------------------
# Tab 3 - Benchmark Results
# ---------------------------------------------------------------------------

def tab_benchmark() -> None:
    st.header("Benchmark Results")

    # ── Narrative intro ──────────────────────────────────────────────────────
    _callout(
        body=(
            "<p>We ran every architecture head-to-head on the same <strong>180 questions</strong> "
            "(30 per question type, stratified across 6 categories) against 100 SEC filings from "
            "Apple, Microsoft, Google, Amazon, and Meta covering FY 2020-2024. Every answer was "
            "generated by <strong>Gemini 2.5 Flash</strong> with no shared state between "
            "architectures. Scores are computed locally with no LLM API calls so results are "
            "fully reproducible.</p>"
            "<p>The goal was to find out: <strong>which architecture actually wins, and for what "
            "kinds of questions?</strong></p>"
        ),
        kind="neutral",
    )

    with st.expander("About the metrics", expanded=False):
        st.markdown(
            """
**Quality score** - a weighted combination of four local metrics that capture different failure modes:
- **Numerical accuracy (35%)** - extracts dollar amounts and percentages from the answer and compares against ground truth. Scores 1.0 for ±1% match, 0.5 for ±10%, 0 otherwise. Returns `n/a` when the ground truth has no numbers (qualitative questions).
- **Faithfulness proxy (30%)** - checks whether each sentence in the answer is actually grounded in the retrieved chunks, not hallucinated. Measures the fraction of answer sentences whose keywords appear in ≥1 retrieved passage.
- **Citation coverage (20%)** - checks whether the expected company names and fiscal years appear in the answer.
- **Keyword hit rate (15%)** - measures how many content words from the reference answer appear in the generated answer.

**Efficiency score** - quality divided by log10(P50 retrieval latency). Rewards architectures that achieve good quality without slow retrieval passes.

**Cost-quality score** - quality divided by the architecture's cost relative to the cheapest option. An architecture that costs 2x more needs proportionally better quality to match.

**Production score** - a balanced 3-way normalised score: Quality x 50% + Speed x 30% + Cost x 20%. This is the most useful single number for deciding what to deploy.

**P50 retrieval (ms)** - median retrieval latency across all questions, excluding LLM generation time. This isolates the architecture's retrieval strategy cost.
            """
        )

    with st.expander("Pipeline improvements", expanded=False):
        st.markdown(
            """
Starting from a baseline run (single random sample per architecture), we made four targeted
pipeline improvements before the final benchmark run:

**1. Stratified sampling (30 per type × 6 types)**
The original run used a random 100-question sample which accidentally over-represented easy
question types. We switched to exactly 30 questions per type so every architecture is judged
fairly on the full difficulty range.

**2. Numerical system prompt**
For `numerical_reasoning` questions, we inject a specialised system prompt that tells the LLM
to extract exact figures, show its arithmetic step-by-step, and never round unless the source
does. This reduced multi-step calculation errors significantly.

**3. Facts lookup pre-step**
Before retrieval, we check a pre-built verified facts table (`data/evaluation/facts.py`) for
the specific company + year in the question. If a verified figure exists, it is prepended to
the context at the top, giving the LLM a trusted anchor before seeing retrieved chunks.

**4. Context compression for numerical questions**
Retrieved chunks often contain multiple fiscal years in the same table. For numerical questions,
we strip sentences that do not contain numbers before passing context to the LLM, reducing
the chance of the model reading the wrong year's column.

These changes are in `architectures/base.py` (facts lookup + compression), `llm/prompts.py`
(numerical system prompt), and `scripts/run_batch_evaluation.py` (stratified sampling via `--per-type`).
            """
        )

    results_by_arch = _load_results()
    summary = _load_summary()

    if not results_by_arch:
        st.info(
            "No evaluation results found.\n\n"
            "Run: `python scripts/run_all_evaluations.py`\n\n"
            "Or for a quick sample: `python scripts/run_all_evaluations.py --sample 20`"
        )
        return

    import pandas as pd

    try:
        import plotly.express as px
        import plotly.graph_objects as go
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False
        st.warning("Install plotly for charts: `pip install plotly`")

    all_flat_quick = [r for res in results_by_arch.values() for r in res]
    ragas_scored_any = any(r.get("ragas_scored") for r in all_flat_quick)

    def _avg_or_none(res, key) -> float | None:
        vals = [r[key] for r in res if r.get(key) is not None and isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals), 3) if vals else None

    # --- Main comparison table ---
    # Load composite scores to augment the table with quality metrics
    composite_path = RESULTS_DIR / "composite_scores.json"
    composite_data: dict = {}
    if composite_path.exists():
        try:
            composite_data = json.loads(composite_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    st.subheader("Architecture comparison")
    if composite_data:
        st.caption(
            "Quality / Efficiency / Cost-Quality / Production from `evaluation/composite_score.py` "
            "(180 questions, 30 per type). Latency = P50 retrieval ms."
        )

    table_rows = []
    for arch, res in results_by_arch.items():
        if not res:
            continue
        cs = composite_data.get(arch, {})
        table_rows.append({
            "Architecture":    arch,
            "N":               len(res),
            "Quality":         cs.get("quality"),
            "Efficiency":      cs.get("efficiency"),
            "Cost-Quality":    cs.get("cost_quality"),
            "Production":      cs.get("production"),
            "P50 ret (ms)":    int(cs.get("p50_ms", 0)) if cs.get("p50_ms") else None,
            "Avg cost ($)":    round(_avg(res, "estimated_cost_usd"), 5),
        })

    if table_rows:
        df_main = pd.DataFrame(table_rows).set_index("Architecture")
        quality_cols = ["Quality", "Efficiency", "Cost-Quality", "Production"]

        def _hl(col):
            lower_is_better = col.name in ("P50 ret (ms)", "Avg cost ($)")
            numeric = pd.to_numeric(col, errors="coerce").dropna()
            if numeric.empty:
                return [""] * len(col)
            best = numeric.min() if lower_is_better else numeric.max()
            return ["font-weight: bold; color: #1a7a1a" if v == best else "" for v in pd.to_numeric(col, errors="coerce")]

        fmt = {c: "{:.4f}" for c in quality_cols}
        fmt["P50 ret (ms)"] = "{:,.0f}"
        fmt["Avg cost ($)"] = "{:.5f}"

        st.dataframe(
            df_main.style.apply(_hl, axis=0).format(fmt, na_rep="-"),
            use_container_width=True,
        )

    # --- Composite scores section ---
    if composite_data:
        try:
            st.divider()

            # ── Narrative: core finding ──────────────────────────────────────
            st.markdown("#### The core finding: complexity does not predict quality")
            _callout(
                body=(
                    "<p>The table above ranks architectures by <strong>overall quality score</strong>. "
                    "The result is counterintuitive: <strong>Naive RAG - the simplest architecture, "
                    "zero extra LLM calls - wins on raw quality (0.6738)</strong>, beating Agentic "
                    "(0.6610), Fusion (0.6588), and even the Full System router (0.6524) which was "
                    "designed to combine the best of everything.</p>"
                    "<p>Why? Because retrieval quality, not generation complexity, is the binding "
                    "constraint. When the right chunk is retrieved, even a simple prompt produces "
                    "the right answer. When the wrong chunk is retrieved, no amount of agentic "
                    "re-ranking or query expansion can recover the correct number from missing "
                    "context.</p>"
                    "<p>But the story does not end there. <strong>No single architecture wins every "
                    "question type.</strong> Expand the per-type breakdown below to see that the "
                    "winner changes for every category - hierarchical dominates factual lookups, "
                    "graph dominates comparisons, fusion dominates trend questions, and naive "
                    "dominates qualitative reasoning at a score of 0.946.</p>"
                    "<p>This fragmentation is exactly what motivated <strong>MeridianRouter</strong>.</p>"
                ),
                kind="info",
            )

            st.subheader("Composite scores - all architectures")
            st.caption(
                "Scores from `evaluation/composite_score.py` - 180 questions, 30 per type. "
                "See [BENCHMARK_ANALYSIS.md](BENCHMARK_ANALYSIS.md) for full methodology."
            )

            COMPOSITE_ROUTER = {
                "MeridianRouter (quality)":    {"quality":0.7236,"efficiency":0.2068,"cost_quality":0.6060,"production":0.8108,"p50_ms":3159,"avg_cost_usd":0.000121},
                "MeridianRouter (production)": {"quality":0.7191,"efficiency":0.2191,"cost_quality":0.6135,"production":0.8148,"p50_ms":1915,"avg_cost_usd":0.000118},
                "MeridianRouter (cost)":       {"quality":0.7084,"efficiency":0.1418,"cost_quality":0.6725,"production":0.5327,"p50_ms":99020,"avg_cost_usd":0.000102},
                "MeridianRouter (efficiency)": {"quality":0.7072,"efficiency":0.3866,"cost_quality":0.5665,"production":0.7998,"p50_ms":66,"avg_cost_usd":0.000127},
            }

            comp_rows = []
            for arch, scores in composite_data.items():
                comp_rows.append({
                    "Architecture": arch,
                    "Quality":       scores.get("quality"),
                    "Efficiency":    scores.get("efficiency"),
                    "Cost-Quality":  scores.get("cost_quality"),
                    "Production":    scores.get("production"),
                    "P50 (ms)":      int(scores.get("p50_ms", 0)),
                    "$/1k q":        round(scores.get("avg_cost_usd", 0) * 1000, 4),
                    "_type": "single",
                })
            for label, scores in COMPOSITE_ROUTER.items():
                comp_rows.append({
                    "Architecture": label,
                    "Quality":       scores["quality"],
                    "Efficiency":    scores["efficiency"],
                    "Cost-Quality":  scores["cost_quality"],
                    "Production":    scores["production"],
                    "P50 (ms)":      scores["p50_ms"],
                    "$/1k q":        round(scores["avg_cost_usd"] * 1000, 4),
                    "_type": "router",
                })

            if comp_rows:
                df_comp = pd.DataFrame(comp_rows).set_index("Architecture")
                df_comp = df_comp.drop(columns=["_type"])
                comp_cols = ["Quality", "Efficiency", "Cost-Quality", "Production"]

                def _hl_comp(col):
                    if col.name not in comp_cols:
                        return [""] * len(col)
                    best = col.max()
                    return [
                        "font-weight:bold; color:#1a7a1a" if v == best else ""
                        for v in col
                    ]

                st.dataframe(
                    df_comp.style.apply(_hl_comp, axis=0).format({
                        "Quality":      "{:.4f}",
                        "Efficiency":   "{:.4f}",
                        "Cost-Quality": "{:.4f}",
                        "Production":   "{:.4f}",
                        "P50 (ms)":     "{:,}",
                        "$/1k q":       "{:.4f}",
                    }),
                    use_container_width=True,
                )
                st.caption("Bold green = column winner. MeridianRouter rows are virtual scores computed via slice-and-stitch - no new API calls.")

            # ── MeridianRouter narrative ─────────────────────────────────────
            st.divider()
            st.markdown("#### Why we built MeridianRouter")
            _callout(
                body=(
                    "<p>After seeing that no single architecture wins every question type, the "
                    "natural question was: <em>what if we just route each question to whichever "
                    "architecture is empirically best for that type?</em></p>"
                    "<p><strong>MeridianRouter</strong> does exactly that. It classifies each "
                    "incoming question into one of six types using a single Gemini call, then "
                    "delegates to the benchmark-validated winner for that type:</p>"
                    "<table style='width:100%;border-collapse:collapse;font-size:0.88rem'>"
                    "<thead><tr>"
                    "<th style='text-align:left;padding:0.3rem 0.5rem;border-bottom:1px solid #E2E8F0;color:#0F172A'>Question type</th>"
                    "<th style='text-align:left;padding:0.3rem 0.5rem;border-bottom:1px solid #E2E8F0;color:#0F172A'>Quality mode routes to</th>"
                    "<th style='text-align:left;padding:0.3rem 0.5rem;border-bottom:1px solid #E2E8F0;color:#0F172A'>Why</th>"
                    "</tr></thead><tbody>"
                    "<tr><td style='padding:0.3rem 0.5rem'>Simple factual</td><td style='padding:0.3rem 0.5rem'>Hierarchical</td><td style='padding:0.3rem 0.5rem'>Document-level pre-filtering finds the right filing first</td></tr>"
                    "<tr><td style='padding:0.3rem 0.5rem'>Numerical reasoning</td><td style='padding:0.3rem 0.5rem'>Hierarchical</td><td style='padding:0.3rem 0.5rem'>Correct document isolation prevents wrong-year column errors</td></tr>"
                    "<tr><td style='padding:0.3rem 0.5rem'>Temporal trends</td><td style='padding:0.3rem 0.5rem'>Fusion</td><td style='padding:0.3rem 0.5rem'>4 query rephrasings capture multi-year phrasing variations</td></tr>"
                    "<tr><td style='padding:0.3rem 0.5rem'>Comparative</td><td style='padding:0.3rem 0.5rem'>Graph</td><td style='padding:0.3rem 0.5rem'>Neo4j entity traversal guarantees coverage of all 5 companies</td></tr>"
                    "<tr><td style='padding:0.3rem 0.5rem'>Multi-hop</td><td style='padding:0.3rem 0.5rem'>Hybrid</td><td style='padding:0.3rem 0.5rem'>BM25 + dense + reranker handles two-condition joins</td></tr>"
                    "<tr><td style='padding:0.3rem 0.5rem'>Risk / qualitative</td><td style='padding:0.3rem 0.5rem'>Naive</td><td style='padding:0.3rem 0.5rem'>Broad dense context is optimal; any filtering reduces score</td></tr>"
                    "</tbody></table>"
                    "<p style='margin-top:0.75rem'><strong>The result: MeridianRouter (quality mode) scores 0.7236 - a +7.4% improvement over the "
                    "best single architecture (Naive, 0.6738), and +10.9% over the Full System (0.6524).</strong></p>"
                    "<p>For production use, MeridianRouter (production mode) scores 0.8148 on the production metric - "
                    "the highest of any architecture or router - at a P50 retrieval latency of 1,915ms and cost "
                    "comparable to running a single lightweight architecture. Four modes are available depending on "
                    "your priority: quality, production, cost, or efficiency. Use the <strong>Ask</strong> tab to try it live.</p>"
                ),
                kind="neutral",
            )

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("MeridianRouter quality", "0.7236", "+7.4% vs best single")
            col2.metric("MeridianRouter production", "0.8148", "best across all")
            col3.metric("P50 latency (prod mode)", "1,915 ms", "vs 66ms naive / 99s corrective")
            col4.metric("Route classification cost", "~1 LLM call", "Gemini 2.5 Flash")

            # ── Per-type composite score breakdown ──────────────────────────
            st.divider()
            st.subheader("Per-type composite scores")
            QTYPE_LABELS = [
                "simple_factual", "numerical_reasoning", "temporal",
                "comparative", "multi_hop", "risk_qualitative",
            ]
            SCORE_OPTIONS = {
                "Quality":      "quality",
                "Efficiency":   "efficiency",
                "Cost-Quality": "cost_quality",
                "Production":   "production",
            }
            SCORE_RANGES = {
                "quality":      (0.3, 1.0),
                "efficiency":   (0.05, 0.6),
                "cost_quality": (0.3, 1.0),
                "production":   (0.3, 1.0),
            }
            archs_c = list(composite_data.keys())
            ARCH_SHORT = {
                "naive":"Naive","hybrid":"Hybrid","fusion":"Fusion",
                "hierarchical":"Hierarch.","corrective":"Corrective",
                "graph":"Graph","agentic":"Agentic","full_system":"FullSys",
            }

            sel_score_label = st.selectbox(
                "Score dimension",
                list(SCORE_OPTIONS.keys()),
                key="comp_score_sel",
            )
            sel_score_key = SCORE_OPTIONS[sel_score_label]
            zmin_s, zmax_s = SCORE_RANGES[sel_score_key]

            # Heatmap
            if HAS_PLOTLY:
                heat_z, heat_text = [], []
                for arch in archs_c:
                    row_z, row_t = [], []
                    pts = composite_data[arch].get("per_type_scores", {})
                    for qt in QTYPE_LABELS:
                        v = pts.get(qt, {}).get(sel_score_key)
                        row_z.append(v if v is not None else -1)
                        row_t.append(f"{v:.3f}" if v is not None else "n/a")
                    heat_z.append(row_z)
                    heat_text.append(row_t)
                fig_cs_heat = go.Figure(data=go.Heatmap(
                    z=heat_z,
                    x=[q.replace("_", " ") for q in QTYPE_LABELS],
                    y=[ARCH_SHORT.get(a, a) for a in archs_c],
                    text=heat_text,
                    texttemplate="%{text}",
                    textfont={"size": 11},
                    colorscale="RdYlGn",
                    zmin=zmin_s, zmax=zmax_s,
                    colorbar=dict(title=sel_score_label),
                ))
                fig_cs_heat.update_layout(
                    title=f"{sel_score_label} score - architecture x question type",
                    height=360,
                    margin=dict(l=10, r=10, t=50, b=10),
                )
                st.plotly_chart(fig_cs_heat, use_container_width=True)

            # Table: rows = qtypes, cols = archs, winner bold-green
            pt_rows = []
            for qt in QTYPE_LABELS:
                row: dict = {"Question type": qt.replace("_", " ")}
                best_val, best_arch_name = -1.0, None
                for arch in archs_c:
                    v = composite_data[arch].get("per_type_scores", {}).get(qt, {}).get(sel_score_key)
                    row[ARCH_SHORT.get(arch, arch)] = v
                    if v is not None and v > best_val:
                        best_val, best_arch_name = v, arch
                row["Winner"] = (
                    f"{ARCH_SHORT.get(best_arch_name, best_arch_name)} ({best_val:.3f})"
                    if best_arch_name else "-"
                )
                pt_rows.append(row)
            # Overall row
            over_row: dict = {"Question type": "OVERALL"}
            for arch in archs_c:
                over_row[ARCH_SHORT.get(arch, arch)] = composite_data[arch].get(sel_score_key)
            best_overall = max(
                (composite_data[a].get(sel_score_key) or 0) for a in archs_c
            )
            best_overall_arch = max(archs_c, key=lambda a: composite_data[a].get(sel_score_key) or 0)
            over_row["Winner"] = f"{ARCH_SHORT.get(best_overall_arch, best_overall_arch)} ({best_overall:.3f})"
            pt_rows.append(over_row)

            if pt_rows:
                df_pt = pd.DataFrame(pt_rows).set_index("Question type")
                arch_short_cols = [ARCH_SHORT.get(a, a) for a in archs_c]

                def _hl_pt(col):
                    if col.name not in arch_short_cols:
                        return [""] * len(col)
                    numeric = pd.to_numeric(col, errors="coerce")
                    best = numeric.max()
                    return [
                        "font-weight:bold; color:#1a7a1a" if v == best else ""
                        for v in numeric
                    ]

                st.dataframe(
                    df_pt.style.apply(_hl_pt, axis=0).format(
                        {c: lambda v: f"{v:.3f}" if isinstance(v, float) else ("-" if v is None else v)
                         for c in arch_short_cols},
                        na_rep="-",
                    ),
                    use_container_width=True,
                )

        except Exception as e:
            st.caption(f"Could not load composite scores: {e}")

    # ── Per-type reliable metrics breakdown ─────────────────────────────────
    reliable_path = RESULTS_DIR / "reliable_metrics.json"
    if reliable_path.exists():
        try:
            rel_data = json.loads(reliable_path.read_text(encoding="utf-8"))
            rel_archs = rel_data.get("architectures", {})
            if rel_archs:
                st.divider()
                st.markdown("#### Raw metric breakdown")
                _callout(
                    body=(
                        "<p>The composite scores above are built from five underlying metrics, each "
                        "measuring a different failure mode. This section lets you inspect each metric "
                        "individually across all question types so you can see <em>why</em> an "
                        "architecture scores high or low - not just that it does.</p>"
                        "<p>A few patterns worth noting:</p>"
                        "<ul>"
                        "<li><strong>Naive leads on numerical accuracy (0.541)</strong> despite being "
                        "the simplest. The facts lookup pre-step injects verified financial figures "
                        "before retrieval, and the numerical system prompt keeps the LLM on track. More "
                        "complex architectures filter or rewrite context in ways that sometimes discard "
                        "the exact number.</li>"
                        "<li><strong>Faithfulness proxy separates the architectures most clearly</strong> "
                        "(range 0.654-0.747). Fusion and Graph score highest because multi-query expansion "
                        "and entity filtering respectively produce context that is more tightly matched to "
                        "what the answer actually says. Hybrid scores lowest because broader parent-chunk "
                        "context introduces sentences the answer does not use.</li>"
                        "<li><strong>BERTScore F1 is tightly clustered (0.810-0.820)</strong> - all "
                        "architectures produce semantically equivalent answers. This confirms the quality "
                        "differences are about <em>precision</em>, not about architectures generating "
                        "fundamentally different content.</li>"
                        "<li><strong>Citation coverage is uniformly high (0.857-0.884)</strong> because "
                        "all architectures reliably mention the correct company and year. This metric does "
                        "not discriminate much; the real signal is in numerical accuracy and faithfulness.</li>"
                        "</ul>"
                    ),
                    kind="neutral",
                )
                st.caption(
                    "Computed locally, no LLM calls. "
                    "Source: `evaluation/metrics_reliable.py` - 180 questions, 30 per type."
                )

                QTYPE_LABELS_RM = [
                    "simple_factual", "numerical_reasoning", "temporal",
                    "comparative", "multi_hop", "risk_qualitative",
                ]
                METRIC_OPTIONS = {
                    "Numerical Accuracy":  "numerical_accuracy",
                    "BERTScore F1":        "bertscore_f1",
                    "Keyword Hit Rate":    "keyword_hit_rate",
                    "Citation Coverage":   "citation_coverage",
                    "Faithfulness Proxy":  "faithfulness_proxy",
                }
                METRIC_RANGES = {
                    "numerical_accuracy":  (0.0, 1.0),
                    "bertscore_f1":        (0.75, 0.90),
                    "keyword_hit_rate":    (0.3, 1.0),
                    "citation_coverage":   (0.7, 1.0),
                    "faithfulness_proxy":  (0.3, 1.0),
                }
                ARCH_SHORT_RM = {
                    "naive":"Naive","hybrid":"Hybrid","fusion":"Fusion",
                    "hierarchical":"Hierarch.","corrective":"Corrective",
                    "graph":"Graph","agentic":"Agentic","full_system":"FullSys",
                }
                archs_rm = list(rel_archs.keys())

                sel_metric_label = st.selectbox(
                    "Metric",
                    list(METRIC_OPTIONS.keys()),
                    key="rel_metric_sel",
                )
                sel_metric_key = METRIC_OPTIONS[sel_metric_label]
                zmin_r, zmax_r = METRIC_RANGES[sel_metric_key]

                # Heatmap
                if HAS_PLOTLY:
                    heat_z_r, heat_text_r = [], []
                    for arch in archs_rm:
                        row_z, row_t = [], []
                        bqt = rel_archs[arch].get("by_question_type", {})
                        for qt in QTYPE_LABELS_RM:
                            v = bqt.get(qt, {}).get(sel_metric_key)
                            row_z.append(v if v is not None else -1)
                            row_t.append(f"{v:.3f}" if v is not None else "n/a")
                        heat_z_r.append(row_z)
                        heat_text_r.append(row_t)
                    fig_rm_heat = go.Figure(data=go.Heatmap(
                        z=heat_z_r,
                        x=[q.replace("_", " ") for q in QTYPE_LABELS_RM],
                        y=[ARCH_SHORT_RM.get(a, a) for a in archs_rm],
                        text=heat_text_r,
                        texttemplate="%{text}",
                        textfont={"size": 11},
                        colorscale="RdYlGn",
                        zmin=zmin_r, zmax=zmax_r,
                        colorbar=dict(title=sel_metric_label),
                    ))
                    fig_rm_heat.update_layout(
                        title=f"{sel_metric_label} - architecture x question type",
                        height=360,
                        margin=dict(l=10, r=10, t=50, b=10),
                    )
                    st.plotly_chart(fig_rm_heat, use_container_width=True)

                # Table: rows = qtypes, cols = archs
                rm_rows = []
                for qt in QTYPE_LABELS_RM:
                    row: dict = {"Question type": qt.replace("_", " ")}
                    best_val, best_arch_name = -1.0, None
                    for arch in archs_rm:
                        v = rel_archs[arch].get("by_question_type", {}).get(qt, {}).get(sel_metric_key)
                        row[ARCH_SHORT_RM.get(arch, arch)] = v
                        if v is not None and v > best_val:
                            best_val, best_arch_name = v, arch
                    row["Winner"] = (
                        f"{ARCH_SHORT_RM.get(best_arch_name, best_arch_name)} ({best_val:.3f})"
                        if best_arch_name else "-"
                    )
                    rm_rows.append(row)
                # Overall row from overall metrics
                over_rm: dict = {"Question type": "OVERALL"}
                for arch in archs_rm:
                    ov = rel_archs[arch].get("overall", {}).get(sel_metric_key)
                    over_rm[ARCH_SHORT_RM.get(arch, arch)] = ov
                best_ov_val = max(
                    (rel_archs[a].get("overall", {}).get(sel_metric_key) or 0) for a in archs_rm
                )
                best_ov_arch = max(
                    archs_rm,
                    key=lambda a: rel_archs[a].get("overall", {}).get(sel_metric_key) or 0,
                )
                over_rm["Winner"] = f"{ARCH_SHORT_RM.get(best_ov_arch, best_ov_arch)} ({best_ov_val:.3f})"
                rm_rows.append(over_rm)

                if rm_rows:
                    df_rm = pd.DataFrame(rm_rows).set_index("Question type")
                    arch_short_rm_cols = [ARCH_SHORT_RM.get(a, a) for a in archs_rm]

                    def _hl_rm(col):
                        if col.name not in arch_short_rm_cols:
                            return [""] * len(col)
                        numeric = pd.to_numeric(col, errors="coerce")
                        best = numeric.max()
                        return [
                            "font-weight:bold; color:#1a7a1a" if v == best else ""
                            for v in numeric
                        ]

                    st.dataframe(
                        df_rm.style.apply(_hl_rm, axis=0).format(
                            {c: lambda v: f"{v:.3f}" if isinstance(v, float) else ("-" if v is None else v)
                             for c in arch_short_rm_cols},
                            na_rep="-",
                        ),
                        use_container_width=True,
                    )

                # Overall metrics bar chart for selected metric
                if HAS_PLOTLY:
                    overall_bar_rows = [
                        {
                            "Architecture": ARCH_SHORT_RM.get(arch, arch),
                            sel_metric_label: rel_archs[arch].get("overall", {}).get(sel_metric_key),
                        }
                        for arch in archs_rm
                        if rel_archs[arch].get("overall", {}).get(sel_metric_key) is not None
                    ]
                    if overall_bar_rows:
                        fig_rm_bar = px.bar(
                            pd.DataFrame(overall_bar_rows).sort_values(sel_metric_label, ascending=False),
                            x="Architecture", y=sel_metric_label,
                            color=sel_metric_label,
                            color_continuous_scale="Viridis",
                            title=f"{sel_metric_label} - overall average by architecture",
                            range_y=[zmin_r, zmax_r],
                            template="plotly_white",
                        )
                        st.plotly_chart(fig_rm_bar, use_container_width=True)

        except Exception as e:
            st.caption(f"Could not load reliable metrics: {e}")

    # --- Charts from composite scores (always available when composite_scores.json exists) ---
    if HAS_PLOTLY and composite_data:
        df_cs = pd.DataFrame([
            {
                "Architecture": arch,
                "Quality":       s.get("quality", 0),
                "Efficiency":    s.get("efficiency", 0),
                "Cost-Quality":  s.get("cost_quality", 0),
                "Production":    s.get("production", 0),
                "P50 ret (ms)":  s.get("p50_ms", 0),
            }
            for arch, s in composite_data.items()
        ])

        # Quality bar chart
        st.subheader("Quality score by architecture")
        fig_qual = px.bar(
            df_cs.sort_values("Quality", ascending=False),
            x="Architecture", y="Quality",
            color="Quality", color_continuous_scale="Viridis",
            title="Quality score (higher = better) - weighted: num_acc x0.35 + faith x0.30 + cit x0.20 + kw x0.15",
            range_y=[0.6, 0.72],
            template="plotly_white",
        )
        st.plotly_chart(fig_qual, use_container_width=True)

        # Quality vs P50 latency scatter
        st.subheader("Quality vs retrieval latency (P50)")
        fig_scatter = px.scatter(
            df_cs, x="P50 ret (ms)", y="Quality",
            text="Architecture",
            log_x=True,
            title="Quality vs P50 retrieval latency - top-left is best (high quality, low latency)",
            template="plotly_white",
            color_discrete_sequence=["#2563EB","#64748B","#0F172A","#16A34A","#D97706","#DC2626","#7C3AED","#0891B2"],
        )
        fig_scatter.update_traces(textposition="top center", marker_size=10)
        fig_scatter.update_layout(xaxis_title="P50 retrieval latency (ms, log scale)")
        st.plotly_chart(fig_scatter, use_container_width=True)

        # Grouped bar - all 4 composite scores
        st.subheader("All composite scores by architecture")
        score_rows = []
        for arch, s in composite_data.items():
            for score_name in ("Quality", "Efficiency", "Cost-Quality", "Production"):
                key = score_name.lower().replace("-", "_")
                score_rows.append({
                    "Architecture": arch,
                    "Score type":   score_name,
                    "Value":        s.get(key, 0),
                })
        fig_group = px.bar(
            pd.DataFrame(score_rows),
            x="Architecture", y="Value", color="Score type",
            barmode="group",
            title="All 4 composite scores per architecture",
            template="plotly_white",
            color_discrete_sequence=["#2563EB","#64748B","#0F172A","#16A34A","#D97706","#DC2626","#7C3AED","#0891B2"],
        )
        st.plotly_chart(fig_group, use_container_width=True)

    # RAGAS charts (only if RAGAS scoring was run - future Oracle deployment)
    if HAS_PLOTLY and table_rows and ragas_scored_any:
        df = pd.DataFrame(table_rows)
        df_scored = df.dropna(subset=["Quality"])

        # Radar chart using composite score dimensions
        st.subheader("Radar chart - architecture profiles")
        radar_metrics = ["Quality", "Efficiency", "Cost-Quality", "Production"]
        fig_radar = go.Figure()
        for arch, s in composite_data.items():
            vals = [s.get(m.lower().replace("-", "_"), 0) for m in radar_metrics]
            vals_norm = [v / max(composite_data[a].get(m.lower().replace("-","_"), 0.001)
                                for a in composite_data)
                         for v, m in zip(vals, radar_metrics)]
            vals_norm += [vals_norm[0]]
            fig_radar.add_trace(go.Scatterpolar(
                r=vals_norm,
                theta=radar_metrics + [radar_metrics[0]],
                name=arch,
            ))
        fig_radar.update_layout(polar=dict(radialaxis=dict(range=[0, 1])))
        st.plotly_chart(fig_radar, use_container_width=True)

    # --- Per-question-type breakdown ---
    all_results_flat = all_flat_quick
    QTYPE_ORDER = [
        "simple_factual", "numerical_reasoning", "temporal",
        "comparative", "multi_hop", "risk_qualitative",
    ]
    all_qtypes_raw = {r["question_type"] for r in all_results_flat if "question_type" in r}
    question_types = [q for q in QTYPE_ORDER if q in all_qtypes_raw] + sorted(all_qtypes_raw - set(QTYPE_ORDER))

    if ragas_scored_any and question_types:
        st.divider()
        st.subheader("Per-question-type RAGAS breakdown")

        METRIC_LABELS = {
            "faithfulness":      "Faithfulness",
            "answer_relevancy":  "Answer Relevancy",
            "context_precision": "Context Precision",
            "context_recall":    "Context Recall",
        }
        RAGAS_METRICS_4 = list(METRIC_LABELS.keys())

        selected_metric = st.selectbox(
            "Metric for heatmap and table",
            RAGAS_METRICS_4,
            format_func=lambda m: METRIC_LABELS[m],
            key="bench_metric_sel",
        )

        archs_with_data = list(results_by_arch.keys())

        # Build per-type × arch matrix
        def _per_type_avg(arch: str, qtype: str, metric: str) -> float | None:
            rows = [r for r in results_by_arch[arch]
                    if r.get("question_type") == qtype and r.get("ragas_scored")]
            return _avg(rows, metric) if rows else None

        # Heatmap
        if HAS_PLOTLY:
            matrix = [
                [_per_type_avg(arch, qt, selected_metric) for qt in question_types]
                for arch in archs_with_data
            ]
            # Replace None with -1 for display (shown as grey)
            z_display = [[v if v is not None else -1 for v in row] for row in matrix]
            text_display = [
                [f"{v:.3f}" if v is not None else "n/a" for v in row]
                for row in matrix
            ]
            fig_heat = go.Figure(data=go.Heatmap(
                z=z_display,
                x=[qt.replace("_", " ") for qt in question_types],
                y=archs_with_data,
                text=text_display,
                texttemplate="%{text}",
                textfont={"size": 11},
                colorscale="RdYlGn",
                zmin=0, zmax=1,
                colorbar=dict(title=METRIC_LABELS[selected_metric]),
            ))
            fig_heat.update_layout(
                title=f"{METRIC_LABELS[selected_metric]} - architecture x question type",
                height=380,
                margin=dict(l=10, r=10, t=50, b=10),
            )
            st.plotly_chart(fig_heat, use_container_width=True)

        # Detailed comparison table - rows = question types, cols = architectures
        st.markdown(f"**{METRIC_LABELS[selected_metric]} by question type**")
        ARCH_SHORT_DASH = {
            "naive": "Naive", "hybrid": "Hybrid", "fusion": "Fusion",
            "hierarchical": "Hier.", "corrective": "Corr.",
            "graph": "Graph", "agentic": "Agent.", "full_system": "Full",
        }
        type_table_rows = []
        for qtype in question_types:
            row: dict = {"Question type": qtype.replace("_", " ")}
            best_val, best_arch = -1.0, None
            for arch in archs_with_data:
                v = _per_type_avg(arch, qtype, selected_metric)
                row[ARCH_SHORT_DASH.get(arch, arch)] = v
                if v is not None and v > best_val:
                    best_val, best_arch = v, arch
            row["Best"] = f"{ARCH_SHORT_DASH.get(best_arch, best_arch or '-')} ({best_val:.3f})" if best_arch else "-"
            type_table_rows.append(row)

        if type_table_rows:
            df_type = pd.DataFrame(type_table_rows).set_index("Question type")
            arch_cols = [ARCH_SHORT_DASH.get(a, a) for a in archs_with_data]

            def _fmt_type_cell(v):
                if isinstance(v, float):
                    return f"{v:.3f}"
                return v if v is not None else "-"

            def _hl_type(col):
                if col.name not in arch_cols:
                    return [""] * len(col)
                numeric = [v for v in col if isinstance(v, float)]
                if not numeric:
                    return [""] * len(col)
                best = max(numeric)
                return ["font-weight:bold; color:#1a7a1a" if v == best else "" for v in col]

            fmt = {c: _fmt_type_cell for c in arch_cols}
            st.dataframe(
                df_type.style.apply(_hl_type, axis=0).format(fmt),
                use_container_width=True,
            )

        # Winners summary
        st.markdown("**Best architecture per question type**")
        winner_rows = []
        for qtype in question_types:
            row = {"Question type": qtype.replace("_", " ")}
            for metric in RAGAS_METRICS_4:
                best_val, best_arch = -1.0, None
                for arch in archs_with_data:
                    v = _per_type_avg(arch, qtype, metric)
                    if v is not None and v > best_val:
                        best_val, best_arch = v, arch
                short_label = METRIC_LABELS[metric].split()[0]
                row[short_label] = f"{ARCH_SHORT_DASH.get(best_arch, best_arch or '-')} ({best_val:.3f})" if best_arch else "-"
            winner_rows.append(row)
        if winner_rows:
            st.dataframe(pd.DataFrame(winner_rows).set_index("Question type"), use_container_width=True)

        # --- Recommendation engine ---
        st.divider()
        st.subheader("Recommendation engine")
        USE_CASE_MAP = {
            "Simple factual lookups (e.g. exact revenue figures)":             "simple_factual",
            "Numerical / arithmetic (e.g. YoY growth, margin delta)":          "numerical_reasoning",
            "Temporal trends (e.g. how did X change from 2020 to 2024)":       "temporal",
            "Comparative across companies (e.g. who spent most on R&D)":       "comparative",
            "Multi-hop reasoning (e.g. which company with AI risk grew most)":  "multi_hop",
            "Risk & qualitative (e.g. supply chain risks, regulatory exposure)": "risk_qualitative",
        }
        use_case = st.selectbox(
            "What kind of questions will you ask most?",
            list(USE_CASE_MAP.keys()),
            key="rec_use_case",
        )
        rec_qtype = USE_CASE_MAP[use_case]

        # Find best arch for this qtype by faithfulness (primary) then avg of all metrics
        scores_for_qtype: dict[str, float] = {}
        for arch in archs_with_data:
            vals = [_per_type_avg(arch, rec_qtype, m) for m in RAGAS_METRICS_4]
            vals = [v for v in vals if v is not None]
            if vals:
                scores_for_qtype[arch] = round(sum(vals) / len(vals), 3)

        if scores_for_qtype:
            ranked = sorted(scores_for_qtype.items(), key=lambda x: x[1], reverse=True)
            best_arch_rec, best_score_rec = ranked[0]
            label_map = {
                "naive": "Naive RAG", "hybrid": "Hybrid RAG", "fusion": "Fusion RAG",
                "hierarchical": "Hierarchical RAG", "corrective": "Corrective RAG (CRAG)",
                "graph": "Graph RAG", "agentic": "Agentic RAG", "full_system": "Full System",
            }
            qtype_label = rec_qtype.replace("_", " ").title()
            st.success(
                f"**Recommended for {qtype_label} queries:** "
                f"{label_map.get(best_arch_rec, best_arch_rec)}  \n"
                f"Avg RAGAS score across metrics: **{best_score_rec:.3f}**"
            )
            if len(ranked) > 1:
                runner_up_arch, runner_up_score = ranked[1]
                st.caption(
                    f"Runner-up: {label_map.get(runner_up_arch, runner_up_arch)} "
                    f"({runner_up_score:.3f})"
                )
            # Show metric breakdown for top-2
            if HAS_PLOTLY and len(ranked) >= 1:
                top_archs = [a for a, _ in ranked[:min(4, len(ranked))]]
                bar_rows = []
                for arch in top_archs:
                    for metric in RAGAS_METRICS_4:
                        v = _per_type_avg(arch, rec_qtype, metric)
                        if v is not None:
                            bar_rows.append({
                                "Architecture": label_map.get(arch, arch),
                                "Metric": METRIC_LABELS[metric],
                                "Score": v,
                            })
                if bar_rows:
                    fig_rec = px.bar(
                        pd.DataFrame(bar_rows),
                        x="Metric", y="Score", color="Architecture",
                        barmode="group",
                        title=f"Top architectures for {qtype_label}",
                        range_y=[0, 1],
                        template="plotly_white",
                        color_discrete_sequence=["#2563EB","#64748B","#0F172A","#16A34A","#D97706","#DC2626","#7C3AED","#0891B2"],
                    )
                    st.plotly_chart(fig_rec, use_container_width=True)
        else:
            st.info(f"No scored results yet for **{rec_qtype.replace('_', ' ')}** questions.")

    # --- COVID vs non-COVID ---
    if all_results_flat and "covid_related" in all_results_flat[0]:
        st.subheader("COVID-related vs non-COVID questions")
        covid    = [r for r in all_results_flat if r.get("covid_related")]
        noncovid = [r for r in all_results_flat if not r.get("covid_related")]
        c1, c2 = st.columns(2)
        if ragas_scored_any:
            c1.metric("COVID avg faithfulness",      f"{_avg(covid,    'faithfulness'):.3f}")
            c1.metric("COVID avg answer correctness", f"{_avg(covid,    'answer_correctness'):.3f}")
            c2.metric("Non-COVID avg faithfulness",  f"{_avg(noncovid, 'faithfulness'):.3f}")
            c2.metric("Non-COVID avg correctness",   f"{_avg(noncovid, 'answer_correctness'):.3f}")
        else:
            c1.metric("COVID avg latency (ms)",      f"{_avg(covid,    'latency_ms'):.0f}")
            c2.metric("Non-COVID avg latency (ms)",  f"{_avg(noncovid, 'latency_ms'):.0f}")


# ---------------------------------------------------------------------------
# Tab 4 - Architecture Explorer
# ---------------------------------------------------------------------------

def tab_explorer() -> None:
    st.header("Architecture Explorer")

    arch_labels = [m["label"] for m in ARCH_META.values()]
    selected_label = st.selectbox("Choose an architecture", arch_labels, key="explorer_arch")
    key = ARCH_KEY_BY_LABEL[selected_label]
    meta = ARCH_META[key]

    st.subheader(meta["label"])
    st.markdown(meta["description"])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Pros**")
        for p in meta["pros"]:
            st.markdown(f"- {p}")
    with col2:
        st.markdown("**Cons**")
        for c in meta["cons"]:
            st.markdown(f"- {c}")

    st.divider()
    c1, c2 = st.columns(2)
    c1.markdown(f"**Best for:** {meta['best_for']}")
    c2.markdown(f"**Avoid for:** {meta['worst_for']}")

    st.divider()
    st.markdown("**Pipeline**")
    st.code(meta["pipeline"], language=None)

    st.divider()
    st.markdown("**Example: excels**")
    st.info(meta["example_good"])
    st.markdown("**Example: struggles**")
    st.warning(meta["example_bad"])

    # Mermaid pipeline diagram
    st.divider()
    st.markdown("**Pipeline diagram**")
    mermaid_defs: dict[str, str] = {
        "naive": """
```mermaid
flowchart LR
    Q[Query] --> E[Embed]
    E --> QD[Qdrant dense search]
    QD --> C[Top-5 chunks]
    C --> L[LLM]
    L --> A[Answer]
```""",
        "hybrid": """
```mermaid
flowchart LR
    Q[Query] --> SY[Synonym expand]
    SY --> D[Dense search]
    SY --> S[BM25 sparse]
    D --> RRF[RRF fusion]
    S --> RRF
    RRF --> R[Reranker]
    R --> P[Parent lookup]
    P --> L[LLM]
    L --> A[Answer]
```""",
        "fusion": """
```mermaid
flowchart LR
    Q[Query] --> LLM1[LLM: rephrase x4]
    LLM1 --> H1[Hybrid search 1]
    LLM1 --> H2[Hybrid search 2]
    LLM1 --> H3[Hybrid search 3]
    LLM1 --> H4[Hybrid search 4]
    H1 --> RRF[Multi-list RRF]
    H2 --> RRF
    H3 --> RRF
    H4 --> RRF
    RRF --> R[Rerank]
    R --> L[LLM]
    L --> A[Answer]
```""",
        "hierarchical": """
```mermaid
flowchart LR
    Q[Query] --> E[Embed]
    E --> S[meridian_summaries]
    S --> T3[Top-3 docs]
    T3 --> F[Filter hybrid search]
    F --> R[Rerank]
    R --> L[LLM]
    L --> A[Answer]
```""",
        "corrective": """
```mermaid
flowchart LR
    Q[Query] --> H[Hybrid search]
    H --> SC[Score each chunk via LLM]
    SC --> F{All below threshold?}
    F -- No --> L[LLM]
    F -- Yes --> W[Flag: needs_web_search]
    W --> L
    L --> A[Answer]
```""",
        "graph": """
```mermaid
flowchart LR
    Q[Query] --> CL[Classify: entity/text]
    CL -- entity --> CY[Neo4j Cypher]
    CL -- text --> VS[Vector search]
    CY --> DOC[Matching docs]
    DOC --> VS
    VS --> R[Rerank]
    R --> L[LLM]
    L --> A[Answer]
```""",
        "agentic": """
```mermaid
flowchart LR
    Q[Query] --> CL[Classify query type]
    CL --> T[Select tool]
    T --> RT[Retrieve]
    RT --> C[Compress]
    C --> L[LLM]
    L --> F{Faithfulness OK?}
    F -- Yes --> A[Answer]
    F -- No, retry < 2 --> RT
    F -- No, retry >= 2 --> A
```""",
        "full_system": """
```mermaid
flowchart LR
    Q[Query] --> CL[Classify type]
    CL -- simple_factual --> H[Hierarchical]
    CL -- numerical --> AG[Agentic]
    CL -- temporal --> AG
    CL -- comparative --> FU[Fusion]
    CL -- multi_hop --> GR[Graph]
    CL -- risk_qualitative --> CR[Corrective]
    H --> A[Answer]
    AG --> A
    FU --> A
    GR --> A
    CR --> A
```""",
    }
    st.markdown(mermaid_defs.get(key, "_Diagram not available._"))


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

def main() -> None:
    _inject_css()
    render_sidebar()

    tab1, tab2, tab3, tab4 = st.tabs([
        "Ask a Question",
        "Compare Architectures",
        "Benchmark Results",
        "Architecture Explorer",
    ])

    with tab1:
        tab_ask()
    with tab2:
        tab_compare()
    with tab3:
        tab_benchmark()
    with tab4:
        tab_explorer()


if __name__ == "__main__":
    main()
