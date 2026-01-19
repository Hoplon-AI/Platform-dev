"""
Pydantic models for upload requests/responses.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    """Upload request model."""
    file_type: str = Field(..., description="Type of file: property_schedule, epc_data, or frsa_document")
    ha_id: Optional[str] = Field(None, description="Housing Association ID (extracted from token if not provided)")


class UploadResponse(BaseModel):
    """Upload response model."""
    success: bool
    upload_id: str
    ha_id: str
    filename: str
    file_type: str
    s3_key: str
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


class BatchUploadResponse(BaseModel):
    """Response model for batch file uploads."""
    total_files: int
    successful: int
    failed: int
    results: list[UploadResponse]
    errors: list[Dict[str, Any]]  # List of {filename, error} dicts
