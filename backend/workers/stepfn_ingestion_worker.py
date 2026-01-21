"""
AWS Step Functions worker (AWS-first ingestion).

Triggered by S3 PUT of the *source file* object.
Typical object key:
  ha_id=<ha_id>/bronze/dataset=<file_type>/ingest_date=YYYY-MM-DD/submission_id=<uuid>/file=<filename>

Responsibilities (PDF pipeline):
- Fetch the uploaded PDF from S3
- Detect scanned vs digital text
- Extract structured JSON (words/boxes + best-effort tables)
- Deterministic validation
- Write canonical artifacts: extraction.json, features.json, interpretation.json
- Update upload_audit + processing_audit with retry/attempt state

Note: This module is designed to be used as either:
- Lambda handler (sync wrapper calling async main)
- ECS task entrypoint (invoke async main directly)
"""

from __future__ import annotations

import asyncio
import os
import re
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import asyncpg

from backend.core.pdf_extraction.pdf_pipeline import (
    build_pdf_artifacts,
    is_pdf_type,
    agent_assisted_interpretation_placeholder,
)
from infrastructure.storage.s3_config import S3Config
from infrastructure.storage.upload_service import UploadService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _parse_s3_event(event: Dict[str, Any]) -> Tuple[str, str, Optional[str]]:
    """
    Accept either:
    - Step Functions input: {"bucket": "...", "key": "...", "execution_arn": "..."}
    - S3 event (EventBridge/Lambda): {"Records":[{"s3":{"bucket":{"name":...},"object":{"key":...}}}]}.
    """
    if "bucket" in event and "key" in event:
        return event["bucket"], event["key"], event.get("execution_arn")

    records = event.get("Records") or []
    if not records:
        raise ValueError("No Records in event and no (bucket,key) fields present")
    r0 = records[0]
    bucket = r0["s3"]["bucket"]["name"]
    key = r0["s3"]["object"]["key"]
    return bucket, key, None


@dataclass(frozen=True)
class ParsedKey:
    ha_id: str
    dataset: str
    submission_id: str
    submission_prefix: str


_RE_HA = re.compile(r"ha_id=([^/]+)/")
_RE_DATASET = re.compile(r"dataset=([^/]+)/")
_RE_SUBMISSION = re.compile(r"submission_id=([0-9a-fA-F-]{36})/")


def _parse_partitioned_key(key: str) -> ParsedKey:
    ha = _RE_HA.search(key)
    ds = _RE_DATASET.search(key)
    sub = _RE_SUBMISSION.search(key)
    if not ha or not ds or not sub:
        raise ValueError(f"Key does not match expected partitioning: {key}")
    submission_id = sub.group(1)
    # Prefix ends at submission_id=<uuid>/
    submission_prefix = key.split(f"submission_id={submission_id}/", 1)[0] + f"submission_id={submission_id}/"
    return ParsedKey(
        ha_id=ha.group(1),
        dataset=ds.group(1),
        submission_id=submission_id,
        submission_prefix=submission_prefix,
    )


def _backoff_next_attempt(attempts: int) -> datetime:
    """
    Exponential backoff (capped). attempts is the *new* attempts count.
    """
    base = min(60 * (2 ** max(0, attempts - 1)), 60 * 60 * 6)  # cap at 6h
    return _utc_now() + timedelta(seconds=base)


async def _db_connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        database=os.getenv("DB_NAME", "platform_dev"),
    )


async def _mark_upload_processing(
    conn: asyncpg.Connection,
    upload_id: uuid.UUID,
    ha_id: str,
    execution_arn: Optional[str],
) -> int:
    """
    Increment attempts and mark status=processing.
    Returns updated attempts count.
    """
    now = _utc_now().replace(tzinfo=None)
    row = await conn.fetchrow(
        """
        UPDATE upload_audit
        SET
            status = 'processing',
            processing_attempts = processing_attempts + 1,
            processing_last_attempt_at = $3,
            processing_started_at = COALESCE(processing_started_at, $3),
            stepfn_execution_arn = COALESCE($4, stepfn_execution_arn),
            processing_last_error = NULL,
            processing_next_attempt_at = NULL
        WHERE upload_id = $1 AND ha_id = $2
        RETURNING processing_attempts
        """,
        upload_id,
        ha_id,
        now,
        execution_arn,
    )
    if not row:
        raise ValueError("upload_audit record not found for upload_id/ha_id")
    return int(row["processing_attempts"])


