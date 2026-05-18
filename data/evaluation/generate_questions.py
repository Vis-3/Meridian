"""
Meridian — Question Set Generator
===================================
Generates data/evaluation/questions.json — exactly 325 questions across 6 types:
  simple_factual(50), numerical_reasoning(50), temporal(60),
  comparative(60), multi_hop(55), risk_qualitative(50).

Facts imported from data/evaluation/facts.py.
Any template whose required field is None is skipped automatically.
Meta FY2024 family_map_millions is None by design — templates using it skip FY2024.

Usage:
    python data/evaluation/generate_questions.py
Output:
    data/evaluation/questions.json
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT))

from config import EVAL_DIR
from data.evaluation.facts import get, yoy_growth, covid_delta
from data.evaluation.qualitative_ground_truths import QUALITATIVE_GROUND_TRUTHS

SEED = 42

QUESTION_COUNTS: dict[str, int] = {
    "simple_factual":      50,
    "numerical_reasoning": 50,
    "temporal":            60,
    "comparative":         60,
    "multi_hop":           55,
    "risk_qualitative":    50,
}
TOTAL_TARGET = sum(QUESTION_COUNTS.values())  # 325

_C  = ["Apple", "Microsoft", "Google", "Amazon", "Meta"]
_Y  = [2020, 2021, 2022, 2023, 2024]
_GY = [2021, 2022, 2023, 2024]           # years where YoY growth is computable


# ===========================================================================
# QuestionTemplate dataclass
# ===========================================================================

@dataclass
class QuestionTemplate:
    """Declarative description of one family of questions."""
    template_id:      str
    q_type:           str
    question_fn:      Callable[..., str | None]
    ground_truth_fn:  Callable[..., str | None]
    companies_fn:     Callable[[], list]   # () → list[str]
    years_fn:         Callable[[], list]   # () → list[int] or [list[int]] for temporal
    mode:             str                  # "single" | "temporal" | "comparative"
    difficulty:       str                  # "easy" | "medium" | "hard"
    requires_table:   bool = False
    requires_multi_hop: bool = False
    requires_graph:   bool = False
    covid_related:    bool = False
    sections_needed:  list[str] = field(default_factory=list)


# ===========================================================================
# Utility helpers
# ===========================================================================

def _bump(d: str) -> str:
    """Bump difficulty one level for covid-related questions."""
    return {"easy": "medium", "medium": "hard", "hard": "hard"}[d]


def _pct(num, denom) -> float | None:
    if num is None or denom is None or denom == 0:
        return None
    return round(num / denom * 100, 1)


def _trend(company: str, metric: str, label: str,
           prefix: str = "$", suffix: str = "B") -> str | None:
    """Build 'FY2020 $X → … FY2024 $Y. Total +Z%.' string.
    Returns None if any year's value is missing."""
    vals: list[tuple[int, float]] = []
    for y in _Y:
        v = get(company, y).get(metric)
        if v is None:
            return None
        vals.append((y, v))
    parts = " → ".join(f"FY{y} {prefix}{v}{suffix}" for y, v in vals)
    first, last = vals[0][1], vals[-1][1]
    if first and first != 0:
        total = round((last - first) / abs(first) * 100, 1)
        sign  = "+" if total >= 0 else ""
        return f"{company}'s {label}: {parts}. Total change FY2020–FY2024: {sign}{total}%."
    return f"{company}'s {label}: {parts}."


def _rank(companies: list[str], metric: str, year: int, label: str,
          prefix: str = "$", suffix: str = "B") -> str | None:
    """Rank companies by metric in a year. Returns None if any value missing."""
    pairs: list[tuple[str, float]] = []
    for c in companies:
        v = get(c, year).get(metric)
        if v is None:
            return None
        pairs.append((c, v))
    pairs.sort(key=lambda x: x[1], reverse=True)
    body = ", ".join(f"{c} {prefix}{v}{suffix}" for c, v in pairs)
    return (
        f"In FY{year}, ranked by {label}: {body}. "
        f"{pairs[0][0]} ranked first among this group."
    )


def _record(tpl: QuestionTemplate, question: str, ground_truth,
            companies: list[str], years: list[int], difficulty: str) -> dict:
    return {
        "type":               tpl.q_type,
        "question":           question,
        "ground_truth":       ground_truth,
        "companies":          companies,
        "years":              years,
        "requires_table":     tpl.requires_table,
        "requires_multi_hop": tpl.requires_multi_hop,
        "requires_graph":     tpl.requires_graph,
        "covid_related":      tpl.covid_related,
        "difficulty":         difficulty,
        "sections_needed":    tpl.sections_needed,
    }


def _expand(tpl: QuestionTemplate) -> list[dict]:
    """Expand one template into all valid candidate question dicts."""
    out: list[dict] = []
    companies = tpl.companies_fn()
    years     = tpl.years_fn()
    diff_base = tpl.difficulty

    if tpl.mode == "single":
        for c in companies:
            for y in years:
                try:
                    q  = tpl.question_fn(c, y)
                    gt = tpl.ground_truth_fn(c, y)
                except Exception:
                    continue
                if q is None:
                    continue
                if gt is None and tpl.q_type != "risk_qualitative":
                    continue
                diff = _bump(diff_base) if tpl.covid_related else diff_base
                out.append(_record(tpl, q, gt, [c], [y], diff))

    elif tpl.mode == "temporal":
        for c in companies:
            try:
                q  = tpl.question_fn(c, years)
                gt = tpl.ground_truth_fn(c, years)
            except Exception:
                continue
            if q is None or gt is None:
                continue
            diff = _bump(diff_base) if tpl.covid_related else diff_base
            out.append(_record(tpl, q, gt, [c], list(years), diff))

    elif tpl.mode == "comparative":
        for y in years:
            try:
                q  = tpl.question_fn(companies, y)
                gt = tpl.ground_truth_fn(companies, y)
            except Exception:
                continue
            if q is None or gt is None:
                continue
            diff = _bump(diff_base) if tpl.covid_related else diff_base
            out.append(_record(tpl, q, gt, list(companies), [y], diff))

    return out


def _collect(templates: list[QuestionTemplate], quota: int) -> list[dict]:
    """Expand all templates, deduplicate, shuffle, trim to quota."""
    candidates: list[dict] = []
    for tpl in templates:
        candidates.extend(_expand(tpl))
    rng = random.Random(SEED)
    rng.shuffle(candidates)
    return candidates[:quota]


