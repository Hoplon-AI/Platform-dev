"""
Enrichment Worker — Populates silver.properties with API data after SoV ingestion.

Workflow:
  1. SoV processor writes rows with enrichment_status='pending'
  2. This worker picks up pending rows
  3. For each row: address+postcode → OS Places → UPRN → EPC + NGD + Listed
  4. API data fills ONLY NULL columns (SoV never overwritten)
  5. Block detection groups properties by PARENT_UPRN → updates silver.blocks
  6. Doc A/B exporters and dashboard read enriched data

PRIORITY RULE: SoV data is NEVER overwritten by API data.
  enrichment_worker only writes to columns where the existing value is NULL.

Rate limits: OS Places 600/min, EPC 5000/day, NGD 600/min
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
import traceback
from typing import Any
import concurrent.futures
import traceback

import psycopg2
import psycopg2.extras
logger = logging.getLogger(__name__)

# API keys from environment (set in .env or system)
DEFAULT_PLACES_KEY = os.getenv("OS_PLACES_API_KEY", "")
DEFAULT_NGD_KEY = os.getenv("OS_NGD_API_KEY", "")
DEFAULT_EPC_EMAIL = os.getenv("EPC_EMAIL", "")
DEFAULT_EPC_KEY = os.getenv("EPC_API_KEY", "")

RATE_LIMIT_DELAY_S = 0.25  # ~400 calls/min, within 600/min limit
EPC_DAILY_LIMIT = 5000
BATCH_COMMIT_SIZE = 50


def _get_db_conn():
    return psycopg2.connect(
        os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/platform_dev")
    )

def _api_call_with_retry(func, *args, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = func(*args)
            if result is not None:
                return result
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except Exception as exc:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.warning(f"  API retry failed: {exc}")
    return None

def _normalize_postcode(pc: str) -> str:
    """Normalize postcode: uppercase, single space before last 3 chars."""
    pc = pc.strip().upper().replace(" ", "")
    if len(pc) >= 5:
        return f"{pc[:-3]} {pc[-3:]}"
    return pc

def _batch_os_places_by_postcode(postcode: str, api_key: str) -> list[dict]:
    """Get ALL addresses for a postcode in ONE API call."""
    try:
        import requests
        url = "https://api.os.uk/search/places/v1/postcode"
        params = {"postcode": postcode, "key": api_key, "maxresults": 100}
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        results = []
        for r in data.get("results", []):
            entry = r.get("DPA") or r.get("LPI")
            if entry:
                results.append(entry)
        return results
    except Exception as exc:
        logger.warning(f"Postcode batch error for {postcode}: {exc}")
        return []


def _match_address_to_uprn(address: str, candidates: list[dict]) -> dict | None:
    """Find best matching UPRN from postcode batch."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    best_match = None
    best_score = 0.0
    addr_lower = address.lower().strip()
    for c in candidates:
        c_addr = (c.get("ADDRESS") or "").lower()
        addr_tokens = set(addr_lower.replace(",", " ").split())
        c_tokens = set(c_addr.replace(",", " ").split())
        if not addr_tokens or not c_tokens:
            continue
        overlap = len(addr_tokens & c_tokens) / max(len(addr_tokens), len(c_tokens))
        if overlap > best_score:
            best_score = overlap
            best_match = c
    return best_match if best_score > 0.3 else None


# ─────────────────────────────────────────────────────────────────
# API Wrappers — thin, call Igor's geo module
# ─────────────────────────────────────────────────────────────────

def _call_os_places(address: str, postcode: str, api_key: str) -> dict | None:
    """Address → UPRN + coordinates via OS Places API."""
    try:
        from backend.geo.uprn_maps.os_datahub_functions import get_uprn_from_address
        query = f"{address}, {postcode}" if postcode else address
        result = get_uprn_from_address(query, api_key)
        return result if isinstance(result, dict) else None
    except Exception as exc:
        logger.warning(f"OS Places error: {exc}")
        return None


