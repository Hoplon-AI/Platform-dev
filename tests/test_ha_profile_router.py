"""
Tests for HA profile API endpoints.
Created by: Govind 
Date Created: 01/02/2026

KAN-449: Test HA profile data retrieval, activity feed, and stats summary.
"""
import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def mock_tenant():
    """Mock tenant context with test HA ID."""
    return {"ha_id": "ha_test"}


@pytest.fixture
def mock_db_pool():
    """
    Mock database pool and connection for testing.
    
    Returns:
        Tuple of (pool, connection) mocks
    """
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool, conn


@pytest.mark.asyncio
async def test_get_ha_profile_success(mock_tenant, mock_db_pool):
    """Test successful HA profile retrieval with valid data."""
    from backend.api.v1.ha_profile_router import get_ha_profile
    
    pool, conn = mock_db_pool
    
    # Mock database responses
    conn.fetchrow.side_effect = [
        # First call: HA basic info
        {
            "ha_id": "ha_test",
            "name": "Test Housing Association",
            "created_at": datetime(2024, 1, 15, 10, 0, 0),
            "metadata": {"region": "Test Region"}
        },
        # Second call: Stats
        {
            "total_portfolios": 2,
            "total_properties": 100
        }
    ]
    # Third call: Recent uploads count
    conn.fetchval.return_value = 3
    
    with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
        result = await get_ha_profile(tenant=mock_tenant)
    
    # Assertions
    assert result["ha_id"] == "ha_test"
    assert result["name"] == "Test Housing Association"
    assert result["metadata"]["region"] == "Test Region"
    assert result["stats"]["total_portfolios"] == 2
    assert result["stats"]["total_properties"] == 100
    assert result["stats"]["recent_uploads"] == 3


@pytest.mark.asyncio
async def test_get_ha_profile_not_found(mock_tenant, mock_db_pool):
    """Test HA profile retrieval when HA doesn't exist."""
    from backend.api.v1.ha_profile_router import get_ha_profile
    from fastapi import HTTPException
    
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = None  # HA not found
    
    with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
        with pytest.raises(HTTPException) as exc_info:
            await get_ha_profile(tenant=mock_tenant)
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_ha_profile_with_null_values(mock_tenant, mock_db_pool):
    """Test HA profile retrieval handles null values correctly."""
    from backend.api.v1.ha_profile_router import get_ha_profile
    
    pool, conn = mock_db_pool
    
    conn.fetchrow.side_effect = [
        {
            "ha_id": "ha_test",
            "name": "Test HA",
            "created_at": None,
            "metadata": None
        },
        {
            "total_portfolios": None,
            "total_properties": None
        }
    ]
    conn.fetchval.return_value = None
    
    with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
        result = await get_ha_profile(tenant=mock_tenant)
    
    assert result["created_at"] is None
    assert result["metadata"] == {}
    assert result["stats"]["total_portfolios"] == 0
    assert result["stats"]["total_properties"] == 0
    assert result["stats"]["recent_uploads"] == 0


@pytest.mark.asyncio
async def test_get_ha_activity_success(mock_tenant, mock_db_pool):
    """Test successful recent activity retrieval."""
    from backend.api.v1.ha_profile_router import get_ha_activity
    
    pool, conn = mock_db_pool
    
    conn.fetch.return_value = [
        {
            "event_id": "123e4567-e89b-12d3-a456-426614174000",
            "event_type": "upload",
            "file_type": "FRAEW",
            "filename": "test.pdf",
            "actor_id": "user@test.com",
            "created_at": datetime(2024, 1, 31, 14, 30, 0),
            "status": "completed",
            "metadata": {}
        }
    ]
    
    with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
        result = await get_ha_activity(limit=10, tenant=mock_tenant)
    
    assert len(result) == 1
    assert result[0]["file_type"] == "FRAEW"
    assert result[0]["filename"] == "test.pdf"


@pytest.mark.asyncio
async def test_get_ha_activity_empty(mock_tenant, mock_db_pool):
    """Test activity retrieval when no activity exists."""
    from backend.api.v1.ha_profile_router import get_ha_activity
    
    pool, conn = mock_db_pool
    conn.fetch.return_value = []
    
    with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
        result = await get_ha_activity(limit=10, tenant=mock_tenant)
    
    assert result == []


@pytest.mark.asyncio
async def test_get_ha_activity_limit_enforced(mock_tenant, mock_db_pool):
    """Test that activity limit is enforced (max 50)."""
    from backend.api.v1.ha_profile_router import get_ha_activity
    
    pool, conn = mock_db_pool
    conn.fetch.return_value = []
    
    with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
        await get_ha_activity(limit=100, tenant=mock_tenant)
    
    # Check that the query was called with max limit of 50
    call_args = conn.fetch.call_args
    assert call_args[0][2] == 50


@pytest.mark.asyncio
async def test_get_ha_stats_summary_success(mock_tenant, mock_db_pool):
    """Test successful stats summary retrieval."""
    from backend.api.v1.ha_profile_router import get_ha_stats_summary
    
    pool, conn = mock_db_pool
    
    # Mock risk distribution
    conn.fetch.return_value = [
        {"risk_rating": "A", "count": 50},
        {"risk_rating": "B", "count": 200},
        {"risk_rating": "C", "count": 150}
    ]
    
    # Mock completeness data
    conn.fetchrow.return_value = {
        "total_properties": 400,
        "properties_with_uprn": 380,
        "properties_with_postcode": 395,
        "properties_with_geocoding": 350,
        "properties_with_risk_rating": 400
    }
    
    with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
        result = await get_ha_stats_summary(tenant=mock_tenant)
    
    # Check risk distribution
    assert len(result["risk_distribution"]) == 3
    assert result["risk_distribution"][0]["risk_rating"] == "A"
    assert result["risk_distribution"][0]["count"] == 50
    
    # Check completeness percentages
    assert result["data_completeness"]["total_properties"] == 400
    assert result["data_completeness"]["uprn_percentage"] == 95.0


@pytest.mark.asyncio
async def test_get_ha_stats_summary_no_properties(mock_tenant, mock_db_pool):
    """Test stats summary when no properties exist."""
    from backend.api.v1.ha_profile_router import get_ha_stats_summary
    
    pool, conn = mock_db_pool
    conn.fetch.return_value = []
    conn.fetchrow.return_value = {
        "total_properties": 0,
        "properties_with_uprn": 0,
        "properties_with_postcode": 0,
        "properties_with_geocoding": 0,
        "properties_with_risk_rating": 0
    }
    
    with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
        result = await get_ha_stats_summary(tenant=mock_tenant)
    
    assert result["risk_distribution"] == []
    assert result["data_completeness"]["total_properties"] == 0
    assert result["data_completeness"]["uprn_percentage"] == 0.0


def test_get_tenant_info_dev_mode():
    """Test tenant info extraction in dev mode."""
    from backend.api.v1.ha_profile_router import get_tenant_info
    
    with patch.dict(os.environ, {"DEV_MODE": "true", "DEV_HA_ID": "ha_test"}):
        tenant = get_tenant_info()
        assert tenant["ha_id"] == "ha_test"


def test_get_tenant_info_production_mode():
    """Test tenant info raises exception when not in dev mode."""
    from backend.api.v1.ha_profile_router import get_tenant_info
    from fastapi import HTTPException
    
    with patch.dict(os.environ, {"DEV_MODE": "false"}, clear=True):
        with pytest.raises(HTTPException) as exc_info:
            get_tenant_info()
        
        assert exc_info.value.status_code == 401
