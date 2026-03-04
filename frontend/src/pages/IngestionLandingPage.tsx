import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { apiFetch } from "../services/apiClient";

// Icons as inline SVGs
const Icons = {
  Upload: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  ),
  Clock: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  Home: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  ),
  FileText: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  ),
  Download: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  ),
  Check: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  AlertCircle: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  ),
  Zap: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  ),
  Shield: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  RefreshCw: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  ),
  BarChart: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  ),
  Link: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  ),
  ChevronRight: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  ),
};

type Submission = {
  upload_id: string;
  ha_id: string;
  filename: string;
  file_type: string;
  status: string;
  uploaded_at: string;
  file_size: number;
  checksum: string;
  metadata?: unknown;
};

type ListResponse = {
  items: Submission[];
};

type BatchUploadResponse = {
  total_files: number;
  successful: number;
  failed: number;
  results: Array<{
    upload_id: string;
    filename: string;
    file_type: string;
    s3_key: string;
    manifest_s3_key?: string | null;
    metadata_s3_key?: string | null;
    checksum: string;
    file_size: number;
  }>;
  errors: Array<{ filename: string; error: string; error_type?: string }>;
};

function formatDateTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function formatBytes(n: number) {
  if (!Number.isFinite(n)) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function getFileTypeLabel(fileType: string): string {
  const labels: Record<string, string> = {
    property_schedule: "Property Schedule",
    fra_document: "Fire Risk Assessment",
    fraew_document: "EWS1 / PAS 9980",
    scr_document: "Safety Case Report",
    epc_data: "EPC Data",
  };
  return labels[fileType] || fileType;
}

export function IngestionLandingPage() {
  const location = useLocation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<BatchUploadResponse | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const sorted = useMemo(() => {
    return [...items].sort(
      (a, b) => new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime()
    );
  }, [items]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/v1/upload/submissions?limit=50");
      const data = (await res.json()) as ListResponse;
      setItems(data.items ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadResult(null);
    setError(null);
    try {
      const form = new FormData();
      Array.from(files).forEach((f) => form.append("files", f));
      const res = await apiFetch("/api/v1/upload/batch", {
        method: "POST",
        body: form,
      });
      const data = (await res.json()) as BatchUploadResponse;
      setUploadResult(data);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  }

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        void onUpload(files);
      }
    },
    [onUpload]
  );

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const navLinks = [
    { path: "/", label: "Uploads", icon: Icons.Upload },
    { path: "/previous", label: "Previous Uploads", icon: Icons.Clock },
    { path: "/portfolio", label: "Portfolio Overview", icon: Icons.Home },
    { path: "/data-quality", label: "Data Quality", icon: Icons.FileText },
    { path: "/exports", label: "Exports", icon: Icons.Download },
  ];

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <Icons.Shield />
          EquiRisk
        </div>
        <nav className="sidebar-nav">
          <div className="sidebar-section">Navigation</div>
          {navLinks.map((link) => (
            <Link
              key={link.path}
              to={link.path}
              className={`sidebar-link ${location.pathname === link.path ? "active" : ""}`}
            >
              <link.icon />
              {link.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main className="main-content">
        {/* Header */}
        <header className="top-header">
          <span className="header-org">Example Housing Association - 2025 Renewal</span>
          <span className="header-badge">
            <Icons.Shield />
            Asset data only - GDPR compliant
          </span>
        </header>

        {/* Page content */}
        <div className="page-content">
          {/* Title */}
          <div className="page-title">
            <h1>Upload Your Portfolio Data</h1>
            <div className="subtitle">Premium Intelligence</div>
            <p className="description">
              Get your insurance submission ready in three simple steps
            </p>
          </div>

          {/* Steps */}
          <div className="steps-container">
            <div className="step">
              <div className="step-number active">1</div>
              <div className="step-title">Upload SoV</div>
              <div className="step-desc">
                Drop your Schedule of Values and supporting documents
              </div>
            </div>
            <div className="step">
              <div className="step-number inactive">2</div>
              <div className="step-title">Portfolio Overview</div>
              <div className="step-desc">See your readiness score and TIV summary</div>
            </div>
            <div className="step">
              <div className="step-number inactive">3</div>
              <div className="step-title">Data Quality</div>
              <div className="step-desc">Review gaps and add missing documentation</div>
            </div>
          </div>

          {/* Upload zone */}
          <div
            className={`upload-zone ${dragOver ? "dragover" : ""} ${uploading ? "uploading" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={handleBrowseClick}
          >
            <div className="upload-icon-prominent">
              <Icons.Upload />
            </div>
            <h3>Drag & drop your files here</h3>
            <p>or click to browse from your computer</p>
            <div className="upload-formats">Supported: Excel (.xlsx, .xls), CSV, PDF, DOCX, ZIP</div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              style={{ display: "none" }}
              onChange={(e) => void onUpload(e.target.files)}
              accept=".xlsx,.xls,.csv,.pdf,.docx,.zip"
            />
          </div>

          {/* Upload progress/result */}
          {uploading && (
            <div className="upload-result">
              <h4>Uploading...</h4>
              <p>Please wait while your files are being uploaded.</p>
            </div>
          )}

          {uploadResult && !uploading && (
            <div className={`upload-result ${uploadResult.failed > 0 ? "error" : ""}`}>
              <h4>
                {uploadResult.failed === 0
                  ? "Upload Complete"
                  : `Upload completed with ${uploadResult.failed} error(s)`}
              </h4>
              <p>
                Successfully uploaded {uploadResult.successful} of {uploadResult.total_files}{" "}
                file(s).
              </p>
              {uploadResult.errors?.length > 0 && (
                <ul>
                  {uploadResult.errors.map((err, idx) => (
                    <li key={idx}>
                      {err.filename}: {err.error}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {error && (
            <div className="upload-result error">
              <h4>Error</h4>
              <p>{error}</p>
            </div>
          )}

          {/* Info box */}
          <div className="info-box-yellow">
            <div className="info-box-header">
              What to upload for best results
            </div>
            <div className="info-box-grid">
              <div className="info-item">
                <Icons.FileText />
                Schedule of Values (SoV) <span className="required">Required</span>
              </div>
              <div className="info-item">
                <Icons.FileText />
                Fire Risk Assessments (FRAs)
              </div>
              <div className="info-item muted">
                <Icons.FileText />
                EICR Certificates <span className="coming-soon">Coming soon</span>
              </div>
              <div className="info-item">
                <Icons.FileText />
                EWS1 / PAS 9980 reports
              </div>
              <div className="info-item muted">
                <Icons.FileText />
                Gas Safety Certificates <span className="coming-soon">Coming soon</span>
              </div>
              <div className="info-item muted">
                <Icons.FileText />
                Asbestos Register <span className="coming-soon">Coming soon</span>
              </div>
            </div>
          </div>

          {/* Integration box */}
          <div className="integration-box">
            <div className="integration-icon">
              <Icons.Link />
            </div>
            <div className="integration-content">
              <h4>Connect Your Asset Management System</h4>
              <p>
                Reduce manual uploads by connecting directly to your AMS. We support Civica CX,
                NEC Housing, MRI Software, and others. Our team will work with your IT to set
                up a secure connection.
              </p>
            </div>
            <button className="btn-outline">
              Request Integration
              <Icons.ChevronRight />
            </button>
          </div>

          {/* Feature cards */}
          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon green">
                <Icons.Zap />
              </div>
              <h4>Smart Ingestion</h4>
              <ul className="feature-list">
                <li>
                  <Icons.Check />
                  Address normalisation
                </li>
                <li>
                  <Icons.Check />
                  UPRN verification
                </li>
                <li>
                  <Icons.Check />
                  AI document extraction
                </li>
              </ul>
            </div>
            <div className="feature-card">
              <div className="feature-icon blue">
                <Icons.Shield />
              </div>
              <h4>Data Quality Checks</h4>
              <ul className="feature-list">
                <li>
                  <Icons.Check />
                  Coverage by domain
                </li>
                <li>
                  <Icons.Check />
                  Missing document flags
                </li>
                <li>
                  <Icons.Check />
                  Policy impact warnings
                </li>
              </ul>
            </div>
            <div className="feature-card">
              <div className="feature-icon purple">
                <Icons.RefreshCw />
              </div>
              <h4>Fast Processing</h4>
              <ul className="feature-list">
                <li>
                  <Icons.Check />
                  Real-time progress
                </li>
                <li>
                  <Icons.Check />
                  Instant overview
                </li>
              </ul>
            </div>
          </div>

          {/* Recent submissions */}
          {sorted.length > 0 && (
            <div className="submissions-section">
              <div className="submissions-header">
                <h3>Recent Uploads</h3>
                <button className="btn btn-secondary" onClick={refresh} disabled={loading}>
                  {loading ? <div className="spinner" /> : <Icons.RefreshCw />}
                  Refresh
                </button>
              </div>
              {sorted.slice(0, 5).map((s) => (
                <div key={s.upload_id} className="submission-card">
                  <div className="submission-info">
                    <h4>{s.filename}</h4>
                    <div className="submission-meta">
                      <span>{getFileTypeLabel(s.file_type)}</span>
                      <span>{formatBytes(s.file_size)}</span>
                      <span className={`status-badge ${s.status}`}>{s.status}</span>
                    </div>
                  </div>
                  <div className="submission-time">{formatDateTime(s.uploaded_at)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
