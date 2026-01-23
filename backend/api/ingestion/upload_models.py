"""
Pydantic models for upload requests/responses.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    """Upload request model."""
    file_type: str = Field(..., description="Type of file: property_schedule, epc_data, fra_document, fraew_document, scr_document")
    ha_id: Optional[str] = Field(None, description="Housing Association ID (extracted from token if not provided)")


class UploadResponse(BaseModel):
    """Upload response model."""
    success: bool
    upload_id: str
    ha_id: str
    filename: str
    file_type: str
    s3_key: str
    manifest_s3_key: Optional[str] = None
    metadata_s3_key: Optional[str] = None
    extraction_s3_key: Optional[str] = None
    features_s3_key: Optional[str] = None
    interpretation_s3_key: Optional[str] = None
    checksum: str
    file_size: int
    uploaded_at: datetime
    status: str
    message: str


class UploadStatusResponse(BaseModel):
    """Upload status response model."""
    upload_id: str
    ha_id: str
    filename: str
    file_type: str
    status: str
    uploaded_at: datetime
    file_size: int
    checksum: str
    metadata: Optional[Dict[str, Any]] = None


class UploadListResponse(BaseModel):
    """List of uploads/submissions for an HA."""
    items: list[UploadStatusResponse]


class BatchUploadResponse(BaseModel):
    """Response model for batch file uploads."""
    total_files: int
    successful: int
    failed: int
    results: list[UploadResponse]
    errors: list[Dict[str, Any]]  # List of {filename, error} dicts
