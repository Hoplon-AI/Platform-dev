"""
TDD tests for AuditLogger database storage methods.
"""
import pytest
import uuid
import asyncpg
from datetime import datetime
from backend.core.audit.audit_logger import AuditLogger, AuditEventType


# test_db_pool fixture is now in conftest.py

@pytest.fixture
async def cleanup_tables(test_db_pool):
    """Clean up test data after each test."""
    yield
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM deletion_audit")
        await conn.execute("DELETE FROM output_audit")
        await conn.execute("DELETE FROM processing_audit")
        await conn.execute("DELETE FROM data_lineage")
        await conn.execute("DELETE FROM upload_audit")
        await conn.execute("DELETE FROM housing_associations")


@pytest.fixture
def test_ha_id():
    """Test housing association ID."""
    return "test_ha_001"


@pytest.fixture
async def setup_ha(test_db_pool, test_ha_id):
    """Set up test housing association."""
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO housing_associations (ha_id, name)
            VALUES ($1, 'Test HA')
            ON CONFLICT (ha_id) DO NOTHING
            """,
            test_ha_id
        )


@pytest.mark.asyncio
async def test_log_upload_stores_record(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that log_upload stores a record in upload_audit table."""
    logger = AuditLogger(db_pool=test_db_pool)
    upload_id = str(uuid.uuid4())
    user_id = "user_123"
    
    await logger.log_upload(
        upload_id=upload_id,
        ha_id=test_ha_id,
        file_type="csv",
        filename="test_properties.csv",
        s3_key=f"{test_ha_id}/bronze/{upload_id}/test_properties.csv",
        checksum="a" * 64,  # SHA-256 hex
        file_size=1024,
        user_id=user_id,
        metadata={"source": "test"},
    )
    
    # Verify record was stored
    async with test_db_pool.acquire() as conn:
        record = await conn.fetchrow(
            """
            SELECT * FROM upload_audit
            WHERE upload_id = $1
            """,
            uuid.UUID(upload_id)
        )
    
    assert record is not None
    assert record['ha_id'] == test_ha_id
    assert record['file_type'] == "csv"
    assert record['filename'] == "test_properties.csv"
    assert record['checksum'] == "a" * 64
    assert record['file_size'] == 1024
    assert record['user_id'] == user_id
    assert record['status'] == 'pending'
    assert record['metadata'] == {"source": "test"}


