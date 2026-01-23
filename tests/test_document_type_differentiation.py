"""
Tests for FRA vs FRAEW document type differentiation.

Validates that the file type detector correctly classifies:
- FRA (Fire Risk Assessment) documents from data/frsa/
- FRAEW (Fire Risk Appraisal of External Walls / PAS 9980) documents from data/fraew/

This ensures documents are routed to the correct extraction pipeline.

Note: Some files in the data directories are reference/support documents that may not
be actual FRA or FRAEW assessments. The explicit file lists below contain only
verified FRA/FRAEW documents.
"""
import pytest
import os
from pathlib import Path

from backend.api.ingestion.file_type_detector import FileTypeDetector, FileType


# Test data directories
DATA_DIR = Path(__file__).parent.parent / "data"
FRA_DIR = DATA_DIR / "frsa"
FRAEW_DIR = DATA_DIR / "fraew"

# Explicit lists of verified FRA and FRAEW documents
# These are files confirmed to be actual assessments of the correct type
VERIFIED_FRA_FILES = [
    "Scarfe-Way-38-48-Fire-Risk-Assessment.pdf",
    "The-Square-1-10-Fire-Risk-Assessment.pdf",
    "20210715fireriskassessmentsharwood.pdf",
    "20210715fireriskassessmentwoodstockhouse.pdf",
    "2021-fra-for-samphire-heights-7-mb.pdf",
    "Southern Housing - 2021-fra-for-vega-house-7-mb.pdf",
]

VERIFIED_FRAEW_FILES = [
    "FRAEW-Report_Aura-Court.pdf",
    "FRAEW-Report-Risk-Factor-HIGH.pdf",
    "fraew.pdf",
    "fraew 2.pdf",
    "PAS-9980.pdf",
    "Fire risk appraisal of external walls for Elizabeth Court.pdf",
    "3661_56-High-Street-Manchester-ORSA-FRAEW_JLO060922.pdf",
]

# Files that are miscategorized or are not actual FRA/FRAEW assessments
# (kept for documentation purposes)
EXCLUDED_FILES = {
    # In data/frsa but not an FRA - it's a regulatory briefing note
    "202425Q1_FRS_BriefingNote_FinalDraft__2_.pdf": "Regulatory briefing note, not FRA",
    # In data/frsa but is a strategy document, not an FRA
    "Southern Housing Resident Strategy.pdf": "Strategy document, not FRA",
    # In data/fraew but is actually an FRA (Type 3) - miscategorized
    "woodhall-flats-block-01-33-fire-risk-assessment-2022.pdf": "Actually an FRA Type 3, not FRAEW",
}


@pytest.fixture
def detector():
    """Create a FileTypeDetector instance."""
    return FileTypeDetector()


class TestFRADocumentDifferentiation:
    """Tests that FRA documents are correctly identified as FRA_DOCUMENT."""

    @pytest.fixture
    def fra_pdf_files(self):
        """Get list of verified FRA PDF files."""
        if not FRA_DIR.exists():
            pytest.skip(f"FRA data directory not found: {FRA_DIR}")

        pdf_files = [FRA_DIR / f for f in VERIFIED_FRA_FILES if (FRA_DIR / f).exists()]
        if not pdf_files:
            pytest.skip(f"No verified FRA PDF files found in {FRA_DIR}")

        return pdf_files

    def test_verified_fra_files_detected_by_content(self, detector, fra_pdf_files):
        """Test that all verified FRA files are detected as FRA_DOCUMENT by content analysis."""
        results = []

        for pdf_path in fra_pdf_files:
            with open(pdf_path, "rb") as f:
                content = f.read()

            detected_type = detector.detect_file_type(pdf_path.name, content)
            results.append({
                "file": pdf_path.name,
                "detected": detected_type,
                "expected": FileType.FRA_DOCUMENT,
                "correct": detected_type == FileType.FRA_DOCUMENT,
            })

        # Print results for debugging
        print("\n\nFRA Document Detection Results:")
        print("=" * 80)
        for r in results:
            status = "PASS" if r["correct"] else "FAIL"
            print(f"[{status}] {r['file']}: {r['detected'].value}")

        # All verified FRA files should be detected as FRA_DOCUMENT
        failed = [r for r in results if not r["correct"]]
        assert len(failed) == 0, f"Files incorrectly classified: {[f['file'] for f in failed]}"

    def test_fra_fire_risk_assessment_files(self, detector):
        """Test specific FRA files with 'fire risk assessment' in name."""
        fra_files = [
            "Scarfe-Way-38-48-Fire-Risk-Assessment.pdf",
            "The-Square-1-10-Fire-Risk-Assessment.pdf",
            "20210715fireriskassessmentsharwood.pdf",
            "20210715fireriskassessmentwoodstockhouse.pdf",
        ]

        for filename in fra_files:
            pdf_path = FRA_DIR / filename
            if not pdf_path.exists():
                continue

            with open(pdf_path, "rb") as f:
                content = f.read()

            detected_type = detector.detect_file_type(filename, content)
            assert detected_type == FileType.FRA_DOCUMENT, \
                f"{filename} should be FRA_DOCUMENT, got {detected_type.value}"


