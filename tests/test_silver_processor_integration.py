"""
Integration tests for Silver layer processor.

Tests use real PostgreSQL database and LocalStack S3.
"""
import pytest
import pytest_asyncio
import uuid
import json
import os
import boto3
import asyncpg
from datetime import datetime

from backend.workers.silver_processor import process_features_to_silver
from infrastructure.storage.s3_config import S3Config, set_s3_config
from infrastructure.storage.upload_service import UploadService


@pytest_asyncio.fixture
async def integration_db_pool():
    """Create a database pool for integration tests using main platform_dev database."""
    try:
        pool = await asyncpg.create_pool(
            host=os.getenv('TEST_DB_HOST', 'localhost'),
            port=int(os.getenv('TEST_DB_PORT', '5432')),
            user=os.getenv('TEST_DB_USER', 'postgres'),
            password=os.getenv('TEST_DB_PASSWORD', 'postgres'),
            database=os.getenv('TEST_DB_NAME', 'platform_dev'),  # Use main DB for integration tests
            min_size=2,
            max_size=5,
        )
        yield pool
        await pool.close()
    except asyncpg.PostgresConnectionError as e:
        pytest.skip(f"Could not connect to database: {e}")


@pytest_asyncio.fixture
async def cleanup_tables(integration_db_pool):
    """Clean up test data after each test."""
    yield
    async with integration_db_pool.acquire() as conn:
        # Delete in order to respect foreign key constraints
        await conn.execute("DELETE FROM silver.fraew_features WHERE ha_id = 'test_ha_silver'")
        await conn.execute("DELETE FROM silver.fra_features WHERE ha_id = 'test_ha_silver'")
        await conn.execute("DELETE FROM silver.scr_features WHERE ha_id = 'test_ha_silver'")
        await conn.execute("DELETE FROM silver.frsa_features WHERE ha_id = 'test_ha_silver'")
        await conn.execute("DELETE FROM silver.document_features WHERE ha_id = 'test_ha_silver'")
        await conn.execute("DELETE FROM processing_audit WHERE ha_id = 'test_ha_silver'")
        await conn.execute("DELETE FROM upload_audit WHERE ha_id = 'test_ha_silver'")
        # Only delete test HA if it exists and has no other references
        await conn.execute("DELETE FROM housing_associations WHERE ha_id = 'test_ha_silver' AND NOT EXISTS (SELECT 1 FROM silver.portfolios WHERE silver.portfolios.ha_id = housing_associations.ha_id)")


@pytest.fixture
def test_ha_id():
    """Test housing association ID."""
    return "test_ha_silver"


@pytest_asyncio.fixture
async def setup_ha(integration_db_pool, test_ha_id):
    """Set up test housing association."""
    async with integration_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO housing_associations (ha_id, name)
            VALUES ($1, 'Test HA Silver')
            ON CONFLICT (ha_id) DO NOTHING
            """,
            test_ha_id
        )


@pytest.fixture
def localstack_s3_config():
    """Configure S3 to use LocalStack."""
    config = S3Config(
        bucket_name="platform-bronze",
        endpoint_url="http://localhost:4566",
        access_key_id="test",
        secret_access_key="test",
        region="us-east-1"
    )
    set_s3_config(config)
    return config


@pytest.fixture
def localstack_s3_client(localstack_s3_config):
    """Create S3 client for LocalStack."""
    return boto3.client(
        's3',
        endpoint_url=localstack_s3_config.endpoint_url,
        aws_access_key_id=localstack_s3_config.access_key_id,
        aws_secret_access_key=localstack_s3_config.secret_access_key,
        region_name=localstack_s3_config.region
    )


@pytest.fixture
def ensure_localstack_bucket(localstack_s3_client):
    """Ensure LocalStack bucket exists."""
    try:
        localstack_s3_client.head_bucket(Bucket="platform-bronze")
    except:
        localstack_s3_client.create_bucket(Bucket="platform-bronze")


@pytest.fixture
def sample_features_json():
    """Sample features.json for FRAEW document."""
    return {
        "document": {
            "file_type": "fraew_document",
            "filename": "test_fraew.pdf"
        },
        "features": {
            "uprns": ["123456789012"],
            "postcodes": ["SW1A 1AA"],
            "dates": ["2024-01-15"],
            "fraew_specific": {
                "pas_9980_compliant": True,
                "pas_9980_version": "2022",
                "building_name": "Test Building",
                "address": "123 Test Street, London",
                "building_risk_rating": "HIGH",
                "assessment_date": "2024-01-15",
                "job_reference": "JOB-123",
                "client_name": "Test Client",
                "assessor_company": "Test Assessor Ltd",
                "wall_types": [
                    {"type_number": 1, "name": "Wall Type A", "risk_rating": "LOW"}
                ],
                "has_interim_measures": True,
                "has_remedial_actions": False,
            }
        },
        "extracted_at": "2024-01-15T10:00:00Z"
    }


@pytest_asyncio.fixture
async def setup_upload_audit(integration_db_pool, test_ha_id):
    """Set up upload_audit record for testing."""
    upload_id = uuid.uuid4()
    async with integration_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO upload_audit (
                upload_id, ha_id, file_type, filename, s3_key, checksum, file_size, user_id, metadata
            )
            VALUES ($1, $2, 'fraew_document', 'test.pdf', 'test/key', 'abc123', 1024, 'test_user', '{}'::jsonb)
            """,
            upload_id,
            test_ha_id
        )
    return upload_id


