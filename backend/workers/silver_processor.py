"""
Silver layer processor: Reads features.json from S3 and writes to normalized PostgreSQL tables.

This processor:
1. Reads features.json from S3 (triggered after extraction completes)
2. Parses and normalizes features based on document type
3. Writes to structured Silver layer tables (document_features, fraew_features, etc.)
4. Updates processing_audit with Silver layer status

This version also adds a unified fire-risk payload contract for FRA/FRAEW so the
frontend can consume a consistent structure for:
- fra
- fraew
- documents
- extraction_errors
- block/property linkage metadata
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
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

    Returns:
        (connection, should_release)
    """
    if conn is not None:
        return conn, False

    if pool is not None:
        return await pool.acquire(), True

    try:
        db_pool = DatabasePool.get_pool()
        return await db_pool.acquire(), True
    except RuntimeError:
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

    Expected format:
    ha_id=<ha_id>/bronze/dataset=<file_type>/ingest_date=YYYY-MM-DD/submission_id=<uuid>/...
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

    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        pass

    try:
        parts = date_str.replace("-", "/").split("/")
        if len(parts) == 3 and len(parts[2]) == 4:
            return datetime(int(parts[2]), int(parts[1]), int(parts[0]), tzinfo=timezone.utc)
    except Exception:
        pass

    return None


def _safe_bool(value: Any) -> Optional[bool]:
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


