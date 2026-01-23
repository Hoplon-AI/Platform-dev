"""
Tests for FRA (Fire Risk Assessment) document ingestion.

Covers:
- FRA-specific feature extraction
- Risk rating extraction (5-level scale: Trivial, Tolerable, Moderate, Substantial, Intolerable)
- Assessment type detection
- Evacuation strategy detection
- FSO compliance indicators
- Integration tests with sample FRA PDFs
"""
import pytest
import io
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from backend.core.pdf_extraction.pdf_pipeline import (
    build_pdf_artifacts,
    extract_fra_features,
    extract_features_from_text,
    _extract_text_sample,
    _convert_text_date_to_iso,
)


def create_pdf_with_text(text: str) -> bytes:
    """Create a simple PDF with the given text content."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
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


class TestFRAFeatureExtraction:
    """Tests for FRA-specific feature extraction."""

    def test_detects_moderate_risk_rating(self):
        """Test extraction of MODERATE risk rating."""
        text = """
        FIRE RISK ASSESSMENT REPORT
        Overall: Moderate
        """
        features = extract_fra_features(text)

        assert features["overall_risk_rating"] == "MODERATE"

    def test_detects_substantial_risk_rating(self):
        """Test extraction of SUBSTANTIAL risk rating."""
        text = "The risk rating is considered to be Substantial based on our findings."
        features = extract_fra_features(text)

        assert features["overall_risk_rating"] == "SUBSTANTIAL"

    def test_detects_intolerable_risk_rating(self):
        """Test extraction of INTOLERABLE risk rating."""
        text = "Overall Risk: Intolerable - immediate action required"
        features = extract_fra_features(text)

        assert features["overall_risk_rating"] == "INTOLERABLE"

    def test_detects_tolerable_risk_rating(self):
        """Test extraction of TOLERABLE risk rating."""
        text = "Risk Assessment Level: Tolerable"
        features = extract_fra_features(text)

        assert features["overall_risk_rating"] == "TOLERABLE"

    def test_detects_trivial_risk_rating(self):
        """Test extraction of TRIVIAL risk rating."""
        text = "Overall fire risk: Trivial"
        features = extract_fra_features(text)

        assert features["overall_risk_rating"] == "TRIVIAL"

    def test_detects_simple_high_medium_low_ratings(self):
        """Test extraction of simplified HIGH/MEDIUM/LOW ratings."""
        text = "Fire Risk Rating: High"
        features = extract_fra_features(text)

        assert features["overall_risk_rating"] == "HIGH"

    def test_extracts_assessment_type(self):
        """Test extraction of assessment type."""
        text = """
        Risk Assessment Type:
        Type 3 - Common parts and flats (non-intrusive)
        """
        features = extract_fra_features(text)

        assert features["assessment_type"] is not None
        assert "Type 3" in features["assessment_type"]

    def test_extracts_building_name_from_premises(self):
        """Test extraction of building name from premises field."""
        text = """
        Site: 38-48 Scarfe Way
        Colchester
        Assessed by: Test
        """
        features = extract_fra_features(text)

        # Building name should be extracted
        assert features["building_name"] is not None or features["address"] is not None

    def test_extracts_client_name(self):
        """Test extraction of client name."""
        text = """
        on behalf of Colchester Borough Homes
        for property
        """
        features = extract_fra_features(text)

        assert features["client_name"] is not None
        assert "Colchester Borough Homes" in features["client_name"]

    def test_extracts_assessment_date_text_format(self):
        """Test extraction and conversion of text format assessment date."""
        text = "Date assessed: 8th February 2023"
        features = extract_fra_features(text)

        assert features["assessment_date"] == "2023-02-08"

    def test_extracts_review_date(self):
        """Test extraction of review date."""
        text = "Review date: 8th February 2028"
        features = extract_fra_features(text)

        assert features["review_date"] == "2028-02-08"

    def test_detects_stay_put_evacuation_strategy(self):
        """Test detection of Stay Put evacuation strategy."""
        text = "The strategy of the building is that of Stay Put."
        features = extract_fra_features(text)

        assert features["evacuation_strategy"] == "STAY_PUT"

    def test_detects_simultaneous_evacuation_strategy(self):
        """Test detection of simultaneous evacuation strategy."""
        text = "The building operates a simultaneous evacuation procedure."
        features = extract_fra_features(text)

        assert features["evacuation_strategy"] == "SIMULTANEOUS"

    def test_detects_phased_evacuation_strategy(self):
        """Test detection of phased evacuation strategy."""
        text = "A phased evacuation strategy is implemented."
        features = extract_fra_features(text)

        assert features["evacuation_strategy"] == "PHASED"

    def test_detects_fso_compliance(self):
        """Test detection of FSO (Regulatory Reform Fire Safety Order) compliance."""
        text = "In accordance with Regulatory Reform (Fire Safety) Order 2005"
        features = extract_fra_features(text)

        assert features["fso_compliant"] is True

    def test_detects_housing_act_compliance(self):
        """Test detection of Housing Act 2004 compliance."""
        text = "This assessment complies with Housing Act 2004 and LACORS guidance."
        features = extract_fra_features(text)

        assert features["housing_act_compliant"] is True

    def test_detects_significant_findings_section(self):
        """Test detection of significant findings section."""
        text = "Section 3: Significant Findings and Action Plan"
        features = extract_fra_features(text)

        assert features["has_significant_findings"] is True

    def test_detects_action_plan_section(self):
        """Test detection of action plan section."""
        text = "Action Plan: The following remedial actions are required"
        features = extract_fra_features(text)

        assert features["has_action_plan"] is True

    def test_handles_empty_text(self):
        """Test that empty text doesn't cause errors."""
        features = extract_fra_features("")

        assert features["overall_risk_rating"] is None
        assert features["building_name"] is None
        assert features["evacuation_strategy"] is None


