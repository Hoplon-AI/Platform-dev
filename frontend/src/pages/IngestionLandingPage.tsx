import React, { useMemo, useRef, useState } from "react";

type IngestionStep = {
  key: string;
  label: string;
  state: "pending" | "active" | "complete";
};

type IngestionStats = {
  properties?: number | string;
  totalValue?: number | string;
  dataPassed?: number | string;
  missingCore?: number | string;
};

type IngestionLandingPageProps = {
  accountName?: string;
  renewalLabel?: string;
  isProcessing?: boolean;
  processingTitle?: string;
  processingStepLabel?: string;
  steps?: IngestionStep[];
  stats?: IngestionStats;
  onFilesSelected?: (files: File[]) => void;
  onDownloadTemplate?: () => void;
  onRequestIntegration?: () => void;
};

const defaultSteps: IngestionStep[] = [
  { key: "validating", label: "Validating", state: "complete" },
  { key: "verifying", label: "Verifying UPRN", state: "active" },
  { key: "cleansing", label: "Cleansing", state: "pending" },
  { key: "normalising", label: "Normalising", state: "pending" },
  { key: "complete", label: "Complete", state: "pending" },
];

const fmtStat = (value?: number | string) => {
  if (value === undefined || value === null || value === "") return "---";
  if (typeof value === "number") return value.toLocaleString("en-GB");
  return value;
};

