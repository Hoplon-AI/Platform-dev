"""
underwriter_router.py
---------------------
Underwriter Dashboard API endpoints.

Provides portfolio-level analytics for underwriters:
  GET /api/v1/underwriter/portfolios                     — dropdown list with KPI badges
  GET /api/v1/underwriter/portfolios/{id}/summary       — KPI header cards
  GET /api/v1/underwriter/portfolios/{id}/composition   — property type breakdown
  GET /api/v1/underwriter/portfolios/{id}/map           — block map markers (RAG colour coded)
  GET /api/v1/underwriter/portfolios/{id}/fra-blocks    — FRA status per block
  GET /api/v1/underwriter/portfolios/{id}/fraew-blocks  — FRAEW detail per block
  GET /api/v1/underwriter/portfolios/{id}/risk-summary  — combined compliance view
  GET /api/v1/underwriter/portfolios/{id}/doc-completeness — Doc A / Doc B completeness
  GET /api/v1/underwriter/portfolios/{id}/fire-documents   — latest FRA/FRAEW docs for dashboard

Design notes:
- Queries use ha_id (resolved from portfolio_id) for all silver.* table joins because
  ha_demo properties/blocks may not have portfolio_id populated.
- Map coordinates: use lat/lon if present, otherwise convert x_coordinate/y_coordinate
  (OS National Grid OSGB36 EPSG:27700) to WGS84 (EPSG:4326) via PostGIS ST_Transform.
- FRA/FRAEW status: LATERAL JOINs directly to fra_features/fraew_features ordered by
  latest document date — does NOT rely on denormalised block status.
- Map colour rule: worst of FRA and FRAEW RAG. GREY = unassessed.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.database.db_pool import DatabasePool
from backend.core.tenancy.tenant_middleware import TenantMiddleware
from backend.api.v1.auth_router import _decode_token

router = APIRouter(prefix="/api/v1/underwriter", tags=["underwriter"])

security = HTTPBearer(auto_error=False)
tenant_middleware = TenantMiddleware()


# ---------------------------------------------------------------------------
# Auth dependency
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in {"true", "yes", "y", "1"}:
            return True
        if lower in {"false", "no", "n", "0"}:
            return False
    return None


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _row_to_dict(row: Any) -> Dict[str, Any]:
    return dict(row) if row else {}


def _build_fire_document_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize combined latest FRA/FRAEW row for frontend use.
    """
    return {
        "block_id": row.get("block_id"),
        "block_name": row.get("block_name"),
        "property_id": row.get("property_id"),
        "property_reference": row.get("property_reference"),
        "address": row.get("address"),
        "postcode": row.get("postcode"),
        "fra": {
            "feature_id": row.get("fra_feature_id"),
            "fra_id": row.get("fra_id"),
            "assessment_date": row.get("fra_assessment_date"),
            "assessment_valid_until": row.get("fra_assessment_valid_until"),
            "is_in_date": _to_bool(row.get("fra_is_in_date")),
            "risk_level": row.get("fra_rag") or row.get("fra_raw_rating"),
            "raw_rating": row.get("fra_raw_rating"),
            "assessor_name": row.get("fra_assessor_name"),
            "assessor_company": row.get("fra_assessor_company"),
            "evacuation_strategy": row.get("fra_evacuation_strategy"),
            "fire_alarm_system": _to_bool(row.get("fra_has_fire_alarm_system")),
            "smoke_detection": _to_bool(row.get("fra_has_smoke_detection")),
            "sprinkler_system": _to_bool(row.get("fra_has_sprinkler_system")),
            "fire_doors": _to_bool(row.get("fra_has_fire_doors")),
            "compartmentation": _to_bool(row.get("fra_has_compartmentation")),
            "significant_findings": row.get("fra_significant_findings") or [],
            "recommendations": row.get("fra_action_items") or [],
            "total_actions": row.get("fra_total_action_count"),
            "overdue_actions": row.get("fra_overdue_action_count"),
            "outstanding_actions": row.get("fra_outstanding_action_count"),
            "extraction_confidence": _to_float(row.get("fra_extraction_confidence")),
        },
        "fraew": {
            "feature_id": row.get("fraew_feature_id"),
            "fraew_id": row.get("fraew_id"),
            "assessment_date": row.get("fraew_assessment_date"),
            "assessment_valid_until": row.get("fraew_assessment_valid_until"),
            "is_in_date": _to_bool(row.get("fraew_is_in_date")),
            "risk_level": row.get("fraew_rag") or row.get("fraew_raw_rating"),
            "raw_rating": row.get("fraew_raw_rating"),
            "assessor_name": row.get("fraew_assessor_name"),
            "assessor_company": row.get("fraew_assessor_company"),
            "building_height_m": _to_float(row.get("fraew_building_height_m")),
            "building_height_category": row.get("fraew_building_height_category"),
            "num_storeys": row.get("fraew_num_storeys"),
            "num_units": row.get("fraew_num_units"),
            "construction_frame_type": row.get("fraew_construction_frame_type"),
            "external_wall_base_construction": row.get("fraew_external_wall_base_construction"),
            "pas_9980_version": row.get("fraew_pas_9980_version"),
            "pas_9980_compliant": _to_bool(row.get("fraew_pas_9980_compliant")),
            "interim_measures_required": _to_bool(row.get("fraew_interim_measures_required")),
            "interim_measures_detail": row.get("fraew_interim_measures_detail"),
            "remediation_required": _to_bool(row.get("fraew_has_remedial_actions")),
            "recommendations": row.get("fraew_remedial_actions") or [],
            "wall_types": row.get("fraew_wall_types") or [],
            "combustible_cladding": _to_bool(row.get("fraew_has_combustible_cladding")),
            "eps_insulation_present": _to_bool(row.get("fraew_eps_insulation_present")),
            "mineral_wool_insulation_present": _to_bool(row.get("fraew_mineral_wool_insulation_present")),
            "pir_insulation_present": _to_bool(row.get("fraew_pir_insulation_present")),
            "phenolic_insulation_present": _to_bool(row.get("fraew_phenolic_insulation_present")),
            "acrylic_render_present": _to_bool(row.get("fraew_acrylic_render_present")),
            "cement_render_present": _to_bool(row.get("fraew_cement_render_present")),
            "cavity_barriers_present": _to_bool(row.get("fraew_cavity_barriers_present")),
            "dry_riser_present": _to_bool(row.get("fraew_dry_riser_present")),
            "wet_riser_present": _to_bool(row.get("fraew_wet_riser_present")),
            "evacuation_strategy": row.get("fraew_evacuation_strategy"),
            "adb_compliant": row.get("fraew_adb_compliant"),
            "bs8414_test_evidence": _to_bool(row.get("fraew_bs8414_test_evidence")),
            "br135_criteria_met": _to_bool(row.get("fraew_br135_criteria_met")),
            "extraction_confidence": _to_float(row.get("fraew_extraction_confidence")),
        },
    }


