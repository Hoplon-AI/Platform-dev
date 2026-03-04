import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { IngestionLandingPage } from "./IngestionLandingPage";

// Mock the apiClient module
vi.mock("../services/apiClient", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "../services/apiClient";
const mockApiFetch = vi.mocked(apiFetch);

function renderWithRouter(component: React.ReactNode) {
  return render(<BrowserRouter>{component}</BrowserRouter>);
}

describe("IngestionLandingPage", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the page title", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    expect(screen.getByText("Upload Your Portfolio Data")).toBeInTheDocument();
    expect(screen.getByText("Premium Intelligence")).toBeInTheDocument();
  });

  it("renders the sidebar navigation", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    expect(screen.getByText("EquiRisk")).toBeInTheDocument();
    expect(screen.getByText("Uploads")).toBeInTheDocument();
    expect(screen.getByText("Previous Uploads")).toBeInTheDocument();
    // These appear in both sidebar nav and step descriptions
    expect(screen.getAllByText("Portfolio Overview").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Data Quality").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Exports")).toBeInTheDocument();
  });

  it("renders the three-step process", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    expect(screen.getByText("Upload SoV")).toBeInTheDocument();
    // Portfolio Overview and Data Quality appear in both nav and steps
    expect(screen.getAllByText("Portfolio Overview").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Data Quality").length).toBeGreaterThanOrEqual(2);
  });

  it("renders the upload zone", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    expect(screen.getByText("Drag & drop your files here")).toBeInTheDocument();
    expect(screen.getByText("or click to browse from your computer")).toBeInTheDocument();
    expect(screen.getByText("Supported: Excel (.xlsx, .xls), CSV, PDF, DOCX, ZIP")).toBeInTheDocument();
  });

  it("renders the info box with required documents", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    expect(screen.getByText("What to upload for best results")).toBeInTheDocument();
    // Use getAllByText since "Schedule of Values" may appear multiple times
    expect(screen.getAllByText(/Schedule of Values/).length).toBeGreaterThan(0);
    expect(screen.getByText("Required")).toBeInTheDocument();
    expect(screen.getByText("Fire Risk Assessments (FRAs)")).toBeInTheDocument();
    expect(screen.getByText("EWS1 / PAS 9980 reports")).toBeInTheDocument();
    // Coming soon items
    expect(screen.getAllByText("Coming soon")).toHaveLength(3);
  });

  it("renders the integration box", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    expect(screen.getByText("Connect Your Asset Management System")).toBeInTheDocument();
    expect(screen.getByText("Request Integration")).toBeInTheDocument();
  });

  it("renders the feature cards", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    expect(screen.getByText("Smart Ingestion")).toBeInTheDocument();
    expect(screen.getByText("Data Quality Checks")).toBeInTheDocument();
    expect(screen.getByText("Fast Processing")).toBeInTheDocument();
    expect(screen.getByText("Address normalisation")).toBeInTheDocument();
    expect(screen.getByText("UPRN verification")).toBeInTheDocument();
    expect(screen.getByText("AI document extraction")).toBeInTheDocument();
  });

  it("fetches submissions on mount", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    await waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith("/api/v1/upload/submissions?limit=50");
    });
  });

  it("displays recent uploads when submissions exist", async () => {
    const mockSubmissions = {
      items: [
        {
          upload_id: "1",
          ha_id: "ha-1",
          filename: "test-schedule.xlsx",
          file_type: "property_schedule",
          status: "completed",
          uploaded_at: "2025-01-26T12:00:00Z",
          file_size: 1024000,
          checksum: "abc123",
        },
        {
          upload_id: "2",
          ha_id: "ha-1",
          filename: "fra-report.pdf",
          file_type: "fra_document",
          status: "processing",
          uploaded_at: "2025-01-26T11:00:00Z",
          file_size: 512000,
          checksum: "def456",
        },
      ],
    };

    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve(mockSubmissions),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    await waitFor(() => {
      expect(screen.getByText("Recent Uploads")).toBeInTheDocument();
    });

    expect(screen.getByText("test-schedule.xlsx")).toBeInTheDocument();
    expect(screen.getByText("fra-report.pdf")).toBeInTheDocument();
    expect(screen.getByText("Property Schedule")).toBeInTheDocument();
    expect(screen.getByText("Fire Risk Assessment")).toBeInTheDocument();
  });

  it("shows uploading state during file upload", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    // Mock for the upload - never resolves to keep uploading state
    let resolveUpload: (value: Response) => void;
    const uploadPromise = new Promise<Response>((resolve) => {
      resolveUpload = resolve;
    });
    mockApiFetch.mockReturnValueOnce(uploadPromise);

    renderWithRouter(<IngestionLandingPage />);

    await waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledTimes(1);
    });

    // Simulate file drop
    const uploadZone = screen.getByText("Drag & drop your files here").closest(".upload-zone");
    expect(uploadZone).toBeInTheDocument();

    const file = new File(["test content"], "test.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    const dataTransfer = {
      files: [file],
    };

    fireEvent.drop(uploadZone!, { dataTransfer });

    await waitFor(() => {
      expect(screen.getByText("Uploading...")).toBeInTheDocument();
    });

    // Resolve the upload to clean up
    resolveUpload!({
      json: () =>
        Promise.resolve({
          total_files: 1,
          successful: 1,
          failed: 0,
          results: [],
          errors: [],
        }),
    } as Response);
  });

  it("displays upload result after successful upload", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    const uploadResponse = {
      total_files: 2,
      successful: 2,
      failed: 0,
      results: [
        { upload_id: "1", filename: "file1.xlsx", file_type: "property_schedule" },
        { upload_id: "2", filename: "file2.pdf", file_type: "fra_document" },
      ],
      errors: [],
    };

    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve(uploadResponse),
    } as Response);

    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    await waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledTimes(1);
    });

    const uploadZone = screen.getByText("Drag & drop your files here").closest(".upload-zone");

    const file = new File(["test content"], "test.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    fireEvent.drop(uploadZone!, { dataTransfer: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText("Upload Complete")).toBeInTheDocument();
    });

    expect(screen.getByText(/Successfully uploaded 2 of 2/)).toBeInTheDocument();
  });

  it("displays errors when upload fails", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    const uploadResponse = {
      total_files: 2,
      successful: 1,
      failed: 1,
      results: [{ upload_id: "1", filename: "file1.xlsx", file_type: "property_schedule" }],
      errors: [{ filename: "file2.pdf", error: "Invalid file format" }],
    };

    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve(uploadResponse),
    } as Response);

    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    await waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledTimes(1);
    });

    const uploadZone = screen.getByText("Drag & drop your files here").closest(".upload-zone");

    const file = new File(["test"], "test.xlsx", { type: "application/octet-stream" });

    fireEvent.drop(uploadZone!, { dataTransfer: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/Upload completed with 1 error/)).toBeInTheDocument();
    });

    expect(screen.getByText(/file2.pdf: Invalid file format/)).toBeInTheDocument();
  });

  it("shows error message when API fetch fails", async () => {
    mockApiFetch.mockRejectedValueOnce(new Error("Network error"));

    renderWithRouter(<IngestionLandingPage />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("handles drag over state", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    const uploadZone = screen.getByText("Drag & drop your files here").closest(".upload-zone");
    expect(uploadZone).not.toHaveClass("dragover");

    fireEvent.dragOver(uploadZone!);
    expect(uploadZone).toHaveClass("dragover");

    fireEvent.dragLeave(uploadZone!);
    expect(uploadZone).not.toHaveClass("dragover");
  });

  it("refreshes submissions when refresh button is clicked", async () => {
    const initialSubmissions = {
      items: [
        {
          upload_id: "1",
          ha_id: "ha-1",
          filename: "initial.xlsx",
          file_type: "property_schedule",
          status: "completed",
          uploaded_at: "2025-01-26T12:00:00Z",
          file_size: 1024,
          checksum: "abc",
        },
      ],
    };

    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve(initialSubmissions),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    await waitFor(() => {
      expect(screen.getByText("initial.xlsx")).toBeInTheDocument();
    });

    const updatedSubmissions = {
      items: [
        ...initialSubmissions.items,
        {
          upload_id: "2",
          ha_id: "ha-1",
          filename: "new-file.xlsx",
          file_type: "property_schedule",
          status: "queued",
          uploaded_at: "2025-01-26T13:00:00Z",
          file_size: 2048,
          checksum: "def",
        },
      ],
    };

    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve(updatedSubmissions),
    } as Response);

    const refreshButton = screen.getByText("Refresh");
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(screen.getByText("new-file.xlsx")).toBeInTheDocument();
    });
  });

  it("renders GDPR badge in header", async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ items: [] }),
    } as Response);

    renderWithRouter(<IngestionLandingPage />);

    expect(screen.getByText("Asset data only - GDPR compliant")).toBeInTheDocument();
  });
});