def _safe_number(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def build_fire_risk_payload(
    *,
    document_type: str,
    upload_id: Optional[str] = None,
    feature_id: Optional[str] = None,
    block_id: Optional[str] = None,
    property_id: Optional[str] = None,
    fra_data: Optional[Dict[str, Any]] = None,
    fraew_data: Optional[Dict[str, Any]] = None,
    extraction_errors: Optional[list[str]] = None,
    raw_features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Unified fire-risk payload contract for frontend/API consumption.
    """
    return {
        "document_type": document_type,
        "upload_id": upload_id,
        "feature_id": feature_id,
        "block_id": block_id,
        "property_id": property_id,
        "fra": fra_data or {},
        "fraew": fraew_data or {},
        "documents": {
            "fra_uploaded": bool(fra_data),
            "fraew_uploaded": bool(fraew_data),
        },
        "extraction_errors": extraction_errors or [],
        "raw_features": raw_features or {},
    }


def normalize_fra_output(features_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize FRA data into a frontend-friendly contract.
    """
    features = features_json.get("features", {})
    fs = features.get("fra_specific", {})

    action_items = fs.get("action_items") or []
    significant_findings = fs.get("significant_findings") or []

    risk_rating = fs.get("risk_rating")
    evacuation_strategy = fs.get("evacuation_strategy")
    next_review_date = fs.get("next_review_date")
    assessment_valid_until = fs.get("assessment_valid_until")

    high_priority_actions = sum(
        1
        for item in action_items
        if str(item.get("priority", "")).lower() == "high"
    )
    overdue_actions = sum(
        1
        for item in action_items
        if str(item.get("status", "")).lower() == "overdue"
    )

    return {
        "risk_level": risk_rating,
        "assessment_type": fs.get("fra_assessment_type"),
        "assessment_date": fs.get("assessment_date"),
        "assessment_valid_until": assessment_valid_until,
        "next_review_date": next_review_date,
        "assessor_name": fs.get("assessor_name"),
        "assessor_company": fs.get("assessor_company"),
        "responsible_person": fs.get("responsible_person"),
        "evacuation_strategy": evacuation_strategy,
        "evacuation_strategy_changed": _safe_bool(fs.get("evacuation_strategy_changed")),
        "evacuation_strategy_notes": fs.get("evacuation_strategy_notes"),
        "accessibility_needs_noted": _safe_bool(fs.get("has_accessibility_needs_noted")),
        "fire_doors": _safe_bool(fs.get("has_fire_doors")),
        "compartmentation": _safe_bool(fs.get("has_compartmentation")),
        "smoke_detection": _safe_bool(fs.get("has_smoke_detection")),
        "fire_alarm_system": _safe_bool(fs.get("has_fire_alarm_system")),
        "sprinkler_system": _safe_bool(fs.get("has_sprinkler_system")),
        "emergency_lighting": _safe_bool(fs.get("has_emergency_lighting")),
        "fire_extinguishers": _safe_bool(fs.get("has_fire_extinguishers")),
        "firefighting_shaft": _safe_bool(fs.get("has_firefighting_shaft")),
        "dry_riser": _safe_bool(fs.get("has_dry_riser")),
        "wet_riser": _safe_bool(fs.get("has_wet_riser")),
        "significant_findings": significant_findings,
        "recommendations": action_items,
        "total_action_count": len(action_items),
        "high_priority_action_count": high_priority_actions,
        "overdue_action_count": overdue_actions,
        "bsa_2022_applicable": _safe_bool(fs.get("bsa_2022_applicable")),
        "accountable_person_noted": _safe_bool(fs.get("accountable_person_noted")),
        "mandatory_occurrence_noted": _safe_bool(fs.get("mandatory_occurrence_noted")),
        "extraction_confidence": _safe_number(fs.get("extraction_confidence")),
    }


def normalize_fraew_output(features_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize FRAEW data into a frontend-friendly contract.
    """
    features = features_json.get("features", {})
    fs = features.get("fraew_specific", {})
    wall_types = fs.get("wall_types") or []
    remedial_actions = fs.get("remedial_actions") or []

    cladding_type = _first_non_empty(
        fs.get("external_wall_base_construction"),
        next(
            (
                wt.get("render_type")
                or wt.get("insulation_type")
                or wt.get("construction_type")
                for wt in wall_types
                if isinstance(wt, dict)
            ),
            None,
        ),
    )

    return {
        "report_reference": fs.get("report_reference"),
        "assessment_date": fs.get("assessment_date"),
        "report_date": fs.get("report_date"),
        "assessment_valid_until": fs.get("assessment_valid_until"),
        "risk_level": fs.get("building_risk_rating"),
        "external_wall_risk": fs.get("building_risk_rating"),
        "cladding_type": cladding_type,
        "balcony_risk": fs.get("balcony_risk"),
        "building_height": _safe_number(fs.get("building_height_m")),
        "building_height_category": fs.get("building_height_category"),
        "num_storeys": _safe_int(fs.get("num_storeys")),
        "num_units": _safe_int(fs.get("num_units")),
        "build_year": _safe_int(fs.get("build_year")),
        "construction_frame_type": fs.get("construction_frame_type"),
        "external_wall_base_construction": fs.get("external_wall_base_construction"),
        "retrofit_year": _safe_int(fs.get("retrofit_year")),
        "pas_9980_version": fs.get("pas_9980_version"),
        "pas_9980_compliant": _safe_bool(fs.get("pas_9980_compliant")),
        "remediation_required": _safe_bool(fs.get("has_remedial_actions")),
        "interim_measures_required": _safe_bool(fs.get("interim_measures_required")),
        "interim_measures_detail": fs.get("interim_measures_detail"),
        "recommendations": remedial_actions,
        "wall_types": wall_types,
        "has_combustible_cladding": _safe_bool(fs.get("has_combustible_cladding")),
        "cavity_barriers_present": _safe_bool(fs.get("cavity_barriers_present")),
        "dry_riser_present": _safe_bool(fs.get("dry_riser_present")),
        "wet_riser_present": _safe_bool(fs.get("wet_riser_present")),
        "evacuation_strategy": fs.get("evacuation_strategy"),
        "bs8414_test_evidence": fs.get("bs8414_test_evidence"),
        "br135_criteria_met": _safe_bool(fs.get("br135_criteria_met")),
        "adb_compliant": fs.get("adb_compliant"),
        "height_survey_recommended": _safe_bool(fs.get("height_survey_recommended")),
        "fire_door_survey_recommended": _safe_bool(fs.get("fire_door_survey_recommended")),
        "intrusive_investigation_recommended": _safe_bool(
            fs.get("intrusive_investigation_recommended")
        ),
        "asbestos_suspected": _safe_bool(fs.get("asbestos_suspected")),
        "extraction_confidence": _safe_number(fs.get("extraction_confidence")),
    }


def build_fire_risk_payload_from_features(
    *,
    document_type: str,
    features_json: Dict[str, Any],
    upload_id: Optional[str] = None,
    feature_id: Optional[str] = None,
    block_id: Optional[str] = None,
    property_id: Optional[str] = None,
    extraction_errors: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Build the unified payload directly from the features.json document.
    """
    fra_data = normalize_fra_output(features_json) if document_type == "fra_document" else {}
    fraew_data = normalize_fraew_output(features_json) if document_type == "fraew_document" else {}

    return build_fire_risk_payload(
        document_type=document_type,
        upload_id=upload_id,
        feature_id=feature_id,
        block_id=block_id,
        property_id=property_id,
        fra_data=fra_data,
        fraew_data=fraew_data,
        extraction_errors=extraction_errors,
        raw_features=features_json,
    )


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

    building_name = None
    address = None
    uprn = None
    postcode = None
    assessment_date = None
    job_reference = None
    client_name = None
    assessor_company = None

    if "uprns" in features and features["uprns"]:
        uprn = features["uprns"][0]

    if "postcodes" in features and features["postcodes"]:
        postcode = features["postcodes"][0]

    if "dates" in features and features["dates"]:
        assessment_date = _normalize_date(features["dates"][0])

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
    Write FRAEW-specific features to silver.fraew_features.
    """
    features = features_json.get("features", {})
    fs = features.get("fraew_specific", {})

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
        return "AMBER"

    def _derive_is_in_date(valid_until_str: Optional[str]) -> Optional[bool]:
        if not valid_until_str:
            return None
        try:
            from datetime import date as _date

            valid_until = _date.fromisoformat(valid_until_str)
            return valid_until >= _date.today()
        except (ValueError, TypeError):
            return None

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

    building_risk_rating = fs.get("building_risk_rating")
    rag_status = _derive_fraew_rag(building_risk_rating)
    is_in_date = _derive_is_in_date(fs.get("assessment_valid_until"))

    valid_height_cats = ("under_11m", "11_to_18m", "18_to_30m", "over_30m", "unknown")
    height_category = fs.get("building_height_category")
    if height_category not in valid_height_cats:
        height_category = None

    valid_adb = ("compliant", "non_compliant", "uncertain", "not_applicable")
    adb_compliant = fs.get("adb_compliant")
    if adb_compliant not in valid_adb:
        adb_compliant = None

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
        uuid.uuid4(),
        feature_id,
        ha_id,
        upload_id,
        fs.get("report_reference"),
        fs.get("assessment_date"),
        fs.get("report_date"),
        fs.get("assessment_valid_until"),
        is_in_date,
        fs.get("assessor_name"),
        fs.get("assessor_company"),
        fs.get("assessor_qualification"),
        fs.get("fire_engineer_name"),
        fs.get("fire_engineer_company"),
        fs.get("fire_engineer_qualification"),
        bool(fs.get("clause_14_applied", False)),
        fs.get("building_height_m"),
        height_category,
        fs.get("num_storeys"),
        fs.get("num_units"),
        fs.get("build_year"),
        fs.get("construction_frame_type"),
        fs.get("external_wall_base_construction"),
        fs.get("retrofit_year"),
        fs.get("pas_9980_version", "2022"),
        fs.get("pas_9980_compliant"),
        building_risk_rating,
        rag_status,
        bool(fs.get("interim_measures_required", False)),
        fs.get("interim_measures_detail"),
        bool(fs.get("has_remedial_actions", False)),
        json.dumps(fs.get("remedial_actions") or []),
        json.dumps(wall_types),
        has_combustible,
        _any_insulation("eps") if wall_types else None,
        _any_insulation("mineral_wool") if wall_types else None,
        _any_insulation("pir") if wall_types else None,
        _any_insulation("phenolic") if wall_types else None,
        _any_render("acrylic") if wall_types else None,
        _any_render("cement") if wall_types else None,
        fs.get("cavity_barriers_present"),
        fs.get("cavity_barriers_windows"),
        fs.get("cavity_barriers_floors"),
        fs.get("fire_breaks_floor_level"),
        fs.get("fire_breaks_party_walls"),
        fs.get("dry_riser_present"),
        fs.get("wet_riser_present"),
        evacuation_strategy,
        fs.get("bs8414_test_evidence"),
        fs.get("br135_criteria_met"),
        adb_compliant,
        bool(fs.get("height_survey_recommended", False)),
        bool(fs.get("fire_door_survey_recommended", False)),
        bool(fs.get("intrusive_investigation_recommended", False)),
        bool(fs.get("asbestos_suspected", False)),
        fs.get("extraction_confidence", 0.5),
        json.dumps(fs) if fs else json.dumps({}),
        uprn,
        postcode,
        now,
        now,
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
    Write FRA-specific features to silver.fra_features.
    """
    features = features_json.get("features", {})
    fs = features.get("fra_specific", {})

    def _derive_fra_rag(rating: Optional[str]) -> Optional[str]:
        if not rating:
            return None
        lower = rating.lower().strip()
        no_data = ("n/a", "not assessed", "unknown", "tbc", "tbd", "none")
        if lower in no_data:
            return None
        red_kw = ("intolerable", "substantial", "high", "critical", "priority 1", "very high", "grade e", "grade d")
        amber_kw = ("moderate", "medium", "significant", "tolerable but", "priority 2", "grade c")
        green_kw = ("trivial", "low", "tolerable", "acceptable", "negligible", "priority 3", "grade a", "grade b")
        if any(kw in lower for kw in red_kw):
            return "RED"
        if any(kw in lower for kw in amber_kw):
            return "AMBER"
        if any(kw in lower for kw in green_kw):
            return "GREEN"
        return "AMBER"

    def _derive_is_in_date(valid_until_str: Optional[str]) -> Optional[bool]:
        if not valid_until_str:
            return None
        try:
            from datetime import date as _date

            return _date.fromisoformat(valid_until_str) >= _date.today()
        except (ValueError, TypeError):
            return None

    action_items = fs.get("action_items") or []
    valid_priority = ("advisory", "low", "medium", "high")
    valid_status = ("outstanding", "completed", "overdue")

    clean_actions = []
    for a in action_items:
        clean_actions.append(
            {
                "issue_ref": a.get("issue_ref"),
                "description": a.get("description", ""),
                "hazard_type": a.get("hazard_type"),
                "priority": a.get("priority") if a.get("priority") in valid_priority else "low",
                "due_date": a.get("due_date"),
                "status": a.get("status") if a.get("status") in valid_status else "outstanding",
                "responsible": a.get("responsible"),
            }
        )

    total_count = len(clean_actions)
    high_priority_count = sum(1 for a in clean_actions if a["priority"] == "high")
    overdue_count = sum(1 for a in clean_actions if a["status"] == "overdue")
    outstanding_count = sum(1 for a in clean_actions if a["status"] in ("outstanding", "overdue"))
    no_date_count = sum(1 for a in clean_actions if not a.get("due_date"))

    valid_evac = ("stay_put", "simultaneous", "phased", "temporary_evacuation")
    evacuation_strategy = fs.get("evacuation_strategy")
    if evacuation_strategy not in valid_evac:
        evacuation_strategy = None

    risk_rating = fs.get("risk_rating")
    rag_status = _derive_fra_rag(risk_rating)
    is_in_date = _derive_is_in_date(fs.get("assessment_valid_until"))

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
        uuid.uuid4(),
        feature_id,
        ha_id,
        risk_rating,
        rag_status,
        fs.get("fra_assessment_type"),
        fs.get("assessment_date"),
        fs.get("assessment_valid_until"),
        fs.get("next_review_date"),
        is_in_date,
        fs.get("assessor_name"),
        fs.get("assessor_company"),
        fs.get("assessor_qualification"),
        fs.get("responsible_person"),
        evacuation_strategy,
        bool(fs.get("evacuation_strategy_changed", False)),
        fs.get("evacuation_strategy_notes"),
        bool(fs.get("has_accessibility_needs_noted", False)),
        fs.get("has_sprinkler_system"),
        fs.get("has_smoke_detection"),
        fs.get("has_fire_alarm_system"),
        fs.get("has_fire_doors"),
        fs.get("has_compartmentation"),
        fs.get("has_emergency_lighting"),
        fs.get("has_fire_extinguishers"),
        fs.get("has_firefighting_shaft"),
        fs.get("has_dry_riser"),
        fs.get("has_wet_riser"),
        json.dumps(clean_actions),
        json.dumps(fs.get("significant_findings") or []),
        total_count,
        high_priority_count,
        overdue_count,
        outstanding_count,
        no_date_count,
        bool(fs.get("bsa_2022_applicable", False)),
        bool(fs.get("accountable_person_noted", False)),
        bool(fs.get("mandatory_occurrence_noted", False)),
        float(fs.get("extraction_confidence", 0.5)),
        json.dumps(fs),
        now,
        now,
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
    """
    features = features_json.get("features", {})
    agentic_features = features_json.get("agentic_features") or features.get("agentic_features") or {}

    high_rise = agentic_features.get("high_rise_indicators", {})
    evacuation = agentic_features.get("evacuation_strategy", {})
    fire_safety = agentic_features.get("fire_safety_measures", {})
    structural = agentic_features.get("structural_integrity", {})
    maintenance = agentic_features.get("maintenance_requirements", {})
    bsa = agentic_features.get("building_safety_act_2022", {})
    mor = agentic_features.get("mandatory_occurrence_reports", {})

    extraction_method = features_json.get("extraction_method", "regex")
    comparison_metadata = features_json.get("extraction_comparison_metadata")

    agentic_confidence = None
    if agentic_features:
        confidence_scores = []
        for group in [high_rise, evacuation, fire_safety, structural, maintenance, bsa, mor]:
            if isinstance(group, dict):
                for _, value in group.items():
                    if isinstance(value, dict) and "confidence" in value:
                        confidence_scores.append(value["confidence"])
        if confidence_scores:
            agentic_confidence = sum(confidence_scores) / len(confidence_scores)

    if not any(
        [
            high_rise.get("high_rise_building_mentioned", False),
            evacuation.get("evacuation_strategy_mentioned", False),
            fire_safety.get("fire_safety_measures_mentioned", False),
            structural.get("structural_integrity_mentioned", False),
            maintenance.get("maintenance_mentioned", False),
            bsa.get("building_safety_act_2022_mentioned", False),
            mor.get("mandatory_occurrence_report_mentioned", False),
            bsa.get("building_safety_regulator_mentioned", False),
        ]
    ) and not agentic_features:
        return

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
        high_rise.get("high_rise_building_mentioned", False),
        high_rise.get("building_height_category"),
        high_rise.get("number_of_storeys"),
        high_rise.get("building_height_metres"),
        high_rise.get("number_of_high_rise_buildings"),
        high_rise.get("building_safety_act_applicable", False),
        evacuation.get("evacuation_strategy_mentioned", False),
        evacuation.get("evacuation_strategy_type"),
        evacuation.get("evacuation_strategy_description"),
        evacuation.get("evacuation_strategy_changed"),
        evacuation.get("personal_evacuation_plans_mentioned", False),
        evacuation.get("evacuation_support_required"),
        fire_safety.get("fire_safety_measures_mentioned", False),
        fire_safety.get("fire_doors_mentioned", False),
        fire_safety.get("fire_safety_officers_mentioned", False),
        structural.get("structural_integrity_mentioned", False),
        structural.get("structural_assessments_mentioned", False),
        structural.get("structural_risks_mentioned", False),
        structural.get("structural_work_mentioned", False),
        structural.get("structural_maintenance_required"),
        maintenance.get("maintenance_mentioned", False),
        maintenance.get("maintenance_schedules_mentioned", False),
        maintenance.get("maintenance_checks_mentioned", False),
        maintenance.get("tenancy_audits_mentioned", False),
        bsa.get("building_safety_act_2022_mentioned", False),
        bsa.get("building_safety_act_compliance_status"),
        bsa.get("part_4_duties_mentioned", False),
        bsa.get("building_safety_decisions_mentioned", False),
        bsa.get("building_safety_regulator_mentioned", False),
        bsa.get("building_safety_case_report_mentioned", False),
        mor.get("mandatory_occurrence_report_mentioned", False),
        mor.get("mandatory_occurrence_reporting_process_mentioned", False),
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
    """
    features = features_json.get("features", {})

    docb_features = (
        features_json.get("docb_features")
        or features.get("docb_features")
        or features.get("agentic_features", {}).get("category_c_docb_planb", {}).get("docb_required_fields", {})
    )

    cladding_type = docb_features.get("claddingType") or docb_features.get("cladding_type")
    ews_status = docb_features.get("ewsStatus") or docb_features.get("ews_status")
    fire_risk_management_summary = (
        docb_features.get("fireRiskManagementSummary")
        or docb_features.get("fire_risk_management_summary")
    )
    docb_ref = docb_features.get("docBRef") or docb_features.get("docb_ref")

    optional_fields = docb_features.get("docb_optional_context_fields", {})
    fire_protection = optional_fields.get("fireProtection") or docb_features.get("fireProtection") or docb_features.get("fire_protection")
    alarms = optional_fields.get("alarms") or docb_features.get("alarms")
    evacuation_strategy = optional_fields.get("evacuationStrategy") or docb_features.get("evacuationStrategy") or docb_features.get("evacuation_strategy")
    floors_above_ground = optional_fields.get("floorsAboveGround") or docb_features.get("floorsAboveGround") or docb_features.get("floors_above_ground")
    floors_below_ground = optional_fields.get("floorsBelowGround") or docb_features.get("floorsBelowGround") or docb_features.get("floors_below_ground")

    extraction_method = features_json.get("extraction_method", "regex")
    agentic_confidence = None
    if docb_features and isinstance(docb_features, dict):
        confidence_scores = []
        for _, value in docb_features.items():
            if isinstance(value, dict) and "confidence" in value:
                confidence_scores.append(value["confidence"])
        if confidence_scores:
            agentic_confidence = sum(confidence_scores) / len(confidence_scores)

    if not any([cladding_type, ews_status, fire_risk_management_summary, docb_ref]) and not docb_features:
        return

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
        return

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
        uuid.uuid4(),
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
    """
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

    if not key.endswith("features.json"):
        return {"status": "ignored", "reason": "not_features_json", "key": key}

    metadata = _parse_s3_key_for_metadata(key)
    ha_id = metadata["ha_id"]
    upload_id_uuid = uuid.UUID(metadata["submission_id"])
    document_type = metadata["file_type"]

    handled_types = {
        "fra",
        "fra_document",
        "fraew",
        "fraew_document",
        "scr",
        "scr_document",
        "property_schedule",
    }
    if document_type not in handled_types:
        return {"status": "ignored", "reason": "unsupported_document_type", "document_type": document_type}

    document_type_map = {
        "fra": "fra_document",
        "fraew": "fraew_document",
        "scr": "scr_document",
    }
    document_type = document_type_map.get(document_type, document_type)

    if upload_service is None:
        s3_cfg = S3Config(bucket_name=bucket)
        upload_service = UploadService(s3_cfg)

    try:
        features_json = upload_service.get_json(key)
    except Exception as e:
        return {
            "status": "failed",
            "reason": "failed_to_read_features",
            "error": str(e),
            "key": key,
        }

    conn, should_release = await _get_db_connection(conn=db_conn, pool=db_pool)
    should_close_conn = not should_release and db_conn is None

    try:
        await conn.execute("SELECT set_config('app.current_ha_id', $1, true)", ha_id)

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

        fire_risk_payload: Optional[Dict[str, Any]] = None

        if document_type in ("fra_document", "fraew_document"):
            pdf_s3_key = await conn.fetchval(
                "SELECT s3_key FROM upload_audit WHERE upload_id = $1",
                upload_id_uuid,
            )
            if not pdf_s3_key:
                raise ValueError(
                    f"upload_audit row not found for upload_id={upload_id_uuid}. "
                    "Cannot fetch source PDF for LLM extraction."
                )

            pdf_bytes = upload_service.get_file(pdf_s3_key)

            from backend.core.pdf_extraction.pdf_pipeline import _extract_text_sample
            from backend.workers.llm_client import LLMClient

            text = _extract_text_sample(pdf_bytes, max_pages=15)
            llm = LLMClient.from_env()

            if document_type == "fra_document":
                from backend.workers.fra_processor import FRAProcessor

                processor = FRAProcessor(conn, llm)
                result = await processor.process(
                    text=text,
                    upload_id=str(upload_id_uuid),
                    block_id=None,
                    ha_id=ha_id,
                    s3_path=pdf_s3_key,
                )
            else:
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

            fire_risk_payload = build_fire_risk_payload_from_features(
                document_type=document_type,
                features_json=features_json,
                upload_id=str(upload_id_uuid),
                feature_id=str(feature_id),
                block_id=None,
                property_id=None,
                extraction_errors=[],
            )

        else:
            feature_id = await _write_document_features(
                conn,
                ha_id=ha_id,
                upload_id=upload_id_uuid,
                document_type=document_type,
                features_json=features_json,
            )

        await _write_building_safety_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id_uuid,
            features_json=features_json,
        )

        await _write_docb_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id_uuid,
            features_json=features_json,
        )

        await _update_document_features_with_agentic(
            conn,
            feature_id=feature_id,
            features_json=features_json,
        )

        await _update_processing_audit(
            conn,
            ha_id=ha_id,
            upload_id=upload_id_uuid,
            status="completed",
            execution_arn=execution_arn,
        )

        response: Dict[str, Any] = {
            "status": "completed",
            "feature_id": str(feature_id),
            "document_type": document_type,
            "ha_id": ha_id,
            "upload_id": str(upload_id_uuid),
        }

        if fire_risk_payload:
            response["fire_risk_payload"] = fire_risk_payload

        return response

    except Exception as e:
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

        error_response: Dict[str, Any] = {
            "status": "failed",
            "error": str(e),
            "ha_id": ha_id,
            "upload_id": str(upload_id_uuid),
        }

        if document_type in ("fra_document", "fraew_document"):
            error_response["fire_risk_payload"] = build_fire_risk_payload(
                document_type=document_type,
                upload_id=str(upload_id_uuid),
                feature_id=None,
                block_id=None,
                property_id=None,
                fra_data={} if document_type != "fra_document" else None,
                fraew_data={} if document_type != "fraew_document" else None,
                extraction_errors=[str(e)],
                raw_features=features_json,
            )

        return error_response

    finally:
        if should_release:
            if db_pool is not None:
                await db_pool.release(conn)
            else:
                try:
                    db_pool = DatabasePool.get_pool()
                    await db_pool.release(conn)
                except RuntimeError:
                    await conn.close()
        elif should_close_conn:
            await conn.close()


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Lambda-compatible synchronous handler."""
    return asyncio.run(process_features_to_silver(event))