class TestDateConversion:
    """Tests for date format conversion."""

    def test_converts_text_date_with_ordinal(self):
        """Test conversion of dates with ordinal suffixes."""
        assert _convert_text_date_to_iso("8th February 2023") == "2023-02-08"
        assert _convert_text_date_to_iso("1st January 2024") == "2024-01-01"
        assert _convert_text_date_to_iso("22nd March 2023") == "2023-03-22"
        assert _convert_text_date_to_iso("3rd April 2023") == "2023-04-03"

    def test_converts_text_date_without_ordinal(self):
        """Test conversion of dates without ordinal suffixes."""
        assert _convert_text_date_to_iso("15 June 2023") == "2023-06-15"

    def test_converts_slash_date_format(self):
        """Test conversion of DD/MM/YYYY format."""
        assert _convert_text_date_to_iso("08/02/2023") == "2023-02-08"

    def test_converts_dash_date_format(self):
        """Test conversion of DD-MM-YYYY format."""
        assert _convert_text_date_to_iso("08-02-2023") == "2023-02-08"

    def test_returns_none_for_invalid_date(self):
        """Test that invalid date formats return None."""
        assert _convert_text_date_to_iso("invalid date") is None
        assert _convert_text_date_to_iso("") is None


class TestBuildPdfArtifactsForFRA:
    """Tests for the full PDF artifact building process for FRA documents."""

    def test_builds_artifacts_for_fra_document(self):
        """Test that artifacts are built correctly for FRA documents."""
        text = """
        FIRE RISK ASSESSMENT REPORT
        Overall: Moderate
        In accordance with Regulatory Reform (Fire Safety) Order 2005
        Stay Put strategy is in place.
        Date assessed: 15th March 2023
        """
        pdf_bytes = create_pdf_with_text(text)

        artifacts = build_pdf_artifacts(
            pdf_bytes,
            file_type="fra_document",
            filename="test_fra.pdf",
        )

        # Check extraction artifact
        assert artifacts.extraction["schema_version"] == "pdf-extraction/v1"
        assert artifacts.extraction["document"]["file_type"] == "fra_document"

        # Check features artifact
        assert "fra_specific" in artifacts.features["features"]

        # Check FRA-specific features
        fra = artifacts.features["features"]["fra_specific"]
        assert fra["fso_compliant"] is True

    def test_fra_document_does_not_have_fraew_features(self):
        """Test that FRA documents don't have FRAEW-specific features."""
        text = "Fire Risk Assessment Report - General assessment"
        pdf_bytes = create_pdf_with_text(text)

        artifacts = build_pdf_artifacts(
            pdf_bytes,
            file_type="fra_document",
            filename="test_fra.pdf",
        )

        # Should have fra_specific, not fraew_specific
        assert "fra_specific" in artifacts.features["features"]
        assert "fraew_specific" not in artifacts.features["features"]