const fmtMoney = (value?: number | string) => {
  if (value === undefined || value === null || value === "") return "---";
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  return `£${num.toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;
};

function IconUpload() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M7 16a4 4 0 0 1-.88-7.903A5 5 0 1 1 15.9 6L16 6a5 5 0 0 1 1 9.9" />
      <path d="M12 12v9" />
      <path d="m9 15 3-3 3 3" />
    </svg>
  );
}

function IconDownload() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 3v12" />
      <path d="m7 10 5 5 5-5" />
      <path d="M5 21h14" />
    </svg>
  );
}

function IconDoc() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M9 13h6" />
      <path d="M9 17h6" />
    </svg>
  );
}

function IconInfo() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 10v6" />
      <path d="M12 7h.01" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m5 13 4 4L19 7" />
    </svg>
  );
}

function IconShield() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 3s6 2 8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6c2-1 8-3 8-3Z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function IconBolt() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />
    </svg>
  );
}

function IconClock() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 3" />
    </svg>
  );
}

function IconDatabase() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <ellipse cx="12" cy="5" rx="7" ry="3" />
      <path d="M5 5v6c0 1.657 3.134 3 7 3s7-1.343 7-3V5" />
      <path d="M5 11v8c0 1.657 3.134 3 7 3s7-1.343 7-3v-8" />
    </svg>
  );
}

function IconArrowRight() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M5 12h14" />
      <path d="m13 5 7 7-7 7" />
    </svg>
  );
}

function LogoMark() {
  return (
    <svg viewBox="0 0 40 40" fill="none">
      <path d="M20 8L32 16L20 20L8 16L20 8Z" fill="#c41e3a" />
      <path d="M20 14L32 22L20 26L8 22L20 14Z" fill="#d64456" />
      <path d="M20 20L32 28L20 32L8 28L20 20Z" fill="#e85a6b" />
    </svg>
  );
}

export default function IngestionLandingPage({
  accountName = "Example Housing Association",
  renewalLabel = "2025 Renewal",
  isProcessing = false,
  processingTitle = "Processing your files...",
  processingStepLabel = "Step 2 of 5",
  steps = defaultSteps,
  stats,
  onFilesSelected,
  onDownloadTemplate,
  onRequestIntegration,
}: IngestionLandingPageProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const activeJourneyIndex = useMemo(() => {
    return isProcessing ? 1 : 0;
  }, [isProcessing]);

  const handleFiles = (files: FileList | File[] | null) => {
    if (!files || files.length === 0) return;
    onFilesSelected?.(Array.from(files));
  };

  const browseFiles = () => {
    fileInputRef.current?.click();
  };

  return (
    <div style={styles.page}>
      <style>{css}</style>

      <div className="ingestion-shell">
        <aside className="ingestion-sidebar">
          <div className="brand-row">
            <div className="brand-mark">
              <LogoMark />
            </div>
            <div className="brand-text">EquiRisk</div>
          </div>

          <div className="nav-label">Navigation</div>

          <button className="nav-item active" type="button">
            <IconUpload />
            <span>Uploads</span>
          </button>

          <button className="nav-item" type="button">
            <IconClock />
            <span>Previous Uploads</span>
          </button>

          <button className="nav-item" type="button">
            <IconDatabase />
            <span>Portfolio Overview</span>
          </button>

          <button className="nav-item" type="button">
            <IconCheck />
            <span>Data Quality</span>
          </button>

          <button className="nav-item" type="button">
            <IconDownload />
            <span>Exports</span>
          </button>

          <div className="sidebar-footer">
            <button className="settings-btn" type="button">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 0 0 2.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 0 0 1.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 0 0-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 0 0-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 0 0-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 0 0-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 0 0 1.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065Z" />
                <path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
              </svg>
            </button>
          </div>
        </aside>

        <main className="ingestion-main">
          <div className="top-bar">
            <div className="top-bar-left">
              <strong>{accountName}</strong>
              <span>•</span>
              <span>{renewalLabel}</span>
            </div>

            <div className="gdpr-badge">
              <IconShield />
              <span>Asset data only • GDPR compliant</span>
            </div>
          </div>

          <div className="page-header">
            <h1>Upload Your Portfolio Data</h1>
            <div className="strapline">Premium Intelligence</div>
            <p>Get your insurance submission ready in three simple steps</p>
          </div>

          <div className="journey-steps">
            {[
              {
                title: "Upload SoV",
                description: "Drop your Schedule of Values and supporting documents",
              },
              {
                title: "Portfolio Overview",
                description: "See your readiness score and TIV summary",
              },
              {
                title: "Data Quality",
                description: "Review gaps and add missing documentation",
              },
            ].map((item, idx) => {
              const state =
                idx < activeJourneyIndex
                  ? "complete"
                  : idx === activeJourneyIndex
                  ? "active"
                  : "pending";

              return (
                <div className="journey-step" key={item.title}>
                  <div className={`step-number ${state}`}>
                    {state === "complete" ? "✓" : idx + 1}
                  </div>
                  <div className="step-title">{item.title}</div>
                  <div className="step-description">{item.description}</div>
                  {idx < 2 ? <div className={`step-line ${idx < activeJourneyIndex ? "active" : ""}`} /> : null}
                </div>
              );
            })}
          </div>

          <div className="upload-card">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              style={{ display: "none" }}
              onChange={(e) => handleFiles(e.target.files)}
            />

            <div
              className={`upload-zone ${isDragOver ? "dragover" : ""}`}
              onClick={browseFiles}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragOver(false);
                handleFiles(e.dataTransfer.files);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") browseFiles();
              }}
            >
              <div className="upload-icon">
                <IconUpload />
              </div>

              <div className="upload-title">Drag &amp; drop your files here</div>
              <div className="upload-subtitle">or click to browse from your computer</div>

              <div className="upload-actions">
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    browseFiles();
                  }}
                >
                  <IconUpload />
                  Browse Files
                </button>

                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDownloadTemplate?.();
                  }}
                >
                  <IconDownload />
                  Download Template
                </button>
              </div>

              <div className="upload-formats">
                Supported: Excel (.xlsx, .xls), CSV, PDF, DOCX, ZIP
              </div>
            </div>

            <div className="what-to-upload">
              <div className="what-to-upload-title">
                <IconInfo />
                <span>What to upload for best results</span>
              </div>

              <div className="upload-items">
                <div className="upload-item">
                  <IconDoc />
                  <span>
                    Schedule of Values (SoV) <span className="required">REQUIRED</span>
                  </span>
                </div>
                <div className="upload-item">
                  <IconDoc />
                  <span>Fire Risk Assessments (FRAs)</span>
                </div>
                <div className="upload-item">
                  <IconDoc />
                  <span>EICR Certificates</span>
                </div>
                <div className="upload-item">
                  <IconDoc />
                  <span>EWS1 / PAS 9980 reports</span>
                </div>
                <div className="upload-item">
                  <IconDoc />
                  <span>Gas Safety Certificates</span>
                </div>
                <div className="upload-item">
                  <IconDoc />
                  <span>Asbestos Register</span>
                </div>
              </div>
            </div>
          </div>

          <div className="ams-card">
            <div className="ams-icon">
              <IconDatabase />
            </div>

            <div className="ams-copy">
              <div className="ams-title">Connect Your Asset Management System</div>
              <div className="ams-description">
                Reduce manual uploads by connecting directly to your AMS. We support Civica
                CX, NEC Housing, MRI Software, and others. Our team will work with your IT
                to set up a secure connection.
              </div>
            </div>

            <button className="btn btn-ams" type="button" onClick={onRequestIntegration}>
              Request Integration
              <IconArrowRight />
            </button>
          </div>

          <div className="info-cards">
            <div className="info-card">
              <div className="info-icon blue">
                <IconBolt />
              </div>
              <div className="info-title">Smart Ingestion</div>
              <ul>
                <li><IconCheck /> Address normalisation</li>
                <li><IconCheck /> UPRN verification</li>
                <li><IconCheck /> AI document extraction</li>
              </ul>
            </div>

            <div className="info-card">
              <div className="info-icon green">
                <IconShield />
              </div>
              <div className="info-title">Data Quality Checks</div>
              <ul>
                <li><IconCheck /> Coverage by domain</li>
                <li><IconCheck /> Missing document flags</li>
                <li><IconCheck /> Policy impact warnings</li>
              </ul>
            </div>

            <div className="info-card">
              <div className="info-icon purple">
                <IconClock />
              </div>
              <div className="info-title">Fast Processing</div>
              <ul>
                <li><IconCheck /> 2-5 mins for 1,000 units</li>
                <li><IconCheck /> Real-time progress</li>
                <li><IconCheck /> Instant overview</li>
              </ul>
            </div>
          </div>

          {isProcessing ? (
            <div className="ingestion-progress">
              <div className="ingestion-progress-header">
                <div className="ingestion-progress-title">
                  <span className="status-dot" />
                  {processingTitle}
                </div>
                <div className="ingestion-progress-step">{processingStepLabel}</div>
              </div>

              <div className="mini-steps">
                {steps.map((step) => (
                  <div key={step.key} className={`mini-step ${step.state}`}>
                    {step.label}
                  </div>
                ))}
              </div>

              <div className="progress-stats">
                <div className="progress-stat">
                  <div className="progress-stat-value">{fmtStat(stats?.properties)}</div>
                  <div className="progress-stat-label">Properties</div>
                </div>
                <div className="progress-stat">
                  <div className="progress-stat-value">{fmtMoney(stats?.totalValue)}</div>
                  <div className="progress-stat-label">Total Value</div>
                </div>
                <div className="progress-stat">
                  <div className="progress-stat-value">{fmtStat(stats?.dataPassed)}</div>
                  <div className="progress-stat-label">Data Passed</div>
                </div>
                <div className="progress-stat">
                  <div className="progress-stat-value">{fmtStat(stats?.missingCore)}</div>
                  <div className="progress-stat-label">Missing Core</div>
                </div>
              </div>

              <div className="progress-note">
                <IconBolt />
                Typical ingestion: <strong>2-5 minutes</strong> for portfolios under 1,000 units
              </div>
            </div>
          ) : null}
        </main>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "#f9fafb",
  },
};

const css = `
  * { box-sizing: border-box; }

  .ingestion-shell {
    display: flex;
    min-height: 100vh;
    font-family: Inter, "DM Sans", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    color: #1f2937;
    background: #f9fafb;
  }

  .ingestion-sidebar {
    width: 220px;
    background: #ffffff;
    border-right: 1px solid #e5e7eb;
    padding: 20px 0;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }

  .brand-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 20px;
    margin-bottom: 28px;
  }

  .brand-mark {
    width: 34px;
    height: 34px;
  }

  .brand-mark svg {
    width: 34px;
    height: 34px;
    display: block;
  }

  .brand-text {
    font-weight: 700;
    font-size: 18px;
    color: #1a2b4a;
    letter-spacing: -0.5px;
  }

  .nav-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #9ca3af;
    padding: 0 20px;
    margin-bottom: 8px;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 20px;
    border: 0;
    background: transparent;
    color: #4b5563;
    font-size: 14px;
    font-weight: 500;
    text-align: left;
    cursor: pointer;
  }

  .nav-item:hover {
    background: #f9fafb;
    color: #111827;
  }

  .nav-item.active {
    background: #e8f0fe;
    color: #1a56db;
    border-right: 3px solid #1a56db;
  }

  .nav-item svg,
  .settings-btn svg,
  .gdpr-badge svg,
  .upload-icon svg,
  .btn svg,
  .what-to-upload-title svg,
  .upload-item svg,
  .ams-icon svg,
  .info-icon svg,
  .info-card li svg,
  .progress-note svg {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
  }

  .sidebar-footer {
    margin-top: auto;
    padding: 16px 20px;
  }

  .settings-btn {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    border: 0;
    background: #f3f4f6;
    color: #6b7280;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .settings-btn:hover {
    background: #e5e7eb;
  }

  .ingestion-main {
  flex: 1;
  padding: 0 28px 40px;
  overflow-y: auto;
  margin-top: -120px;
}

  .top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
  }

  .top-bar-left {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #4b5563;
  }

  .top-bar-left strong {
    color: #111827;
  }

  .gdpr-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    background: #d1fae5;
    border: 1px solid #10b981;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    color: #10b981;
  }

 .page-header {
  text-align: center;
  margin-bottom: 22px;
}

  .page-header h1 {
    margin: 0 0 4px;
    font-size: 28px;
    font-weight: 800;
    color: #111827;
    letter-spacing: -0.02em;
  }

  .strapline {
    font-size: 14px;
    font-weight: 600;
    color: #1a56db;
    letter-spacing: 0.4px;
    margin-bottom: 8px;
  }

  .page-header p {
    margin: 0 auto;
    max-width: 500px;
    font-size: 16px;
    color: #6b7280;
  }

