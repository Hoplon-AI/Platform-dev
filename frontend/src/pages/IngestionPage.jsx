import React, { useCallback, useMemo, useRef, useState } from "react";

function StepCard({ number, title, subtitle, state = "upcoming" }) {
  return (
    <div className={`step ${state === "active" ? "step-active" : ""} ${state === "done" ? "step-done" : ""}`}>
      <div className="step-dot">{number}</div>
      <div className="step-meta">
        <div className="step-title">{title}</div>
        <div className="step-sub">{subtitle}</div>
      </div>
    </div>
  );
}

function SummaryTile({ label, value, wide = false }) {
  return (
    <div className={`summary-item ${wide ? "summary-wide" : ""}`}>
      <div className="summary-k">{label}</div>
      <div className="summary-v">{value}</div>
    </div>
  );
}

function ChecklistItem({ children }) {
  return (
    <li className="mini-list-item">
      <span className="mini-list-dot" />
      <span>{children}</span>
    </li>
  );
}

export default function IngestionPage({
  onFilesSelected,
  pipelineStep,
  ingestionSummary,
  uploadError,
  isUploading,
}) {
  const inputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);

  const steps = useMemo(
    () => [
      {
        n: 1,
        title: "Upload portfolio",
        sub: "Submit SoV spreadsheet",
      },
      {
        n: 2,
        title: "Backend ingestion",
        sub: "Normalize and validate rows",
      },
      {
        n: 3,
        title: "Portfolio overview",
        sub: "Map, blocks, and review",
      },
    ],
    []
  );

  const pickFiles = () => {
    if (!isUploading) inputRef.current?.click();
  };

  const handleInput = (event) => {
    const files = event.target.files;
    if (files && files.length) {
      onFilesSelected?.(files);
    }
    event.target.value = "";
  };

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      event.stopPropagation();
      setDragActive(false);

      const files = event.dataTransfer?.files;
      if (files && files.length) {
        onFilesSelected?.(files);
      }
    },
    [onFilesSelected]
  );

  const onDrag = (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (isUploading) return;

    if (event.type === "dragenter" || event.type === "dragover") {
      setDragActive(true);
    }
    if (event.type === "dragleave") {
      setDragActive(false);
    }
  };

  return (
    <div className="page pad-xl">
      <div className="ingestion-shell">
        <div className="ingestion-head">
          <div className="ingestion-kicker">Portfolio ingestion</div>
          <h1 className="ingestion-title">Upload your portfolio data</h1>
          <p className="ingestion-subtitle">
            Keep the same workflow, but align the experience to the backend:
            upload the SoV, let the API ingest it, then move directly into
            portfolio and block analysis.
          </p>
          <div className="ingestion-head-tags">
            <span className="pill pill-soft">CSV</span>
            <span className="pill pill-soft">XLSX</span>
            <span className="pill pill-soft">Backend-connected</span>
          </div>
        </div>

        <div className="stepper">
          <StepCard number={1} title={steps[0].title} subtitle={steps[0].sub} state="active" />
          <StepCard number={2} title={steps[1].title} subtitle={steps[1].sub} state={isUploading ? "active" : "upcoming"} />
          <StepCard
            number={3}
            title={steps[2].title}
            subtitle={steps[2].sub}
            state={ingestionSummary ? "done" : "upcoming"}
          />
        </div>

        <div className="card card-lg ingestion-main-card">
          <div className="card-header row-between">
            <div>
              <div className="card-title">Upload SoV</div>
              <div className="card-subtitle">
                Drag and drop a schedule of values file, or browse from your computer.
              </div>
            </div>
            <span className="pill pill-muted">Excel / CSV</span>
          </div>

          <div className="card-body">
            <input
              ref={inputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleInput}
              style={{ display: "none" }}
            />

            <div
              className={[
                "dropzone",
                dragActive ? "dropzone-active" : "",
                isUploading ? "dropzone-busy" : "",
              ].join(" ")}
              onDragEnter={onDrag}
              onDragOver={onDrag}
              onDragLeave={onDrag}
              onDrop={onDrop}
              onClick={pickFiles}
              role="button"
              tabIndex={0}
            >
              <div className="dropzone-inner">
                <div className="dropzone-icon">⤒</div>

                <div className="dropzone-text">
                  <div className="dropzone-title">Drag &amp; drop your file here</div>
                  <div className="dropzone-sub">
                    or click to browse from your computer
                  </div>
                </div>

                <div className="dropzone-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={isUploading}
                    onClick={(event) => {
                      event.stopPropagation();
                      pickFiles();
                    }}
                  >
                    {isUploading ? "Uploading…" : "Browse files"}
                  </button>
                </div>
              </div>

              <div className="dropzone-foot">
                Supported: Excel (.xlsx / .xls) and CSV
              </div>
            </div>

            {uploadError ? (
              <div className="alert alert-error" style={{ marginTop: 16 }}>
                {uploadError}
              </div>
            ) : null}

            <div className="ingestion-grid">
              <div className="card card-soft">
                <div className="card-body">
                  <div className="mini-title">Best results when your SoV includes</div>
                  <ul className="mini-list">
                    <ChecklistItem>address line, town / city, and postcode</ChecklistItem>
                    <ChecklistItem>sum insured and property type</ChecklistItem>
                    <ChecklistItem>height / storeys where available</ChecklistItem>
                    <ChecklistItem>UPRN or block reference if you already have it</ChecklistItem>
                  </ul>
                </div>
              </div>

              <div className="card card-soft">
                <div className="card-body">
                  <div className="mini-title">Pipeline status</div>

                  <div className="pipeline-row">
                    <span
                      className={`pill ${
                        isUploading
                          ? "pill-warn"
                          : ingestionSummary
                          ? "pill-good"
                          : "pill-muted"
                      }`}
                    >
                      {isUploading
                        ? "Processing"
                        : ingestionSummary
                        ? "Ready"
                        : "Waiting"}
                    </span>

                    <span className="pipeline-step">
                      {pipelineStep || "Waiting for upload"}
                    </span>
                  </div>

                  <div className="mini-muted">
                    The backend validates format, normalizes fields, writes the
                    ingested rows, and prepares the portfolio dashboard.
                  </div>
                </div>
              </div>
            </div>

            <div className="section">
              <div className="section-head">
                <div className="section-title">Upload summary</div>
                {ingestionSummary ? (
                  <span className="pill pill-good">Portfolio loaded</span>
                ) : null}
              </div>

              {!ingestionSummary ? (
                <div className="mini-muted">
                  Upload a file to generate a summary of rows, mappable properties,
                  readiness, and UPRN coverage before you move to the dashboard.
                </div>
              ) : (
                <>
                  <div className="summary-grid">
                    <SummaryTile label="Source" value={ingestionSummary.source} wide />
                    <SummaryTile label="Rows" value={ingestionSummary.propertyCount} />
                    <SummaryTile label="Mappable" value={ingestionSummary.mappableCount} />
                    <SummaryTile
                      label="Invalid coords"
                      value={ingestionSummary.skippedInvalidCoords}
                    />
                    <SummaryTile
                      label="Avg readiness"
                      value={`${ingestionSummary.avgReadiness ?? 0}/100`}
                    />
                    <SummaryTile
                      label="UPRN match"
                      value={`${ingestionSummary.uprnMatchPct ?? 0}%`}
                    />
                    <SummaryTile
                      label="Blocks detected"
                      value={ingestionSummary.blockCount ?? 0}
                    />
                    <SummaryTile
                      label="Total insured value"
                      value={`£${Number(
                        ingestionSummary.totalValue || 0
                      ).toLocaleString(undefined, {
                        maximumFractionDigits: 0,
                      })}`}
                    />
                  </div>

                  <div className="mini-muted" style={{ marginTop: 10 }}>
                    Once uploaded, the app automatically routes into the Portfolio Overview.
                  </div>
                </>
              )}
            </div>

            <div className="feature-row">
              <div className="feature">
                <div className="feature-title">Backend-led ingestion</div>
                <div className="feature-sub">
                  The frontend now follows the backend contract rather than relying on local-only parsing.
                </div>
              </div>

              <div className="feature">
                <div className="feature-title">Portfolio-first flow</div>
                <div className="feature-sub">
                  Uploading is the entry point into block analysis, mapping, and underwriting review.
                </div>
              </div>

              <div className="feature">
                <div className="feature-title">Geo-ready model</div>
                <div className="feature-sub">
                  The dashboard can consume UPRN, block, coordinate, and enrichment fields as they arrive.
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mini-muted" style={{ marginTop: 10 }}>
          Tip: keep your SoV columns clear and consistent. The backend can normalize aliases,
          but cleaner data produces better portfolio and geo analysis.
        </div>
      </div>
    </div>
  );
}