def _call_epc(uprn: str, email: str, api_key: str) -> dict | None:
    """UPRN → most recent EPC certificate (England/Wales only)."""
    try:
        from backend.geo.uprn_maps.uprn_to_epc import get_epc_from_uprn
        result = get_epc_from_uprn(uprn, email, api_key)
        return result[0] if isinstance(result, list) and result else None
    except Exception as exc:
        logger.warning(f"EPC error for UPRN {uprn}: {exc}")
        return None


def _call_ngd_buildings(x: float, y: float, api_key: str) -> dict | None:
    """Coordinates → nearest building from NGD Buildings API."""
    try:
        from backend.geo.uprn_maps.uprn_to_height import get_building_from_coords
        result = get_building_from_coords(x, y, api_key)
        return result.get("properties", {}) if isinstance(result, dict) else None
    except Exception as exc:
        logger.warning(f"NGD error: {exc}")
        return None


def _call_listed(uprn: str, api_key: str) -> dict | None:
    """UPRN → listed building status (England or Scotland)."""
    try:
        from backend.geo.uprn_maps.uprn_to_listed import get_listed_building_status
        result = get_listed_building_status(uprn, api_key)
        return result if isinstance(result, dict) and result.get("is_listed") is not None else None
    except Exception as exc:
        logger.warning(f"Listed building error: {exc}")
        return None


def _call_address_confidence(original: str, returned: str) -> dict | None:
    """Cross-validate two addresses."""
    try:
        from backend.geo.uprn_maps.address_confidence import compare_addresses
        return compare_addresses(original, returned)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────
# SoV-Priority Merge — ONLY update NULL fields
# ─────────────────────────────────────────────────────────────────

def _merge_sov_priority(existing_row: dict, api_data: dict, field_map: dict) -> dict:
    """
    Returns dict of {db_column: api_value} ONLY for columns where existing is NULL.

    Args:
        existing_row: current silver.properties row (SoV data)
        api_data:     data from API call
        field_map:    {api_key: db_column_name}
    """
    updates = {}
    for api_key, db_col in field_map.items():
        api_val = api_data.get(api_key)
        if api_val is None:
            continue
        existing_val = existing_row.get(db_col)
        # SoV priority: only write if existing is NULL or empty string
        if existing_val is None or (isinstance(existing_val, str) and not existing_val.strip()):
            updates[db_col] = api_val
    return updates


# ─────────────────────────────────────────────────────────────────
# Single Property Enrichment
# ─────────────────────────────────────────────────────────────────