class TestFRAIntegration:
    """Integration tests using real sample FRA PDFs."""

    @pytest.fixture
    def sample_fra_pdf_path(self):
        """Path to sample FRA PDF file."""
        return "data/frsa/Scarfe-Way-38-48-Fire-Risk-Assessment.pdf"

    @pytest.fixture
    def sample_fra_pdf_bytes(self, sample_fra_pdf_path):
        """Load sample FRA PDF bytes."""
        if not os.path.exists(sample_fra_pdf_path):
            pytest.skip(f"Sample FRA PDF not found: {sample_fra_pdf_path}")
        with open(sample_fra_pdf_path, "rb") as f:
            return f.read()

    def test_integration_extracts_fra_features_from_real_pdf(self, sample_fra_pdf_bytes):
        """Integration test: extract features from real FRA PDF."""
        artifacts = build_pdf_artifacts(
            sample_fra_pdf_bytes,
            file_type="fra_document",
            filename="Scarfe-Way-38-48-Fire-Risk-Assessment.pdf",
        )

        # Verify extraction completed
        assert artifacts.extraction["scanned"] is False
        assert artifacts.extraction["validation"]["is_valid"] is True

        # Verify FRA-specific features extracted
        fra = artifacts.features["features"].get("fra_specific", {})
        assert fra.get("overall_risk_rating") is not None

    def test_integration_extracts_risk_rating_from_real_pdf(self, sample_fra_pdf_bytes):
        """Integration test: extract risk rating from real FRA PDF."""
        text = _extract_text_sample(sample_fra_pdf_bytes, max_pages=15)
        features = extract_fra_features(text)

        # The Scarfe Way report has MODERATE risk rating
        assert features["overall_risk_rating"] == "MODERATE"

    def test_integration_extracts_client_from_real_pdf(self, sample_fra_pdf_bytes):
        """Integration test: extract client from real FRA PDF."""
        text = _extract_text_sample(sample_fra_pdf_bytes, max_pages=10)
        features = extract_fra_features(text)

        assert features["client_name"] is not None
        assert "Colchester" in features["client_name"] or "Borough" in features["client_name"]

    def test_integration_extracts_dates_from_real_pdf(self, sample_fra_pdf_bytes):
        """Integration test: extract dates from real FRA PDF."""
        text = _extract_text_sample(sample_fra_pdf_bytes, max_pages=10)
        features = extract_fra_features(text)

        # Should find assessment and review dates
        assert features["assessment_date"] is not None
        assert features["review_date"] is not None

    def test_integration_detects_evacuation_strategy_from_real_pdf(self, sample_fra_pdf_bytes):
        """Integration test: detect evacuation strategy from real FRA PDF."""
        text = _extract_text_sample(sample_fra_pdf_bytes, max_pages=15)
        features = extract_fra_features(text)

        # The Scarfe Way report uses Stay Put strategy
        assert features["evacuation_strategy"] == "STAY_PUT"

    def test_integration_detects_fso_compliance_from_real_pdf(self, sample_fra_pdf_bytes):
        """Integration test: detect FSO compliance from real FRA PDF."""
        text = _extract_text_sample(sample_fra_pdf_bytes, max_pages=15)
        features = extract_fra_features(text)

        assert features["fso_compliant"] is True

    def test_integration_detects_assessment_type_from_real_pdf(self, sample_fra_pdf_bytes):
        """Integration test: detect assessment type from real FRA PDF."""
        text = _extract_text_sample(sample_fra_pdf_bytes, max_pages=10)
        features = extract_fra_features(text)

        assert features["assessment_type"] is not None
        assert "Type 3" in features["assessment_type"]


