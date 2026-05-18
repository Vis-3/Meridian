"""
Meridian — SEC EDGAR downloader.

Downloads 10-K (annual) and 10-Q (quarterly) filings for all companies/years.
Uses the EDGAR Submissions API to locate filings reliably.
Downloads primary HTM documents (modern SEC filings are HTML/iXBRL, not PDF).
Rate-limits to SEC's 10 req/s maximum.

S3 upload is best-effort: a missing credential logs a warning but never aborts.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    CIK_MAP, COMPANIES, YEARS, FISCAL_YEAR_END_MONTH,
    RAW_DIR, EDGAR_BASE_URL, EDGAR_HEADERS,
    EDGAR_RATE_LIMIT_SLEEP, EDGAR_MAX_RETRIES,
)

log = logging.getLogger(__name__)
RAW_DIR.mkdir(parents=True, exist_ok=True)

# EDGAR Submissions API — returns every filing for a company
_SUBMISSIONS_URL     = "https://data.sec.gov/submissions/CIK{cik}.json"
_SUBMISSIONS_EXT_URL = "https://data.sec.gov/submissions/{filename}"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get_json(url: str, params: dict = None) -> Optional[dict]:
    """GET JSON with retry and rate-limit sleep."""
    for attempt in range(1, EDGAR_MAX_RETRIES + 1):
        try:
            time.sleep(EDGAR_RATE_LIMIT_SLEEP)
            resp = requests.get(url, params=params, headers=EDGAR_HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            log.warning(f"Attempt {attempt}/{EDGAR_MAX_RETRIES} failed for {url}: {e}")
            if attempt < EDGAR_MAX_RETRIES:
                time.sleep(2 ** attempt)
    return None


def _download_file(file_url: str, dest_path: Path) -> bool:
    """Stream-download any file to dest_path. Returns True on success."""
    if dest_path.exists():
        log.info(f"Already cached: {dest_path.name}")
        return True

    for attempt in range(1, EDGAR_MAX_RETRIES + 1):
        try:
            time.sleep(EDGAR_RATE_LIMIT_SLEEP)
            resp = requests.get(file_url, headers=EDGAR_HEADERS, timeout=60, stream=True)
            resp.raise_for_status()
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            log.info(f"Downloaded: {dest_path.name}  ({dest_path.stat().st_size // 1024} KB)")
            return True
        except requests.RequestException as e:
            log.warning(f"Download attempt {attempt} failed for {file_url}: {e}")
            if attempt < EDGAR_MAX_RETRIES:
                time.sleep(2 ** attempt)

    log.error(f"Failed to download: {file_url}")
    return False


# ---------------------------------------------------------------------------
# Submissions API helpers
# ---------------------------------------------------------------------------

def _get_submissions(cik: str) -> Optional[dict]:
    """
    Fetch the full filing history for a company from the EDGAR Submissions API.

    The primary response contains the most recent ~1000 submissions. High-volume
    filers (Meta, Google) have older filings in supplementary pages listed under
    filings.files — we fetch those too and merge them into one flat record.
    """
    url  = _SUBMISSIONS_URL.format(cik=cik)
    data = _get_json(url)
    if not data:
        return None

    recent = data.get("filings", {}).get("recent", {})

    # Collect all keys present in the recent block (form, filingDate, etc.)
    all_filings: dict[str, list] = {k: list(v) for k, v in recent.items()}

    # Supplementary pages (older filings for high-volume companies)
    for page_info in data.get("filings", {}).get("files", []):
        page_name = page_info.get("name", "")
        if not page_name:
            continue
        page_data = _get_json(_SUBMISSIONS_EXT_URL.format(filename=page_name))
        if not page_data:
            continue
        for k, v in page_data.items():
            if k in all_filings and isinstance(v, list):
                all_filings[k].extend(v)

    data["filings"]["recent"] = all_filings
    return data


def _filing_date_window(company: str, fiscal_year: int, form_type: str,
                        quarter: Optional[str] = None) -> tuple[str, str]:
    """
    Return (start_date, end_date) window for when a filing would have been
    submitted to EDGAR, given company, fiscal year, form type, and quarter.
    """
    end_month = FISCAL_YEAR_END_MONTH[company]

    if form_type == "10-K":
        if end_month == 12:
            # Calendar-year: 10-K filed Jan-Apr of fiscal_year + 1
            return (f"{fiscal_year + 1}-01-01", f"{fiscal_year + 1}-04-30")
        elif end_month == 9:
            # Apple: FY ends Sep, filed Oct-Dec of same year
            return (f"{fiscal_year}-09-01", f"{fiscal_year}-12-31")
        elif end_month == 6:
            # Microsoft: FY ends Jun, filed Jul-Oct of same year
            return (f"{fiscal_year}-06-01", f"{fiscal_year}-10-31")

    elif form_type == "10-Q":
        q_num = int(quarter[1]) if quarter else 1
        if end_month == 12:
            # Q1=Jan-Mar filed ~May, Q2=Apr-Jun filed ~Aug, Q3=Jul-Sep filed ~Nov
            windows = {
                1: (f"{fiscal_year}-04-01", f"{fiscal_year}-05-31"),
                2: (f"{fiscal_year}-07-01", f"{fiscal_year}-08-31"),
                3: (f"{fiscal_year}-10-01", f"{fiscal_year}-11-30"),
            }
        elif end_month == 9:
            # Apple: Q1(Dec) filed ~Feb, Q2(Mar) filed ~May, Q3(Jun) filed ~Aug
            windows = {
                1: (f"{fiscal_year}-01-01", f"{fiscal_year}-02-28"),
                2: (f"{fiscal_year}-04-01", f"{fiscal_year}-05-31"),
                3: (f"{fiscal_year}-07-01", f"{fiscal_year}-08-31"),
            }
        elif end_month == 6:
            prev = fiscal_year - 1
            # Microsoft: Q1(Sep) filed ~Nov, Q2(Dec) filed ~Feb, Q3(Mar) filed ~May
            windows = {
                1: (f"{prev}-10-01",      f"{prev}-11-30"),
                2: (f"{fiscal_year}-01-01", f"{fiscal_year}-02-28"),
                3: (f"{fiscal_year}-04-01", f"{fiscal_year}-05-31"),
            }
        else:
            windows = {}
        window = windows.get(q_num)
        if window:
            return window

    return ("2000-01-01", "2030-01-01")  # fallback — should never hit


def _find_filing(
    cik: str,
    company: str,
    form_type: str,
    fiscal_year: int,
    quarter: Optional[str] = None,
) -> Optional[tuple[str, str]]:
    """
    Use the Submissions API to find a specific filing.
    Returns (primary_doc_url, extension) or None.

    The primary document is almost always a .htm file for modern filings.
    """
    data = _get_submissions(cik)
    if not data:
        return None

    filings   = data.get("filings", {}).get("recent", {})
    forms      = filings.get("form", [])
    dates      = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])
    primary    = filings.get("primaryDocument", [""] * len(forms))

    start_dt, end_dt = _filing_date_window(company, fiscal_year, form_type, quarter)
    entity_id = cik.lstrip("0")

    for form, date, acc, pdoc in zip(forms, dates, accessions, primary):
        if form == form_type and start_dt <= date <= end_dt and pdoc:
            acc_clean = acc.replace("-", "")
            ext = Path(pdoc).suffix.lstrip(".")  # "htm", "pdf", etc.
            url = f"{EDGAR_BASE_URL}/Archives/edgar/data/{entity_id}/{acc_clean}/{pdoc}"
            log.info(f"  Found {form_type} filing: filed {date}, accession {acc}, doc={pdoc}")
            return url, ext

    log.warning(f"No {form_type} found for {company} FY{fiscal_year} between {start_dt} and {end_dt}")
    return None


# ---------------------------------------------------------------------------
# Filing year resolution
# ---------------------------------------------------------------------------

def fiscal_filing_year(company: str, fiscal_year: int) -> int:
    """Returns the calendar year in which the 10-K was filed."""
    end_month = FISCAL_YEAR_END_MONTH[company]
    return fiscal_year + 1 if end_month == 12 else fiscal_year


def quarter_date_ranges(company: str, fiscal_year: int):
    """Yields (quarter_label, start_date, end_date) for Q1-Q3 10-Q filings."""
    end_month = FISCAL_YEAR_END_MONTH[company]
    if end_month == 12:
        return [
            ("Q1", f"{fiscal_year}-01-01", f"{fiscal_year}-04-15"),
            ("Q2", f"{fiscal_year}-04-01", f"{fiscal_year}-07-15"),
            ("Q3", f"{fiscal_year}-07-01", f"{fiscal_year}-10-15"),
        ]
    elif end_month == 9:
        prev = fiscal_year - 1
        return [
            ("Q1", f"{prev}-10-01",        f"{prev}-12-31"),
            ("Q2", f"{fiscal_year}-01-01", f"{fiscal_year}-04-15"),
            ("Q3", f"{fiscal_year}-04-01", f"{fiscal_year}-07-15"),
        ]
    elif end_month == 6:
        prev = fiscal_year - 1
        return [
            ("Q1", f"{prev}-07-01",        f"{prev}-10-15"),
            ("Q2", f"{prev}-10-01",        f"{prev}-12-31"),
            ("Q3", f"{fiscal_year}-01-01", f"{fiscal_year}-04-15"),
        ]
    return []


# ---------------------------------------------------------------------------
# S3 upload — best-effort, never raises
# ---------------------------------------------------------------------------

def _upload_to_s3(local_path: Path, company: str, year: int, doctype: str):
    try:
        from ingestion.s3_client import upload_pdf as s3_upload_pdf
        s3_upload_pdf(local_path, company, year, doctype)
    except Exception as e:
        log.warning(f"S3 upload skipped for {local_path.name}: {e}")


# ---------------------------------------------------------------------------
# Public download functions
# ---------------------------------------------------------------------------

def download_10k(company: str, fiscal_year: int) -> bool:
    """Download the 10-K for a company/fiscal_year. Returns True on success."""
    cik = CIK_MAP[company]
    log.info(f"Fetching 10-K: {company} FY{fiscal_year}")

    result = _find_filing(cik, company, "10-K", fiscal_year)
    if not result:
        return False

    url, ext = result
    dest = RAW_DIR / f"{company.lower()}_{fiscal_year}_10k.{ext}"

    ok = _download_file(url, dest)
    if ok:
        _upload_to_s3(dest, company, fiscal_year, "10-K")
    return ok


def download_10q(company: str, fiscal_year: int, quarter: str,
                 _start_dt: str, _end_dt: str) -> bool:
    """Download one 10-Q. Returns True on success."""
    cik = CIK_MAP[company]
    log.info(f"Fetching 10-Q: {company} FY{fiscal_year} {quarter}")

    result = _find_filing(cik, company, "10-Q", fiscal_year, quarter)
    if not result:
        return False

    url, ext = result
    dest = RAW_DIR / f"{company.lower()}_{fiscal_year}_{quarter.lower()}_10q.{ext}"

    ok = _download_file(url, dest)
    if ok:
        _upload_to_s3(dest, company, fiscal_year, "10-Q")
    return ok


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def save_manifest(results: list[dict]):
    manifest_path = RAW_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(results, f, indent=2)
    log.info(f"Manifest saved: {manifest_path}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def download_all():
    results = []
    total_10k = len(COMPANIES) * len(YEARS)
    total_10q = len(COMPANIES) * len(YEARS) * 3
    log.info(f"Starting download: {total_10k} 10-Ks + {total_10q} 10-Qs = {total_10k + total_10q} filings")

    for company in COMPANIES:
        for year in YEARS:
            ok = download_10k(company, year)
            results.append({
                "company": company, "fiscal_year": year,
                "document_type": "10-K", "quarter": None, "success": ok,
            })

            for q_label, q_start, q_end in quarter_date_ranges(company, year):
                ok = download_10q(company, year, q_label, q_start, q_end)
                results.append({
                    "company": company, "fiscal_year": year,
                    "document_type": "10-Q", "quarter": q_label, "success": ok,
                })

    save_manifest(results)
    success = sum(1 for r in results if r["success"])
    log.info(f"Download complete: {success}/{len(results)} succeeded")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    download_all()