# ===========================================================================
# SIMPLE FACTUAL — 50 questions
# single company, single year, direct lookup, difficulty = easy
# ===========================================================================

def _sf_tpl(tid: str, metric: str, q_tmpl: str, gt_tmpl: str,
            diff: str = "easy", req_tbl: bool = True,
            sections: list[str] | None = None,
            cos: list[str] | None = None,
            yrs: list[int] | None = None,
            covid: bool = False) -> QuestionTemplate:
    _cos = cos or _C
    _yrs = yrs or _Y
    _sec = sections or ["Item 8", "Item 7"]

    def qfn(c, y, _m=metric, _q=q_tmpl):
        v = get(c, y).get(_m)
        if v is None:
            return None
        return _q.format(c=c, y=y, v=v)

    def gtfn(c, y, _m=metric, _g=gt_tmpl):
        v = get(c, y).get(_m)
        if v is None:
            return None
        return _g.format(c=c, y=y, v=v)

    return QuestionTemplate(
        template_id=tid, q_type="simple_factual",
        question_fn=qfn, ground_truth_fn=gtfn,
        companies_fn=lambda _c=_cos: _c,
        years_fn=lambda _y=_yrs: _y,
        mode="single", difficulty=diff,
        requires_table=req_tbl, sections_needed=_sec,
        covid_related=covid,
    )


def _build_simple_factual() -> list[dict]:
    tpls: list[QuestionTemplate] = [
        # Generic — all 5 companies × 5 years
        _sf_tpl("sf_revenue",     "revenue_b",
                "What was {c}'s total revenue in FY{y}?",
                "{c}'s total revenue in FY{y} was ${v}B."),
        _sf_tpl("sf_net_income",  "net_income_b",
                "What was {c}'s net income in FY{y}?",
                "{c}'s net income in FY{y} was ${v}B.",
                sections=["Item 8"]),
        _sf_tpl("sf_gm_pct",      "gross_margin_pct",
                "What was {c}'s gross margin percentage in FY{y}?",
                "{c}'s gross margin in FY{y} was {v}%."),
        _sf_tpl("sf_rd",          "rd_spend_b",
                "How much did {c} spend on research and development in FY{y}?",
                "{c} spent ${v}B on research and development in FY{y}."),
        _sf_tpl("sf_employees",   "employees_k",
                "How many full-time employees did {c} have at the end of FY{y}?",
                "{c} had approximately {v}K full-time employees at the end of FY{y}.",
                req_tbl=False, sections=["Item 1"]),
        _sf_tpl("sf_capex",       "capex_b",
                "What was {c}'s capital expenditure in FY{y}?",
                "{c}'s capital expenditure in FY{y} was ${v}B."),
        _sf_tpl("sf_op_income",   "operating_income_b",
                "What was {c}'s operating income in FY{y}?",
                "{c}'s operating income in FY{y} was ${v}B."),
        _sf_tpl("sf_op_margin",   "operating_margin_pct",
                "What was {c}'s operating margin in FY{y}?",
                "{c}'s operating margin in FY{y} was {v}%."),
        _sf_tpl("sf_gross_profit","gross_profit_b",
                "What was {c}'s gross profit in FY{y}?",
                "{c}'s gross profit in FY{y} was ${v}B."),
        # Apple-specific
        _sf_tpl("sf_aapl_iphone",    "iphone_revenue_b",
                "What was Apple's iPhone revenue in FY{y}?",
                "Apple's iPhone revenue in FY{y} was ${v}B.",
                cos=["Apple"]),
        _sf_tpl("sf_aapl_services",  "services_revenue_b",
                "What was Apple's Services segment revenue in FY{y}?",
                "Apple's Services segment revenue in FY{y} was ${v}B.",
                cos=["Apple"]),
        _sf_tpl("sf_aapl_china",     "greater_china_revenue_b",
                "What was Apple's Greater China revenue in FY{y}?",
                "Apple's Greater China revenue in FY{y} was ${v}B.",
                cos=["Apple"]),
        _sf_tpl("sf_aapl_wearables", "wearables_revenue_b",
                "What was Apple's Wearables, Home & Accessories revenue in FY{y}?",
                "Apple's Wearables, Home & Accessories revenue in FY{y} was ${v}B.",
                cos=["Apple"]),
        # Microsoft-specific
        _sf_tpl("sf_msft_cloud",  "cloud_revenue_b",
                "What was Microsoft's Intelligent Cloud segment revenue in FY{y}?",
                "Microsoft's Intelligent Cloud segment revenue in FY{y} was ${v}B.",
                cos=["Microsoft"]),
        _sf_tpl("sf_msft_azure",  "azure_growth_pct",
                "What was Microsoft's Azure revenue growth rate in FY{y}?",
                "Microsoft reported approximately {v}% Azure revenue growth in FY{y}.",
                req_tbl=False, sections=["Item 7"], cos=["Microsoft"]),
        _sf_tpl("sf_msft_prod",   "productivity_revenue_b",
                "What was Microsoft's Productivity and Business Processes segment revenue in FY{y}?",
                "Microsoft's Productivity and Business Processes segment revenue in FY{y} was ${v}B.",
                cos=["Microsoft"]),
        # Google-specific
        _sf_tpl("sf_goog_cloud",   "cloud_revenue_b",
                "What was Google Cloud's revenue in FY{y}?",
                "Google Cloud revenue in FY{y} was ${v}B.",
                cos=["Google"]),
        _sf_tpl("sf_goog_ads",     "advertising_revenue_b",
                "What was Alphabet's total advertising revenue in FY{y}?",
                "Alphabet's total advertising revenue in FY{y} was ${v}B.",
                cos=["Google"]),
        _sf_tpl("sf_goog_youtube", "youtube_revenue_b",
                "What was YouTube's advertising revenue in FY{y}?",
                "YouTube's advertising revenue in FY{y} was ${v}B.",
                cos=["Google"]),
        # Amazon-specific
        _sf_tpl("sf_amzn_aws",  "aws_revenue_b",
                "What was Amazon Web Services (AWS) revenue in FY{y}?",
                "AWS revenue in FY{y} was ${v}B.",
                cos=["Amazon"]),
        _sf_tpl("sf_amzn_na",   "north_america_revenue_b",
                "What was Amazon's North America segment revenue in FY{y}?",
                "Amazon's North America segment revenue in FY{y} was ${v}B.",
                cos=["Amazon"]),
        _sf_tpl("sf_amzn_ads",  "advertising_revenue_b",
                "What was Amazon's advertising services revenue in FY{y}?",
                "Amazon's advertising services revenue in FY{y} was ${v}B.",
                cos=["Amazon"]),
        # Meta-specific
        _sf_tpl("sf_meta_ads", "advertising_revenue_b",
                "What was Meta's advertising revenue in FY{y}?",
                "Meta's advertising revenue in FY{y} was ${v}B.",
                cos=["Meta"]),
        _sf_tpl("sf_meta_dap", "family_dap_millions",
                "How many daily active people did Meta's Family of Apps have in FY{y}?",
                "Meta's Family of Apps had {v}M daily active people (DAP) in FY{y}.",
                req_tbl=False, sections=["Item 7", "Item 1"], cos=["Meta"]),
    ]
    return _collect(tpls, QUESTION_COUNTS["simple_factual"])