# ---------------------------------------------------------------------------
# Helper — resolve portfolio_id → {portfolio_id, ha_id, ha_name, ...}
# ---------------------------------------------------------------------------

async def _resolve_portfolio(conn, portfolio_id: str) -> Dict[str, Any]:
    row = await conn.fetchrow(
        """
        SELECT
            po.portfolio_id,
            po.ha_id,
            po.name          AS portfolio_name,
            po.renewal_year,
            po.renewal_date,
            ha.name          AS ha_name
        FROM silver.portfolios po
        JOIN public.housing_associations ha ON ha.ha_id = po.ha_id
        WHERE po.portfolio_id = $1
        """,
        portfolio_id,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio {portfolio_id} not found.",
        )
    return dict(row)


# ===========================================================================
# 0. Underwriter Home
# ===========================================================================

@router.get("/home")
async def underwriter_home(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"

    if credentials:
        payload = _decode_token(credentials.credentials)
        ha_ids: List[str] = payload.get("ha_ids", [])
        underwriter_id: Optional[str] = payload.get("sub")
    elif dev_mode:
        ha_ids = [os.getenv("DEV_HA_ID", "ha_demo")]
        underwriter_id = None
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    if not ha_ids:
        return {
            "portfolios": [],
            "attention": {
                "fra_red_blocks": 0,
                "combustible_cladding_portfolios": 0,
                "new_portfolios": 0,
            },
        }

    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                po.portfolio_id::text,
                po.ha_id,
                po.name          AS portfolio_name,
                po.renewal_year,
                po.renewal_date,
                ha.name          AS ha_name,

                acc.granted_by,
                acc.status       AS access_status,

                COUNT(DISTINCT b.block_id)                          AS block_count,
                COALESCE(SUM(b.unit_count), 0)::bigint              AS total_units,
                COALESCE(SUM(b.total_sum_insured), 0)               AS total_insured_value,

                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status = 'RED'
                )                                                   AS fra_red_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status = 'AMBER'
                )                                                   AS fra_amber_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status = 'GREEN'
                )                                                   AS fra_green_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status IS NULL
                )                                                   AS fra_unassessed_count,

                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.rag_status IS NOT NULL
                )                                                   AS fraew_assessed_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.rag_status IS NULL
                )                                                   AS fraew_unassessed_count,
                BOOL_OR(fraew.has_combustible_cladding = TRUE)      AS has_combustible_cladding_blocks

            FROM silver.portfolios po
            JOIN public.housing_associations ha ON ha.ha_id = po.ha_id

            LEFT JOIN public.ha_underwriter_access acc
                ON  acc.ha_id = po.ha_id
                AND acc.renewal_year = po.renewal_year
                AND ($2::text IS NULL OR acc.underwriter_id::text = $2)

            LEFT JOIN silver.blocks b ON b.ha_id = po.ha_id

            LEFT JOIN LATERAL (
                SELECT rag_status
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST, created_at DESC
                LIMIT 1
            ) fra ON TRUE

            LEFT JOIN LATERAL (
                SELECT rag_status, has_combustible_cladding
                FROM silver.fraew_features
                WHERE block_id = b.block_id
                ORDER BY created_at DESC
                LIMIT 1
            ) fraew ON TRUE

            WHERE po.ha_id = ANY($1)

            GROUP BY
                po.portfolio_id, po.ha_id, po.name, po.renewal_year, po.renewal_date,
                ha.name, acc.granted_by, acc.status

            ORDER BY po.renewal_year DESC, ha.name
            """,
            ha_ids,
            underwriter_id,
        )

    portfolios = [dict(r) for r in rows]
    fra_red_blocks = sum((p.get("fra_red_count") or 0) for p in portfolios)
    cladding_count = sum(1 for p in portfolios if p.get("has_combustible_cladding_blocks"))
    new_count = sum(1 for p in portfolios if p.get("access_status") == "new")

    return {
        "portfolios": portfolios,
        "attention": {
            "fra_red_blocks": fra_red_blocks,
            "combustible_cladding_portfolios": cladding_count,
            "new_portfolios": new_count,
        },
    }


# ===========================================================================
# 1. Portfolio Dropdown
# ===========================================================================

@router.get("/portfolios", response_model=List[Dict[str, Any]])
async def list_portfolios(
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> List[Dict[str, Any]]:
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                po.portfolio_id::text,
                po.ha_id,
                po.name          AS portfolio_name,
                po.renewal_year,
                po.renewal_date,
                ha.name          AS ha_name,

                COUNT(DISTINCT b.block_id)                          AS block_count,
                COALESCE(SUM(b.unit_count), 0)::bigint              AS total_units,
                COALESCE(SUM(b.total_sum_insured), 0)               AS total_insured_value,

                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status = 'RED'
                )                                                   AS fra_red_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status = 'AMBER'
                )                                                   AS fra_amber_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status = 'GREEN'
                )                                                   AS fra_green_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status IS NULL
                )                                                   AS fra_unassessed_count,

                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.rag_status IS NOT NULL
                )                                                   AS fraew_assessed_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.rag_status IS NULL
                )                                                   AS fraew_unassessed_count,

                BOOL_OR(fraew.has_combustible_cladding = TRUE)      AS has_combustible_cladding_blocks

            FROM silver.portfolios po
            JOIN public.housing_associations ha ON ha.ha_id = po.ha_id
            LEFT JOIN silver.blocks b ON b.ha_id = po.ha_id

            LEFT JOIN LATERAL (
                SELECT rag_status
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST, created_at DESC
                LIMIT 1
            ) fra ON TRUE

            LEFT JOIN LATERAL (
                SELECT rag_status, has_combustible_cladding
                FROM silver.fraew_features
                WHERE block_id = b.block_id
                ORDER BY created_at DESC
                LIMIT 1
            ) fraew ON TRUE

            GROUP BY po.portfolio_id, po.ha_id, po.name, po.renewal_year, ha.name
            ORDER BY po.renewal_year DESC, ha.name
            """,
        )
        return [dict(r) for r in rows]


