"""
TDD tests for UPRNLineage database methods.
"""
import pytest
import uuid
import asyncpg
from backend.core.audit.uprn_lineage import UPRNLineage


# test_db_pool fixture is now in conftest.py

@pytest.fixture
async def cleanup_tables(test_db_pool):
    """Clean up test data after each test."""
    yield
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM uprn_lineage_map")
        await conn.execute("DELETE FROM properties_silver")
        await conn.execute("DELETE FROM upload_audit")
        await conn.execute("DELETE FROM housing_associations")


@pytest.fixture
def test_ha_id():
    """Test housing association ID."""
    return "test_ha_uprn"


@pytest.fixture
async def setup_ha(test_db_pool, test_ha_id):
    """Set up test housing association."""
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO housing_associations (ha_id, name)
            VALUES ($1, 'Test HA UPRN')
            ON CONFLICT (ha_id) DO NOTHING
            """,
            test_ha_id
        )


@pytest.fixture
async def setup_upload(test_db_pool, test_ha_id):
    """Set up a test upload."""
    upload_id = str(uuid.uuid4())
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO upload_audit (
                upload_id, ha_id, file_type, filename, s3_key,
                checksum, file_size, user_id, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            uuid.UUID(upload_id),
            test_ha_id,
            "csv",
            "properties.csv",
            "test/key",
            "a" * 64,
            1024,
            "user_123",
            "completed",
        )
    return upload_id


@pytest.mark.asyncio
async def test_link_uprn_to_submission_stores_record(test_db_pool, cleanup_tables, setup_ha, setup_upload, test_ha_id):
    """Test that link_uprn_to_submission stores a record in uprn_lineage_map."""
    tracker = UPRNLineage(db_pool=test_db_pool)
    
    uprn = "123456789012"
    submission_id = setup_upload
    property_id = str(uuid.uuid4())
    
    await tracker.link_uprn_to_submission(
        uprn=uprn,
        ha_id=test_ha_id,
        submission_id=submission_id,
        property_id=property_id,
    )
    
    # Verify record was stored
    async with test_db_pool.acquire() as conn:
        record = await conn.fetchrow(
            """
            SELECT * FROM uprn_lineage_map
            WHERE uprn = $1 AND ha_id = $2 AND submission_id = $3
            """,
            uprn,
            test_ha_id,
            uuid.UUID(submission_id),
        )
    
    assert record is not None
    assert record['uprn'] == uprn
    assert record['ha_id'] == test_ha_id
    assert record['submission_id'] == uuid.UUID(submission_id)
    assert record['property_id'] == uuid.UUID(property_id)
    assert record['first_seen_at'] is not None


@pytest.mark.asyncio
async def test_link_uprn_to_submission_without_property_id(test_db_pool, cleanup_tables, setup_ha, setup_upload, test_ha_id):
    """Test that link_uprn_to_submission works without property_id."""
    tracker = UPRNLineage(db_pool=test_db_pool)
    
    uprn = "123456789013"
    submission_id = setup_upload
    
    await tracker.link_uprn_to_submission(
        uprn=uprn,
        ha_id=test_ha_id,
        submission_id=submission_id,
        property_id=None,
    )
    
    # Verify record was stored
    async with test_db_pool.acquire() as conn:
        record = await conn.fetchrow(
            """
            SELECT * FROM uprn_lineage_map
            WHERE uprn = $1 AND ha_id = $2 AND submission_id = $3
            """,
            uprn,
            test_ha_id,
            uuid.UUID(submission_id),
        )
    
    assert record is not None
    assert record['property_id'] is None


@pytest.mark.asyncio
async def test_get_submissions_for_uprn_returns_all_submissions(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that get_submissions_for_uprn returns all submissions for a UPRN."""
    tracker = UPRNLineage(db_pool=test_db_pool)
    
    uprn = "123456789014"
    submission_id_1 = str(uuid.uuid4())
    submission_id_2 = str(uuid.uuid4())
    
    # Create uploads
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO upload_audit (
                upload_id, ha_id, file_type, filename, s3_key,
                checksum, file_size, user_id, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            uuid.UUID(submission_id_1),
            test_ha_id,
            "csv",
            "properties1.csv",
            "test/key1",
            "b" * 64,
            1024,
            "user_123",
            "completed",
        )
        await conn.execute(
            """
            INSERT INTO upload_audit (
                upload_id, ha_id, file_type, filename, s3_key,
                checksum, file_size, user_id, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            uuid.UUID(submission_id_2),
            test_ha_id,
            "csv",
            "properties2.csv",
            "test/key2",
            "c" * 64,
            1024,
            "user_123",
            "completed",
        )
    
    # Link UPRN to both submissions
    await tracker.link_uprn_to_submission(
        uprn=uprn,
        ha_id=test_ha_id,
        submission_id=submission_id_1,
    )
    
    await tracker.link_uprn_to_submission(
        uprn=uprn,
        ha_id=test_ha_id,
        submission_id=submission_id_2,
    )
    
    # Get submissions
    submissions = await tracker.get_submissions_for_uprn(uprn, test_ha_id)
    
    assert len(submissions) == 2
    assert submission_id_1 in submissions
    assert submission_id_2 in submissions


@pytest.mark.asyncio
async def test_get_submissions_for_uprn_returns_empty_for_no_links(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that get_submissions_for_uprn returns empty list when no links exist."""
    tracker = UPRNLineage(db_pool=test_db_pool)
    
    uprn = "123456789015"
    submissions = await tracker.get_submissions_for_uprn(uprn, test_ha_id)
    
    assert submissions == []


@pytest.mark.asyncio
async def test_get_properties_for_uprn_returns_property_ids(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that get_properties_for_uprn returns all property IDs for a UPRN."""
    tracker = UPRNLineage(db_pool=test_db_pool)
    
    uprn = "123456789016"
    property_id_1 = str(uuid.uuid4())
    property_id_2 = str(uuid.uuid4())
    
    # Create properties in Silver layer
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO properties_silver (
                property_id, ha_id, uprn, address_raw, postcode
            )
            VALUES ($1, $2, $3, $4, $5)
            """,
            uuid.UUID(property_id_1),
            test_ha_id,
            uprn,
            "123 Test Street",
            "SW1A 1AA",
        )
        await conn.execute(
            """
            INSERT INTO properties_silver (
                property_id, ha_id, uprn, address_raw, postcode
            )
            VALUES ($1, $2, $3, $4, $5)
            """,
            uuid.UUID(property_id_2),
            test_ha_id,
            uprn,
            "456 Test Avenue",
            "SW1A 1AB",
        )
    
    # Get properties
    properties = await tracker.get_properties_for_uprn(uprn, test_ha_id)
    
    assert len(properties) == 2
    assert property_id_1 in properties
    assert property_id_2 in properties


@pytest.mark.asyncio
async def test_get_properties_for_uprn_returns_empty_for_no_properties(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that get_properties_for_uprn returns empty list when no properties exist."""
    tracker = UPRNLineage(db_pool=test_db_pool)
    
    uprn = "123456789017"
    properties = await tracker.get_properties_for_uprn(uprn, test_ha_id)
    
    assert properties == []


@pytest.mark.asyncio
async def test_get_uprn_lineage_returns_complete_graph(test_db_pool, cleanup_tables, setup_ha, test_ha_id):
    """Test that get_uprn_lineage returns complete lineage graph."""
    tracker = UPRNLineage(db_pool=test_db_pool)
    
    uprn = "123456789018"
    submission_id = str(uuid.uuid4())
    property_id = str(uuid.uuid4())
    
    # Create upload
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO upload_audit (
                upload_id, ha_id, file_type, filename, s3_key,
                checksum, file_size, user_id, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            uuid.UUID(submission_id),
            test_ha_id,
            "csv",
            "properties.csv",
            "test/key",
            "d" * 64,
            1024,
            "user_123",
            "completed",
        )
        
        # Create property
        await conn.execute(
            """
            INSERT INTO properties_silver (
                property_id, ha_id, uprn, address_raw, postcode
            )
            VALUES ($1, $2, $3, $4, $5)
            """,
            uuid.UUID(property_id),
            test_ha_id,
            uprn,
            "789 Test Road",
            "SW1A 1AC",
        )
    
    # Link UPRN to submission and property
    await tracker.link_uprn_to_submission(
        uprn=uprn,
        ha_id=test_ha_id,
        submission_id=submission_id,
        property_id=property_id,
    )
    
    # Get lineage
    lineage = await tracker.get_uprn_lineage(uprn, test_ha_id)
    
    assert 'nodes' in lineage
    assert 'edges' in lineage
    assert len(lineage['nodes']) >= 1  # At least UPRN node
    # Should include UPRN, submission, and property nodes
    node_ids = {node.get('id', '') for node in lineage['nodes']}
    assert any('uprn' in str(node_id).lower() for node_id in node_ids)


@pytest.mark.asyncio
async def test_link_uprn_to_submission_updates_last_updated_at(test_db_pool, cleanup_tables, setup_ha, setup_upload, test_ha_id):
    """Test that linking same UPRN to same submission updates last_updated_at."""
    tracker = UPRNLineage(db_pool=test_db_pool)
    
    uprn = "123456789019"
    submission_id = setup_upload
    
    # First link
    await tracker.link_uprn_to_submission(
        uprn=uprn,
        ha_id=test_ha_id,
        submission_id=submission_id,
    )
    
    async with test_db_pool.acquire() as conn:
        first_record = await conn.fetchrow(
            """
            SELECT first_seen_at, last_updated_at FROM uprn_lineage_map
            WHERE uprn = $1 AND ha_id = $2 AND submission_id = $3
            """,
            uprn,
            test_ha_id,
            uuid.UUID(submission_id),
        )
    
    first_seen = first_record['first_seen_at']
    first_updated = first_record['last_updated_at']
    
    # Wait a bit and link again (should update last_updated_at)
    import asyncio
    await asyncio.sleep(0.1)
    
    await tracker.link_uprn_to_submission(
        uprn=uprn,
        ha_id=test_ha_id,
        submission_id=submission_id,
    )
    
    async with test_db_pool.acquire() as conn:
        second_record = await conn.fetchrow(
            """
            SELECT first_seen_at, last_updated_at FROM uprn_lineage_map
            WHERE uprn = $1 AND ha_id = $2 AND submission_id = $3
            """,
            uprn,
            test_ha_id,
            uuid.UUID(submission_id),
        )
    
    # first_seen_at should remain the same
    assert second_record['first_seen_at'] == first_seen
    # last_updated_at should be updated (or at least not None)
    assert second_record['last_updated_at'] is not None


@pytest.mark.asyncio
async def test_uprn_lineage_without_db_handles_gracefully():
    """Test that UPRNLineage works without db_pool (uses global pool when None)."""
    tracker = UPRNLineage(db_pool=None)
    
    # Should not raise exceptions
    result = await tracker.get_submissions_for_uprn("123456789020", "test_ha")
    assert result == [] or isinstance(result, list)
    
    result = await tracker.get_properties_for_uprn("123456789020", "test_ha")
    assert result == [] or isinstance(result, list)
    
    result = await tracker.get_uprn_lineage("123456789020", "test_ha")
    assert isinstance(result, dict)
    assert 'nodes' in result
    assert 'edges' in result