# ===========================================================================
# NUMERICAL REASONING — 50 questions
# requires computation (growth rates, ratios, margins), difficulty = medium
# ===========================================================================

def _build_numerical_reasoning() -> list[dict]:
    out: list[dict] = []

    # NR-A: YoY total revenue growth
    for c in _C:
        for y in _GY:
            g = yoy_growth(c, "revenue_b", y)
            if g is None:
                continue
            prev = get(c, y - 1).get("revenue_b")
            curr = get(c, y).get("revenue_b")
            if prev is None or curr is None:
                continue
            word  = "grew" if g >= 0 else "declined"
            covid = (y == 2021)
            diff  = _bump("medium") if covid else "medium"
            out.append({
                "type": "numerical_reasoning",
                "question": (
                    f"What was {c}'s year-over-year revenue growth rate in FY{y}?"
                ),
                "ground_truth": (
                    f"{c}'s revenue {word} {abs(g):.1f}% year-over-year in FY{y}, "
                    f"from ${prev}B in FY{y - 1} to ${curr}B."
                ),
                "companies": [c], "years": [y],
                "requires_table": True, "requires_multi_hop": False,
                "requires_graph": False, "covid_related": covid,
                "difficulty": diff, "sections_needed": ["Item 8", "Item 7"],
            })

    # NR-B: YoY gross margin change (pp)
    for c in _C:
        for y in _GY:
            curr = get(c, y).get("gross_margin_pct")
            prev = get(c, y - 1).get("gross_margin_pct")
            if curr is None or prev is None:
                continue
            delta = round(curr - prev, 1)
            word  = "expanded" if delta >= 0 else "contracted"
            out.append({
                "type": "numerical_reasoning",
                "question": (
                    f"How did {c}'s gross margin change from FY{y - 1} to FY{y}?"
                ),
                "ground_truth": (
                    f"{c}'s gross margin {word} by {abs(delta):.1f} percentage points "
                    f"from {prev}% in FY{y - 1} to {curr}% in FY{y}."
                ),
                "companies": [c], "years": [y],
                "requires_table": True, "requires_multi_hop": False,
                "requires_graph": False, "covid_related": False,
                "difficulty": "medium", "sections_needed": ["Item 8", "Item 7"],
            })

    # NR-C: Net income margin (net_income / revenue)
    for c in _C:
        for y in _Y:
            ni  = get(c, y).get("net_income_b")
            rev = get(c, y).get("revenue_b")
            nim = _pct(ni, rev)
            if nim is None:
                continue
            out.append({
                "type": "numerical_reasoning",
                "question": (
                    f"What was {c}'s net income margin in FY{y}?"
                ),
                "ground_truth": (
                    f"{c}'s net income margin in FY{y} was {nim}% "
                    f"(${ni}B net income on ${rev}B revenue)."
                ),
                "companies": [c], "years": [y],
                "requires_table": True, "requires_multi_hop": False,
                "requires_graph": False, "covid_related": False,
                "difficulty": "medium", "sections_needed": ["Item 8"],
            })

    # NR-D: R&D as percentage of revenue
    for c in _C:
        for y in _Y:
            rd  = get(c, y).get("rd_spend_b")
            rev = get(c, y).get("revenue_b")
            rp  = _pct(rd, rev)
            if rp is None:
                continue
            out.append({
                "type": "numerical_reasoning",
                "question": (
                    f"What percentage of {c}'s revenue was spent on R&D in FY{y}?"
                ),
                "ground_truth": (
                    f"{c} spent {rp}% of its FY{y} revenue (${rev}B) on R&D "
                    f"(${rd}B)."
                ),
                "companies": [c], "years": [y],
                "requires_table": True, "requires_multi_hop": False,
                "requires_graph": False, "covid_related": False,
                "difficulty": "medium", "sections_needed": ["Item 8", "Item 7"],
            })

    # NR-E: Capex as % of revenue
    for c in _C:
        for y in _Y:
            cx  = get(c, y).get("capex_b")
            rev = get(c, y).get("revenue_b")
            cp  = _pct(cx, rev)
            if cp is None:
                continue
            out.append({
                "type": "numerical_reasoning",
                "question": (
                    f"What was {c}'s capital expenditure as a percentage of "
                    f"revenue in FY{y}?"
                ),
                "ground_truth": (
                    f"{c}'s capex was {cp}% of revenue in FY{y} "
                    f"(${cx}B capex on ${rev}B revenue)."
                ),
                "companies": [c], "years": [y],
                "requires_table": True, "requires_multi_hop": False,
                "requires_graph": False, "covid_related": False,
                "difficulty": "medium", "sections_needed": ["Item 8", "Item 7"],
            })

    # NR-F: YoY operating margin change
    for c in _C:
        for y in _GY:
            curr = get(c, y).get("operating_margin_pct")
            prev = get(c, y - 1).get("operating_margin_pct")
            if curr is None or prev is None:
                continue
            delta = round(curr - prev, 1)
            word  = "improved" if delta >= 0 else "declined"
            out.append({
                "type": "numerical_reasoning",
                "question": (
                    f"How did {c}'s operating margin change from FY{y - 1} to FY{y}?"
                ),
                "ground_truth": (
                    f"{c}'s operating margin {word} by {abs(delta):.1f} pp "
                    f"from {prev}% in FY{y - 1} to {curr}% in FY{y}."
                ),
                "companies": [c], "years": [y],
                "requires_table": True, "requires_multi_hop": False,
                "requires_graph": False, "covid_related": False,
                "difficulty": "medium", "sections_needed": ["Item 8", "Item 7"],
            })

    rng = random.Random(SEED)
    rng.shuffle(out)
    return out[:QUESTION_COUNTS["numerical_reasoning"]]


