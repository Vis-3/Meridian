"""
Meridian — Retrieval quality audit (5 tests).

Run from the project root:
    python scripts/retrieval_audit.py

Prints PASS/FAIL for each test, plus top-3 chunk previews.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from retrieval import dense, sparse, hybrid

COLLECTION = "meridian_fixed"
BM25_NAME  = "fixed"

RESET  = "\033[0m"
GREEN  = "\033[32m"
RED    = "\033[31m"
BOLD   = "\033[1m"
DIM    = "\033[2m"


def _preview(chunk: dict, width: int = 100) -> str:
    text = chunk.get("text", "").replace("\n", " ").strip()
    return text[:width] + ("…" if len(text) > width else "")


def _print_chunks(chunks: list[dict], n: int = 3) -> None:
    for i, c in enumerate(chunks[:n], 1):
        company = c.get("company", "?")
        year    = c.get("fiscal_year", "?")
        section = c.get("section", "?")
        score   = c.get("score", 0.0)
        print(f"  {DIM}[{i}] {company} FY{year} {section}  score={score:.4f}{RESET}")
        print(f"      {_preview(c)}")


def _header(n: int, title: str) -> None:
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}Test {n}: {title}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")


def _result(passed: bool, reason: str = "") -> None:
    if passed:
        print(f"  {GREEN}{BOLD}PASS{RESET}")
    else:
        print(f"  {RED}{BOLD}FAIL{RESET}  — {reason}")


# ---------------------------------------------------------------------------
# Test 1 — Simple factual retrieval
# ---------------------------------------------------------------------------

def test_1_simple_factual() -> bool:
    _header(1, "Simple factual — Apple total revenue FY2023")
    # Apple SEC filings use "net sales" not "revenue" — expansion covers both
    q = "Apple total revenue fiscal year 2023"

    results = {
        "dense":  dense.search(q, COLLECTION, top_k=5, companies=["Apple"], fiscal_years=[2023]),
        "sparse": sparse.search(q, BM25_NAME,  top_k=5, companies=["Apple"], fiscal_years=[2023]),
        "hybrid": hybrid.search(q, top_k=5, companies=["Apple"], fiscal_years=[2023]),
    }

    keywords = ["383", "391"]   # $383B total net sales in Apple FY2023 10-K Item 7

    passed_overall = True
    for name, chunks in results.items():
        # Check top-3: the revenue table may not be the single top-ranked chunk
        top3_text = " ".join(c["text"] for c in chunks[:3])
        hit = any(kw in top3_text for kw in keywords)
        label = f"{name} top-3"
        if hit:
            print(f"  {GREEN}PASS{RESET}  {label}")
        else:
            print(f"  {RED}FAIL{RESET}  {label} — keywords {keywords} not in top-3")
            passed_overall = False

    print("\n  Top-3 hybrid chunks:")
    _print_chunks(results["hybrid"])
    return passed_overall


# ---------------------------------------------------------------------------
# Test 2 — Temporal span
# ---------------------------------------------------------------------------

def test_2_temporal_span() -> bool:
    _header(2, "Temporal span — Apple gross margin across multiple years")
    q = "Apple gross margin 2020 2021 2022 2023 2024"

    chunks = hybrid.search(q, top_k=10, companies=["Apple"])

    years_found = {c.get("fiscal_year") for c in chunks if c.get("fiscal_year")}
    span = len(years_found)

    print(f"  Fiscal years found in top-10: {sorted(years_found)}")
    _print_chunks(chunks)

    passed = span >= 3
    _result(passed, f"only {span} year(s) — need ≥3" if not passed else "")
    return passed


# ---------------------------------------------------------------------------
# Test 3 — Comparative (all 5 companies in top-10)
# ---------------------------------------------------------------------------

def test_3_comparative() -> bool:
    _header(3, "Comparative — R&D expense 2023, all 5 companies")
    q = "R&D research development expense 2023"
    all_companies = ["Apple", "Microsoft", "Google", "Amazon", "Meta"]

    # Balanced retrieval: per-company top-3 to guarantee all companies represented
    chunks = hybrid.search_balanced(
        q,
        companies=all_companies,
        fiscal_years=[2023],
        top_k_per_company=3,
    )

    companies_found = {c.get("company") for c in chunks if c.get("company")}
    expected = set(all_companies)
    missing  = expected - companies_found

    print(f"  Companies in results: {sorted(companies_found)}")
    if missing:
        print(f"  Missing: {sorted(missing)}")
    _print_chunks(chunks)

    passed = len(missing) == 0
    _result(passed, f"missing {sorted(missing)}" if not passed else "")
    return passed


# ---------------------------------------------------------------------------
# Test 4 — Qualitative risk (Item 1A recall)
# ---------------------------------------------------------------------------

def test_4_risk_qualitative() -> bool:
    _header(4, "Risk qualitative — supply chain / semiconductor / COVID 2021")
    q = "supply chain semiconductor shortage COVID 2021"

    chunks = hybrid.search(q, top_k=5, fiscal_years=[2021])

    item1a_count = sum(1 for c in chunks if "1A" in c.get("section", ""))
    print(f"  Item 1A chunks in top-5: {item1a_count}/5")
    _print_chunks(chunks)

    passed = item1a_count >= 3
    _result(passed, f"only {item1a_count}/5 from Item 1A — need ≥3" if not passed else "")
    return passed


# ---------------------------------------------------------------------------
# Test 5 — Cross-company isolation (filter correctness)
# ---------------------------------------------------------------------------

def test_5_isolation() -> bool:
    _header(5, "Cross-company isolation — Microsoft Azure, filter=Microsoft")
    q = "Microsoft Azure cloud revenue"

    chunks = dense.search(
        q, COLLECTION, top_k=10,
        companies=["Microsoft"],
    )

    non_ms = [c for c in chunks if c.get("company") != "Microsoft"]
    print(f"  Total chunks: {len(chunks)} | Non-Microsoft: {len(non_ms)}")
    _print_chunks(chunks)

    passed = len(non_ms) == 0
    _result(passed, f"{len(non_ms)} non-Microsoft chunk(s) leaked through" if not passed else "")
    return passed


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"\n{BOLD}Meridian Retrieval Audit{RESET}")
    print(f"Collection: {COLLECTION}  |  BM25: {BM25_NAME}")

    tests = [
        test_1_simple_factual,
        test_2_temporal_span,
        test_3_comparative,
        test_4_risk_qualitative,
        test_5_isolation,
    ]

    results = []
    for fn in tests:
        try:
            ok = fn()
        except Exception as exc:
            print(f"  {RED}ERROR{RESET}  {exc}")
            ok = False
        results.append(ok)

    passed = sum(results)
    total  = len(results)

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}Summary: {passed}/{total} passed{RESET}")
    for i, (ok, fn) in enumerate(zip(results, tests), 1):
        mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        name = fn.__name__.replace("test_", "").replace("_", " ")
        print(f"  Test {i} [{mark}]  {name}")

    if passed < total:
        print(f"\n{RED}ACTION REQUIRED: Fix failing tests before Phase 6.{RESET}")
    else:
        print(f"\n{GREEN}All tests passed — retrieval layer is healthy.{RESET}")


if __name__ == "__main__":
    main()