async def _mark_upload_complete(
    conn: asyncpg.Connection,
    upload_id: uuid.UUID,
    ha_id: str,
    status: str,
    metadata_patch: Dict[str, Any],
) -> None:
    now = _utc_now().replace(tzinfo=None)
    await conn.execute(
        """
        UPDATE upload_audit
        SET
            status = $3,
            processing_completed_at = $4,
            processing_last_error = NULL,
            processing_next_attempt_at = NULL,
            metadata = COALESCE(metadata, '{}'::jsonb) || $5::jsonb
        WHERE upload_id = $1 AND ha_id = $2
        """,
        upload_id,
        ha_id,
        status,
        now,
        metadata_patch,
    )


async def _mark_upload_retryable_failure(
    conn: asyncpg.Connection,
    upload_id: uuid.UUID,
    ha_id: str,
    error: str,
    attempts: int,
) -> None:
    now = _utc_now().replace(tzinfo=None)
    next_attempt = _backoff_next_attempt(attempts).replace(tzinfo=None)
    await conn.execute(
        """
        UPDATE upload_audit
        SET
            status = 'retrying',
            processing_last_error = $3,
            processing_next_attempt_at = $4
        WHERE upload_id = $1 AND ha_id = $2
        """,
        upload_id,
        ha_id,
        error[:4000],
        next_attempt,
    )


async def _insert_processing_audit(
    conn: asyncpg.Connection,
    *,
    ha_id: str,
    upload_id: uuid.UUID,
    transformation_type: str,
    status: str,
    attempt: int,
    max_attempts: int,
    execution_arn: Optional[str],
    metadata: Dict[str, Any],
    last_error: Optional[str] = None,
) -> None:
    processing_id = uuid.uuid4()
    now = _utc_now().replace(tzinfo=None)
    await conn.execute(
        """
        INSERT INTO processing_audit (
            processing_id, ha_id, source_type, source_id,
            target_type, target_id, transformation_type,
            started_at, completed_at, status, metadata,
            attempt, max_attempts, last_error, next_attempt_at, retryable, stepfn_execution_arn
        )
        VALUES (
            $1, $2, 'upload', $3,
            'artifact', $4, $5,
            $6, $7, $8, $9::jsonb,
            $10, $11, $12, NULL, true, $13
        )
        """,
        processing_id,
        ha_id,
        upload_id,
        uuid.uuid4(),  # artifact placeholder id (future: stable id per artifact set)
        transformation_type,
        now,
        now if status in {"completed", "failed", "needs_review"} else None,
        status,
        metadata,
        attempt,
        max_attempts,
        (last_error or "")[:4000] if last_error else None,
        execution_arn,
    )