# ===========================================================================
# TEMPORAL — 60 questions
# single company, all 5 years, trend analysis, difficulty = hard
# ===========================================================================

def _t_tpl(tid: str, metric: str,
           q_fn: Callable[[str], str],
           label: str,
           prefix: str = "$", suffix: str = "B",
           cos: list[str] | None = None,
           extra_sections: list[str] | None = None) -> QuestionTemplate:
    _cos = cos or _C
    _sec = (extra_sections or []) + ["Item 8", "Item 7"]

    def qfn(c, years, _qf=q_fn):
        return _qf(c)

    def gtfn(c, years, _m=metric, _l=label, _p=prefix, _s=suffix):
        return _trend(c, _m, _l, prefix=_p, suffix=_s)

    return QuestionTemplate(
        template_id=tid, q_type="temporal",
        question_fn=qfn, ground_truth_fn=gtfn,
        companies_fn=lambda _c=_cos: _c,
        years_fn=lambda: _Y,
        mode="temporal", difficulty="hard",
        requires_table=True, sections_needed=_sec,
    )


def _build_temporal() -> list[dict]:
    tpls: list[QuestionTemplate] = [
        _t_tpl("t_revenue",    "revenue_b",
               lambda c: f"How did {c}'s total revenue evolve from FY2020 to FY2024?",
               "total revenue trend"),
        _t_tpl("t_gm",         "gross_margin_pct",
               lambda c: f"How did {c}'s gross margin change from FY2020 to FY2024?",
               "gross margin trend (%)", prefix="", suffix="%"),
        _t_tpl("t_net_income", "net_income_b",
               lambda c: f"How did {c}'s net income trend from FY2020 to FY2024?",
               "net income trend"),
        _t_tpl("t_rd",         "rd_spend_b",
               lambda c: f"How did {c}'s R&D spending change from FY2020 to FY2024?",
               "R&D spend trend"),
        _t_tpl("t_op_margin",  "operating_margin_pct",
               lambda c: f"How did {c}'s operating margin evolve from FY2020 to FY2024?",
               "operating margin trend (%)", prefix="", suffix="%"),
        _t_tpl("t_capex",      "capex_b",
               lambda c: f"How did {c}'s capital expenditure change from FY2020 to FY2024?",
               "capital expenditure trend"),
        _t_tpl("t_employees",  "employees_k",
               lambda c: f"How did {c}'s employee count change from FY2020 to FY2024?",
               "employee count trend (thousands)", prefix="", suffix="K",
               extra_sections=["Item 1"]),
        _t_tpl("t_op_income",  "operating_income_b",
               lambda c: f"How did {c}'s operating income evolve from FY2020 to FY2024?",
               "operating income trend"),
        _t_tpl("t_gp",         "gross_profit_b",
               lambda c: f"How did {c}'s gross profit change from FY2020 to FY2024?",
               "gross profit trend"),
        # Segment-specific temporal — each scoped to one company
        _t_tpl("t_aapl_services", "services_revenue_b",
               lambda c: f"How did Apple's Services segment revenue grow from FY2020 to FY2024?",
               "Services revenue trend", cos=["Apple"]),
        _t_tpl("t_aapl_iphone",   "iphone_revenue_b",
               lambda c: f"How did Apple's iPhone revenue change from FY2020 to FY2024?",
               "iPhone revenue trend", cos=["Apple"]),
        _t_tpl("t_msft_cloud",    "cloud_revenue_b",
               lambda c: f"How did Microsoft's Intelligent Cloud revenue evolve from FY2020 to FY2024?",
               "Intelligent Cloud revenue trend", cos=["Microsoft"]),
        _t_tpl("t_goog_cloud",    "cloud_revenue_b",
               lambda c: f"How did Google Cloud's revenue grow from FY2020 to FY2024?",
               "Google Cloud revenue trend", cos=["Google"]),
        _t_tpl("t_amzn_aws",      "aws_revenue_b",
               lambda c: f"How did Amazon Web Services (AWS) revenue evolve from FY2020 to FY2024?",
               "AWS revenue trend", cos=["Amazon"]),
        _t_tpl("t_meta_ads",      "advertising_revenue_b",
               lambda c: f"How did Meta's advertising revenue change from FY2020 to FY2024?",
               "advertising revenue trend", cos=["Meta"]),
        _t_tpl("t_goog_youtube",  "youtube_revenue_b",
               lambda c: f"How did YouTube's advertising revenue evolve from FY2020 to FY2024?",
               "YouTube advertising revenue trend", cos=["Google"]),
        # Additional segment and geographic trends to reach 60
        _t_tpl("t_aapl_mac",     "mac_revenue_b",
               lambda c: f"How did Apple's Mac revenue change from FY2020 to FY2024?",
               "Mac revenue trend", cos=["Apple"]),
        _t_tpl("t_aapl_ipad",    "ipad_revenue_b",
               lambda c: f"How did Apple's iPad revenue evolve from FY2020 to FY2024?",
               "iPad revenue trend", cos=["Apple"]),
        _t_tpl("t_aapl_americas","americas_revenue_b",
               lambda c: f"How did Apple's Americas segment revenue trend from FY2020 to FY2024?",
               "Americas revenue trend", cos=["Apple"]),
        _t_tpl("t_msft_personal","more_personal_revenue_b",
               lambda c: f"How did Microsoft's More Personal Computing segment revenue "
                         f"change from FY2020 to FY2024?",
               "More Personal Computing revenue trend", cos=["Microsoft"]),
        _t_tpl("t_goog_ads",     "advertising_revenue_b",
               lambda c: f"How did Alphabet's total advertising revenue (Search + YouTube + Network) "
                         f"evolve from FY2020 to FY2024?",
               "total advertising revenue trend", cos=["Google"]),
        _t_tpl("t_amzn_na",      "north_america_revenue_b",
               lambda c: f"How did Amazon's North America segment revenue grow from FY2020 to FY2024?",
               "North America revenue trend", cos=["Amazon"]),
        _t_tpl("t_amzn_intl",    "international_revenue_b",
               lambda c: f"How did Amazon's International segment revenue change from FY2020 to FY2024?",
               "International revenue trend", cos=["Amazon"]),
        _t_tpl("t_meta_other",   "other_revenue_b",
               lambda c: f"How did Meta's non-advertising (Reality Labs hardware) revenue "
                         f"evolve from FY2020 to FY2024?",
               "other revenue (Reality Labs) trend", cos=["Meta"]),
    ]
    return _collect(tpls, QUESTION_COUNTS["temporal"])


