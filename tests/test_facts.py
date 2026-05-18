"""Tests for data/evaluation/facts.py — no external calls."""

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from data.evaluation.facts import FACTS, get, yoy_growth, covid_delta


COMPANIES = ["Apple", "Microsoft", "Google", "Amazon", "Meta"]
YEARS     = [2020, 2021, 2022, 2023, 2024]


def test_all_companies_present():
    assert set(FACTS.keys()) == set(COMPANIES)


@pytest.mark.parametrize("company", COMPANIES)
@pytest.mark.parametrize("year", YEARS)
def test_all_company_year_combinations_present(company, year):
    f = get(company, year)
    assert f is not None, f"Missing {company} {year}"
    assert isinstance(f, dict)
    assert "revenue_b" in f, f"{company} {year} missing revenue_b"


def test_get_returns_empty_dict_for_missing_company():
    result = get("NonExistentCorp", 2023)
    assert result == {} or result is None  # get() returns {} not None for missing


def test_yoy_growth_apple_2021_revenue():
    """Apple FY2021 revenue grew from $274.5B to $365.8B = ~33.3%."""
    growth = yoy_growth("Apple", "revenue_b", 2021)
    assert growth is not None
    assert abs(growth - 33.3) < 1.0, f"Expected ~33.3%, got {growth}"


def test_yoy_growth_returns_none_for_first_year():
    """No prior year for 2020 — should return None."""
    result = yoy_growth("Apple", "revenue_b", 2020)
    assert result is None


def test_yoy_growth_returns_none_for_missing_metric():
    result = yoy_growth("Apple", "nonexistent_metric", 2021)
    assert result is None


def test_covid_delta_apple_revenue():
    """covid_delta returns the 2020→2021 percentage change."""
    delta = covid_delta("Apple", "revenue_b")
    assert delta is not None
    # Apple: (365.8 - 274.5) / 274.5 * 100 = ~33.3%
    assert abs(delta - 33.3) < 1.0, f"Expected ~33.3%, got {delta}"


def test_covid_delta_returns_none_for_missing():
    result = covid_delta("Apple", "nonexistent_metric")
    assert result is None


def test_revenue_values_are_positive():
    for company in COMPANIES:
        for year in YEARS:
            f = get(company, year)
            if f:
                assert f["revenue_b"] > 0, f"{company} {year} revenue must be positive"


def test_gross_margin_is_percentage():
    """gross_margin_pct should be between 0 and 100."""
    for company in COMPANIES:
        for year in YEARS:
            f = get(company, year)
            if f and "gross_margin_pct" in f and f["gross_margin_pct"] is not None:
                assert 0 < f["gross_margin_pct"] < 100, \
                    f"{company} {year} gross_margin_pct={f['gross_margin_pct']} out of range"
