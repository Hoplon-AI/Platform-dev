"""
FastAPI router for file uploads.
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Tuple
import os
import io
from datetime import datetime
from backend.core.database.db_pool import DatabasePool
from backend.workers.sov_processor import process_sov_to_silver
import json

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


@router.post("/property-schedule", response_model=UploadResponse)
async def upload_property_schedule(
    file: UploadFile = File(...),
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Upload property schedule (CSV/Excel).
    
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
        file_type='property_schedule',
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


@router.post("/fra-document", response_model=UploadResponse)
async def upload_fra_document(
    file: UploadFile = File(...),
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Upload FRA document (PDF - Fire Risk Assessment).
    
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
        file_type='fra_document',
    )


@router.post("/fraew-document", response_model=UploadResponse)
async def upload_fraew_document(
    file: UploadFile = File(...),
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Upload FRAEW document (PDF - PAS 9980 Fire Risk Appraisal of External Walls).
    
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
        file_type='fraew_document',
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
