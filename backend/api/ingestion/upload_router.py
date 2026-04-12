"""
FastAPI router for file uploads and unified ingestion.
"""
from __future__ import annotations

import asyncio
import decimal
import hashlib
import io
import json
import logging
import os
import uuid
from datetime import date, datetime
from typing import Literal, Optional, List, Tuple, Any

import pdfplumber
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
    HTTPException,
    Query,
    status,
    BackgroundTasks,
)
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.api.ingestion.file_type_detector import FileTypeDetector, FileType
from backend.api.ingestion.upload_models import (
    UploadResponse,
    UploadStatusResponse,
    UploadListResponse,
    BatchUploadResponse,
)
from backend.api.ingestion.upload_validator import UploadValidator
from backend.core.audit.audit_logger import get_audit_logger
from backend.core.database.db_pool import DatabasePool
from backend.core.pdf_extraction.pdf_pipeline import (
    build_pdf_artifacts,
    is_pdf_type,
    agent_assisted_interpretation_placeholder,
)
from backend.core.tenancy.tenant_middleware import TenantMiddleware
from backend.workers.sov_processor_v2 import process_sov_to_silver
from infrastructure.storage.upload_service import get_upload_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/upload", tags=["upload"])
security = HTTPBearer(auto_error=False)
validator = UploadValidator()
detector = FileTypeDetector()
middleware = TenantMiddleware()


def _is_true_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


def _is_local_dev() -> bool:
    return _is_true_env("LOCAL_DEV") or _is_true_env("DEV_MODE")


def _get_dev_tenant() -> Tuple[str, str]:
    return (
        os.getenv("DEV_HA_ID", "ha_demo"),
        os.getenv("DEV_USER_ID", "dev_user"),
    )


def _get_upload_status() -> str:
    """
    Return initial upload status based on environment.

    In LOCAL_DEV mode (no background worker), files are marked as 'completed'.
    In AWS/production (with Step Functions worker), files are 'queued'.
    """
    return "completed" if _is_true_env("LOCAL_DEV") else "queued"


def _derive_sidecar_keys(s3_key: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Derive manifest.json and metadata.json keys from a stored source file key.
    """
    if not s3_key:
        return (None, None)

    if "/file=" in s3_key:
        prefix = s3_key.split("/file=", 1)[0] + "/"
        return (prefix + "manifest.json", prefix + "metadata.json")

    if "/" in s3_key:
        prefix = s3_key.rsplit("/", 1)[0] + "/"
        return (prefix + "manifest.json", prefix + "metadata.json")

    return (None, None)


def _derive_submission_prefix(s3_key: Optional[str]) -> Optional[str]:
    """
    Best-effort: derive the submission prefix from a stored source file key.
    """
    if not s3_key:
        return None
    if "/file=" in s3_key:
        return s3_key.split("/file=", 1)[0] + "/"
    if "/" in s3_key:
        return s3_key.rsplit("/", 1)[0] + "/"
    return None


def _derive_pdf_artifact_keys(submission_prefix: Optional[str]) -> dict:
    if not submission_prefix:
        return {}
    return {
        "extraction_s3_key": f"{submission_prefix}extraction.json",
        "features_s3_key": f"{submission_prefix}features.json",
        "interpretation_s3_key": f"{submission_prefix}interpretation.json",
    }


def _safe_write_pdf_artifacts(
    *,
    upload_service,
    manifest_s3_key: Optional[str],
    submission_prefix: Optional[str],
    file_content: bytes,
    file_type: str,
    filename: str,
) -> dict:
    """
    Write extraction/features/interpretation JSON sidecars for PDFs.
    """
    if not submission_prefix:
        return {}

    artifacts = build_pdf_artifacts(
        file_content,
        file_type=file_type,
        filename=filename,
    )

    extraction_s3_key = f"{submission_prefix}extraction.json"
    features_s3_key = f"{submission_prefix}features.json"
    interpretation_s3_key = f"{submission_prefix}interpretation.json"

    artifacts.interpretation["inputs"] = {
        "file_type": file_type,
        "extraction_s3_key": extraction_s3_key,
        "features_s3_key": features_s3_key,
    }

    upload_service.put_json(extraction_s3_key, artifacts.extraction)
    upload_service.put_json(features_s3_key, artifacts.features)
    upload_service.put_json(
        interpretation_s3_key,
        agent_assisted_interpretation_placeholder(
            file_type=file_type,
            extraction_s3_key=extraction_s3_key,
            features_s3_key=features_s3_key,
        ),
    )

    if manifest_s3_key:
        upload_service.append_manifest_objects(
            manifest_s3_key,
            new_objects=[
                {
                    "role": "extraction",
                    "filename": "extraction.json",
                    "s3_key": extraction_s3_key,
                    "content_type": "application/json",
                },
                {
                    "role": "features",
                    "filename": "features.json",
                    "s3_key": features_s3_key,
                    "content_type": "application/json",
                },
                {
                    "role": "interpretation",
                    "filename": "interpretation.json",
                    "s3_key": interpretation_s3_key,
                    "content_type": "application/json",
                },
            ],
        )

    return {
        "extraction_s3_key": extraction_s3_key,
        "features_s3_key": features_s3_key,
        "interpretation_s3_key": interpretation_s3_key,
        "pdf_scanned": bool(artifacts.extraction.get("scanned")),
        "pdf_validation": artifacts.extraction.get("validation"),
    }


def _parse_metadata(value) -> Optional[dict]:
    """
    upload_audit.metadata is JSONB, but asyncpg may return it as a string.
    Normalize to dict for API responses.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {"raw": value}
    try:
        return dict(value)
    except Exception:
        return {"raw": str(value)}


def _make_serializable(obj):
    """Recursively convert non-JSON-serializable values."""
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, set):
        return sorted(_make_serializable(v) for v in obj)
    if isinstance(obj, (int, float, str)):
        return obj
    return str(obj)


