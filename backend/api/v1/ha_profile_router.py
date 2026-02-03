"""
Housing Association Profile API endpoints - MVP Implementation.

KAN-449: Complete HA Profile Dashboard MVP
Created By: Govind 
Date Created: 03/02/2026
Endpoints:
- GET /api/v1/ha/profile - HA profile and summary stats
- GET /api/v1/ha/activity - Recent activity feed
- GET /api/v1/ha/properties/map - Property locations for map visualization
- GET /api/v1/ha/stats/summary - Dashboard metrics and analytics
- GET /api/v1/ha/stats/height-bands - Height distribution for properties

All endpoints are tenant-scoped by ha_id for multi-tenant security.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.database.db_pool import DatabasePool
from backend.core.tenancy.tenant_middleware import TenantMiddleware


router = APIRouter(prefix="/api/v1/ha", tags=["housing-associations"])

# JWT authentication setup
security = HTTPBearer(auto_error=False)
tenant_middleware = TenantMiddleware()


async def get_tenant_info(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Tuple[str, str]:
    """
    FastAPI dependency to extract ha_id and user_id from JWT token.

    In DEV_MODE, missing/invalid credentials fall back to defaults.
    
    Returns:
        Tuple[str, str]: (ha_id, user_id)
    
    Raises:
        HTTPException: 401 if authentication required and missing/invalid
    """
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
    dev_ha_id = os.getenv("DEV_HA_ID", "ha_demo")
    dev_user_id = os.getenv("DEV_USER_ID", "dev_user")

    if dev_mode:
        if not credentials:
            return (dev_ha_id, dev_user_id)
        try:
            return tenant_middleware.extract_tenant_from_token(credentials.credentials)
        except HTTPException:
            return (dev_ha_id, dev_user_id)

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return tenant_middleware.extract_tenant_from_token(credentials.credentials)


@router.get("/profile")
@router.get("/profile")
async def get_ha_profile(
    tenant: Tuple[str, str] = Depends(get_tenant_info)
) -> Dict[str, Any]:
    """
    Get Housing Association profile information including summary statistics.
    
    Returns:
        - HA basic information (name, created_at, metadata)
        - Summary statistics (total portfolios, properties, blocks, recent uploads)
        - Location information if available in metadata
    
    Security: Tenant-scoped by ha_id from JWT token
    
    Raises:
        HTTPException: 404 if Housing Association not found
    """
    ha_id, _user_id = tenant
    
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        # Get HA basic info
        ha = await conn.fetchrow(
            """
            SELECT ha_id, name, created_at, metadata
            FROM housing_associations
            WHERE ha_id = $1
            """,
            ha_id
        )
        
        if not ha:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Housing Association {ha_id} not found"
            )
        
        # Get portfolio, property, and block counts
        stats = await conn.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT portfolio_id) as total_portfolios,
                COUNT(DISTINCT property_id) as total_properties,
                COUNT(DISTINCT block_id) as total_blocks,
                SUM(units) as total_units
            FROM properties
            WHERE ha_id = $1
            """,
            ha_id
        )
        
        # Get recent uploads count (last 30 days)
        recent_uploads = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM upload_audit
            WHERE ha_id = $1
            AND uploaded_at >= NOW() - INTERVAL '30 days'
            """,
            ha_id
        )
        
        # Extract location from metadata if available
        # Handle both dict and string JSONB returns
        metadata = ha["metadata"]
        if metadata is None:
            metadata = {}
        elif isinstance(metadata, str):
            import json
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        
        location = metadata.get("location") if isinstance(metadata, dict) else None
        region = metadata.get("region") if isinstance(metadata, dict) else None
        
        return {
            "ha_id": ha["ha_id"],
            "name": ha["name"],
            "created_at": ha["created_at"],
            "location": location,
            "region": region,
            "metadata": metadata,
            "stats": {
                "total_portfolios": stats["total_portfolios"] or 0,
                "total_properties": stats["total_properties"] or 0,
                "total_blocks": stats["total_blocks"] or 0,
                "total_units": stats["total_units"] or 0,
                "recent_uploads": recent_uploads or 0
            }
        }

@router.get("/activity")
async def get_ha_activity(
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of activity items to return"),
    tenant: Tuple[str, str] = Depends(get_tenant_info)
) -> List[Dict[str, Any]]:
    """
    Get recent activity feed for the Housing Association.
    
    Args:
        limit: Maximum number of activity items to return (1-50, default: 10)
    
    Returns:
        List of recent activity events (uploads, processing, etc.)
        Ordered by created_at descending (newest first)
        
    Security: Tenant-scoped by ha_id from JWT token
    """
    ha_id, _user_id = tenant
    
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        activities = await conn.fetch(
            """
            SELECT *
            FROM gold.ha_recent_activity_v1
            WHERE ha_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            ha_id,
            limit
        )
        
        return [dict(activity) for activity in activities]


