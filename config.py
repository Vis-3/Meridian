"""
Meridian — single source of truth for all configuration.
No magic numbers or hardcoded paths anywhere else in the project.
"""

from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()  # loads .env into os.environ if present

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EVAL_DIR = DATA_DIR / "evaluation"
RESULTS_DIR = EVAL_DIR / "results"
INDEX_DIR = DATA_DIR / "indexes"   # persisted BM25 indexes

# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------
COMPANIES = ["Apple", "Microsoft", "Google", "Amazon", "Meta"]
YEARS = [2020, 2021, 2022, 2023, 2024]

CIK_MAP = {
    "Apple":     "0000320193",
    "Microsoft": "0000789019",
    "Google":    "0001652044",
    "Amazon":    "0001018724",
    "Meta":      "0001326801",
}

# Apple fiscal year ends September; Microsoft ends June; rest are calendar year.
# Values: month number when fiscal year ENDS
FISCAL_YEAR_END_MONTH = {
    "Apple":     9,   # September
    "Microsoft": 6,   # June
    "Google":    12,
    "Amazon":    12,
    "Meta":      12,
}

DOCUMENT_TYPES = ["10-K", "10-Q"]

# SEC EDGAR endpoints
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_BASE_URL   = "https://www.sec.gov"
EDGAR_HEADERS    = {"User-Agent": "Meridian research@meridian-rag.com"}
EDGAR_RATE_LIMIT_SLEEP = 0.12   # seconds between requests (~8 req/s, under 10 limit)
EDGAR_MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------
# Sections we care about (10-K Item numbers)
TARGET_SECTIONS = {
    "Item 1":   "Business",
    "Item 1A":  "Risk Factors",
    "Item 7":   "MD&A",
    "Item 8":   "Financial Statements",
}

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
FIXED_CHUNK_SIZE  = 512    # tokens
FIXED_OVERLAP     = 50     # tokens

SEMANTIC_THRESHOLD = 0.85  # cosine similarity below this → split

RECURSIVE_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

PARENT_CHUNK_SIZE = 1024   # tokens — returned to LLM
CHILD_CHUNK_SIZE  = 256    # tokens — used for retrieval

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
TOP_K_RETRIEVAL = 20
TOP_K_RERANK    = 5
RRF_K           = 60       # reciprocal rank fusion constant

HYBRID_DENSE_WEIGHT  = 0.6
HYBRID_SPARSE_WEIGHT = 0.4

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
EMBEDDING_MODEL_FAST    = "all-MiniLM-L6-v2"
EMBEDDING_MODEL_QUALITY = "BAAI/bge-large-en-v1.5"
EMBEDDING_MODEL         = EMBEDDING_MODEL_QUALITY   # default

RERANKER_MODEL = "BAAI/bge-reranker-base"

LLM_MODEL       = "llama3.1:8b"
OLLAMA_BASE_URL = "http://localhost:11434"
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS  = 1024

# spaCy model for NER
SPACY_MODEL = "en_core_web_trf"

# ---------------------------------------------------------------------------
# Vector store — Qdrant
# ---------------------------------------------------------------------------

COLLECTION_NAMES = {
    "fixed":                   "meridian_fixed",
    "semantic":                "meridian_semantic",
    "recursive":               "meridian_recursive",
    "hierarchical_chunks":     "meridian_hier_chunks",
    "hierarchical_summaries":  "meridian_hier_summaries",
}

EMBEDDING_DIM = {
    "all-MiniLM-L6-v2":       384,
    "BAAI/bge-large-en-v1.5": 1024,
}

