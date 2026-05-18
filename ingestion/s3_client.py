"""
Meridian — AWS S3 client wrapper.

Raw PDFs land in:      s3://meridian-raw/{company}/{year}/{doctype}/{filename}
Processed JSON lands in: s3://meridian-processed/{company}/{year}/{doctype}/{filename}.json

Credentials are read from the environment or ~/.aws/credentials (standard boto3 chain).
Never hardcode keys here.
"""

import io
import json
import logging
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import S3_RAW_BUCKET, S3_PROCESSED_BUCKET, S3_REGION

log = logging.getLogger(__name__)

_s3 = None


def _client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=S3_REGION)
    return _s3


# ---------------------------------------------------------------------------
# Key builders
# ---------------------------------------------------------------------------

def raw_key(company: str, year: int, doctype: str, filename: str) -> str:
    """e.g. Apple/2024/10-K/apple_2024_10k.pdf"""
    return f"{company}/{year}/{doctype}/{filename}"


def processed_key(company: str, year: int, doctype: str, filename: str) -> str:
    """e.g. Apple/2024/10-K/apple_2024_10k.json"""
    stem = Path(filename).stem
    return f"{company}/{year}/{doctype}/{stem}.json"


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_pdf(local_path: Path, company: str, year: int, doctype: str) -> str:
    """Upload a local PDF to the raw bucket. Returns the S3 URI."""
    key = raw_key(company, year, doctype, local_path.name)
    try:
        _client().upload_file(
            str(local_path),
            S3_RAW_BUCKET,
            key,
            ExtraArgs={"ContentType": "application/pdf"},
        )
        uri = f"s3://{S3_RAW_BUCKET}/{key}"
        log.info(f"Uploaded to S3: {uri}")
        return uri
    except ClientError as e:
        log.error(f"S3 upload failed for {local_path.name}: {e}")
        raise


def upload_processed(data: dict, company: str, year: int, doctype: str,
                     source_filename: str) -> str:
    """Upload a processed JSON dict to the processed bucket. Returns S3 URI."""
    key = processed_key(company, year, doctype, source_filename)
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    try:
        _client().put_object(
            Bucket=S3_PROCESSED_BUCKET,
            Key=key,
            Body=body,
            ContentType="application/json",
        )
        uri = f"s3://{S3_PROCESSED_BUCKET}/{key}"
        log.info(f"Uploaded processed JSON to S3: {uri}")
        return uri
    except ClientError as e:
        log.error(f"S3 processed upload failed for {source_filename}: {e}")
        raise


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_pdf(company: str, year: int, doctype: str,
                 filename: str, dest_dir: Path) -> Path:
    """Download a raw PDF from S3 to a local path. Returns the local Path."""
    key = raw_key(company, year, doctype, filename)
    dest = dest_dir / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        log.info(f"Already cached locally: {dest.name}")
        return dest

    try:
        _client().download_file(S3_RAW_BUCKET, key, str(dest))
        log.info(f"Downloaded from S3: s3://{S3_RAW_BUCKET}/{key}")
        return dest
    except ClientError as e:
        log.error(f"S3 download failed for {key}: {e}")
        raise


def download_processed(company: str, year: int, doctype: str,
                       source_filename: str) -> Optional[dict]:
    """Fetch a processed JSON from S3. Returns None if not found."""
    key = processed_key(company, year, doctype, source_filename)
    try:
        resp = _client().get_object(Bucket=S3_PROCESSED_BUCKET, Key=key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        log.error(f"S3 fetch failed for {key}: {e}")
        raise


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def list_raw_pdfs(company: Optional[str] = None) -> list[str]:
    """List all raw PDF keys, optionally filtered by company."""
    prefix = f"{company}/" if company else ""
    paginator = _client().get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=S3_RAW_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".pdf"):
                keys.append(obj["Key"])
    return keys


def list_processed_jsons(company: Optional[str] = None) -> list[str]:
    """List all processed JSON keys."""
    prefix = f"{company}/" if company else ""
    paginator = _client().get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=S3_PROCESSED_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".json"):
                keys.append(obj["Key"])
    return keys


# ---------------------------------------------------------------------------
# Bucket bootstrap (run once)
# ---------------------------------------------------------------------------

def ensure_buckets():
    """Create buckets if they don't exist. Safe to call repeatedly."""
    s3 = _client()
    for bucket in (S3_RAW_BUCKET, S3_PROCESSED_BUCKET):
        try:
            if S3_REGION == "us-east-1":
                s3.create_bucket(Bucket=bucket)
            else:
                s3.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": S3_REGION},
                )
            log.info(f"Created bucket: {bucket}")
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                log.info(f"Bucket already exists: {bucket}")
            else:
                raise
