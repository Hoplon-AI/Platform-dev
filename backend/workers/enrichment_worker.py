"""
Enrichment Worker — Populates silver.properties with API data after SoV ingestion.

Workflow:
  1. SoV processor writes rows with enrichment_status='pending'
  2. This worker picks up pending rows
  3. For each row: address+postcode → OS Places → UPRN → EPC + NGD + Listed
  4. API data fills ONLY columns that actually exist in silver.properties
  5. Block detection groups properties by parent_uprn → updates silver.blocks
  6. Dashboard/exporters can read enriched data when available

Important local-dev behavior:
  - If API keys are missing, enrichment is skipped gracefully.
  - If enrichment columns/tables do not exist yet, updates are filtered to only
    existing columns instead of crashing.
  - If silver.blocks does not exist, block detection is skipped gracefully.

This keeps SoV ingestion working even when enrichment is only partially set up.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

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
                time.sleep(2**attempt)
        except Exception as exc:
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
            else:
                logger.warning("API retry failed for %s: %s", getattr(func, "__name__", "api_call"), exc)
    return None


def _normalize_postcode(pc: str) -> str:
    """Normalize postcode: uppercase, single space before last 3 chars."""
    pc = pc.strip().upper().replace(" ", "")
    if len(pc) >= 5:
        return f"{pc[:-3]} {pc[-3:]}"
    return pc


def _batch_os_places_by_postcode(postcode: str, api_key: str) -> list[dict]:
    """Get all addresses for a postcode in one API call."""
    try:
        import requests

        url = "https://api.os.uk/search/places/v1/postcode"
        params = {"postcode": postcode, "key": api_key, "maxresults": 100}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        results: list[dict] = []
        for r in data.get("results", []):
            entry = r.get("DPA") or r.get("LPI")
            if entry:
                results.append(entry)
        return results
    except Exception as exc:
        logger.warning("Postcode batch error for %s: %s", postcode, exc)
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


def _table_exists(conn, schema: str, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_name = %s
            )
            """,
            (schema, table),
        )
        row = cur.fetchone()
        return bool(row and row[0])