@router.get("/properties/map")
async def get_properties_map(
    include_risk_rating: bool = Query(default=True, description="Include risk rating in response"),
    tenant: Tuple[str, str] = Depends(get_tenant_info)
) -> Dict[str, Any]:
    """
    Get property locations for map visualization.
    
    Returns properties with UPRN, coordinates, and optional risk rating
    for rendering on an interactive map (UPRN-linked, non-valued as per wireframe).
    
    Args:
        include_risk_rating: Whether to include risk rating data (default: True)
    
    Returns:
        - type: "FeatureCollection" (GeoJSON compatible)
        - features: List of properties with coordinates and metadata
        - summary: Basic statistics about the dataset
    
    Security: Tenant-scoped by ha_id from JWT token
    """
    ha_id, _user_id = tenant
    
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        # Get properties with coordinates
        if include_risk_rating:
            query = """
                SELECT 
                    property_id,
                    uprn,
                    address,
                    postcode,
                    latitude,
                    longitude,
                    risk_rating,
                    height_m,
                    units
                FROM properties
                WHERE ha_id = $1
                AND latitude IS NOT NULL
                AND longitude IS NOT NULL
                ORDER BY property_id
            """
        else:
            query = """
                SELECT 
                    property_id,
                    uprn,
                    address,
                    postcode,
                    latitude,
                    longitude,
                    height_m,
                    units
                FROM properties
                WHERE ha_id = $1
                AND latitude IS NOT NULL
                AND longitude IS NOT NULL
                ORDER BY property_id
            """
        
        properties = await conn.fetch(query, ha_id)
        
        # Get total property count for coverage stats
        total_properties = await conn.fetchval(
            """
            SELECT COUNT(*) FROM properties WHERE ha_id = $1
            """,
            ha_id
        )
        
        # Convert to GeoJSON-like structure
        features = []
        for prop in properties:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(prop["longitude"]), float(prop["latitude"])]
                },
                "properties": {
                    "property_id": prop["property_id"],
                    "uprn": prop["uprn"],
                    "address": prop["address"],
                    "postcode": prop["postcode"],
                    "height_m": float(prop["height_m"]) if prop["height_m"] else None,
                    "units": prop["units"]
                }
            }
            
            if include_risk_rating and "risk_rating" in prop.keys():
                feature["properties"]["risk_rating"] = prop["risk_rating"]
            
            features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "summary": {
                "total_properties": total_properties or 0,
                "properties_with_coordinates": len(features),
                "coverage_percentage": round((len(features) / total_properties * 100), 1) if total_properties > 0 else 0.0
            }
        }


