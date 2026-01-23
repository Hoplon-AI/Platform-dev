"""
Unit tests for Silver layer processor.

Tests use mocked S3 and database connections.
"""
import pytest
import uuid
import json
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime, timezone

from backend.workers.silver_processor import (
    process_features_to_silver,
    _parse_s3_key_for_metadata,
    _normalize_date,
    _write_document_features,
    _write_fraew_features,
    _write_fra_features,
    _write_scr_features,
    _update_processing_audit,
)


class TestParseS3KeyForMetadata:
    """Tests for S3 key parsing."""

    def test_parses_valid_s3_key(self):
        """Test parsing a valid S3 key with all required fields."""
        key = "ha_id=test_ha/bronze/dataset=fraew_document/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/features.json"
        result = _parse_s3_key_for_metadata(key)
        
        assert result["ha_id"] == "test_ha"
        assert result["file_type"] == "fraew_document"
        assert result["submission_id"] == "123e4567-e89b-12d3-a456-426614174000"

    def test_raises_error_for_invalid_key(self):
        """Test that invalid S3 key raises ValueError."""
        key = "invalid/key/format"
        with pytest.raises(ValueError, match="Could not parse S3 key"):
            _parse_s3_key_for_metadata(key)

    def test_parses_key_with_special_characters(self):
        """Test parsing key with URL-encoded characters."""
        key = "ha_id=test-ha-123/bronze/dataset=fra_document/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/features.json"
        result = _parse_s3_key_for_metadata(key)
        
        assert result["ha_id"] == "test-ha-123"
        assert result["file_type"] == "fra_document"