@pytest.mark.asyncio
async def test_process_fraew_features_to_silver(
    integration_db_pool,
    cleanup_tables,
    setup_ha,
    test_ha_id,
    localstack_s3_config,
    localstack_s3_client,
    ensure_localstack_bucket,
    sample_features_json,
    setup_upload_audit
):
    """Integration test: Process FRAEW features from LocalStack S3 to PostgreSQL."""
    upload_id = setup_upload_audit
    
    # Upload features.json to LocalStack S3
    s3_key = f"ha_id={test_ha_id}/bronze/dataset=fraew_document/ingest_date=2024-01-15/submission_id={upload_id}/features.json"
    
    localstack_s3_client.put_object(
        Bucket="platform-bronze",
        Key=s3_key,
        Body=json.dumps(sample_features_json),
        ContentType="application/json"
    )
    
    # Process features to Silver
    event = {
        "bucket": "platform-bronze",
        "key": s3_key,
        "execution_arn": "arn:aws:states:us-east-1:123456789012:execution:test"
    }
    
    # Set environment variables for database connection
    os.environ["DB_HOST"] = "localhost"
    os.environ["DB_PORT"] = "5432"
    os.environ["DB_USER"] = "postgres"
    os.environ["DB_PASSWORD"] = "postgres"
    os.environ["DB_NAME"] = "platform_dev"
    
    result = await process_features_to_silver(event)
    
    # Debug: print result if failed
    if result.get("status") != "completed":
        print(f"\nProcessing failed. Result: {json.dumps(result, indent=2)}")
    
    # Verify processing succeeded
    assert result["status"] == "completed", f"Expected 'completed' but got: {result}"
    assert result["document_type"] == "fraew_document"
    assert result["ha_id"] == test_ha_id
    assert result["upload_id"] == str(upload_id)
    
    # Verify data in document_features table
    async with integration_db_pool.acquire() as conn:
        doc_feature = await conn.fetchrow(
            """
            SELECT * FROM silver.document_features
            WHERE upload_id = $1 AND ha_id = $2
            """,
            upload_id,
            test_ha_id
        )

        assert doc_feature is not None
        assert doc_feature["document_type"] == "fraew_document"
        assert doc_feature["building_name"] == "Test Building"
        assert doc_feature["address"] == "123 Test Street, London"
        assert doc_feature["uprn"] == "123456789012"
        assert doc_feature["postcode"] == "SW1A 1AA"

        # Verify data in fraew_features table
        fraew_feature = await conn.fetchrow(
            """
            SELECT * FROM silver.fraew_features
            WHERE upload_id = $1 AND ha_id = $2
            """,
            upload_id,
            test_ha_id
        )
        
        assert fraew_feature is not None
        assert fraew_feature["pas_9980_compliant"] is True
        assert fraew_feature["pas_9980_version"] == "2022"
        assert fraew_feature["building_risk_rating"] == "HIGH"
        assert fraew_feature["has_interim_measures"] is True
        assert fraew_feature["has_remedial_actions"] is False
        
        # Verify processing_audit updated
        processing = await conn.fetchrow(
            """
            SELECT * FROM processing_audit
            WHERE source_id = $1 AND ha_id = $2 AND transformation_type = 'silver_layer_v1'
            """,
            upload_id,
            test_ha_id
        )
        
        assert processing is not None
        assert processing["status"] == "completed"


