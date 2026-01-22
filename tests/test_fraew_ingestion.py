"""
Tests for FRAEW (PAS 9980:2022) document ingestion.

Covers:
- FRAEW-specific feature extraction
- PDF error handling (password-protected, corrupted, empty)
- Integration tests with sample FRAEW PDFs
"""
import pytest
import io
import os
from unittest.mock import patch, MagicMock
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from backend.core.pdf_extraction.pdf_pipeline import (
    build_pdf_artifacts,
    extract_fraew_features,
    extract_features_from_text,
    _extract_text_sample,
    _check_pdf_accessible,
    detect_scanned_pdf,
    PDFExtractionError,
    PasswordProtectedPDFError,
    CorruptedPDFError,
    EmptyPDFError,
)


def create_pdf_with_text(text: str) -> bytes:
    """Create a simple PDF with the given text content."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    # Split text into lines and write each line
    y_position = 750
    for line in text.split('\n'):
        c.drawString(72, y_position, line)
        y_position -= 15
        if y_position < 72:
            c.showPage()
            y_position = 750
    c.save()
    buffer.seek(0)
    return buffer.read()


def create_empty_pdf() -> bytes:
    """Create an empty PDF (no pages)."""
    # This is a minimal valid PDF structure with no pages
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [] /Count 0 >>
endobj
xref
0 3
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
trailer
<< /Size 3 /Root 1 0 R >>
startxref
109
%%EOF"""


class TestFRAEWFeatureExtraction:
    """Tests for FRAEW-specific feature extraction."""

    def test_detects_pas_9980_compliance(self):
        """Test that PAS 9980:2022 compliance is detected."""
        text = """
        Fire Risk Appraisal of the External Wall (FRAEW)
        In accordance with PAS 9980:2022
        """
        features = extract_fraew_features(text)

        assert features["pas_9980_compliant"] is True
        assert features["pas_9980_version"] == "2022"

    def test_detects_pas_9980_without_year(self):
        """Test PAS 9980 detection when year is not specified."""
        text = "This assessment follows PAS 9980 methodology"
        features = extract_fraew_features(text)

        assert features["pas_9980_compliant"] is True
        assert features["pas_9980_version"] == "2022"  # Defaults to 2022

    def test_detects_building_risk_rating_high(self):
        """Test extraction of HIGH building risk rating."""
        text = """
        Building Risk Rating
        The risk rating is therefore considered as HIGH.
        """
        features = extract_fraew_features(text)

        assert features["building_risk_rating"] == "HIGH"

    def test_detects_building_risk_rating_low(self):
        """Test extraction of LOW building risk rating."""
        text = "Based on our assessment, the risk rating is considered as low."
        features = extract_fraew_features(text)

        assert features["building_risk_rating"] == "LOW"

    def test_detects_building_risk_rating_medium(self):
        """Test extraction of MEDIUM building risk rating."""
        text = 'The building has been rated as medium risk overall.'
        features = extract_fraew_features(text)

        assert features["building_risk_rating"] == "MEDIUM"

    def test_extracts_building_name(self):
        """Test extraction of building name."""
        text = """
        Property
        AuraCourt,1PercyStreet,Manchester
        Client
        """
        features = extract_fraew_features(text)

        assert features["building_name"] == "Aura Court"

    def test_extracts_job_reference(self):
        """Test extraction of job reference number."""
        text = """
        JobNr
        34254
        IssueDate
        """
        features = extract_fraew_features(text)

        assert features["job_reference"] == "34254"

    def test_extracts_client_name(self):
        """Test extraction of client name."""
        text = """
        Client
        EdgertonsEstatesLimited
        """
        features = extract_fraew_features(text)

        assert "Edgertons" in features["client_name"] or features["client_name"] is None

    def test_extracts_assessment_date(self):
        """Test extraction and conversion of assessment date."""
        text = """
        IssueDate
        27/02/2024
        """
        features = extract_fraew_features(text)

        assert features["assessment_date"] == "2024-02-27"

    def test_extracts_assessor_company(self):
        """Test extraction of assessor company name."""
        text = """
        Bailey Partnership (Consultants) LLP undertook a Fire Risk
        """
        features = extract_fraew_features(text)

        assert features["assessor_company"] == "Bailey Partnership (Consultants) LLP"

    def test_extracts_wall_types(self):
        """Test extraction of wall types."""
        text = """
        Wall Type 1 - Artstone - Summary
        Wall Type 2 - Timber Cladding - Summary
        Wall Type 3 - Trespa HPL - Summary
        """
        features = extract_fraew_features(text)

        assert len(features["wall_types"]) >= 3
        wall_names = [w["name"] for w in features["wall_types"]]
        assert "Artstone" in wall_names

    def test_deduplicates_wall_types(self):
        """Test that duplicate wall type entries are deduplicated."""
        text = """
        Wall Type 1 - Artstone - Summary
        Some content here
        Wall Type 1 - Artstone - Summary
        Wall Type 2 - Brick
        """
        features = extract_fraew_features(text)

        type_numbers = [w["type_number"] for w in features["wall_types"]]
        # Should not have duplicate type numbers
        assert len(type_numbers) == len(set(type_numbers))

    def test_detects_interim_measures(self):
        """Test detection of interim measures section."""
        text = "Recommendations - Interim Measures\nThe following interim measures are recommended"
        features = extract_fraew_features(text)

        assert features["has_interim_measures"] is True

    def test_detects_remedial_actions(self):
        """Test detection of remedial actions section."""
        text = "Recommendations - Remedial Actions\nThe following remedial works are required"
        features = extract_fraew_features(text)

        assert features["has_remedial_actions"] is True

    def test_handles_empty_text(self):
        """Test that empty text doesn't cause errors."""
        features = extract_fraew_features("")

        assert features["pas_9980_compliant"] is False
        assert features["building_name"] is None
        assert features["wall_types"] == []


