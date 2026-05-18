"""
Meridian — PySpark parallel PDF extractor.

Pipeline:
  1. Read manifest.json to get list of all downloaded PDFs.
  2. For benchmarking, run sequential extraction first and record wall time.
  3. Run PySpark extraction (each PDF = one partition) and record wall time.
  4. Log speedup ratio; write benchmark result to logs/extraction_benchmark.json.
  5. Upload processed JSON to S3 processed bucket.

Each output JSON has shape:
  {
    "source_filename": "apple_2024_10k.pdf",
    "company": "Apple",
    "fiscal_year": 2024,
    "document_type": "10-K",
    "sections": { "Item 1": {...}, "Item 1A": {...}, ... },
    "tables": [ { "page": int, "section": str, "markdown": str } ],
    "metadata": { ... }
  }
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    RAW_DIR, PROCESSED_DIR, TARGET_SECTIONS,
    SPARK_APP_NAME, SPARK_MASTER, SPARK_LOG_LEVEL,
    LOG_DIR,
)
from ingestion.metadata import build_file_metadata, parse_filename

log = logging.getLogger(__name__)
LOG_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

SECTION_PATTERNS = {
    "Item 1":  re.compile(r"^\s*item\s+1[^a-z0-9]", re.IGNORECASE),
    "Item 1A": re.compile(r"^\s*item\s+1a[^a-z0-9]", re.IGNORECASE),
    "Item 7":  re.compile(r"^\s*item\s+7[^a-z0-9]", re.IGNORECASE),
    "Item 8":  re.compile(r"^\s*item\s+8[^a-z0-9]", re.IGNORECASE),
}

SECTION_ORDER = ["Item 1", "Item 1A", "Item 7", "Item 8"]


def _detect_section(text: str) -> Optional[str]:
    for section, pattern in SECTION_PATTERNS.items():
        if pattern.match(text):
            return section
    return None


# ---------------------------------------------------------------------------
# Table extraction → markdown
# ---------------------------------------------------------------------------

def _table_to_markdown(table) -> str:
    """Convert a PyMuPDF table (list of rows) to GitHub-flavored markdown."""
    if not table or not table[0]:
        return ""

    rows = []
    for i, row in enumerate(table):
        cells = [str(c).strip() if c else "" for c in row]
        rows.append("| " + " | ".join(cells) + " |")
        if i == 0:
            rows.append("| " + " | ".join(["---"] * len(cells)) + " |")

    return "\n".join(rows)


# ---------------------------------------------------------------------------
# HTML extraction (EDGAR iXBRL/HTM filings)
# ---------------------------------------------------------------------------

def _extract_tables_from_html(soup: BeautifulSoup, section: str) -> list[dict]:
    """Extract markdown tables from all <table> elements in a BeautifulSoup tree."""
    tables = []
    for tbl_idx, tbl in enumerate(soup.find_all("table")):
        rows_out = []
        for row in tbl.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in row.find_all(["td", "th"])]
            if any(cells):
                rows_out.append(cells)
        if not rows_out:
            continue
        md_rows = []
        for i, row in enumerate(rows_out):
            md_rows.append("| " + " | ".join(row) + " |")
            if i == 0:
                md_rows.append("| " + " | ".join(["---"] * len(row)) + " |")
        tables.append({
            "page": tbl_idx + 1,
            "section": section or "unknown",
            "markdown": "\n".join(md_rows),
        })
    return tables


def extract_html_document(htm_path: Path) -> dict:
    """
    Extract text + tables from an EDGAR HTML/iXBRL filing.
    Splits content into TARGET_SECTIONS by scanning for Item headings.
    """
    meta = parse_filename(htm_path.name)
    if meta is None:
        log.warning(f"Cannot parse filename: {htm_path.name}, skipping")
        return {}

    raw_html = htm_path.read_bytes()
    # EDGAR iXBRL files are XML-based HTML; suppress the parser mismatch warning
    import warnings
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    soup = BeautifulSoup(raw_html, "lxml")

    # Remove non-content tags
    for tag in soup(["script", "style", "ix:header", "ix:hidden"]):
        tag.decompose()

    full_text = soup.get_text(separator="\n", strip=True)
    lines = full_text.splitlines()

    sections: dict[str, dict] = {s: {"text": "", "pages": []} for s in SECTION_ORDER}
    tables: list[dict] = []
    current_section: Optional[str] = None
    page_est = 1

    for line in lines:
        detected = _detect_section(line)
        if detected:
            current_section = detected
            page_est += 1
        if current_section and current_section in sections:
            sections[current_section]["text"] += line + "\n"
            if page_est not in sections[current_section]["pages"]:
                sections[current_section]["pages"].append(page_est)

    # Extract tables per section
    # Use the whole soup since HTM is one page — attribute tables to current_section heuristic
    tables = _extract_tables_from_html(soup, current_section or "unknown")

    file_meta = build_file_metadata(meta)

    return {
        "source_filename": htm_path.name,
        "company":         meta["company"],
        "fiscal_year":     meta["fiscal_year"],
        "document_type":   meta["document_type"],
        "quarter":         meta.get("quarter"),
        "sections":        sections,
        "tables":          tables,
        "metadata":        file_meta,
        "page_count":      page_est,
    }


# ---------------------------------------------------------------------------
# Core single-document extractor (PDF)
# ---------------------------------------------------------------------------

def extract_pdf_document(pdf_path: Path) -> dict:
    """
    Extract text + tables from one PDF.
    Returns structured dict ready for JSON serialisation.
    """
    meta = parse_filename(pdf_path.name)
    if meta is None:
        log.warning(f"Cannot parse filename: {pdf_path.name}, skipping")
        return {}

    doc = fitz.open(str(pdf_path))
    sections: dict[str, dict] = {s: {"text": "", "pages": []} for s in SECTION_ORDER}
    tables: list[dict] = []

    current_section: Optional[str] = None

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        for line in text.splitlines():
            if line.strip():
                detected = _detect_section(line)
                if detected:
                    current_section = detected
                break

        if current_section and current_section in sections:
            sections[current_section]["text"] += text + "\n"
            sections[current_section]["pages"].append(page_num + 1)

        try:
            page_tables = page.find_tables()
            for tbl in page_tables.tables:
                md = _table_to_markdown(tbl.extract())
                if md:
                    tables.append({
                        "page": page_num + 1,
                        "section": current_section or "unknown",
                        "markdown": md,
                    })
        except Exception:
            pass

    doc.close()

    file_meta = build_file_metadata(meta)

    return {
        "source_filename": pdf_path.name,
        "company":         meta["company"],
        "fiscal_year":     meta["fiscal_year"],
        "document_type":   meta["document_type"],
        "quarter":         meta.get("quarter"),
        "sections":        sections,
        "tables":          tables,
        "metadata":        file_meta,
        "page_count":      sum(len(s["pages"]) for s in sections.values()),
    }


def extract_document(path: Path) -> dict:
    """Route to PDF or HTML extractor based on file extension."""
    if path.suffix.lower() == ".htm":
        return extract_html_document(path)
    return extract_pdf_document(path)


# ---------------------------------------------------------------------------
# Sequential extraction (baseline for benchmark)
# ---------------------------------------------------------------------------

def extract_sequential(pdf_paths: list[Path]) -> tuple[list[dict], float]:
    """Extract all PDFs sequentially. Returns (results, elapsed_seconds)."""
    t0 = time.perf_counter()
    results = []
    for p in pdf_paths:
        result = extract_document(p)
        if result:
            results.append(result)
    elapsed = time.perf_counter() - t0
    log.info(f"Sequential extraction: {len(results)} docs in {elapsed:.2f}s")
    return results, elapsed


# ---------------------------------------------------------------------------
# PySpark extraction
# ---------------------------------------------------------------------------

def extract_spark(pdf_paths: list[Path]) -> tuple[list[dict], float]:
    """Extract all PDFs in parallel using PySpark. Returns (results, elapsed_seconds)."""
    try:
        from pyspark.sql import SparkSession
    except ImportError:
        log.error("PySpark not installed. Run: pip install pyspark")
        raise

    spark = (
        SparkSession.builder
        .appName(SPARK_APP_NAME)
        .master(SPARK_MASTER)
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel(SPARK_LOG_LEVEL)

    # Broadcast the function — each executor gets a copy
    path_strings = [str(p) for p in pdf_paths]
    n_partitions = min(len(path_strings), spark.sparkContext.defaultParallelism)
    rdd = spark.sparkContext.parallelize(path_strings, n_partitions)

    t0 = time.perf_counter()

    def _worker(path_str: str) -> dict:
        # Import must happen inside worker (each executor is a separate process)
        import sys, fitz
        from pathlib import Path as P
        sys.path.insert(0, str(P(path_str).parent.parent.parent))
        from ingestion.extractor import extract_document
        return extract_document(P(path_str))

    results_raw = rdd.map(_worker).filter(lambda d: bool(d)).collect()
    elapsed = time.perf_counter() - t0

    spark.stop()
    log.info(f"Spark extraction: {len(results_raw)} docs in {elapsed:.2f}s "
             f"({n_partitions} partitions / cores)")
    return results_raw, elapsed


# ---------------------------------------------------------------------------
# Benchmark harness
# ---------------------------------------------------------------------------

def run_with_benchmark(pdf_paths: list[Path], use_spark: bool = True) -> list[dict]:
    """
    Run sequential extraction, then Spark extraction, log the speedup,
    and write a benchmark JSON to logs/.
    Returns the Spark results (or sequential if use_spark=False).
    """
    log.info(f"Starting extraction benchmark on {len(pdf_paths)} PDFs")

    seq_results, seq_time = extract_sequential(pdf_paths)

    if not use_spark:
        return seq_results

    spark_results, spark_time = extract_spark(pdf_paths)

    speedup = seq_time / spark_time if spark_time > 0 else 0.0

    benchmark = {
        "n_documents":        len(pdf_paths),
        "sequential_seconds": round(seq_time, 3),
        "spark_seconds":      round(spark_time, 3),
        "speedup":            round(speedup, 2),
        "timestamp":          time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    bench_path = LOG_DIR / "extraction_benchmark.json"
    with open(bench_path, "w") as f:
        json.dump(benchmark, f, indent=2)

    log.info(
        f"Extraction benchmark — Sequential: {seq_time:.2f}s | "
        f"Spark: {spark_time:.2f}s | Speedup: {speedup:.2f}x"
    )
    return spark_results


# ---------------------------------------------------------------------------
# Save + upload results
# ---------------------------------------------------------------------------

def save_and_upload(results: list[dict], upload_to_s3: bool = True):
    """Save each extraction result locally and optionally upload to S3."""
    for doc in results:
        filename = doc["source_filename"]
        stem = Path(filename).stem
        local_path = PROCESSED_DIR / f"{stem}.json"

        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        if upload_to_s3:
            try:
                from ingestion.s3_client import upload_processed
                upload_processed(
                    doc,
                    company=doc["company"],
                    year=doc["fiscal_year"],
                    doctype=doc["document_type"],
                    source_filename=filename,
                )
            except Exception as e:
                log.warning(f"S3 upload skipped for {filename}: {e}")

    log.info(f"Saved {len(results)} processed documents")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    manifest_path = RAW_DIR / "manifest.json"
    if not manifest_path.exists():
        log.error("manifest.json not found. Run ingestion/downloader.py first.")
        return

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Collect successfully downloaded PDFs
    pdf_paths = []
    for entry in manifest:
        if entry["success"]:
            p = RAW_DIR / entry["filename"]
            if p.exists():
                pdf_paths.append(p)

    if not pdf_paths:
        log.error("No local PDFs found. Check RAW_DIR or run downloader first.")
        return

    results = run_with_benchmark(pdf_paths, use_spark=True)
    save_and_upload(results, upload_to_s3=True)
    log.info("Extraction pipeline complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    main()