def _extract_pdf_text_full(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF using pdfplumber (all pages)."""
    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            parts = []
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text and text.strip():
                parts.append(text.strip())
            elif not parts:
                words = page.extract_words(x_tolerance=3, y_tolerance=3)
                if words:
                    parts.append(" ".join(w["text"] for w in words))
            try:
                for table in page.extract_tables():
                    for row in table:
                        if row:
                            row_text = " | ".join(c.strip() if c else "" for c in row)
                            if row_text.strip(" |"):
                                parts.append(row_text)
            except Exception:
                pass
            if parts:
                pages.append(f"[Page {page_num}]\n" + "\n".join(parts))
    return "\n\n".join(pages)


def _fallback_local_upload_metadata(
    *,
    ha_id: str,
    user_id: str,
    filename: str,
    file_type: str,
    file_content: bytes,
) -> tuple[str, Optional[str], str]:
    """
    Local fallback when S3/LocalStack is unavailable.
    Returns (upload_id, s3_key, checksum).
    """
    upload_id = str(uuid.uuid4())
    checksum = hashlib.sha256(file_content).hexdigest()
    fake_key = (
        f"local-dev/ha_id={ha_id}/dataset={file_type}/submission_id={upload_id}/file={filename}"
    )
    logger.warning(
        "[UPLOAD] Falling back to local-only upload metadata for %s (ha_id=%s user_id=%s)",
        filename,
        ha_id,
        user_id,
    )
    return upload_id, fake_key, checksum


async def _store_upload_best_effort(
    *,
    ha_id: str,
    user_id: str,
    filename: str,
    file_type: str,
    file_content: bytes,
) -> tuple[str, Optional[str], str, dict]:
    """
    Try to upload to storage. In local dev, do not fail the whole request if
    LocalStack/S3 is unavailable.
    """
    upload_service = get_upload_service()

    try:
        upload_id, s3_key, checksum = upload_service.upload_file(
            ha_id=ha_id,
            file_content=file_content,
            filename=filename,
            file_type=file_type,
            user_id=user_id,
        )
        return upload_id, s3_key, checksum, {"storage_mode": "s3"}
    except Exception as exc:
        if not _is_local_dev():
            raise

        logger.warning("[UPLOAD] Storage unavailable in local dev: %s", exc)
        upload_id, s3_key, checksum = _fallback_local_upload_metadata(
            ha_id=ha_id,
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            file_content=file_content,
        )
        return upload_id, s3_key, checksum, {
            "storage_mode": "local-dev-fallback",
            "storage_warning": str(exc),
        }


async def _audit_upload_best_effort(
    *,
    upload_id: str,
    ha_id: str,
    file_type: str,
    filename: str,
    s3_key: Optional[str],
    metadata: dict,
    checksum: str,
    file_size: int,
    user_id: str,
    status_value: str,
) -> None:
    """
    Try to write audit log. In local dev, do not fail the whole ingestion flow
    if audit logging is unavailable.
    """
    try:
        audit_logger = get_audit_logger()
        await audit_logger.log_upload(
            upload_id=upload_id,
            ha_id=ha_id,
            file_type=file_type,
            filename=filename,
            s3_key=s3_key,
            metadata=metadata,
            checksum=checksum,
            file_size=file_size,
            user_id=user_id,
            status=status_value,
        )
    except Exception as exc:
        if not _is_local_dev():
            raise
        logger.warning("[UPLOAD] Audit logging skipped in local dev: %s", exc)


def _run_enrichment_sync(
    ha_id: str,
    places_key: str = "",
    ngd_key: str = "",
    epc_email: str = "",
    epc_key: str = "",
    limit: int = 0,
) -> None:
    """
    Run the async enrichment worker in its own event loop.

    This is sync on purpose so FastAPI background tasks execute it in a worker
    thread without delaying the request response.
    """
    try:
        from backend.workers.enrichment_worker import enrich_portfolio

        asyncio.run(
            enrich_portfolio(
                ha_id=ha_id,
                places_key=places_key,
                ngd_key=ngd_key,
                epc_email=epc_email,
                epc_key=epc_key,
                limit=limit,
            )
        )
    except Exception as exc:
        logger.exception("[INGEST] Background enrichment crashed for ha_id=%s: %s", ha_id, exc)


def _queue_enrichment_background(
    background_tasks: BackgroundTasks,
    ha_id: str,
    limit: int = 50,
) -> str:
    """
    Queue enrichment safely in the background without delaying the API response.
    """
    try:
        background_tasks.add_task(
            _run_enrichment_sync,
            ha_id,
            "",
            "",
            "",
            "",
            limit,
        )
        logger.info(
            "[INGEST] Enrichment background task queued for ha_id=%s limit=%s",
            ha_id,
            limit,
        )
        return f"Enrichment queued in background (limit {limit})."
    except Exception as exc:
        logger.warning("[INGEST] Failed to queue enrichment: %s", exc)
        return f"Enrichment not queued: {exc}"


async def get_tenant_info(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Tuple[str, str]:
    """
    Standard tenant extraction.

    DEV_MODE:
    - no token -> dev tenant
    - bad token -> dev tenant
    """
    dev_mode = _is_true_env("DEV_MODE")
    dev_ha_id, dev_user_id = _get_dev_tenant()

    if dev_mode:
        if not credentials:
            return (dev_ha_id, dev_user_id)
        try:
            return middleware.extract_tenant_from_token(credentials.credentials)
        except HTTPException:
            return (dev_ha_id, dev_user_id)

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return middleware.extract_tenant_from_token(credentials.credentials)


async def get_ingest_tenant_info(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Tuple[str, str]:
    """
    Tenant extraction specifically for /ingest.
    """
    local_dev = _is_true_env("LOCAL_DEV")
    dev_mode = _is_true_env("DEV_MODE")
    dev_ha_id, dev_user_id = _get_dev_tenant()

    if local_dev or dev_mode:
        if not credentials:
            return (dev_ha_id, dev_user_id)
        try:
            return middleware.extract_tenant_from_token(credentials.credentials)
        except HTTPException:
            return (dev_ha_id, dev_user_id)

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return middleware.extract_tenant_from_token(credentials.credentials)


async def _process_single_file(
    file: UploadFile,
    ha_id: str,
    user_id: str,
    file_type: str,
) -> UploadResponse:
    """
    Helper function to process a single file upload.
    """
    validator.validate_and_raise(file, file_type)
    file_content = await file.read()
    filename = file.filename or f"{file_type}.csv"

    upload_id, s3_key, checksum, storage_meta = await _store_upload_best_effort(
        ha_id=ha_id,
        user_id=user_id,
        filename=filename,
        file_type=file_type,
        file_content=file_content,
    )

    manifest_s3_key, metadata_s3_key = _derive_sidecar_keys(s3_key)
    submission_prefix = _derive_submission_prefix(s3_key)

    inline_pdf_extraction = _is_true_env("INLINE_PDF_EXTRACTION")
    pdf_metadata_updates: dict[str, Any] = {}

    if is_pdf_type(file_type=file_type, filename=filename):
        pdf_metadata_updates.update(_derive_pdf_artifact_keys(submission_prefix))
        if inline_pdf_extraction and storage_meta.get("storage_mode") == "s3":
            try:
                upload_service = get_upload_service()
                pdf_metadata_updates.update(
                    _safe_write_pdf_artifacts(
                        upload_service=upload_service,
                        manifest_s3_key=manifest_s3_key,
                        submission_prefix=submission_prefix,
                        file_content=file_content,
                        file_type=file_type,
                        filename=filename,
                    )
                )
            except Exception as exc:
                pdf_metadata_updates["pdf_extraction_error"] = str(exc)

    await _audit_upload_best_effort(
        upload_id=upload_id,
        ha_id=ha_id,
        file_type=file_type,
        filename=filename,
        s3_key=s3_key,
        metadata={
            "manifest_s3_key": manifest_s3_key,
            "metadata_s3_key": metadata_s3_key,
            **storage_meta,
            **pdf_metadata_updates,
        },
        checksum=checksum,
        file_size=len(file_content),
        user_id=user_id,
        status_value=_get_upload_status(),
    )

    if file_type == "property_schedule":
        pool = DatabasePool.get_pool()
        await process_sov_to_silver(
            file_bytes=file_content,
            ha_id=ha_id,
            submission_id=upload_id,
            upload_id=upload_id,
            db_pool=pool,
            filename=filename,
        )

    return UploadResponse(
        success=True,
        upload_id=upload_id,
        ha_id=ha_id,
        filename=filename,
        file_type=file_type,
        s3_key=s3_key,
        manifest_s3_key=manifest_s3_key,
        metadata_s3_key=metadata_s3_key,
        extraction_s3_key=pdf_metadata_updates.get("extraction_s3_key"),
        features_s3_key=pdf_metadata_updates.get("features_s3_key"),
        interpretation_s3_key=pdf_metadata_updates.get("interpretation_s3_key"),
        checksum=checksum,
        file_size=len(file_content),
        uploaded_at=datetime.utcnow(),
        status=_get_upload_status(),
        message=f"Successfully uploaded {filename}",
    )


@router.post("/batch", response_model=BatchUploadResponse)
async def upload_files_batch(
    files: List[UploadFile] = File(...),
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Upload multiple files with automatic type detection.
    """
    ha_id, user_id = tenant
    results = []
    errors = []

    for file in files:
        try:
            file_content = await file.read()

            detected_type = detector.detect_file_type(
                filename=file.filename or "unknown",
                file_content=file_content,
            )

            file_type_str = (
                detected_type.value
                if detected_type != FileType.UNKNOWN
                else "property_schedule"
            )

            filename = file.filename or f"{file_type_str}.csv"
            ext = os.path.splitext(filename)[1].lower()

            if file_type_str not in validator.ALLOWED_TYPES:
                raise ValueError(f"Invalid detected file type: {file_type_str}")
            if ext not in validator.ALLOWED_TYPES[file_type_str]:
                raise ValueError(f"File extension {ext} not allowed for {file_type_str}")

            max_size = validator.MAX_FILE_SIZES.get(file_type_str)
            if max_size and len(file_content) > max_size:
                raise ValueError(
                    f"File size exceeds maximum allowed size of {max_size / (1024 * 1024):.1f} MB"
                )

            upload_id, s3_key, checksum, storage_meta = await _store_upload_best_effort(
                ha_id=ha_id,
                user_id=user_id,
                filename=filename,
                file_type=file_type_str,
                file_content=file_content,
            )

            manifest_s3_key, metadata_s3_key = _derive_sidecar_keys(s3_key)
            submission_prefix = _derive_submission_prefix(s3_key)

            inline_pdf_extraction = _is_true_env("INLINE_PDF_EXTRACTION")
            pdf_metadata_updates: dict[str, Any] = {}

            if is_pdf_type(file_type=file_type_str, filename=filename):
                pdf_metadata_updates.update(_derive_pdf_artifact_keys(submission_prefix))
                if inline_pdf_extraction and storage_meta.get("storage_mode") == "s3":
                    try:
                        upload_service = get_upload_service()
                        pdf_metadata_updates.update(
                            _safe_write_pdf_artifacts(
                                upload_service=upload_service,
                                manifest_s3_key=manifest_s3_key,
                                submission_prefix=submission_prefix,
                                file_content=file_content,
                                file_type=file_type_str,
                                filename=filename,
                            )
                        )
                    except Exception as exc:
                        pdf_metadata_updates["pdf_extraction_error"] = str(exc)

            await _audit_upload_best_effort(
                upload_id=upload_id,
                ha_id=ha_id,
                file_type=file_type_str,
                filename=filename,
                s3_key=s3_key,
                metadata={
                    "manifest_s3_key": manifest_s3_key,
                    "metadata_s3_key": metadata_s3_key,
                    **storage_meta,
                    **pdf_metadata_updates,
                },
                checksum=checksum,
                file_size=len(file_content),
                user_id=user_id,
                status_value=_get_upload_status(),
            )

            results.append(
                UploadResponse(
                    success=True,
                    upload_id=upload_id,
                    ha_id=ha_id,
                    filename=filename,
                    file_type=file_type_str,
                    s3_key=s3_key,
                    manifest_s3_key=manifest_s3_key,
                    metadata_s3_key=metadata_s3_key,
                    extraction_s3_key=pdf_metadata_updates.get("extraction_s3_key"),
                    features_s3_key=pdf_metadata_updates.get("features_s3_key"),
                    interpretation_s3_key=pdf_metadata_updates.get("interpretation_s3_key"),
                    checksum=checksum,
                    file_size=len(file_content),
                    uploaded_at=datetime.utcnow(),
                    status=_get_upload_status(),
                    message=f"Successfully uploaded {filename} (detected as {file_type_str})",
                )
            )

        except Exception as exc:
            errors.append(
                {
                    "filename": file.filename or "unknown",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )

    return BatchUploadResponse(
        total_files=len(files),
        successful=len(results),
        failed=len(errors),
        results=results,
        errors=errors,
    )


@router.post("/epc-data", response_model=UploadResponse)
async def upload_epc_data(
    file: UploadFile = File(...),
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    ha_id, user_id = tenant
    return await _process_single_file(
        file=file,
        ha_id=ha_id,
        user_id=user_id,
        file_type="epc_data",
    )


@router.post("/scr-document", response_model=UploadResponse)
async def upload_scr_document(
    file: UploadFile = File(...),
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    ha_id, user_id = tenant
    return await _process_single_file(
        file=file,
        ha_id=ha_id,
        user_id=user_id,
        file_type="scr_document",
    )


@router.get("/submissions", response_model=UploadListResponse)
async def list_submissions(
    tenant: Tuple[str, str] = Depends(get_tenant_info),
    limit: int = 50,
):
    """
    List recent upload submissions for the current tenant.
    """
    ha_id, _user_id = tenant
    limit = max(1, min(limit, 200))

    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT upload_id, ha_id, filename, file_type, status, uploaded_at, file_size, checksum, metadata
            FROM upload_audit
            WHERE ha_id = $1
            ORDER BY uploaded_at DESC
            LIMIT $2
            """,
            ha_id,
            limit,
        )

    items = []
    for r in rows:
        items.append(
            UploadStatusResponse(
                upload_id=str(r["upload_id"]),
                ha_id=r["ha_id"],
                filename=r["filename"],
                file_type=r["file_type"],
                status=r["status"],
                uploaded_at=r["uploaded_at"],
                file_size=r["file_size"],
                checksum=r["checksum"],
                metadata=_parse_metadata(r["metadata"]),
            )
        )

    return UploadListResponse(items=items)


@router.get("/{upload_id}/status", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Get upload status and metadata.
    """
    ha_id, _user_id = tenant

    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT upload_id, ha_id, filename, file_type, status, uploaded_at, file_size, checksum, metadata
            FROM upload_audit
            WHERE upload_id = $1 AND ha_id = $2
            """,
            upload_id,
            ha_id,
        )

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

    return UploadStatusResponse(
        upload_id=str(row["upload_id"]),
        ha_id=row["ha_id"],
        filename=row["filename"],
        file_type=row["file_type"],
        status=row["status"],
        uploaded_at=row["uploaded_at"],
        file_size=row["file_size"],
        checksum=row["checksum"],
        metadata=_parse_metadata(row["metadata"]),
    )


@router.post("/ingest", summary="Unified ingestion — SoV (Excel) or FRA/FRAEW (PDF)")
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: Literal["sov", "fra", "fraew"] = Query(
        ...,
        description="Select document type: 'sov' for Schedule of Values (Excel), 'fra' for Fire Risk Assessment (PDF), 'fraew' for Fire Risk Appraisal of External Walls (PDF)",
    ),
    block_reference: Optional[str] = Query(
        None,
        description="Block reference (e.g. '02BR') to link FRA/FRAEW to a specific block. If omitted, auto-resolved from block name in PDF.",
    ),
    tenant: Tuple[str, str] = Depends(get_ingest_tenant_info),
):
    """
    Single ingestion endpoint for all document types.

    - sov   -> Excel/CSV Schedule of Values -> processed into silver.properties
    - fra   -> FRA PDF -> Bedrock LLM extraction -> silver.fra_features
    - fraew -> FRAEW PDF -> Bedrock LLM extraction -> silver.fraew_features

    In local dev, this endpoint can run without an Authorization header.
    """
    ha_id, user_id = tenant
    file_content = await file.read()
    filename = file.filename or "upload"

    if not file_content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    auto_detected = detector.detect_file_type(filename=filename, file_content=file_content)

    user_type_map = {
        "sov": FileType.PROPERTY_SCHEDULE,
        "fra": FileType.FRA_DOCUMENT,
        "fraew": FileType.FRAEW_DOCUMENT,
    }
    user_file_type = user_type_map[document_type]

    detection_warning = None
    if auto_detected != FileType.UNKNOWN and auto_detected != user_file_type:
        detection_warning = (
            f"You selected '{document_type}' but the system detected this file as "
            f"'{auto_detected.value}'. Proceeding with your selection."
        )
        logger.warning(
            "Type mismatch for %s: user=%s detected=%s ha_id=%s",
            filename,
            document_type,
            auto_detected.value,
            ha_id,
        )

    ext = os.path.splitext(filename)[1].lower()
    if document_type == "sov" and ext not in [".xlsx", ".xls", ".csv"]:
        raise HTTPException(
            status_code=400,
            detail="SoV must be an Excel or CSV file (.xlsx, .xls, .csv)",
        )
    if document_type in ("fra", "fraew") and ext != ".pdf":
        raise HTTPException(
            status_code=400,
            detail=f"{document_type.upper()} must be a PDF file",
        )

    upload_id, s3_key, checksum, storage_meta = await _store_upload_best_effort(
        ha_id=ha_id,
        user_id=user_id,
        filename=filename,
        file_type=user_file_type.value,
        file_content=file_content,
    )

    await _audit_upload_best_effort(
        upload_id=upload_id,
        ha_id=ha_id,
        file_type=user_file_type.value,
        filename=filename,
        s3_key=s3_key,
        metadata={
            "auto_detected": auto_detected.value,
            "user_selected": document_type,
            **storage_meta,
        },
        checksum=checksum,
        file_size=len(file_content),
        user_id=user_id,
        status_value="processing",
    )

    if document_type == "sov":
        pool = DatabasePool.get_pool()

        try:
            report = await process_sov_to_silver(
                file_bytes=file_content,
                ha_id=ha_id,
                submission_id=upload_id,
                upload_id=upload_id,
                db_pool=pool,
                filename=filename,
            )
        except Exception as exc:
            logger.exception("[INGEST] SoV processing failed for %s", filename)
            raise HTTPException(
                status_code=500,
                detail=f"SoV processing failed: {exc}",
            )

        rows = []
        async with pool.acquire() as conn:
            db_rows = await conn.fetch(
                """
                SELECT
                    property_id,
                    property_reference,
                    submission_id,
                    block_reference,
                    address,
                    address_2,
                    address_3,
                    postcode,
                    occupancy_type,
                    sum_insured,
                    property_type,
                    year_of_build,
                    storeys,
                    units,
                    uprn,
                    parent_uprn,
                    x_coordinate,
                    y_coordinate,
                    country_code,
                    uprn_match_score,
                    uprn_match_description,
                    built_form,
                    total_floor_area_m2,
                    main_fuel,
                    epc_rating,
                    epc_potential_rating,
                    epc_lodgement_date,
                    height_max_m,
                    height_roofbase_m,
                    height_confidence,
                    building_footprint_m2,
                    is_listed,
                    listed_grade,
                    listed_name,
                    listed_reference,
                    enrichment_status,
                    enrichment_source,
                    enriched_at,
                    metadata
                FROM silver.properties
                WHERE ha_id = $1
                  AND submission_id = $2::uuid
                ORDER BY property_reference
                LIMIT 5000
                """,
                ha_id,
                str(upload_id),
            )

            for r in db_rows:
                row = dict(r)
                row["raw"] = _parse_metadata(row.pop("metadata", None))
                rows.append(_make_serializable(row))

        enrichment_message = _queue_enrichment_background(
            background_tasks=background_tasks,
            ha_id=ha_id,
            limit=50,
        )

        logger.info(
            "[INGEST] SoV done — %s rows returned for ha_id=%s",
            len(rows),
            ha_id,
        )

        return JSONResponse(
            content=_make_serializable(
                {
                    "status": "success",
                    "document_type": "sov",
                    "upload_id": upload_id,
                    "filename": filename,
                    "file_size": len(file_content),
                    "s3_key": s3_key,
                    "auto_detected": auto_detected.value,
                    "user_selected": document_type,
                    "detection_warning": detection_warning,
                    "storage": storage_meta,
                    "message": (
                        "SoV processed and written to silver.properties. "
                        f"{enrichment_message}"
                    ),
                    "properties": rows,
                    "summary": report,
                }
            )
        )

    try:
        text = _extract_pdf_text_full(file_content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}")

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted. File may be a scanned/image PDF.",
        )

    try:
        from backend.workers.llm_client import LLMClient

        llm = LLMClient.from_env()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM client error: {exc}")

    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        resolved_block_id: Optional[str] = None
        block_lookup_warning: Optional[str] = None

        if block_reference:
            try:
                row = await conn.fetchrow(
                    "SELECT block_id::text FROM silver.blocks WHERE ha_id=$1 AND name=$2 LIMIT 1",
                    ha_id,
                    block_reference.strip().upper(),
                )
                if row:
                    resolved_block_id = row["block_id"]
                else:
                    block_lookup_warning = (
                        f"block_reference '{block_reference}' not found in silver.blocks"
                    )
            except Exception as exc:
                block_lookup_warning = f"Could not resolve block_reference: {exc}"
                logger.warning("[INGEST] Block lookup failed: %s", exc)

        processor = None
        try:
            if document_type == "fra":
                from backend.workers.fra_processor import FRAProcessor

                processor = FRAProcessor(conn, llm)
                result = await processor.process(
                    text=text,
                    upload_id=str(upload_id),
                    block_id=resolved_block_id,
                    ha_id=ha_id,
                    s3_path=s3_key or "",
                )
            else:
                from backend.workers.fraew_processor import FRAEWProcessor

                processor = FRAEWProcessor(conn, llm)
                result = await processor.process(
                    text=text,
                    upload_id=str(upload_id),
                    block_id=resolved_block_id,
                    ha_id=ha_id,
                    s3_path=s3_key or "",
                )
        except Exception as exc:
            raw_llm = getattr(processor, "last_raw_response", None) if processor else None
            logger.exception("Processor failed for %s", filename)
            return JSONResponse(
                status_code=500,
                content=_make_serializable(
                    {
                        "status": "failed",
                        "document_type": document_type,
                        "upload_id": upload_id,
                        "filename": filename,
                        "error": str(exc),
                        "raw_llm_response": raw_llm,
                        "detection_warning": detection_warning,
                        "block_lookup_warning": block_lookup_warning,
                    }
                ),
            )

    return JSONResponse(
        content=_make_serializable(
            {
                "status": "success",
                "document_type": document_type,
                "upload_id": upload_id,
                "feature_id": result.get("feature_id"),
                "block_id": resolved_block_id,
                "filename": filename,
                "file_size": len(file_content),
                "s3_key": s3_key,
                "text_chars_extracted": len(text),
                "auto_detected": auto_detected.value,
                "user_selected": document_type,
                "detection_warning": detection_warning,
                "block_lookup_warning": block_lookup_warning,
                "storage": storage_meta,
                "message": f"{document_type.upper()} extracted by Bedrock and written to silver.{document_type}_features",
            }
        )
    )