def enrich_single_property(
    prop: dict,
    places_key: str,
    ngd_key: str,
    epc_email: str,
    epc_key: str,
    postcode_cache: dict | None = None,
) -> dict:
    address = prop.get("address") or ""
    postcode = prop.get("postcode") or ""
    updates = {}
    sources = []

    # 1. OS Places (must be first, with retry)
    os_data = None
    pc_normalized = _normalize_postcode(postcode) if postcode else ""
    if postcode_cache and pc_normalized in postcode_cache:
        os_data = _match_address_to_uprn(address, postcode_cache[pc_normalized])
    if not os_data:
        os_data = _api_call_with_retry(_call_os_places, address, postcode, places_key)
        time.sleep(RATE_LIMIT_DELAY_S)

    if not os_data:
        return {"enrichment_status": "failed", "enriched_at": datetime.now(timezone.utc)}

    uprn = str(os_data.get("UPRN", ""))
    parent_uprn = str(os_data.get("PARENT_UPRN") or "")
    x = os_data.get("X_COORDINATE")
    y = os_data.get("Y_COORDINATE")

    conf = _call_address_confidence(address, os_data.get("ADDRESS", ""))
    if conf and conf.get("confidence") == "LOW":
        logger.warning(f"  Address mismatch: SoV='{address[:40]}' score={conf['score']}")

    updates["uprn"] = uprn if uprn else None
    updates["parent_uprn"] = parent_uprn if parent_uprn else None
    updates["x_coordinate"] = float(x) if x else None
    updates["y_coordinate"] = float(y) if y else None
    updates["country_code"] = os_data.get("COUNTRY_CODE")
    updates["uprn_match_score"] = float(os_data["MATCH"]) if os_data.get("MATCH") else None
    updates["uprn_match_description"] = os_data.get("MATCH_DESCRIPTION")
    sources.append("OS_PLACES")

    # 2. EPC + NGD + Listed in PARALLEL
    country = os_data.get("COUNTRY_CODE", "")
    epc_result = None
    ngd_result = None
    listed_result = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {}
        if country in ("E", "W") and uprn and epc_email and epc_key:
            futures["epc"] = pool.submit(_api_call_with_retry, _call_epc, uprn, epc_email, epc_key)
        if x and y and ngd_key:
            futures["ngd"] = pool.submit(_api_call_with_retry, _call_ngd_buildings, float(x), float(y), ngd_key)
        if uprn and places_key:
            futures["listed"] = pool.submit(_api_call_with_retry, _call_listed, uprn, places_key)

        for key, future in futures.items():
            try:
                if key == "epc":
                    epc_result = future.result(timeout=30)
                elif key == "ngd":
                    ngd_result = future.result(timeout=30)
                elif key == "listed":
                    listed_result = future.result(timeout=30)
            except Exception as exc:
                logger.warning(f"  {key} failed: {exc}")

    # 3. Merge EPC
    if epc_result:
        sources.append("EPC")
        epc_map = {
            "walls-description": "wall_construction",
            "roof-description": "roof_construction",
            "floor-description": "floor_construction",
            "property-type": "property_type",
            "built-form": "built_form",
            "construction-age-band": "age_banding",
            "total-floor-area": "total_floor_area_m2",
            "main-fuel": "main_fuel",
        }
        updates.update(_merge_sov_priority(prop, epc_result, epc_map))
        updates["epc_rating"] = epc_result.get("current-energy-rating")
        updates["epc_potential_rating"] = epc_result.get("potential-energy-rating")
        updates["epc_lodgement_date"] = epc_result.get("lodgement-datetime")
        if not prop.get("year_of_build") and epc_result.get("construction-age-band"):
            updates.setdefault("age_banding", epc_result["construction-age-band"])

    # 4. Merge NGD
    if ngd_result:
        sources.append("NGD")
        basement_raw = ngd_result.get("basementpresence")
        if basement_raw is not None:
            ngd_result["basementpresence"] = basement_raw.lower() in ("present", "yes", "true")
        updates["height_max_m"] = ngd_result.get("height_relativemax_m")
        updates["height_roofbase_m"] = ngd_result.get("height_relativeroofbase_m")
        updates["height_confidence"] = ngd_result.get("height_confidencelevel")
        updates["building_footprint_m2"] = ngd_result.get("geometry_area_m2")
        ngd_map = {
            "constructionmaterial": "wall_construction",
            "roofmaterial_primarymaterial": "roof_construction",
            "numberoffloors": "storeys",
            "basementpresence": "basement",
            "buildingage_year": "year_of_build",
            "buildingage_period": "age_banding",
            "description": "property_type",
        }
        current = {**prop, **updates}
        updates.update(_merge_sov_priority(current, ngd_result, ngd_map))

    # 5. Merge Listed
    if listed_result:
        sources.append("LISTED")
        if prop.get("is_listed") is None:
            updates["is_listed"] = listed_result.get("is_listed")
        if listed_result.get("is_listed"):
            updates["listed_grade"] = listed_result.get("grade")
            updates["listed_name"] = listed_result.get("name")
            updates["listed_reference"] = listed_result.get("reference")

    updates["enrichment_status"] = "enriched"
    updates["enrichment_source"] = ",".join(sources)
    updates["enriched_at"] = datetime.now(timezone.utc)
    return updates


# ─────────────────────────────────────────────────────────────────
# Block Detection — uses EXISTING silver.blocks table
# ─────────────────────────────────────────────────────────────────