# ===========================================================================
# COMPARATIVE — 60 questions
# multiple companies, same period, ranked comparison, difficulty = medium/hard
# ===========================================================================

def _cmp_tpl(tid: str, metric: str,
             q_fn: Callable[[list[str], int], str],
             label: str,
             prefix: str = "$", suffix: str = "B",
             cos: list[str] | None = None,
             yrs: list[int] | None = None,
             diff: str = "medium",
             req_graph: bool = False) -> QuestionTemplate:
    _cos = cos or _C
    _yrs = yrs or _Y

    def qfn(companies, y, _qf=q_fn):
        return _qf(companies, y)

    def gtfn(companies, y, _m=metric, _l=label, _p=prefix, _s=suffix):
        return _rank(companies, _m, y, _l, prefix=_p, suffix=_s)

    return QuestionTemplate(
        template_id=tid, q_type="comparative",
        question_fn=qfn, ground_truth_fn=gtfn,
        companies_fn=lambda _c=_cos: _c,
        years_fn=lambda _y=_yrs: _y,
        mode="comparative", difficulty=diff,
        requires_table=True, requires_graph=req_graph,
        sections_needed=["Item 8", "Item 7"],
    )


def _build_comparative() -> list[dict]:
    tpls: list[QuestionTemplate] = [
        _cmp_tpl("cmp_revenue", "revenue_b",
                 lambda cos, y: f"Rank {', '.join(cos)} by total revenue in FY{y}.",
                 "total revenue", diff="medium"),
        _cmp_tpl("cmp_gm", "gross_margin_pct",
                 lambda cos, y: f"Compare gross margins across {', '.join(cos)} in FY{y}. Which had the highest?",
                 "gross margin (%)", prefix="", suffix="%", diff="medium"),
        _cmp_tpl("cmp_net_income", "net_income_b",
                 lambda cos, y: f"Which company had the highest net income among {', '.join(cos)} in FY{y}?",
                 "net income", diff="medium"),
        _cmp_tpl("cmp_rd", "rd_spend_b",
                 lambda cos, y: f"Compare R&D spending across {', '.join(cos)} in FY{y}.",
                 "R&D spend", diff="medium"),
        _cmp_tpl("cmp_op_margin", "operating_margin_pct",
                 lambda cos, y: f"Which company had the best operating margin among {', '.join(cos)} in FY{y}?",
                 "operating margin (%)", prefix="", suffix="%", diff="medium"),
        _cmp_tpl("cmp_capex", "capex_b",
                 lambda cos, y: f"Compare capital expenditure across {', '.join(cos)} in FY{y}.",
                 "capital expenditure", diff="medium"),
        _cmp_tpl("cmp_employees", "employees_k",
                 lambda cos, y: f"Which company had the largest workforce among {', '.join(cos)} in FY{y}?",
                 "employee count (thousands)", prefix="", suffix="K", diff="medium"),
        _cmp_tpl("cmp_gp", "gross_profit_b",
                 lambda cos, y: f"Rank {', '.join(cos)} by gross profit in FY{y}.",
                 "gross profit", diff="medium"),
        _cmp_tpl("cmp_op_income", "operating_income_b",
                 lambda cos, y: f"Which company generated the most operating income among {', '.join(cos)} in FY{y}?",
                 "operating income", diff="medium"),
        # Advertising revenue — Google, Amazon, Meta
        _cmp_tpl("cmp_ads", "advertising_revenue_b",
                 lambda cos, y: f"Compare advertising revenue across {', '.join(cos)} in FY{y}.",
                 "advertising revenue",
                 cos=["Google", "Amazon", "Meta"],
                 yrs=[2022, 2023, 2024],  # Amazon breaks out ads from 2022
                 diff="medium"),
        # Net income margin comparison — computed inline via a custom comparative
    ]

    # Cloud revenue comparison — Microsoft (Intelligent Cloud), Google (Cloud), Amazon (AWS)
    # Each company uses a different metric key, so we build this inline.
    for y in _Y:
        cloud_pairs: list[tuple[str, float]] = []
        for c, metric in [("Microsoft", "cloud_revenue_b"),
                          ("Google",    "cloud_revenue_b"),
                          ("Amazon",    "aws_revenue_b")]:
            v = get(c, y).get(metric)
            if v is None:
                break
            cloud_pairs.append((c, v))
        else:
            cloud_pairs.sort(key=lambda x: x[1], reverse=True)
            body = ", ".join(
                f"{c} ${v}B ({'Intelligent Cloud' if c == 'Microsoft' else 'Google Cloud' if c == 'Google' else 'AWS'})"
                for c, v in cloud_pairs
            )
            tpls.append({  # type: ignore[arg-type]
                "type": "comparative",
                "question": (
                    f"Compare cloud and infrastructure revenue across Microsoft "
                    f"(Intelligent Cloud), Google (Google Cloud), and Amazon (AWS) in FY{y}."
                ),
                "ground_truth": (
                    f"In FY{y}, ranked by cloud/infrastructure revenue: {body}. "
                    f"{cloud_pairs[0][0]} was the largest cloud provider by revenue."
                ),
                "companies": ["Microsoft", "Google", "Amazon"], "years": [y],
                "requires_table": True, "requires_multi_hop": False,
                "requires_graph": False, "covid_related": False,
                "difficulty": "medium", "sections_needed": ["Item 8", "Item 7"],
            })

    # YoY revenue growth ranking across all 5 companies (computed, 4 questions for 2021-2024)
    for y in _GY:
        growth_pairs: list[tuple[str, float]] = []
        for c in _C:
            g = yoy_growth(c, "revenue_b", y)
            if g is None:
                break
            growth_pairs.append((c, g))
        else:
            growth_pairs.sort(key=lambda x: x[1], reverse=True)
            body = ", ".join(f"{c} {'+' if v >= 0 else ''}{v}%" for c, v in growth_pairs)
            tpls.append({  # type: ignore[arg-type]
                "type": "comparative",
                "question": (
                    f"Which company had the highest year-over-year revenue growth "
                    f"rate among the big five tech companies in FY{y}?"
                ),
                "ground_truth": (
                    f"In FY{y}, ranked by YoY revenue growth: {body}. "
                    f"{growth_pairs[0][0]} achieved the highest growth rate."
                ),
                "companies": list(_C), "years": [y],
                "requires_table": True, "requires_multi_hop": False,
                "requires_graph": False, "covid_related": y == 2021,
                "difficulty": "hard" if y == 2021 else "medium",
                "sections_needed": ["Item 8", "Item 7"],
            })

    # NR-comparative: R&D intensity across all 5 companies (computed, not direct lookup)
    def _rd_pct_rank(companies, year):
        pairs = []
        for c in companies:
            rd  = get(c, year).get("rd_spend_b")
            rev = get(c, year).get("revenue_b")
            rp  = _pct(rd, rev)
            if rp is None:
                return None
            pairs.append((c, rp))
        pairs.sort(key=lambda x: x[1], reverse=True)
        body = ", ".join(f"{c} {v}%" for c, v in pairs)
        return (
            f"In FY{year}, R&D as % of revenue: {body}. "
            f"{pairs[0][0]} invested the highest proportion."
        )

    class _RDIntensityTpl:
        """Ad-hoc comparative template for R&D intensity (computed ratio)."""
        q_type         = "comparative"
        template_id    = "cmp_rd_intensity"
        requires_table = True
        requires_multi_hop = False
        requires_graph = False
        covid_related  = False
        sections_needed = ["Item 8", "Item 7"]

    for y in _Y:
        q  = f"Which company had the highest R&D-to-revenue ratio among the big five tech companies in FY{y}?"
        gt = _rd_pct_rank(_C, y)
        if gt is None:
            continue
        _t = _RDIntensityTpl()
        out_item: dict = {
            "type": "comparative", "question": q, "ground_truth": gt,
            "companies": list(_C), "years": [y],
            "requires_table": True, "requires_multi_hop": False,
            "requires_graph": False, "covid_related": False,
            "difficulty": "hard", "sections_needed": ["Item 8", "Item 7"],
        }
        tpls.append(out_item)  # type: ignore[arg-type]

    # Net income margin ranking
    def _nim_rank(companies, year):
        pairs = []
        for c in companies:
            ni  = get(c, year).get("net_income_b")
            rev = get(c, year).get("revenue_b")
            nim = _pct(ni, rev)
            if nim is None:
                return None
            pairs.append((c, nim))
        pairs.sort(key=lambda x: x[1], reverse=True)
        body = ", ".join(f"{c} {v}%" for c, v in pairs)
        return (
            f"In FY{year}, net income margin: {body}. "
            f"{pairs[0][0]} had the highest net income margin."
        )

    for y in _Y:
        q  = f"Which company had the highest net income margin among the big five tech companies in FY{y}?"
        gt = _nim_rank(_C, y)
        if gt is None:
            continue
        tpls.append({  # type: ignore[arg-type]
            "type": "comparative", "question": q, "ground_truth": gt,
            "companies": list(_C), "years": [y],
            "requires_table": True, "requires_multi_hop": False,
            "requires_graph": False, "covid_related": False,
            "difficulty": "hard", "sections_needed": ["Item 8"],
        })

    # Expand proper QuestionTemplate objects and collect raw dicts
    raw: list[dict] = []
    for item in tpls:
        if isinstance(item, QuestionTemplate):
            raw.extend(_expand(item))
        else:
            raw.append(item)  # already a dict

    rng = random.Random(SEED)
    rng.shuffle(raw)
    return raw[:QUESTION_COUNTS["comparative"]]


