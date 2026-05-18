"""Tests for data/evaluation/questions.json."""

import json
import sys
from pathlib import Path
from collections import Counter

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

QUESTIONS_PATH = ROOT / "data" / "evaluation" / "questions.json"

REQUIRED_FIELDS = [
    "id", "type", "question", "ground_truth",
    "companies", "years", "covid_related", "difficulty",
]

EXPECTED_COUNTS = {
    "simple_factual":    50,
    "numerical_reasoning": 50,
    "temporal":          60,
    "comparative":       60,
    "multi_hop":         55,
    "risk_qualitative":  50,
}

VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_TYPES        = set(EXPECTED_COUNTS.keys())


@pytest.fixture(scope="module")
def questions():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_total_count(questions):
    assert len(questions) == 325, f"Expected 325, got {len(questions)}"


@pytest.mark.parametrize("qtype,expected", EXPECTED_COUNTS.items())
def test_count_per_type(questions, qtype, expected):
    count = sum(1 for q in questions if q["type"] == qtype)
    assert count == expected, f"{qtype}: expected {expected}, got {count}"


def test_all_ids_unique(questions):
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids)), "Duplicate question IDs found"


def test_required_fields_present(questions):
    for q in questions:
        for field in REQUIRED_FIELDS:
            assert field in q, f"Question {q.get('id')} missing field '{field}'"


def test_valid_types(questions):
    for q in questions:
        assert q["type"] in VALID_TYPES, \
            f"Question {q['id']} has invalid type '{q['type']}'"


def test_valid_difficulties(questions):
    for q in questions:
        assert q["difficulty"] in VALID_DIFFICULTIES, \
            f"Question {q['id']} has invalid difficulty '{q['difficulty']}'"


def test_non_qualitative_has_ground_truth(questions):
    """Only risk_qualitative may have null ground_truth."""
    for q in questions:
        if q["type"] != "risk_qualitative":
            assert q["ground_truth"] is not None, \
                f"Question {q['id']} (type={q['type']}) has null ground_truth"


def test_covid_questions_difficulty(questions):
    """COVID-related questions should be medium or hard."""
    for q in questions:
        if q.get("covid_related"):
            assert q["difficulty"] in {"medium", "hard"}, \
                f"COVID question {q['id']} should be medium/hard, got {q['difficulty']}"


def test_risk_qualitative_has_keywords(questions):
    """Every risk_qualitative question must have a keywords list."""
    for q in questions:
        if q["type"] == "risk_qualitative":
            assert "keywords" in q, f"Question {q['id']} missing keywords"
            assert isinstance(q["keywords"], list), \
                f"Question {q['id']} keywords must be a list"


def test_risk_qualitative_keywords_min_length(questions):
    """Each keywords list must have >= 5 items."""
    for q in questions:
        if q["type"] == "risk_qualitative":
            assert len(q.get("keywords", [])) >= 5, \
                f"Question {q['id']} has fewer than 5 keywords"


def test_companies_field_is_list(questions):
    for q in questions:
        assert isinstance(q["companies"], list), \
            f"Question {q['id']} companies must be a list"
        assert len(q["companies"]) >= 1


def test_years_field_is_list(questions):
    for q in questions:
        assert isinstance(q["years"], list), \
            f"Question {q['id']} years must be a list"
        assert all(2020 <= y <= 2024 for y in q["years"]), \
            f"Question {q['id']} has year outside 2020-2024"
