"""
FastAPI router for file uploads.
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, Response
from typing import Optional, List, Tuple, Literal
import decimal
import hashlib
import io
import json
import logging
import os
import re
import uuid
from datetime import date, datetime, timezone

import pdfplumber

from backend.core.database.db_pool import DatabasePool
from backend.api.ingestion.upload_models import (
    UploadRequest, UploadResponse, UploadStatusResponse, UploadListResponse, BatchUploadResponse
)
from backend.api.ingestion.upload_validator import UploadValidator
from backend.api.ingestion.file_type_detector import FileTypeDetector, FileType
from backend.workers.sov_processor_v2 import process_sov_to_silver
from infrastructure.storage.upload_service import get_upload_service
from backend.core.audit.audit_logger import get_audit_logger
from backend.core.tenancy.tenant_middleware import TenantMiddleware
from backend.core.pdf_extraction.pdf_pipeline import (
    build_pdf_artifacts,
    is_pdf_type,
    agent_assisted_interpretation_placeholder,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/upload", tags=["upload"])
security = HTTPBearer(auto_error=False)  # Don't auto-raise on missing token
validator = UploadValidator()
detector = FileTypeDetector()


def _get_upload_status() -> str:
    """Return initial upload status based on environment.

    In LOCAL_DEV mode (no background worker), files are marked as 'completed'.
    In AWS/production (with Step Functions worker), files are 'queued'.

    Note: DEV_MODE controls auth bypass, LOCAL_DEV controls upload status.
    """
    local_dev = os.getenv("LOCAL_DEV", "false").lower() == "true"
    return "completed" if local_dev else "queued"
middleware = TenantMiddleware()

def _derive_sidecar_keys(s3_key: str) -> tuple[Optional[str], Optional[str]]:
    """
    Derive manifest.json and metadata.json keys from a stored source file key.

    Supports both:
    - New scheme: .../submission_id=<uuid>/file=<name>
    - Legacy scheme: .../<upload_id>/<filename>
    """
    if "/file=" in s3_key:
        prefix = s3_key.split("/file=", 1)[0] + "/"
        return (prefix + "manifest.json", prefix + "metadata.json")

    # Fallback: treat parent directory as the submission prefix
    if "/" in s3_key:
        prefix = s3_key.rsplit("/", 1)[0] + "/"
        return (prefix + "manifest.json", prefix + "metadata.json")

    return (None, None)

def _derive_submission_prefix(s3_key: str) -> Optional[str]:
    """
    Best-effort: derive the submission prefix from a stored source file key.

    New scheme: .../submission_id=<uuid>/file=<name>  -> prefix ends with /
    Legacy scheme: .../<upload_id>/<filename>         -> prefix ends with /
    """
    if "/file=" in s3_key:
        return s3_key.split("/file=", 1)[0] + "/"
    if "/" in s3_key:
        return s3_key.rsplit("/", 1)[0] + "/"
    return None


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
    Returns metadata updates: {extraction_s3_key, features_s3_key, interpretation_s3_key, pdf_scanned, pdf_validation}
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

    # Fill interpretation inputs now that we know the S3 keys
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

    # Update manifest to include canonical artifacts (best-effort)
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

def _derive_pdf_artifact_keys(submission_prefix: Optional[str]) -> dict:
    if not submission_prefix:
        return {}
    return {
        "extraction_s3_key": f"{submission_prefix}extraction.json",
        "features_s3_key": f"{submission_prefix}features.json",
        "interpretation_s3_key": f"{submission_prefix}interpretation.json",
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
    # Fallback for unexpected types (e.g. asyncpg.Record/Mapping)
    try:
        return dict(value)
    except Exception:
        return {"raw": str(value)}


async def get_tenant_info(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Tuple[str, str]:
    """
    FastAPI dependency to extract ha_id and user_id from JWT token.
    
    Args:
        credentials: Optional HTTP Bearer credentials from Authorization header
        
    Returns:
        Tuple of (ha_id, user_id)
        
    Raises:
        HTTPException: If authentication is required and token is missing/invalid
    """
    # Check if development mode is enabled (skip auth)
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
    dev_ha_id = os.getenv("DEV_HA_ID", "ha_demo")
    dev_user_id = os.getenv("DEV_USER_ID", "dev_user")
    
    if dev_mode:
        # Development mode: return default values if no token provided
        if not credentials:
            return (dev_ha_id, dev_user_id)
        # If token is provided, still validate it
        try:
            return middleware.extract_tenant_from_token(credentials.credentials)
        except HTTPException:
            # If token is invalid in dev mode, fall back to defaults
            return (dev_ha_id, dev_user_id)
    
    # Production mode: authentication required
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract and validate token
    return middleware.extract_tenant_from_token(credentials.credentials)


async def _process_single_file(
    file: UploadFile,
    ha_id: str,
    user_id: str,
    file_type: str,
) -> UploadResponse:
    """
    Helper function to process a single file upload.
    
    Args:
        file: Uploaded file
        ha_id: Housing Association ID
        user_id: User ID
        file_type: Detected or specified file type
        
    Returns:
        UploadResponse
    """
    # Validate file
    validator.validate_and_raise(file, file_type)
    
    # Read file content
    file_content = await file.read()
    
    # Upload to S3
    upload_service = get_upload_service()
    upload_id, s3_key, checksum = upload_service.upload_file(
        ha_id=ha_id,
        file_content=file_content,
        filename=file.filename or f"{file_type}.csv",
        file_type=file_type,
        user_id=user_id,
    )

    manifest_s3_key, metadata_s3_key = _derive_sidecar_keys(s3_key)
    submission_prefix = _derive_submission_prefix(s3_key)

    # Core pattern: do not do heavy extraction in-request by default.
    inline_pdf_extraction = os.getenv("INLINE_PDF_EXTRACTION", "false").lower() == "true"

    pdf_metadata_updates: dict = {}
    if is_pdf_type(file_type=file_type, filename=file.filename or ""):
        # Always return/record deterministic artifact keys (Step Functions worker will write them)
        pdf_metadata_updates.update(_derive_pdf_artifact_keys(submission_prefix))

        if inline_pdf_extraction:
            # Optional: local/dev inline extraction (best-effort)
            try:
                pdf_metadata_updates.update(
                    _safe_write_pdf_artifacts(
                        upload_service=upload_service,
                        manifest_s3_key=manifest_s3_key,
                        submission_prefix=submission_prefix,
                        file_content=file_content,
                        file_type=file_type,
                        filename=file.filename or "document.pdf",
                    )
                )
            except Exception as e:
                pdf_metadata_updates["pdf_extraction_error"] = str(e)
    
    # Log upload in audit
    audit_logger = get_audit_logger()
    await audit_logger.log_upload(
        upload_id=upload_id,
        ha_id=ha_id,
        file_type=file_type,
        filename=file.filename or f"{file_type}.csv",
        s3_key=s3_key,
        metadata={
            "manifest_s3_key": manifest_s3_key,
            "metadata_s3_key": metadata_s3_key,
            **pdf_metadata_updates,
        },
        checksum=checksum,
        file_size=len(file_content),
        user_id=user_id,
        status=_get_upload_status(),
    )

    if file_type == 'property_schedule':
        pool = DatabasePool.get_pool()
        await process_sov_to_silver(
            file_bytes=file_content,
            ha_id=ha_id,
            submission_id=upload_id,
            upload_id=upload_id,
            db_pool=pool,
        )

    return UploadResponse(
        success=True,
        upload_id=upload_id,
        ha_id=ha_id,
        filename=file.filename or f"{file_type}.csv",
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
        message=f"Successfully uploaded {file.filename}",
    )


@router.post("/batch", response_model=BatchUploadResponse)
async def upload_files_batch(
    files: List[UploadFile] = File(...),
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Upload multiple files with automatic type detection.
    
    Each file is automatically detected and routed to the appropriate handler:
    - Property schedules (CSV/Excel with address/UPRN/postcode)
    - EPC data (CSV/Excel with EPC ratings)
    - FRA documents (PDF - Fire Risk Assessment)
    - FRSA documents (PDF - Fire Risk Safety Assessment)
    - FRAEW documents (PDF - PAS 9980 Fire Risk Appraisal of External Walls)
    - SCR documents (PDF - Safety Case Report)
    
    Args:
        files: List of uploaded files
        tenant: Tuple of (ha_id, user_id) extracted from JWT token
        
    Returns:
        BatchUploadResponse with results for each file
    """
    ha_id, user_id = tenant
    
    results = []
    errors = []
    
    for file in files:
        try:
            # Read file content for detection
            file_content = await file.read()
            
            # Detect file type
            detected_type = detector.detect_file_type(
                filename=file.filename or "unknown",
                file_content=file_content,
            )
            
            # Map FileType enum to string
            file_type_str = detected_type.value if detected_type != FileType.UNKNOWN else 'property_schedule'
            
            # Validate file type (check extension and size)
            filename = file.filename or f"{file_type_str}.csv"
            ext = os.path.splitext(filename)[1].lower()
            if file_type_str not in validator.ALLOWED_TYPES:
                raise ValueError(f"Invalid detected file type: {file_type_str}")
            if ext not in validator.ALLOWED_TYPES[file_type_str]:
                raise ValueError(f"File extension {ext} not allowed for {file_type_str}")
            max_size = validator.MAX_FILE_SIZES.get(file_type_str)
            if max_size and len(file_content) > max_size:
                raise ValueError(f"File size exceeds maximum allowed size of {max_size / (1024*1024):.1f} MB")
            
            # Upload to S3
            upload_service = get_upload_service()
            upload_id, s3_key, checksum = upload_service.upload_file(
                ha_id=ha_id,
                file_content=file_content,
                filename=file.filename or f"{file_type_str}.csv",
                file_type=file_type_str,
                user_id=user_id,
            )

            manifest_s3_key, metadata_s3_key = _derive_sidecar_keys(s3_key)
            submission_prefix = _derive_submission_prefix(s3_key)

            inline_pdf_extraction = os.getenv("INLINE_PDF_EXTRACTION", "false").lower() == "true"

            pdf_metadata_updates: dict = {}
            if is_pdf_type(file_type=file_type_str, filename=file.filename or ""):
                pdf_metadata_updates.update(_derive_pdf_artifact_keys(submission_prefix))
                if inline_pdf_extraction:
                    try:
                        pdf_metadata_updates.update(
                            _safe_write_pdf_artifacts(
                                upload_service=upload_service,
                                manifest_s3_key=manifest_s3_key,
                                submission_prefix=submission_prefix,
                                file_content=file_content,
                                file_type=file_type_str,
                                filename=file.filename or "document.pdf",
                            )
                        )
                    except Exception as e:
                        pdf_metadata_updates["pdf_extraction_error"] = str(e)
            
            # Log upload in audit
            audit_logger = get_audit_logger()
            await audit_logger.log_upload(
                upload_id=upload_id,
                ha_id=ha_id,
                file_type=file_type_str,
                filename=file.filename or f"{file_type_str}.csv",
                s3_key=s3_key,
                metadata={
                    "manifest_s3_key": manifest_s3_key,
                    "metadata_s3_key": metadata_s3_key,
                    **pdf_metadata_updates,
                },
                checksum=checksum,
                file_size=len(file_content),
                user_id=user_id,
                status=_get_upload_status(),
            )
            
            results.append(UploadResponse(
                success=True,
                upload_id=upload_id,
                ha_id=ha_id,
                filename=file.filename or f"{file_type_str}.csv",
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
                message=f"Successfully uploaded {file.filename} (detected as {file_type_str})",
            ))
            
        except Exception as e:
            errors.append({
                'filename': file.filename or 'unknown',
                'error': str(e),
                'error_type': type(e).__name__,
            })
    
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
    """
    Upload EPC rating data (CSV/Excel).
    
    Args:
        file: Uploaded file
        tenant: Tuple of (ha_id, user_id) extracted from JWT token
        
    Returns:
        UploadResponse with upload details
    """
    ha_id, user_id = tenant
    return await _process_single_file(
        file=file,
        ha_id=ha_id,
        user_id=user_id,
        file_type='epc_data',
    )