# ===========================================================================
# MULTI-HOP — 55 questions
# two conditions joined across sections or documents, difficulty = medium/hard
# ===========================================================================

def _build_multi_hop() -> list[dict]:
    out: list[dict] = []

    def _mh(question, ground_truth, companies, years, difficulty,
            covid=False, req_graph=False, sections=None):
        diff = _bump(difficulty) if covid else difficulty
        out.append({
            "type": "multi_hop", "question": question,
            "ground_truth": ground_truth,
            "companies": companies if isinstance(companies, list) else [companies],
            "years": years if isinstance(years, list) else [years],
            "requires_table": True, "requires_multi_hop": True,
            "requires_graph": req_graph, "covid_related": covid,
            "difficulty": diff, "sections_needed": sections or ["Item 8", "Item 7", "Item 1A"],
        })

    # --- MH-A: Peak gross margin year → net income (5 questions) ---
    for c in _C:
        fy_data = [(y, get(c, y).get("gross_margin_pct")) for y in _Y]
        fy_data = [(y, v) for y, v in fy_data if v is not None]
        if not fy_data:
            continue
        peak_y, peak_gm = max(fy_data, key=lambda x: x[1])
        ni = get(c, peak_y).get("net_income_b")
        if ni is None:
            continue
        _mh(
            question=(
                f"In the fiscal year {c} achieved its highest gross margin "
                f"between FY2020 and FY2024, what was its net income?"
            ),
            ground_truth=(
                f"{c}'s peak gross margin between FY2020 and FY2024 was {peak_gm}% "
                f"in FY{peak_y}. Its net income in that year was ${ni}B."
            ),
            companies=[c], years=[peak_y], difficulty="hard",
        )

    # --- MH-B: Headcount decline year → operating margin (5 questions) ---
    _headcount_declines = [
        ("Apple",   2023),
        ("Google",  2023),
        ("Amazon",  2022),
        ("Amazon",  2023),
        ("Meta",    2023),
    ]
    for c, y in _headcount_declines:
        emp_curr = get(c, y).get("employees_k")
        emp_prev = get(c, y - 1).get("employees_k")
        op_curr  = get(c, y).get("operating_margin_pct")
        op_prev  = get(c, y - 1).get("operating_margin_pct")
        if any(v is None for v in [emp_curr, emp_prev, op_curr, op_prev]):
            continue
        delta_op = round(op_curr - op_prev, 1)
        word     = "improved" if delta_op >= 0 else "declined"
        _mh(
            question=(
                f"In the fiscal year {c}'s employee count fell year-over-year, "
                f"what was its operating margin and how did it compare to the prior year?"
            ),
            ground_truth=(
                f"In FY{y}, {c}'s employee count fell from {emp_prev}K to {emp_curr}K. "
                f"Its operating margin was {op_curr}%, which {word} by "
                f"{abs(delta_op):.1f} pp versus {op_prev}% in FY{y - 1}."
            ),
            companies=[c], years=[y], difficulty="hard",
        )

    # --- MH-C: Revenue growth > 25% → operating margin that year (3 questions) ---
    for c in _C:
        for y in _GY:
            g = yoy_growth(c, "revenue_b", y)
            if g is None or g <= 25:
                continue
            rev_curr = get(c, y).get("revenue_b")
            rev_prev = get(c, y - 1).get("revenue_b")
            op_m     = get(c, y).get("operating_margin_pct")
            if any(v is None for v in [rev_curr, rev_prev, op_m]):
                continue
            _mh(
                question=(
                    f"In the fiscal year {c}'s total revenue grew by more than 25% "
                    f"year-over-year, what was its operating margin?"
                ),
                ground_truth=(
                    f"{c}'s revenue grew {g:.1f}% in FY{y} from ${rev_prev}B to "
                    f"${rev_curr}B. Its operating margin that year was {op_m}%."
                ),
                companies=[c], years=[y], difficulty="hard",
                covid=(y == 2021),
            )

    # --- MH-D: Amazon net loss year → AWS revenue and operating margin (1 question) ---
    amzn_ni_2022 = get("Amazon", 2022).get("net_income_b")
    amzn_aws_2022 = get("Amazon", 2022).get("aws_revenue_b")
    amzn_op_2022  = get("Amazon", 2022).get("operating_margin_pct")
    if all(v is not None for v in [amzn_ni_2022, amzn_aws_2022, amzn_op_2022]):
        _mh(
            question=(
                "In the fiscal year Amazon reported a net loss, what were its "
                "AWS revenue and overall operating margin?"
            ),
            ground_truth=(
                f"Amazon reported a net loss of ${abs(amzn_ni_2022)}B in FY2022 "
                f"(primarily due to Rivian equity write-downs). "
                f"AWS revenue was ${amzn_aws_2022}B and operating margin was "
                f"{amzn_op_2022}% that year."
            ),
            companies=["Amazon"], years=[2022], difficulty="hard",
        )

    # --- MH-E: R&D compound question — R&D% + operating margin delta (20 questions) ---
    for c in _C:
        for y in _GY:
            rd   = get(c, y).get("rd_spend_b")
            rev  = get(c, y).get("revenue_b")
            op_c = get(c, y).get("operating_margin_pct")
            op_p = get(c, y - 1).get("operating_margin_pct")
            rp   = _pct(rd, rev)
            if any(v is None for v in [rd, rev, op_c, op_p, rp]):
                continue
            delta = round(op_c - op_p, 1)
            word  = "improved" if delta >= 0 else "declined"
            _mh(
                question=(
                    f"In FY{y}, {c} invested ${rd}B in R&D. What percentage of "
                    f"revenue was this, and how did the operating margin compare "
                    f"to FY{y - 1}?"
                ),
                ground_truth=(
                    f"In FY{y}, {c}'s R&D spend of ${rd}B represented {rp}% of "
                    f"${rev}B revenue. Its operating margin was {op_c}%, "
                    f"which {word} {abs(delta):.1f} pp from {op_p}% in FY{y - 1}."
                ),
                companies=[c], years=[y], difficulty="medium",
            )

    # --- MH-F: COVID recovery — revenue AND employee change (5 questions, covid_related) ---
    for c in _C:
        rev20 = get(c, 2020).get("revenue_b")
        rev21 = get(c, 2021).get("revenue_b")
        emp20 = get(c, 2020).get("employees_k")
        emp21 = get(c, 2021).get("employees_k")
        if any(v is None for v in [rev20, rev21, emp20, emp21]):
            continue
        rev_d = round((rev21 - rev20) / abs(rev20) * 100, 1)
        emp_d = round(emp21 - emp20, 1)
        emp_w = "increased" if emp_d >= 0 else "decreased"
        _mh(
            question=(
                f"From FY2020 to FY2021, how did {c}'s total revenue change "
                f"and what happened to its employee count over the same period?"
            ),
            ground_truth=(
                f"From FY2020 to FY2021, {c}'s revenue grew {rev_d:.1f}% from "
                f"${rev20}B to ${rev21}B. Employee count {emp_w} from {emp20}K "
                f"to {emp21}K (a change of {abs(emp_d):.0f}K employees)."
            ),
            companies=[c], years=[2020, 2021], difficulty="medium",
            covid=True, sections=["Item 8", "Item 7", "Item 1"],
        )

    # --- MH-G: Peak operating income year → R&D intensity (5 questions) ---
    for c in _C:
        fy_data = [(y, get(c, y).get("operating_income_b")) for y in _Y]
        fy_data = [(y, v) for y, v in fy_data if v is not None]
        if not fy_data:
            continue
        peak_y, peak_oi = max(fy_data, key=lambda x: x[1])
        rd  = get(c, peak_y).get("rd_spend_b")
        rev = get(c, peak_y).get("revenue_b")
        rp  = _pct(rd, rev)
        if any(v is None for v in [rd, rev, rp]):
            continue
        _mh(
            question=(
                f"In the fiscal year {c} reported its highest operating income "
                f"between FY2020 and FY2024, what was its R&D spending as a "
                f"percentage of revenue?"
            ),
            ground_truth=(
                f"{c}'s peak operating income between FY2020 and FY2024 was "
                f"${peak_oi}B in FY{peak_y}. R&D spending that year was ${rd}B, "
                f"representing {rp}% of ${rev}B in revenue."
            ),
            companies=[c], years=[peak_y], difficulty="hard",
        )

    # --- MH-H: Two-segment ratio (Amazon AWS vs advertising, Microsoft cloud vs productivity) ---
    seg_pairs = [
        ("Amazon",    "aws_revenue_b",          "advertising_revenue_b",
         "AWS",       "advertising services",   [2022, 2023, 2024]),
        ("Microsoft", "cloud_revenue_b",         "productivity_revenue_b",
         "Intelligent Cloud", "Productivity & Business Processes", _Y),
        ("Google",    "cloud_revenue_b",         "advertising_revenue_b",
         "Google Cloud", "advertising",          _Y),
    ]
    for (c, m1, m2, label1, label2, yrs) in seg_pairs:
        for y in yrs:
            v1 = get(c, y).get(m1)
            v2 = get(c, y).get(m2)
            if v1 is None or v2 is None or v2 == 0:
                continue
            ratio = round(v2 / v1, 2)
            _mh(
                question=(
                    f"In FY{y}, what was the ratio of {c}'s {label2} revenue "
                    f"to its {label1} revenue, and what did this reveal about "
                    f"the relative size of each segment?"
                ),
                ground_truth=(
                    f"In FY{y}, {c}'s {label1} revenue was ${v1}B and {label2} "
                    f"revenue was ${v2}B. The {label2}-to-{label1} ratio was "
                    f"{ratio:.2f}x, indicating {label2} was "
                    f"{'larger' if ratio > 1 else 'smaller'} than {label1}."
                ),
                companies=[c], years=[y], difficulty="medium",
            )

    rng = random.Random(SEED)
    rng.shuffle(out)
    return out[:QUESTION_COUNTS["multi_hop"]]