class TestPDFErrorHandling:
    """Tests for PDF error handling."""

    def test_check_pdf_accessible_with_valid_pdf(self):
        """Test that valid PDFs pass accessibility check."""
        pdf_bytes = create_pdf_with_text("This is a valid PDF document")

        # Should not raise any exception
        _check_pdf_accessible(pdf_bytes)

    def test_check_pdf_accessible_raises_for_corrupted_pdf(self):
        """Test that corrupted PDFs raise CorruptedPDFError."""
        corrupted_bytes = b"This is not a valid PDF file"

        with pytest.raises(CorruptedPDFError):
            _check_pdf_accessible(corrupted_bytes)

    def test_check_pdf_accessible_raises_for_empty_pdf(self):
        """Test that empty PDFs raise appropriate error."""
        empty_pdf = create_empty_pdf()

        # Should raise either EmptyPDFError or CorruptedPDFError
        with pytest.raises((EmptyPDFError, CorruptedPDFError)):
            _check_pdf_accessible(empty_pdf)

    def test_build_pdf_artifacts_raises_for_corrupted_pdf(self):
        """Test that build_pdf_artifacts raises for corrupted PDFs."""
        corrupted_bytes = b"Not a valid PDF"

        with pytest.raises(CorruptedPDFError):
            build_pdf_artifacts(
                corrupted_bytes,
                file_type="fraew_document",
                filename="corrupted.pdf",
            )


class TestGenericFeatureExtraction:
    """Tests for generic PDF feature extraction (UPRNs, postcodes, dates)."""

    def test_extracts_uprns(self):
        """Test extraction of 12-digit UPRNs."""
        text = "Property UPRN: 123456789012 and another 987654321098"
        features = extract_features_from_text(text)

        assert "123456789012" in features["uprns"]
        assert "987654321098" in features["uprns"]

    def test_extracts_uk_postcodes(self):
        """Test extraction of UK postcodes."""
        text = "Address: 1 Percy Street, Manchester M15 4AB and London SW1A 1AA"
        features = extract_features_from_text(text)

        assert "M15 4AB" in features["postcodes"] or "M154AB" in features["postcodes"]
        assert "SW1A 1AA" in features["postcodes"]

    def test_extracts_dates_iso_format(self):
        """Test extraction of ISO format dates."""
        text = "Assessment date: 2024-02-27"
        features = extract_features_from_text(text)

        assert "2024-02-27" in features["dates"]

    def test_extracts_dates_uk_format(self):
        """Test extraction of UK format dates."""
        text = "Issue date: 27/02/2024"
        features = extract_features_from_text(text)

        assert "27/02/2024" in features["dates"]


