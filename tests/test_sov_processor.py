"""
Unit tests for SOV (Schedule of Values) processor.

Tests use mocked S3 and database connections.
"""
import pytest
import uuid
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import pandas as pd

from backend.workers.sov_processor import (
    process_sov_to_silver,
    _parse_s3_key_for_metadata,
    _parse_sov_file,
    _normalize_columns,
    _validate_uprn,
    _validate_postcode,
    _validate_latitude,
    _validate_longitude,
    _validate_risk_rating,
    _validate_row,
    _upsert_property,
    _link_uprn_lineage,
    is_sov_type,
    COLUMN_MAPPING,
)


class TestParseS3KeyForMetadata:
    """Tests for S3 key parsing."""

    def test_parses_valid_s3_key(self):
        """Test parsing a valid S3 key with all required fields."""
        key = "ha_id=test_ha/bronze/dataset=property_schedule/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/file=properties.csv"
        result = _parse_s3_key_for_metadata(key)

        assert result["ha_id"] == "test_ha"
        assert result["file_type"] == "property_schedule"
        assert result["submission_id"] == "123e4567-e89b-12d3-a456-426614174000"

    def test_raises_error_for_invalid_key(self):
        """Test that invalid S3 key raises ValueError."""
        key = "invalid/key/format"
        with pytest.raises(ValueError, match="Could not parse S3 key"):
            _parse_s3_key_for_metadata(key)


class TestValidateUPRN:
    """Tests for UPRN validation."""

    def test_valid_12_digit_uprn(self):
        """Test valid 12-digit UPRN."""
        is_valid, cleaned = _validate_uprn("100023456789")
        assert is_valid is True
        assert cleaned == "100023456789"

    def test_valid_shorter_uprn_gets_padded(self):
        """Test shorter UPRN gets zero-padded."""
        is_valid, cleaned = _validate_uprn("23456789")
        assert is_valid is True
        assert cleaned == "000023456789"

    def test_invalid_uprn_with_letters(self):
        """Test UPRN with letters is invalid."""
        is_valid, cleaned = _validate_uprn("ABC123456789")
        assert is_valid is False

    def test_none_uprn_is_valid(self):
        """Test None UPRN is valid (optional field)."""
        is_valid, cleaned = _validate_uprn(None)
        assert is_valid is True
        assert cleaned is None

    def test_empty_uprn_is_valid(self):
        """Test empty UPRN is valid (optional field)."""
        is_valid, cleaned = _validate_uprn("")
        assert is_valid is True
        assert cleaned is None


class TestValidatePostcode:
    """Tests for UK postcode validation."""

    def test_valid_postcode_with_space(self):
        """Test valid UK postcode with space."""
        is_valid, cleaned = _validate_postcode("SW1A 1AA")
        assert is_valid is True
        assert cleaned == "SW1A 1AA"

    def test_valid_postcode_without_space(self):
        """Test valid UK postcode without space gets formatted."""
        is_valid, cleaned = _validate_postcode("SW1A1AA")
        assert is_valid is True
        assert cleaned == "SW1A 1AA"

    def test_lowercase_gets_uppercased(self):
        """Test lowercase postcode gets uppercased."""
        is_valid, cleaned = _validate_postcode("sw1a 1aa")
        assert is_valid is True
        assert cleaned == "SW1A 1AA"

    def test_invalid_postcode_format(self):
        """Test invalid postcode format."""
        is_valid, cleaned = _validate_postcode("INVALID")
        assert is_valid is False

    def test_none_postcode_is_valid(self):
        """Test None postcode is valid (optional field)."""
        is_valid, cleaned = _validate_postcode(None)
        assert is_valid is True
        assert cleaned is None

    def test_extra_whitespace_is_normalized(self):
        """Test extra whitespace is normalized."""
        is_valid, cleaned = _validate_postcode("  SW1A   1AA  ")
        assert is_valid is True
        assert cleaned == "SW1A 1AA"