# ===========================================================================
# RISK QUALITATIVE — 50 questions
# qualitative reasoning over risk factors and MD&A
# ground_truth = None (placeholder — filled after document extraction)
# ===========================================================================

def _build_risk_qualitative() -> list[dict]:
    """
    Convert QUALITATIVE_GROUND_TRUTHS (approved, hand-curated) into the
    standard question schema.  No shuffle or trim — source is exactly 50.

    keywords is forwarded into questions.json so the retrieval evaluator
    can use it as a lightweight chunk-relevance check without a full LLM judge.
    """
    assert len(QUALITATIVE_GROUND_TRUTHS) == QUESTION_COUNTS["risk_qualitative"], (
        f"qualitative_ground_truths.py has {len(QUALITATIVE_GROUND_TRUTHS)} entries, "
        f"expected {QUESTION_COUNTS['risk_qualitative']}. "
        f"Update QUESTION_COUNTS or the source file."
    )

    out: list[dict] = []
    for entry in QUALITATIVE_GROUND_TRUTHS:
        difficulty = _bump("medium") if entry["covid_related"] else "medium"
        out.append({
            "type":               "risk_qualitative",
            "question":           entry["question"],
            "ground_truth":       entry["ground_truth"],   # None — filled post-extraction
            "companies":          entry["companies"],
            "years":              entry["years"],
            "requires_table":     False,
            "requires_multi_hop": False,
            "requires_graph":     False,
            "covid_related":      entry["covid_related"],
            "difficulty":         difficulty,
            "sections_needed":    [entry["section"]],
            "keywords":           entry["keywords"],
        })

    assert len(out) == QUESTION_COUNTS["risk_qualitative"]
    return out