def run_block_detection(ha_id: str) -> dict:
    """
    After enrichment, group properties by PARENT_UPRN.
    Updates the EXISTING silver.blocks table with enrichment data.
    Also fills NULL block_reference on properties.
    """
    conn = _get_db_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        parent_uprn,
                        COUNT(*) as unit_count,
                        SUM(COALESCE(sum_insured, 0)) as total_si,
                        MAX(storeys) as max_storeys,
                        MODE() WITHIN GROUP (ORDER BY wall_construction) as wall,
                        MODE() WITHIN GROUP (ORDER BY roof_construction) as roof,
                        MAX(height_max_m) as height,
                        BOOL_OR(is_listed) as listed,
                        MAX(listed_grade) as grade,
                        COALESCE(
                            MODE() WITHIN GROUP (ORDER BY block_reference),
                            MIN(address)
                        ) as block_name
                    FROM silver.properties
                    WHERE ha_id = %s
                      AND parent_uprn IS NOT NULL
                      AND parent_uprn != ''
                    GROUP BY parent_uprn
                    HAVING COUNT(*) > 1
                """, (ha_id,))

                blocks = cur.fetchall()
                logger.info(f"Block detection: {len(blocks)} blocks for ha_id={ha_id}")

                upserted = 0
                for b in blocks:
                    cur.execute("""
                        INSERT INTO silver.blocks (
                            ha_id, name,
                            parent_uprn, unit_count, total_sum_insured,
                            max_storeys, predominant_wall, predominant_roof,
                            height_max_m, is_listed, listed_grade
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (ha_id, name)
                        DO UPDATE SET
                            parent_uprn = EXCLUDED.parent_uprn,
                            unit_count = EXCLUDED.unit_count,
                            total_sum_insured = EXCLUDED.total_sum_insured,
                            max_storeys = EXCLUDED.max_storeys,
                            predominant_wall = EXCLUDED.predominant_wall,
                            predominant_roof = EXCLUDED.predominant_roof,
                            height_max_m = EXCLUDED.height_max_m,
                            is_listed = EXCLUDED.is_listed,
                            listed_grade = EXCLUDED.listed_grade,
                            updated_at = NOW()
                    """, (
                        ha_id, b["block_name"],
                        b["parent_uprn"], b["unit_count"], b["total_si"],
                        b["max_storeys"], b["wall"], b["roof"],
                        b["height"], b["listed"], b["grade"],
                    ))
                    upserted += 1

                cur.execute("""
                    UPDATE silver.properties p
                    SET block_reference = blk.name
                    FROM silver.blocks blk
                    WHERE p.ha_id = %s
                      AND p.parent_uprn = blk.parent_uprn
                      AND blk.ha_id = %s
                      AND (p.block_reference IS NULL OR p.block_reference = '')
                """, (ha_id, ha_id))
                filled = cur.rowcount

                logger.info(f"Block detection: {upserted} blocks upserted, "
                            f"{filled} NULL block_refs filled")

        return {"blocks_upserted": upserted, "block_refs_filled": filled}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────
# Batch Enrichment — main entry point
# ─────────────────────────────────────────────────────────────────

def _build_update_sql(updates: dict, prop_id: str) -> tuple[str, list]:
    """Build dynamic UPDATE from updates dict."""
    if not updates:
        return ("", [])
    set_clauses = []
    values = []
    for col, val in updates.items():
        set_clauses.append(f"{col} = %s")
        values.append(val)
    values.append(prop_id)
    sql = f"UPDATE silver.properties SET {', '.join(set_clauses)} WHERE property_id = %s"
    return (sql, values)


async def enrich_portfolio(
    ha_id: str,
    places_key: str = "",
    ngd_key: str = "",
    epc_email: str = "",
    epc_key: str = "",
    limit: int = 0,
) -> dict:
    """
    Enrich all pending properties for an HA.
    Called after SoV Stage D, before Doc A/B export.
    This is Igor's enrichment slot.
    """
    places_key = places_key or DEFAULT_PLACES_KEY
    ngd_key = ngd_key or DEFAULT_NGD_KEY
    epc_email = epc_email or DEFAULT_EPC_EMAIL
    epc_key = epc_key or DEFAULT_EPC_KEY

    if not places_key:
        return {"error": "OS_PLACES_API_KEY not configured", "enriched": 0}

    logger.info(f"[ENRICH] Starting for ha_id={ha_id}")
    start = time.time()

    # Fetch pending rows
    conn = _get_db_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            lim = f"LIMIT {limit}" if limit > 0 else ""
            cur.execute(f"""
                SELECT * FROM silver.properties
                WHERE ha_id = %s AND enrichment_status = 'pending'
                ORDER BY property_reference {lim}
            """, (ha_id,))
            rows = cur.fetchall()
    finally:
        conn.close()

    total = len(rows)
    logger.info(f"[ENRICH] {total} pending properties")
    if total == 0:
        return {"enriched": 0, "failed": 0, "total": 0}

    enriched = 0
    failed = 0
    epc_calls = 0

    conn = _get_db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # Pre-fetch UPRNs by postcode (1 API call per unique postcode)
                postcode_cache = {}
                unique_postcodes = set(
                    str(r.get("postcode", "")).strip().upper()
                    for r in rows if r.get("postcode")
                )
                logger.info(f"[ENRICH] Pre-fetching {len(unique_postcodes)} unique postcodes")
                for pc in unique_postcodes:
                    if not pc:
                        continue
                    normalized = _normalize_postcode(pc)
                    if normalized in postcode_cache:
                        continue  # already fetched this postcode
                    result = _api_call_with_retry(_batch_os_places_by_postcode, normalized, places_key)
                    if result:
                        postcode_cache[normalized] = result
                    time.sleep(RATE_LIMIT_DELAY_S)
                logger.info(f"[ENRICH] Cache built: {len(postcode_cache)} postcodes, "
                            f"{sum(len(v) for v in postcode_cache.values())} UPRNs cached")
                for i, row in enumerate(rows):
                    try:
                        cur.execute("SAVEPOINT enrich_row")
                        ek = epc_key if epc_calls < EPC_DAILY_LIMIT else ""
                        em = epc_email if epc_calls < EPC_DAILY_LIMIT else ""

                        updates = enrich_single_property(
                            dict(row), places_key, ngd_key, em, ek,
                            postcode_cache=postcode_cache,
                        )

                        if "EPC" in (updates.get("enrichment_source") or ""):
                            epc_calls += 1

                        result = _build_update_sql(updates, str(row["property_id"]))
                        if result and result[0]:
                            cur.execute(result[0], result[1])

                        if updates.get("enrichment_status") == "enriched":
                            enriched += 1
                        else:
                            failed += 1

                        if (i + 1) % BATCH_COMMIT_SIZE == 0:
                            conn.commit()
                            elapsed = time.time() - start
                            logger.info(
                                f"[ENRICH] {i+1}/{total} ({enriched} ok, {failed} fail) "
                                f"{(i+1)/elapsed:.1f}/sec EPC={epc_calls}"
                            )

                    except Exception as exc:
                        cur.execute("ROLLBACK TO SAVEPOINT enrich_row")
                        logger.error(f"[ENRICH] Error {row.get('property_reference')}: {exc}")
                        traceback.print_exc()
                        failed += 1

                conn.commit()
    finally:
        conn.close()

    # Block detection
    block_result = {}
    try:
        block_result = run_block_detection(ha_id)
    except Exception as exc:
        logger.error(f"[ENRICH] Block detection failed: {exc}")
        block_result = {"error": str(exc)}

    elapsed = time.time() - start
    result = {
        "ha_id": ha_id, "total": total,
        "enriched": enriched, "failed": failed,
        "epc_calls": epc_calls,
        "seconds": round(elapsed, 1),
        "blocks": block_result,
    }
    logger.info(f"[ENRICH] DONE: {enriched}/{total} in {elapsed:.0f}s | "
                f"Blocks: {block_result.get('blocks_upserted', 0)}")
    return result