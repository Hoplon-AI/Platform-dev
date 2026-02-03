"""
Unit tests for Housing Association Profile API endpoints - MVP.

KAN-449: Tests for all HA Profile Dashboard MVP endpoints
Created By: Govind 
Date Created: 03/02/2026

Tests cover:
- Authentication and multi-tenant security
- Data retrieval and formatting
- Error handling (404, 401)
- Edge cases (empty data, null values)
- Query parameters validation
"""

import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

# IMPORTANT: Update these imports to match YOUR project structure
# If your router file is at backend/routers/ha_profile_router.py, use:
from backend.api.v1.ha_profile_router import (
    get_ha_profile,
    get_ha_activity,
    get_properties_map,
    get_ha_stats_summary,
    get_height_bands_distribution,
    get_data_gaps_register,
    get_tenant_info
)

# If the module path is different, adjust accordingly. For example:
# from routers.ha_profile_router import ...
# from backend.api.routers.ha_profile_router import ...


# Mock data fixtures
@pytest.fixture
def mock_ha_data():
    """Mock housing association data."""
    return {
        "ha_id": "ha_test_123",
        "name": "Test Housing Association",
        "created_at": datetime(2024, 1, 1, 10, 0, 0),
        "metadata": {"location": "Edinburgh", "region": "Scotland"}
    }


@pytest.fixture
def mock_property_data():
    """Mock property data."""
    return [
        {
            "property_id": "prop_001",
            "uprn": "100000000001",
            "address": "1 Test Street",
            "postcode": "SW1A 1AA",
            "latitude": 51.501,
            "longitude": -0.1416,
            "risk_rating": "C",
            "height_m": 18.5,
            "units": 1
        },
        {
            "property_id": "prop_002",
            "uprn": "100000000002",
            "address": "2 Demo Road",
            "postcode": "EH1 1AA",
            "latitude": 55.9533,
            "longitude": -3.1883,
            "risk_rating": "D",
            "height_m": 9.2,
            "units": 1
        }
    ]


@pytest.fixture
def mock_db_pool():
    """Mock DatabasePool for testing."""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    pool.acquire.return_value.__aexit__.return_value = None
    return pool, conn


class TestGetTenantInfo:
    """Tests for JWT authentication dependency."""
    
    @pytest.mark.asyncio
    async def test_dev_mode_no_credentials(self):
        """Test DEV_MODE allows missing credentials."""
        with patch.dict(os.environ, {"DEV_MODE": "true", "DEV_HA_ID": "ha_dev", "DEV_USER_ID": "dev_user"}):
            ha_id, user_id = await get_tenant_info(credentials=None)
            assert ha_id == "ha_dev"
            assert user_id == "dev_user"
    
    @pytest.mark.asyncio
    async def test_dev_mode_with_valid_token(self):
        """Test DEV_MODE uses token if provided and valid."""
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid_token"
        
        with patch.dict(os.environ, {"DEV_MODE": "true"}):
            # Update this path to match your tenant_middleware location
            with patch("backend.api.v1.ha_profile_router.tenant_middleware.extract_tenant_from_token") as mock_extract:
                mock_extract.return_value = ("ha_from_token", "user_from_token")
                
                ha_id, user_id = await get_tenant_info(credentials=mock_credentials)
                assert ha_id == "ha_from_token"
                assert user_id == "user_from_token"
    
    @pytest.mark.asyncio
    async def test_dev_mode_with_invalid_token_falls_back(self):
        """Test DEV_MODE falls back to defaults if token invalid."""
        mock_credentials = MagicMock()
        mock_credentials.credentials = "invalid_token"
        
        with patch.dict(os.environ, {"DEV_MODE": "true", "DEV_HA_ID": "ha_dev", "DEV_USER_ID": "dev_user"}):
            with patch("backend.api.v1.ha_profile_router.tenant_middleware.extract_tenant_from_token") as mock_extract:
                mock_extract.side_effect = HTTPException(status_code=401, detail="Invalid token")
                
                ha_id, user_id = await get_tenant_info(credentials=mock_credentials)
                assert ha_id == "ha_dev"
                assert user_id == "dev_user"
    
    @pytest.mark.asyncio
    async def test_production_mode_no_credentials_raises_401(self):
        """Test production mode requires credentials."""
        with patch.dict(os.environ, {"DEV_MODE": "false"}):
            with pytest.raises(HTTPException) as exc_info:
                await get_tenant_info(credentials=None)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Authentication required" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_production_mode_with_valid_token(self):
        """Test production mode extracts tenant from valid token."""
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid_token"
        
        with patch.dict(os.environ, {"DEV_MODE": "false"}):
            with patch("backend.api.v1.ha_profile_router.tenant_middleware.extract_tenant_from_token") as mock_extract:
                mock_extract.return_value = ("ha_prod", "user_prod")
                
                ha_id, user_id = await get_tenant_info(credentials=mock_credentials)
                assert ha_id == "ha_prod"
                assert user_id == "user_prod"


