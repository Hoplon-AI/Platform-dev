"""
underwriter_router.py
---------------------
Underwriter Dashboard API endpoints.

Provides portfolio-level analytics for underwriters:
  GET /api/v1/underwriter/portfolios              — dropdown list with KPI badges
  GET /api/v1/underwriter/portfolios/{id}/summary — KPI header cards
  GET /api/v1/underwriter/portfolios/{id}/composition — property type breakdown
  GET /api/v1/underwriter/portfolios/{id}/map     — block map markers (RAG colour coded)
  GET /api/v1/underwriter/portfolios/{id}/fra-blocks  — FRA status per block
  GET /api/v1/underwriter/portfolios/{id}/fraew-blocks — FRAEW detail per block

Design notes:
- Queries use ha_id (resolved from portfolio_id) for all silver.* table joins because
  ha_demo properties/blocks have no portfolio_id set (orphan linkage issue).
- Map coordinates: use lat/lon if present, otherwise convert x_coordinate/y_coordinate
  (OS National Grid OSGB36 EPSG:27700) to WGS84 (EPSG:4326) via PostGIS ST_Transform.
- FRA/FRAEW status: LATERAL JOINs directly to fra_features/fraew_features ordered by
  assessment_date DESC — does NOT rely on blocks.fra_status denormalisation (which is
  currently NULL for ha_demo blocks).
- Map colour rule: worst of FRA and FRAEW RAG. GREY = unassessed.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.database.db_pool import DatabasePool
from backend.core.tenancy.tenant_middleware import TenantMiddleware

router = APIRouter(prefix="/api/v1/underwriter", tags=["underwriter"])

security = HTTPBearer(auto_error=False)
tenant_middleware = TenantMiddleware()


# ---------------------------------------------------------------------------
# Auth dependency (same pattern as portfolios_router.py)
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
# 1. Portfolio Dropdown
# ===========================================================================

@router.get("/portfolios", response_model=List[Dict[str, Any]])
async def list_portfolios(
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> List[Dict[str, Any]]:
    """
    Portfolio dropdown — returns all portfolios with badge KPIs.

    Each entry includes:
      - portfolio_id, ha_id, portfolio_name, renewal_year, ha_name
      - block_count, total_units, total_insured_value (£)
      - fra_red_count, fra_amber_count, fra_green_count, fra_unassessed_count
      - fraew_assessed_count, fraew_unassessed_count
      - has_combustible_cladding_blocks (bool)
    """
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                po.portfolio_id::text,
                po.ha_id,
                po.name          AS portfolio_name,
                po.renewal_year,
                ha.name          AS ha_name,

                -- Block counts
                COUNT(DISTINCT b.block_id)                          AS block_count,
                COALESCE(SUM(b.unit_count), 0)::bigint              AS total_units,
                COALESCE(SUM(b.total_sum_insured), 0)               AS total_insured_value,

                -- FRA RAG from direct join (not denormalised fra_status)
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

                -- FRAEW coverage
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.rag_status IS NOT NULL
                )                                                   AS fraew_assessed_count,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.rag_status IS NULL
                )                                                   AS fraew_unassessed_count,

                -- Combustible cladding flag
                BOOL_OR(fraew.has_combustible_cladding = TRUE)      AS has_combustible_cladding_blocks

            FROM silver.portfolios po
            JOIN public.housing_associations ha ON ha.ha_id = po.ha_id
            LEFT JOIN silver.blocks b ON b.ha_id = po.ha_id

            -- Latest FRA per block (LATERAL)
            LEFT JOIN LATERAL (
                SELECT rag_status
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST, created_at DESC
                LIMIT 1
            ) fra ON TRUE

            -- Latest FRAEW per block (LATERAL)
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
# 2. Portfolio Summary — KPI Header Cards
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/summary")
async def portfolio_summary(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    """
    KPI header cards for a portfolio:
      - Total Insured Value
      - Block / unit counts
      - FRA RAG distribution (RED/AMBER/GREEN/unassessed)
      - FRAEW coverage (assessed/unassessed)
      - Height distribution (under_11m / 11-18m / 18-30m / over_30m)
      - Combustible cladding exposure
      - Enrichment coverage
    """
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        row = await conn.fetchrow(
            """
            SELECT
                -- Portfolio identity
                $2::text                                            AS ha_id,
                $1::text                                            AS portfolio_id,

                -- Block & unit totals
                COUNT(DISTINCT b.block_id)                          AS total_blocks,
                COALESCE(SUM(b.unit_count), 0)::bigint              AS total_units,
                COALESCE(SUM(b.total_sum_insured), 0)               AS total_insured_value,

                -- Property count (direct from silver.properties by ha_id)
                (SELECT COUNT(*) FROM silver.properties WHERE ha_id = $2)::bigint
                                                                    AS total_properties,

                -- Enrichment
                (SELECT COUNT(*) FROM silver.properties WHERE ha_id = $2 AND enrichment_status = 'enriched')::bigint
                                                                    AS enriched_properties,
                (SELECT COUNT(*) FROM silver.properties WHERE ha_id = $2 AND enrichment_status = 'pending')::bigint
                                                                    AS pending_properties,

                -- FRA RAG distribution
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

                -- FRAEW coverage
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

                -- Combustible cladding exposure
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.has_combustible_cladding = TRUE
                )                                                   AS combustible_cladding_blocks,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.eps_insulation_present = TRUE
                )                                                   AS eps_insulation_blocks,
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE fraew.aluminium_composite_cladding = TRUE
                )                                                   AS acm_cladding_blocks,

                -- Height bands
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

                -- Listed buildings
                COUNT(DISTINCT b.block_id) FILTER (
                    WHERE b.is_listed = TRUE
                )                                                   AS listed_blocks

            FROM silver.blocks b

            LEFT JOIN LATERAL (
                SELECT rag_status
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST, created_at DESC
                LIMIT 1
            ) fra ON TRUE

            LEFT JOIN LATERAL (
                SELECT rag_status, has_combustible_cladding,
                       eps_insulation_present, aluminium_composite_cladding
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
            "ha_name":        portfolio["ha_name"],
            "renewal_year":   portfolio["renewal_year"],
        })
        return result


