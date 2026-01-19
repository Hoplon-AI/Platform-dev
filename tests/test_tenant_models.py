"""
TDD tests for TenantModels.
"""
import pytest
import asyncpg
from datetime import datetime
from backend.core.tenancy.tenant_models import TenantModels, HousingAssociation


# test_db_pool fixture is now in conftest.py

@pytest.fixture
async def cleanup_tables(test_db_pool):
    """Clean up test tables before and after each test."""
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM housing_associations")
    yield
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM housing_associations")


@pytest.fixture
def tenant_models(test_db_pool):
    """Create TenantModels instance with test database pool."""
    return TenantModels(db_pool=test_db_pool)


@pytest.mark.asyncio
async def test_get_housing_association_returns_none_when_not_found(
    tenant_models, cleanup_tables
):
    """Test that get_housing_association returns None for non-existent HA."""
    result = await tenant_models.get_housing_association("nonexistent_ha")
    
    assert result is None


@pytest.mark.asyncio
async def test_get_housing_association_returns_ha_when_exists(
    tenant_models, cleanup_tables, test_db_pool
):
    """Test that get_housing_association returns HA when it exists."""
    # Create HA in database
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO housing_associations (ha_id, name, created_at)
            VALUES ($1, $2, $3)
            """,
            "test_ha_001",
            "Test Housing Association",
            datetime.utcnow(),
        )
    
    # Retrieve it
    ha = await tenant_models.get_housing_association("test_ha_001")
    
    assert ha is not None
    assert ha.ha_id == "test_ha_001"
    assert ha.name == "Test Housing Association"
    assert isinstance(ha.created_at, datetime)


@pytest.mark.asyncio
async def test_get_housing_association_parses_metadata_json(
    tenant_models, cleanup_tables, test_db_pool
):
    """Test that get_housing_association correctly parses JSON metadata."""
    metadata = {"key1": "value1", "key2": 123}
    metadata_json = '{"key1": "value1", "key2": 123}'
    
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO housing_associations (ha_id, name, created_at, metadata)
            VALUES ($1, $2, $3, $4::jsonb)
            """,
            "test_ha_002",
            "Test HA with Metadata",
            datetime.utcnow(),
            metadata_json,
        )
    
    ha = await tenant_models.get_housing_association("test_ha_002")
    
    assert ha is not None
    assert ha.metadata == metadata


@pytest.mark.asyncio
async def test_create_housing_association_stores_in_database(
    tenant_models, cleanup_tables, test_db_pool
):
    """Test that create_housing_association stores HA in database."""
    ha = await tenant_models.create_housing_association(
        ha_id="test_ha_003",
        name="New Housing Association",
        metadata={"test": "data"},
    )
    
    assert ha.ha_id == "test_ha_003"
    assert ha.name == "New Housing Association"
    assert ha.metadata == {"test": "data"}
    assert isinstance(ha.created_at, datetime)
    
    # Verify it was stored in database
    async with test_db_pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT ha_id, name, metadata FROM housing_associations WHERE ha_id = $1",
            "test_ha_003",
        )
        
        assert record is not None
        assert record['ha_id'] == "test_ha_003"
        assert record['name'] == "New Housing Association"


@pytest.mark.asyncio
async def test_create_housing_association_raises_on_duplicate(
    tenant_models, cleanup_tables, test_db_pool
):
    """Test that create_housing_association raises ValueError on duplicate ha_id."""
    # Create first HA
    await tenant_models.create_housing_association(
        ha_id="duplicate_ha",
        name="First HA",
    )
    
    # Try to create duplicate
    with pytest.raises(ValueError, match="already exists"):
        await tenant_models.create_housing_association(
            ha_id="duplicate_ha",
            name="Second HA",
        )


@pytest.mark.asyncio
async def test_create_housing_association_without_metadata(
    tenant_models, cleanup_tables, test_db_pool
):
    """Test that create_housing_association works without metadata."""
    ha = await tenant_models.create_housing_association(
        ha_id="test_ha_004",
        name="HA Without Metadata",
    )
    
    assert ha.metadata is None
    
    # Verify in database
    async with test_db_pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT metadata FROM housing_associations WHERE ha_id = $1",
            "test_ha_004",
        )
        
        assert record['metadata'] is None


@pytest.mark.asyncio
async def test_list_housing_associations_returns_empty_list_when_none(
    tenant_models, cleanup_tables
):
    """Test that list_housing_associations returns empty list when no HAs exist."""
    result = await tenant_models.list_housing_associations()
    
    assert result == []


@pytest.mark.asyncio
async def test_list_housing_associations_returns_all_housing_associations(
    tenant_models, cleanup_tables, test_db_pool
):
    """Test that list_housing_associations returns all HAs."""
    # Create multiple HAs
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO housing_associations (ha_id, name, created_at)
            VALUES 
                ('ha_001', 'First HA', $1),
                ('ha_002', 'Second HA', $2),
                ('ha_003', 'Third HA', $3)
            """,
            datetime.utcnow(),
            datetime.utcnow(),
            datetime.utcnow(),
        )
    
    result = await tenant_models.list_housing_associations()
    
    assert len(result) == 3
    ha_ids = {ha.ha_id for ha in result}
    assert ha_ids == {"ha_001", "ha_002", "ha_003"}


@pytest.mark.asyncio
async def test_list_housing_associations_ordered_by_created_at(
    tenant_models, cleanup_tables, test_db_pool
):
    """Test that list_housing_associations returns HAs ordered by created_at."""
    import time
    
    # Create HAs with different timestamps
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO housing_associations (ha_id, name, created_at) VALUES ($1, $2, $3)",
            "ha_old", "Old HA", datetime(2024, 1, 1, 10, 0, 0),
        )
        await conn.execute(
            "INSERT INTO housing_associations (ha_id, name, created_at) VALUES ($1, $2, $3)",
            "ha_new", "New HA", datetime(2024, 1, 1, 12, 0, 0),
        )
        await conn.execute(
            "INSERT INTO housing_associations (ha_id, name, created_at) VALUES ($1, $2, $3)",
            "ha_middle", "Middle HA", datetime(2024, 1, 1, 11, 0, 0),
        )
    
    result = await tenant_models.list_housing_associations()
    
    assert len(result) == 3
    assert result[0].ha_id == "ha_old"
    assert result[1].ha_id == "ha_middle"
    assert result[2].ha_id == "ha_new"


@pytest.mark.asyncio
async def test_list_housing_associations_parses_metadata(
    tenant_models, cleanup_tables, test_db_pool
):
    """Test that list_housing_associations correctly parses metadata for all HAs."""
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO housing_associations (ha_id, name, created_at, metadata)
            VALUES ($1, $2, $3, $4::jsonb)
            """,
            "ha_with_meta",
            "HA with Metadata",
            datetime.utcnow(),
            '{"key": "value", "number": 42}',
        )
    
    result = await tenant_models.list_housing_associations()
    
    assert len(result) == 1
    assert result[0].metadata == {"key": "value", "number": 42}


@pytest.mark.asyncio
async def test_tenant_models_works_without_db_pool():
    """Test that TenantModels methods handle missing database gracefully."""
    tenant_models = TenantModels(db_pool=None)
    
    # Should return None/empty without raising
    ha = await tenant_models.get_housing_association("test")
    assert ha is None
    
    result = await tenant_models.list_housing_associations()
    assert result == []
    
    # Create should still return object but not store in DB
    ha = await tenant_models.create_housing_association(
        ha_id="test",
        name="Test",
    )
    assert ha.ha_id == "test"
    assert ha.name == "Test"