class TestGetHAProfile:
    """Tests for GET /api/v1/ha/profile endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_ha_profile_success(self, mock_ha_data, mock_db_pool):
        """Test successful HA profile retrieval."""
        pool, conn = mock_db_pool
        
        # Mock database responses
        conn.fetchrow.side_effect = [
            mock_ha_data,  # HA basic info
            {"total_portfolios": 5, "total_properties": 8420, "total_blocks": 247, "total_units": 9000}  # Stats
        ]
        conn.fetchval.return_value = 3  # Recent uploads
        
        # Update this path to match your DatabasePool location
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_ha_profile(tenant=("ha_test_123", "user_123"))
        
        assert result["ha_id"] == "ha_test_123"
        assert result["name"] == "Test Housing Association"
        assert result["location"] == "Edinburgh"
        assert result["region"] == "Scotland"
        assert result["stats"]["total_portfolios"] == 5
        assert result["stats"]["total_properties"] == 8420
        assert result["stats"]["total_blocks"] == 247
        assert result["stats"]["total_units"] == 9000
        assert result["stats"]["recent_uploads"] == 3
    
    @pytest.mark.asyncio
    async def test_get_ha_profile_not_found(self, mock_db_pool):
        """Test 404 when HA not found."""
        pool, conn = mock_db_pool
        conn.fetchrow.return_value = None  # HA not found
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            with pytest.raises(HTTPException) as exc_info:
                await get_ha_profile(tenant=("ha_nonexistent", "user_123"))
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_get_ha_profile_with_null_metadata(self, mock_db_pool):
        """Test handling of null metadata."""
        pool, conn = mock_db_pool
        
        ha_data_no_metadata = {
            "ha_id": "ha_test_123",
            "name": "Test Housing Association",
            "created_at": datetime(2024, 1, 1, 10, 0, 0),
            "metadata": None
        }
        
        conn.fetchrow.side_effect = [
            ha_data_no_metadata,
            {"total_portfolios": 5, "total_properties": 8420, "total_blocks": 247, "total_units": 9000}
        ]
        conn.fetchval.return_value = 3
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_ha_profile(tenant=("ha_test_123", "user_123"))
        
        assert result["location"] is None
        assert result["region"] is None
        assert result["metadata"] == {}


class TestGetHAActivity:
    """Tests for GET /api/v1/ha/activity endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_ha_activity_success(self, mock_db_pool):
        """Test successful activity feed retrieval."""
        pool, conn = mock_db_pool
        
        mock_activities = [
            {"activity_id": "act_001", "activity_type": "upload", "created_at": datetime.now()},
            {"activity_id": "act_002", "activity_type": "processing", "created_at": datetime.now() - timedelta(hours=1)}
        ]
        conn.fetch.return_value = mock_activities
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_ha_activity(limit=10, tenant=("ha_test_123", "user_123"))
        
        assert len(result) == 2
        assert result[0]["activity_id"] == "act_001"
        assert result[1]["activity_id"] == "act_002"
    
    @pytest.mark.asyncio
    async def test_get_ha_activity_empty(self, mock_db_pool):
        """Test empty activity feed."""
        pool, conn = mock_db_pool
        conn.fetch.return_value = []
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_ha_activity(limit=10, tenant=("ha_test_123", "user_123"))
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_ha_activity_respects_limit(self, mock_db_pool):
        """Test limit parameter is enforced."""
        pool, conn = mock_db_pool
        conn.fetch.return_value = [{"activity_id": f"act_{i}"} for i in range(5)]
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_ha_activity(limit=5, tenant=("ha_test_123", "user_123"))
        
        # Verify SQL was called with correct limit
        conn.fetch.assert_called_once()
        call_args = conn.fetch.call_args[0]
        assert call_args[2] == 5  # limit parameter