def _get_table_columns(conn, schema: str, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            """,
            (schema, table),
        )
        return {r[0] for r in cur.fetchall()}


def _choose_first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row.get(key)
    return None


def _get_property_pk_value(row: dict[str, Any]) -> Any:
    return _choose_first_present(row, "property_id", "id", "property_reference")


def _get_property_pk_column(row: dict[str, Any], available_columns: set[str]) -> Optional[str]:
    candidates = ["property_id", "id", "property_reference"]
    for col in candidates:
        if col in row and col in available_columns:
            return col
    for col in candidates:
        if col in row:
            return col
    return None


# ─────────────────────────────────────────────────────────────────
# API Wrappers
# ─────────────────────────────────────────────────────────────────

def _call_os_places(address: str, postcode: str, api_key: str) -> dict | None:
    """Address → UPRN + coordinates via OS Places API."""
    try:
        from backend.geo.uprn_maps.os_datahub_functions import get_uprn_from_address

        query = f"{address}, {postcode}" if postcode else address
        result = get_uprn_from_address(query, api_key)
        return result if isinstance(result, dict) else None
    except Exception as exc:
        logger.warning("OS Places error: %s", exc)
        return None


def _call_epc(uprn: str, email: str, api_key: str) -> dict | None:
    """UPRN → most recent EPC certificate (England/Wales only)."""
    try:
        from backend.geo.uprn_maps.uprn_to_epc import get_epc_from_uprn

        result = get_epc_from_uprn(uprn, email, api_key)
        return result[0] if isinstance(result, list) and result else None
    except Exception as exc:
        logger.warning("EPC error for UPRN %s: %s", uprn, exc)
        return None


def _call_ngd_buildings(x: float, y: float, api_key: str) -> dict | None:
    """Coordinates → nearest building from NGD Buildings API."""
    try:
        from backend.geo.uprn_maps.uprn_to_height import get_building_from_coords

        result = get_building_from_coords(x, y, api_key)
        return result.get("properties", {}) if isinstance(result, dict) else None
    except Exception as exc:
        logger.warning("NGD error: %s", exc)
        return None


def _call_listed(uprn: str, api_key: str) -> dict | None:
    """UPRN → listed building status (England or Scotland)."""
    try:
        from backend.geo.uprn_maps.uprn_to_listed import get_listed_building_status

        result = get_listed_building_status(uprn, api_key)
        return result if isinstance(result, dict) and result.get("is_listed") is not None else None
    except Exception as exc:
        logger.warning("Listed building error: %s", exc)
        return None


def _call_address_confidence(original: str, returned: str) -> dict | None:
    """Cross-validate two addresses."""
    try:
        from backend.geo.uprn_maps.address_confidence import compare_addresses

        return compare_addresses(original, returned)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────
# Merge helpers
# ─────────────────────────────────────────────────────────────────

def _merge_api_values(api_data: dict, field_map: dict[str, str]) -> dict[str, Any]:
    """
    Returns dict of {db_column: api_value} for all fields where API has a value.
    """
    updates: dict[str, Any] = {}
    for api_key, db_col in field_map.items():
        api_val = api_data.get(api_key)
        if api_val is None:
            continue
        updates[db_col] = api_val
    return updates


def _filter_updates_to_existing_columns(updates: dict[str, Any], available_columns: set[str]) -> dict[str, Any]:
    return {k: v for k, v in updates.items() if k in available_columns}


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
    updates: dict[str, Any] = {}
    sources: list[str] = []

    if not places_key:
        return {
            "enrichment_status": "skipped",
            "enrichment_source": "NO_OS_PLACES_KEY",
            "enriched_at": datetime.now(timezone.utc),
        }

    # 1. OS Places
    os_data = None
    pc_normalized = _normalize_postcode(postcode) if postcode else ""
    if postcode_cache and pc_normalized in postcode_cache:
        os_data = _match_address_to_uprn(address, postcode_cache[pc_normalized])

    if not os_data:
        os_data = _api_call_with_retry(_call_os_places, address, postcode, places_key)
        time.sleep(RATE_LIMIT_DELAY_S)

    if not os_data:
        return {
            "enrichment_status": "failed",
            "enrichment_source": "OS_PLACES",
            "enriched_at": datetime.now(timezone.utc),
        }

    uprn = str(os_data.get("UPRN", "") or "")
    parent_uprn = str(os_data.get("PARENT_UPRN") or "")
    x = os_data.get("X_COORDINATE")
    y = os_data.get("Y_COORDINATE")

    conf = _call_address_confidence(address, os_data.get("ADDRESS", ""))
    if conf and conf.get("confidence") == "LOW":
        logger.warning("Address mismatch: SoV='%s' score=%s", address[:40], conf.get("score"))

    updates["uprn"] = uprn if uprn else None
    updates["parent_uprn"] = parent_uprn if parent_uprn else None
    updates["x_coordinate"] = float(x) if x is not None else None
    updates["y_coordinate"] = float(y) if y is not None else None
    updates["country_code"] = os_data.get("COUNTRY_CODE")
    updates["uprn_match_score"] = float(os_data["MATCH"]) if os_data.get("MATCH") else None
    updates["uprn_match_description"] = os_data.get("MATCH_DESCRIPTION")
    sources.append("OS_PLACES")

    # 2. EPC + NGD + Listed in parallel
    country = os_data.get("COUNTRY_CODE", "")
    epc_result = None
    ngd_result = None
    listed_result = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {}

        if country in ("E", "W") and uprn and epc_email and epc_key:
            futures["epc"] = pool.submit(_api_call_with_retry, _call_epc, uprn, epc_email, epc_key)

        if x is not None and y is not None and ngd_key:
            futures["ngd"] = pool.submit(_api_call_with_retry, _call_ngd_buildings, float(x), float(y), ngd_key)

        if uprn and places_key:
            futures["listed"] = pool.submit(_api_call_with_retry, _call_listed, uprn, places_key)

        for key, future in futures.items():
            try:
                result = future.result(timeout=30)
                if key == "epc":
                    epc_result = result
                elif key == "ngd":
                    ngd_result = result
                elif key == "listed":
                    listed_result = result
            except Exception as exc:
                logger.warning("%s failed: %s", key, exc)

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
        updates.update(_merge_api_values(epc_result, epc_map))
        updates["epc_rating"] = epc_result.get("current-energy-rating")
        updates["epc_potential_rating"] = epc_result.get("potential-energy-rating")
        updates["epc_lodgement_date"] = epc_result.get("lodgement-datetime")
        if not prop.get("year_of_build") and epc_result.get("construction-age-band"):
            updates.setdefault("age_banding", epc_result["construction-age-band"])

    # 4. Merge NGD
    if ngd_result:
        sources.append("NGD")
        basement_raw = ngd_result.get("basementpresence")
        if isinstance(basement_raw, str):
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
        updates.update(_merge_api_values(ngd_result, ngd_map))

    # 5. Merge Listed
    if listed_result:
        sources.append("LISTED")
        updates["is_listed"] = listed_result.get("is_listed")
        if listed_result.get("is_listed"):
            updates["listed_grade"] = listed_result.get("grade")
            updates["listed_name"] = listed_result.get("name")
            updates["listed_reference"] = listed_result.get("reference")

    updates["enrichment_status"] = "enriched"
    updates["enrichment_source"] = ",".join(sources) if sources else "NONE"
    updates["enriched_at"] = datetime.now(timezone.utc)
    return updates


# ─────────────────────────────────────────────────────────────────
# Block Detection
# ─────────────────────────────────────────────────────────────────

def run_block_detection(ha_id: str, places_key: str = "") -> dict:
    """
    Group properties into blocks using detect_block_properties().

    Graceful behavior:
      - If silver.blocks does not exist, skip.
      - If required columns do not exist, skip.
      - Never crash ingestion.
    """
    from backend.geo.uprn_maps.block_detection import detect_block_properties

    places_key = places_key or DEFAULT_PLACES_KEY

    conn = _get_db_conn()
    try:
        if not _table_exists(conn, "silver", "properties"):
            logger.info("Block detection skipped: silver.properties does not exist")
            return {"blocks_upserted": 0, "block_refs_filled": 0, "skipped": True}

        if not _table_exists(conn, "silver", "blocks"):
            logger.info("Block detection skipped: silver.blocks does not exist")
            return {"blocks_upserted": 0, "block_refs_filled": 0, "skipped": True}

        property_columns = _get_table_columns(conn, "silver", "properties")
        required_property_cols = {"ha_id", "address"}
        optional_uprn_cols = {"uprn", "parent_uprn"}

        if not required_property_cols.issubset(property_columns):
            logger.info("Block detection skipped: silver.properties missing required columns")
            return {"blocks_upserted": 0, "block_refs_filled": 0, "skipped": True}

        if not optional_uprn_cols.issubset(property_columns):
            logger.info("Block detection skipped: silver.properties missing uprn/parent_uprn")
            return {"blocks_upserted": 0, "block_refs_filled": 0, "skipped": True}

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT uprn, parent_uprn, address
                FROM silver.properties
                WHERE ha_id = %s
                  AND uprn IS NOT NULL
                  AND uprn != ''
                """,
                (ha_id,),
            )
            enriched_rows = cur.fetchall()

        if not enriched_rows:
            logger.info("Block detection: no enriched properties for ha_id=%s", ha_id)
            return {"blocks_upserted": 0, "block_refs_filled": 0}

        os_format_props = [
            {
                "UPRN": str(r["uprn"]),
                "PARENT_UPRN": str(r["parent_uprn"]) if r["parent_uprn"] else None,
                "ADDRESS": r["address"] or "",
            }
            for r in enriched_rows
        ]

        logger.info(
            "Block detection: running detect_block_properties() on %s properties (api_key=%s)",
            len(os_format_props),
            "set" if places_key else "not set",
        )
        detection_result = detect_block_properties(os_format_props, api_key=places_key or None)
        detected_blocks = detection_result.get("blocks", {})
        standalone_count = len(detection_result.get("standalone", []))
        logger.info(
            "Block detection: %s blocks, %s standalone properties",
            len(detected_blocks),
            standalone_count,
        )

        block_columns = _get_table_columns(conn, "silver", "blocks")

        upserted = 0
        filled = 0

        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                for block_data in detected_blocks.values():
                    root_parent_uprn = block_data["root_parent_uprn"]
                    member_uprns = block_data["properties"]

                    if len(member_uprns) < 2:
                        continue

                    cur.execute(
                        """
                        SELECT
                            COUNT(*) AS unit_count,
                            SUM(COALESCE(sum_insured, 0)) AS total_si,
                            MAX(storeys) AS max_storeys,
                            MODE() WITHIN GROUP (ORDER BY wall_construction) AS wall,
                            MODE() WITHIN GROUP (ORDER BY roof_construction) AS roof,
                            MAX(height_max_m) AS height,
                            BOOL_OR(COALESCE(is_listed, FALSE)) AS listed,
                            MAX(listed_grade) AS grade,
                            COALESCE(
                                MODE() WITHIN GROUP (ORDER BY block_reference),
                                MIN(address)
                            ) AS block_name
                        FROM silver.properties
                        WHERE ha_id = %s
                          AND uprn = ANY(%s)
                        """,
                        (ha_id, member_uprns),
                    )
                    agg = cur.fetchone()

                    if not agg or not agg["block_name"]:
                        continue

                    insert_payload = {
                        "ha_id": ha_id,
                        "name": agg["block_name"],
                        "parent_uprn": root_parent_uprn,
                        "unit_count": agg["unit_count"],
                        "total_sum_insured": agg["total_si"],
                        "max_storeys": agg["max_storeys"],
                        "predominant_wall": agg["wall"],
                        "predominant_roof": agg["roof"],
                        "height_max_m": agg["height"],
                        "is_listed": agg["listed"],
                        "listed_grade": agg["grade"],
                    }
                    insert_payload = _filter_updates_to_existing_columns(insert_payload, block_columns)

                    if "ha_id" not in insert_payload or "name" not in insert_payload:
                        continue

                    cols = list(insert_payload.keys())
                    values = [insert_payload[c] for c in cols]
                    placeholders = ", ".join(["%s"] * len(cols))
                    col_sql = ", ".join(cols)

                    update_cols = [c for c in cols if c not in {"ha_id", "name"}]
                    update_sql = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols] + ["updated_at = NOW()"])

                    cur.execute(
                        f"""
                        INSERT INTO silver.blocks ({col_sql})
                        VALUES ({placeholders})
                        ON CONFLICT (ha_id, name)
                        DO UPDATE SET {update_sql}
                        """,
                        values,
                    )
                    upserted += 1

                if {"block_reference", "parent_uprn", "ha_id"}.issubset(property_columns) and {
                    "name", "parent_uprn", "ha_id"
                }.issubset(block_columns):
                    cur.execute(
                        """
                        UPDATE silver.properties p
                        SET block_reference = blk.name
                        FROM silver.blocks blk
                        WHERE p.ha_id = %s
                          AND p.parent_uprn = blk.parent_uprn
                          AND blk.ha_id = %s
                          AND (p.block_reference IS NULL OR p.block_reference = '')
                        """,
                        (ha_id, ha_id),
                    )
                    filled = cur.rowcount

        logger.info("Block detection: %s blocks upserted, %s NULL block_refs filled", upserted, filled)
        return {"blocks_upserted": upserted, "block_refs_filled": filled}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────