.journey-steps {

  display: flex;

  justify-content: center;

  align-items: flex-start;

  gap: 24px;

  margin: 0 auto 28px;

  max-width: 860px;

  padding: 0 20px;

}

  .journey-step {
    position: relative;
    flex: 1;
    max-width: 220px;
    text-align: center;
  }

  .step-number {
    width: 48px;
    height: 48px;
    margin: 0 auto 12px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 800;
    position: relative;
    z-index: 2;
  }

  .step-number.active {
    background: #1a56db;
    color: #fff;
  }

  .step-number.pending {
    background: #e5e7eb;
    color: #6b7280;
  }

  .step-number.complete {
    background: #10b981;
    color: #fff;
  }

  .step-title {
    font-size: 14px;
    font-weight: 700;
    color: #1f2937;
    margin-bottom: 4px;
  }

  .step-description {
    font-size: 12px;
    line-height: 1.4;
    color: #6b7280;
  }

  .step-line {
    position: absolute;
    top: 24px;
    left: calc(50% + 40px);
    width: calc(100% - 28px);
    height: 2px;
    background: #e5e7eb;
    z-index: 1;
  }

  .step-line.active {
    background: #1a56db;
  }

  .upload-card {
    background: #fff;
    border: 2px solid #1a56db;
    border-radius: 16px;
    box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.08);
    padding: 40px;
    max-width: 700px;
    margin: 0 auto 32px;
  }

  .upload-zone {
    border: 2px dashed #d1d5db;
    border-radius: 12px;
    background: #f9fafb;
    padding: 48px 32px;
    text-align: center;
    transition: 0.2s ease;
    cursor: pointer;
  }

  .upload-zone:hover,
  .upload-zone.dragover {
    border-color: #1a56db;
    background: #e8f0fe;
  }

  .upload-icon {
    width: 64px;
    height: 64px;
    margin: 0 auto 16px;
    border-radius: 16px;
    background: #e8f0fe;
    color: #1a56db;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .upload-icon svg {
    width: 32px;
    height: 32px;
  }

  .upload-title {
    font-size: 18px;
    font-weight: 700;
    color: #1f2937;
    margin-bottom: 8px;
  }

  .upload-subtitle {
    font-size: 14px;
    color: #6b7280;
    margin-bottom: 20px;
  }

  .upload-actions {
    display: flex;
    justify-content: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .btn {
    border: 0;
    border-radius: 8px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    transition: 0.15s ease;
  }

  .btn-primary {
    background: #1a56db;
    color: #fff;
  }

  .btn-primary:hover {
    background: #1e40af;
  }

  .btn-secondary {
    background: #fff;
    color: #1a56db;
    border: 1px solid #1a56db;
  }

  .btn-secondary:hover {
    background: #e8f0fe;
  }

  .upload-formats {
    margin-top: 20px;
    font-size: 12px;
    color: #9ca3af;
  }

  .what-to-upload {
    margin-top: 24px;
    background: #fef3c7;
    border: 1px solid #f59e0b;
    border-radius: 10px;
    padding: 20px 24px;
  }

  .what-to-upload-title {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #d97706;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 12px;
  }

  .upload-items {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 24px;
  }

  .upload-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #374151;
  }

  .upload-item svg {
    color: #d97706;
    width: 16px;
    height: 16px;
  }

  .required {
    font-size: 10px;
    font-weight: 800;
    color: #ef4444;
    margin-left: 4px;
  }

  .ams-card {
    max-width: 700px;
    margin: 0 auto 32px;
    padding: 20px 24px;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    background: #fff;
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .ams-icon {
    width: 48px;
    height: 48px;
    border-radius: 10px;
    background: #e0e7ff;
    color: #6366f1;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .ams-copy {
    flex: 1;
  }

  .ams-title {
    font-size: 15px;
    font-weight: 700;
    color: #111827;
    margin-bottom: 4px;
  }

  .ams-description {
    font-size: 13px;
    color: #6b7280;
    line-height: 1.5;
  }

  .btn-ams {
    background: #fff;
    color: #6366f1;
    border: 1px solid #6366f1;
    white-space: nowrap;
  }

  .btn-ams:hover {
    background: #6366f1;
    color: #fff;
  }

  .info-cards {
    max-width: 900px;
    margin: 0 auto 32px;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 20px;
  }

  .info-card {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 24px;
  }

  .info-icon {
    width: 44px;
    height: 44px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 16px;
  }

  .info-icon.blue {
    background: #e8f0fe;
    color: #1a56db;
  }

  .info-icon.green {
    background: #d1fae5;
    color: #10b981;
  }

  .info-icon.purple {
    background: #e0e7ff;
    color: #6366f1;
  }

  .info-title {
    font-size: 15px;
    font-weight: 700;
    color: #111827;
    margin-bottom: 8px;
  }

  .info-card ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .info-card li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    font-size: 13px;
    color: #4b5563;
  }

  .info-card li svg {
    width: 14px;
    height: 14px;
    color: #10b981;
  }

  .ingestion-progress {
    max-width: 700px;
    margin: 0 auto;
    padding: 24px;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
  }

  .ingestion-progress-header {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;
    align-items: center;
  }

  .ingestion-progress-title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 16px;
    font-weight: 700;
    color: #1f2937;
  }

  .status-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: #f59e0b;
    display: inline-block;
    animation: pulse 1.5s infinite;
  }

  .ingestion-progress-step {
    font-size: 13px;
    font-weight: 600;
    color: #4b5563;
  }

  .mini-steps {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }

  .mini-step {
    font-size: 11px;
    color: #9ca3af;
    position: relative;
    padding-left: 16px;
  }

  .mini-step::before {
    content: "";
    position: absolute;
    left: 0;
    top: 4px;
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: #d1d5db;
  }

  .mini-step.active {
    color: #1a56db;
    font-weight: 700;
  }

  .mini-step.active::before {
    background: #1a56db;
  }

  .mini-step.complete {
    color: #10b981;
    font-weight: 700;
  }

  .mini-step.complete::before {
    background: #10b981;
  }

  .progress-stats {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
    padding-top: 16px;
    border-top: 1px solid #f3f4f6;
  }

  .progress-stat {
    text-align: center;
  }

  .progress-stat-value {
    font-size: 20px;
    font-weight: 800;
    color: #111827;
  }

  .progress-stat-label {
    font-size: 11px;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .progress-note {
    margin-top: 16px;
    text-align: center;
    font-size: 12px;
    color: #6b7280;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.45; }
  }

  @media (max-width: 1100px) {
    .ingestion-sidebar {
      display: none;
    }

    .ingestion-main {
      padding: 20px;
    }
  }

  @media (max-width: 900px) {
    .info-cards {
      grid-template-columns: 1fr;
    }

    .upload-items {
      grid-template-columns: 1fr;
    }

    .progress-stats {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .journey-steps {
      flex-direction: column;
      align-items: center;
      gap: 18px;
    }

    .step-line {
      display: none;
    }

    .ams-card {
      flex-direction: column;
      align-items: flex-start;
    }

    .top-bar {
      flex-direction: column;
      align-items: flex-start;
    }
  }
`;