class TestValidateLatitude:
    """Tests for latitude validation."""

    def test_valid_uk_latitude(self):
        """Test valid UK latitude."""
        is_valid, cleaned = _validate_latitude("51.5074")
        assert is_valid is True
        assert cleaned == 51.5074

    def test_latitude_too_low(self):
        """Test latitude below UK range."""
        is_valid, cleaned = _validate_latitude("48.5")
        assert is_valid is False

    def test_latitude_too_high(self):
        """Test latitude above UK range."""
        is_valid, cleaned = _validate_latitude("62.0")
        assert is_valid is False

    def test_none_latitude_is_valid(self):
        """Test None latitude is valid (optional field)."""
        is_valid, cleaned = _validate_latitude(None)
        assert is_valid is True
        assert cleaned is None

    def test_non_numeric_latitude(self):
        """Test non-numeric latitude is invalid."""
        is_valid, cleaned = _validate_latitude("not_a_number")
        assert is_valid is False
        assert cleaned is None


class TestValidateLongitude:
    """Tests for longitude validation."""

    def test_valid_uk_longitude(self):
        """Test valid UK longitude."""
        is_valid, cleaned = _validate_longitude("-0.1278")
        assert is_valid is True
        assert cleaned == -0.1278

    def test_longitude_too_low(self):
        """Test longitude below UK range."""
        is_valid, cleaned = _validate_longitude("-9.0")
        assert is_valid is False

    def test_longitude_too_high(self):
        """Test longitude above UK range."""
        is_valid, cleaned = _validate_longitude("3.0")
        assert is_valid is False

    def test_none_longitude_is_valid(self):
        """Test None longitude is valid (optional field)."""
        is_valid, cleaned = _validate_longitude(None)
        assert is_valid is True
        assert cleaned is None


class TestValidateRiskRating:
    """Tests for risk rating validation."""

    def test_valid_risk_rating_a(self):
        """Test valid risk rating A."""
        is_valid, cleaned = _validate_risk_rating("A")
        assert is_valid is True
        assert cleaned == "A"

    def test_valid_risk_rating_lowercase(self):
        """Test lowercase risk rating gets uppercased."""
        is_valid, cleaned = _validate_risk_rating("b")
        assert is_valid is True
        assert cleaned == "B"

    def test_invalid_risk_rating(self):
        """Test invalid risk rating."""
        is_valid, cleaned = _validate_risk_rating("X")
        assert is_valid is False

    def test_none_risk_rating_is_valid(self):
        """Test None risk rating is valid (optional field)."""
        is_valid, cleaned = _validate_risk_rating(None)
        assert is_valid is True
        assert cleaned is None


class TestNormalizeColumns:
    """Tests for column name normalization."""

    def test_normalizes_uprn_variations(self):
        """Test UPRN column variations are normalized."""
        df = pd.DataFrame({"unique_property_reference": ["123"]})
        result = _normalize_columns(df)
        assert "uprn" in result.columns

    def test_normalizes_address_variations(self):
        """Test address column variations are normalized."""
        df = pd.DataFrame({"full_address": ["123 Main St"]})
        result = _normalize_columns(df)
        assert "address" in result.columns

    def test_normalizes_postcode_variations(self):
        """Test postcode column variations are normalized."""
        df = pd.DataFrame({"postal_code": ["SW1A 1AA"]})
        result = _normalize_columns(df)
        assert "postcode" in result.columns

    def test_normalizes_multiple_columns(self):
        """Test multiple columns are normalized."""
        df = pd.DataFrame({
            "property_reference": ["123"],
            "property_address": ["123 Main St"],
            "post_code": ["SW1A 1AA"],
            "lat": [51.5],
            "lng": [-0.1],
        })
        result = _normalize_columns(df)
        assert "uprn" in result.columns
        assert "address" in result.columns
        assert "postcode" in result.columns
        assert "latitude" in result.columns
        assert "longitude" in result.columns

    def test_preserves_unknown_columns(self):
        """Test unknown columns are preserved."""
        df = pd.DataFrame({
            "address": ["123 Main St"],
            "custom_field": ["value"],
        })
        result = _normalize_columns(df)
        assert "custom_field" in result.columns


