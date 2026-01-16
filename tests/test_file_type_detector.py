"""
TDD tests for file type detector (content-based detection).
"""
import pytest
import pandas as pd
import io
from backend.api.ingestion.file_type_detector import FileTypeDetector, FileType
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


@pytest.fixture
def detector():
    """Create a file type detector instance."""
    return FileTypeDetector()


class TestPropertyScheduleDetection:
    """Tests for detecting property schedule files."""
    
    def test_detects_property_schedule_by_address_column(self, detector):
        """Test that files with address columns are detected as property schedules."""
        df = pd.DataFrame({
            'property_id': [1, 2, 3],
            'address': ['123 Test Street', '456 Test Road', '789 Test Avenue'],
            'postcode': ['SW1A 1AA', 'M1 1AA', 'EH1 1AB'],
            'uprn': ['123456789012', '123456789013', '123456789014'],
        })
        
        detected_type = detector.detect_file_type_from_dataframe(df, 'test.csv')
        
        assert detected_type == FileType.PROPERTY_SCHEDULE
    
    def test_detects_property_schedule_by_uprn_column(self, detector):
        """Test that files with UPRN columns are detected as property schedules."""
        df = pd.DataFrame({
            'uprn': ['123456789012', '123456789013'],
            'postcode': ['SW1A 1AA', 'M1 1AA'],
        })
        
        detected_type = detector.detect_file_type_from_dataframe(df, 'test.csv')
        
        assert detected_type == FileType.PROPERTY_SCHEDULE
    
    def test_detects_property_schedule_by_postcode_column(self, detector):
        """Test that files with postcode columns are detected as property schedules."""
        df = pd.DataFrame({
            'postcode': ['SW1A 1AA', 'M1 1AA', 'EH1 1AB'],
            'property_ref': ['P001', 'P002', 'P003'],
        })
        
        detected_type = detector.detect_file_type_from_dataframe(df, 'test.csv')
        
        assert detected_type == FileType.PROPERTY_SCHEDULE
    
    def test_detects_property_schedule_by_property_keywords(self, detector):
        """Test that files with property-related keywords are detected as property schedules."""
        df = pd.DataFrame({
            'property_id': [1, 2, 3],
            'tenure': ['social', 'private', 'shared'],
            'unit_type': ['flat', 'house', 'bungalow'],
        })
        
        detected_type = detector.detect_file_type_from_dataframe(df, 'test.csv')
        
        assert detected_type == FileType.PROPERTY_SCHEDULE


class TestEPCDataDetection:
    """Tests for detecting EPC data files."""
    
    def test_detects_epc_data_by_epc_rating_column(self, detector):
        """Test that files with EPC rating columns are detected as EPC data."""
        df = pd.DataFrame({
            'uprn': ['123456789012', '123456789013', '123456789014'],
            'epc_rating': ['A', 'B', 'C'],
            'epc_date': ['2023-01-15', '2023-02-20', '2023-03-10'],
        })
        
        detected_type = detector.detect_file_type_from_dataframe(df, 'test.csv')
        
        assert detected_type == FileType.EPC_DATA
    
    def test_detects_epc_data_by_epc_keywords(self, detector):
        """Test that files with EPC-related keywords are detected as EPC data."""
        df = pd.DataFrame({
            'property_id': [1, 2, 3],
            'current_energy_rating': ['A', 'B', 'C'],
            'energy_efficiency': [85, 75, 65],
        })
        
        detected_type = detector.detect_file_type_from_dataframe(df, 'test.csv')
        
        assert detected_type == FileType.EPC_DATA


class TestFRADetection:
    """Tests for detecting FRA (Fire Risk Assessment) document files."""
    
    def test_detects_fra_by_filename_pattern(self, detector):
        """Test that PDF files with FRA in filename are detected as FRA documents."""
        detected_type = detector.detect_file_type_from_filename('fra_report_block_a.pdf')
        
        assert detected_type == FileType.FRA_DOCUMENT
    
    def test_detects_fra_by_fire_risk_assessment_keywords(self, detector):
        """Test that PDF files with fire risk assessment keywords are detected as FRA documents."""
        detected_type = detector.detect_file_type_from_filename('fire_risk_assessment_block_b.pdf')
        
        assert detected_type == FileType.FRA_DOCUMENT


class TestFRSADetection:
    """Tests for detecting FRSA (Fire Risk Safety Assessment) document files."""
    
    def test_detects_frsa_by_filename_pattern(self, detector):
        """Test that PDF files with FRSA in filename are detected as FRSA documents."""
        detected_type = detector.detect_file_type_from_filename('frsa_report_block_a.pdf')
        
        assert detected_type == FileType.FRSA_DOCUMENT
    
    def test_detects_frsa_by_fire_risk_safety_assessment_keywords(self, detector):
        """Test that PDF files with fire risk safety assessment keywords are detected as FRSA documents."""
        detected_type = detector.detect_file_type_from_filename('fire_risk_safety_assessment.pdf')
        
        assert detected_type == FileType.FRSA_DOCUMENT


