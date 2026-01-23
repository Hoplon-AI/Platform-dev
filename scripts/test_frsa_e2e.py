#!/usr/bin/env python3
"""
End-to-end test script for FRA document ingestion.
Tests the full pipeline: upload → extraction → silver layer processing.
"""

import asyncio
import json
import os
import sys
import boto3
import time
from pathlib import Path
from typing import Dict, Optional, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncpg
from backend.core.database.db_pool import DatabasePool
from backend.workers.silver_processor import process_features_to_silver
from backend.core.pdf_extraction.pdf_pipeline import build_pdf_artifacts
from infrastructure.storage.s3_config import S3Config
from infrastructure.storage.upload_service import UploadService

# Configuration
HA_ID = "ha_demo"
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "platform-bronze")
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://localhost:4566")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# S3 client
s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)


async def upload_fra_file(file_path: Path) -> Dict:
    """Upload a FRA PDF file via the API."""
    import httpx
    
    url = f"{BASE_URL}/api/v1/upload/fra-document"
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f.read(), "application/pdf")}
            data = {"ha_id": HA_ID}
            
            try:
                response = await client.post(url, data=data, files=files)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_text = e.response.text if e.response else str(e)
                raise Exception(f"Upload failed: {e.response.status_code} - {error_text}")
            except Exception as e:
                raise Exception(f"Upload failed: {str(e)}")


async def validate_in_database(upload_id: str, feature_id: Optional[str] = None) -> Dict[str, any]:
    """Validate that FRA features were written to the database."""
    pool = DatabasePool.get_pool()
    conn = await pool.acquire()
    
    try:
        # Check document_features
        doc_row = await conn.fetchrow(
            """
            SELECT feature_id, document_type, building_name, address, 
                   uprn, postcode, assessment_date, job_reference,
                   client_name, assessor_company
            FROM document_features
            WHERE upload_id = $1 AND document_type = 'fra_document'
            """,
            upload_id,
        )
        
        if not doc_row:
            return {"status": "error", "message": "No document_features found"}
        
        feature_id = str(doc_row["feature_id"])
        
        # Check fra_features
        fra_row = await conn.fetchrow(
            """
            SELECT fra_id, risk_rating, assessment_valid_until,
                   building_name, address, job_reference,
                   client_name, assessor_company,
                   has_fire_safety_measures, has_emergency_procedures,
                   has_maintenance_requirements, fso_compliant,
                   fire_safety_act_compliant, uprn, postcode
            FROM fra_features
            WHERE feature_id = $1
            """,
            doc_row["feature_id"],
        )
        
        if not fra_row:
            return {"status": "error", "message": "No fra_features found"}
        
        return {
            "status": "success",
            "document_features": dict(doc_row),
            "fra_features": dict(fra_row),
        }
    finally:
        await pool.release(conn)


def find_features_json_in_s3(upload_id: str, max_wait: int = 30) -> Optional[str]:
    """Find features.json in S3 for the given upload_id, wait if needed."""
    prefix = f"ha_id={HA_ID}/bronze/dataset=fra_document/"
    
    for i in range(max_wait):
        try:
            # List objects with the prefix
            response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    if f"submission_id={upload_id}" in key and key.endswith("features.json"):
                        return key
            
            if i < max_wait - 1:
                time.sleep(1)
                continue
        except Exception as e:
            if i < max_wait - 1:
                time.sleep(1)
                continue
            raise Exception(f"Error listing S3 objects: {e}")
    
    return None