# Batch Enrichment
# ─────────────────────────────────────────────────────────────────

def _build_update_sql(
    updates: dict[str, Any],
    pk_column: str,
    pk_value: Any,
    available_columns: set[str],
) -> tuple[str, list]:
    """
    Build dynamic UPDATE from updates dict, filtered to existing columns.
    """
    filtered = _filter_updates_to_existing_columns(updates, available_columns)
    if not filtered:
        return ("", [])

    set_clauses = []
    values = []
    for col, val in filtered.items():
        set_clauses.append(f"{col} = %s")
        values.append(val)

    values.append(pk_value)
    sql = f"UPDATE silver.properties SET {', '.join(set_clauses)} WHERE {pk_column} = %s"
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

    Local-dev friendly behavior:
      - If no OS_PLACES_API_KEY, skip gracefully and return success metadata.
      - If enrichment columns are missing, filter updates to existing columns.
      - If there are no pending rows, return cleanly.
    """
    places_key = places_key or DEFAULT_PLACES_KEY
    ngd_key = ngd_key or DEFAULT_NGD_KEY
    epc_email = epc_email or DEFAULT_EPC_EMAIL
    epc_key = epc_key or DEFAULT_EPC_KEY

    logger.info("[ENRICH] Starting for ha_id=%s", ha_id)
    start = time.time()

    conn = _get_db_conn()
    try:
        if not _table_exists(conn, "silver", "properties"):
            logger.info("[ENRICH] silver.properties does not exist; skipping")
            return {"ha_id": ha_id, "total": 0, "enriched": 0, "failed": 0, "skipped": True}

        property_columns = _get_table_columns(conn, "silver", "properties")

        lim = f"LIMIT {int(limit)}" if limit and limit > 0 else ""
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT *
                FROM silver.properties
                WHERE ha_id = %s
                  AND (
                    enrichment_status = 'pending'
                    OR enrichment_status IS NULL
                    OR enrichment_status = ''
                  )
                ORDER BY property_reference
                {lim}
                """,
                (ha_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    total = len(rows)
    logger.info("[ENRICH] %s pending properties", total)

    if total == 0:
        return {"ha_id": ha_id, "enriched": 0, "failed": 0, "total": 0}

    if not places_key:
        logger.info("[ENRICH] OS_PLACES_API_KEY not configured; skipping external enrichment")
        return {
            "ha_id": ha_id,
            "total": total,
            "enriched": 0,
            "failed": 0,
            "epc_calls": 0,
            "seconds": round(time.time() - start, 1),
            "blocks": {"skipped": True, "reason": "OS_PLACES_API_KEY not configured"},
            "skipped": True,
            "reason": "OS_PLACES_API_KEY not configured",
        }

    enriched = 0
    failed = 0
    epc_calls = 0

    conn = _get_db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                postcode_cache: dict[str, list[dict]] = {}
                unique_postcodes = {
                    str(r.get("postcode", "")).strip().upper()
                    for r in rows
                    if r.get("postcode")
                }

                logger.info("[ENRICH] Pre-fetching %s unique postcodes", len(unique_postcodes))
                for pc in unique_postcodes:
                    if not pc:
                        continue
                    normalized = _normalize_postcode(pc)
                    if normalized in postcode_cache:
                        continue
                    result = _api_call_with_retry(_batch_os_places_by_postcode, normalized, places_key)
                    if result:
                        postcode_cache[normalized] = result
                    time.sleep(RATE_LIMIT_DELAY_S)

                logger.info(
                    "[ENRICH] Cache built: %s postcodes, %s UPRNs cached",
                    len(postcode_cache),
                    sum(len(v) for v in postcode_cache.values()),
                )

                for i, row in enumerate(rows):
                    try:
                        cur.execute("SAVEPOINT enrich_row")

                        ek = epc_key if epc_calls < EPC_DAILY_LIMIT else ""
                        em = epc_email if epc_calls < EPC_DAILY_LIMIT else ""

                        updates = enrich_single_property(
                            dict(row),
                            places_key,
                            ngd_key,
                            em,
                            ek,
                            postcode_cache=postcode_cache,
                        )

                        if "EPC" in (updates.get("enrichment_source") or ""):
                            epc_calls += 1

                        pk_column = _get_property_pk_column(dict(row), property_columns)
                        pk_value = _get_property_pk_value(dict(row))

                        if pk_column and pk_value is not None:
                            sql, params = _build_update_sql(
                                updates=updates,
                                pk_column=pk_column,
                                pk_value=pk_value,
                                available_columns=property_columns,
                            )
                            if sql:
                                cur.execute(sql, params)

                        if updates.get("enrichment_status") == "enriched":
                            enriched += 1
                        else:
                            failed += 1

                        if (i + 1) % BATCH_COMMIT_SIZE == 0:
                            conn.commit()
                            elapsed = time.time() - start
                            logger.info(
                                "[ENRICH] %s/%s (%s ok, %s fail) %.1f/sec EPC=%s",
                                i + 1,
                                total,
                                enriched,
                                failed,
                                (i + 1) / elapsed if elapsed > 0 else 0.0,
                                epc_calls,
                            )

                    except Exception as exc:
                        cur.execute("ROLLBACK TO SAVEPOINT enrich_row")
                        logger.error("[ENRICH] Error %s: %s", row.get("property_reference"), exc)
                        traceback.print_exc()
                        failed += 1

                conn.commit()
    finally:
        conn.close()

    block_result: dict[str, Any] = {}
    try:
        block_result = run_block_detection(ha_id, places_key=places_key)
    except Exception as exc:
        logger.error("[ENRICH] Block detection failed: %s", exc)
        block_result = {"error": str(exc)}

    elapsed = time.time() - start
    result = {
        "ha_id": ha_id,
        "total": total,
        "enriched": enriched,
        "failed": failed,
        "epc_calls": epc_calls,
        "seconds": round(elapsed, 1),
        "blocks": block_result,
    }
    logger.info(
        "[ENRICH] DONE: %s/%s in %.0fs | Blocks: %s",
        enriched,
        total,
        elapsed,
        block_result.get("blocks_upserted", 0),
    )
    return result