class TestBuildPdfArtifacts:
    """Tests for the full PDF artifact building process."""

    def test_builds_artifacts_for_fraew_document(self):
        """Test that artifacts are built correctly for FRAEW documents."""
        text = """
        Fire Risk Appraisal of the External Wall (FRAEW)
        PAS 9980:2022
        Property: Test Building
        Postcode: M15 4AB
        The risk rating is considered as HIGH.
        """
        pdf_bytes = create_pdf_with_text(text)

        artifacts = build_pdf_artifacts(
            pdf_bytes,
            file_type="fraew_document",
            filename="test_fraew.pdf",
        )

        # Check extraction artifact
        assert artifacts.extraction["schema_version"] == "pdf-extraction/v1"
        assert artifacts.extraction["document"]["file_type"] == "fraew_document"
        assert artifacts.extraction["scanned"] is False

        # Check features artifact
        assert artifacts.features["schema_version"] == "pdf-features/v1"
        assert "fraew_specific" in artifacts.features["features"]

        # Check FRAEW-specific features
        fraew = artifacts.features["features"]["fraew_specific"]
        assert fraew["pas_9980_compliant"] is True

        # Check interpretation artifact
        assert artifacts.interpretation["status"] == "placeholder"
        assert artifacts.interpretation["requires_human_approval"] is True

    def test_builds_artifacts_for_non_fraew_document(self):
        """Test that non-FRAEW documents don't get FRAEW-specific features."""
        text = "Generic fire risk assessment document"
        pdf_bytes = create_pdf_with_text(text)

        artifacts = build_pdf_artifacts(
            pdf_bytes,
            file_type="fra_document",
            filename="test_fra.pdf",
        )

        # Should not have fraew_specific section
        assert "fraew_specific" not in artifacts.features["features"]

    def test_detects_scanned_pdf(self):
        """Test that scanned PDFs are detected correctly."""
        # Create PDF with minimal text (simulating scanned)
        pdf_bytes = create_pdf_with_text("")

        is_scanned = detect_scanned_pdf(pdf_bytes)

        # Empty text = scanned
        assert is_scanned is True

    def test_detects_digital_pdf(self):
        """Test that digital PDFs are detected correctly."""
        text = "This is a digital PDF with substantial text content. " * 10
        pdf_bytes = create_pdf_with_text(text)

        is_scanned = detect_scanned_pdf(pdf_bytes)

        assert is_scanned is False


class TestFRAEWIntegration:
    """Integration tests using real sample FRAEW PDFs."""

    @pytest.fixture
    def sample_fraew_pdf_path(self):
        """Path to sample FRAEW PDF file."""
        return "data/fraew/FRAEW-Report_Aura-Court.pdf"

    @pytest.fixture
    def sample_fraew_pdf_bytes(self, sample_fraew_pdf_path):
        """Load sample FRAEW PDF bytes."""
        if not os.path.exists(sample_fraew_pdf_path):
            pytest.skip(f"Sample FRAEW PDF not found: {sample_fraew_pdf_path}")
        with open(sample_fraew_pdf_path, "rb") as f:
            return f.read()

    def test_integration_extracts_fraew_features_from_real_pdf(self, sample_fraew_pdf_bytes):
        """Integration test: extract features from real FRAEW PDF."""
        artifacts = build_pdf_artifacts(
            sample_fraew_pdf_bytes,
            file_type="fraew_document",
            filename="FRAEW-Report_Aura-Court.pdf",
        )

        # Verify extraction completed
        assert artifacts.extraction["scanned"] is False
        assert artifacts.extraction["validation"]["is_valid"] is True

        # Verify FRAEW-specific features extracted
        fraew = artifacts.features["features"].get("fraew_specific", {})
        assert fraew.get("pas_9980_compliant") is True
        assert fraew.get("pas_9980_version") == "2022"

    def test_integration_extracts_building_info_from_real_pdf(self, sample_fraew_pdf_bytes):
        """Integration test: extract building info from real FRAEW PDF."""
        text = _extract_text_sample(sample_fraew_pdf_bytes, max_pages=15)
        features = extract_fraew_features(text)

        # Verify building information extracted
        assert features["building_name"] is not None
        assert "aura" in features["building_name"].lower() or "court" in features["building_name"].lower()

    def test_integration_extracts_risk_rating_from_real_pdf(self, sample_fraew_pdf_bytes):
        """Integration test: extract risk rating from real FRAEW PDF."""
        text = _extract_text_sample(sample_fraew_pdf_bytes, max_pages=15)
        features = extract_fraew_features(text)

        # The Aura Court report has HIGH risk rating
        assert features["building_risk_rating"] == "HIGH"

    def test_integration_extracts_postcodes_from_real_pdf(self, sample_fraew_pdf_bytes):
        """Integration test: extract postcodes from real FRAEW PDF."""
        text = _extract_text_sample(sample_fraew_pdf_bytes, max_pages=5)
        features = extract_features_from_text(text)

        # Should find Manchester postcode
        postcodes = features["postcodes"]
        assert len(postcodes) > 0
        # M15 4AB is the postcode in the sample
        assert any("M15" in pc or "M154" in pc for pc in postcodes)

    def test_integration_extracts_dates_from_real_pdf(self, sample_fraew_pdf_bytes):
        """Integration test: extract dates from real FRAEW PDF."""
        text = _extract_text_sample(sample_fraew_pdf_bytes, max_pages=5)
        features = extract_features_from_text(text)

        # Should find the issue date
        assert len(features["dates"]) > 0

    def test_integration_extracts_wall_types_from_real_pdf(self, sample_fraew_pdf_bytes):
        """Integration test: extract wall types from real FRAEW PDF."""
        text = _extract_text_sample(sample_fraew_pdf_bytes, max_pages=15)
        features = extract_fraew_features(text)

        # The Aura Court report has multiple wall types
        assert len(features["wall_types"]) >= 3
        wall_names = [w["name"].lower() for w in features["wall_types"]]
        assert any("artstone" in name for name in wall_names)

    def test_integration_detects_interim_measures_from_real_pdf(self, sample_fraew_pdf_bytes):
        """Integration test: detect interim measures section from real FRAEW PDF."""
        text = _extract_text_sample(sample_fraew_pdf_bytes, max_pages=15)
        features = extract_fraew_features(text)

        assert features["has_interim_measures"] is True

    def test_integration_detects_remedial_actions_from_real_pdf(self, sample_fraew_pdf_bytes):
        """Integration test: detect remedial actions section from real FRAEW PDF."""
        text = _extract_text_sample(sample_fraew_pdf_bytes, max_pages=15)
        features = extract_fraew_features(text)

        assert features["has_remedial_actions"] is True


