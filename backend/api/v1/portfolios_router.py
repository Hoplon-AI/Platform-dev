"""
Portfolio endpoints for Week 3 dashboard development.

Backed by Gold views:
- gold.portfolio_summary_v1
- gold.portfolio_readiness_v1
- gold.portfolio_risk_distribution_v1
- gold.ha_recent_activity_v1 (HA scoped; derived from upload_audit)
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.database.db_pool import DatabasePool
from backend.core.tenancy.tenant_middleware import TenantMiddleware


router = APIRouter(prefix="/api/v1/portfolios", tags=["portfolios"])

security = HTTPBearer(auto_error=False)  # Don't auto-raise on missing token
tenant_middleware = TenantMiddleware()


async def get_tenant_info(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Tuple[str, str]:
    """
    FastAPI dependency to extract ha_id and user_id from JWT token.

    In DEV_MODE, missing/invalid credentials fall back to defaults.
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


def _is_dev_mode() -> bool:
    return os.getenv("DEV_MODE", "false").lower() == "true"


@router.get("", response_model=list[dict])
async def list_portfolios(tenant: Tuple[str, str] = Depends(get_tenant_info)) -> List[Dict[str, Any]]:
    """
    List portfolios (tenant-scoped in production; unscoped in DEV_MODE).
    """
    ha_id, _user_id = tenant

    where_clause = ""
    params: list[Any] = []
    if not _is_dev_mode():
        where_clause = "WHERE ha_id = $1"
        params = [ha_id]

    query = f"""
        SELECT portfolio_id, ha_id, name, renewal_year, created_at, updated_at
        FROM silver.portfolios
        {where_clause}
        ORDER BY created_at DESC
        LIMIT 100
    """

    async with DatabasePool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [dict(r) for r in rows]


@router.get("/{portfolio_id}/summary", response_model=dict)
async def get_portfolio_summary(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    ha_id, _user_id = tenant

    if _is_dev_mode():
        query = "SELECT * FROM gold.portfolio_summary_v1 WHERE portfolio_id = $1"
        params = [portfolio_id]
    else:
        query = "SELECT * FROM gold.portfolio_summary_v1 WHERE portfolio_id = $1 AND ha_id = $2"
        params = [portfolio_id, ha_id]

    async with DatabasePool.acquire() as conn:
        row = await conn.fetchrow(query, *params)

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    return dict(row)


@router.get("/{portfolio_id}/readiness", response_model=dict)
async def get_portfolio_readiness(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    ha_id, _user_id = tenant

    if _is_dev_mode():
        query = "SELECT * FROM gold.portfolio_readiness_v1 WHERE portfolio_id = $1"
        params = [portfolio_id]
    else:
        query = "SELECT * FROM gold.portfolio_readiness_v1 WHERE portfolio_id = $1 AND ha_id = $2"
        params = [portfolio_id, ha_id]

    async with DatabasePool.acquire() as conn:
        row = await conn.fetchrow(query, *params)

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    return dict(row)


@router.get("/{portfolio_id}/risk-distribution", response_model=list[dict])
async def get_portfolio_risk_distribution(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> List[Dict[str, Any]]:
    ha_id, _user_id = tenant

    if _is_dev_mode():
        query = """
            SELECT risk_rating, property_count
            FROM gold.portfolio_risk_distribution_v1
            WHERE portfolio_id = $1
            ORDER BY risk_rating
        """
        params = [portfolio_id]
    else:
        query = """
            SELECT risk_rating, property_count
            FROM gold.portfolio_risk_distribution_v1
            WHERE portfolio_id = $1 AND ha_id = $2
            ORDER BY risk_rating
        """
        params = [portfolio_id, ha_id]

    async with DatabasePool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    # Empty is valid (e.g., no ratings yet)
    return [dict(r) for r in rows]


@router.get("/{portfolio_id}/recent-activity", response_model=list[dict])
async def get_portfolio_recent_activity(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """
    Recent activity feed for a portfolio.

    Note: the underlying gold view is HA-scoped (upload_audit). We resolve the
    portfolio's ha_id first, then return recent HA activity as a practical MVP.
    """
    ha_id, _user_id = tenant
    limit = max(1, min(limit, 200))

    async with DatabasePool.acquire() as conn:
        if _is_dev_mode():
            portfolio_row = await conn.fetchrow(
                "SELECT ha_id FROM silver.portfolios WHERE portfolio_id = $1",
                portfolio_id,
            )
        else:
            portfolio_row = await conn.fetchrow(
                "SELECT ha_id FROM silver.portfolios WHERE portfolio_id = $1 AND ha_id = $2",
                portfolio_id,
                ha_id,
            )

        if not portfolio_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

        portfolio_ha_id = portfolio_row["ha_id"]

        rows = await conn.fetch(
            """
            SELECT *
            FROM gold.ha_recent_activity_v1
            WHERE ha_id = $1
            LIMIT $2
            """,
            portfolio_ha_id,
            limit,
        )

    return [dict(r) for r in rows]