@pytest.mark.asyncio
async def test_log_processing_stores_record_and_lineage(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that log_processing stores record and creates lineage link."""
    logger = AuditLogger(db_pool=test_db_pool)
    processing_id = str(uuid.uuid4())
    upload_id = str(uuid.uuid4())
    property_id = str(uuid.uuid4())
    
    # First create an upload record
    await logger.log_upload(
        upload_id=upload_id,
        ha_id=test_ha_id,
        file_type="csv",
        filename="test.csv",
        s3_key="test/key",
        checksum="b" * 64,
        file_size=512,
        user_id="user_123",
    )
    
    # Log processing
    await logger.log_processing(
        processing_id=processing_id,
        ha_id=test_ha_id,
        source_type="upload",
        source_id=upload_id,
        target_type="property",
        target_id=property_id,
        transformation_type="validation",
        metadata={"rules_applied": ["required_fields", "type_check"]},
    )
    
    # Verify processing_audit record
    async with test_db_pool.acquire() as conn:
        proc_record = await conn.fetchrow(
            """
            SELECT * FROM processing_audit
            WHERE processing_id = $1
            """,
            uuid.UUID(processing_id)
        )
        
        assert proc_record is not None
        assert proc_record['ha_id'] == test_ha_id
        assert proc_record['source_type'] == "upload"
        assert proc_record['source_id'] == uuid.UUID(upload_id)
        assert proc_record['target_type'] == "property"
        assert proc_record['target_id'] == uuid.UUID(property_id)
        assert proc_record['transformation_type'] == "validation"
        assert proc_record['status'] == 'pending'
        
        # Verify lineage link was created
        lineage = await conn.fetchrow(
            """
            SELECT * FROM data_lineage
            WHERE source_type = $1 AND source_id = $2
            AND target_type = $3 AND target_id = $4
            """,
            "upload",
            uuid.UUID(upload_id),
            "property",
            uuid.UUID(property_id),
        )
    
    assert lineage is not None
    assert lineage['transformation_type'] == "validation"


@pytest.mark.asyncio
async def test_log_output_stores_record_and_lineage(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that log_output stores record and creates lineage links to sources."""
    logger = AuditLogger(db_pool=test_db_pool)
    output_id = str(uuid.uuid4())
    source_id_1 = str(uuid.uuid4())
    source_id_2 = str(uuid.uuid4())
    
    await logger.log_output(
        output_id=output_id,
        ha_id=test_ha_id,
        output_type="pdf",
        source_ids=[source_id_1, source_id_2],
        metadata={"template": "portfolio_summary", "version": "1.0"},
    )
    
    # Verify output_audit record
    async with test_db_pool.acquire() as conn:
        output_record = await conn.fetchrow(
            """
            SELECT * FROM output_audit
            WHERE output_id = $1
            """,
            uuid.UUID(output_id)
        )
        
        assert output_record is not None
        assert output_record['ha_id'] == test_ha_id
        assert output_record['output_type'] == "pdf"
        assert set(output_record['source_ids']) == {source_id_1, source_id_2}
        assert output_record['metadata'] == {"template": "portfolio_summary", "version": "1.0"}
        
        # Verify lineage links for both sources
        lineage_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM data_lineage
            WHERE target_type = 'output' AND target_id = $1
            """,
            uuid.UUID(output_id)
        )
    
    assert lineage_count == 2


@pytest.mark.asyncio
async def test_log_deletion_stores_record(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that log_deletion stores a record in deletion_audit table."""
    logger = AuditLogger(db_pool=test_db_pool)
    deletion_id = str(uuid.uuid4())
    entity_id = str(uuid.uuid4())
    deleted_by = "admin_123"
    
    await logger.log_deletion(
        deletion_id=deletion_id,
        ha_id=test_ha_id,
        deletion_type="gdpr_request",
        entity_type="property",
        entity_id=entity_id,
        deleted_by=deleted_by,
        deletion_reason="User requested data deletion",
        metadata={"deleted_fields": ["name", "email"]},
    )
    
    # Verify record was stored
    async with test_db_pool.acquire() as conn:
        record = await conn.fetchrow(
            """
            SELECT * FROM deletion_audit
            WHERE deletion_id = $1
            """,
            uuid.UUID(deletion_id)
        )
    
    assert record is not None
    assert record['ha_id'] == test_ha_id
    assert record['deletion_type'] == "gdpr_request"
    assert record['entity_type'] == "property"
    assert record['entity_id'] == entity_id
    assert record['deleted_by'] == deleted_by
    assert record['deletion_reason'] == "User requested data deletion"
    assert record['metadata'] == {"deleted_fields": ["name", "email"]}


@pytest.mark.asyncio
async def test_audit_logger_without_db_does_not_fail():
    """Test that AuditLogger methods don't fail when db_pool is None (uses global)."""
    logger = AuditLogger(db_pool=None)
    
    # Should not raise exceptions
    await logger.log_upload(
        upload_id=str(uuid.uuid4()),
        ha_id="test",
        file_type="csv",
        filename="test.csv",
        s3_key="test/key",
        checksum="a" * 64,
        file_size=100,
        user_id="user_123",
    )
    
    await logger.log_processing(
        processing_id=str(uuid.uuid4()),
        ha_id="test",
        source_type="upload",
        source_id=str(uuid.uuid4()),
        target_type="property",
        target_id=str(uuid.uuid4()),
        transformation_type="validation",
    )


@pytest.mark.asyncio
async def test_upload_audit_timestamps(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that upload_audit records have proper timestamps."""
    logger = AuditLogger(db_pool=test_db_pool)
    upload_id = str(uuid.uuid4())
    before = datetime.utcnow()
    
    await logger.log_upload(
        upload_id=upload_id,
        ha_id=test_ha_id,
        file_type="csv",
        filename="test.csv",
        s3_key="test/key",
        checksum="a" * 64,
        file_size=100,
        user_id="user_123",
    )
    
    after = datetime.utcnow()
    
    async with test_db_pool.acquire() as conn:
        record = await conn.fetchrow(
            """
            SELECT uploaded_at FROM upload_audit
            WHERE upload_id = $1
            """,
            uuid.UUID(upload_id)
        )
    
    assert record is not None
    uploaded_at = record['uploaded_at']
    assert before <= uploaded_at <= after