class TestAcceptanceCriteriaMapping:
    """
    Test cases mapped to Jira acceptance criteria for KAN-467.

    Acceptance Criteria:
    [ ] FRAEW PDF files can be uploaded via API endpoint
    [ ] File type detection correctly identifies FRAEW documents (prioritized over FRA)
    [ ] Files are stored in S3 bronze layer with proper partitioning
    [ ] PDF text extraction works for both digital and scanned PDFs
    [ ] Tables are extracted and structured appropriately
    [ ] Metadata is captured (dates, assessor, PAS 9980 compliance, building info)
    [ ] PAS 9980:2022 standard references are identified
    [ ] Extraction artifacts are generated (extraction.json, features.json, interpretation.json)
    [ ] Audit trail (upload_audit, processing_audit) records ingestion
    [ ] Error handling for corrupted PDFs, password-protected files, unreadable content
    [ ] Unit tests for file detection, PDF extraction, and processing
    [ ] Integration test with sample FRAEW PDF file
    """

    def test_ac_pdf_text_extraction_digital(self):
        """AC: PDF text extraction works for digital PDFs."""
        text = "PAS 9980:2022 Fire Risk Appraisal of External Walls"
        pdf_bytes = create_pdf_with_text(text)

        artifacts = build_pdf_artifacts(
            pdf_bytes,
            file_type="fraew_document",
            filename="digital.pdf",
        )

        assert artifacts.extraction["scanned"] is False
        assert len(artifacts.extraction.get("pages", [])) > 0

    def test_ac_metadata_captured_pas_9980(self):
        """AC: PAS 9980:2022 standard references are identified."""
        text = "Assessment conducted in accordance with PAS 9980:2022"
        features = extract_fraew_features(text)

        assert features["pas_9980_compliant"] is True
        assert features["pas_9980_version"] == "2022"

    def test_ac_metadata_captured_dates(self):
        """AC: Metadata - dates are captured."""
        text = "Issue Date: 27/02/2024"
        features = extract_fraew_features(text)

        assert features["assessment_date"] == "2024-02-27"

    def test_ac_metadata_captured_building_info(self):
        """AC: Metadata - building info is captured."""
        text = """
        Property
        TestCourt
        Client
        """
        features = extract_fraew_features(text)

        # Building name should be extracted (handling concatenated text)
        assert features["building_name"] is not None

    def test_ac_extraction_artifacts_generated(self):
        """AC: Extraction artifacts are generated (extraction.json, features.json, interpretation.json)."""
        pdf_bytes = create_pdf_with_text("FRAEW Report PAS 9980:2022")

        artifacts = build_pdf_artifacts(
            pdf_bytes,
            file_type="fraew_document",
            filename="test.pdf",
        )

        # All three artifacts should be generated
        assert artifacts.extraction is not None
        assert artifacts.features is not None
        assert artifacts.interpretation is not None

        # Check schema versions
        assert "schema_version" in artifacts.extraction
        assert "schema_version" in artifacts.features

    def test_ac_error_handling_corrupted_pdf(self):
        """AC: Error handling for corrupted PDFs."""
        corrupted_bytes = b"not a pdf file"

        with pytest.raises(CorruptedPDFError):
            build_pdf_artifacts(
                corrupted_bytes,
                file_type="fraew_document",
                filename="corrupted.pdf",
            )
