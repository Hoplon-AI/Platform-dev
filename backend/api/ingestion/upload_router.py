"""
FastAPI router for file uploads.
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Tuple
import os
import io
from datetime import datetime

from backend.api.ingestion.upload_models import (
    UploadRequest, UploadResponse, UploadStatusResponse, BatchUploadResponse
)
from backend.api.ingestion.upload_validator import UploadValidator
from backend.api.ingestion.file_type_detector import FileTypeDetector, FileType
from infrastructure.storage.upload_service import get_upload_service
from backend.core.audit.audit_logger import get_audit_logger
from backend.core.tenancy.tenant_middleware import TenantMiddleware

router = APIRouter(prefix="/api/v1/upload", tags=["upload"])
security = HTTPBearer(auto_error=False)  # Don't auto-raise on missing token
validator = UploadValidator()
detector = FileTypeDetector()
middleware = TenantMiddleware()


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
    
    if dev_mode:
        # Development mode: return default values if no token provided
        if not credentials:
            return ("default_ha", "default_user")
        # If token is provided, still validate it
        try:
            return middleware.extract_tenant_from_token(credentials.credentials)
        except HTTPException:
            # If token is invalid in dev mode, fall back to defaults
            return ("default_ha", "default_user")
    
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
    
    # Log upload in audit
    audit_logger = get_audit_logger()
    await audit_logger.log_upload(
        upload_id=upload_id,
        ha_id=ha_id,
        file_type=file_type,
        filename=file.filename or f"{file_type}.csv",
        s3_key=s3_key,
        checksum=checksum,
        file_size=len(file_content),
        user_id=user_id,
    )
    
    return UploadResponse(
        success=True,
        upload_id=upload_id,
        ha_id=ha_id,
        filename=file.filename or f"{file_type}.csv",
        file_type=file_type,
        s3_key=s3_key,
        checksum=checksum,
        file_size=len(file_content),
        uploaded_at=datetime.utcnow(),
        status='pending',
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
            
            # Log upload in audit
            audit_logger = get_audit_logger()
            await audit_logger.log_upload(
                upload_id=upload_id,
                ha_id=ha_id,
                file_type=file_type_str,
                filename=file.filename or f"{file_type_str}.csv",
                s3_key=s3_key,
                checksum=checksum,
                file_size=len(file_content),
                user_id=user_id,
            )
            
            results.append(UploadResponse(
                success=True,
                upload_id=upload_id,
                ha_id=ha_id,
                filename=file.filename or f"{file_type_str}.csv",
                file_type=file_type_str,
                s3_key=s3_key,
                checksum=checksum,
                file_size=len(file_content),
                uploaded_at=datetime.utcnow(),
                status='pending',
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


@router.post("/frsa-document", response_model=UploadResponse)
async def upload_frsa_document(
    file: UploadFile = File(...),
    tenant: Tuple[str, str] = Depends(get_tenant_info),
):
    """
    Upload FRSA document (PDF - Fire Risk Safety Assessment).
    
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
        file_type='frsa_document',
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

# TODO: Query upload_audit table
# This is a placeholder
@router.get("/{upload_id}/status", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: str,
    ha_id: Optional[str] = None,
):
    """
    Get upload status and metadata.
    
    Args:
        upload_id: Upload UUID
        ha_id: Housing Association ID
        
    Returns:
        UploadStatusResponse with upload details
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Upload status endpoint not yet implemented"
    )
