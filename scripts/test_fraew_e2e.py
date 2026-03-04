#!/usr/bin/env python3
"""
End-to-end test for each FRAEW file in data/fraew directory.

For each file, this script:
1. Uploads the file via API
2. Verifies features.json is created in S3
3. Processes features to Silver layer
4. Validates data in database tables
5. Reports success/failure for each step
"""
import os
import sys
import asyncio
import httpx
import boto3
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncpg
from backend.workers.silver_processor import process_features_to_silver

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
FRAEW_UPLOAD_ENDPOINT = f"{API_BASE_URL}/api/v1/upload/fraew-document"

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://localhost:4566")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "platform-bronze")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "platform_dev")

# S3 client
s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)


async def upload_file(file_path: Path) -> Dict[str, Any]:
    """Upload a file via the API."""
    print(f"  📤 Uploading {file_path.name}...")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        with open(file_path, "rb") as f:
            file_data = {"file": (file_path.name, f.read(), "application/pdf")}
            
            try:
                response = await client.post(
                    FRAEW_UPLOAD_ENDPOINT,
                    files=file_data,
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "success": True,
                    "upload_id": result.get("upload_id"),
                    "s3_key": result.get("s3_key"),
                    "features_s3_key": result.get("features_s3_key"),
                    "extraction_s3_key": result.get("extraction_s3_key"),
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }


def check_features_in_s3(features_key: str, max_wait: int = 30) -> bool:
    """Check if features.json exists in S3, wait if needed."""
    print(f"  🔍 Checking for features.json in S3...")
    
    for i in range(max_wait):
        try:
            s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=features_key)
            print(f"  ✅ features.json found in S3")
            return True
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                if i < max_wait - 1:
                    time.sleep(1)
                    continue
                print(f"  ❌ features.json not found after {max_wait} seconds")
                return False
            else:
                print(f"  ❌ Error checking S3: {e}")
                return False
    
    return False


async def process_to_silver(features_key: str) -> Dict[str, Any]:
    """Process features.json to Silver layer."""
    print(f"  ⚙️  Processing to Silver layer...")
    
    event = {
        "bucket": S3_BUCKET_NAME,
        "key": features_key,
    }
    
    try:
        result = await process_features_to_silver(event)
        
        if result.get("status") == "completed":
            return {
                "success": True,
                "feature_id": result.get("feature_id"),
                "document_type": result.get("document_type"),
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status": result.get("status"),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def validate_in_database(upload_id: str, feature_id: Optional[str] = None) -> Dict[str, Any]:
    """Validate data exists in database tables."""
    print(f"  ✅ Validating in database...")
    
    conn = await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )
    
    try:
        # Check upload_audit
        upload_row = await conn.fetchrow(
            "SELECT upload_id, filename, status FROM upload_audit WHERE upload_id = $1",
            upload_id,
        )
        
        if not upload_row:
            return {
                "success": False,
                "error": "Upload not found in upload_audit",
            }
        
        # Check document_features
        doc_feature = await conn.fetchrow(
            "SELECT feature_id, document_type, building_name, uprn, postcode FROM document_features WHERE upload_id = $1",
            upload_id,
        )
        
        if not doc_feature:
            return {
                "success": False,
                "error": "Document features not found",
            }
        
        # Check fraew_features
        fraew_feature = await conn.fetchrow(
            "SELECT fraew_id, pas_9980_compliant, building_risk_rating FROM fraew_features WHERE feature_id = $1",
            doc_feature["feature_id"],
        )
        
        if not fraew_feature:
            return {
                "success": False,
                "error": "FRAEW features not found",
            }
        
        # Check processing_audit
        processing = await conn.fetchrow(
            "SELECT status FROM processing_audit WHERE source_id = $1 AND transformation_type = 'silver_layer_v1'",
            upload_id,
        )
        
        return {
            "success": True,
            "upload": {
                "filename": upload_row["filename"],
                "status": upload_row["status"],
            },
            "document_features": {
                "feature_id": str(doc_feature["feature_id"]),
                "document_type": doc_feature["document_type"],
                "building_name": doc_feature["building_name"],
                "uprn": doc_feature["uprn"],
                "postcode": doc_feature["postcode"],
            },
            "fraew_features": {
                "pas_9980_compliant": fraew_feature["pas_9980_compliant"],
                "building_risk_rating": fraew_feature["building_risk_rating"],
            },
            "processing_audit": {
                "status": processing["status"] if processing else None,
            },
        }
    finally:
        await conn.close()


