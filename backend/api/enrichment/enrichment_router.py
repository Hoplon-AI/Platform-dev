"""
Enrichment Router — API endpoints for the underwriter dashboard.

POST /api/v1/enrich/{ha_id}         — Start enrichment
GET  /api/v1/enrich/{ha_id}/status  — Coverage stats (for dashboard widgets)
POST /api/v1/enrich/{ha_id}/blocks  — Re-run block detection only
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

import psycopg2
import psycopg2.extras

from backend.workers.enrichment_worker import enrich_portfolio, run_block_detection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/enrich", tags=["Enrichment"])

_active_jobs: dict[str, dict] = {}


class EnrichRequest(BaseModel):
    limit: int = Field(0, description="Max properties to enrich (0 = all)")


async def _run_background(ha_id: str, limit: int):
    _active_jobs[ha_id] = {"status": "running", "result": None}
    try:
        result = await enrich_portfolio(ha_id=ha_id, limit=limit)
        _active_jobs[ha_id] = {"status": "complete", "result": result}
    except Exception as exc:
        logger.error(f"Enrichment failed for {ha_id}: {exc}", exc_info=True)
        _active_jobs[ha_id] = {"status": "failed", "result": {"error": str(exc)}}


@router.post("/{ha_id}")
async def start_enrichment(ha_id: str, req: EnrichRequest, bg: BackgroundTasks):
    """Start enrichment for all pending properties. Runs in background."""
    if ha_id in _active_jobs and _active_jobs[ha_id]["status"] == "running":
        return {"ha_id": ha_id, "status": "already_running"}

    bg.add_task(_run_background, ha_id, req.limit)
    return {"ha_id": ha_id, "status": "started", "message": "Check /status for progress"}


@router.get("/{ha_id}/status")
async def enrichment_status(ha_id: str):
    """
    Enrichment coverage stats — powers the underwriter dashboard widgets.

    Returns:
      - job_status: running/complete/failed/no_job
      - counts: pending/enriched/failed property counts
      - coverage: field-level population percentages
      - blocks: how many blocks detected
      - total_si: total sum insured across portfolio
    """
    job = _active_jobs.get(ha_id)

    conn = psycopg2.connect(
        os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/platform_dev")
    )
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Status breakdown
            cur.execute("""
                SELECT enrichment_status, COUNT(*) as count
                FROM silver.properties WHERE ha_id = %s
                GROUP BY enrichment_status
            """, (ha_id,))
            counts = {r["enrichment_status"]: r["count"] for r in cur.fetchall()}

            # Field coverage (for dashboard progress bars)
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(uprn) as uprn,
                    COUNT(wall_construction) as wall,
                    COUNT(roof_construction) as roof,
                    COUNT(floor_construction) as floor,
                    COUNT(year_of_build) as year_of_build,
                    COUNT(height_max_m) as height,
                    COUNT(epc_rating) as epc,
                    COUNT(CASE WHEN is_listed IS NOT NULL THEN 1 END) as listed,
                    COUNT(sum_insured) as sum_insured,
                    COUNT(block_reference) as block_ref,
                    SUM(COALESCE(sum_insured, 0))::float as total_si
                FROM silver.properties WHERE ha_id = %s
            """, (ha_id,))
            raw = dict(cur.fetchone() or {})
            total = raw.get("total", 0)

            coverage = {}
            if total > 0:
                for field in ["uprn", "wall", "roof", "floor", "year_of_build",
                              "height", "epc", "listed", "sum_insured", "block_ref"]:
                    val = raw.get(field, 0) or 0
                    coverage[field] = {"count": val, "pct": round(100 * val / total, 1)}

            # Block count
            cur.execute("""
                SELECT COUNT(*) as blocks,
                       COALESCE(SUM(unit_count), 0) as units_in_blocks
                FROM silver.blocks WHERE ha_id = %s AND parent_uprn IS NOT NULL
            """, (ha_id,))
            blocks = dict(cur.fetchone() or {})
    finally:
        conn.close()

    return {
        "ha_id": ha_id,
        "job_status": job["status"] if job else "no_job",
        "job_result": job.get("result") if job else None,
        "counts": counts,
        "total_properties": total,
        "total_sum_insured": raw.get("total_si", 0),
        "field_coverage": coverage,
        "blocks": blocks,
    }


@router.post("/{ha_id}/blocks")
async def rerun_blocks(ha_id: str):
    """Re-run block detection without re-enriching."""
    try:
        result = run_block_detection(ha_id)
        return {"ha_id": ha_id, **result}
    except Exception as exc:
        raise HTTPException(500, str(exc))