class TestAcceptanceCriteriaMapping:
    """
    Test cases mapped to Jira acceptance criteria for KAN-465.

    Acceptance Criteria:
    [ ] FRA PDF files can be uploaded via API endpoint
    [ ] File type detection correctly identifies FRA documents
    [ ] Files are stored in S3 bronze layer with proper partitioning
    [ ] PDF text extraction works for both digital and scanned PDFs
    [ ] Tables are extracted and structured appropriately
    [ ] Metadata is captured (dates, assessor, building info)
    [ ] Extraction artifacts are generated (extraction.json, features.json, interpretation.json)
    [ ] Audit trail (upload_audit, processing_audit) records ingestion
    [ ] Error handling for corrupted PDFs, password-protected files, unreadable content
    [ ] Unit tests for file detection, PDF extraction, and processing
    [ ] Integration test with sample FRA PDF file
    """

    def test_ac_pdf_text_extraction_digital(self):
        """AC: PDF text extraction works for digital PDFs."""
        text = "Fire Risk Assessment Report - Overall Risk: Moderate"
        pdf_bytes = create_pdf_with_text(text)

        artifacts = build_pdf_artifacts(
            pdf_bytes,
            file_type="fra_document",
            filename="digital.pdf",
        )

        assert artifacts.extraction["scanned"] is False
        assert len(artifacts.extraction.get("pages", [])) > 0

    def test_ac_metadata_captured_dates(self):
        """AC: Metadata - dates are captured."""
        text = "Date assessed: 15th March 2023\nReview date: 15th March 2028"
        features = extract_fra_features(text)

        assert features["assessment_date"] == "2023-03-15"
        assert features["review_date"] == "2028-03-15"

    def test_ac_metadata_captured_assessor(self):
        """AC: Metadata - assessor info is captured."""
        text = "Risk Assessment Consultant: John Smith"
        features = extract_fra_features(text)

        assert features["assessor_name"] is not None

    def test_ac_metadata_captured_building_info(self):
        """AC: Metadata - building info is captured."""
        text = """
        Site: Test Building, 123 Main Street
        Client: Test Housing Association
        """
        features = extract_fra_features(text)

        # Should capture some building info
        assert features["building_name"] is not None or features["address"] is not None

    def test_ac_extraction_artifacts_generated(self):
        """AC: Extraction artifacts are generated (extraction.json, features.json, interpretation.json)."""
        pdf_bytes = create_pdf_with_text("FRA Report - Fire Risk Assessment")

        artifacts = build_pdf_artifacts(
            pdf_bytes,
            file_type="fra_document",
            filename="test.pdf",
        )

        # All three artifacts should be generated
        assert artifacts.extraction is not None
        assert artifacts.features is not None
        assert artifacts.interpretation is not None

        # Check schema versions
        assert "schema_version" in artifacts.extraction
        assert "schema_version" in artifacts.features

    def test_ac_fra_specific_features_extracted(self):
        """AC: FRA-specific metadata is captured."""
        text = """
        Fire Risk Assessment
        Overall Risk: Moderate
        Stay Put strategy
        Regulatory Reform (Fire Safety) Order 2005
        """
        features = extract_fra_features(text)

        assert features["overall_risk_rating"] == "MODERATE"
        assert features["evacuation_strategy"] == "STAY_PUT"
        assert features["fso_compliant"] is True