async def process_s3_put(event: Dict[str, Any]) -> Dict[str, Any]:
    bucket, key, execution_arn = _parse_s3_event(event)

    # Guard: only process source objects (avoid loops on sidecars)
    if key.endswith("manifest.json") or key.endswith("metadata.json"):
        return {"status": "ignored", "reason": "sidecar", "bucket": bucket, "key": key}
    if key.endswith("extraction.json") or key.endswith("features.json") or key.endswith("interpretation.json"):
        return {"status": "ignored", "reason": "artifact", "bucket": bucket, "key": key}
    if "/file=" not in key:
        return {"status": "ignored", "reason": "not_a_source_file_key", "bucket": bucket, "key": key}

    parsed = _parse_partitioned_key(key)
    upload_id_uuid = uuid.UUID(parsed.submission_id)

    # If it's not a PDF dataset, no-op for now
    if not is_pdf_type(file_type=parsed.dataset, filename=key):
        return {"status": "ignored", "reason": "not_pdf_dataset", "bucket": bucket, "key": key}

    # S3 helpers
    s3_cfg = S3Config(bucket_name=bucket)
    upload_service = UploadService(s3_cfg)

    # DB connect
    conn = await _db_connect()
    try:
        # Ensure RLS policies (if enabled) allow tenant-scoped access.
        await conn.execute("SELECT set_config('app.current_ha_id', $1, true)", parsed.ha_id)

        attempts = await _mark_upload_processing(conn, upload_id_uuid, parsed.ha_id, execution_arn)

        file_bytes = upload_service.get_file(key)

        artifacts = build_pdf_artifacts(
            file_bytes,
            file_type=parsed.dataset,
            filename=key.split("/file=", 1)[1],
        )

        extraction_key = f"{parsed.submission_prefix}extraction.json"
        features_key = f"{parsed.submission_prefix}features.json"
        interpretation_key = f"{parsed.submission_prefix}interpretation.json"

        # Write artifacts
        artifacts.interpretation["inputs"] = {
            "file_type": parsed.dataset,
            "extraction_s3_key": extraction_key,
            "features_s3_key": features_key,
        }

        upload_service.put_json(extraction_key, artifacts.extraction)
        upload_service.put_json(features_key, artifacts.features)
        upload_service.put_json(
            interpretation_key,
            agent_assisted_interpretation_placeholder(
                file_type=parsed.dataset,
                extraction_s3_key=extraction_key,
                features_s3_key=features_key,
            ),
        )

        # Update or create manifest.
        # This avoids race conditions where Step Functions starts before manifest.json is written.
        manifest_key = f"{parsed.submission_prefix}manifest.json"
        new_objects = [
            {"role": "extraction", "filename": "extraction.json", "s3_key": extraction_key, "content_type": "application/json"},
            {"role": "features", "filename": "features.json", "s3_key": features_key, "content_type": "application/json"},
            {"role": "interpretation", "filename": "interpretation.json", "s3_key": interpretation_key, "content_type": "application/json"},
        ]
        try:
            manifest = upload_service.get_json(manifest_key)
        except Exception:
            source_filename = key.split("/file=", 1)[1]
            manifest = {
                "submission_id": parsed.submission_id,
                "ha_id": parsed.ha_id,
                "dataset": parsed.dataset,
                "ingested_at": _utc_now_iso(),
                "objects": [
                    {
                        "role": "source",
                        "filename": source_filename,
                        "s3_key": key,
                        "checksum": hashlib.sha256(file_bytes).hexdigest(),
                        "file_size": len(file_bytes),
                        "content_type": "application/pdf",
                    },
                    *new_objects,
                ],
            }
            upload_service.put_json(manifest_key, manifest)
        else:
            upload_service.append_manifest_objects(manifest_key, new_objects=new_objects)

        validation = (artifacts.extraction or {}).get("validation") or {}
        is_valid = bool(validation.get("is_valid", True))
        scanned = bool((artifacts.extraction or {}).get("scanned", False))

        final_status = "completed" if is_valid else "needs_review"

        metadata_patch = {
            "extraction_s3_key": extraction_key,
            "features_s3_key": features_key,
            "interpretation_s3_key": interpretation_key,
            "pdf_scanned": scanned,
            "pdf_validation": validation,
        }

        await _mark_upload_complete(conn, upload_id_uuid, parsed.ha_id, final_status, metadata_patch)

        await _insert_processing_audit(
            conn,
            ha_id=parsed.ha_id,
            upload_id=upload_id_uuid,
            transformation_type="pdf_extract_v1",
            status=final_status,
            attempt=attempts,
            max_attempts=int(os.getenv("PDF_PROCESSING_MAX_ATTEMPTS", "5")),
            execution_arn=execution_arn,
            metadata={
                "bucket": bucket,
                "key": key,
                **metadata_patch,
            },
        )

        return {
            "status": final_status,
            "bucket": bucket,
            "key": key,
            "upload_id": parsed.submission_id,
            "ha_id": parsed.ha_id,
            "attempts": attempts,
        }

    except Exception as e:
        # Record retryable failure for observability; Step Functions should perform retries.
        err = f"{type(e).__name__}: {e}"
        try:
            # We may not have incremented attempts if failure was earlier
            row = await conn.fetchrow(
                "SELECT processing_attempts FROM upload_audit WHERE upload_id=$1 AND ha_id=$2",
                upload_id_uuid,
                parsed.ha_id,
            )
            attempts = int(row["processing_attempts"]) if row else 0
            await _mark_upload_retryable_failure(conn, upload_id_uuid, parsed.ha_id, err, attempts)
            await _insert_processing_audit(
                conn,
                ha_id=parsed.ha_id,
                upload_id=upload_id_uuid,
                transformation_type="pdf_extract_v1",
                status="failed",
                attempt=attempts,
                max_attempts=int(os.getenv("PDF_PROCESSING_MAX_ATTEMPTS", "5")),
                execution_arn=execution_arn,
                metadata={"bucket": bucket, "key": key},
                last_error=err,
            )
        except Exception:
            pass
        raise
    finally:
        await conn.close()


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    Lambda-compatible synchronous handler.
    """
    return asyncio.run(process_s3_put(event))

