"""
TDD tests for VersionManager database methods.
"""
import pytest
import uuid
import asyncpg
from datetime import datetime
from infrastructure.storage.version_manager import VersionManager, UploadVersion


# test_db_pool fixture is now in conftest.py

@pytest.fixture
async def cleanup_tables(test_db_pool):
    """Clean up test data after each test."""
    yield
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM upload_audit")
        await conn.execute("DELETE FROM housing_associations")


@pytest.fixture
def test_ha_id():
    """Test housing association ID."""
    return "test_ha_002"


@pytest.fixture
async def setup_ha(test_db_pool, test_ha_id):
    """Set up test housing association."""
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO housing_associations (ha_id, name)
            VALUES ($1, 'Test HA 2')
            ON CONFLICT (ha_id) DO NOTHING
            """,
            test_ha_id
        )


@pytest.mark.asyncio
async def test_create_upload_version_stores_in_db(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that create_upload_version stores record in upload_audit."""
    manager = VersionManager(db_pool=test_db_pool)
    user_id = "user_456"
    
    version = await manager.create_upload_version(
        ha_id=test_ha_id,
        file_type="csv",
        filename="properties_v1.csv",
        s3_key=f"{test_ha_id}/bronze/test/key",
        checksum="c" * 64,
        file_size=2048,
        user_id=user_id,
        metadata={"source": "manual_upload"},
    )
    
    assert version.upload_id is not None
    assert version.version == 1
    assert version.status == 'pending'
    
    # Verify stored in database
    async with test_db_pool.acquire() as conn:
        record = await conn.fetchrow(
            """
            SELECT * FROM upload_audit
            WHERE upload_id = $1
            """,
            uuid.UUID(version.upload_id)
        )
    
    assert record is not None
    assert record['ha_id'] == test_ha_id
    assert record['filename'] == "properties_v1.csv"


