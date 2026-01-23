"""
Tests for Bronze layer (upload and audit).
"""
import pytest
from infrastructure.storage.upload_service import UploadService
from backend.core.audit.audit_logger import AuditLogger


def test_upload_service_checksum():
    """Test checksum calculation."""
    service = UploadService()
    test_content = b"test file content"
    checksum = service.calculate_checksum(test_content)
    
    assert checksum is not None
    assert len(checksum) == 64  # SHA-256 hex digest length


def test_audit_logger_initialization():
    """Test audit logger initialization."""
    logger = AuditLogger()
    assert logger is not None
