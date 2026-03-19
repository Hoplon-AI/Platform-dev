"""
export_router.py
----------------
Endpoints for downloading Doc A and Doc B Excel files.

GET /api/v1/portfolios/{portfolio_id}/export/doc-a
    → Downloads a Doc A (Stock Listing) Excel file
      One row per property unit, 35 columns in Aviva format.

GET /api/v1/portfolios/{portfolio_id}/export/doc-b
    → Downloads a partial Doc B (High Value Building) Excel file
      One row per block, 64 columns.
      SOV sections filled; FRA/FRAEW sections show "Pending".

Both endpoints follow the exact same auth/tenant pattern as portfolios_router.py.
"""

from __future__ import annotations

import os
from typing import Any, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.database.db_pool import DatabasePool
from backend.core.tenancy.tenant_middleware import TenantMiddleware
from backend.core.exporters.doc_a_exporter import generate_doc_a
from backend.core.exporters.doc_b_exporter import generate_doc_b

router = APIRouter(prefix="/api/v1/portfolios", tags=["exports"])

security = HTTPBearer(auto_error=False)
tenant_middleware = TenantMiddleware()


# ---------------------------------------------------------------------------
# Auth dependency — copied exactly from portfolios_router.py
# ---------------------------------------------------------------------------

async def get_tenant_info(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Tuple[str, str]:
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
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return tenant_middleware.extract_tenant_from_token(credentials.credentials)


def _is_dev_mode() -> bool:
    return os.getenv("DEV_MODE", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Helper — resolve portfolio → ha_id + ha_name
# ---------------------------------------------------------------------------

async def _get_portfolio(
    conn,
    portfolio_id: str,
    ha_id: str,
) -> dict[str, Any]:
    """
    Fetch portfolio row. Raises 404 if not found.
    In DEV_MODE skips the ha_id filter.
    """
    if _is_dev_mode():
        row = await conn.fetchrow(
            """
            SELECT p.portfolio_id, p.ha_id, h.name AS ha_name
            FROM silver.portfolios p
            JOIN housing_associations h ON h.ha_id = p.ha_id
            WHERE p.portfolio_id = $1
            """,
            portfolio_id,
        )
    else:
        row = await conn.fetchrow(
            """
            SELECT p.portfolio_id, p.ha_id, h.name AS ha_name
            FROM silver.portfolios p
            JOIN housing_associations h ON h.ha_id = p.ha_id
            WHERE p.portfolio_id = $1 AND p.ha_id = $2
            """,
            portfolio_id,
            ha_id,
        )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio '{portfolio_id}' not found.",
        )

    return dict(row)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{portfolio_id}/export/doc-a",
    summary="Download Doc A — Stock Listing Excel",
    response_description="Excel file (.xlsx) in Aviva Doc A format",
    responses={
        200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}},
        404: {"description": "Portfolio not found"},
        204: {"description": "No properties found for this portfolio"},
    },
)
async def export_doc_a(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Generate and download a Doc A Stock Listing Excel file.

    - One row per property unit
    - 35 columns in Aviva format
    - Insurer-only columns (policy number, GWP etc.) are left blank
    - Data populated from silver.properties for this HA
    """
    ha_id, _user_id = tenant

    async with DatabasePool.acquire() as conn:
        portfolio = await _get_portfolio(conn, portfolio_id, ha_id)

        # Quick check — does this portfolio have any properties?
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM silver.properties WHERE ha_id = $1",
            portfolio["ha_id"],
        )

    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_204_NO_CONTENT,
            detail="No properties found. Upload a SOV file first.",
        )

    # Generate the Excel
    excel_bytes = await generate_doc_a(
        db_pool=DatabasePool,
        ha_id=portfolio["ha_id"],
        ha_name=portfolio["ha_name"],
        portfolio_id=portfolio_id,
    )

    filename = f"DocA_{portfolio['ha_name'].replace(' ', '_')}_{portfolio_id}.xlsx"

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(excel_bytes)),
        },
    )


@router.get(
    "/{portfolio_id}/export/doc-b",
    summary="Download Doc B — High Value Building Excel",
    response_description="Excel file (.xlsx) in Aviva Doc B format",
    responses={
        200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}},
        404: {"description": "Portfolio not found"},
        204: {"description": "No properties found for this portfolio"},
    },
)
async def export_doc_b(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Generate and download a partial Doc B High Value Building Excel file.

    - One row per block (properties grouped by block_reference)
    - 64 columns in Aviva Doc B format
    - SOV sections (property details + construction) fully populated
    - Fire Risk (Q32–Q40) marked as 'Pending FRA' — populated when FRA uploaded
    - EWS/Cladding (Q41–Q58) marked as 'Pending FRAEW' — populated when FRAEW uploaded
    - Insurer columns left blank
    - Includes a Legend sheet explaining colour coding
    """
    ha_id, _user_id = tenant

    async with DatabasePool.acquire() as conn:
        portfolio = await _get_portfolio(conn, portfolio_id, ha_id)

        count = await conn.fetchval(
            "SELECT COUNT(*) FROM silver.properties WHERE ha_id = $1",
            portfolio["ha_id"],
        )

    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_204_NO_CONTENT,
            detail="No properties found. Upload a SOV file first.",
        )

    excel_bytes = await generate_doc_b(
        db_pool=DatabasePool,
        ha_id=portfolio["ha_id"],
        ha_name=portfolio["ha_name"],
        portfolio_id=portfolio_id,
    )

    filename = f"DocB_{portfolio['ha_name'].replace(' ', '_')}_{portfolio_id}.xlsx"

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(excel_bytes)),
        },
    )