class TestFRAEWDetection:
    """Tests for detecting FRAEW (PAS 9980) document files."""
    
    def test_detects_fraew_by_filename_pattern(self, detector):
        """Test that PDF files with FRAEW in filename are detected as FRAEW documents."""
        detected_type = detector.detect_file_type_from_filename('fraew_report_block_a.pdf')
        
        assert detected_type == FileType.FRAEW_DOCUMENT
    
    def test_detects_fraew_by_pas_9980_keyword(self, detector):
        """Test that PDF files with PAS 9980 in filename are detected as FRAEW documents."""
        detected_type = detector.detect_file_type_from_filename('pas_9980_appraisal.pdf')
        
        assert detected_type == FileType.FRAEW_DOCUMENT
    
    def test_detects_fraew_by_external_walls_keyword(self, detector):
        """Test that PDF files with external walls keywords are detected as FRAEW documents."""
        detected_type = detector.detect_file_type_from_filename('external_walls_appraisal.pdf')
        
        assert detected_type == FileType.FRAEW_DOCUMENT
    
    def test_detects_fraew_by_fire_risk_appraisal_keyword(self, detector):
        """Test that PDF files with fire risk appraisal keywords are detected as FRAEW documents."""
        detected_type = detector.detect_file_type_from_filename('fire_risk_appraisal_external_walls.pdf')
        
        assert detected_type == FileType.FRAEW_DOCUMENT


class TestSCRDetection:
    """Tests for detecting SCR (Safety Case Report) document files."""
    
    def test_detects_scr_by_filename_pattern(self, detector):
        """Test that PDF files with SCR in filename are detected as SCR documents."""
        detected_type = detector.detect_file_type_from_filename('scr_report_block_a.pdf')
        
        assert detected_type == FileType.SCR_DOCUMENT
    
    def test_detects_scr_by_safety_case_keyword(self, detector):
        """Test that PDF files with safety case keywords are detected as SCR documents."""
        detected_type = detector.detect_file_type_from_filename('safety_case_report.pdf')
        
        assert detected_type == FileType.SCR_DOCUMENT
    
    def test_detects_scr_by_safety_case_report_keyword(self, detector):
        """Test that PDF files with safety case report keywords are detected as SCR documents."""
        detected_type = detector.detect_file_type_from_filename('safety_case_report_block_b.pdf')
        
        assert detected_type == FileType.SCR_DOCUMENT


class TestFilenameBasedDetection:
    """Tests for filename-based detection fallback."""
    
    def test_detects_by_sov_keyword(self, detector):
        """Test that files with SOV (Schedule of Values) keyword are detected as property schedules."""
        detected_type = detector.detect_file_type_from_filename('property_sov_2024.csv')
        
        assert detected_type == FileType.PROPERTY_SCHEDULE
    
    def test_detects_by_epc_keyword(self, detector):
        """Test that files with EPC keyword are detected as EPC data."""
        detected_type = detector.detect_file_type_from_filename('epc_ratings_2024.csv')
        
        assert detected_type == FileType.EPC_DATA
    
    def test_detects_by_property_keyword(self, detector):
        """Test that files with property keyword are detected as property schedules."""
        detected_type = detector.detect_file_type_from_filename('property_portfolio.csv')
        
        assert detected_type == FileType.PROPERTY_SCHEDULE
    
    def test_detection_priority_fraew_before_fra(self, detector):
        """Test that FRAEW detection takes priority over general FRA detection."""
        # FRAEW should be detected before FRA due to more specific keywords
        detected_type = detector.detect_file_type_from_filename('fraew_block_a.pdf')
        
        assert detected_type == FileType.FRAEW_DOCUMENT
    
    def test_detection_priority_scr_before_general_fire(self, detector):
        """Test that SCR detection takes priority over general fire keywords."""
        detected_type = detector.detect_file_type_from_filename('safety_case_report.pdf')
        
        assert detected_type == FileType.SCR_DOCUMENT
    
    def test_detection_priority_frsa_before_fra(self, detector):
        """Test that FRSA detection takes priority over FRA."""
        detected_type = detector.detect_file_type_from_filename('frsa_report.pdf')
        
        assert detected_type == FileType.FRSA_DOCUMENT


class TestUncertaintyHandling:
    """Tests for handling uncertain detections."""
    
    def test_returns_unknown_for_unclear_content(self, detector):
        """Test that unclear files return UNKNOWN type."""
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'value': [100, 200, 300],
        })
        
        detected_type = detector.detect_file_type_from_dataframe(df, 'data.csv')
        
        # Should default to property_schedule for CSV/Excel if unclear
        assert detected_type in [FileType.PROPERTY_SCHEDULE, FileType.UNKNOWN]
    
    def test_pdf_defaults_to_fra_if_uncertain(self, detector):
        """Test that PDF files default to FRA if content cannot be analyzed."""
        # Use detect_file_type with no content to trigger default behavior
        detected_type = detector.detect_file_type('document.pdf', file_content=None)
        
        assert detected_type == FileType.FRA_DOCUMENT


