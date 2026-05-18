"""
Meridian test fixtures — no LLM calls, no Qdrant, no disk I/O beyond project files.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def sample_questions():
    """10 questions from questions.json (first 10)."""
    path = ROOT / "data" / "evaluation" / "questions.json"
    with open(path, encoding="utf-8") as f:
        all_q = json.load(f)
    return all_q[:10]


@pytest.fixture(scope="session")
def all_questions():
    """Full 325-question set."""
    path = ROOT / "data" / "evaluation" / "questions.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def sample_facts():
    """Apple FY2023 facts dict."""
    from data.evaluation.facts import get
    return get("Apple", 2023)


@pytest.fixture
def mock_chunks():
    """Three plausible chunk dicts matching retriever output schema."""
    return [
        {
            "chunk_id":      "apple_2023_10k_item7_chunk_0001",
            "text":          "Total net sales for fiscal year 2023 were $383,285 million.",
            "score":         0.91,
            "company":       "Apple",
            "fiscal_year":   2023,
            "section":       "Item 7",
            "document_type": "10-K",
            "document_path": "apple_2023_10k",
            "page_range":    [20, 21],
        },
        {
            "chunk_id":      "microsoft_2023_10k_item7_chunk_0003",
            "text":          "Research and development expenses were $27.2 billion in fiscal 2023.",
            "score":         0.85,
            "company":       "Microsoft",
            "fiscal_year":   2023,
            "section":       "Item 7",
            "document_type": "10-K",
            "document_path": "microsoft_2023_10k",
            "page_range":    [30, 31],
        },
        {
            "chunk_id":      "meta_2023_10k_item1a_chunk_0007",
            "text":          "Our business is subject to risks related to supply chain disruptions.",
            "score":         0.78,
            "company":       "Meta",
            "fiscal_year":   2023,
            "section":       "Item 1A",
            "document_type": "10-K",
            "document_path": "meta_2023_10k",
            "page_range":    [10, 11],
        },
    ]


@pytest.fixture
def mock_result(mock_chunks):
    """One complete result dict matching the architecture run() output schema."""
    return {
        "question_id":        "test_q_001",
        "architecture_name":  "naive",
        "question":           "What was Apple revenue 2023?",
        "answer":             "Apple total net sales were $383,285 million in FY2023.",
        "citations":          [
            {
                "chunk_id": c["chunk_id"],
                "text":     c["text"],
                "score":    c["score"],
                "company":  c["company"],
                "year":     c["fiscal_year"],
                "section":  c["section"],
            }
            for c in mock_chunks
        ],
        "faithfulness":       0.85,
        "answer_relevancy":   0.90,
        "context_precision":  0.80,
        "context_recall":     0.75,
        "answer_correctness": 0.88,
        "latency_ms":         4200.0,
        "tokens_used":        1315,
        "estimated_cost_usd": 0.000263,
        "keyword_hit_rate":   None,
        # extra fields used by metrics.py
        "question_type":  "simple_factual",
        "difficulty":     "easy",
        "covid_related":  False,
        "companies":      ["Apple"],
        "years":          [2023],
        "n_citations":    3,
    }