# ===========================================================================
# 2. Portfolio Summary
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/summary")
async def portfolio_summary(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        row = await conn.fetchrow(
            """
            SELECT
                $2::text                                            AS ha_id,
                $1::text                                            AS portfolio_id,

                COUNT(DISTINCT b.block_id)                          AS total_blocks,
                COALESCE(SUM(b.unit_count), 0)::bigint              AS total_units,
                COALESCE(SUM(b.total_sum_insured), 0)               AS total_insured_value,

                (SELECT COUNT(*) FROM silver.properties WHERE ha_id = $2)::bigint
                                                                    AS total_properties,

                (SELECT COUNT(*) FROM silver.properties WHERE ha_id = $2 AND enrichment_status = 'enriched')::bigint
                                                                    AS enriched_properties,
                (SELECT COUNT(*) FROM silver.properties WHERE ha_id = $2 AND enrichment_status = 'pending')::bigint
                                                                    AS pending_properties,

                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status = 'RED'
                )                                                   AS fra_red_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status = 'AMBER'
                )                                                   AS fra_amber_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status = 'GREEN'
                )                                                   AS fra_green_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status IS NULL
                )                                                   AS fra_unassessed_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.rag_status IS NOT NULL
                )                                                   AS fra_assessed_count,

                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.rag_status IS NOT NULL
                )                                                   AS fraew_assessed_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.rag_status IS NULL
                )                                                   AS fraew_unassessed_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.rag_status = 'RED'
                )                                                   AS fraew_red_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.rag_status = 'AMBER'
                )                                                   AS fraew_amber_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.rag_status = 'GREEN'
                )                                                   AS fraew_green_count,

                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.has_combustible_cladding = TRUE
                )                                                   AS combustible_cladding_blocks,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.eps_insulation_present = TRUE
                )                                                   AS eps_insulation_blocks,

                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE b.height_max_m IS NOT NULL AND b.height_max_m < 11
                )                                                   AS blocks_under_11m,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE b.height_max_m >= 11 AND b.height_max_m < 18
                )                                                   AS blocks_11_to_18m,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE b.height_max_m >= 18 AND b.height_max_m < 30
                )                                                   AS blocks_18_to_30m,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE b.height_max_m >= 30
                )                                                   AS blocks_over_30m,

                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE b.is_listed = TRUE
                )                                                   AS listed_blocks,

                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE b.height_max_m >= 18
                )                                                   AS fraew_18m_total,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE b.height_max_m >= 18 AND fraew.rag_status IS NOT NULL
                )                                                   AS fraew_18m_assessed,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE b.height_max_m >= 18 AND fraew.rag_status IS NULL
                )                                                   AS fraew_18m_awaiting

            FROM silver.blocks b

            LEFT JOIN LATERAL (
                SELECT rag_status
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST, created_at DESC
                LIMIT 1
            ) fra ON TRUE

            LEFT JOIN LATERAL (
                SELECT rag_status, has_combustible_cladding, eps_insulation_present
                FROM silver.fraew_features
                WHERE block_id = b.block_id
                ORDER BY created_at DESC
                LIMIT 1
            ) fraew ON TRUE

            WHERE b.ha_id = $2
            """,
            portfolio_id,
            ha_id,
        )

        result = dict(row)
        result.update({
            "portfolio_name": portfolio["portfolio_name"],
            "ha_name": portfolio["ha_name"],
            "renewal_year": portfolio["renewal_year"],
            "renewal_date": portfolio["renewal_date"].isoformat() if portfolio["renewal_date"] else None,
        })
        return result


# ===========================================================================
# 3. Portfolio Composition
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/composition")
async def portfolio_composition(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        tenancy_rows = await conn.fetch(
            """
            WITH totals AS (
                SELECT SUM(sum_insured) AS grand_total
                FROM silver.properties
                WHERE ha_id = $1
            )
            SELECT
                COALESCE(occupancy_type, 'Not recorded')    AS type,
                COUNT(*)::integer                           AS units,
                COALESCE(SUM(sum_insured), 0)               AS sum_insured,
                CASE WHEN t.grand_total > 0
                    THEN ROUND(SUM(sum_insured) / t.grand_total * 100, 1)
                    ELSE 0
                END                                         AS pct
            FROM silver.properties, totals t
            WHERE ha_id = $1
            GROUP BY occupancy_type, t.grand_total
            ORDER BY sum_insured DESC
            """,
            ha_id,
        )

        block_summary = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE block_reference IS NULL)::integer AS no_block_units,
                COALESCE(SUM(sum_insured) FILTER (WHERE block_reference IS NULL), 0) AS no_block_tiv,
                COUNT(DISTINCT block_reference) FILTER (WHERE block_reference IS NOT NULL)::integer AS block_count,
                COUNT(*) FILTER (WHERE block_reference IS NOT NULL)::integer AS block_units,
                COALESCE(SUM(sum_insured) FILTER (WHERE block_reference IS NOT NULL), 0) AS block_tiv
            FROM silver.properties
            WHERE ha_id = $1
            """,
            ha_id,
        )

        block_rows = await conn.fetch(
            """
            SELECT
                block_reference                             AS block,
                COUNT(*)::integer                           AS units,
                COALESCE(SUM(sum_insured), 0)               AS tiv,
                (SUM(sum_insured) > 5000000)                AS over_5m
            FROM silver.properties
            WHERE ha_id = $1
              AND block_reference IS NOT NULL
            GROUP BY block_reference
            ORDER BY tiv DESC
            """,
            ha_id,
        )
        blocks_over_5m = sum(1 for r in block_rows if r["over_5m"])

        type_rows = await conn.fetch(
            """
            WITH totals AS (
                SELECT SUM(sum_insured) AS grand_total
                FROM silver.properties
                WHERE ha_id = $1
            )
            SELECT
                COALESCE(avid_property_type, 'Not recorded') AS type,
                COUNT(*)::integer                            AS units,
                COALESCE(SUM(sum_insured), 0)                AS sum_insured,
                CASE WHEN t.grand_total > 0
                    THEN ROUND(SUM(sum_insured) / t.grand_total * 100, 1)
                    ELSE 0
                END                                          AS pct
            FROM silver.properties, totals t
            WHERE ha_id = $1
            GROUP BY avid_property_type, t.grand_total
            ORDER BY sum_insured DESC
            """,
            ha_id,
        )

        age_rows = await conn.fetch(
            """
            WITH totals AS (
                SELECT SUM(sum_insured) AS grand_total
                FROM silver.properties
                WHERE ha_id = $1
            )
            SELECT
                COALESCE(age_banding, 'Unknown')            AS age_band,
                COUNT(*)::integer                           AS units,
                COALESCE(SUM(sum_insured), 0)               AS sum_insured,
                CASE WHEN t.grand_total > 0
                    THEN ROUND(SUM(sum_insured) / t.grand_total * 100, 1)
                    ELSE 0
                END                                         AS pct
            FROM silver.properties, totals t
            WHERE ha_id = $1
            GROUP BY age_banding, t.grand_total
            ORDER BY
                CASE age_banding
                    WHEN 'Pre-1919'   THEN 1
                    WHEN '1901-1919'  THEN 1
                    WHEN '1920-1944'  THEN 2
                    WHEN '1945-1979'  THEN 3
                    WHEN '1980-2000'  THEN 4
                    WHEN '2001+'      THEN 5
                    ELSE 6
                END
            """,
            ha_id,
        )

        composition_rows = await conn.fetch(
            """
            SELECT
                COALESCE(avid_property_type, 'Other')           AS property_type,
                COALESCE(responsible_party, 'ha_controlled')    AS responsible_party,
                COUNT(*)::integer                               AS units,
                COALESCE(SUM(sum_insured), 0)                   AS sum_insured
            FROM silver.properties
            WHERE ha_id = $1
            GROUP BY avid_property_type, responsible_party
            ORDER BY avid_property_type, responsible_party
            """,
            ha_id,
        )

        comp: Dict[str, Any] = {}
        for r in composition_rows:
            pt = r["property_type"]
            rp = r["responsible_party"]
            if pt not in comp:
                comp[pt] = {
                    "property_type": pt,
                    "total_units": 0,
                    "total_sum_insured": 0,
                    "ha_controlled": 0,
                    "third_party": 0,
                    "ha_controlled_tiv": 0,
                    "third_party_tiv": 0,
                }
            comp[pt]["total_units"] += r["units"]
            comp[pt]["total_sum_insured"] = float(comp[pt]["total_sum_insured"]) + float(r["sum_insured"])
            if rp == "third_party":
                comp[pt]["third_party"] += r["units"]
                comp[pt]["third_party_tiv"] = float(comp[pt]["third_party_tiv"]) + float(r["sum_insured"])
            else:
                comp[pt]["ha_controlled"] += r["units"]
                comp[pt]["ha_controlled_tiv"] = float(comp[pt]["ha_controlled_tiv"]) + float(r["sum_insured"])

        totals = await conn.fetchrow(
            """
            SELECT
                COUNT(*)::integer       AS total_units,
                SUM(sum_insured)        AS total_sum_insured
            FROM silver.properties
            WHERE ha_id = $1
            """,
            ha_id,
        )

        total_units = totals["total_units"] or 1

        for v in comp.values():
            v["pct"] = round(v["total_units"] / total_units * 100, 1)

        third_party_flats = comp.get("Flat", {}).get("third_party", 0)
        third_party_blocks = sum(
            v["third_party"] for k, v in comp.items()
            if k not in ("Flat",)
        )

        return {
            "portfolio_id": portfolio_id,
            "ha_id": ha_id,
            "portfolio_name": portfolio["portfolio_name"],
            "ha_name": portfolio["ha_name"],
            "totals": {
                "units": totals["total_units"],
                "sum_insured": totals["total_sum_insured"],
            },
            "portfolio_composition": {
                "total_units": totals["total_units"],
                "breakdown": list(comp.values()),
                "third_party_flat_units": third_party_flats,
                "third_party_block_count": third_party_blocks,
                "has_third_party_warning": third_party_flats > 0 or third_party_blocks > 0,
            },
            "by_tenancy": [dict(r) for r in tenancy_rows],
            "by_block": {
                "no_block_units": block_summary["no_block_units"],
                "no_block_tiv": block_summary["no_block_tiv"],
                "block_count": block_summary["block_count"],
                "block_units": block_summary["block_units"],
                "block_tiv": block_summary["block_tiv"],
                "blocks_over_5m": blocks_over_5m,
                "blocks": [dict(r) for r in block_rows],
            },
            "by_property_type": [dict(r) for r in type_rows],
            "by_age_banding": [dict(r) for r in age_rows],
        }


# ===========================================================================
# 4. Portfolio Map
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/map")
async def portfolio_map(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        rows = await conn.fetch(
            """
            WITH block_coords AS (
                SELECT
                    p.block_reference,
                    p.ha_id,
                    AVG(p.latitude)      AS lat_direct,
                    AVG(p.longitude)     AS lon_direct,
                    AVG(p.x_coordinate)  AS avg_easting,
                    AVG(p.y_coordinate)  AS avg_northing,
                    MIN(p.address)       AS sample_address,
                    MIN(p.postcode)      AS sample_postcode
                FROM silver.properties p
                WHERE p.ha_id = $1
                  AND (
                      p.latitude IS NOT NULL
                      OR p.x_coordinate IS NOT NULL
                  )
                GROUP BY p.block_reference, p.ha_id
            )

            SELECT
                b.block_id::text,
                b.name              AS block_name,
                b.unit_count,
                b.total_sum_insured,
                b.height_max_m,
                b.is_listed,

                COALESCE(
                    coords.lat_direct,
                    CASE WHEN coords.avg_easting IS NOT NULL
                        THEN ST_Y(ST_Transform(
                            ST_SetSRID(ST_MakePoint(coords.avg_easting, coords.avg_northing), 27700),
                            4326
                        ))
                    END
                )::numeric(10,6)    AS latitude,

                COALESCE(
                    coords.lon_direct,
                    CASE WHEN coords.avg_easting IS NOT NULL
                        THEN ST_X(ST_Transform(
                            ST_SetSRID(ST_MakePoint(coords.avg_easting, coords.avg_northing), 27700),
                            4326
                        ))
                    END
                )::numeric(10,6)    AS longitude,

                coords.sample_address,
                coords.sample_postcode,

                fra.feature_id::text     AS fra_feature_id,
                fra.rag_status           AS fra_rag,
                fra.risk_rating          AS fra_raw_rating,
                fra.assessment_date      AS fra_date,
                fra.assessment_valid_until AS fra_valid_until,
                fra.is_in_date           AS fra_is_in_date,
                fra.total_action_count,
                fra.overdue_action_count,

                fraew.feature_id::text   AS fraew_feature_id,
                fraew.rag_status         AS fraew_rag,
                fraew.building_risk_rating AS fraew_raw_rating,
                fraew.has_combustible_cladding,
                fraew.eps_insulation_present,
                fraew.has_remedial_actions,

                CASE
                    WHEN fra.rag_status = 'RED'   OR fraew.rag_status = 'RED'   THEN 'red'
                    WHEN fra.rag_status = 'AMBER' OR fraew.rag_status = 'AMBER' THEN 'amber'
                    WHEN fra.rag_status = 'GREEN'
                         AND (fraew.rag_status = 'GREEN' OR fraew.rag_status IS NULL)
                                                                                 THEN 'green'
                    ELSE 'grey'
                END                     AS map_colour,

                CASE
                    WHEN fra.rag_status = 'RED'   OR fraew.rag_status = 'RED'
                        THEN 'High Risk'
                    WHEN fra.rag_status = 'AMBER' OR fraew.rag_status = 'AMBER'
                        THEN 'Medium Risk'
                    WHEN fra.rag_status = 'GREEN'
                        THEN 'Low Risk'
                    ELSE 'Not Assessed'
                END                     AS risk_label

            FROM silver.blocks b

            LEFT JOIN block_coords coords
                ON coords.block_reference = b.name
                AND coords.ha_id = b.ha_id

            LEFT JOIN LATERAL (
                SELECT feature_id, rag_status, risk_rating, assessment_date,
                       assessment_valid_until, is_in_date,
                       total_action_count, overdue_action_count
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST, created_at DESC
                LIMIT 1
            ) fra ON TRUE

            LEFT JOIN LATERAL (
                SELECT feature_id, rag_status, building_risk_rating, has_combustible_cladding,
                       eps_insulation_present, has_remedial_actions
                FROM silver.fraew_features
                WHERE block_id = b.block_id
                ORDER BY created_at DESC
                LIMIT 1
            ) fraew ON TRUE

            WHERE b.ha_id = $1
              AND (
                  coords.lat_direct IS NOT NULL
                  OR coords.avg_easting IS NOT NULL
              )
            ORDER BY
                CASE
                    WHEN fra.rag_status = 'RED'   OR fraew.rag_status = 'RED'   THEN 1
                    WHEN fra.rag_status = 'AMBER' OR fraew.rag_status = 'AMBER' THEN 2
                    WHEN fra.rag_status = 'GREEN'                                THEN 3
                    ELSE 4
                END,
                b.name
            """,
            ha_id,
        )

        markers = [dict(r) for r in rows]

        colour_counts = {"red": 0, "amber": 0, "green": 0, "grey": 0}
        for m in markers:
            colour_counts[m.get("map_colour", "grey")] += 1

        return {
            "portfolio_id": portfolio_id,
            "ha_id": ha_id,
            "portfolio_name": portfolio["portfolio_name"],
            "ha_name": portfolio["ha_name"],
            "total_markers": len(markers),
            "colour_counts": colour_counts,
            "markers": markers,
        }


# ===========================================================================
# 5. FRA Blocks Table
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/fra-blocks")
async def fra_blocks(
    portfolio_id: str,
    rag_filter: Optional[str] = None,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        if rag_filter == "unassessed":
            rag_clause = "AND fra.rag_status IS NULL"
        elif rag_filter in ("RED", "AMBER", "GREEN"):
            rag_clause = f"AND fra.rag_status = '{rag_filter}'"
        else:
            rag_clause = ""

        rows = await conn.fetch(
            f"""
            SELECT
                b.block_id::text,
                b.name              AS block_name,
                b.unit_count,
                b.height_max_m,
                b.total_sum_insured,
                b.is_listed,
                b.listed_grade,

                fra.fra_id::text,
                fra.feature_id::text AS fra_feature_id,
                fra.rag_status      AS fra_rag,
                fra.risk_rating     AS fra_raw_rating,
                fra.assessment_date AS fra_date,
                fra.assessment_valid_until,
                fra.is_in_date,
                fra.assessor_name,
                fra.assessor_company,
                COALESCE(fra.total_action_count, 0)      AS total_actions,
                COALESCE(fra.overdue_action_count, 0)    AS overdue_actions,
                COALESCE(fra.no_date_action_count, 0)    AS no_date_actions,
                COALESCE(fra.outstanding_action_count, 0) AS outstanding_actions,
                fra.evacuation_strategy,
                fra.evacuation_strategy_changed,
                fra.has_sprinkler_system,
                fra.has_fire_alarm_system,
                fra.has_fire_doors,
                fra.has_compartmentation,
                fra.has_emergency_lighting,
                fra.bsa_2022_applicable,
                fra.mandatory_occurrence_noted,
                fra.fra_assessment_type,
                fra.significant_findings,
                fra.action_items,
                fra.extraction_confidence,

                fraew.feature_id::text AS fraew_feature_id,
                fraew.rag_status    AS fraew_rag,
                fraew.has_combustible_cladding,
                fraew.has_remedial_actions AS fraew_remediation

            FROM silver.blocks b

            LEFT JOIN LATERAL (
                SELECT *
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST, created_at DESC
                LIMIT 1
            ) fra ON TRUE

            LEFT JOIN LATERAL (
                SELECT feature_id, rag_status, has_combustible_cladding, has_remedial_actions
                FROM silver.fraew_features
                WHERE block_id = b.block_id
                ORDER BY created_at DESC
                LIMIT 1
            ) fraew ON TRUE

            WHERE b.ha_id = $1
              {rag_clause}
            ORDER BY
                CASE fra.rag_status
                    WHEN 'RED'   THEN 1
                    WHEN 'AMBER' THEN 2
                    WHEN 'GREEN' THEN 3
                    ELSE 4
                END,
                b.height_max_m DESC NULLS LAST,
                b.name
            """,
            ha_id,
        )

        result_rows = [dict(r) for r in rows]
        summary = {
            "RED": sum(1 for r in result_rows if r.get("fra_rag") == "RED"),
            "AMBER": sum(1 for r in result_rows if r.get("fra_rag") == "AMBER"),
            "GREEN": sum(1 for r in result_rows if r.get("fra_rag") == "GREEN"),
            "unassessed": sum(1 for r in result_rows if r.get("fra_rag") is None),
        }

        return {
            "portfolio_id": portfolio_id,
            "ha_id": ha_id,
            "portfolio_name": portfolio["portfolio_name"],
            "total_blocks": len(result_rows),
            "rag_summary": summary,
            "blocks": result_rows,
        }


# ===========================================================================
# 6. FRAEW Blocks Table
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/fraew-blocks")
async def fraew_blocks(
    portfolio_id: str,
    rag_filter: Optional[str] = None,
    combustible_only: bool = False,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        filters = ["b.ha_id = $1"]
        if rag_filter == "unassessed":
            filters.append("fraew.rag_status IS NULL")
        elif rag_filter in ("RED", "AMBER", "GREEN"):
            filters.append(f"fraew.rag_status = '{rag_filter}'")
        if combustible_only:
            filters.append("fraew.has_combustible_cladding = TRUE")

        where = "WHERE " + " AND ".join(filters)

        rows = await conn.fetch(
            f"""
            SELECT
                b.block_id::text,
                b.name                  AS block_name,
                b.unit_count,
                b.height_max_m,
                b.total_sum_insured,

                fraew.fraew_id::text,
                fraew.feature_id::text  AS fraew_feature_id,
                fraew.report_reference,
                fraew.assessment_date   AS fraew_date,
                fraew.assessment_valid_until,
                fraew.is_in_date,
                fraew.assessor_name,
                fraew.assessor_company,
                fraew.clause_14_applied,
                fraew.pas_9980_version,
                fraew.pas_9980_compliant,

                fraew.rag_status        AS fraew_rag,
                fraew.building_risk_rating AS fraew_raw_rating,

                fraew.building_height_m,
                fraew.building_height_category,
                fraew.num_storeys       AS fraew_storeys,
                fraew.num_units,
                fraew.construction_frame_type,
                fraew.external_wall_base_construction,
                fraew.retrofit_year,

                fraew.has_combustible_cladding,
                fraew.eps_insulation_present,
                fraew.mineral_wool_insulation_present,
                fraew.pir_insulation_present,
                fraew.phenolic_insulation_present,
                fraew.acrylic_render_present,
                fraew.cement_render_present,

                fraew.cavity_barriers_present,
                fraew.cavity_barriers_windows,
                fraew.cavity_barriers_floors,
                fraew.fire_breaks_floor_level,
                fraew.fire_breaks_party_walls,
                fraew.dry_riser_present,
                fraew.wet_riser_present,
                fraew.evacuation_strategy,

                fraew.bs8414_test_evidence,
                fraew.br135_criteria_met,
                fraew.adb_compliant,

                fraew.interim_measures_required,
                fraew.interim_measures_detail,
                fraew.has_remedial_actions,
                fraew.remedial_actions,
                fraew.wall_types,

                fraew.height_survey_recommended,
                fraew.fire_door_survey_recommended,
                fraew.intrusive_investigation_recommended,
                fraew.asbestos_suspected,

                fraew.extraction_confidence,

                fra.feature_id::text    AS fra_feature_id,
                fra.rag_status          AS fra_rag

            FROM silver.blocks b

            LEFT JOIN LATERAL (
                SELECT *
                FROM silver.fraew_features
                WHERE block_id = b.block_id
                ORDER BY created_at DESC
                LIMIT 1
            ) fraew ON TRUE

            LEFT JOIN LATERAL (
                SELECT feature_id, rag_status
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST
                LIMIT 1
            ) fra ON TRUE

            {where}
            ORDER BY
                CASE fraew.rag_status
                    WHEN 'RED'   THEN 1
                    WHEN 'AMBER' THEN 2
                    WHEN 'GREEN' THEN 3
                    ELSE 4
                END,
                fraew.has_combustible_cladding DESC NULLS LAST,
                b.height_max_m DESC NULLS LAST,
                b.name
            """,
            ha_id,
        )

        result_rows = [dict(r) for r in rows]
        summary = {
            "RED": sum(1 for r in result_rows if r.get("fraew_rag") == "RED"),
            "AMBER": sum(1 for r in result_rows if r.get("fraew_rag") == "AMBER"),
            "GREEN": sum(1 for r in result_rows if r.get("fraew_rag") == "GREEN"),
            "unassessed": sum(1 for r in result_rows if r.get("fraew_rag") is None),
            "combustible_cladding": sum(1 for r in result_rows if r.get("has_combustible_cladding")),
            "no_bs8414_evidence": sum(
                1 for r in result_rows
                if r.get("bs8414_test_evidence") is False and r.get("has_combustible_cladding")
            ),
        }

        return {
            "portfolio_id": portfolio_id,
            "ha_id": ha_id,
            "portfolio_name": portfolio["portfolio_name"],
            "total_blocks": len(result_rows),
            "fraew_summary": summary,
            "blocks": result_rows,
        }


# ===========================================================================
# 7. Risk Summary
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/risk-summary")
async def risk_summary(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        fra_stats = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT b.block_id)                          AS total_blocks,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.fra_id IS NOT NULL
                )                                                   AS blocks_with_fra,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.is_in_date = TRUE
                )                                                   AS fra_in_date,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fra.is_in_date = FALSE
                )                                                   AS fra_out_of_date,
                COALESCE(SUM(fra.total_action_count), 0)::bigint    AS total_actions,
                COALESCE(SUM(fra.overdue_action_count), 0)::bigint  AS overdue_actions,
                COALESCE(SUM(fra.no_date_action_count), 0)::bigint  AS no_date_actions,
                COALESCE(SUM(fra.outstanding_action_count), 0)::bigint AS outstanding_actions,
                COALESCE(SUM(fra.high_priority_action_count), 0)::bigint AS high_priority_actions

            FROM silver.blocks b
            LEFT JOIN LATERAL (
                SELECT fra_id, rag_status, is_in_date,
                       total_action_count, overdue_action_count, no_date_action_count,
                       outstanding_action_count, high_priority_action_count
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST, created_at DESC
                LIMIT 1
            ) fra ON TRUE
            WHERE b.ha_id = $1
            """,
            ha_id,
        )

        fraew_stats = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.fraew_id IS NOT NULL
                )                                                   AS blocks_with_fraew,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.has_combustible_cladding = TRUE
                )                                                   AS combustible_blocks,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.bs8414_test_evidence = FALSE
                      AND fraew.has_combustible_cladding = TRUE
                )                                                   AS no_bs8414_combustible,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.clause_14_applied = TRUE
                )                                                   AS clause_14_used,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.interim_measures_required = TRUE
                )                                                   AS interim_measures_required,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.asbestos_suspected = TRUE
                )                                                   AS asbestos_suspected,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.height_survey_recommended = TRUE
                )                                                   AS height_survey_needed

            FROM silver.blocks b
            LEFT JOIN LATERAL (
                SELECT fraew_id, has_combustible_cladding, bs8414_test_evidence,
                       clause_14_applied, interim_measures_required,
                       asbestos_suspected, height_survey_recommended
                FROM silver.fraew_features
                WHERE block_id = b.block_id
                ORDER BY created_at DESC
                LIMIT 1
            ) fraew ON TRUE
            WHERE b.ha_id = $1
            """,
            ha_id,
        )

        urgent_blocks = await conn.fetch(
            """
            SELECT
                b.block_id::text,
                b.name          AS block_name,
                b.unit_count,
                b.height_max_m,
                fra.feature_id::text AS fra_feature_id,
                fra.rag_status  AS fra_rag,
                fra.overdue_action_count,
                fra.assessment_date AS fra_date,
                fra.assessment_valid_until,
                fraew.feature_id::text AS fraew_feature_id,
                fraew.rag_status AS fraew_rag,
                fraew.has_combustible_cladding
            FROM silver.blocks b
            LEFT JOIN LATERAL (
                SELECT feature_id, rag_status, overdue_action_count,
                       assessment_date, assessment_valid_until
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST
                LIMIT 1
            ) fra ON TRUE
            LEFT JOIN LATERAL (
                SELECT feature_id, rag_status, has_combustible_cladding
                FROM silver.fraew_features
                WHERE block_id = b.block_id
                ORDER BY created_at DESC
                LIMIT 1
            ) fraew ON TRUE
            WHERE b.ha_id = $1
              AND (
                  fra.rag_status = 'RED'
                  OR fraew.rag_status = 'RED'
                  OR COALESCE(fra.overdue_action_count, 0) > 0
              )
            ORDER BY
                CASE WHEN fra.rag_status = 'RED' OR fraew.rag_status = 'RED' THEN 0 ELSE 1 END,
                COALESCE(fra.overdue_action_count, 0) DESC,
                b.height_max_m DESC NULLS LAST
            """,
            ha_id,
        )

        fra = dict(fra_stats)
        fraew = dict(fraew_stats)
        total = fra.get("total_blocks", 0)
        assessed = fra.get("blocks_with_fra", 0)
        in_date = fra.get("fra_in_date", 0)
        overdue = fra.get("overdue_actions", 0)

        score = 100.0
        if total > 0:
            score -= (total - assessed) / total * 30
            score -= (assessed - in_date) / total * 20
            if overdue > 0:
                score -= min(overdue * 2, 20)
            score = max(0.0, round(score, 1))

        return {
            "portfolio_id": portfolio_id,
            "ha_id": ha_id,
            "portfolio_name": portfolio["portfolio_name"],
            "compliance_score": score,
            "fra": fra,
            "fraew": fraew,
            "urgent_blocks": [dict(r) for r in urgent_blocks],
        }


# ===========================================================================
# 8. Doc A / Doc B Completeness
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/doc-completeness")
async def doc_completeness(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        doc_a_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*)                                            AS total_properties,
                ROUND(AVG(CASE WHEN property_reference   IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_property_reference,
                ROUND(AVG(CASE WHEN block_reference      IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_block_reference,
                ROUND(AVG(CASE WHEN occupancy_type       IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_occupancy_type,
                ROUND(AVG(CASE WHEN address              IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_address,
                ROUND(AVG(CASE WHEN postcode             IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_postcode,
                ROUND(AVG(CASE WHEN units                IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_units,
                ROUND(AVG(CASE WHEN sum_insured          IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_sum_insured,
                ROUND(AVG(CASE WHEN wall_construction    IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_wall_construction,
                ROUND(AVG(CASE WHEN roof_construction    IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_roof_construction,
                ROUND(AVG(CASE WHEN year_of_build        IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_year_of_build,
                ROUND(AVG(CASE WHEN age_banding          IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_age_banding,
                ROUND(AVG(CASE WHEN storeys              IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_storeys,
                ROUND(AVG(CASE WHEN is_listed            IS NOT NULL THEN 1.0 ELSE 0.0 END), 3) AS f_is_listed
            FROM silver.properties
            WHERE ha_id = $1
            """,
            ha_id,
        )

        doc_a_fields = [
            "property_reference", "block_reference", "occupancy_type", "address",
            "postcode", "units", "sum_insured", "wall_construction", "roof_construction",
            "year_of_build", "age_banding", "storeys", "is_listed",
        ]
        doc_a_detail = {f: float(doc_a_row[f"f_{f}"]) for f in doc_a_fields}
        doc_a_pct = round(sum(doc_a_detail.values()) / len(doc_a_fields) * 100, 1)

        doc_b_rows = await conn.fetch(
            """
            SELECT
                b.block_id,
                CASE WHEN b.name                IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_block_name,
                CASE WHEN b.unit_count          IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_unit_count,
                CASE WHEN b.total_sum_insured   IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_sum_insured,
                CASE WHEN b.max_storeys         IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_storeys,
                CASE WHEN b.height_max_m        IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_height,
                CASE WHEN b.predominant_wall    IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_wall,
                CASE WHEN b.predominant_roof    IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_roof,
                CASE WHEN b.is_listed           IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_is_listed,
                CASE WHEN fra.assessment_date       IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_fra_date,
                CASE WHEN fra.has_sprinkler_system  IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_sprinklers,
                CASE WHEN fra.has_fire_alarm_system IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_fire_alarms,
                CASE WHEN fraew.has_combustible_cladding IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_combustible,
                CASE WHEN fraew.has_remedial_actions     IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_remedial,
                CASE WHEN fraew.building_height_m        IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_fraew_height,
                CASE WHEN fraew.pas_9980_compliant       IS NOT NULL THEN 1.0 ELSE 0.0 END AS f_pas9980

            FROM silver.blocks b

            LEFT JOIN LATERAL (
                SELECT assessment_date, has_sprinkler_system, has_fire_alarm_system
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST, created_at DESC
                LIMIT 1
            ) fra ON TRUE

            LEFT JOIN LATERAL (
                SELECT has_combustible_cladding, has_remedial_actions,
                       building_height_m, pas_9980_compliant
                FROM silver.fraew_features
                WHERE block_id = b.block_id
                ORDER BY created_at DESC
                LIMIT 1
            ) fraew ON TRUE

            WHERE b.ha_id = $1
            """,
            ha_id,
        )

        doc_b_field_keys = [
            "block_name", "unit_count", "sum_insured", "storeys", "height",
            "wall", "roof", "is_listed",
            "fra_date", "sprinklers", "fire_alarms",
            "combustible", "remedial", "fraew_height", "pas9980",
        ]

        if doc_b_rows:
            doc_b_detail = {
                k: round(sum(float(r[f"f_{k}"]) for r in doc_b_rows) / len(doc_b_rows), 3)
                for k in doc_b_field_keys
            }
            doc_b_pct = round(sum(doc_b_detail.values()) / len(doc_b_field_keys) * 100, 1)
        else:
            doc_b_detail = {k: 0.0 for k in doc_b_field_keys}
            doc_b_pct = 0.0

        return {
            "portfolio_id": portfolio_id,
            "ha_id": ha_id,
            "portfolio_name": portfolio["portfolio_name"],
            "doc_a": {
                "total_properties": doc_a_row["total_properties"],
                "total_fields": len(doc_a_fields),
                "completeness_pct": doc_a_pct,
                "field_detail": doc_a_detail,
            },
            "doc_b": {
                "total_blocks": len(doc_b_rows),
                "total_fields": len(doc_b_field_keys),
                "completeness_pct": doc_b_pct,
                "field_detail": doc_b_detail,
            },
        }