@router.post("/scr-document", response_model=UploadResponse)
async def upload_scr_document(
    file: UploadFile = File(...),
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Upload SCR document (PDF - Safety Case Report).
    
    Args:
        file: Uploaded file
        tenant: Tuple of (ha_id, user_id) extracted from JWT token
        
    Returns:
        UploadResponse with upload details
    """
    ha_id, user_id = tenant
    return await _process_single_file(
        file=file,
        ha_id=ha_id,
        user_id=user_id,
        file_type='scr_document',
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
    
    Args:
        upload_id: Upload UUID
        ha_id: Housing Association ID
        
    Returns:
        UploadStatusResponse with upload details
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


@router.get("/{upload_id}/file")
async def get_upload_file(
    upload_id: str,
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Stream the original uploaded source file (e.g. an FRA/FRAEW PDF) from S3.

    Used by the Data Provenance section so underwriters can open the source
    document an extraction was derived from. Returns the file inline so the
    browser renders the PDF rather than forcing a download.
    """
    ha_id, _user_id = tenant

    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT s3_key, filename, file_type
            FROM upload_audit
            WHERE upload_id = $1 AND ha_id = $2
            """,
            upload_id,
            ha_id,
        )

    if not row or not row["s3_key"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source file not found")

    try:
        upload_service = get_upload_service()
        content = upload_service.get_file(row["s3_key"])
    except Exception as exc:
        logger.error("Failed to fetch %s from S3: %s", row["s3_key"], exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not retrieve source file from storage")

    filename = row["filename"] or "document"
    ext = os.path.splitext(filename)[1].lower()
    media_type = {
        ".pdf":  "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls":  "application/vnd.ms-excel",
        ".csv":  "text/csv",
    }.get(ext, "application/octet-stream")

    return Response(
        content=content,
        media_type=media_type,
        headers={
            # inline → browser renders PDF in a new tab instead of downloading
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(content)),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for the unified ingest endpoint
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Unified ingest endpoint
# ─────────────────────────────────────────────────────────────────────────────

async def _resolve_or_create_portfolio(conn, ha_id: str, portfolio_id: Optional[str], filename: str) -> str:
    """
    Return a valid portfolio_id for this upload.
    - If portfolio_id provided: verify it belongs to ha_id.
    - If not provided: create a new portfolio row named after the file.
    """
    if portfolio_id:
        row = await conn.fetchrow(
            "SELECT portfolio_id FROM silver.portfolios WHERE portfolio_id = $1::uuid AND ha_id = $2",
            portfolio_id, ha_id,
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Portfolio '{portfolio_id}' not found for this housing association.",
            )
        return portfolio_id

    name = os.path.splitext(filename)[0] if filename else "Portfolio"
    renewal_year = datetime.utcnow().year
    new_id = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO silver.portfolios (portfolio_id, ha_id, name, renewal_year, created_at, updated_at)
        VALUES ($1::uuid, $2, $3, $4, NOW(), NOW())
        """,
        new_id, ha_id, name, renewal_year,
    )
    logger.info("[INGEST] Created portfolio '%s' (%s) for ha_id=%s", name, new_id, ha_id)
    return new_id


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
    portfolio_id: Optional[str] = Query(
        None,
        description="Portfolio UUID to upload into. If omitted for a SoV upload, a new portfolio is created automatically.",
    ),
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Single ingestion endpoint for all document types.

    - **sov**   → Excel/CSV Schedule of Values → processed into silver.properties
    - **fra**   → FRA PDF → Bedrock LLM extraction → silver.fra_features
    - **fraew** → FRAEW PDF → Bedrock LLM extraction → silver.fraew_features

    The system also auto-detects the file type internally. If the user selection
    and auto-detection disagree, the user's selection takes priority and a
    `detection_warning` is included in the response.
    """
    ha_id, user_id = tenant
    file_content = await file.read()
    filename = file.filename or "upload"

    if not file_content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── Step 1: Auto-detect file type internally ──────────────────────────
    auto_detected = detector.detect_file_type(filename=filename, file_content=file_content)

    # Map user selection to FileType for comparison
    user_type_map = {
        "sov":   FileType.PROPERTY_SCHEDULE,
        "fra":   FileType.FRA_DOCUMENT,
        "fraew": FileType.FRAEW_DOCUMENT,
    }
    user_file_type = user_type_map[document_type]

    # ── Step 2: Two-way check ─────────────────────────────────────────────
    detection_warning = None
    if auto_detected != FileType.UNKNOWN and auto_detected != user_file_type:
        detection_warning = (
            f"You selected '{document_type}' but the system detected this file as "
            f"'{auto_detected.value}'. Proceeding with your selection."
        )
        logger.warning(
            "Type mismatch for %s: user=%s detected=%s ha_id=%s",
            filename, document_type, auto_detected.value, ha_id,
        )

    # ── Step 3: Validate extension matches selection ───────────────────────
    ext = os.path.splitext(filename)[1].lower()
    if document_type == "sov" and ext not in [".xlsx", ".xls", ".csv"]:
        raise HTTPException(status_code=400, detail="SoV must be an Excel or CSV file (.xlsx, .xls, .csv)")
    if document_type in ("fra", "fraew") and ext != ".pdf":
        raise HTTPException(status_code=400, detail=f"{document_type.upper()} must be a PDF file")

    # ── Step 4: Upload to S3 + audit log ──────────────────────────────────
    upload_service = get_upload_service()
    upload_id, s3_key, checksum = upload_service.upload_file(
        ha_id=ha_id,
        file_content=file_content,
        filename=filename,
        file_type=user_file_type.value,
        user_id=user_id,
    )

    audit_logger = get_audit_logger()
    await audit_logger.log_upload(
        upload_id=upload_id,
        ha_id=ha_id,
        file_type=user_file_type.value,
        filename=filename,
        s3_key=s3_key,
        metadata={
            "auto_detected": auto_detected.value,
            "user_selected": document_type,
            # Persist the block reference the user typed so the document library
            # can show "Linked to" even when no matching silver.blocks row exists
            # yet (block detection may not have run). Independent of block_id.
            "block_reference": block_reference.strip() if block_reference else None,
        },
        checksum=checksum,
        file_size=len(file_content),
        user_id=user_id,
        status="processing",
    )

    # ── Step 5: Process based on user selection ───────────────────────────

    # SoV → sov_processor_v2 → auto-enrich (background, limit 50)
    if document_type == "sov":
        pool = DatabasePool.get_pool()

        # Resolve or create portfolio before processing so every property row
        # is stamped with the correct portfolio_id from the start.
        async with pool.acquire() as _conn:
            resolved_portfolio_id = await _resolve_or_create_portfolio(
                _conn, ha_id, portfolio_id, filename
            )

        await process_sov_to_silver(
            file_bytes=file_content,
            ha_id=ha_id,
            submission_id=upload_id,
            upload_id=upload_id,
            portfolio_id=resolved_portfolio_id,
            db_pool=pool,
        )

        # Auto-trigger enrichment in the background and register the job so the
        # frontend can poll GET /api/v1/enrich/{ha_id}/status and only reveal the
        # dashboard once enrichment finishes. We mark the job "running"
        # synchronously (before returning) so a re-upload never sees a previous
        # run's stale "complete" during the gap before the task starts.
        from backend.api.enrichment.enrichment_router import _run_background, _active_jobs
        _active_jobs[ha_id] = {"status": "running", "result": None, "target": 50}
        background_tasks.add_task(_run_background, ha_id, 50, resolved_portfolio_id)
        logger.info("[INGEST] SoV done — enrichment queued for ha_id=%s limit=50", ha_id)

        # Fetch property rows back so the frontend can render them immediately
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
                    dwelling_form,
                    is_standalone,
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
                """,
                ha_id, upload_id,
            )
        properties = [dict(r) for r in db_rows]

        return JSONResponse(content=_make_serializable({
            "status": "success",
            "success": True,
            "document_type": "sov",
            "ha_id": ha_id,
            "portfolio_id": resolved_portfolio_id,
            "upload_id": upload_id,
            "filename": filename,
            "file_size": len(file_content),
            "s3_key": s3_key,
            "auto_detected": auto_detected.value,
            "user_selected": document_type,
            "detection_warning": detection_warning,
            "properties": properties,
            "property_count": len(properties),
            "message": f"SoV processed. {len(properties)} properties written to silver. Enrichment running in background.",
        }))

    # FRA / FRAEW → pdfplumber text extraction → Bedrock LLM → silver.*
    try:
        text = _extract_pdf_text_full(file_content)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {e}")

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted. File may be a scanned/image PDF.",
        )

    try:
        from backend.workers.llm_client import LLMClient
        llm = LLMClient.from_env()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM client error: {e}")

    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:

        # Resolve block_id:
        #   1. explicit block_reference param (user-typed) takes priority
        #   2. otherwise AUTO-RESOLVE from the filename — FRA/FRAEW files follow a
        #      naming convention like "FRA_04CR_Clarkston_Road.pdf" where the block
        #      code (e.g. 04CR, 01BR, 03BR) is a token in the name. This removes the
        #      manual block-reference entry that was previously required every upload.
        resolved_block_id: Optional[str] = None
        resolved_block_ref: Optional[str] = None
        resolved_portfolio_id: Optional[str] = None

        candidate_refs: list[str] = []
        if block_reference and block_reference.strip():
            candidate_refs.append(block_reference.strip().upper())
        # Auto-derive candidate block codes from the filename (e.g. 04CR, 01BR, 12HR).
        for token in re.split(r"[ _\-.]+", filename or ""):
            t = token.strip().upper()
            if re.fullmatch(r"\d{1,3}[A-Z]{1,3}", t) and t not in candidate_refs:
                candidate_refs.append(t)

        for ref in candidate_refs:
            row = await conn.fetchrow(
                "SELECT block_id::text, name, portfolio_id::text FROM silver.blocks WHERE ha_id=$1 AND UPPER(name)=$2 LIMIT 1",
                ha_id, ref,
            )
            if row:
                resolved_block_id = row["block_id"]
                resolved_block_ref = row["name"]
                resolved_portfolio_id = row["portfolio_id"]
                logger.info("[INGEST] FRA/FRAEW linked to block '%s' (block_id=%s)", row["name"], resolved_block_id)
                break

        # Fall back to the HA's most recent portfolio so the frontend always has a
        # portfolio_id to re-pull fire documents against (even if no block matched).
        if not resolved_portfolio_id:
            prow = await conn.fetchrow(
                "SELECT portfolio_id::text FROM silver.portfolios WHERE ha_id=$1 ORDER BY created_at DESC LIMIT 1",
                ha_id,
            )
            if prow:
                resolved_portfolio_id = prow["portfolio_id"]

        if not resolved_block_id:
            logger.warning(
                "Could not resolve a block for %s (candidates=%s) — block_id will be NULL",
                filename, candidate_refs,
            )

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
                    s3_path=s3_key,
                )
            else:  # fraew
                from backend.workers.fraew_processor import FRAEWProcessor
                processor = FRAEWProcessor(conn, llm)
                result = await processor.process(
                    text=text,
                    upload_id=str(upload_id),
                    block_id=resolved_block_id,
                    ha_id=ha_id,
                    s3_path=s3_key,
                )
        except Exception as e:
            raw_llm = getattr(processor, "last_raw_response", None) if processor else None
            logger.exception("Processor failed for %s", filename)
            return JSONResponse(status_code=500, content=_make_serializable({
                "status": "failed",
                "document_type": document_type,
                "upload_id": upload_id,
                "filename": filename,
                "error": str(e),
                "raw_llm_response": raw_llm,
                "detection_warning": detection_warning,
            }))

        # Fetch the extracted risk data back from DB so the frontend can show
        # the correct RAG colour without a separate round-trip.
        extracted_feature: dict = {}
        feature_id = result.get("feature_id")
        fra_id = result.get("fra_id")
        fraew_id = result.get("fraew_id")
        db_lookup_id = fra_id if document_type == "fra" else fraew_id
        if db_lookup_id:
            try:
                if document_type == "fra":
                    _row = await conn.fetchrow(
                        "SELECT risk_rating, rag_status, assessor_company, assessor_name, "
                        "assessment_date, next_review_date, evacuation_strategy, "
                        "has_fire_doors, has_sprinkler_system, has_compartmentation, "
                        "has_fire_alarm_system, has_smoke_detection, "
                        "total_action_count, overdue_action_count, outstanding_action_count "
                        "FROM silver.fra_features WHERE fra_id = $1::uuid AND ha_id = $2",
                        db_lookup_id, ha_id,
                    )
                else:
                    _row = await conn.fetchrow(
                        "SELECT building_risk_rating, rag_status, assessor_company, "
                        "assessment_date, assessment_valid_until, is_in_date, "
                        "has_combustible_cladding, eps_insulation_present, wall_types, "
                        "cavity_barriers_present, pas_9980_compliant, pas_9980_version, "
                        "interim_measures_required, interim_measures_detail, has_remedial_actions, "
                        "evacuation_strategy, dry_riser_present, wet_riser_present, adb_compliant, "
                        "building_height_m, building_height_category, num_storeys, num_units "
                        "FROM silver.fraew_features WHERE fraew_id = $1::uuid AND ha_id = $2",
                        db_lookup_id, ha_id,
                    )
                if _row:
                    extracted_feature = dict(_row)
            except Exception:
                pass

    return JSONResponse(content=_make_serializable({
        "status": "success",
        "success": True,
        "document_type": document_type,
        "upload_id": upload_id,
        "feature_id": result.get("feature_id"),
        "portfolio_id": resolved_portfolio_id,
        "block_id": resolved_block_id,
        "block_reference": resolved_block_ref or block_reference,
        "block_auto_resolved": bool(resolved_block_ref and not (block_reference and block_reference.strip())),
        "filename": filename,
        "file_size": len(file_content),
        "s3_key": s3_key,
        "text_chars_extracted": len(text),
        "auto_detected": auto_detected.value,
        "user_selected": document_type,
        "detection_warning": detection_warning,
        "message": (
            f"{document_type.upper()} extracted and linked to block {resolved_block_ref}."
            if resolved_block_ref else
            f"{document_type.upper()} extracted but no matching block found — link it manually."
        ),
        "fire_risk_payload": {
            "document_type": document_type,
            "upload_id": str(upload_id),
            "feature_id": result.get("feature_id"),
            "block_id": resolved_block_id,
            "block_reference": resolved_block_ref or block_reference,
            document_type: extracted_feature,
        },
    }))