async def test_file_e2e(file_path: Path) -> Dict[str, Any]:
    """Run end-to-end test for a single file."""
    print(f"\n{'='*60}")
    print(f"Testing: {file_path.name}")
    print(f"{'='*60}")
    
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    print(f"File size: {file_size_mb:.2f} MB")
    
    results = {
        "filename": file_path.name,
        "file_size_mb": file_size_mb,
        "steps": {},
    }
    
    # Step 1: Upload
    upload_result = await upload_file(file_path)
    results["steps"]["upload"] = upload_result
    
    if not upload_result["success"]:
        print(f"  ❌ Upload failed: {upload_result.get('error')}")
        return results
    
    upload_id = upload_result["upload_id"]
    features_key = upload_result.get("features_s3_key")
    
    print(f"  ✅ Upload successful (ID: {upload_id})")
    
    # Step 2: Wait for features extraction (if INLINE_PDF_EXTRACTION is enabled)
    if features_key:
        features_exist = check_features_in_s3(features_key)
        results["steps"]["features_extraction"] = {
            "success": features_exist,
            "features_key": features_key,
        }
        
        if not features_exist:
            print(f"  ⚠️  Features not extracted (may need INLINE_PDF_EXTRACTION=true)")
            # Try to extract manually
            print(f"  🔧 Attempting manual extraction...")
            from scripts.extract_missing_features import extract_and_upload_features
            try:
                extract_result = await extract_and_upload_features({
                    "upload_id": upload_id,
                    "filename": file_path.name,
                    "s3_key": upload_result["s3_key"],
                    "features_s3_key": features_key,
                    "extraction_s3_key": upload_result.get("extraction_s3_key"),
                    "submission_prefix": "/".join(features_key.split("/")[:-1]) + "/",
                })
                if extract_result.get("success"):
                    features_exist = True
                    results["steps"]["features_extraction"]["manual_extraction"] = True
            except Exception as e:
                print(f"  ❌ Manual extraction failed: {e}")
    else:
        features_exist = False
        results["steps"]["features_extraction"] = {
            "success": False,
            "error": "No features_s3_key in upload response",
        }
    
    # Step 3: Process to Silver layer
    if features_exist and features_key:
        silver_result = await process_to_silver(features_key)
        results["steps"]["silver_processing"] = silver_result
        
        if silver_result["success"]:
            print(f"  ✅ Silver processing successful (feature_id: {silver_result.get('feature_id')})")
            
            # Step 4: Validate in database
            db_result = await validate_in_database(upload_id, silver_result.get("feature_id"))
            results["steps"]["database_validation"] = db_result
            
            if db_result["success"]:
                print(f"  ✅ Database validation successful")
                print(f"     - Building: {db_result['document_features'].get('building_name', 'N/A')}")
                print(f"     - UPRN: {db_result['document_features'].get('uprn', 'N/A')}")
                print(f"     - Postcode: {db_result['document_features'].get('postcode', 'N/A')}")
                print(f"     - Risk Rating: {db_result['fraew_features'].get('building_risk_rating', 'N/A')}")
                print(f"     - PAS 9980 Compliant: {db_result['fraew_features'].get('pas_9980_compliant', 'N/A')}")
            else:
                print(f"  ❌ Database validation failed: {db_result.get('error')}")
        else:
            print(f"  ❌ Silver processing failed: {silver_result.get('error')}")
            results["steps"]["database_validation"] = {
                "success": False,
                "error": "Silver processing failed, skipping validation",
            }
    else:
        results["steps"]["silver_processing"] = {
            "success": False,
            "error": "Features not available",
        }
        results["steps"]["database_validation"] = {
            "success": False,
            "error": "Features not available",
        }
    
    return results


async def main():
    """Main function to test all FRAEW files."""
    print("=" * 60)
    print("FRAEW End-to-End Test Suite")
    print("=" * 60)
    
    # Find all FRAEW files
    fraew_dir = project_root / "data" / "fraew"
    if not fraew_dir.exists():
        print(f"❌ Directory not found: {fraew_dir}")
        return
    
    pdf_files = sorted([f for f in fraew_dir.glob("*.pdf") if not f.name.startswith(".")])
    
    if not pdf_files:
        print(f"❌ No PDF files found in {fraew_dir}")
        return
    
    print(f"\nFound {len(pdf_files)} FRAEW file(s) to test:")
    for i, file_path in enumerate(pdf_files, 1):
        file_size = file_path.stat().st_size / (1024 * 1024)
        print(f"  {i}. {file_path.name} ({file_size:.2f} MB)")
    
    # Test each file
    all_results = []
    for file_path in pdf_files:
        result = await test_file_e2e(file_path)
        all_results.append(result)
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    total = len(all_results)
    upload_success = sum(1 for r in all_results if r["steps"].get("upload", {}).get("success"))
    features_success = sum(1 for r in all_results if r["steps"].get("features_extraction", {}).get("success"))
    silver_success = sum(1 for r in all_results if r["steps"].get("silver_processing", {}).get("success"))
    db_success = sum(1 for r in all_results if r["steps"].get("database_validation", {}).get("success"))
    
    print(f"\nTotal files tested: {total}")
    print(f"✅ Upload successful: {upload_success}/{total}")
    print(f"✅ Features extracted: {features_success}/{total}")
    print(f"✅ Silver processing: {silver_success}/{total}")
    print(f"✅ Database validation: {db_success}/{total}")
    
    # Detailed results
    print("\n" + "=" * 60)
    print("Detailed Results")
    print("=" * 60)
    
    for result in all_results:
        print(f"\n📄 {result['filename']} ({result['file_size_mb']:.2f} MB)")
        print(f"   Upload: {'✅' if result['steps'].get('upload', {}).get('success') else '❌'}")
        print(f"   Features: {'✅' if result['steps'].get('features_extraction', {}).get('success') else '❌'}")
        print(f"   Silver: {'✅' if result['steps'].get('silver_processing', {}).get('success') else '❌'}")
        print(f"   Database: {'✅' if result['steps'].get('database_validation', {}).get('success') else '❌'}")
        
        # Show errors if any
        for step_name, step_result in result["steps"].items():
            if not step_result.get("success"):
                error = step_result.get("error", "Unknown error")
                print(f"      {step_name} error: {error}")
    
    print("\n" + "=" * 60)
    print("End-to-end test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