class TestGetPropertiesMap:
    """Tests for GET /api/v1/ha/properties/map endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_properties_map_success(self, mock_property_data, mock_db_pool):
        """Test successful property map data retrieval."""
        pool, conn = mock_db_pool
        
        conn.fetch.return_value = mock_property_data
        conn.fetchval.return_value = 8420  # Total properties
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_properties_map(include_risk_rating=True, tenant=("ha_test_123", "user_123"))
        
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 2
        
        # Check first feature
        feature1 = result["features"][0]
        assert feature1["type"] == "Feature"
        assert feature1["geometry"]["type"] == "Point"
        assert feature1["geometry"]["coordinates"] == [-0.1416, 51.501]
        assert feature1["properties"]["property_id"] == "prop_001"
        assert feature1["properties"]["uprn"] == "100000000001"
        assert feature1["properties"]["risk_rating"] == "C"
        
        # Check summary
        assert result["summary"]["total_properties"] == 8420
        assert result["summary"]["properties_with_coordinates"] == 2
        assert result["summary"]["coverage_percentage"] == 0.0  # 2/8420 rounds to 0
    
    @pytest.mark.asyncio
    async def test_get_properties_map_without_risk_rating(self, mock_db_pool):
        """Test property map without risk rating."""
        pool, conn = mock_db_pool
        
        property_data_no_risk = [
            {
                "property_id": "prop_001",
                "uprn": "100000000001",
                "address": "1 Test Street",
                "postcode": "SW1A 1AA",
                "latitude": 51.501,
                "longitude": -0.1416,
                "height_m": 18.5,
                "units": 1
            }
        ]
        conn.fetch.return_value = property_data_no_risk
        conn.fetchval.return_value = 100
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_properties_map(include_risk_rating=False, tenant=("ha_test_123", "user_123"))
        
        # Risk rating should not be in properties
        assert "risk_rating" not in result["features"][0]["properties"]
    
    @pytest.mark.asyncio
    async def test_get_properties_map_empty(self, mock_db_pool):
        """Test empty property map."""
        pool, conn = mock_db_pool
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_properties_map(include_risk_rating=True, tenant=("ha_test_123", "user_123"))
        
        assert result["features"] == []
        assert result["summary"]["properties_with_coordinates"] == 0


class TestGetHAStatsSummary:
    """Tests for GET /api/v1/ha/stats/summary endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_stats_summary_success(self, mock_db_pool):
        """Test successful stats summary retrieval."""
        pool, conn = mock_db_pool
        
        mock_risk_dist = [
            {"risk_rating": "A", "count": 1000},
            {"risk_rating": "B", "count": 2500},
            {"risk_rating": "C", "count": 3000},
            {"risk_rating": "D", "count": 1500},
            {"risk_rating": "E", "count": 420}
        ]
        
        mock_completeness = {
            "total_properties": 8420,
            "properties_with_uprn": 8083,
            "properties_with_postcode": 8295,
            "properties_with_geocoding": 8016,
            "properties_with_risk_rating": 8420,
            "properties_with_height": 7500,
            "properties_with_build_year": 8000
        }
        
        conn.fetch.return_value = mock_risk_dist
        conn.fetchrow.return_value = mock_completeness
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_ha_stats_summary(tenant=("ha_test_123", "user_123"))
        
        # Check risk distribution
        assert len(result["risk_distribution"]) == 5
        assert result["risk_distribution"][0]["risk_rating"] == "A"
        assert result["risk_distribution"][0]["count"] == 1000
        assert result["risk_distribution"][0]["percentage"] == 11.9  # 1000/8420
        
        # Check data completeness
        assert result["data_completeness"]["total_properties"] == 8420
        assert result["data_completeness"]["uprn_percentage"] == 96.0
        assert result["data_completeness"]["postcode_percentage"] == 98.5
        assert result["data_completeness"]["geocoding_percentage"] == 95.2
        assert result["data_completeness"]["risk_rating_percentage"] == 100.0
        
        # Check data quality score
        assert "data_quality_score" in result
        assert result["data_quality_score"] > 0
    
    @pytest.mark.asyncio
    async def test_get_stats_summary_no_properties(self, mock_db_pool):
        """Test stats summary with no properties."""
        pool, conn = mock_db_pool
        
        conn.fetch.return_value = []
        conn.fetchrow.return_value = {
            "total_properties": 0,
            "properties_with_uprn": 0,
            "properties_with_postcode": 0,
            "properties_with_geocoding": 0,
            "properties_with_risk_rating": 0,
            "properties_with_height": 0,
            "properties_with_build_year": 0
        }
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_ha_stats_summary(tenant=("ha_test_123", "user_123"))
        
        assert result["risk_distribution"] == []
        assert result["data_completeness"]["total_properties"] == 0
        assert result["data_completeness"]["uprn_percentage"] == 0.0