@router.get("/stats/summary")
async def get_ha_stats_summary(
    tenant: Tuple[str, str] = Depends(get_tenant_info)
) -> Dict[str, Any]:
    """
    Get dashboard statistics summary for the Housing Association.
    
    Returns comprehensive dashboard metrics:
        - Risk distribution by rating (A, B, C, D, E)
        - Data completeness percentages (UPRN, postcode, geocoding, risk rating)
        - Height bands distribution
        - Data quality indicators
        
    Security: Tenant-scoped by ha_id from JWT token
    """
    ha_id, _user_id = tenant
    
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        # Get risk distribution
        risk_dist = await conn.fetch(
            """
            SELECT 
                risk_rating,
                COUNT(*) as count
            FROM properties
            WHERE ha_id = $1
            AND risk_rating IS NOT NULL
            GROUP BY risk_rating
            ORDER BY risk_rating
            """,
            ha_id
        )
        
        # Get data completeness statistics
        completeness = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_properties,
                COUNT(uprn) as properties_with_uprn,
                COUNT(postcode) as properties_with_postcode,
                COUNT(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 END) as properties_with_geocoding,
                COUNT(risk_rating) as properties_with_risk_rating,
                COUNT(height_m) as properties_with_height,
                COUNT(build_year) as properties_with_build_year
            FROM properties
            WHERE ha_id = $1
            """,
            ha_id
        )
        
        total = completeness["total_properties"] or 0
        
        # Calculate data completeness percentages
        data_completeness = {
            "total_properties": total,
            "uprn_percentage": round((completeness["properties_with_uprn"] or 0) / total * 100, 1) if total > 0 else 0.0,
            "postcode_percentage": round((completeness["properties_with_postcode"] or 0) / total * 100, 1) if total > 0 else 0.0,
            "geocoding_percentage": round((completeness["properties_with_geocoding"] or 0) / total * 100, 1) if total > 0 else 0.0,
            "risk_rating_percentage": round((completeness["properties_with_risk_rating"] or 0) / total * 100, 1) if total > 0 else 0.0,
            "height_percentage": round((completeness["properties_with_height"] or 0) / total * 100, 1) if total > 0 else 0.0,
            "build_year_percentage": round((completeness["properties_with_build_year"] or 0) / total * 100, 1) if total > 0 else 0.0
        }
        
        # Calculate overall data quality score (simple average of key fields)
        key_fields_avg = (
            data_completeness["uprn_percentage"] +
            data_completeness["postcode_percentage"] +
            data_completeness["geocoding_percentage"] +
            data_completeness["risk_rating_percentage"]
        ) / 4
        
        return {
            "risk_distribution": [
                {
                    "risk_rating": row["risk_rating"],
                    "count": row["count"],
                    "percentage": round(row["count"] / total * 100, 1) if total > 0 else 0.0
                }
                for row in risk_dist
            ],
            "data_completeness": data_completeness,
            "data_quality_score": round(key_fields_avg, 1)
        }


@router.get("/stats/height-bands")
async def get_height_bands_distribution(
    tenant: Tuple[str, str] = Depends(get_tenant_info)
) -> Dict[str, Any]:
    """
    Get height bands distribution for properties.
    
    Categorizes properties into height bands as per building regulations:
        - <11m: Low rise
        - 11-18m: Medium rise
        - 18-30m: High rise
        - 30m+: High Rise Building (HRB) - requires additional safety measures
    
    Returns:
        Distribution by height band with counts and percentages
        
    Security: Tenant-scoped by ha_id from JWT token
    """
    ha_id, _user_id = tenant
    
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        # Get height band distribution
        height_bands = await conn.fetch(
            """
            SELECT 
                CASE 
                    WHEN height_m < 11 THEN '<11m'
                    WHEN height_m >= 11 AND height_m < 18 THEN '11-18m'
                    WHEN height_m >= 18 AND height_m < 30 THEN '18-30m'
                    WHEN height_m >= 30 THEN '30m+'
                    ELSE 'Unknown'
                END as height_band,
                COUNT(*) as count,
                SUM(units) as total_units
            FROM properties
            WHERE ha_id = $1
            GROUP BY 
                CASE 
                    WHEN height_m < 11 THEN '<11m'
                    WHEN height_m >= 11 AND height_m < 18 THEN '11-18m'
                    WHEN height_m >= 18 AND height_m < 30 THEN '18-30m'
                    WHEN height_m >= 30 THEN '30m+'
                    ELSE 'Unknown'
                END
            ORDER BY 
                MIN(CASE 
                    WHEN height_m < 11 THEN 1
                    WHEN height_m >= 11 AND height_m < 18 THEN 2
                    WHEN height_m >= 18 AND height_m < 30 THEN 3
                    WHEN height_m >= 30 THEN 4
                    ELSE 5
                END)
            """,
            ha_id
        )
        
        # Get total for percentage calculations
        total = await conn.fetchval(
            """
            SELECT COUNT(*) FROM properties WHERE ha_id = $1
            """,
            ha_id
        )
        
        return {
            "height_bands": [
                {
                    "height_band": row["height_band"],
                    "count": row["count"],
                    "total_units": row["total_units"] or 0,
                    "percentage": round(row["count"] / total * 100, 1) if total > 0 else 0.0
                }
                for row in height_bands
            ],
            "total_properties": total or 0
        }

@router.get("/stats/data-gaps")
async def get_data_gaps_register(
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of properties with data gaps to return"),
    tenant: Tuple[str, str] = Depends(get_tenant_info)
) -> Dict[str, Any]:
    """
    Get Risk & Data Gap Register for the Housing Association.
    
    Identifies properties with missing critical data fields to help
    prioritize data quality improvements.
    
    Args:
        limit: Maximum number of properties to return (1-500, default: 100)
    
    Returns:
        - summary: Counts of properties missing each field
        - critical_gaps: Properties missing multiple critical fields
        - properties_with_gaps: Detailed list of properties with data gaps
        
    Security: Tenant-scoped by ha_id from JWT token
    """
    ha_id, _user_id = tenant
    
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        # Get summary of data gaps
        gap_summary = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_properties,
                COUNT(*) FILTER (WHERE uprn IS NULL) as missing_uprn,
                COUNT(*) FILTER (WHERE postcode IS NULL) as missing_postcode,
                COUNT(*) FILTER (WHERE latitude IS NULL OR longitude IS NULL) as missing_geocoding,
                COUNT(*) FILTER (WHERE risk_rating IS NULL) as missing_risk_rating,
                COUNT(*) FILTER (WHERE height_m IS NULL) as missing_height,
                COUNT(*) FILTER (WHERE build_year IS NULL) as missing_build_year
            FROM properties
            WHERE ha_id = $1
            """,
            ha_id
        )
        
        # Get properties with critical data gaps (missing 2+ critical fields)
        critical_gaps = await conn.fetch(
            f"""
            SELECT 
                property_id,
                uprn,
                address,
                postcode,
                risk_rating,
                ARRAY_REMOVE(ARRAY[
                    CASE WHEN uprn IS NULL THEN 'uprn' END,
                    CASE WHEN postcode IS NULL THEN 'postcode' END,
                    CASE WHEN latitude IS NULL OR longitude IS NULL THEN 'geocoding' END,
                    CASE WHEN risk_rating IS NULL THEN 'risk_rating' END
                ], NULL) as missing_fields,
                ARRAY_LENGTH(ARRAY_REMOVE(ARRAY[
                    CASE WHEN uprn IS NULL THEN 'uprn' END,
                    CASE WHEN postcode IS NULL THEN 'postcode' END,
                    CASE WHEN latitude IS NULL OR longitude IS NULL THEN 'geocoding' END,
                    CASE WHEN risk_rating IS NULL THEN 'risk_rating' END
                ], NULL), 1) as gap_count
            FROM properties
            WHERE ha_id = $1
            AND (
                (CASE WHEN uprn IS NULL THEN 1 ELSE 0 END) +
                (CASE WHEN postcode IS NULL THEN 1 ELSE 0 END) +
                (CASE WHEN latitude IS NULL OR longitude IS NULL THEN 1 ELSE 0 END) +
                (CASE WHEN risk_rating IS NULL THEN 1 ELSE 0 END)
            ) >= 2
            ORDER BY gap_count DESC, property_id
            LIMIT $2
            """,
            ha_id,
            limit
        )
        
        return {
            "summary": {
                "total_properties": gap_summary["total_properties"] or 0,
                "missing_uprn": gap_summary["missing_uprn"] or 0,
                "missing_postcode": gap_summary["missing_postcode"] or 0,
                "missing_geocoding": gap_summary["missing_geocoding"] or 0,
                "missing_risk_rating": gap_summary["missing_risk_rating"] or 0,
                "missing_height": gap_summary["missing_height"] or 0,
                "missing_build_year": gap_summary["missing_build_year"] or 0
            },
            "critical_gaps_count": len(critical_gaps),
            "properties_with_critical_gaps": [
                {
                    "property_id": row["property_id"],
                    "uprn": row["uprn"],
                    "address": row["address"],
                    "postcode": row["postcode"],
                    "risk_rating": row["risk_rating"],
                    "missing_fields": row["missing_fields"],
                    "gap_count": row["gap_count"]
                }
                for row in critical_gaps
            ]
        }