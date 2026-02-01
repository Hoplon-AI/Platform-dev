"""
HA Profile API endpoints - KAN-449
Created by: Govind
Date Created: 01/02/2026

Provides Housing Association profile data for the frontend dashboard.
Includes basic info, statistics, recent activity, and data completeness metrics.
"""
import os
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from backend.core.database.db_pool import DatabasePool


router = APIRouter(
    prefix="/api/v1/ha",
    tags=["ha_profile"]
)


def get_tenant_info() -> Dict[str, str]:
    """
    Get tenant context (ha_id) from JWT or dev mode.
    
    In production: Extracts ha_id from JWT token.
    In dev mode: Uses DEV_HA_ID environment variable.
    
    Returns:
        Dict with ha_id for the authenticated tenant
        
    Raises:
        HTTPException: 401 if not authenticated and not in dev mode
    """
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
    if dev_mode:
        ha_id = os.getenv("DEV_HA_ID", "ha_demo")
        return {"ha_id": ha_id}
    
    # TODO: In production, extract ha_id from JWT token
    # from fastapi.security import HTTPBearer
    # token = ... decode JWT
    # ha_id = token["ha_id"]
    # return {"ha_id": ha_id}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required"
    )


@router.get("/profile")
async def get_ha_profile(
    tenant: Dict[str, str] = Depends(get_tenant_info)
) -> Dict[str, Any]:
    """
    Get Housing Association profile information.
    
    Returns basic HA information along with summary statistics:
    - HA name and metadata
    - Total portfolios count
    - Total properties count
    - Recent uploads (last 30 days)
    
    Args:
        tenant: Tenant context (injected via dependency)
        
    Returns:
        Dictionary containing HA profile and stats
        
    Raises:
        HTTPException: 404 if HA not found
    """
    ha_id = tenant["ha_id"]
    pool = DatabasePool.get_pool()
    
    async with pool.acquire() as conn:
        # Get HA basic information
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
        
        # Get portfolio and property counts
        stats = await conn.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT portfolio_id) as total_portfolios,
                COUNT(DISTINCT property_id) as total_properties
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
        
        # Format response
        return {
            "ha_id": ha["ha_id"],
            "name": ha["name"],
            "created_at": ha["created_at"].isoformat() if ha["created_at"] else None,
            "metadata": ha["metadata"] or {},
            "stats": {
                "total_portfolios": stats["total_portfolios"] or 0,
                "total_properties": stats["total_properties"] or 0,
                "recent_uploads": recent_uploads or 0
            }
        }


@router.get("/activity")
async def get_ha_activity(
    limit: int = 10,
    tenant: Dict[str, str] = Depends(get_tenant_info)
) -> List[Dict[str, Any]]:
    """
    Get recent activity for the Housing Association.
    
    Returns recent uploads and processing events for the HA,
    useful for activity timelines and dashboards.
    
    Args:
        limit: Maximum number of activity items to return (default: 10, max: 50)
        tenant: Tenant context (injected via dependency)
        
    Returns:
        List of recent activity events, newest first
    """
    ha_id = tenant["ha_id"]
    
    # Enforce maximum limit
    if limit > 50:
        limit = 50
    
    pool = DatabasePool.get_pool()
    
    async with pool.acquire() as conn:
        # Query the gold view for recent activity
        activities = await conn.fetch(
            """
            SELECT 
                event_id,
                event_type,
                file_type,
                filename,
                actor_id,
                created_at,
                status,
                metadata
            FROM gold.ha_recent_activity_v1
            WHERE ha_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            ha_id,
            limit
        )
        
        # Format response
        return [
            {
                "event_id": str(activity["event_id"]),
                "event_type": activity["event_type"],
                "file_type": activity["file_type"],
                "filename": activity["filename"],
                "actor_id": activity["actor_id"],
                "created_at": activity["created_at"].isoformat() if activity["created_at"] else None,
                "status": activity["status"],
                "metadata": activity["metadata"] or {}
            }
            for activity in activities
        ]


@router.get("/stats/summary")
async def get_ha_stats_summary(
    tenant: Dict[str, str] = Depends(get_tenant_info)
) -> Dict[str, Any]:
    """
    Get detailed statistics summary for the HA dashboard.
    
    Returns comprehensive statistics including:
    - Risk distribution (properties by risk rating)
    - Data completeness percentages (UPRN, postcode, geocoding, risk rating)
    
    Args:
        tenant: Tenant context (injected via dependency)
        
    Returns:
        Dictionary containing risk distribution and data completeness metrics
    """
    ha_id = tenant["ha_id"]
    pool = DatabasePool.get_pool()
    
    async with pool.acquire() as conn:
        # Get risk distribution
        risk_distribution = await conn.fetch(
            """
            SELECT 
                risk_rating,
                COUNT(*) as count
            FROM properties
            WHERE ha_id = $1 AND risk_rating IS NOT NULL
            GROUP BY risk_rating
            ORDER BY risk_rating
            """,
            ha_id
        )
        
        # Get data completeness metrics
        completeness = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_properties,
                COUNT(uprn) as properties_with_uprn,
                COUNT(postcode) as properties_with_postcode,
                COUNT(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 END) as properties_with_geocoding,
                COUNT(risk_rating) as properties_with_risk_rating
            FROM properties
            WHERE ha_id = $1
            """,
            ha_id
        )
        
        # Calculate percentages (avoid division by zero)
        total = completeness["total_properties"] or 1
        
        return {
            "risk_distribution": [
                {
                    "risk_rating": item["risk_rating"],
                    "count": item["count"]
                }
                for item in risk_distribution
            ],
            "data_completeness": {
                "total_properties": completeness["total_properties"] or 0,
                "uprn_percentage": round((completeness["properties_with_uprn"] or 0) / total * 100, 2),
                "postcode_percentage": round((completeness["properties_with_postcode"] or 0) / total * 100, 2),
                "geocoding_percentage": round((completeness["properties_with_geocoding"] or 0) / total * 100, 2),
                "risk_rating_percentage": round((completeness["properties_with_risk_rating"] or 0) / total * 100, 2)
            }
        }