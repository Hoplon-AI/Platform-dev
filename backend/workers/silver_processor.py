"""
Silver layer processor: Reads features.json from S3 and writes to normalized PostgreSQL tables.

This processor:
1. Reads features.json from S3 (triggered after extraction completes)
2. Parses and normalizes features based on document type
3. Writes to structured Silver layer tables (document_features, fraew_features, etc.)
4. Updates processing_audit with Silver layer status

Triggered by:
- Step Functions state machine (after extraction step)
- Or S3 event on features.json creation (alternative pattern)
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone, date
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote_plus

import asyncpg
import boto3

from infrastructure.storage.s3_config import S3Config
from infrastructure.storage.upload_service import UploadService
from backend.core.database.db_pool import DatabasePool


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_db_connection(
    conn: Optional[asyncpg.Connection] = None,
    pool: Optional[asyncpg.Pool] = None,
) -> Tuple[asyncpg.Connection, bool]:
    """
    Get a database connection using dependency injection.
    
    Args:
        conn: Optional existing connection (for testing/mocking)
        pool: Optional connection pool (for dependency injection)
        
    Returns:
        Tuple of (connection, should_release)
        - should_release: True if connection should be released back to pool, False otherwise
        
    Raises:
        RuntimeError: If no connection can be obtained
    """
    # If connection provided, use it (for testing/mocking) - don't release
    if conn is not None:
        return conn, False
    
    # If pool provided, acquire from it (for dependency injection) - release back
    if pool is not None:
        return await pool.acquire(), True
    
    # Default: try to use DatabasePool (like rest of codebase) - release back
    try:
        db_pool = DatabasePool.get_pool()
        return await db_pool.acquire(), True
    except RuntimeError:
        # Fallback: create direct connection (for Lambda environments where pool may not be initialized)
        # Don't release - we created it directly
        host = os.getenv("DB_HOST", "localhost")
        port = int(os.getenv("DB_PORT", "5432"))
        database = os.getenv("DB_NAME", "platform_dev")
        
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "postgres")
        
        secret_arn = os.getenv("DATABASE_SECRET_ARN")
        if secret_arn:
            sm = boto3.client("secretsmanager")
            resp = sm.get_secret_value(SecretId=secret_arn)
            secret_str = resp.get("SecretString") or "{}"
            try:
                secret = json.loads(secret_str)
                user = secret.get("username", user)
                password = secret.get("password", password)
            except Exception:
                pass
        
        connection = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
        return connection, False


def _parse_s3_key_for_metadata(key: str) -> Dict[str, str]:
    """
    Parse S3 key to extract ha_id, submission_id, and file_type.
    
    Expected format: ha_id=<ha_id>/bronze/dataset=<file_type>/ingest_date=YYYY-MM-DD/submission_id=<uuid>/...
    """
    import re
    
    ha_match = re.search(r"ha_id=([^/]+)/", key)
    dataset_match = re.search(r"dataset=([^/]+)/", key)
    submission_match = re.search(r"submission_id=([0-9a-fA-F-]{36})/", key)
    
    if not ha_match or not dataset_match or not submission_match:
        raise ValueError(f"Could not parse S3 key: {key}")
    
    return {
        "ha_id": ha_match.group(1),
        "file_type": dataset_match.group(1),
        "submission_id": submission_match.group(1),
    }


def _normalize_date(date_str: Optional[str]) -> Optional[datetime]:
    """Convert date string to datetime object."""
    if not date_str:
        return None
    
    # Try ISO format first (YYYY-MM-DD)
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        pass
    
    # Try DD/MM/YYYY or DD-MM-YYYY
    try:
        parts = date_str.replace("-", "/").split("/")
        if len(parts) == 3 and len(parts[2]) == 4:
            return datetime(int(parts[2]), int(parts[1]), int(parts[0]), tzinfo=timezone.utc)
    except Exception:
        pass
    
    return None


async def _write_document_features(
    conn: asyncpg.Connection,
    *,
    ha_id: str,
    upload_id: uuid.UUID,
    document_type: str,
    features_json: Dict[str, Any],
) -> uuid.UUID:
    """
    Write common document features to document_features table.
    Returns feature_id.
    """
    features = features_json.get("features", {})
    
    # Extract common fields
    building_name = None
    address = None
    uprn = None
    postcode = None
    assessment_date = None
    job_reference = None
    client_name = None
    assessor_company = None
    
    # Extract from general features
    if "uprns" in features and features["uprns"]:
        uprn = features["uprns"][0]  # Take first UPRN
    
    if "postcodes" in features and features["postcodes"]:
        postcode = features["postcodes"][0]  # Take first postcode
    
    if "dates" in features and features["dates"]:
        assessment_date = _normalize_date(features["dates"][0])
    
    # Extract document-specific features
    if document_type == "fraew_document" and "fraew_specific" in features:
        fraew = features["fraew_specific"]
        building_name = fraew.get("building_name")
        address = fraew.get("address")
        assessment_date = _normalize_date(fraew.get("assessment_date")) or assessment_date
        job_reference = fraew.get("job_reference")
        client_name = fraew.get("client_name")
        assessor_company = fraew.get("assessor_company")
    elif document_type == "fra_document" and "fra_specific" in features:
        fra = features["fra_specific"]
        building_name = fra.get("building_name")
        address = fra.get("address")
        assessment_date = _normalize_date(fra.get("assessment_date")) or assessment_date
        job_reference = None  # Not in FRA features
        client_name = fra.get("client_name")
        assessor_company = fra.get("assessor_company")

    extracted_at_str = features_json.get("extracted_at")
    extracted_at = None
    if extracted_at_str:
        try:
            extracted_at = datetime.fromisoformat(extracted_at_str.replace("Z", "+00:00"))
        except Exception:
            pass
    
    feature_id = uuid.uuid4()
    now = _utc_now().replace(tzinfo=None)
    
    await conn.execute(
        """
        INSERT INTO silver.document_features (
            feature_id, ha_id, upload_id, document_type,
            building_name, address, uprn, postcode, assessment_date,
            job_reference, client_name, assessor_company,
            features_json, extracted_at, processed_at, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14, $15, $16, $17)
        """,
        feature_id,
        ha_id,
        upload_id,
        document_type,
        building_name,
        address,
        uprn,
        postcode,
        assessment_date.date() if assessment_date else None,
        job_reference,
        client_name,
        assessor_company,
        json.dumps(features_json),
        extracted_at.replace(tzinfo=None) if extracted_at else None,
        now,
        now,
        now,
    )
    
    return feature_id


async def _write_fraew_features(
    conn: asyncpg.Connection,
    *,
    feature_id: uuid.UUID,
    ha_id: str,
    upload_id: uuid.UUID,
    features_json: Dict[str, Any],
    uprn: Optional[str] = None,
    postcode: Optional[str] = None,
) -> None:
    """
    Write FRAEW-specific features to silver.fraew_features (migration 015, 50 columns).

    Reads from features_json.features.fraew_specific — the shape produced by the
    updated agentic-feature-definitions.json fed to Bedrock.

    The rag_status and is_in_date columns are derived here in Python using the
    same logic as the normalize_fraew_risk_rating() SQL function so that the
    silver processor does not need to make an extra DB round-trip.

    All existing args and call signature preserved for compatibility.
    """
    features = features_json.get("features", {})
    fs = features.get("fraew_specific", {})

    # ------------------------------------------------------------------
    # Derive rag_status from building_risk_rating (mirrors SQL function)
    # ------------------------------------------------------------------
    def _derive_fraew_rag(rating: Optional[str]) -> Optional[str]:
        if not rating:
            return None
        lower = rating.lower().strip()
        no_data = ("n/a", "not assessed", "unknown", "tbc", "tbd", "none")
        if lower in no_data:
            return None
        if "no further action" in lower:
            return "GREEN"
        if "tolerable but" in lower or "tolerable with" in lower:
            return "AMBER"
        if "further action" in lower or "further assessment" in lower:
            return "AMBER"
        if "not acceptable" in lower:
            return "RED"
        if "broadly acceptable" in lower:
            return "GREEN"
        red_kw = ("high", "intolerable", "unacceptable", "extreme", "critical")
        if any(kw in lower for kw in red_kw):
            return "RED"
        amber_kw = ("medium", "moderate", "significant")
        if any(kw in lower for kw in amber_kw):
            return "AMBER"
        green_kw = ("low", "tolerable", "acceptable", "negligible")
        if any(kw in lower for kw in green_kw):
            return "GREEN"
        return "AMBER"  # conservative fallback

    # ------------------------------------------------------------------
    # Derive is_in_date
    # ------------------------------------------------------------------
    def _derive_is_in_date(valid_until_str: Optional[str]) -> Optional[bool]:
        if not valid_until_str:
            return None
        try:
            from datetime import date as _date
            valid_until = _date.fromisoformat(valid_until_str)
            return valid_until >= _date.today()
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Derive material flags from wall_types array
    # ------------------------------------------------------------------
    wall_types = fs.get("wall_types") or []

    def _any_insulation(t: str) -> bool:
        return any(wt.get("insulation_type") == t for wt in wall_types)

    def _any_render(t: str) -> bool:
        return any(wt.get("render_type") == t for wt in wall_types)

    has_combustible = None
    if wall_types:
        combustible_vals = [
            wt.get("insulation_combustible") or wt.get("render_combustible")
            for wt in wall_types
            if wt.get("insulation_combustible") is not None
            or wt.get("render_combustible") is not None
        ]
        has_combustible = any(combustible_vals) if combustible_vals else None

    # ------------------------------------------------------------------
    # Pull all fields from fraew_specific
    # ------------------------------------------------------------------
    building_risk_rating = fs.get("building_risk_rating")
    rag_status           = _derive_fraew_rag(building_risk_rating)
    is_in_date           = _derive_is_in_date(fs.get("assessment_valid_until"))

    # Validate height_category against allowed values
    valid_height_cats = ("under_11m", "11_to_18m", "18_to_30m", "over_30m", "unknown")
    height_category = fs.get("building_height_category")
    if height_category not in valid_height_cats:
        height_category = None

    # Validate adb_compliant
    valid_adb = ("compliant", "non_compliant", "uncertain", "not_applicable")
    adb_compliant = fs.get("adb_compliant")
    if adb_compliant not in valid_adb:
        adb_compliant = None

    # Validate evacuation_strategy
    valid_evac = ("stay_put", "simultaneous", "phased", "temporary_evacuation")
    evacuation_strategy = fs.get("evacuation_strategy")
    if evacuation_strategy not in valid_evac:
        evacuation_strategy = None

    now = _utc_now().replace(tzinfo=None)

    await conn.execute(
        """
        INSERT INTO silver.fraew_features (
            fraew_id, feature_id, ha_id, upload_id,

            report_reference, assessment_date, report_date,
            assessment_valid_until, is_in_date,

            assessor_name, assessor_company, assessor_qualification,
            fire_engineer_name, fire_engineer_company, fire_engineer_qualification,
            clause_14_applied,

            building_height_m, building_height_category,
            num_storeys, num_units, build_year,
            construction_frame_type, external_wall_base_construction, retrofit_year,

            pas_9980_version, pas_9980_compliant,
            building_risk_rating, rag_status,

            interim_measures_required, interim_measures_detail,
            has_remedial_actions, remedial_actions,

            wall_types,

            has_combustible_cladding, eps_insulation_present,
            mineral_wool_insulation_present, pir_insulation_present,
            phenolic_insulation_present, acrylic_render_present,
            cement_render_present,

            cavity_barriers_present, cavity_barriers_windows, cavity_barriers_floors,
            fire_breaks_floor_level, fire_breaks_party_walls,
            dry_riser_present, wet_riser_present,
            evacuation_strategy,

            bs8414_test_evidence, br135_criteria_met, adb_compliant,

            height_survey_recommended, fire_door_survey_recommended,
            intrusive_investigation_recommended, asbestos_suspected,

            extraction_confidence, fraew_features_json,
            uprn, postcode,

            created_at, updated_at
        )
        VALUES (
            $1,  $2,  $3,  $4,
            $5,  $6,  $7,
            $8,  $9,
            $10, $11, $12,
            $13, $14, $15,
            $16,
            $17, $18,
            $19, $20, $21,
            $22, $23, $24,
            $25, $26,
            $27, $28,
            $29, $30,
            $31, $32::jsonb,
            $33::jsonb,
            $34, $35,
            $36, $37,
            $38, $39,
            $40,
            $41, $42, $43,
            $44, $45,
            $46, $47,
            $48,
            $49, $50, $51,
            $52, $53,
            $54, $55,
            $56, $57::jsonb,
            $58, $59,
            $60, $61
        )
        """,
        uuid.uuid4(),           # $1  fraew_id
        feature_id,             # $2  feature_id
        ha_id,                  # $3  ha_id
        upload_id,              # $4  upload_id

        fs.get("report_reference"),                                     # $5
        fs.get("assessment_date"),                                      # $6  (date str, asyncpg casts)
        fs.get("report_date"),                                          # $7
        fs.get("assessment_valid_until"),                               # $8
        is_in_date,                                                     # $9

        fs.get("assessor_name"),                                        # $10
        fs.get("assessor_company"),                                     # $11
        fs.get("assessor_qualification"),                               # $12
        fs.get("fire_engineer_name"),                                   # $13
        fs.get("fire_engineer_company"),                                # $14
        fs.get("fire_engineer_qualification"),                          # $15
        bool(fs.get("clause_14_applied", False)),                       # $16

        fs.get("building_height_m"),                                    # $17
        height_category,                                                # $18
        fs.get("num_storeys"),                                          # $19
        fs.get("num_units"),                                            # $20
        fs.get("build_year"),                                           # $21
        fs.get("construction_frame_type"),                              # $22
        fs.get("external_wall_base_construction"),                      # $23
        fs.get("retrofit_year"),                                        # $24

        fs.get("pas_9980_version", "2022"),                             # $25
        fs.get("pas_9980_compliant"),                                   # $26
        building_risk_rating,                                           # $27
        rag_status,                                                     # $28

        bool(fs.get("interim_measures_required", False)),               # $29
        fs.get("interim_measures_detail"),                              # $30
        bool(fs.get("has_remedial_actions", False)),                    # $31
        json.dumps(fs.get("remedial_actions") or []),                   # $32 JSONB

        json.dumps(wall_types),                                         # $33 JSONB

        has_combustible,                                                # $34
        _any_insulation("eps") if wall_types else None,                 # $35
        _any_insulation("mineral_wool") if wall_types else None,        # $36
        _any_insulation("pir") if wall_types else None,                 # $37
        _any_insulation("phenolic") if wall_types else None,            # $38
        _any_render("acrylic") if wall_types else None,                 # $39
        _any_render("cement") if wall_types else None,                  # $40

        fs.get("cavity_barriers_present"),                              # $41
        fs.get("cavity_barriers_windows"),                              # $42
        fs.get("cavity_barriers_floors"),                               # $43
        fs.get("fire_breaks_floor_level"),                              # $44
        fs.get("fire_breaks_party_walls"),                              # $45
        fs.get("dry_riser_present"),                                    # $46
        fs.get("wet_riser_present"),                                    # $47
        evacuation_strategy,                                            # $48

        fs.get("bs8414_test_evidence"),                                 # $49
        fs.get("br135_criteria_met"),                                   # $50
        adb_compliant,                                                  # $51

        bool(fs.get("height_survey_recommended", False)),               # $52
        bool(fs.get("fire_door_survey_recommended", False)),            # $53
        bool(fs.get("intrusive_investigation_recommended", False)),     # $54
        bool(fs.get("asbestos_suspected", False)),                      # $55

        fs.get("extraction_confidence", 0.5),                           # $56
        json.dumps(fs) if fs else json.dumps({}),                       # $57 fraew_features_json

        uprn,                                                           # $58
        postcode,                                                       # $59

        now,                                                            # $60 created_at
        now,                                                            # $61 updated_at
    )



async def _write_fra_features(
    conn: asyncpg.Connection,
    *,
    feature_id: uuid.UUID,
    ha_id: str,
    upload_id: uuid.UUID,
    features_json: Dict[str, Any],
) -> None:
    """
    Write FRA-specific features to silver.fra_features (migration 013, 43 columns).

    Reads from features_json.features.fra_specific — the shape produced by the
    updated agentic-feature-definitions.json fed to Bedrock.

    The original function inserted only fra_id, feature_id, ha_id, upload_id, and
    a raw JSON dump. This replacement populates all 43 columns from the new schema.

    Call signature preserved for compatibility.
    """
    features = features_json.get("features", {})
    fs = features.get("fra_specific", {})

    # ------------------------------------------------------------------
    # Derive rag_status (mirrors normalize_fra_rag_status() SQL function)
    # ------------------------------------------------------------------
    def _derive_fra_rag(rating: Optional[str]) -> Optional[str]:
        if not rating:
            return None
        lower = rating.lower().strip()
        no_data = ("n/a", "not assessed", "unknown", "tbc", "tbd", "none")
        if lower in no_data:
            return None
        red_kw  = ("intolerable", "substantial", "high", "critical",
                    "priority 1", "very high", "grade e", "grade d")
        amber_kw = ("moderate", "medium", "significant", "tolerable but",
                     "priority 2", "grade c")
        green_kw = ("trivial", "low", "tolerable", "acceptable", "negligible",
                     "priority 3", "grade a", "grade b")
        if any(kw in lower for kw in red_kw):
            return "RED"
        if any(kw in lower for kw in amber_kw):
            return "AMBER"
        if any(kw in lower for kw in green_kw):
            return "GREEN"
        return "AMBER"  # conservative fallback

    # ------------------------------------------------------------------
    # Derive is_in_date
    # ------------------------------------------------------------------
    def _derive_is_in_date(valid_until_str: Optional[str]) -> Optional[bool]:
        if not valid_until_str:
            return None
        try:
            from datetime import date as _date
            return _date.fromisoformat(valid_until_str) >= _date.today()
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Validate and count action items
    # ------------------------------------------------------------------
    action_items = fs.get("action_items") or []
    valid_priority = ("advisory", "low", "medium", "high")
    valid_status   = ("outstanding", "completed", "overdue")

    # Sanitise each action item before storing
    clean_actions = []
    for a in action_items:
        clean_actions.append({
            "issue_ref":   a.get("issue_ref"),
            "description": a.get("description", ""),
            "hazard_type": a.get("hazard_type"),
            "priority":    a.get("priority") if a.get("priority") in valid_priority else "low",
            "due_date":    a.get("due_date"),
            "status":      a.get("status") if a.get("status") in valid_status else "outstanding",
            "responsible": a.get("responsible"),
        })

    total_count        = len(clean_actions)
    high_priority_count = sum(1 for a in clean_actions if a["priority"] == "high")
    overdue_count      = sum(1 for a in clean_actions if a["status"] == "overdue")
    outstanding_count  = sum(1 for a in clean_actions
                             if a["status"] in ("outstanding", "overdue"))
    no_date_count      = sum(1 for a in clean_actions if not a.get("due_date"))

    # ------------------------------------------------------------------
    # Validate evacuation_strategy
    # ------------------------------------------------------------------
    valid_evac = ("stay_put", "simultaneous", "phased", "temporary_evacuation")
    evacuation_strategy = fs.get("evacuation_strategy")
    if evacuation_strategy not in valid_evac:
        evacuation_strategy = None

    risk_rating = fs.get("risk_rating")
    rag_status  = _derive_fra_rag(risk_rating)
    is_in_date  = _derive_is_in_date(fs.get("assessment_valid_until"))

    now = _utc_now().replace(tzinfo=None)

    await conn.execute(
        """
        INSERT INTO silver.fra_features (
            fra_id, feature_id, ha_id,

            risk_rating, rag_status, fra_assessment_type,
            assessment_date, assessment_valid_until, next_review_date,
            is_in_date,

            assessor_name, assessor_company, assessor_qualification,
            responsible_person,

            evacuation_strategy, evacuation_strategy_changed,
            evacuation_strategy_notes, has_accessibility_needs_noted,

            has_sprinkler_system, has_smoke_detection, has_fire_alarm_system,
            has_fire_doors, has_compartmentation, has_emergency_lighting,
            has_fire_extinguishers, has_firefighting_shaft,
            has_dry_riser, has_wet_riser,

            action_items, significant_findings,
            total_action_count, high_priority_action_count,
            overdue_action_count, outstanding_action_count, no_date_action_count,

            bsa_2022_applicable, accountable_person_noted, mandatory_occurrence_noted,

            extraction_confidence, raw_features,

            created_at, updated_at
        )
        VALUES (
            $1,  $2,  $3,
            $4,  $5,  $6,
            $7,  $8,  $9,
            $10,
            $11, $12, $13,
            $14,
            $15, $16,
            $17, $18,
            $19, $20, $21,
            $22, $23, $24,
            $25, $26,
            $27, $28,
            $29::jsonb, $30::jsonb,
            $31, $32,
            $33, $34, $35,
            $36, $37, $38,
            $39, $40::jsonb,
            $41, $42
        )
        """,
        uuid.uuid4(),       # $1  fra_id
        feature_id,         # $2  feature_id
        ha_id,              # $3  ha_id
        # NOTE: fra_features has no upload_id column in migration 013.
        # If your schema has it, add $4 upload_id and shift remaining params.

        risk_rating,                                                    # $4
        rag_status,                                                     # $5
        fs.get("fra_assessment_type"),                                  # $6

        fs.get("assessment_date"),                                      # $7
        fs.get("assessment_valid_until"),                               # $8
        fs.get("next_review_date"),                                     # $9
        is_in_date,                                                     # $10

        fs.get("assessor_name"),                                        # $11
        fs.get("assessor_company"),                                     # $12
        fs.get("assessor_qualification"),                               # $13
        fs.get("responsible_person"),                                   # $14

        evacuation_strategy,                                            # $15
        bool(fs.get("evacuation_strategy_changed", False)),             # $16
        fs.get("evacuation_strategy_notes"),                            # $17
        bool(fs.get("has_accessibility_needs_noted", False)),           # $18

        fs.get("has_sprinkler_system"),                                 # $19
        fs.get("has_smoke_detection"),                                  # $20
        fs.get("has_fire_alarm_system"),                                # $21
        fs.get("has_fire_doors"),                                       # $22
        fs.get("has_compartmentation"),                                 # $23
        fs.get("has_emergency_lighting"),                               # $24
        fs.get("has_fire_extinguishers"),                               # $25
        fs.get("has_firefighting_shaft"),                               # $26
        fs.get("has_dry_riser"),                                        # $27
        fs.get("has_wet_riser"),                                        # $28

        json.dumps(clean_actions),                                      # $29 action_items
        json.dumps(fs.get("significant_findings") or []),               # $30 significant_findings

        total_count,                                                    # $31
        high_priority_count,                                            # $32
        overdue_count,                                                  # $33
        outstanding_count,                                              # $34
        no_date_count,                                                  # $35

        bool(fs.get("bsa_2022_applicable", False)),                     # $36
        bool(fs.get("accountable_person_noted", False)),                # $37
        bool(fs.get("mandatory_occurrence_noted", False)),              # $38

        float(fs.get("extraction_confidence", 0.5)),                    # $39
        json.dumps(fs),                                                 # $40 raw_features

        now,                                                            # $41 created_at
        now,                                                            # $42 updated_at
    )


async def _write_building_safety_features(
    conn: asyncpg.Connection,
    *,
    feature_id: uuid.UUID,
    ha_id: str,
    upload_id: uuid.UUID,
    features_json: Dict[str, Any],
) -> None:
    """
    Write agentic building safety features (Category A + B) to building_safety_features table.
    
    Extracts features from agentic_features_json or features_json.agentic_features if present.
    """
    features = features_json.get("features", {})
    
    # Check for agentic features in the features JSON
    # They may be in features.agentic_features or at the root level
    agentic_features = features_json.get("agentic_features") or features.get("agentic_features") or {}
    
    # Extract Category A: High-rise indicators
    high_rise = agentic_features.get("high_rise_indicators", {})
    high_rise_mentioned = high_rise.get("high_rise_building_mentioned", False)
    building_height_category = high_rise.get("building_height_category")
    number_of_storeys = high_rise.get("number_of_storeys")
    building_height_metres = high_rise.get("building_height_metres")
    number_of_high_rise_buildings = high_rise.get("number_of_high_rise_buildings")
    building_safety_act_applicable = high_rise.get("building_safety_act_applicable", False)
    
    # Extract Category A: Evacuation strategies
    evacuation = agentic_features.get("evacuation_strategy", {})
    evacuation_mentioned = evacuation.get("evacuation_strategy_mentioned", False)
    evacuation_strategy_type = evacuation.get("evacuation_strategy_type")
    evacuation_strategy_description = evacuation.get("evacuation_strategy_description")
    evacuation_strategy_changed = evacuation.get("evacuation_strategy_changed")
    personal_evacuation_plans_mentioned = evacuation.get("personal_evacuation_plans_mentioned", False)
    evacuation_support_required = evacuation.get("evacuation_support_required")
    
    # Extract Category A: Fire safety measures
    fire_safety = agentic_features.get("fire_safety_measures", {})
    fire_safety_mentioned = fire_safety.get("fire_safety_measures_mentioned", False)
    fire_doors_mentioned = fire_safety.get("fire_doors_mentioned", False)
    fire_safety_officers_mentioned = fire_safety.get("fire_safety_officers_mentioned", False)
    
    # Extract Category A: Structural integrity
    structural = agentic_features.get("structural_integrity", {})
    structural_mentioned = structural.get("structural_integrity_mentioned", False)
    structural_assessments_mentioned = structural.get("structural_assessments_mentioned", False)
    structural_risks_mentioned = structural.get("structural_risks_mentioned", False)
    structural_work_mentioned = structural.get("structural_work_mentioned", False)
    structural_maintenance_required = structural.get("structural_maintenance_required")
    
    # Extract Category A: Maintenance requirements
    maintenance = agentic_features.get("maintenance_requirements", {})
    maintenance_mentioned = maintenance.get("maintenance_mentioned", False)
    maintenance_schedules_mentioned = maintenance.get("maintenance_schedules_mentioned", False)
    maintenance_checks_mentioned = maintenance.get("maintenance_checks_mentioned", False)
    tenancy_audits_mentioned = maintenance.get("tenancy_audits_mentioned", False)
    
    # Extract Category B: Building Safety Act 2022
    bsa = agentic_features.get("building_safety_act_2022", {})
    bsa_mentioned = bsa.get("building_safety_act_2022_mentioned", False)
    bsa_compliance_status = bsa.get("building_safety_act_compliance_status")
    part_4_duties_mentioned = bsa.get("part_4_duties_mentioned", False)
    building_safety_decisions_mentioned = bsa.get("building_safety_decisions_mentioned", False)
    bsr_mentioned = bsa.get("building_safety_regulator_mentioned", False)
    building_safety_case_report_mentioned = bsa.get("building_safety_case_report_mentioned", False)
    
    # Extract Category B: Mandatory Occurrence Reports
    mor = agentic_features.get("mandatory_occurrence_reports", {})
    mor_mentioned = mor.get("mandatory_occurrence_report_mentioned", False)
    mor_process_mentioned = mor.get("mandatory_occurrence_reporting_process_mentioned", False)
    
    # Extract extraction metadata
    extraction_method = features_json.get("extraction_method", "regex")
    comparison_metadata = features_json.get("extraction_comparison_metadata")
    
    # Calculate overall confidence score (average if available)
    agentic_confidence = None
    if agentic_features:
        # Try to extract confidence scores from various feature groups
        confidence_scores = []
        for group in [high_rise, evacuation, fire_safety, structural, maintenance, bsa, mor]:
            if isinstance(group, dict):
                for key, value in group.items():
                    if isinstance(value, dict) and "confidence" in value:
                        confidence_scores.append(value["confidence"])
        if confidence_scores:
            agentic_confidence = sum(confidence_scores) / len(confidence_scores)
    
    # Only insert if we have any agentic features
    if not any([
        high_rise_mentioned, evacuation_mentioned, fire_safety_mentioned,
        structural_mentioned, maintenance_mentioned, bsa_mentioned,
        mor_mentioned, bsr_mentioned
    ]) and not agentic_features:
        return  # No agentic features to store
    
    await conn.execute(
        """
        INSERT INTO silver.building_safety_features (
            safety_feature_id, feature_id, ha_id, upload_id,
            high_rise_building_mentioned, building_height_category, number_of_storeys,
            building_height_metres, number_of_high_rise_buildings, building_safety_act_applicable,
            evacuation_strategy_mentioned, evacuation_strategy_type, evacuation_strategy_description,
            evacuation_strategy_changed, personal_evacuation_plans_mentioned, evacuation_support_required,
            fire_safety_measures_mentioned, fire_doors_mentioned, fire_safety_officers_mentioned,
            structural_integrity_mentioned, structural_assessments_mentioned, structural_risks_mentioned,
            structural_work_mentioned, structural_maintenance_required,
            maintenance_mentioned, maintenance_schedules_mentioned, maintenance_checks_mentioned,
            tenancy_audits_mentioned,
            building_safety_act_2022_mentioned, building_safety_act_compliance_status,
            part_4_duties_mentioned, building_safety_decisions_mentioned,
            building_safety_regulator_mentioned, building_safety_case_report_mentioned,
            mandatory_occurrence_report_mentioned, mandatory_occurrence_reporting_process_mentioned,
            agentic_features_json, extraction_method, agentic_confidence_score,
            extraction_comparison_metadata, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19,
                $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36,
                $37::jsonb, $38, $39, $40::jsonb, $41, $42)
        """,
        uuid.uuid4(),
        feature_id,
        ha_id,
        upload_id,
        high_rise_mentioned,
        building_height_category,
        number_of_storeys,
        building_height_metres,
        number_of_high_rise_buildings,
        building_safety_act_applicable,
        evacuation_mentioned,
        evacuation_strategy_type,
        evacuation_strategy_description,
        evacuation_strategy_changed,
        personal_evacuation_plans_mentioned,
        evacuation_support_required,
        fire_safety_mentioned,
        fire_doors_mentioned,
        fire_safety_officers_mentioned,
        structural_mentioned,
        structural_assessments_mentioned,
        structural_risks_mentioned,
        structural_work_mentioned,
        structural_maintenance_required,
        maintenance_mentioned,
        maintenance_schedules_mentioned,
        maintenance_checks_mentioned,
        tenancy_audits_mentioned,
        bsa_mentioned,
        bsa_compliance_status,
        part_4_duties_mentioned,
        building_safety_decisions_mentioned,
        bsr_mentioned,
        building_safety_case_report_mentioned,
        mor_mentioned,
        mor_process_mentioned,
        json.dumps(agentic_features) if agentic_features else None,
        extraction_method,
        agentic_confidence,
        json.dumps(comparison_metadata) if comparison_metadata else None,
        _utc_now().replace(tzinfo=None),
        _utc_now().replace(tzinfo=None),
    )


async def _write_docb_features(
    conn: asyncpg.Connection,
    *,
    feature_id: uuid.UUID,
    ha_id: str,
    upload_id: uuid.UUID,
    features_json: Dict[str, Any],
) -> None:
    """
    Write DocB/PlanB features (Category C) to docb_features table.
    
    Extracts DocB fields from agentic_features_json or features_json.docb_features if present.
    """
    features = features_json.get("features", {})
    
    # Check for DocB features in the features JSON
    # They may be in features.docb_features, features.agentic_features.docb_required_fields, or at root
    docb_features = (
        features_json.get("docb_features") or
        features.get("docb_features") or
        features.get("agentic_features", {}).get("category_c_docb_planb", {}).get("docb_required_fields", {})
    )
    
    # Extract required DocB fields
    cladding_type = docb_features.get("claddingType") or docb_features.get("cladding_type")
    ews_status = docb_features.get("ewsStatus") or docb_features.get("ews_status")
    fire_risk_management_summary = docb_features.get("fireRiskManagementSummary") or docb_features.get("fire_risk_management_summary")
    docb_ref = docb_features.get("docBRef") or docb_features.get("docb_ref") or docb_features.get("docBRef")
    
    # Extract optional context fields
    optional_fields = docb_features.get("docb_optional_context_fields", {})
    fire_protection = optional_fields.get("fireProtection") or docb_features.get("fireProtection") or docb_features.get("fire_protection")
    alarms = optional_fields.get("alarms") or docb_features.get("alarms")
    evacuation_strategy = optional_fields.get("evacuationStrategy") or docb_features.get("evacuationStrategy") or docb_features.get("evacuation_strategy")
    floors_above_ground = optional_fields.get("floorsAboveGround") or docb_features.get("floorsAboveGround") or docb_features.get("floors_above_ground")
    floors_below_ground = optional_fields.get("floorsBelowGround") or docb_features.get("floorsBelowGround") or docb_features.get("floors_below_ground")
    
    # Extract extraction metadata
    extraction_method = features_json.get("extraction_method", "regex")
    agentic_confidence = None
    if docb_features and isinstance(docb_features, dict):
        # Try to extract confidence score
        confidence_scores = []
        for key, value in docb_features.items():
            if isinstance(value, dict) and "confidence" in value:
                confidence_scores.append(value["confidence"])
        if confidence_scores:
            agentic_confidence = sum(confidence_scores) / len(confidence_scores)
    
    # Only insert if we have any DocB features
    if not any([cladding_type, ews_status, fire_risk_management_summary, docb_ref]) and not docb_features:
        return  # No DocB features to store
    
    await conn.execute(
        """
        INSERT INTO silver.docb_features (
            docb_id, feature_id, ha_id, upload_id,
            cladding_type, ews_status, fire_risk_management_summary, docb_ref,
            fire_protection, alarms, evacuation_strategy,
            floors_above_ground, floors_below_ground,
            docb_features_json, extraction_method, agentic_confidence_score,
            created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb, $15, $16, $17, $18)
        """,
        uuid.uuid4(),
        feature_id,
        ha_id,
        upload_id,
        cladding_type,
        ews_status,
        fire_risk_management_summary,
        docb_ref,
        fire_protection,
        alarms,
        evacuation_strategy,
        floors_above_ground,
        floors_below_ground,
        json.dumps(docb_features) if docb_features else None,
        extraction_method,
        agentic_confidence,
        _utc_now().replace(tzinfo=None),
        _utc_now().replace(tzinfo=None),
    )


async def _update_document_features_with_agentic(
    conn: asyncpg.Connection,
    *,
    feature_id: uuid.UUID,
    features_json: Dict[str, Any],
) -> None:
    """
    Update document_features table with agentic extraction metadata.
    """
    agentic_features = features_json.get("agentic_features")
    extraction_method = features_json.get("extraction_method", "regex")
    comparison_metadata = features_json.get("extraction_comparison_metadata")
    
    if not agentic_features and not comparison_metadata:
        return  # No agentic metadata to store
    
    await conn.execute(
        """
        UPDATE silver.document_features
        SET agentic_features_json = $1::jsonb,
            extraction_method = $2,
            extraction_comparison_metadata = $3::jsonb,
            updated_at = $4
        WHERE feature_id = $5
        """,
        json.dumps(agentic_features) if agentic_features else None,
        extraction_method,
        json.dumps(comparison_metadata) if comparison_metadata else None,
        _utc_now().replace(tzinfo=None),
        feature_id,
    )


async def _update_processing_audit(
    conn: asyncpg.Connection,
    *,
    ha_id: str,
    upload_id: uuid.UUID,
    status: str,
    execution_arn: Optional[str] = None,
) -> None:
    """Update processing_audit to mark Silver layer processing complete."""
    now = _utc_now().replace(tzinfo=None)
    
    await conn.execute(
        """
        INSERT INTO processing_audit (
            processing_id, ha_id, source_type, source_id,
            target_type, target_id, transformation_type,
            started_at, completed_at, status, metadata,
            attempt, max_attempts, last_error, next_attempt_at, retryable, stepfn_execution_arn
        )
        VALUES ($1, $2, 'upload', $3, 'document_features', $4, 'silver_layer_v1',
                $5, $6, $7, $8::jsonb, 1, 1, NULL, NULL, false, $9)
        ON CONFLICT DO NOTHING
        """,
        uuid.uuid4(),
        ha_id,
        upload_id,
        uuid.uuid4(),  # Placeholder target_id
        now,
        now if status == "completed" else None,
        status,
        json.dumps({"silver_layer_processed": True}),
        execution_arn,
    )


async def process_features_to_silver(
    event: Dict[str, Any],
    *,
    db_conn: Optional[asyncpg.Connection] = None,
    db_pool: Optional[asyncpg.Pool] = None,
    upload_service: Optional[UploadService] = None,
) -> Dict[str, Any]:
    """
    Main processing function: Read features.json from S3 and write to Silver layer tables.
    
    Event format (from Step Functions):
    {
        "bucket": "bucket-name",
        "key": "ha_id=.../bronze/dataset=.../.../features.json",
        "execution_arn": "arn:..."
    }
    
    Or from S3 event:
    {
        "Records": [{"s3": {"bucket": {"name": "..."}, "object": {"key": "..."}}}]
    }
    """
    # Parse event to get bucket and key
    if "bucket" in event and "key" in event:
        bucket = event["bucket"]
        key = unquote_plus(event["key"])
        execution_arn = event.get("execution_arn")
    elif "Records" in event and event["Records"]:
        record = event["Records"][0]
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        execution_arn = None
    else:
        raise ValueError("Invalid event format: missing bucket/key or Records")
    
    # Only process features.json files
    if not key.endswith("features.json"):
        return {"status": "ignored", "reason": "not_features_json", "key": key}
    
    # Parse metadata from S3 key
    metadata = _parse_s3_key_for_metadata(key)
    ha_id = metadata["ha_id"]
    upload_id_uuid = uuid.UUID(metadata["submission_id"])
    document_type = metadata["file_type"]
    
    # Handled document types
    handled_types = {
        "fra", "fra_document",
        "fraew", "fraew_document",
        "scr", "scr_document",
        "property_schedule",   # SOV CSV
    }
    if document_type not in handled_types:
        return {"status": "ignored", "reason": "unsupported_document_type", "document_type": document_type}

    # Normalize document type to full name for consistent processing
    document_type_map = {
        "fra": "fra_document",
        "fraew": "fraew_document",
        "scr": "scr_document",
    }
    document_type = document_type_map.get(document_type, document_type)
    
    # S3 helpers (dependency injection support)
    if upload_service is None:
        s3_cfg = S3Config(bucket_name=bucket)
        upload_service = UploadService(s3_cfg)
    
    # Read features.json from S3
    try:
        features_json = upload_service.get_json(key)
    except Exception as e:
        return {
            "status": "failed",
            "reason": "failed_to_read_features",
            "error": str(e),
            "key": key,
        }
    
    # DB connect (dependency injection support)
    conn, should_release = await _get_db_connection(conn=db_conn, pool=db_pool)
    should_close_conn = not should_release and db_conn is None  # Only close if we created direct connection
    try:
        # Set tenant context for RLS
        await conn.execute("SELECT set_config('app.current_ha_id', $1, true)", ha_id)
        
        # -----------------------------------------------------------------
        # SOV / Property Schedule: parse CSV and write to silver layer
        # -----------------------------------------------------------------
        if document_type == "property_schedule":
            csv_s3_key = await conn.fetchval(
                "SELECT s3_key FROM upload_audit WHERE upload_id = $1",
                upload_id_uuid,
            )
            if not csv_s3_key:
                raise ValueError(f"upload_audit row not found for upload_id={upload_id_uuid}")

            csv_bytes = upload_service.get_file(csv_s3_key)

            from backend.workers.sov_processor import SOVProcessor
            processor = SOVProcessor(conn)
            sov_result = await processor.process(
                csv_bytes=csv_bytes,
                upload_id=str(upload_id_uuid),
                ha_id=ha_id,
                filename=csv_s3_key.split("/")[-1],
            )

            await _update_processing_audit(
                conn,
                ha_id=ha_id,
                upload_id=upload_id_uuid,
                status="completed" if sov_result["status"] == "completed" else "failed",
                execution_arn=execution_arn,
            )

            return {
                "status": sov_result["status"],
                "document_type": "property_schedule",
                "ha_id": ha_id,
                "upload_id": str(upload_id_uuid),
                **{k: v for k, v in sov_result.items() if k != "status"},
            }

        # -----------------------------------------------------------------
        # FRA / FRAEW: LLM-powered processor path
        #
        # FRAProcessor / FRAEWProcessor fetch raw PDF text, call the LLM,
        # and write BOTH document_features AND fra_features/fraew_features
        # themselves inside a single transaction — so we do NOT call
        # _write_document_features() or _write_fra/ew_features() here.
        #
        # SCR keeps the original regex path (unchanged).
        # -----------------------------------------------------------------
        if document_type in ("fra_document", "fraew_document"):
            # 1. Retrieve the original PDF S3 key from upload_audit
            pdf_s3_key = await conn.fetchval(
                "SELECT s3_key FROM upload_audit WHERE upload_id = $1",
                upload_id_uuid,
            )
            if not pdf_s3_key:
                raise ValueError(
                    f"upload_audit row not found for upload_id={upload_id_uuid}. "
                    "Cannot fetch source PDF for LLM extraction."
                )

            # 2. Fetch raw PDF bytes from S3
            pdf_bytes = upload_service.get_file(pdf_s3_key)

            # 3. Extract text (same helper used by the ingestion worker)
            from backend.core.pdf_extraction.pdf_pipeline import _extract_text_sample
            text = _extract_text_sample(pdf_bytes, max_pages=15)

            # 4. Create LLM client (reads LLM_PROVIDER + ANTHROPIC_API_KEY from env)
            from backend.workers.llm_client import LLMClient
            llm = LLMClient.from_env()

            # 5. Route to the correct processor — it handles all DB writes
            if document_type == "fra_document":
                from backend.workers.fra_processor import FRAProcessor
                processor = FRAProcessor(conn, llm)
                result = await processor.process(
                    text=text,
                    upload_id=str(upload_id_uuid),
                    block_id=None,          # not yet linked to a block
                    ha_id=ha_id,
                    s3_path=pdf_s3_key,     # kept in signature for logging
                )
            else:  # fraew_document
                from backend.workers.fraew_processor import FRAEWProcessor
                processor = FRAEWProcessor(conn, llm)
                result = await processor.process(
                    text=text,
                    upload_id=str(upload_id_uuid),
                    block_id=None,
                    ha_id=ha_id,
                    s3_path=pdf_s3_key,
                )

            feature_id = uuid.UUID(result["feature_id"])

        else:
            # SCR (and any future non-LLM types): original regex flow
            feature_id = await _write_document_features(
                conn,
                ha_id=ha_id,
                upload_id=upload_id_uuid,
                document_type=document_type,
                features_json=features_json,
            )

            doc_row = await conn.fetchrow(
                "SELECT uprn, postcode FROM silver.document_features WHERE feature_id = $1",
                feature_id,
            )
            uprn = doc_row["uprn"] if doc_row else None
            postcode = doc_row["postcode"] if doc_row else None

            if document_type == "scr_document":
                await _write_scr_features(
                    conn,
                    feature_id=feature_id,
                    ha_id=ha_id,
                    upload_id=upload_id_uuid,
                    features_json=features_json,
                )
        
        # Write agentic building safety features (Category A + B) - applies to all document types
        await _write_building_safety_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id_uuid,
            features_json=features_json,
        )
        
        # Write DocB/PlanB features (Category C) - applies to all document types
        await _write_docb_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id_uuid,
            features_json=features_json,
        )
        
        # Update document_features with agentic extraction metadata
        await _update_document_features_with_agentic(
            conn,
            feature_id=feature_id,
            features_json=features_json,
        )
        
        # Update processing_audit
        await _update_processing_audit(
            conn,
            ha_id=ha_id,
            upload_id=upload_id_uuid,
            status="completed",
            execution_arn=execution_arn,
        )
        
        return {
            "status": "completed",
            "feature_id": str(feature_id),
            "document_type": document_type,
            "ha_id": ha_id,
            "upload_id": str(upload_id_uuid),
        }
    
    except Exception as e:
        # Update processing_audit with failure
        try:
            await _update_processing_audit(
                conn,
                ha_id=ha_id,
                upload_id=upload_id_uuid,
                status="failed",
                execution_arn=execution_arn,
            )
        except Exception:
            pass
        
        return {
            "status": "failed",
            "error": str(e),
            "ha_id": ha_id,
            "upload_id": str(upload_id_uuid),
        }
    
    finally:
        # Handle connection cleanup based on how we got it
        if should_release:
            # Release back to pool (if we acquired from one)
            if db_pool is not None:
                await db_pool.release(conn)
            else:
                # Acquired from DatabasePool, release back
                try:
                    db_pool = DatabasePool.get_pool()
                    await db_pool.release(conn)
                except RuntimeError:
                    # Pool not available, close connection
                    await conn.close()
        elif should_close_conn:
            # Close direct connection we created
            await conn.close()
        # If conn was injected (db_conn provided), don't close or release it


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Lambda-compatible synchronous handler."""
    return asyncio.run(process_features_to_silver(event))