@pytest.mark.asyncio
async def test_get_upload_version_retrieves_record(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that get_upload_version retrieves a stored record."""
    manager = VersionManager(db_pool=test_db_pool)
    
    # Create a version
    created = await manager.create_upload_version(
        ha_id=test_ha_id,
        file_type="xlsx",
        filename="test.xlsx",
        s3_key="test/key",
        checksum="d" * 64,
        file_size=1024,
        user_id="user_789",
    )
    
    # Retrieve it
    retrieved = await manager.get_upload_version(created.upload_id)
    
    assert retrieved is not None
    assert retrieved.upload_id == created.upload_id
    assert retrieved.ha_id == test_ha_id
    assert retrieved.filename == "test.xlsx"
    assert retrieved.file_type == "xlsx"
    assert retrieved.checksum == "d" * 64
    assert retrieved.file_size == 1024


@pytest.mark.asyncio
async def test_get_upload_version_returns_none_for_missing(test_db_pool, cleanup_tables):
    """Test that get_upload_version returns None for non-existent upload."""
    manager = VersionManager(db_pool=test_db_pool)
    
    result = await manager.get_upload_version(str(uuid.uuid4()))
    
    assert result is None


@pytest.mark.asyncio
async def test_get_latest_version_returns_highest_version(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that get_latest_version returns the highest version number."""
    manager = VersionManager(db_pool=test_db_pool)
    
    # Create parent upload
    parent = await manager.create_upload_version(
        ha_id=test_ha_id,
        file_type="csv",
        filename="data.csv",
        s3_key="test/parent",
        checksum="e" * 64,
        file_size=500,
        user_id="user_1",
    )
    
    # Create version 2
    version2 = await manager.create_upload_version(
        ha_id=test_ha_id,
        file_type="csv",
        filename="data.csv",
        s3_key="test/v2",
        checksum="f" * 64,
        file_size=600,
        user_id="user_1",
        parent_upload_id=parent.upload_id,
    )
    
    # Create version 3
    version3 = await manager.create_upload_version(
        ha_id=test_ha_id,
        file_type="csv",
        filename="data.csv",
        s3_key="test/v3",
        checksum="g" * 64,
        file_size=700,
        user_id="user_1",
        parent_upload_id=parent.upload_id,
    )
    
    # Get latest version
    latest = await manager.get_latest_version(parent.upload_id)
    
    assert latest is not None
    assert latest.version == 3
    assert latest.upload_id == version3.upload_id


@pytest.mark.asyncio
async def test_get_upload_versions_filters_by_ha_id(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that get_upload_versions returns only uploads for specified HA."""
    manager = VersionManager(db_pool=test_db_pool)
    
    # Create uploads for test_ha_id
    await manager.create_upload_version(
        ha_id=test_ha_id,
        file_type="csv",
        filename="file1.csv",
        s3_key="test/1",
        checksum="h" * 64,
        file_size=100,
        user_id="user_1",
    )
    
    await manager.create_upload_version(
        ha_id=test_ha_id,
        file_type="csv",
        filename="file2.csv",
        s3_key="test/2",
        checksum="i" * 64,
        file_size=200,
        user_id="user_1",
    )
    
    # Create upload for different HA
    other_ha_id = "other_ha"
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO housing_associations (ha_id, name)
            VALUES ($1, 'Other HA')
            ON CONFLICT (ha_id) DO NOTHING
            """,
            other_ha_id
        )
    
    await manager.create_upload_version(
        ha_id=other_ha_id,
        file_type="csv",
        filename="file3.csv",
        s3_key="test/3",
        checksum="j" * 64,
        file_size=300,
        user_id="user_1",
    )
    
    # Get versions for test_ha_id
    versions = await manager.get_upload_versions(test_ha_id)
    
    assert len(versions) == 2
    assert all(v.ha_id == test_ha_id for v in versions)


@pytest.mark.asyncio
async def test_get_upload_versions_filters_by_filename(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that get_upload_versions can filter by filename."""
    manager = VersionManager(db_pool=test_db_pool)
    
    # Create uploads with different filenames
    await manager.create_upload_version(
        ha_id=test_ha_id,
        file_type="csv",
        filename="properties.csv",
        s3_key="test/1",
        checksum="k" * 64,
        file_size=100,
        user_id="user_1",
    )
    
    await manager.create_upload_version(
        ha_id=test_ha_id,
        file_type="csv",
        filename="epc_data.csv",
        s3_key="test/2",
        checksum="l" * 64,
        file_size=200,
        user_id="user_1",
    )
    
    await manager.create_upload_version(
        ha_id=test_ha_id,
        file_type="csv",
        filename="properties.csv",
        s3_key="test/3",
        checksum="m" * 64,
        file_size=300,
        user_id="user_1",
    )
    
    # Filter by filename
    versions = await manager.get_upload_versions(test_ha_id, filename="properties.csv")
    
    assert len(versions) == 2
    assert all(v.filename == "properties.csv" for v in versions)


@pytest.mark.asyncio
async def test_update_upload_status_updates_record(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that update_upload_status updates the status field."""
    manager = VersionManager(db_pool=test_db_pool)
    
    # Create upload
    version = await manager.create_upload_version(
        ha_id=test_ha_id,
        file_type="csv",
        filename="test.csv",
        s3_key="test/key",
        checksum="n" * 64,
        file_size=100,
        user_id="user_1",
    )
    
    assert version.status == 'pending'
    
    # Update status
    await manager.update_upload_status(version.upload_id, 'processing')
    
    # Verify update
    updated = await manager.get_upload_version(version.upload_id)
    assert updated.status == 'processing'
    
    # Update to completed
    await manager.update_upload_status(version.upload_id, 'completed')
    
    final = await manager.get_upload_version(version.upload_id)
    assert final.status == 'completed'


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_version_manager_without_db_creates_in_memory():
    """Test that VersionManager works without DB (uses global pool when None)."""
    # Test with None - should use GlobalDatabaseAdapter
    manager = VersionManager(db_pool=None)
    
    version = await manager.create_upload_version(
        ha_id="test_ha",
        file_type="csv",
        filename="test.csv",
        s3_key="test/key",
        checksum="o" * 64,
        file_size=100,
        user_id="user_1",
    )
    
    # Should create version object but not store in DB
    assert version is not None
    assert version.upload_id is not None
    
    # Should return None when trying to retrieve (no DB)
    retrieved = await manager.get_upload_version(version.upload_id)
    assert retrieved is None