class TestFRAEWDocumentDifferentiation:
    """Tests that FRAEW documents are correctly identified as FRAEW_DOCUMENT."""

    @pytest.fixture
    def fraew_pdf_files(self):
        """Get list of verified FRAEW PDF files."""
        if not FRAEW_DIR.exists():
            pytest.skip(f"FRAEW data directory not found: {FRAEW_DIR}")

        pdf_files = [FRAEW_DIR / f for f in VERIFIED_FRAEW_FILES if (FRAEW_DIR / f).exists()]
        if not pdf_files:
            pytest.skip(f"No verified FRAEW PDF files found in {FRAEW_DIR}")

        return pdf_files

    def test_verified_fraew_files_detected_by_content(self, detector, fraew_pdf_files):
        """Test that all verified FRAEW files are detected as FRAEW_DOCUMENT by content analysis."""
        results = []

        for pdf_path in fraew_pdf_files:
            with open(pdf_path, "rb") as f:
                content = f.read()

            detected_type = detector.detect_file_type(pdf_path.name, content)
            results.append({
                "file": pdf_path.name,
                "detected": detected_type,
                "expected": FileType.FRAEW_DOCUMENT,
                "correct": detected_type == FileType.FRAEW_DOCUMENT,
            })

        # Print results for debugging
        print("\n\nFRAEW Document Detection Results:")
        print("=" * 80)
        for r in results:
            status = "PASS" if r["correct"] else "FAIL"
            print(f"[{status}] {r['file']}: {r['detected'].value}")

        # All verified FRAEW files should be detected as FRAEW_DOCUMENT
        failed = [r for r in results if not r["correct"]]
        assert len(failed) == 0, f"Files incorrectly classified: {[f['file'] for f in failed]}"

    def test_fraew_pas_9980_files(self, detector):
        """Test specific FRAEW files with PAS 9980 or FRAEW in name."""
        for filename in VERIFIED_FRAEW_FILES:
            pdf_path = FRAEW_DIR / filename
            if not pdf_path.exists():
                continue

            with open(pdf_path, "rb") as f:
                content = f.read()

            detected_type = detector.detect_file_type(filename, content)
            assert detected_type == FileType.FRAEW_DOCUMENT, \
                f"{filename} should be FRAEW_DOCUMENT, got {detected_type.value}"


class TestCrossValidation:
    """Cross-validation tests to ensure FRA and FRAEW don't get confused."""

    def test_no_verified_fra_files_detected_as_fraew(self, detector):
        """Ensure no verified FRA files are incorrectly detected as FRAEW."""
        if not FRA_DIR.exists():
            pytest.skip(f"FRA data directory not found: {FRA_DIR}")

        misclassified = []
        for filename in VERIFIED_FRA_FILES:
            pdf_path = FRA_DIR / filename
            if not pdf_path.exists():
                continue

            with open(pdf_path, "rb") as f:
                content = f.read()

            detected_type = detector.detect_file_type(pdf_path.name, content)
            if detected_type == FileType.FRAEW_DOCUMENT:
                misclassified.append(pdf_path.name)

        assert len(misclassified) == 0, \
            f"FRA files incorrectly classified as FRAEW: {misclassified}"

    def test_no_verified_fraew_files_detected_as_fra(self, detector):
        """Ensure no verified FRAEW files are incorrectly detected as FRA."""
        if not FRAEW_DIR.exists():
            pytest.skip(f"FRAEW data directory not found: {FRAEW_DIR}")

        misclassified = []
        for filename in VERIFIED_FRAEW_FILES:
            pdf_path = FRAEW_DIR / filename
            if not pdf_path.exists():
                continue

            with open(pdf_path, "rb") as f:
                content = f.read()

            detected_type = detector.detect_file_type(pdf_path.name, content)
            if detected_type == FileType.FRA_DOCUMENT:
                misclassified.append(pdf_path.name)

        assert len(misclassified) == 0, \
            f"FRAEW files incorrectly classified as FRA: {misclassified}"


