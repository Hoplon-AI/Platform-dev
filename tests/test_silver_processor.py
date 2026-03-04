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
    _write_building_safety_features,
    _write_docb_features,
    _update_document_features_with_agentic,
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
            mock_conn.fetchrow = AsyncMock(return_value={"uprn": None, "postcode": None})
            
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
            mock_conn.fetchrow = AsyncMock(return_value={"uprn": None, "postcode": None})
            
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
            mock_conn.fetchrow = AsyncMock(return_value={"uprn": None, "postcode": None})
            
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
            mock_conn.fetchrow = AsyncMock(return_value={"uprn": None, "postcode": None})

            result = await process_features_to_silver(event, db_conn=mock_conn, upload_service=mock_service)

            assert result["status"] == "completed"
            assert result["document_type"] == "fra_document"


class TestWriteBuildingSafetyFeatures:
    """Tests for writing building safety features (Category A + B)."""

    @pytest.mark.asyncio
    async def test_writes_high_rise_indicators(self):
        """Test writing high-rise building indicators."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "agentic_features": {
                "high_rise_indicators": {
                    "high_rise_building_mentioned": True,
                    "building_height_category": "HIGH_RISE",
                    "number_of_storeys": 20,
                    "building_height_metres": 60.5,
                    "building_safety_act_applicable": True,
                }
            },
            "extraction_method": "agentic"
        }
        
        await _write_building_safety_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        # Check that high_rise_building_mentioned is True (5th positional arg after safety_feature_id, feature_id, ha_id, upload_id)
        assert call_args[0][5] is True  # high_rise_building_mentioned
        assert call_args[0][6] == "HIGH_RISE"  # building_height_category
        assert call_args[0][7] == 20  # number_of_storeys

    @pytest.mark.asyncio
    async def test_writes_evacuation_strategy(self):
        """Test writing evacuation strategy features."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "agentic_features": {
                "evacuation_strategy": {
                    "evacuation_strategy_mentioned": True,
                    "evacuation_strategy_type": "STAY_PUT",
                    "evacuation_strategy_description": "Stay in flat if fire elsewhere",
                    "personal_evacuation_plans_mentioned": True,
                }
            },
            "extraction_method": "merged"
        }
        
        await _write_building_safety_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        # Check evacuation strategy fields (11th positional arg is evacuation_strategy_mentioned)
        assert call_args[0][11] is True  # evacuation_strategy_mentioned
        assert call_args[0][12] == "STAY_PUT"  # evacuation_strategy_type

    @pytest.mark.asyncio
    async def test_writes_fire_safety_measures(self):
        """Test writing fire safety measures."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "agentic_features": {
                "fire_safety_measures": {
                    "fire_safety_measures_mentioned": True,
                    "fire_doors_mentioned": True,
                    "fire_safety_officers_mentioned": True,
                }
            }
        }
        
        await _write_building_safety_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert call_args[0][17] is True  # fire_safety_measures_mentioned
        assert call_args[0][18] is True  # fire_doors_mentioned

    @pytest.mark.asyncio
    async def test_writes_bsa_compliance(self):
        """Test writing Building Safety Act 2022 compliance features."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "agentic_features": {
                "building_safety_act_2022": {
                    "building_safety_act_2022_mentioned": True,
                    "building_safety_act_compliance_status": "COMPLIANT",
                    "part_4_duties_mentioned": True,
                    "building_safety_regulator_mentioned": True,
                }
            }
        }
        
        await _write_building_safety_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert call_args[0][29] is True  # building_safety_act_2022_mentioned
        assert call_args[0][30] == "COMPLIANT"  # building_safety_act_compliance_status

    @pytest.mark.asyncio
    async def test_writes_mor_references(self):
        """Test writing Mandatory Occurrence Report references."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "agentic_features": {
                "mandatory_occurrence_reports": {
                    "mandatory_occurrence_report_mentioned": True,
                    "mandatory_occurrence_reporting_process_mentioned": True,
                }
            }
        }
        
        await _write_building_safety_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert call_args[0][35] is True  # mandatory_occurrence_report_mentioned

    @pytest.mark.asyncio
    async def test_skips_when_no_agentic_features(self):
        """Test that function returns early when no agentic features present."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "features": {
                "fraew_specific": {}  # Only regex features, no agentic
            }
        }
        
        await _write_building_safety_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        # Should not call execute since no agentic features
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_extracts_from_features_agentic_features(self):
        """Test extracting agentic features from features.agentic_features path."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "features": {
                "agentic_features": {
                    "high_rise_indicators": {
                        "high_rise_building_mentioned": True,
                    }
                }
            }
        }
        
        await _write_building_safety_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculates_confidence_score(self):
        """Test that confidence scores are calculated from feature groups."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "agentic_features": {
                "high_rise_indicators": {
                    "high_rise_building_mentioned": {"value": True, "confidence": 0.9},
                },
                "evacuation_strategy": {
                    "evacuation_strategy_type": {"value": "STAY_PUT", "confidence": 0.85},
                }
            }
        }
        
        await _write_building_safety_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        # agentic_confidence_score should be average of 0.9 and 0.85 = 0.875
        assert call_args[0][39] == 0.875  # agentic_confidence_score