# ===========================================================================
# 9. Fire documents for dashboard
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/fire-documents")
async def fire_documents(
    portfolio_id: str,
    block_id: Optional[str] = Query(default=None),
    property_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    """
    Latest FRA/FRAEW documents exposed in a frontend-friendly shape.

    Optional filters:
      - block_id
      - property_id

    Returns one row per block/property context with nested FRA/FRAEW data.
    """
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        where_clauses = ["b.ha_id = $1"]
        params: List[Any] = [ha_id]
        param_index = 2

        if block_id:
            where_clauses.append(f"b.block_id::text = ${param_index}")
            params.append(block_id)
            param_index += 1

        if property_id:
            where_clauses.append(f"p.property_id::text = ${param_index}")
            params.append(property_id)
            param_index += 1

        params.append(limit)
        limit_param = f"${param_index}"

        rows = await conn.fetch(
            f"""
            SELECT
                b.block_id::text                       AS block_id,
                b.name                                AS block_name,
                p.property_id::text                   AS property_id,
                p.property_reference,
                p.address,
                p.postcode,

                fra.feature_id::text                  AS fra_feature_id,
                fra.fra_id::text                      AS fra_id,
                fra.assessment_date                   AS fra_assessment_date,
                fra.assessment_valid_until            AS fra_assessment_valid_until,
                fra.is_in_date                        AS fra_is_in_date,
                fra.rag_status                        AS fra_rag,
                fra.risk_rating                       AS fra_raw_rating,
                fra.assessor_name                     AS fra_assessor_name,
                fra.assessor_company                  AS fra_assessor_company,
                fra.evacuation_strategy               AS fra_evacuation_strategy,
                fra.has_fire_alarm_system             AS fra_has_fire_alarm_system,
                fra.has_smoke_detection               AS fra_has_smoke_detection,
                fra.has_sprinkler_system              AS fra_has_sprinkler_system,
                fra.has_fire_doors                    AS fra_has_fire_doors,
                fra.has_compartmentation              AS fra_has_compartmentation,
                fra.significant_findings              AS fra_significant_findings,
                fra.action_items                      AS fra_action_items,
                fra.total_action_count                AS fra_total_action_count,
                fra.overdue_action_count              AS fra_overdue_action_count,
                fra.outstanding_action_count          AS fra_outstanding_action_count,
                fra.extraction_confidence             AS fra_extraction_confidence,

                fraew.feature_id::text                AS fraew_feature_id,
                fraew.fraew_id::text                  AS fraew_id,
                fraew.assessment_date                 AS fraew_assessment_date,
                fraew.assessment_valid_until          AS fraew_assessment_valid_until,
                fraew.is_in_date                      AS fraew_is_in_date,
                fraew.rag_status                      AS fraew_rag,
                fraew.building_risk_rating            AS fraew_raw_rating,
                fraew.assessor_name                   AS fraew_assessor_name,
                fraew.assessor_company                AS fraew_assessor_company,
                fraew.building_height_m               AS fraew_building_height_m,
                fraew.building_height_category        AS fraew_building_height_category,
                fraew.num_storeys                     AS fraew_num_storeys,
                fraew.num_units                       AS fraew_num_units,
                fraew.construction_frame_type         AS fraew_construction_frame_type,
                fraew.external_wall_base_construction AS fraew_external_wall_base_construction,
                fraew.pas_9980_version                AS fraew_pas_9980_version,
                fraew.pas_9980_compliant              AS fraew_pas_9980_compliant,
                fraew.interim_measures_required       AS fraew_interim_measures_required,
                fraew.interim_measures_detail         AS fraew_interim_measures_detail,
                fraew.has_remedial_actions            AS fraew_has_remedial_actions,
                fraew.remedial_actions                AS fraew_remedial_actions,
                fraew.wall_types                      AS fraew_wall_types,
                fraew.has_combustible_cladding        AS fraew_has_combustible_cladding,
                fraew.eps_insulation_present          AS fraew_eps_insulation_present,
                fraew.mineral_wool_insulation_present AS fraew_mineral_wool_insulation_present,
                fraew.pir_insulation_present          AS fraew_pir_insulation_present,
                fraew.phenolic_insulation_present     AS fraew_phenolic_insulation_present,
                fraew.acrylic_render_present          AS fraew_acrylic_render_present,
                fraew.cement_render_present           AS fraew_cement_render_present,
                fraew.cavity_barriers_present         AS fraew_cavity_barriers_present,
                fraew.dry_riser_present               AS fraew_dry_riser_present,
                fraew.wet_riser_present               AS fraew_wet_riser_present,
                fraew.evacuation_strategy             AS fraew_evacuation_strategy,
                fraew.adb_compliant                   AS fraew_adb_compliant,
                fraew.bs8414_test_evidence            AS fraew_bs8414_test_evidence,
                fraew.br135_criteria_met              AS fraew_br135_criteria_met,
                fraew.extraction_confidence           AS fraew_extraction_confidence

            FROM silver.blocks b
            LEFT JOIN silver.properties p
              ON p.ha_id = b.ha_id
             AND p.block_reference = b.name

            LEFT JOIN LATERAL (
                SELECT *
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST, created_at DESC
                LIMIT 1
            ) fra ON TRUE

            LEFT JOIN LATERAL (
                SELECT *
                FROM silver.fraew_features
                WHERE block_id = b.block_id
                ORDER BY created_at DESC
                LIMIT 1
            ) fraew ON TRUE

            WHERE {" AND ".join(where_clauses)}
            ORDER BY b.name, p.property_reference NULLS LAST
            LIMIT {limit_param}
            """,
            *params,
        )

        items = [_build_fire_document_payload(dict(r)) for r in rows]

        return {
            "portfolio_id": portfolio_id,
            "ha_id": ha_id,
            "portfolio_name": portfolio["portfolio_name"],
            "block_id": block_id,
            "property_id": property_id,
            "count": len(items),
            "items": items,
        }