class TestFeatureExtractionDifferentiation:
    """Tests that extracted features differ appropriately between FRA and FRAEW."""

    def test_fra_files_have_fra_specific_features(self):
        """Test that FRA files produce fra_specific features, not fraew_specific."""
        from backend.core.pdf_extraction.pdf_pipeline import build_pdf_artifacts

        if not FRA_DIR.exists():
            pytest.skip(f"FRA data directory not found: {FRA_DIR}")

        # Use Scarfe Way as test file
        test_file = FRA_DIR / "Scarfe-Way-38-48-Fire-Risk-Assessment.pdf"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        with open(test_file, "rb") as f:
            content = f.read()

        artifacts = build_pdf_artifacts(content, file_type="fra_document", filename=test_file.name)
        features = artifacts.features.get("features", {})

        assert "fra_specific" in features, "FRA document should have fra_specific features"
        assert "fraew_specific" not in features, "FRA document should NOT have fraew_specific features"

        # Verify FRA-specific fields
        fra = features["fra_specific"]
        assert "overall_risk_rating" in fra
        assert "evacuation_strategy" in fra
        assert "fso_compliant" in fra

    def test_fraew_files_have_fraew_specific_features(self):
        """Test that FRAEW files produce fraew_specific features, not fra_specific."""
        from backend.core.pdf_extraction.pdf_pipeline import build_pdf_artifacts

        if not FRAEW_DIR.exists():
            pytest.skip(f"FRAEW data directory not found: {FRAEW_DIR}")

        # Use Aura Court as test file
        test_file = FRAEW_DIR / "FRAEW-Report_Aura-Court.pdf"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        with open(test_file, "rb") as f:
            content = f.read()

        artifacts = build_pdf_artifacts(content, file_type="fraew_document", filename=test_file.name)
        features = artifacts.features.get("features", {})

        assert "fraew_specific" in features, "FRAEW document should have fraew_specific features"
        assert "fra_specific" not in features, "FRAEW document should NOT have fra_specific features"

        # Verify FRAEW-specific fields
        fraew = features["fraew_specific"]
        assert "pas_9980_compliant" in fraew
        assert "building_risk_rating" in fraew
        assert "wall_types" in fraew


class TestFilenameBasedDifferentiation:
    """Tests for filename-based detection (fallback when content is unclear)."""

    def test_fra_filenames_detected_correctly(self, detector):
        """Test that FRA-like filenames are detected as FRA_DOCUMENT."""
        fra_filenames = [
            "fire_risk_assessment_block_a.pdf",
            "fra_report_2024.pdf",
            "frsa_document_test.pdf",  # FRSA should map to FRA
            "fire_risk_safety_assessment.pdf",
            "Scarfe-Way-38-48-Fire-Risk-Assessment.pdf",  # Hyphenated version
            "20210715fireriskassessmentsharwood.pdf",  # Concatenated version
        ]

        for filename in fra_filenames:
            detected = detector.detect_file_type_from_filename(filename)
            assert detected == FileType.FRA_DOCUMENT, \
                f"{filename} should be FRA_DOCUMENT, got {detected.value}"

    def test_fraew_filenames_detected_correctly(self, detector):
        """Test that FRAEW-like filenames are detected as FRAEW_DOCUMENT."""
        fraew_filenames = [
            "fraew_report_2024.pdf",
            "pas_9980_assessment.pdf",
            "external_walls_appraisal.pdf",
            "fire_risk_appraisal_external_walls.pdf",
            "PAS-9980-Report.pdf",
        ]

        for filename in fraew_filenames:
            detected = detector.detect_file_type_from_filename(filename)
            assert detected == FileType.FRAEW_DOCUMENT, \
                f"{filename} should be FRAEW_DOCUMENT, got {detected.value}"

    def test_fraew_takes_priority_over_fra_in_filename(self, detector):
        """Test that FRAEW keywords take priority when filename has both."""
        # Files with both FRA and FRAEW indicators should be FRAEW
        ambiguous_filenames = [
            "fire_risk_assessment_external_walls.pdf",  # Has "external walls" -> FRAEW
            "fra_pas_9980_report.pdf",  # Has "pas 9980" -> FRAEW
        ]

        for filename in ambiguous_filenames:
            detected = detector.detect_file_type_from_filename(filename)
            assert detected == FileType.FRAEW_DOCUMENT, \
                f"{filename} should prioritize FRAEW, got {detected.value}"