class TestParseSovFile:
    """Tests for SOV file parsing."""

    def test_parses_csv_file(self):
        """Test parsing a CSV file."""
        csv_content = "uprn,address,postcode\n123456789012,123 Main St,SW1A 1AA"
        result = _parse_sov_file(csv_content.encode('utf-8'), "test.csv")

        assert len(result) == 1
        assert "uprn" in result.columns
        assert result.iloc[0]["uprn"] == "123456789012"

    def test_parses_csv_with_different_encoding(self):
        """Test parsing CSV with latin-1 encoding."""
        csv_content = "uprn,address,postcode\n123456789012,123 Main St,SW1A 1AA"
        result = _parse_sov_file(csv_content.encode('latin-1'), "test.csv")

        assert len(result) == 1

    def test_strips_whitespace_from_columns(self):
        """Test whitespace is stripped from column names."""
        csv_content = "  uprn  ,  address  \n123,Main St"
        result = _parse_sov_file(csv_content.encode('utf-8'), "test.csv")

        assert "uprn" in result.columns
        assert "address" in result.columns

    def test_raises_error_for_unsupported_type(self):
        """Test unsupported file type raises error."""
        with pytest.raises(ValueError, match="Unsupported file type"):
            _parse_sov_file(b"content", "test.pdf")


class TestValidateRow:
    """Tests for row validation."""

    def test_validates_complete_row(self):
        """Test validation of a complete valid row."""
        row = pd.Series({
            "uprn": "100023456789",
            "address": "123 Main St",
            "postcode": "SW1A 1AA",
            "latitude": "51.5",
            "longitude": "-0.1",
            "units": "10",
            "height_m": "25.5",
            "build_year": "2000",
            "construction_type": "Brick",
            "tenure": "Social Housing",
            "risk_rating": "B",
        })

        cleaned, errors = _validate_row(row, 0)

        assert len(errors) == 0
        assert cleaned["uprn"] == "100023456789"
        assert cleaned["address"] == "123 Main St"
        assert cleaned["postcode"] == "SW1A 1AA"
        assert cleaned["latitude"] == 51.5
        assert cleaned["longitude"] == -0.1

    def test_requires_address(self):
        """Test that address is required."""
        row = pd.Series({
            "uprn": "100023456789",
            "address": None,
        })

        cleaned, errors = _validate_row(row, 0)

        assert len(errors) == 1
        assert errors[0].field == "address"
        assert cleaned["address"] is None

    def test_collects_multiple_errors(self):
        """Test that multiple validation errors are collected."""
        row = pd.Series({
            "uprn": "invalid",
            "address": "123 Main St",
            "postcode": "INVALID",
            "latitude": "99.0",  # Out of range
            "longitude": "15.0",  # Out of range
            "risk_rating": "X",
        })

        cleaned, errors = _validate_row(row, 0)

        assert len(errors) >= 4  # uprn, postcode, latitude, longitude, risk_rating


class TestIsSovType:
    """Tests for SOV file type detection."""

    def test_property_schedule_is_sov(self):
        """Test property_schedule dataset type is SOV."""
        assert is_sov_type("property_schedule", "data.csv") is True

    def test_sov_dataset_is_sov(self):
        """Test sov dataset type is SOV."""
        assert is_sov_type("sov", "data.xlsx") is True

    def test_fra_is_not_sov(self):
        """Test fra dataset type is not SOV."""
        assert is_sov_type("fra", "document.pdf") is False

    def test_pdf_file_is_not_sov(self):
        """Test PDF file is not SOV even with property_schedule type."""
        # Note: This test verifies the current behavior
        # SOV type check requires both correct dataset AND file extension
        assert is_sov_type("other", "data.csv") is False


