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


async def _write_frsa_features(
    conn: asyncpg.Connection,
    *,
    feature_id: uuid.UUID,
    ha_id: str,
    upload_id: uuid.UUID,
    features_json: Dict[str, Any],
) -> None:
    """Write FRSA-specific features to frsa_features table."""
    features = features_json.get("features", {})
    
    await conn.execute(
        """
        INSERT INTO frsa_features (
            frsa_id, feature_id, ha_id, upload_id,
            frsa_features_json, created_at, updated_at
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
    pdf_types = {"fra_document", "frsa_document", "fraew_document", "scr_document"}
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
        elif document_type == "frsa_document":
            await _write_frsa_features(
                conn,
                feature_id=feature_id,
                ha_id=ha_id,
                upload_id=upload_id_uuid,
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
