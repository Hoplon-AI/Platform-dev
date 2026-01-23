"""
TDD tests for unified batch upload endpoint.
"""
import pytest
import pandas as pd
import io
from fastapi.testclient import TestClient
from backend.main import app
from backend.api.ingestion.file_type_detector import FileType


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def create_csv_file(content: str, filename: str = "test.csv") -> io.BytesIO:
    """Helper to create a CSV file-like object."""
    file_obj = io.BytesIO(content.encode('utf-8'))
    file_obj.name = filename
    return file_obj


def create_property_schedule_csv() -> io.BytesIO:
    """Create a property schedule CSV."""
    content = """property_id,address,postcode,uprn
1,123 Test Street,SW1A 1AA,123456789012
2,456 Test Road,M1 1AA,123456789013"""
    return create_csv_file(content, "property_schedule.csv")


def create_epc_data_csv() -> io.BytesIO:
    """Create an EPC data CSV."""
    content = """uprn,epc_rating,epc_date
123456789012,A,2023-01-15
123456789013,B,2023-02-20"""
    return create_csv_file(content, "epc_data.csv")


@pytest.mark.asyncio
async def test_batch_upload_detects_property_schedule(client):
    """Test that batch upload detects property schedule files."""
    file_obj = create_property_schedule_csv()
    
    response = client.post(
        "/api/v1/upload/batch",
        files={"files": ("property_schedule.csv", file_obj, "text/csv")},
        data={"ha_id": "test_ha", "user_id": "test_user"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 1
    assert data["successful"] == 1
    assert data["failed"] == 0
    assert len(data["results"]) == 1
    assert data["results"][0]["file_type"] == "property_schedule"
    assert "upload_id" in data["results"][0]


@pytest.mark.asyncio
async def test_batch_upload_detects_epc_data(client):
    """Test that batch upload detects EPC data files."""
    file_obj = create_epc_data_csv()
    
    response = client.post(
        "/api/v1/upload/batch",
        files={"files": ("epc_data.csv", file_obj, "text/csv")},
        data={"ha_id": "test_ha", "user_id": "test_user"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 1
    assert data["successful"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["file_type"] == "epc_data"


@pytest.mark.asyncio
async def test_batch_upload_handles_multiple_files(client):
    """Test that batch upload handles multiple files with different types."""
    property_file = create_property_schedule_csv()
    epc_file = create_epc_data_csv()
    
    response = client.post(
        "/api/v1/upload/batch",
        files=[
            ("files", ("property_schedule.csv", property_file, "text/csv")),
            ("files", ("epc_data.csv", epc_file, "text/csv")),
        ],
        data={"ha_id": "test_ha", "user_id": "test_user"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 2
    assert data["successful"] == 2
    assert data["failed"] == 0
    assert len(data["results"]) == 2
    
    # Check that files were detected correctly
    file_types = {r["file_type"] for r in data["results"]}
    assert "property_schedule" in file_types
    assert "epc_data" in file_types


@pytest.mark.asyncio
async def test_batch_upload_handles_errors_gracefully(client):
    """Test that batch upload handles errors gracefully and continues processing."""
    # Create a valid file and an invalid one
    property_file = create_property_schedule_csv()
    invalid_file = io.BytesIO(b"not a valid csv")
    invalid_file.name = "invalid.txt"
    
    response = client.post(
        "/api/v1/upload/batch",
        files=[
            ("files", ("property_schedule.csv", property_file, "text/csv")),
            ("files", ("invalid.txt", invalid_file, "text/plain")),
        ],
        data={"ha_id": "test_ha", "user_id": "test_user"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 2
    assert data["successful"] == 1
    assert data["failed"] == 1
    assert len(data["results"]) == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["filename"] == "invalid.txt"


@pytest.mark.asyncio
async def test_batch_upload_detects_by_filename_pattern(client):
    """Test that batch upload uses filename patterns for detection."""
    # Create a file with EPC in filename but unclear content
    content = """id,value
1,100
2,200"""
    file_obj = create_csv_file(content, "epc_ratings_2024.csv")
    
    response = client.post(
        "/api/v1/upload/batch",
        files={"files": ("epc_ratings_2024.csv", file_obj, "text/csv")},
        data={"ha_id": "test_ha", "user_id": "test_user"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["successful"] == 1
    # Should detect as EPC based on filename
    assert data["results"][0]["file_type"] == "epc_data"


@pytest.mark.asyncio
async def test_batch_upload_detects_sov_files(client):
    """Test that batch upload detects SOV (Schedule of Values) files."""
    content = """property_id,address
1,123 Test St"""
    file_obj = create_csv_file(content, "property_sov_2024.csv")
    
    response = client.post(
        "/api/v1/upload/batch",
        files={"files": ("property_sov_2024.csv", file_obj, "text/csv")},
        data={"ha_id": "test_ha", "user_id": "test_user"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["successful"] == 1
    assert data["results"][0]["file_type"] == "property_schedule"


def create_pdf_file(filename: str) -> io.BytesIO:
    """Helper to create a PDF file-like object (minimal PDF header)."""
    # Minimal valid PDF header
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\nstartxref\n9\n%%EOF"
    file_obj = io.BytesIO(pdf_content)
    file_obj.name = filename
    return file_obj


@pytest.mark.asyncio
async def test_batch_upload_detects_fra_documents(client):
    """Test that batch upload detects FRA (Fire Risk Assessment) documents."""
    file_obj = create_pdf_file("fra_report_block_a.pdf")
    
    response = client.post(
        "/api/v1/upload/batch",
        files={"files": ("fra_report_block_a.pdf", file_obj, "application/pdf")},
        data={"ha_id": "test_ha", "user_id": "test_user"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["successful"] == 1
    assert data["results"][0]["file_type"] == "fra_document"


@pytest.mark.asyncio
async def test_batch_upload_detects_frsa_as_fra_documents(client):
    """Test that batch upload detects FRSA files as FRA documents (consolidated)."""
    file_obj = create_pdf_file("frsa_report_block_b.pdf")

    response = client.post(
        "/api/v1/upload/batch",
        files={"files": ("frsa_report_block_b.pdf", file_obj, "application/pdf")},
        data={"ha_id": "test_ha", "user_id": "test_user"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["successful"] == 1
    assert data["results"][0]["file_type"] == "fra_document"


@pytest.mark.asyncio
async def test_batch_upload_detects_fraew_documents(client):
    """Test that batch upload detects FRAEW (PAS 9980) documents."""
    file_obj = create_pdf_file("pas_9980_appraisal_block_c.pdf")
    
    response = client.post(
        "/api/v1/upload/batch",
        files={"files": ("pas_9980_appraisal_block_c.pdf", file_obj, "application/pdf")},
        data={"ha_id": "test_ha", "user_id": "test_user"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["successful"] == 1
    assert data["results"][0]["file_type"] == "fraew_document"


@pytest.mark.asyncio
async def test_batch_upload_detects_scr_documents(client):
    """Test that batch upload detects SCR (Safety Case Report) documents."""
    file_obj = create_pdf_file("safety_case_report_block_d.pdf")
    
    response = client.post(
        "/api/v1/upload/batch",
        files={"files": ("safety_case_report_block_d.pdf", file_obj, "application/pdf")},
        data={"ha_id": "test_ha", "user_id": "test_user"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["successful"] == 1
    assert data["results"][0]["file_type"] == "scr_document"


@pytest.mark.asyncio
async def test_batch_upload_detects_mixed_document_types(client):
    """Test that batch upload correctly detects multiple different document types."""
    property_file = create_property_schedule_csv()
    epc_file = create_epc_data_csv()
    fra_file = create_pdf_file("fra_report.pdf")
    fraew_file = create_pdf_file("pas_9980_appraisal.pdf")
    scr_file = create_pdf_file("safety_case_report.pdf")
    
    response = client.post(
        "/api/v1/upload/batch",
        files=[
            ("files", ("property_schedule.csv", property_file, "text/csv")),
            ("files", ("epc_data.csv", epc_file, "text/csv")),
            ("files", ("fra_report.pdf", fra_file, "application/pdf")),
            ("files", ("pas_9980_appraisal.pdf", fraew_file, "application/pdf")),
            ("files", ("safety_case_report.pdf", scr_file, "application/pdf")),
        ],
        data={"ha_id": "test_ha", "user_id": "test_user"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 5
    assert data["successful"] == 5
    assert data["failed"] == 0
    
    # Check that all types were detected correctly
    file_types = {r["file_type"] for r in data["results"]}
    assert "property_schedule" in file_types
    assert "epc_data" in file_types
    assert "fra_document" in file_types
    assert "fraew_document" in file_types
    assert "scr_document" in file_types