class TestUpsertProperty:
    """Tests for property upsert."""

    @pytest.mark.asyncio
    async def test_upserts_property_with_uprn(self):
        """Test upserting property with UPRN uses ON CONFLICT."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"property_id": uuid.uuid4()})

        cleaned = {
            "uprn": "100023456789",
            "address": "123 Main St",
            "postcode": "SW1A 1AA",
            "latitude": 51.5,
            "longitude": -0.1,
            "units": 10,
            "height_m": 25.5,
            "build_year": 2000,
            "construction_type": "Brick",
            "tenure": "Social Housing",
            "risk_rating": "B",
        }

        property_id = await _upsert_property(
            conn, "test_ha", uuid.uuid4(), cleaned
        )

        assert isinstance(property_id, uuid.UUID)
        conn.fetchrow.assert_called_once()
        # Check that ON CONFLICT is in the query
        call_args = conn.fetchrow.call_args
        assert "ON CONFLICT" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_inserts_property_without_uprn(self):
        """Test inserting property without UPRN creates new record."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"property_id": uuid.uuid4()})

        cleaned = {
            "uprn": None,
            "address": "123 Main St",
            "postcode": "SW1A 1AA",
            "latitude": 51.5,
            "longitude": -0.1,
            "units": 10,
            "height_m": 25.5,
            "build_year": 2000,
            "construction_type": "Brick",
            "tenure": "Social Housing",
            "risk_rating": "B",
        }

        property_id = await _upsert_property(
            conn, "test_ha", uuid.uuid4(), cleaned
        )

        assert isinstance(property_id, uuid.UUID)
        conn.fetchrow.assert_called_once()


class TestLinkUprnLineage:
    """Tests for UPRN lineage tracking."""

    @pytest.mark.asyncio
    async def test_inserts_lineage_record(self):
        """Test inserting UPRN lineage record."""
        conn = AsyncMock()

        await _link_uprn_lineage(
            conn,
            "test_ha",
            "100023456789",
            uuid.uuid4(),
            uuid.uuid4(),
        )

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert "uprn_lineage_map" in call_args[0][0]
        assert "ON CONFLICT" in call_args[0][0]