class TestGetHeightBandsDistribution:
    """Tests for GET /api/v1/ha/stats/height-bands endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_height_bands_success(self, mock_db_pool):
        """Test successful height bands distribution retrieval."""
        pool, conn = mock_db_pool
        
        mock_height_bands = [
            {"height_band": "<11m", "count": 2100, "total_units": 2100},
            {"height_band": "11-18m", "count": 2100, "total_units": 2500},
            {"height_band": "18-30m", "count": 1680, "total_units": 2000},
            {"height_band": "30m+", "count": 2520, "total_units": 3200}
        ]
        
        conn.fetch.return_value = mock_height_bands
        conn.fetchval.return_value = 8400
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_height_bands_distribution(tenant=("ha_test_123", "user_123"))
        
        assert len(result["height_bands"]) == 4
        assert result["height_bands"][0]["height_band"] == "<11m"
        assert result["height_bands"][0]["count"] == 2100
        assert result["height_bands"][0]["percentage"] == 25.0
        assert result["total_properties"] == 8400
    
    @pytest.mark.asyncio
    async def test_get_height_bands_empty(self, mock_db_pool):
        """Test empty height bands distribution."""
        pool, conn = mock_db_pool
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_height_bands_distribution(tenant=("ha_test_123", "user_123"))
        
        assert result["height_bands"] == []
        assert result["total_properties"] == 0


class TestGetDataGapsRegister:
    """Tests for GET /api/v1/ha/stats/data-gaps endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_data_gaps_success(self, mock_db_pool):
        """Test successful data gaps register retrieval."""
        pool, conn = mock_db_pool
        
        mock_summary = {
            "total_properties": 8420,
            "missing_uprn": 337,
            "missing_postcode": 125,
            "missing_geocoding": 404,
            "missing_risk_rating": 0,
            "missing_height": 920,
            "missing_build_year": 420
        }
        
        mock_critical_gaps = [
            {
                "property_id": "prop_001",
                "uprn": None,
                "address": "1 Test Street",
                "postcode": None,
                "risk_rating": None,
                "missing_fields": ["uprn", "postcode", "risk_rating"],
                "gap_count": 3
            },
            {
                "property_id": "prop_002",
                "uprn": "100000000002",
                "address": "2 Demo Road",
                "postcode": None,
                "risk_rating": None,
                "missing_fields": ["postcode", "risk_rating"],
                "gap_count": 2
            }
        ]
        
        conn.fetchrow.return_value = mock_summary
        conn.fetch.return_value = mock_critical_gaps
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_data_gaps_register(limit=100, tenant=("ha_test_123", "user_123"))
        
        # Check summary
        assert result["summary"]["total_properties"] == 8420
        assert result["summary"]["missing_uprn"] == 337
        assert result["summary"]["missing_postcode"] == 125
        
        # Check critical gaps
        assert result["critical_gaps_count"] == 2
        assert len(result["properties_with_critical_gaps"]) == 2
        assert result["properties_with_critical_gaps"][0]["gap_count"] == 3
        assert "uprn" in result["properties_with_critical_gaps"][0]["missing_fields"]
    
    @pytest.mark.asyncio
    async def test_get_data_gaps_no_gaps(self, mock_db_pool):
        """Test data gaps with perfect data quality."""
        pool, conn = mock_db_pool
        
        mock_summary = {
            "total_properties": 8420,
            "missing_uprn": 0,
            "missing_postcode": 0,
            "missing_geocoding": 0,
            "missing_risk_rating": 0,
            "missing_height": 0,
            "missing_build_year": 0
        }
        
        conn.fetchrow.return_value = mock_summary
        conn.fetch.return_value = []
        
        with patch("backend.api.v1.ha_profile_router.DatabasePool.get_pool", return_value=pool):
            result = await get_data_gaps_register(limit=100, tenant=("ha_test_123", "user_123"))
        
        assert result["critical_gaps_count"] == 0
        assert result["properties_with_critical_gaps"] == []