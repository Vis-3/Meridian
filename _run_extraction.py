"""
Extract all downloaded HTM/PDF filings into structured JSON.
Saves to data/processed/ and uploads to S3 processed bucket.
Skips files already processed (checks local cache).
"""
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from ingestion.extractor import extract_document, save_and_upload
from config import RAW_DIR, PROCESSED_DIR

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Collect all downloaded HTM/PDF files from RAW_DIR
all_paths = sorted(RAW_DIR.glob("*.htm")) + sorted(RAW_DIR.glob("*.pdf"))
# Skip the manifest itself and any non-filing files
all_paths = [p for p in all_paths if p.stem != "manifest"]

pdf_paths = []
skipped   = 0
for path in all_paths:
    processed = PROCESSED_DIR / f"{path.stem}.json"
    if processed.exists():
        skipped += 1
        continue
    pdf_paths.append(path)

log.info(f"Files to extract: {len(pdf_paths)}  (skipped already-done: {skipped})")

results = []
for i, path in enumerate(pdf_paths, 1):
    log.info(f"[{i}/{len(pdf_paths)}] Extracting {path.name}")
    doc = extract_document(path)
    if doc:
        results.append(doc)

save_and_upload(results, upload_to_s3=True)

# Summary
total_words = sum(
    sum(len(s["text"].split()) for s in doc["sections"].values())
    for doc in results
)
log.info(f"Done. Extracted {len(results)} documents, ~{total_words:,} words total.")