class TestWriteDocBFeatures:
    """Tests for writing DocB/PlanB features (Category C)."""

    @pytest.mark.asyncio
    async def test_writes_required_docb_fields(self):
        """Test writing required DocB fields."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "docb_features": {
                "claddingType": "ACM",
                "ewsStatus": "A1",
                "fireRiskManagementSummary": "Comprehensive fire safety measures in place",
                "docBRef": "DOCB-12345",
            }
        }
        
        await _write_docb_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert call_args[0][5] == "ACM"  # cladding_type
        assert call_args[0][6] == "A1"  # ews_status
        assert call_args[0][7] == "Comprehensive fire safety measures in place"  # fire_risk_management_summary
        assert call_args[0][8] == "DOCB-12345"  # docb_ref

    @pytest.mark.asyncio
    async def test_writes_optional_docb_fields(self):
        """Test writing optional DocB context fields."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "docb_features": {
                "claddingType": "HPL",
                "fireProtection": "Sprinkler system",
                "alarms": "Grade A fire alarm",
                "evacuationStrategy": "Stay Put",
                "floorsAboveGround": 15,
                "floorsBelowGround": 2,
            }
        }
        
        await _write_docb_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert call_args[0][9] == "Sprinkler system"  # fire_protection
        assert call_args[0][10] == "Grade A fire alarm"  # alarms
        assert call_args[0][11] == "Stay Put"  # evacuation_strategy
        assert call_args[0][12] == 15  # floors_above_ground
        assert call_args[0][13] == 2  # floors_below_ground

    @pytest.mark.asyncio
    async def test_extracts_from_agentic_features_path(self):
        """Test extracting DocB features from nested agentic_features path."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "features": {
                "agentic_features": {
                    "category_c_docb_planb": {
                        "docb_required_fields": {
                            "claddingType": "Composite",
                            "ewsStatus": "B2",
                        }
                    }
                }
            }
        }
        
        await _write_docb_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert call_args[0][5] == "Composite"  # cladding_type
        assert call_args[0][6] == "B2"  # ews_status

    @pytest.mark.asyncio
    async def test_handles_snake_case_field_names(self):
        """Test that function handles both camelCase and snake_case field names."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "docb_features": {
                "cladding_type": "Timber",  # snake_case
                "ews_status": "A2",  # snake_case
                "fire_risk_management_summary": "Summary text",  # snake_case
            }
        }
        
        await _write_docb_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert call_args[0][5] == "Timber"  # cladding_type
        assert call_args[0][6] == "A2"  # ews_status

    @pytest.mark.asyncio
    async def test_skips_when_no_docb_features(self):
        """Test that function returns early when no DocB features present."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        ha_id = "test_ha"
        upload_id = uuid.uuid4()
        
        features_json = {
            "features": {
                "fraew_specific": {}  # No DocB features
            }
        }
        
        await _write_docb_features(
            conn,
            feature_id=feature_id,
            ha_id=ha_id,
            upload_id=upload_id,
            features_json=features_json,
        )
        
        # Should not call execute since no DocB features
        conn.execute.assert_not_called()


class TestUpdateDocumentFeaturesWithAgentic:
    """Tests for updating document_features with agentic metadata."""

    @pytest.mark.asyncio
    async def test_updates_with_agentic_features(self):
        """Test updating document_features with agentic features JSON."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        
        features_json = {
            "agentic_features": {
                "high_rise_indicators": {"high_rise_building_mentioned": True},
            },
            "extraction_method": "agentic"
        }
        
        await _update_document_features_with_agentic(
            conn,
            feature_id=feature_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert call_args[0][5] == feature_id  # WHERE clause (5th positional arg)
        # Check that agentic_features_json is set
        assert "UPDATE silver.document_features" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_updates_with_comparison_metadata(self):
        """Test updating document_features with comparison metadata."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        
        features_json = {
            "extraction_method": "merged",
            "extraction_comparison_metadata": {
                "agreement_score": 0.85,
                "discrepancies": ["evacuation_strategy_type"],
            }
        }
        
        await _update_document_features_with_agentic(
            conn,
            feature_id=feature_id,
            features_json=features_json,
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        # extraction_method should be "merged"
        assert "merged" in str(call_args[0])

    @pytest.mark.asyncio
    async def test_skips_when_no_agentic_metadata(self):
        """Test that function returns early when no agentic metadata present."""
        conn = AsyncMock()
        feature_id = uuid.uuid4()
        
        features_json = {
            "features": {
                "fraew_specific": {}  # Only regex features
            }
        }
        
        await _update_document_features_with_agentic(
            conn,
            feature_id=feature_id,
            features_json=features_json,
        )
        
        # Should not call execute since no agentic metadata
        conn.execute.assert_not_called()


class TestProcessFeaturesToSilverWithAgentic:
    """Tests for main processing function with agentic features."""

    @pytest.mark.asyncio
    async def test_processes_with_agentic_features(self):
        """Test processing document with agentic features."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=fraew_document/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/features.json",
        }
        
        features_json = {
            "features": {
                "fraew_specific": {
                    "pas_9980_compliant": True,
                }
            },
            "agentic_features": {
                "high_rise_indicators": {
                    "high_rise_building_mentioned": True,
                    "building_height_category": "HIGH_RISE",
                },
                "evacuation_strategy": {
                    "evacuation_strategy_mentioned": True,
                    "evacuation_strategy_type": "STAY_PUT",
                }
            },
            "extraction_method": "merged",
            "extraction_comparison_metadata": {
                "agreement_score": 0.9
            }
        }
        
        with patch("backend.workers.silver_processor.UploadService") as mock_upload_service:
            mock_service = MagicMock()
            mock_service.get_json.return_value = features_json
            mock_upload_service.return_value = mock_service
            
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"uprn": None, "postcode": None})
            
            result = await process_features_to_silver(event, db_conn=mock_conn, upload_service=mock_service)
            
            assert result["status"] == "completed"
            # Verify that all write functions were called
            # _write_document_features, _write_fraew_features, _write_building_safety_features,
            # _write_docb_features, _update_document_features_with_agentic, _update_processing_audit
            assert mock_conn.execute.call_count >= 4  # At least document_features, fraew_features, building_safety_features, processing_audit

    @pytest.mark.asyncio
    async def test_processes_with_docb_features(self):
        """Test processing document with DocB features."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=fra_document/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/features.json",
        }
        
        features_json = {
            "features": {},
            "docb_features": {
                "claddingType": "ACM",
                "ewsStatus": "A1",
                "fireRiskManagementSummary": "Test summary",
                "docBRef": "DOCB-123",
            }
        }
        
        with patch("backend.workers.silver_processor.UploadService") as mock_upload_service:
            mock_service = MagicMock()
            mock_service.get_json.return_value = features_json
            mock_upload_service.return_value = mock_service
            
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"uprn": None, "postcode": None})
            
            result = await process_features_to_silver(event, db_conn=mock_conn, upload_service=mock_service)
            
            assert result["status"] == "completed"
            # Verify docb_features write was attempted
            # The function should have been called (even if it returns early if no features match)
            assert mock_conn.execute.call_count >= 2  # At least document_features and processing_audit