# ---------------------------------------------------------------------------
# Deployment mode  (must be defined before Graph DB / Qdrant URL references)
# ---------------------------------------------------------------------------
DEPLOYMENT    = os.getenv("DEPLOYMENT", "local")   # "local", "oracle", or "gemini"
USE_GROQ      = DEPLOYMENT == "oracle"
USE_GEMINI    = DEPLOYMENT == "gemini"
LLM_PROVIDER  = os.getenv("LLM_PROVIDER", "ollama")   # "ollama", "groq", "gemini"

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL            = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")        # legacy alias
GEMINI_GENERATION_MODEL = os.getenv("GEMINI_GENERATION_MODEL", "gemini-2.5-flash")
GEMINI_RAGAS_MODEL      = os.getenv("GEMINI_RAGAS_MODEL",      "gemini-2.5-flash-lite")

# Qdrant and Neo4j URLs — overridable via env for oracle deployment
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
NEO4J_URI  = os.getenv("NEO4J_URI",  "bolt://localhost:7687")

# ---------------------------------------------------------------------------
# Graph DB — Neo4j
# ---------------------------------------------------------------------------
NEO4J_URL      = NEO4J_URI   # alias used by graph/loader.py and graph_rag.py
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "meridian123")

KEY_TOPICS = [
    "artificial intelligence", "machine learning", "cloud",
    "supply chain", "COVID", "pandemic", "inflation",
    "interest rate", "regulation", "competition",
    "layoffs", "restructuring", "efficiency",
]

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
FAITHFULNESS_THRESHOLD         = 0.7
RETRIEVAL_RELEVANCE_THRESHOLD  = 0.5
MAX_RETRIES                    = 2

# Cost estimate for local Ollama compute ($/1K tokens)
COST_PER_1K_INPUT_TOKENS  = 0.0002
COST_PER_1K_OUTPUT_TOKENS = 0.0002

# ---------------------------------------------------------------------------
# Agent / LangGraph
# ---------------------------------------------------------------------------
QUERY_TYPES = [
    "simple_factual",
    "numerical",
    "temporal",
    "comparative",
    "multi_hop",
    "risk_qualitative",
]

# Map query type → best architecture for full_system.py
BEST_ARCH_PER_TYPE = {
    "simple_factual":  "hierarchical",
    "numerical":       "agentic",
    "temporal":        "agentic",
    "comparative":     "fusion",
    "multi_hop":       "graph",
    "risk_qualitative":"corrective",
}

# ---------------------------------------------------------------------------
# AWS S3
# ---------------------------------------------------------------------------
S3_RAW_BUCKET       = os.getenv("S3_RAW_BUCKET",       "meridian-raw-sanskar")
S3_PROCESSED_BUCKET = os.getenv("S3_PROCESSED_BUCKET", "meridian-processed-sanskar")
S3_REGION           = os.getenv("AWS_DEFAULT_REGION",  "us-east-2")

# S3 key patterns
# raw:       {company}/{year}/{doctype}/{filename}
# processed: {company}/{year}/{doctype}/{filename}.json

S3_RAW_PREFIX       = "{company}/{year}/{doctype}/"
S3_PROCESSED_PREFIX = "{company}/{year}/{doctype}/"

# ---------------------------------------------------------------------------
# Prometheus / Grafana monitoring
# ---------------------------------------------------------------------------
PROMETHEUS_PORT     = 8000          # app exposes metrics here
PROMETHEUS_SCRAPE_INTERVAL = "15s"

# Metric names (used in monitoring/prometheus_metrics.py)
METRIC_QUERY_LATENCY    = "meridian_query_latency_seconds"
METRIC_TOKENS_USED      = "meridian_tokens_used_total"
METRIC_RETRIEVAL_COUNT  = "meridian_retrieval_count_total"
METRIC_FAITHFULNESS     = "meridian_faithfulness_score"
METRIC_QUERIES_TOTAL    = "meridian_queries_total"

# ---------------------------------------------------------------------------
# PySpark
# ---------------------------------------------------------------------------
SPARK_APP_NAME   = "MeridianExtractor"
SPARK_MASTER     = "local[*]"       # use all local cores; swap for cluster URL
SPARK_LOG_LEVEL  = "WARN"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR  = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "meridian.log"