class TestCSVExcelHandling:
    """Tests for CSV and Excel file handling."""
    
    def test_detects_from_csv_content(self, detector):
        """Test detection from CSV file content."""
        csv_content = """property_id,address,postcode
1,123 Test St,SW1A 1AA
2,456 Test Rd,M1 1AA"""
        
        df = pd.read_csv(io.StringIO(csv_content))
        detected_type = detector.detect_file_type_from_dataframe(df, 'test.csv')
        
        assert detected_type == FileType.PROPERTY_SCHEDULE
    
    def test_detects_from_excel_content(self, detector):
        """Test detection from Excel file content."""
        df = pd.DataFrame({
            'uprn': ['123456789012'],
            'epc_rating': ['A'],
        })
        
        detected_type = detector.detect_file_type_from_dataframe(df, 'test.xlsx')
        
        assert detected_type == FileType.EPC_DATA


def create_pdf_with_text(text: str) -> bytes:
    """Helper function to create a PDF with text content."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    # Add text to PDF
    c.drawString(100, 750, text)
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


class TestPDFContentDetection:
    """Tests for PDF content-based detection."""
    
    def test_detects_fra_from_pdf_content(self, detector):
        """Test that PDFs with FRA content are detected correctly."""
        pdf_content = create_pdf_with_text(
            "Fire Risk Assessment Report\nBlock A Assessment\nFire safety evaluation"
        )
        
        detected_type = detector.detect_file_type_from_pdf_content(
            pdf_content, "generic_document.pdf"
        )
        
        assert detected_type == FileType.FRA_DOCUMENT
    
    def test_detects_frsa_from_pdf_content(self, detector):
        """Test that PDFs with FRSA content are detected correctly."""
        pdf_content = create_pdf_with_text(
            "Fire Risk Safety Assessment\nBuilding Safety Report\nFRSA evaluation"
        )
        
        detected_type = detector.detect_file_type_from_pdf_content(
            pdf_content, "generic_document.pdf"
        )
        
        assert detected_type == FileType.FRSA_DOCUMENT
    
    def test_detects_fraew_from_pdf_content(self, detector):
        """Test that PDFs with FRAEW (PAS 9980) content are detected correctly."""
        pdf_content = create_pdf_with_text(
            "PAS 9980 Fire Risk Appraisal of External Walls\nExternal Walls Assessment\nFRAEW Report"
        )
        
        detected_type = detector.detect_file_type_from_pdf_content(
            pdf_content, "generic_document.pdf"
        )
        
        assert detected_type == FileType.FRAEW_DOCUMENT
    
    def test_detects_scr_from_pdf_content(self, detector):
        """Test that PDFs with SCR content are detected correctly."""
        pdf_content = create_pdf_with_text(
            "Safety Case Report\nBuilding Safety Case\nSCR Document"
        )
        
        detected_type = detector.detect_file_type_from_pdf_content(
            pdf_content, "generic_document.pdf"
        )
        
        assert detected_type == FileType.SCR_DOCUMENT
    
    def test_pdf_content_takes_priority_over_filename(self, detector):
        """Test that PDF content detection takes priority over filename."""
        # Create PDF with FRAEW content but generic filename
        pdf_content = create_pdf_with_text(
            "PAS 9980 Fire Risk Appraisal of External Walls\nExternal Walls Assessment"
        )
        
        detected_type = detector.detect_file_type(
            filename="generic_report.pdf",
            file_content=pdf_content
        )
        
        assert detected_type == FileType.FRAEW_DOCUMENT
    
    def test_pdf_falls_back_to_filename_if_content_unclear(self, detector):
        """Test that PDF falls back to filename if content is unclear."""
        # Create PDF with minimal/unclear content
        pdf_content = create_pdf_with_text("Generic Document\nNo specific keywords")
        
        detected_type = detector.detect_file_type(
            filename="frsa_report.pdf",
            file_content=pdf_content
        )
        
        # Should use filename since content is unclear
        assert detected_type == FileType.FRSA_DOCUMENT
    
    def test_pdf_defaults_to_fra_if_both_unclear(self, detector):
        """Test that PDF defaults to FRA if both content and filename are unclear."""
        pdf_content = create_pdf_with_text("Generic Document\nNo keywords")
        
        detected_type = detector.detect_file_type(
            filename="document.pdf",
            file_content=pdf_content
        )
        
        assert detected_type == FileType.FRA_DOCUMENT
    
    def test_pdf_content_detection_requires_multiple_keywords(self, detector):
        """Test that PDF content detection requires multiple keywords for confidence."""
        # Single keyword should not be enough for FRAEW
        pdf_content = create_pdf_with_text("External walls assessment")
        
        detected_type = detector.detect_file_type_from_pdf_content(
            pdf_content, "document.pdf"
        )
        
        # Should return UNKNOWN since we need multiple keywords
        assert detected_type == FileType.UNKNOWN
    
    def test_pdf_content_detection_handles_extraction_failure(self, detector):
        """Test that PDF detection handles extraction failures gracefully."""
        # Invalid PDF content
        invalid_pdf = b"Not a valid PDF"
        
        detected_type = detector.detect_file_type_from_pdf_content(
            invalid_pdf, "document.pdf"
        )
        
        # Should return UNKNOWN on failure
        assert detected_type == FileType.UNKNOWN
