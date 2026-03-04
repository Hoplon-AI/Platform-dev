#!/usr/bin/env python3
"""
Standalone e2e: PDF -> build_pdf_artifacts -> S3 -> process_features_to_silver -> DB checks.

Does not require the API or Step Functions. Run after:
  docker compose up -d
  # Apply migrations 001_bronze, 001_silver, 002, 003, 004, 005, 006 (and 007, 001_gold if desired)
  # Seed: week3_seed.sql (or ensure ha_demo exists)
  # Create bucket: awslocal s3 mb s3://platform-bronze  (or the script ensures it)

Usage:
  export S3_ENDPOINT_URL=http://localhost:4566
  export S3_BUCKET_NAME=platform-bronze
  export AWS_ACCESS_KEY_ID=test
  export AWS_SECRET_ACCESS_KEY=test
  export AWS_DEFAULT_REGION=us-east-1
  export DB_HOST=localhost DB_PORT=5432 DB_USER=postgres DB_PASSWORD=postgres DB_NAME=platform_dev

  python scripts/run_e2e_ingestion_local.py
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Set env before imports that read it
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:4566")
os.environ.setdefault("S3_BUCKET_NAME", "platform-bronze")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_USER", "postgres")
os.environ.setdefault("DB_PASSWORD", "postgres")
os.environ.setdefault("DB_NAME", "platform_dev")

import asyncpg
from backend.core.pdf_extraction.pdf_pipeline import build_pdf_artifacts
from backend.workers.silver_processor import process_features_to_silver
from infrastructure.storage.s3_config import S3Config
from infrastructure.storage.upload_service import UploadService


HA_ID = "ha_demo"
BUCKET = os.environ.get("S3_BUCKET_NAME", "platform-bronze")


def create_minimal_fra_pdf() -> bytes:
    """Create a minimal FRA-like PDF with text that extract_fra_features can parse."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        raise SystemExit("reportlab is required: pip install reportlab")

    buf = __import__("io").BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 800, "Fire Risk Assessment")
    c.drawString(72, 770, "Premises: E2E Test Building")
    c.drawString(72, 750, "Address: 1 Test Street, London")
    c.drawString(72, 720, "Overall risk: Moderate")
    c.drawString(72, 690, "Evacuation strategy: Stay Put")
    c.drawString(72, 660, "Regulatory Reform (Fire Safety) Order 2005")
    c.drawString(72, 630, "Date assessed: 15 January 2025")
    c.drawString(72, 600, "Client: Demo Housing Association")
    c.save()
    return buf.getvalue()


async def ensure_ha_and_upload_audit(conn: asyncpg.Connection, upload_id: uuid.UUID, s3_key: str, file_bytes: bytes) -> None:
    """Ensure ha_demo exists and insert upload_audit row."""
    await conn.execute(
        "INSERT INTO housing_associations (ha_id, name) VALUES ($1, 'Demo HA') ON CONFLICT (ha_id) DO NOTHING",
        HA_ID,
    )
    checksum = hashlib.sha256(file_bytes).hexdigest()
    await conn.execute(
        """
        INSERT INTO upload_audit (upload_id, ha_id, file_type, filename, s3_key, checksum, file_size, user_id, status)
        VALUES ($1, $2, 'fra_document', 'sample_fra.pdf', $3, $4, $5, 'e2e', 'pending')
        ON CONFLICT (upload_id) DO UPDATE SET s3_key = $3, checksum = $4, file_size = $5
        """,
        upload_id,
        HA_ID,
        s3_key,
        checksum,
        len(file_bytes),
    )


async def main() -> int:
    print("E2E Ingestion (build_pdf_artifacts -> S3 -> process_features_to_silver)")
    print("  S3_ENDPOINT_URL:", os.environ.get("S3_ENDPOINT_URL"))
    print("  S3_BUCKET_NAME:", BUCKET)
    print("  DB_HOST:", os.environ.get("DB_HOST"))

    # 1) Create minimal PDF
    print("\n[1/6] Creating minimal FRA PDF...")
    file_bytes = create_minimal_fra_pdf()
    print(f"  PDF size: {len(file_bytes)} bytes")

    # 2) DB: ensure ha_demo and upload_audit
    upload_id = uuid.uuid4()
    ingest_date = datetime.now(timezone.utc).date().isoformat()
    submission_prefix = f"ha_id={HA_ID}/bronze/dataset=fra_document/ingest_date={ingest_date}/submission_id={upload_id}/"
    source_s3_key = f"{submission_prefix}file=sample_fra.pdf"

    print("\n[2/6] Ensuring DB state (ha_demo, upload_audit)...")
    try:
        conn = await asyncpg.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "5432")),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", "postgres"),
            database=os.environ.get("DB_NAME", "platform_dev"),
        )
    except Exception as e:
        print(f"  DB connection failed: {e}")
        return 1

    try:
        await ensure_ha_and_upload_audit(conn, upload_id, source_s3_key, file_bytes)
    finally:
        await conn.close()

    # 3) S3: bucket, source PDF, extraction + features
    print("\n[3/6] S3: bucket, source PDF, extraction + features...")
    s3_cfg = S3Config(bucket_name=BUCKET)
    upload_svc = UploadService(s3_cfg)
    s3_cfg.ensure_bucket_exists()

    upload_svc.s3_client.put_object(
        Bucket=BUCKET,
        Key=source_s3_key,
        Body=file_bytes,
        ContentType="application/pdf",
    )

    artifacts = build_pdf_artifacts(
        file_bytes,
        file_type="fra_document",
        filename="sample_fra.pdf",
    )

    features_key = f"{submission_prefix}features.json"
    extraction_key = f"{submission_prefix}extraction.json"
    upload_svc.put_json(features_key, artifacts.features)
    upload_svc.put_json(extraction_key, artifacts.extraction)
    print(f"  features: {features_key}")

    # 4) process_features_to_silver
    print("\n[4/6] process_features_to_silver...")
    event = {"bucket": BUCKET, "key": features_key}
    result = await process_features_to_silver(event)
    if result.get("status") != "completed":
        print(f"  FAILED: {result}")
        return 1
    print(f"  feature_id: {result.get('feature_id')}")

    # 5) Validate document_features and fra_features
    print("\n[5/6] Validating DB (document_features, fra_features)...")
    conn = await asyncpg.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        database=os.environ.get("DB_NAME", "platform_dev"),
    )
    try:
        doc = await conn.fetchrow(
            "SELECT feature_id, document_type, building_name FROM document_features WHERE upload_id = $1",
            upload_id,
        )
        if not doc:
            print("  document_features: no row")
            return 1
        print(f"  document_features: feature_id={doc['feature_id']}, document_type={doc['document_type']}")

        fra = await conn.fetchrow(
            "SELECT fra_id, fra_features_json FROM fra_features WHERE feature_id = $1",
            doc["feature_id"],
        )
        if not fra:
            print("  fra_features: no row")
            return 1
        print(f"  fra_features: fra_id={fra['fra_id']}")
    finally:
        await conn.close()

    print("\n[6/6] E2E OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