async def extract_and_upload_features(file_path: Path, upload_result: Dict) -> Optional[str]:
    """Manually extract features from PDF and upload to S3."""
    try:
        print("  🔧 Extracting features manually...")
        
        # Read the PDF file
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        
        # Extract features
        artifacts = build_pdf_artifacts(
            file_bytes,
            file_type="fra_document",
            filename=file_path.name,
        )
        
        # Upload to S3
        features_s3_key = upload_result.get("features_s3_key")
        if not features_s3_key:
            return None
        
        s3_cfg = S3Config(bucket_name=S3_BUCKET)
        upload_service = UploadService(s3_cfg)
        
        # Upload features.json
        upload_service.put_json(features_s3_key, artifacts.features)
        
        # Also upload extraction.json if we have the key
        extraction_s3_key = upload_result.get("extraction_s3_key")
        if extraction_s3_key:
            upload_service.put_json(extraction_s3_key, artifacts.extraction)
        
        print(f"  ✓ Features extracted and uploaded to {features_s3_key}")
        return features_s3_key
        
    except Exception as e:
        print(f"  ✗ Manual extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None




async def test_fra_file(file_path: Path):
    """Test a single FRA file end-to-end."""
    print(f"\n{'='*60}")
    print(f"Testing: {file_path.name}")
    print(f"{'='*60}")
    
    # Step 1: Upload
    print("\n[1/4] Uploading FRA document...")
    try:
        upload_result = await upload_fra_file(file_path)
        upload_id = upload_result.get("upload_id")
        features_s3_key = upload_result.get("features_s3_key")
        print(f"✓ Upload successful: upload_id={upload_id}")
        print(f"  File type: {upload_result.get('file_type')}")
        print(f"  Status: {upload_result.get('status')}")
        if features_s3_key:
            print(f"  Features key: {features_s3_key}")
    except Exception as e:
        print(f"✗ Upload failed: {e}")
        return
    
    # Step 2: Wait for feature extraction (if not already done)
    print("\n[2/4] Waiting for feature extraction...")
    if not features_s3_key:
        # Wait and search for features.json
        print("  Features not extracted inline, searching S3...")
        features_s3_key = find_features_json_in_s3(upload_id, max_wait=10)
        if not features_s3_key:
            print(f"  Features.json not found, attempting manual extraction...")
            features_s3_key = await extract_and_upload_features(file_path, upload_result)
            if not features_s3_key:
                print(f"✗ Failed to extract features")
                return
    else:
        # Even if key is returned, file might not exist yet - wait for it
        print(f"  Checking if features.json exists in S3...")
        max_wait = 5
        features_exist = False
        for i in range(max_wait):
            try:
                s3_client.head_object(Bucket=S3_BUCKET, Key=features_s3_key)
                features_exist = True
                print(f"✓ Features.json found in S3")
                break
            except s3_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == '404':
                    if i < max_wait - 1:
                        await asyncio.sleep(1)
                        continue
                    # File doesn't exist, extract manually
                    print(f"  Features.json not found, attempting manual extraction...")
                    features_s3_key = await extract_and_upload_features(file_path, upload_result)
                    if not features_s3_key:
                        print(f"✗ Failed to extract features")
                        return
                    break
                else:
                    raise
    
    # Step 3: Process to silver
    print("\n[3/4] Processing to silver layer...")
    try:
        event = {
            "bucket": S3_BUCKET,
            "key": features_s3_key,
        }
        silver_result = await process_features_to_silver(event)
        if silver_result.get("status") == "completed":
            print(f"✓ Silver processing successful")
            print(f"  Feature ID: {silver_result.get('feature_id')}")
        else:
            print(f"✗ Silver processing failed: {silver_result}")
            return
    except Exception as e:
        print(f"✗ Silver processing error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 4: Validate in database
    print("\n[4/4] Validating database records...")
    try:
        validation = await validate_in_database(upload_id)
        if validation.get("status") == "success":
            print("✓ Database validation successful")
            print("\nDocument Features:")
            doc_feat = validation["document_features"]
            for key, value in doc_feat.items():
                if value:
                    print(f"  {key}: {value}")
            
            print("\nFRA Features:")
            fra_feat = validation["fra_features"]
            for key, value in fra_feat.items():
                if value:
                    print(f"  {key}: {value}")
        else:
            print(f"✗ Database validation failed: {validation.get('message')}")
    except Exception as e:
        print(f"✗ Database validation error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main test function."""
    # Initialize database pool
    await DatabasePool.initialize()
    
    # Find FRA files
    frsa_dir = Path(__file__).parent.parent / "data" / "frsa"
    frsa_files = list(frsa_dir.glob("*.pdf")) if frsa_dir.exists() else []
    
    if not frsa_files:
        print(f"No FRA PDF files found in {frsa_dir}")
        print("Please add FRA PDF files to test.")
        return
    
    print(f"Found {len(frsa_files)} FRA file(s) to test")
    
    # Test each file
    for frsa_file in frsa_files:
        await test_fra_file(frsa_file)
    
    print(f"\n{'='*60}")
    print("Testing complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
