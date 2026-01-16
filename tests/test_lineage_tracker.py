"""
TDD tests for LineageTracker database methods.
"""
import pytest
import uuid
import asyncpg
from backend.core.audit.lineage_tracker import LineageTracker


# test_db_pool fixture is now in conftest.py

@pytest.fixture
async def cleanup_tables(test_db_pool):
    """Clean up test data after each test."""
    yield
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM data_lineage")
        await conn.execute("DELETE FROM upload_audit")
        await conn.execute("DELETE FROM housing_associations")


@pytest.fixture
def test_ha_id():
    """Test housing association ID."""
    return "test_ha_lineage"


@pytest.fixture
async def setup_ha(test_db_pool, test_ha_id):
    """Set up test housing association."""
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO housing_associations (ha_id, name)
            VALUES ($1, 'Test HA Lineage')
            ON CONFLICT (ha_id) DO NOTHING
            """,
            test_ha_id
        )


@pytest.mark.asyncio
async def test_create_lineage_link_stores_record(test_db_pool, cleanup_tables, setup_ha):
    """Test that create_lineage_link stores a record in data_lineage table."""
    tracker = LineageTracker(db_pool=test_db_pool)
    
    upload_id = str(uuid.uuid4())
    property_id = str(uuid.uuid4())
    
    await tracker.create_lineage_link(
        source_type="upload",
        source_id=upload_id,
        target_type="property",
        target_id=property_id,
        transformation_type="validation",
    )
    
    # Verify record was stored
    async with test_db_pool.acquire() as conn:
        record = await conn.fetchrow(
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
    
    assert record is not None
    assert record['source_type'] == "upload"
    assert record['source_id'] == uuid.UUID(upload_id)
    assert record['target_type'] == "property"
    assert record['target_id'] == uuid.UUID(property_id)
    assert record['transformation_type'] == "validation"


@pytest.mark.asyncio
async def test_get_lineage_forward_returns_targets(test_db_pool, cleanup_tables, setup_ha):
    """Test that get_lineage_forward returns entities created from source."""
    tracker = LineageTracker(db_pool=test_db_pool)
    
    upload_id = str(uuid.uuid4())
    property_id_1 = str(uuid.uuid4())
    property_id_2 = str(uuid.uuid4())
    
    # Create forward links
    await tracker.create_lineage_link(
        source_type="upload",
        source_id=upload_id,
        target_type="property",
        target_id=property_id_1,
        transformation_type="validation",
    )
    
    await tracker.create_lineage_link(
        source_type="upload",
        source_id=upload_id,
        target_type="property",
        target_id=property_id_2,
        transformation_type="validation",
    )
    
    # Get forward lineage
    forward_links = await tracker.get_lineage_forward("upload", upload_id)
    
    assert len(forward_links) == 2
    target_ids = {link['target_id'] for link in forward_links}
    assert property_id_1 in target_ids
    assert property_id_2 in target_ids
    assert all(link['source_type'] == "upload" for link in forward_links)
    assert all(link['source_id'] == upload_id for link in forward_links)


@pytest.mark.asyncio
async def test_get_lineage_backward_returns_sources(test_db_pool, cleanup_tables, setup_ha):
    """Test that get_lineage_backward returns entities that created the target."""
    tracker = LineageTracker(db_pool=test_db_pool)
    
    upload_id_1 = str(uuid.uuid4())
    upload_id_2 = str(uuid.uuid4())
    property_id = str(uuid.uuid4())
    
    # Create backward links (property created from multiple uploads)
    await tracker.create_lineage_link(
        source_type="upload",
        source_id=upload_id_1,
        target_type="property",
        target_id=property_id,
        transformation_type="validation",
    )
    
    await tracker.create_lineage_link(
        source_type="upload",
        source_id=upload_id_2,
        target_type="property",
        target_id=property_id,
        transformation_type="validation",
    )
    
    # Get backward lineage
    backward_links = await tracker.get_lineage_backward("property", property_id)
    
    assert len(backward_links) == 2
    source_ids = {link['source_id'] for link in backward_links}
    assert upload_id_1 in source_ids
    assert upload_id_2 in source_ids
    assert all(link['target_type'] == "property" for link in backward_links)
    assert all(link['target_id'] == property_id for link in backward_links)


@pytest.mark.asyncio
async def test_get_full_lineage_returns_graph(test_db_pool, cleanup_tables, setup_ha):
    """Test that get_full_lineage returns both forward and backward lineage."""
    tracker = LineageTracker(db_pool=test_db_pool)
    
    upload_id = str(uuid.uuid4())
    property_id = str(uuid.uuid4())
    rating_id = str(uuid.uuid4())
    
    # Create a chain: upload -> property -> rating
    await tracker.create_lineage_link(
        source_type="upload",
        source_id=upload_id,
        target_type="property",
        target_id=property_id,
        transformation_type="validation",
    )
    
    await tracker.create_lineage_link(
        source_type="property",
        source_id=property_id,
        target_type="rating",
        target_id=rating_id,
        transformation_type="calculation",
    )
    
    # Get full lineage from property (should include both upload and rating)
    full_lineage = await tracker.get_full_lineage("property", property_id, max_depth=10)
    
    assert 'nodes' in full_lineage
    assert 'edges' in full_lineage
    assert len(full_lineage['nodes']) >= 3  # upload, property, rating
    assert len(full_lineage['edges']) >= 2  # upload->property, property->rating
    
    # Verify nodes contain the entities
    node_ids = {node['id'] for node in full_lineage['nodes']}
    assert upload_id in node_ids or any(upload_id in str(n.get('id', '')) for n in full_lineage['nodes'])
    assert property_id in node_ids or any(property_id in str(n.get('id', '')) for n in full_lineage['nodes'])
    assert rating_id in node_ids or any(rating_id in str(n.get('id', '')) for n in full_lineage['nodes'])


@pytest.mark.asyncio
async def test_get_lineage_forward_handles_multiple_transformations(test_db_pool, cleanup_tables, setup_ha):
    """Test that get_lineage_forward handles multiple transformation types."""
    tracker = LineageTracker(db_pool=test_db_pool)
    
    upload_id = str(uuid.uuid4())
    property_id = str(uuid.uuid4())
    block_id = str(uuid.uuid4())
    
    # Create multiple forward links with different transformations
    await tracker.create_lineage_link(
        source_type="upload",
        source_id=upload_id,
        target_type="property",
        target_id=property_id,
        transformation_type="validation",
    )
    
    await tracker.create_lineage_link(
        source_type="upload",
        source_id=upload_id,
        target_type="block",
        target_id=block_id,
        transformation_type="grouping",
    )
    
    forward_links = await tracker.get_lineage_forward("upload", upload_id)
    
    assert len(forward_links) == 2
    transformation_types = {link['transformation_type'] for link in forward_links}
    assert "validation" in transformation_types
    assert "grouping" in transformation_types


@pytest.mark.asyncio
async def test_get_lineage_forward_returns_empty_for_no_links(test_db_pool, cleanup_tables, setup_ha):
    """Test that get_lineage_forward returns empty list when no links exist."""
    tracker = LineageTracker(db_pool=test_db_pool)
    
    entity_id = str(uuid.uuid4())
    forward_links = await tracker.get_lineage_forward("upload", entity_id)
    
    assert forward_links == []


@pytest.mark.asyncio
async def test_get_lineage_backward_returns_empty_for_no_links(test_db_pool, cleanup_tables, setup_ha):
    """Test that get_lineage_backward returns empty list when no links exist."""
    tracker = LineageTracker(db_pool=test_db_pool)
    
    entity_id = str(uuid.uuid4())
    backward_links = await tracker.get_lineage_backward("property", entity_id)
    
    assert backward_links == []


@pytest.mark.asyncio
async def test_get_full_lineage_respects_max_depth(test_db_pool, cleanup_tables, setup_ha):
    """Test that get_full_lineage respects max_depth parameter."""
    tracker = LineageTracker(db_pool=test_db_pool)
    
    # Create a long chain
    ids = [str(uuid.uuid4()) for _ in range(5)]
    types = ["upload", "property", "block", "rating", "output"]
    
    for i in range(len(ids) - 1):
        await tracker.create_lineage_link(
            source_type=types[i],
            source_id=ids[i],
            target_type=types[i + 1],
            target_id=ids[i + 1],
            transformation_type="transformation",
        )
    
    # Get lineage with max_depth=2
    full_lineage = await tracker.get_full_lineage(types[1], ids[1], max_depth=2)
    
    # Should limit depth to 2 levels
    assert len(full_lineage['nodes']) <= 3  # Current + 2 levels
    assert len(full_lineage['edges']) <= 2


@pytest.mark.asyncio
async def test_lineage_tracker_without_db_handles_gracefully():
    """Test that LineageTracker works without db_pool (uses global pool when None)."""
    tracker = LineageTracker(db_pool=None)
    
    # Should not raise exceptions
    result = await tracker.get_lineage_forward("upload", str(uuid.uuid4()))
    assert result == [] or isinstance(result, list)
    
    result = await tracker.get_lineage_backward("property", str(uuid.uuid4()))
    assert result == [] or isinstance(result, list)
    
    result = await tracker.get_full_lineage("property", str(uuid.uuid4()))
    assert isinstance(result, dict)
    assert 'nodes' in result
    assert 'edges' in result