# ===========================================================================
# Main generator
# ===========================================================================

def generate() -> None:
    rng = random.Random(SEED)

    type_builders = [
        ("simple_factual",      _build_simple_factual),
        ("numerical_reasoning", _build_numerical_reasoning),
        ("temporal",            _build_temporal),
        ("comparative",         _build_comparative),
        ("multi_hop",           _build_multi_hop),
        ("risk_qualitative",    _build_risk_qualitative),
    ]

    questions: list[dict] = []

    for q_type, builder in type_builders:
        bucket = builder()
        quota  = QUESTION_COUNTS[q_type]
        assert len(bucket) == quota, (
            f"{q_type}: got {len(bucket)} questions, expected {quota}. "
            f"Add more templates or check for skipped None facts."
        )
        # Assign IDs within type
        for i, q in enumerate(bucket, start=1):
            q["id"] = f"{q_type}_{i:03d}"
        questions.extend(bucket)

        # Progress report every 50 questions
        total_so_far = len(questions)
        for checkpoint in range(50, total_so_far + 1, 50):
            if (total_so_far - quota) < checkpoint <= total_so_far:
                print(f"  [{checkpoint:>3}] questions generated "
                      f"(just finished: {q_type})")

    # --- End-of-generation validation ---
    assert len(questions) == TOTAL_TARGET, (
        f"Total question count: expected {TOTAL_TARGET}, got {len(questions)}"
    )
    assert all(
        q["ground_truth"] is not None
        for q in questions
        if q["type"] != "risk_qualitative"
    ), "Found non-risk-qualitative question with ground_truth=None"

    # --- Breakdown ---
    from collections import Counter
    type_counts = Counter(q["type"] for q in questions)
    co_counts   = Counter(c for q in questions for c in q["companies"])
    yr_counts   = Counter(y for q in questions for y in q["years"])
    diff_counts = Counter(q["difficulty"] for q in questions)
    covid_n     = sum(1 for q in questions if q["covid_related"])
    graph_n     = sum(1 for q in questions if q["requires_graph"])
    table_n     = sum(1 for q in questions if q["requires_table"])

    print("\n=== Question Set Summary ===")
    print(f"Total: {len(questions)}\n")
    print("By type:")
    for t, n in sorted(type_counts.items()):
        print(f"  {t:<22} {n:>3}")
    print("\nBy company:")
    for co in _C:
        print(f"  {co:<12} {co_counts.get(co, 0):>4}")
    print("\nBy year (questions that reference this year):")
    for y in _Y:
        print(f"  FY{y}  {yr_counts.get(y, 0):>4}")
    print("\nBy difficulty:")
    for d in ["easy", "medium", "hard"]:
        print(f"  {d:<8} {diff_counts.get(d, 0):>4}")
    print(f"\ncovid_related: {covid_n}")
    print(f"requires_graph: {graph_n}")
    print(f"requires_table: {table_n}")

    # --- Write output ---
    out_path = EVAL_DIR / "questions.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(questions)} questions -> {out_path}")


if __name__ == "__main__":
    print("Meridian — generating question set...")
    generate()