@pytest.mark.asyncio
async def test_process_fra_features_to_silver(
    integration_db_pool,
    cleanup_tables,
    setup_ha,
    test_ha_id,
    localstack_s3_config,
    localstack_s3_client,
    ensure_localstack_bucket
):
    """Integration test: Process FRA features from LocalStack S3 to PostgreSQL."""
    upload_id = uuid.uuid4()
    
    # Set up upload_audit
    async with integration_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO upload_audit (
                upload_id, ha_id, file_type, filename, s3_key, checksum, file_size, user_id, metadata
            )
            VALUES ($1, $2, 'fra_document', 'test.pdf', 'test/key', 'abc123', 1024, 'test_user', '{}'::jsonb)
            """,
            upload_id,
            test_ha_id
        )
    
    # Upload features.json to LocalStack S3
    features_json = {
        "document": {"file_type": "fra_document"},
        "features": {
            "uprns": ["987654321098"],
            "postcodes": ["NW1 1AA"],
        }
    }
    
    s3_key = f"ha_id={test_ha_id}/bronze/dataset=fra_document/ingest_date=2024-01-15/submission_id={upload_id}/features.json"
    
    localstack_s3_client.put_object(
        Bucket="platform-bronze",
        Key=s3_key,
        Body=json.dumps(features_json),
        ContentType="application/json"
    )
    
    # Process features to Silver
    event = {
        "bucket": "platform-bronze",
        "key": s3_key,
    }
    
    os.environ["DB_HOST"] = "localhost"
    os.environ["DB_PORT"] = "5432"
    os.environ["DB_USER"] = "postgres"
    os.environ["DB_PASSWORD"] = "postgres"
    os.environ["DB_NAME"] = "platform_dev"
    
    result = await process_features_to_silver(event)
    
    # Verify processing succeeded
    assert result["status"] == "completed"
    assert result["document_type"] == "fra_document"
    
    # Verify data in document_features table
    async with integration_db_pool.acquire() as conn:
        doc_feature = await conn.fetchrow(
            """
            SELECT * FROM silver.document_features
            WHERE upload_id = $1 AND ha_id = $2
            """,
            upload_id,
            test_ha_id
        )

        assert doc_feature is not None
        assert doc_feature["document_type"] == "fra_document"

        # Verify data in fra_features table
        fra_feature = await conn.fetchrow(
            """
            SELECT * FROM silver.fra_features
            WHERE upload_id = $1 AND ha_id = $2
            """,
            upload_id,
            test_ha_id
        )

        assert fra_feature is not None


@pytest.mark.asyncio
async def test_ignores_non_features_json_file(
    integration_db_pool,
    cleanup_tables,
    setup_ha,
    test_ha_id,
    localstack_s3_config,
    localstack_s3_client,
    ensure_localstack_bucket
):
    """Test that non-features.json files are ignored."""
    upload_id = uuid.uuid4()
    
    s3_key = f"ha_id={test_ha_id}/bronze/dataset=fraew_document/ingest_date=2024-01-15/submission_id={upload_id}/extraction.json"
    
    localstack_s3_client.put_object(
        Bucket="platform-bronze",
        Key=s3_key,
        Body=json.dumps({"test": "data"}),
        ContentType="application/json"
    )
    
    event = {
        "bucket": "platform-bronze",
        "key": s3_key,
    }
    
    result = await process_features_to_silver(event)
    
    assert result["status"] == "ignored"
    assert result["reason"] == "not_features_json"


@pytest.mark.asyncio
async def test_handles_missing_features_json(
    integration_db_pool,
    cleanup_tables,
    setup_ha,
    test_ha_id,
    localstack_s3_config,
    localstack_s3_client,
    ensure_localstack_bucket
):
    """Test handling missing features.json in S3."""
    upload_id = uuid.uuid4()
    
    s3_key = f"ha_id={test_ha_id}/bronze/dataset=fraew_document/ingest_date=2024-01-15/submission_id={upload_id}/features.json"
    
    event = {
        "bucket": "platform-bronze",
        "key": s3_key,
    }
    
    os.environ["DB_HOST"] = "localhost"
    os.environ["DB_PORT"] = "5432"
    os.environ["DB_USER"] = "postgres"
    os.environ["DB_PASSWORD"] = "postgres"
    os.environ["DB_NAME"] = "platform_dev"
    
    result = await process_features_to_silver(event)
    
    assert result["status"] == "failed"
    assert result["reason"] == "failed_to_read_features"