# ===========================================================================
# 3. Portfolio Composition — Property Type Breakdown
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/composition")
async def portfolio_composition(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    """
    Portfolio composition breakdown:
      - houses / flats / blocks by count and unit count
      - wall / roof construction distribution
      - age banding distribution
      - occupancy type distribution
    """
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        # ── 1. BY TENANCY / OWNERSHIP ────────────────────────────────────────
        # occupancy_type → units + sum_insured
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

        # ── 2. BY BLOCK REFERENCE ────────────────────────────────────────────
        # Two rows as shown in wireframe:
        #   Row A — properties with no block_reference ("No block")
        #   Row B — summary of all blocks (count, units, TIV, >£5M badge count)
        # Plus individual block rows for drill-down.
        block_summary = await conn.fetchrow(
            """
            SELECT
                -- Properties NOT in any block
                COUNT(*) FILTER (WHERE block_reference IS NULL)::integer
                                                            AS no_block_units,
                COALESCE(SUM(sum_insured) FILTER (WHERE block_reference IS NULL), 0)
                                                            AS no_block_tiv,

                -- Properties IN a block
                COUNT(DISTINCT block_reference) FILTER (WHERE block_reference IS NOT NULL)::integer
                                                            AS block_count,
                COUNT(*) FILTER (WHERE block_reference IS NOT NULL)::integer
                                                            AS block_units,
                COALESCE(SUM(sum_insured) FILTER (WHERE block_reference IS NOT NULL), 0)
                                                            AS block_tiv
            FROM silver.properties
            WHERE ha_id = $1
            """,
            ha_id,
        )

        # Individual blocks — for the >£5M count and the detail list
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

        # ── 3. BY PROPERTY TYPE ──────────────────────────────────────────────
        # Use avid_property_type (Flat / House/Bungalow / Garage / Commercial)
        # which has meaningful values; property_type is always "Housing Association"
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

        # ── 4. BY AGE BANDING ────────────────────────────────────────────────
        # Canonical order: Pre-1919 → 1920-1944 → 1945-1979 → 1980-2000 → 2001+
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

        # ── 5. Portfolio Composition widget — responsible_party split ────────
        # Powers the top card: Houses / Flats (HA-controlled vs third-party)
        # / Blocks (HA responsible vs third-party managed)
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

        # Build the nested structure the frontend needs for the progress-bar card
        comp: Dict[str, Any] = {}
        for r in composition_rows:
            pt  = r["property_type"]
            rp  = r["responsible_party"]
            if pt not in comp:
                comp[pt] = {"property_type": pt, "total_units": 0,
                            "total_sum_insured": 0, "ha_controlled": 0,
                            "third_party": 0, "ha_controlled_tiv": 0,
                            "third_party_tiv": 0}
            comp[pt]["total_units"]      += r["units"]
            comp[pt]["total_sum_insured"] = float(comp[pt]["total_sum_insured"]) + float(r["sum_insured"])
            if rp == "third_party":
                comp[pt]["third_party"]     += r["units"]
                comp[pt]["third_party_tiv"]  = float(comp[pt]["third_party_tiv"]) + float(r["sum_insured"])
            else:
                comp[pt]["ha_controlled"]     += r["units"]
                comp[pt]["ha_controlled_tiv"]  = float(comp[pt]["ha_controlled_tiv"]) + float(r["sum_insured"])

        # ── Totals row (for footer) ──────────────────────────────────────────
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

        total_units = totals["total_units"] or 1  # avoid div/0

        # Add % of total to each composition entry
        for v in comp.values():
            v["pct"] = round(v["total_units"] / total_units * 100, 1)

        # Third-party warning callout
        third_party_flats  = comp.get("Flat",  {}).get("third_party", 0)
        third_party_blocks = sum(
            v["third_party"] for k, v in comp.items()
            if k not in ("Flat",)
        )

        return {
            "portfolio_id":   portfolio_id,
            "ha_id":          ha_id,
            "portfolio_name": portfolio["portfolio_name"],
            "ha_name":        portfolio["ha_name"],
            "totals": {
                "units":       totals["total_units"],
                "sum_insured": totals["total_sum_insured"],
            },
            # ── Portfolio Composition widget (top card) ──────────────────────
            "portfolio_composition": {
                "total_units":          totals["total_units"],
                "breakdown":            list(comp.values()),
                # Warning callout: "X flats in Y third-party blocks"
                "third_party_flat_units":   third_party_flats,
                "third_party_block_count":  third_party_blocks,
                "has_third_party_warning":  third_party_flats > 0 or third_party_blocks > 0,
            },
            # ── Portfolio Analysis section (4 tables) ────────────────────────
            "by_tenancy":       [dict(r) for r in tenancy_rows],
            "by_block": {
                "no_block_units":   block_summary["no_block_units"],
                "no_block_tiv":     block_summary["no_block_tiv"],
                "block_count":      block_summary["block_count"],
                "block_units":      block_summary["block_units"],
                "block_tiv":        block_summary["block_tiv"],
                "blocks_over_5m":   blocks_over_5m,
                "blocks":           [dict(r) for r in block_rows],
            },
            "by_property_type": [dict(r) for r in type_rows],
            "by_age_banding":   [dict(r) for r in age_rows],
        }


# ===========================================================================
# 4. Portfolio Map — Block Markers with RAG Colour Coding
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/map")
async def portfolio_map(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    """
    Map markers — one entry per block with coordinates and RAG colour.

    Coordinate strategy (in priority order):
      1. AVG(property.latitude / longitude) — direct WGS84
      2. PostGIS ST_Transform of AVG(property.x_coordinate / y_coordinate)
         from OSGB36 (EPSG:27700) to WGS84 (EPSG:4326)
      Blocks with no coordinates are excluded.

    Colour coding (worst of FRA and FRAEW):
      red    — FRA RED or FRAEW RED (highest risk)
      amber  — FRA AMBER or FRAEW AMBER
      green  — FRA GREEN (and FRAEW GREEN or no FRAEW)
      grey   — no FRA or FRAEW assessment yet
    """
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        rows = await conn.fetch(
            """
            WITH block_coords AS (
                -- Aggregate property coordinates per block_reference → match block by name
                SELECT
                    p.block_reference,
                    p.ha_id,
                    -- WGS84 direct (ha_albyn)
                    AVG(p.latitude)      AS lat_direct,
                    AVG(p.longitude)     AS lon_direct,
                    -- OS Grid easting/northing (ha_demo enriched)
                    AVG(p.x_coordinate)  AS avg_easting,
                    AVG(p.y_coordinate)  AS avg_northing,
                    -- Best address for tooltip
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

                -- Resolve coordinates: prefer direct WGS84, fallback to PostGIS conversion
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

                -- FRA detail
                fra.rag_status          AS fra_rag,
                fra.risk_rating         AS fra_raw_rating,
                fra.assessment_date     AS fra_date,
                fra.assessment_valid_until AS fra_valid_until,
                fra.is_in_date          AS fra_is_in_date,
                fra.total_action_count,
                fra.overdue_action_count,

                -- FRAEW detail
                fraew.rag_status        AS fraew_rag,
                fraew.building_risk_rating  AS fraew_raw_rating,
                fraew.has_combustible_cladding,
                fraew.eps_insulation_present,
                fraew.aluminium_composite_cladding,
                fraew.has_remedial_actions,

                -- Map colour: worst of FRA and FRAEW
                CASE
                    WHEN fra.rag_status = 'RED'   OR fraew.rag_status = 'RED'   THEN 'red'
                    WHEN fra.rag_status = 'AMBER' OR fraew.rag_status = 'AMBER' THEN 'amber'
                    WHEN fra.rag_status = 'GREEN'
                         AND (fraew.rag_status = 'GREEN' OR fraew.rag_status IS NULL)
                                                                                 THEN 'green'
                    ELSE 'grey'
                END                     AS map_colour,

                -- Tooltip: combined risk label
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

            -- Coordinates from properties
            LEFT JOIN block_coords coords
                ON coords.block_reference = b.name
                AND coords.ha_id = b.ha_id

            -- Latest FRA per block
            LEFT JOIN LATERAL (
                SELECT
                    rag_status, risk_rating, assessment_date,
                    assessment_valid_until, is_in_date,
                    total_action_count, overdue_action_count
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST, created_at DESC
                LIMIT 1
            ) fra ON TRUE

            -- Latest FRAEW per block
            LEFT JOIN LATERAL (
                SELECT
                    rag_status, building_risk_rating, has_combustible_cladding,
                    eps_insulation_present, aluminium_composite_cladding,
                    has_remedial_actions
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

        # Summary counts for the map legend
        colour_counts = {"red": 0, "amber": 0, "green": 0, "grey": 0}
        for m in markers:
            colour_counts[m.get("map_colour", "grey")] += 1

        return {
            "portfolio_id":   portfolio_id,
            "ha_id":          ha_id,
            "portfolio_name": portfolio["portfolio_name"],
            "ha_name":        portfolio["ha_name"],
            "total_markers":  len(markers),
            "colour_counts":  colour_counts,
            "markers":        markers,
        }


# ===========================================================================
# 5. FRA Blocks Table
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/fra-blocks")
async def fra_blocks(
    portfolio_id: str,
    rag_filter: Optional[str] = None,   # RED | AMBER | GREEN | unassessed
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    """
    FRA status table — one row per block.

    Query params:
      ?rag_filter=RED     — only RED blocks
      ?rag_filter=AMBER   — only AMBER blocks
      ?rag_filter=GREEN   — only GREEN blocks
      ?rag_filter=unassessed — blocks with no FRA

    Returns per-block:
      block name, height, unit count, TIV,
      FRA RAG, risk rating, assessment date, valid until, in-date flag,
      action counts (total / overdue / no-date), evacuation strategy,
      key safety flags (sprinklers, fire alarms, fire doors),
      FRAEW rag (cross-reference column)
    """
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        # Build optional RAG filter
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

                -- FRA fields
                fra.fra_id::text,
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

                -- Cross-reference FRAEW
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
                SELECT rag_status, has_combustible_cladding, has_remedial_actions
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

        # Summary
        summary = {
            "RED":        sum(1 for r in result_rows if r.get("fra_rag") == "RED"),
            "AMBER":      sum(1 for r in result_rows if r.get("fra_rag") == "AMBER"),
            "GREEN":      sum(1 for r in result_rows if r.get("fra_rag") == "GREEN"),
            "unassessed": sum(1 for r in result_rows if r.get("fra_rag") is None),
        }

        return {
            "portfolio_id":   portfolio_id,
            "ha_id":          ha_id,
            "portfolio_name": portfolio["portfolio_name"],
            "total_blocks":   len(result_rows),
            "rag_summary":    summary,
            "blocks":         result_rows,
        }


# ===========================================================================
# 6. FRAEW Blocks Table
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/fraew-blocks")
async def fraew_blocks(
    portfolio_id: str,
    rag_filter: Optional[str] = None,   # RED | AMBER | GREEN | unassessed
    combustible_only: bool = False,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    """
    FRAEW detail table — one row per block with full PAS 9980:2022 fields.

    Query params:
      ?rag_filter=RED           — only RED blocks
      ?combustible_only=true    — only blocks with combustible cladding

    Returns per-block:
      block name, height, PAS 9980 compliance, RAG status,
      all cladding material flags (EPS, ACM, HPL, timber, PIR, phenolic),
      cavity barriers, BS 8414 / BR 135 test evidence,
      evacuation strategy, Clause 14 usage,
      recommended further actions flags
    """
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

                -- FRAEW document identity
                fraew.fraew_id::text,
                fraew.report_reference,
                fraew.assessment_date   AS fraew_date,
                fraew.is_in_date,
                fraew.assessor_name,
                fraew.assessor_company,
                fraew.clause_14_applied,
                fraew.pas_9980_version,
                fraew.pas_9980_compliant,

                -- Overall risk
                fraew.rag_status        AS fraew_rag,
                fraew.building_risk_rating AS fraew_raw_rating,

                -- Building description
                fraew.building_height_m,
                fraew.building_height_category,
                fraew.num_storeys       AS fraew_storeys,
                fraew.construction_frame_type,
                fraew.retrofit_year,

                -- Cladding flags (key underwriting signals)
                fraew.has_combustible_cladding,
                fraew.eps_insulation_present,
                fraew.mineral_wool_insulation_present,
                fraew.pir_insulation_present,
                fraew.phenolic_insulation_present,
                fraew.acrylic_render_present,
                fraew.cement_render_present,
                fraew.aluminium_composite_cladding,
                fraew.hpl_cladding_present,
                fraew.timber_cladding_present,

                -- Fire safety
                fraew.cavity_barriers_present,
                fraew.cavity_barriers_windows,
                fraew.cavity_barriers_floors,
                fraew.fire_breaks_floor_level,
                fraew.fire_breaks_party_walls,
                fraew.dry_riser_present,
                fraew.wet_riser_present,
                fraew.evacuation_strategy,

                -- Compliance tests
                fraew.bs8414_test_evidence,
                fraew.br135_criteria_met,
                fraew.adb_compliant,

                -- Interim & remediation
                fraew.interim_measures_required,
                fraew.interim_measures_detail,
                fraew.has_remedial_actions,

                -- Recommended actions flags
                fraew.height_survey_recommended,
                fraew.fire_door_survey_recommended,
                fraew.intrusive_investigation_recommended,
                fraew.asbestos_suspected,

                fraew.extraction_confidence,

                -- Cross-reference FRA
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
                SELECT rag_status
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
            "RED":                   sum(1 for r in result_rows if r.get("fraew_rag") == "RED"),
            "AMBER":                 sum(1 for r in result_rows if r.get("fraew_rag") == "AMBER"),
            "GREEN":                 sum(1 for r in result_rows if r.get("fraew_rag") == "GREEN"),
            "unassessed":            sum(1 for r in result_rows if r.get("fraew_rag") is None),
            "combustible_cladding":  sum(1 for r in result_rows if r.get("has_combustible_cladding")),
            "no_bs8414_evidence":    sum(1 for r in result_rows
                                         if r.get("bs8414_test_evidence") is False
                                         and r.get("has_combustible_cladding")),
        }

        return {
            "portfolio_id":   portfolio_id,
            "ha_id":          ha_id,
            "portfolio_name": portfolio["portfolio_name"],
            "total_blocks":   len(result_rows),
            "fraew_summary":  summary,
            "blocks":         result_rows,
        }


# ===========================================================================
# 7. Risk Summary — Combined FRA + FRAEW Compliance Overview
# ===========================================================================

@router.get("/portfolios/{portfolio_id}/risk-summary")
async def risk_summary(
    portfolio_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
) -> Dict[str, Any]:
    """
    Combined FRA + FRAEW compliance overview for the safety widget.

    Returns:
      - Overall compliance score (0–100)
      - In-date / overdue FRA counts
      - Action items summary (overdue / no-date / outstanding)
      - FRAEW: combustible exposure, BS 8414 gaps, Clause 14 usage
      - Blocks requiring urgent attention (RED + overdue actions)
    """
    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        portfolio = await _resolve_portfolio(conn, portfolio_id)
        ha_id = portfolio["ha_id"]

        # FRA compliance stats
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

        # FRAEW compliance stats
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

        # Blocks needing urgent attention (RED FRA or RED FRAEW, with overdue actions)
        urgent_blocks = await conn.fetch(
            """
            SELECT
                b.block_id::text,
                b.name          AS block_name,
                b.unit_count,
                b.height_max_m,
                fra.rag_status  AS fra_rag,
                fra.overdue_action_count,
                fra.assessment_date AS fra_date,
                fra.assessment_valid_until,
                fraew.rag_status AS fraew_rag,
                fraew.has_combustible_cladding
            FROM silver.blocks b
            LEFT JOIN LATERAL (
                SELECT rag_status, overdue_action_count,
                       assessment_date, assessment_valid_until
                FROM silver.fra_features
                WHERE block_id = b.block_id
                ORDER BY assessment_date DESC NULLS LAST
                LIMIT 1
            ) fra ON TRUE
            LEFT JOIN LATERAL (
                SELECT rag_status, has_combustible_cladding
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

        # Simple compliance score: penalise unassessed, RED, overdue
        assessed = fra.get("blocks_with_fra", 0)
        in_date = fra.get("fra_in_date", 0)
        red_blocks = 0  # compute from urgent_blocks
        overdue = fra.get("overdue_actions", 0)

        score = 100.0
        if total > 0:
            score -= (total - assessed) / total * 30        # -30 for unassessed
            score -= (assessed - in_date) / total * 20      # -20 for out of date
            if overdue > 0:
                score -= min(overdue * 2, 20)                # -2 per overdue action, max -20
            score = max(0.0, round(score, 1))

        return {
            "portfolio_id":      portfolio_id,
            "ha_id":             ha_id,
            "portfolio_name":    portfolio["portfolio_name"],
            "compliance_score":  score,
            "fra":               fra,
            "fraew":             fraew,
            "urgent_blocks":     [dict(r) for r in urgent_blocks],
        }