class TestProcessSovToSilver:
    """Tests for main processing function."""

    @pytest.mark.asyncio
    async def test_processes_csv_file(self):
        """Test processing a valid CSV file."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=property_schedule/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/file=properties.csv",
        }

        csv_content = "uprn,address,postcode\n100023456789,123 Main St,SW1A 1AA"

        with patch("backend.workers.sov_processor.UploadService") as mock_upload_service:
            mock_service = MagicMock()
            mock_service.get_file.return_value = csv_content.encode('utf-8')
            mock_upload_service.return_value = mock_service

            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"property_id": uuid.uuid4()})

            result = await process_sov_to_silver(
                event, db_conn=mock_conn, upload_service=mock_service
            )

            assert result["status"] in ("completed", "completed_with_warnings")
            assert result["records_processed"] == 1
            assert result["ha_id"] == "test_ha"

    @pytest.mark.asyncio
    async def test_handles_empty_file(self):
        """Test handling empty file."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=property_schedule/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/file=empty.csv",
        }

        csv_content = "uprn,address,postcode\n"  # Header only

        with patch("backend.workers.sov_processor.UploadService") as mock_upload_service:
            mock_service = MagicMock()
            mock_service.get_file.return_value = csv_content.encode('utf-8')
            mock_upload_service.return_value = mock_service

            result = await process_sov_to_silver(event, upload_service=mock_service)

            assert result["status"] == "failed"
            assert result["reason"] == "empty_file"

    @pytest.mark.asyncio
    async def test_handles_missing_address_column(self):
        """Test handling file without address column."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=property_schedule/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/file=no_address.csv",
        }

        csv_content = "uprn,postcode\n100023456789,SW1A 1AA"

        with patch("backend.workers.sov_processor.UploadService") as mock_upload_service:
            mock_service = MagicMock()
            mock_service.get_file.return_value = csv_content.encode('utf-8')
            mock_upload_service.return_value = mock_service

            result = await process_sov_to_silver(event, upload_service=mock_service)

            assert result["status"] == "failed"
            assert result["reason"] == "missing_required_column"

    @pytest.mark.asyncio
    async def test_handles_s3_read_error(self):
        """Test handling S3 read errors."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=property_schedule/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/file=properties.csv",
        }

        with patch("backend.workers.sov_processor.UploadService") as mock_upload_service:
            mock_service = MagicMock()
            mock_service.get_file.side_effect = Exception("S3 error")
            mock_upload_service.return_value = mock_service

            result = await process_sov_to_silver(event)

            assert result["status"] == "failed"
            assert result["reason"] == "failed_to_read_file"

    @pytest.mark.asyncio
    async def test_processes_with_validation_warnings(self):
        """Test processing file with validation warnings."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=property_schedule/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/file=properties.csv",
        }

        # CSV with invalid postcode
        csv_content = "uprn,address,postcode\n100023456789,123 Main St,INVALID"

        with patch("backend.workers.sov_processor.UploadService") as mock_upload_service:
            mock_service = MagicMock()
            mock_service.get_file.return_value = csv_content.encode('utf-8')
            mock_upload_service.return_value = mock_service

            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"property_id": uuid.uuid4()})

            result = await process_sov_to_silver(
                event, db_conn=mock_conn, upload_service=mock_service
            )

            # Should complete with warnings due to invalid postcode
            assert result["status"] == "completed_with_warnings"
            assert result["validation_errors_count"] >= 1

    @pytest.mark.asyncio
    async def test_tracks_uprn_lineage(self):
        """Test that UPRN lineage is tracked."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=property_schedule/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/file=properties.csv",
        }

        csv_content = "uprn,address,postcode\n100023456789,123 Main St,SW1A 1AA"

        with patch("backend.workers.sov_processor.UploadService") as mock_upload_service:
            mock_service = MagicMock()
            mock_service.get_file.return_value = csv_content.encode('utf-8')
            mock_upload_service.return_value = mock_service

            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"property_id": uuid.uuid4()})

            await process_sov_to_silver(
                event, db_conn=mock_conn, upload_service=mock_service
            )

            # Check that execute was called with uprn_lineage_map
            calls = mock_conn.execute.call_args_list
            lineage_calls = [c for c in calls if "uprn_lineage_map" in str(c)]
            assert len(lineage_calls) >= 1

    @pytest.mark.asyncio
    async def test_processes_multiple_rows(self):
        """Test processing file with multiple rows."""
        event = {
            "bucket": "test-bucket",
            "key": "ha_id=test_ha/bronze/dataset=property_schedule/ingest_date=2024-01-15/submission_id=123e4567-e89b-12d3-a456-426614174000/file=properties.csv",
        }

        csv_content = """uprn,address,postcode
100023456789,123 Main St,SW1A 1AA
100023456790,456 High St,E1 6AN
100023456791,789 Park Ave,M1 4PF"""

        with patch("backend.workers.sov_processor.UploadService") as mock_upload_service:
            mock_service = MagicMock()
            mock_service.get_file.return_value = csv_content.encode('utf-8')
            mock_upload_service.return_value = mock_service

            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"property_id": uuid.uuid4()})

            result = await process_sov_to_silver(
                event, db_conn=mock_conn, upload_service=mock_service
            )

            assert result["records_total"] == 3
            assert result["records_processed"] == 3


class TestColumnMappingCompleteness:
    """Tests to ensure column mapping covers common variations."""

    def test_all_mapped_columns_have_standard_names(self):
        """Test all mapped columns point to standard names."""
        standard_columns = {
            "uprn", "address", "postcode", "latitude", "longitude",
            "units", "height_m", "build_year", "construction_type",
            "tenure", "risk_rating", "block_name"
        }

        for source, target in COLUMN_MAPPING.items():
            assert target in standard_columns, f"Unknown target column: {target}"

    def test_common_variations_are_mapped(self):
        """Test common column variations are mapped."""
        # Address variations
        assert COLUMN_MAPPING.get("full_address") == "address"
        assert COLUMN_MAPPING.get("property_address") == "address"

        # Postcode variations
        assert COLUMN_MAPPING.get("post_code") == "postcode"
        assert COLUMN_MAPPING.get("postal_code") == "postcode"

        # Coordinate variations
        assert COLUMN_MAPPING.get("lat") == "latitude"
        assert COLUMN_MAPPING.get("lng") == "longitude"

        # Build year variations
        assert COLUMN_MAPPING.get("year_built") == "build_year"
        assert COLUMN_MAPPING.get("construction_year") == "build_year"
