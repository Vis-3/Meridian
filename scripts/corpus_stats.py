"""
Meridian — Corpus statistics report.

Reads data/processed/ JSONs + Qdrant metadata (no embedding model loaded).
Outputs to console, docs/corpus_stats.json, docs/corpus_stats.txt.

Run:
    python scripts/corpus_stats.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import PROCESSED_DIR, COMPANIES, YEARS, QDRANT_URL, COLLECTION_NAMES

QUESTIONS_PATH = ROOT / "data" / "evaluation" / "questions.json"
OUT_DIR        = ROOT / "docs"
OUT_DIR.mkdir(exist_ok=True)

# Ordered longest-first so "Item 1A".startswith("Item 1A") matches before "Item 1"
TARGET_SECTIONS = ["Item 1A", "Item 1", "Item 7", "Item 8"]
TARGET_SECTIONS_DISPLAY = ["Item 1", "Item 1A", "Item 7", "Item 8"]  # print order

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _words(text: str) -> int:
    return len(text.split())


def _qdrant_client():
    try:
        from qdrant_client import QdrantClient
        return QdrantClient(url=QDRANT_URL, prefer_grpc=False)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Document stats
# ---------------------------------------------------------------------------

def compute_doc_stats(docs: list[dict]) -> dict:
    by_company    = defaultdict(int)
    by_year       = defaultdict(int)
    by_doctype    = defaultdict(int)
    word_counts   = []
    doc_sizes     = {}

    for doc in docs:
        company = doc.get("company", "Unknown")
        year    = doc.get("fiscal_year", 0)
        dtype   = doc.get("document_type", "Unknown")
        stem    = doc.get("_stem", "unknown")

        # Total words across all sections
        total_words = sum(
            _words(sec.get("text", ""))
            for sec in doc.get("sections", {}).values()
        )

        by_company[company] += 1
        by_year[year]       += 1
        by_doctype[dtype]   += 1
        word_counts.append(total_words)
        doc_sizes[stem]     = total_words

    avg_words = round(sum(word_counts) / len(word_counts)) if word_counts else 0
    largest   = max(doc_sizes, key=doc_sizes.get) if doc_sizes else ""
    smallest  = min(doc_sizes, key=doc_sizes.get) if doc_sizes else ""

    return {
        "total_documents": len(docs),
        "by_company":      dict(sorted(by_company.items())),
        "by_year":         dict(sorted(by_year.items())),
        "by_doctype":      dict(by_doctype),
        "avg_words":       avg_words,
        "largest_doc":     {"name": largest, "words": doc_sizes.get(largest, 0)},
        "smallest_doc":    {"name": smallest, "words": doc_sizes.get(smallest, 0)},
    }


# ---------------------------------------------------------------------------
# Section stats
# ---------------------------------------------------------------------------

def compute_section_stats(docs: list[dict]) -> dict:
    total_sections      = 0
    section_presence    = defaultdict(int)   # section → doc count with it
    section_word_totals = defaultdict(int)
    section_word_counts = defaultdict(int)

    for doc in docs:
        sections = doc.get("sections", {})
        total_sections += len(sections)
        for sec_name, sec_content in sections.items():
            w = _words(sec_content.get("text", ""))
            # Normalise to canonical names
            for target in TARGET_SECTIONS:
                if sec_name.startswith(target):
                    section_presence[target]    += 1
                    section_word_totals[target] += w
                    section_word_counts[target] += 1
                    break

    n_docs = len(docs)
    coverage = {}
    avg_len  = {}
    for sec in TARGET_SECTIONS:
        count = section_presence[sec]
        coverage[sec] = {
            "count":    count,
            "coverage_pct": round(count / n_docs * 100, 1) if n_docs else 0,
        }
        wc = section_word_counts[sec]
        avg_len[sec] = round(section_word_totals[sec] / wc) if wc else 0

    return {
        "total_sections":     total_sections,
        "section_coverage":   coverage,
        "avg_section_length": avg_len,
    }


# ---------------------------------------------------------------------------
# Chunk stats (from Qdrant)
# ---------------------------------------------------------------------------

def compute_chunk_stats() -> dict:
    client = _qdrant_client()
    collection = COLLECTION_NAMES["fixed"]

    if client is None:
        return {"error": "Qdrant not reachable"}

    try:
        total = client.count(collection_name=collection, exact=True).count
    except Exception as e:
        return {"error": str(e)}

    # Scroll all payloads (no vectors needed)
    by_company    = defaultdict(int)
    by_year       = defaultdict(int)
    by_section    = defaultdict(int)
    token_counts  = []

    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=collection,
            limit=500,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for hit in batch:
            p       = hit.payload or {}
            company = p.get("company", "Unknown")
            year    = p.get("fiscal_year", 0)
            section = p.get("section", "Unknown")
            text    = p.get("text", "")

            by_company[company] += 1
            by_year[year]       += 1
            # Normalise section
            matched = False
            for target in TARGET_SECTIONS:
                if section.startswith(target):
                    by_section[target] += 1
                    matched = True
                    break
            if not matched:
                by_section["Other"] += 1

            token_counts.append(len(text.split()))

        if offset is None:
            break

    avg_tokens = round(sum(token_counts) / len(token_counts)) if token_counts else 0

    return {
        "total_chunks":   total,
        "avg_chunk_tokens": avg_tokens,
        "by_company":     dict(sorted(by_company.items())),
        "by_year":        dict(sorted(by_year.items())),
        "by_section":     dict(sorted(by_section.items())),
    }


# ---------------------------------------------------------------------------
# Question coverage
# ---------------------------------------------------------------------------

def compute_question_coverage(docs: list[dict]) -> dict:
    # Build set of (company, year) pairs present in corpus
    corpus_pairs = {
        (doc.get("company"), doc.get("fiscal_year"))
        for doc in docs
    }

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))

    full_coverage  = 0
    missing        = []

    for q in questions:
        companies = q.get("companies", [])
        years     = q.get("years", [])
        required  = [(c, y) for c in companies for y in years]
        gaps      = [pair for pair in required if pair not in corpus_pairs]

        if not gaps:
            full_coverage += 1
        else:
            missing.append({
                "id":      q.get("id"),
                "type":    q.get("type"),
                "missing": [f"{c} FY{y}" for c, y in gaps],
            })

    total = len(questions)
    return {
        "total_questions":         total,
        "full_coverage_count":     full_coverage,
        "full_coverage_pct":       round(full_coverage / total * 100, 1),
        "missing_coverage_count":  len(missing),
        "missing_questions":       missing,
    }


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _bar(value: int, max_val: int, width: int = 20) -> str:
    filled = round(value / max_val * width) if max_val else 0
    return "#" * filled + "-" * (width - filled)


def format_text_report(stats: dict) -> str:
    lines = []

    def h(title): lines.append(f"\n{'='*60}\n{title}\n{'='*60}")
    def row(label, val): lines.append(f"  {label:<35} {val}")

    lines.append("MERIDIAN CORPUS STATISTICS REPORT")
    lines.append(f"Generated from: {PROCESSED_DIR}")

    # --- Documents ---
    h("DOCUMENT STATS")
    d = stats["documents"]
    row("Total documents:", d["total_documents"])
    row("Average document size (words):", f"{d['avg_words']:,}")
    row("Largest document:", f"{d['largest_doc']['name']}  ({d['largest_doc']['words']:,} words)")
    row("Smallest document:", f"{d['smallest_doc']['name']}  ({d['smallest_doc']['words']:,} words)")

    lines.append("\n  By company:")
    max_c = max(d["by_company"].values(), default=1)
    for co, cnt in d["by_company"].items():
        lines.append(f"    {co:<12} {cnt:>3}  [{_bar(cnt, max_c)}]")

    lines.append("\n  By year:")
    max_y = max(d["by_year"].values(), default=1)
    for yr, cnt in d["by_year"].items():
        lines.append(f"    {yr}  {cnt:>3}  [{_bar(cnt, max_y)}]")

    lines.append("\n  By document type:")
    for dt, cnt in d["by_doctype"].items():
        lines.append(f"    {dt:<8}  {cnt}")

    # --- Sections ---
    h("SECTION STATS")
    s = stats["sections"]
    row("Total sections extracted:", s["total_sections"])
    lines.append("\n  Coverage per section type:")
    for sec in TARGET_SECTIONS_DISPLAY:
        cov = s["section_coverage"].get(sec, {})
        avg = s["avg_section_length"].get(sec, 0)
        lines.append(
            f"    {sec:<10}  {cov.get('count',0):>3}/{d['total_documents']} docs "
            f"({cov.get('coverage_pct',0):>5.1f}%)  "
            f"avg {avg:>6,} words"
        )

    # --- Chunks ---
    h("CHUNK STATS  (Qdrant: meridian_fixed)")
    c = stats["chunks"]
    if "error" in c:
        row("Error:", c["error"])
    else:
        row("Total chunks:", f"{c['total_chunks']:,}")
        row("Avg chunk size (tokens):", c["avg_chunk_tokens"])

        lines.append("\n  Chunks by company:")
        max_cc = max(c["by_company"].values(), default=1)
        for co, cnt in c["by_company"].items():
            lines.append(f"    {co:<12} {cnt:>5}  [{_bar(cnt, max_cc)}]")

        lines.append("\n  Chunks by year:")
        for yr, cnt in c["by_year"].items():
            lines.append(f"    {yr}  {cnt:>5}")

        lines.append("\n  Chunks by section:")
        for sec, cnt in sorted(c["by_section"].items(), key=lambda x: -x[1]):
            lines.append(f"    {sec:<10}  {cnt:>5}")

    # --- Question coverage ---
    h("QUESTION COVERAGE")
    q = stats["question_coverage"]
    row("Total questions:", q["total_questions"])
    row("Full corpus coverage:", f"{q['full_coverage_count']}/{q['total_questions']}  ({q['full_coverage_pct']}%)")
    row("Questions with gaps:", q["missing_coverage_count"])

    if q["missing_questions"]:
        lines.append("\n  Missing coverage:")
        for m in q["missing_questions"][:20]:
            lines.append(f"    [{m['id']}] missing: {', '.join(m['missing'])}")
        if len(q["missing_questions"]) > 20:
            lines.append(f"    ... and {len(q['missing_questions'])-20} more")
    else:
        lines.append("\n  All questions have full corpus coverage.")

    lines.append(f"\n{'='*60}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Load processed JSONs
    doc_paths = sorted(PROCESSED_DIR.glob("*.json"))
    print(f"Loading {len(doc_paths)} processed documents...")

    docs = []
    for p in doc_paths:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            doc["_stem"] = p.stem
            docs.append(doc)
        except Exception as e:
            print(f"  [WARN] Could not load {p.name}: {e}")

    print("Computing document stats...")
    doc_stats = compute_doc_stats(docs)

    print("Computing section stats...")
    sec_stats = compute_section_stats(docs)

    print("Computing chunk stats from Qdrant...")
    chunk_stats = compute_chunk_stats()

    print("Computing question coverage...")
    qcov_stats = compute_question_coverage(docs)

    stats = {
        "documents":        doc_stats,
        "sections":         sec_stats,
        "chunks":           chunk_stats,
        "question_coverage": qcov_stats,
    }

    # Console output
    report = format_text_report(stats)
    print("\n" + report)

    # Save JSON
    json_path = OUT_DIR / "corpus_stats.json"
    json_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"\nJSON saved to: {json_path}")

    # Save text
    txt_path = OUT_DIR / "corpus_stats.txt"
    txt_path.write_text(report, encoding="utf-8")
    print(f"Text saved to: {txt_path}")


if __name__ == "__main__":
    main()
