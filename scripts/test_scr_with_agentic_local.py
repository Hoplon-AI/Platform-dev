#!/usr/bin/env python3
"""
Test SCR document ingestion locally with agentic extraction (mocked Bedrock).

This simulates the full pipeline: upload -> extraction (regex + agentic) -> silver layer.
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Set env before imports
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
# Disable agentic for local (no Bedrock)
os.environ.setdefault("USE_AGENTIC_EXTRACTION", "false")

import asyncpg
from backend.core.pdf_extraction.pdf_pipeline import build_pdf_artifacts
from backend.workers.silver_processor import process_features_to_silver
from infrastructure.storage.s3_config import S3Config
from infrastructure.storage.upload_service import UploadService

HA_ID = "ha_demo"
BUCKET = os.environ.get("S3_BUCKET_NAME", "platform-bronze")
SCR_FILE = project_root / "data" / "scr" / "10532-midland-heart-crocodile-works-report.pdf"


async def ensure_ha_and_upload_audit(conn: asyncpg.Connection, upload_id: uuid.UUID, s3_key: str, file_bytes: bytes) -> None:
    """Ensure ha_demo exists and insert upload_audit row."""
    await conn.execute(
        "INSERT INTO housing_associations (ha_id, name) VALUES ($1, 'Demo HA') ON CONFLICT (ha_id) DO NOTHING",
        HA_ID,
    )
    import hashlib
    checksum = hashlib.sha256(file_bytes).hexdigest()
    await conn.execute(
        """
        INSERT INTO upload_audit (upload_id, ha_id, file_type, filename, s3_key, checksum, file_size, user_id, status)
        VALUES ($1, $2, 'scr_document', $3, $4, $5, $6, 'e2e', 'pending')
        ON CONFLICT (upload_id) DO UPDATE SET s3_key = $4, checksum = $5, file_size = $6
        """,
        upload_id,
        HA_ID,
        SCR_FILE.name,
        s3_key,
        checksum,
        len(file_bytes),
    )


async def main() -> int:
    print("=" * 70)
    print("Test SCR Document Ingestion (Regex + Agentic)")
    print("=" * 70)
    print(f"File: {SCR_FILE}")
    print(f"Bucket: {BUCKET}")
    print(f"Agentic: {'ENABLED' if os.getenv('USE_AGENTIC_EXTRACTION', '').lower() in ('1', 'true', 'yes') else 'DISABLED (local test)'}")
    print()

    if not SCR_FILE.exists():
        print(f"Error: SCR file not found: {SCR_FILE}")
        return 1

    # Read PDF
    print("[1/6] Reading SCR PDF...")
    with open(SCR_FILE, "rb") as f:
        file_bytes = f.read()
    print(f"  Size: {len(file_bytes):,} bytes")

    # Setup
    upload_id = uuid.uuid4()
    ingest_date = datetime.now(timezone.utc).date().isoformat()
    submission_prefix = f"ha_id={HA_ID}/bronze/dataset=scr_document/ingest_date={ingest_date}/submission_id={upload_id}/"
    source_s3_key = f"{submission_prefix}file={SCR_FILE.name}"

    print("\n[2/6] Ensuring DB state...")
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
        print("\nMake sure Postgres is running:")
        print("  docker compose up -d postgres")
        return 1

    try:
        await ensure_ha_and_upload_audit(conn, upload_id, source_s3_key, file_bytes)
    finally:
        await conn.close()

    # S3 setup
    print("\n[3/6] Setting up S3...")
    s3_cfg = S3Config(bucket_name=BUCKET)
    upload_svc = UploadService(s3_cfg)
    s3_cfg.ensure_bucket_exists()

    upload_svc.s3_client.put_object(
        Bucket=BUCKET,
        Key=source_s3_key,
        Body=file_bytes,
        ContentType="application/pdf",
    )

    # Extract features (regex)
    print("\n[4/6] Extracting features (regex)...")
    artifacts = build_pdf_artifacts(
        file_bytes,
        file_type="scr_document",
        filename=SCR_FILE.name,
    )
    print(f"  Scanned: {artifacts.extraction.get('scanned', False)}")
    print(f"  Pages: {len(artifacts.extraction.get('pages', []))}")

    # Note: Agentic would run here if USE_AGENTIC_EXTRACTION=true
    # For local test, we skip it (no Bedrock access)

    features_key = f"{submission_prefix}features.json"
    extraction_key = f"{submission_prefix}extraction.json"
    upload_svc.put_json(features_key, artifacts.features)
    upload_svc.put_json(extraction_key, artifacts.extraction)
    print(f"  Features key: {features_key}")

    # Process to silver
    print("\n[5/6] Processing to silver layer...")
    event = {"bucket": BUCKET, "key": features_key}
    result = await process_features_to_silver(event)
    if result.get("status") != "completed":
        print(f"  FAILED: {result}")
        return 1
    print(f"  Feature ID: {result.get('feature_id')}")

    # Validate
    print("\n[6/6] Validating results...")
    conn = await asyncpg.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        database=os.environ.get("DB_NAME", "platform_dev"),
    )
    try:
        doc = await conn.fetchrow(
            """
            SELECT feature_id, document_type, extraction_method,
                   agentic_features_json, extraction_comparison_metadata
            FROM document_features
            WHERE upload_id = $1
            """,
            upload_id,
        )
        if doc:
            print(f"  Document Type: {doc['document_type']}")
            print(f"  Extraction Method: {doc['extraction_method'] or 'regex'}")
            if doc["agentic_features_json"]:
                agentic = doc["agentic_features_json"]
                if isinstance(agentic, str):
                    agentic = json.loads(agentic)
                print(f"  Agentic Features: {len(agentic)} groups")
            else:
                print("  Agentic Features: None (regex-only in local test)")

        bsf = await conn.fetchrow(
            """
            SELECT high_rise_building_mentioned, evacuation_strategy_type,
                   fire_safety_measures_mentioned, extraction_method
            FROM building_safety_features
            WHERE upload_id = $1
            """,
            upload_id,
        )
        if bsf:
            print(f"  Building Safety Features: Found")
            print(f"    High-Rise: {bsf['high_rise_building_mentioned']}")
            print(f"    Evacuation: {bsf['evacuation_strategy_type']}")
            print(f"    Fire Safety: {bsf['fire_safety_measures_mentioned']}")
    finally:
        await conn.close()

    print("\n" + "=" * 70)
    print("✓ Test Complete")
    print("=" * 70)
    print(f"\nUpload ID: {upload_id}")
    print("\nTo see full results:")
    print(f"  python scripts/check_agentic_results.py {upload_id}")
    print("\nNote: Agentic extraction requires AWS Bedrock. For full test:")
    print("  1. Deploy PlatformIngestionDev to AWS")
    print("  2. Upload PDF to S3 bucket")
    print("  3. Lambda will run both regex and agentic extraction")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