class TestNormalizeDate:
    """Tests for date normalization."""

    def test_normalizes_iso_date(self):
        """Test normalizing ISO format date (YYYY-MM-DD)."""
        result = _normalize_date("2024-01-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_normalizes_iso_datetime_with_z(self):
        """Test normalizing ISO datetime with Z timezone."""
        result = _normalize_date("2024-01-15T10:30:00Z")
        assert result is not None
        assert result.year == 2024

    def test_normalizes_dd_mm_yyyy_format(self):
        """Test normalizing DD/MM/YYYY format."""
        result = _normalize_date("15/01/2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_normalizes_dd_mm_yyyy_with_dashes(self):
        """Test normalizing DD-MM-YYYY format."""
        result = _normalize_date("15-01-2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_returns_none_for_invalid_date(self):
        """Test that invalid date returns None."""
        assert _normalize_date("invalid") is None
        assert _normalize_date("") is None
        assert _normalize_date(None) is None


class TestWriteDocumentFeatures:
    """Tests for writing document features."""

    @pytest.mark.asyncio
    async def test_writes_common_fields(self):
        """Test writing common document features."""
        conn = AsyncMock()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        document_type = "fraew_document"
        
        features_json = {
            "features": {
                "uprns": ["123456789012"],
                "postcodes": ["SW1A 1AA"],
                "dates": ["2024-01-15"],
            },
            "extracted_at": "2024-01-15T10:00:00Z"
        }
        
        feature_id = await _write_document_features(
            conn,
            ha_id=ha_id,
            upload_id=upload_id,
            document_type=document_type,
            features_json=features_json,
        )
        
        assert isinstance(feature_id, uuid.UUID)
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        # First arg is SQL string, then feature_id, ha_id, upload_id, etc.
        assert call_args[0][2] == ha_id  # Third positional arg is ha_id
        assert call_args[0][3] == upload_id  # Fourth positional arg is upload_id

    @pytest.mark.asyncio
    async def test_writes_fraew_specific_fields(self):
        """Test writing FRAEW-specific fields."""
        conn = AsyncMock()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        document_type = "fraew_document"
        
        features_json = {
            "features": {
                "fraew_specific": {
                    "building_name": "Test Building",
                    "address": "123 Test Street",
                    "assessment_date": "2024-01-15",
                    "job_reference": "JOB-123",
                    "client_name": "Test Client",
                    "assessor_company": "Test Assessor",
                }
            }
        }
        
        feature_id = await _write_document_features(
            conn,
            ha_id=ha_id,
            upload_id=upload_id,
            document_type=document_type,
            features_json=features_json,
        )
        
        assert isinstance(feature_id, uuid.UUID)
        conn.execute.assert_called_once()


class TestWriteFRAEWFeatures:
    """Tests for writing FRAEW-specific features."""

    @pytest.mark.asyncio
    async def test_writes_fraew_features(self):
        """Test writing FRAEW features to fraew_features table."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "features": {
                "fraew_specific": {
                    "pas_9980_compliant": True,
                    "pas_9980_version": "2022",
                    "building_risk_rating": "HIGH",
                    "wall_types": [{"type": 1, "name": "Wall Type A"}],
                    "has_interim_measures": True,
                    "has_remedial_actions": False,
                }
            }
        }
        
        await _write_fraew_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert call_args[0][2] == feature_id  # feature_id is third positional arg
        assert call_args[0][3] == ha_id


class TestProcessFeaturesToSilver:
    """Tests for main processing function."""

    @pytest.mark.asyncio
    async def test_processes_fraew_document(self):
        """Test processing FRAEW document features."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=fraew_document/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/features.json",
            "execution_arn": "arn:aws:states:us-east-1:123456789012:execution:test"
        }
        
        features_json = {
            "features": {
                "fraew_specific": {
                    "pas_9980_compliant": True,
                    "pas_9980_version": "2022",
                    "building_risk_rating": "HIGH",
                }
            }
        }
        
        with patch("backend.workers.silver_processor.UploadService") as mock_upload_service:
            
            # Mock S3 service
            mock_service = MagicMock()
            mock_service.get_json.return_value = features_json
            mock_upload_service.return_value = mock_service
            
            # Mock database connection (dependency injection)
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            
            result = await process_features_to_silver(event, db_conn=mock_conn, upload_service=mock_service)
            
            assert result["status"] == "completed"
            assert result["document_type"] == "fraew_document"
            assert result["ha_id"] == "test_ha"
            assert "feature_id" in result

    @pytest.mark.asyncio
    async def test_ignores_non_features_json(self):
        """Test that non-features.json files are ignored."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=fraew_document/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/extraction.json",
        }
        
        result = await process_features_to_silver(event)
        
        assert result["status"] == "ignored"
        assert result["reason"] == "not_features_json"

    @pytest.mark.asyncio
    async def test_ignores_non_pdf_document_types(self):
        """Test that non-PDF document types are ignored."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=csv_file/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/features.json",
        }
        
        result = await process_features_to_silver(event)
        
        assert result["status"] == "ignored"
        assert result["reason"] == "not_pdf_document"

    @pytest.mark.asyncio
    async def test_handles_s3_read_error(self):
        """Test handling S3 read errors."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=fraew_document/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/features.json",
        }
        
        with patch("backend.workers.silver_processor.UploadService") as mock_upload_service:
            mock_service = MagicMock()
            mock_service.get_json.side_effect = Exception("S3 read error")
            mock_upload_service.return_value = mock_service
            
            result = await process_features_to_silver(event)
            
            assert result["status"] == "failed"
            assert result["reason"] == "failed_to_read_features"

    @pytest.mark.asyncio
    async def test_handles_database_error(self):
        """Test handling database errors."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=fraew_document/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/features.json",
        }
        
        features_json = {
            "features": {
                "fraew_specific": {}
            }
        }
        
        with patch("backend.workers.silver_processor.UploadService") as mock_upload_service:
            
            mock_service = MagicMock()
            mock_service.get_json.return_value = features_json
            mock_upload_service.return_value = mock_service
            
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(side_effect=Exception("Database error"))
            
            result = await process_features_to_silver(event, db_conn=mock_conn, upload_service=mock_service)
            
            assert result["status"] == "failed"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_processes_fra_document(self):
        """Test processing FRA document features."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=fra_document/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/features.json",
        }
        
        features_json = {
            "features": {}
        }
        
        with patch("backend.workers.silver_processor.UploadService") as mock_upload_service:
            
            mock_service = MagicMock()
            mock_service.get_json.return_value = features_json
            mock_upload_service.return_value = mock_service
            
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            
            result = await process_features_to_silver(event, db_conn=mock_conn, upload_service=mock_service)
            
            assert result["status"] == "completed"
            assert result["document_type"] == "fra_document"

    @pytest.mark.asyncio
    async def test_processes_scr_document(self):
        """Test processing SCR document features."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=scr_document/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/features.json",
        }
        
        features_json = {
            "features": {}
        }
        
        with patch("backend.workers.silver_processor.UploadService") as mock_upload_service:
            
            mock_service = MagicMock()
            mock_service.get_json.return_value = features_json
            mock_upload_service.return_value = mock_service
            
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            
            result = await process_features_to_silver(event, db_conn=mock_conn, upload_service=mock_service)
            
            assert result["status"] == "completed"
            assert result["document_type"] == "scr_document"

    @pytest.mark.asyncio
    async def test_processes_fra_document_with_features(self):
        """Test processing FRA document features."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=fra_document/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/features.json",
        }

        features_json = {
            "features": {}
        }

        with patch("backend.workers.silver_processor.UploadService") as mock_upload_service:

            mock_service = MagicMock()
            mock_service.get_json.return_value = features_json
            mock_upload_service.return_value = mock_service

            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            result = await process_features_to_silver(event, db_conn=mock_conn, upload_service=mock_service)

            assert result["status"] == "completed"
            assert result["document_type"] == "fra_document"
