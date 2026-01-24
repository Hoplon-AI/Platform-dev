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
        INSERT INTO document_features (
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
    Write FRAEW-specific features to fraew_features table.
    
    Args:
        conn: Database connection
        feature_id: Feature ID from document_features
        ha_id: Housing association ID
        upload_id: Upload ID
        features_json: Full features JSON
        uprn: UPRN (denormalized from document_features for query performance)
        postcode: Postcode (denormalized from document_features for query performance)
    """
    features = features_json.get("features", {})
    fraew_specific = features.get("fraew_specific", {})
    
    await conn.execute(
        """
        INSERT INTO fraew_features (
            fraew_id, feature_id, ha_id, upload_id,
            pas_9980_compliant, pas_9980_version,
            building_risk_rating,
            wall_types, has_interim_measures, has_remedial_actions,
            uprn, postcode,
            fraew_features_json, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11, $12, $13::jsonb, $14, $15)
        """,
        uuid.uuid4(),
        feature_id,
        ha_id,
        upload_id,
        fraew_specific.get("pas_9980_compliant", False),
        fraew_specific.get("pas_9980_version"),
        fraew_specific.get("building_risk_rating"),
        json.dumps(fraew_specific.get("wall_types", [])),
        fraew_specific.get("has_interim_measures", False),
        fraew_specific.get("has_remedial_actions", False),
        uprn,
        postcode,
        json.dumps(fraew_specific),
        _utc_now().replace(tzinfo=None),
        _utc_now().replace(tzinfo=None),
    )


async def _write_fra_features(
    conn: asyncpg.Connection,
    *,
    feature_id: uuid.UUID,
    ha_id: str,
    upload_id: uuid.UUID,
    features_json: Dict[str, Any],
) -> None:
    """Write FRA-specific features to fra_features table."""
    features = features_json.get("features", {})
    
    await conn.execute(
        """
        INSERT INTO fra_features (
            fra_id, feature_id, ha_id, upload_id,
            fra_features_json, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
        """,
        uuid.uuid4(),
        feature_id,
        ha_id,
        upload_id,
        json.dumps(features),
        _utc_now().replace(tzinfo=None),
        _utc_now().replace(tzinfo=None),
    )


async def _write_scr_features(
    conn: asyncpg.Connection,
    *,
    feature_id: uuid.UUID,
    ha_id: str,
    upload_id: uuid.UUID,
    features_json: Dict[str, Any],
) -> None:
    """Write SCR-specific features to scr_features table."""
    features = features_json.get("features", {})
    
    await conn.execute(
        """
        INSERT INTO scr_features (
            scr_id, feature_id, ha_id, upload_id,
            scr_features_json, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
        """,
        uuid.uuid4(),
        feature_id,
        ha_id,
        upload_id,
        json.dumps(features),
        _utc_now().replace(tzinfo=None),
        _utc_now().replace(tzinfo=None),
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
        INSERT INTO building_safety_features (
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
        INSERT INTO docb_features (
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
        UPDATE document_features
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
    
    # Only process PDF document types
    pdf_types = {"fra_document", "fraew_document", "scr_document"}
    if document_type not in pdf_types:
        return {"status": "ignored", "reason": "not_pdf_document", "document_type": document_type}
    
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
        
        # Write to document_features (base table)
        feature_id = await _write_document_features(
            conn,
            ha_id=ha_id,
            upload_id=upload_id_uuid,
            document_type=document_type,
            features_json=features_json,
        )
        
        # Get UPRN and postcode from document_features for denormalization
        doc_row = await conn.fetchrow(
            "SELECT uprn, postcode FROM document_features WHERE feature_id = $1",
            feature_id,
        )
        uprn = doc_row["uprn"] if doc_row else None
        postcode = doc_row["postcode"] if doc_row else None
        
        # Write to document-type-specific table
        if document_type == "fraew_document":
            await _write_fraew_features(
                conn,
                feature_id=feature_id,
                ha_id=ha_id,
                upload_id=upload_id_uuid,
                features_json=features_json,
                uprn=uprn,
                postcode=postcode,
            )
        elif document_type == "fra_document":
            await _write_fra_features(
                conn,
                feature_id=feature_id,
                ha_id=ha_id,
                upload_id=upload_id_uuid,
                features_json=features_json,
            )
        elif document_type == "scr_document":
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
