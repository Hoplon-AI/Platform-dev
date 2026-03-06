// src/pages/IngestionPage.jsx
import React, { useCallback, useRef, useState } from "react";

export default function IngestionPage({
  onFilesSelected,
  pipelineStep,
  ingestionSummary,
  uploadError,
  isUploading,
}) {
  const inputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);

  const pickFiles = () => inputRef.current?.click();

  const handleInput = (e) => {
    const files = e.target.files;
    if (files && files.length) onFilesSelected?.(files);
    e.target.value = ""; // allow selecting same file twice
  };

  const onDrop = useCallback(
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);

      const files = e.dataTransfer?.files;
      if (files && files.length) onFilesSelected?.(files);
    },
    [onFilesSelected]
  );

  const onDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    if (e.type === "dragleave") setDragActive(false);
  };

  const stepIndex = 0; // Upload SoV page
  const steps = [
    { n: 1, title: "Upload SoV", sub: "Drop your file below" },
    { n: 2, title: "Portfolio Overview", sub: "Readiness + map" },
    { n: 3, title: "Data Quality", sub: "Evidence gaps (later)" },
  ];

  return (
    <div className="page pad-xl">
      <div className="ingestion-shell">
        {/* Header */}
        <div className="ingestion-head">
          <div className="ingestion-kicker">Uploads</div>
          <h1 className="ingestion-title">Upload Your Portfolio Data</h1>
          <p className="ingestion-subtitle">
            Upload an SOV-style file. We’ll normalise key fields and compute submission readiness.
          </p>
          <span className="pill pill-soft">Supported: CSV, XLSX</span>
        </div>

        {/* Stepper */}
        <div className="stepper">
          {steps.map((s, idx) => {
            const active = idx === stepIndex;
            const done = idx < stepIndex;
            return (
              <div key={s.n} className={`step ${active ? "step-active" : ""} ${done ? "step-done" : ""}`}>
                <div className="step-dot">{s.n}</div>
                <div className="step-meta">
                  <div className="step-title">{s.title}</div>
                  <div className="step-sub">{s.sub}</div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Dropzone card */}
        <div className="card card-lg">
          <div className="card-header">
            <div>
              <div className="card-title">Upload SoV</div>
              <div className="card-muted">Drag & drop your file, or browse from your computer.</div>
            </div>
            <div className="pill">CSV / XLSX</div>
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
              className={`dropzone ${dragActive ? "dropzone-active" : ""} ${isUploading ? "dropzone-busy" : ""}`}
              onDragEnter={onDrag}
              onDragOver={onDrag}
              onDragLeave={onDrag}
              onDrop={onDrop}
              onClick={() => !isUploading && pickFiles()}
              role="button"
              tabIndex={0}
            >
              <div className="dropzone-inner">
                <div className="dropzone-icon">⤒</div>
                <div className="dropzone-text">
                  <div className="dropzone-title">Drag &amp; drop your file here</div>
                  <div className="dropzone-sub">or click to browse from your computer</div>
                </div>

                <div className="dropzone-actions">
                  <button className="btn btn-primary" onClick={(e) => (e.stopPropagation(), pickFiles())} disabled={isUploading}>
                    {isUploading ? "Uploading…" : "Browse files"}
                  </button>
                </div>
              </div>

              <div className="dropzone-foot">
                Supported: Excel (.xlsx/.xls), CSV
              </div>
            </div>

            {/* Error */}
            {uploadError && <div className="alert alert-error">{uploadError}</div>}

            {/* Tip + pipeline */}
            <div className="ingestion-grid">
              <div className="card card-soft">
                <div className="card-body">
                  <div className="mini-title">What to include for best results</div>
                  <ul className="mini-list">
                    <li>latitude + longitude (UK bounds)</li>
                    <li>height_m (for building context)</li>
                    <li>sum_insured / declared value</li>
                    <li>UPRN column if available</li>
                  </ul>
                </div>
              </div>

              <div className="card card-soft">
                <div className="card-body">
                  <div className="mini-title">Pipeline</div>
                  <div className="pipeline-row">
                    <span className={`pill ${isUploading ? "pill-warn" : "pill-good"}`}>
                      {isUploading ? "Processing" : pipelineStep ? "Running" : "Ready"}
                    </span>
                    <span className="pipeline-step">{pipelineStep || "Waiting for upload"}</span>
                  </div>
                  <div className="mini-muted">
                    We normalise headers, coerce types, score readiness, and validate coordinates.
                  </div>
                </div>
              </div>
            </div>

            {/* Upload summary */}
            <div className="section">
              <div className="section-head">
                <div className="section-title">Upload Summary</div>
                {ingestionSummary && <span className="pill pill-good">Ready</span>}
              </div>

              {!ingestionSummary ? (
                <div className="mini-muted">
                  Upload a file to generate a summary (rows, mappable locations, readiness, UPRN match).
                </div>
              ) : (
                <div className="summary-grid">
                  <div className="summary-item summary-wide">
                    <div className="summary-k">Source</div>
                    <div className="summary-v">{ingestionSummary.source}</div>
                  </div>

                  <div className="summary-item">
                    <div className="summary-k">Rows</div>
                    <div className="summary-v">{ingestionSummary.propertyCount}</div>
                  </div>

                  <div className="summary-item">
                    <div className="summary-k">Mappable</div>
                    <div className="summary-v">{ingestionSummary.mappableCount}</div>
                  </div>

                  <div className="summary-item">
                    <div className="summary-k">Invalid coords</div>
                    <div className="summary-v">{ingestionSummary.skippedInvalidCoords}</div>
                  </div>

                  <div className="summary-item">
                    <div className="summary-k">Avg readiness</div>
                    <div className="summary-v">{ingestionSummary.avgReadiness ?? "—"}/100</div>
                  </div>

                  <div className="summary-item">
                    <div className="summary-k">UPRN match</div>
                    <div className="summary-v">{ingestionSummary.uprnMatchPct ?? "0"}%</div>
                  </div>
                </div>
              )}

              {ingestionSummary && (
                <div className="mini-muted" style={{ marginTop: 10 }}>
                  After upload, you’ll be taken to the Portfolio Overview automatically.
                </div>
              )}
            </div>

            {/* Small features row (nice like the reference) */}
            <div className="feature-row">
              <div className="feature">
                <div className="feature-title">Smart ingestion</div>
                <div className="feature-sub">Header aliasing, type coercion, UK bounds validation.</div>
              </div>
              <div className="feature">
                <div className="feature-title">Data quality checks</div>
                <div className="feature-sub">Readiness scoring & missing core fields.</div>
              </div>
              <div className="feature">
                <div className="feature-title">Fast iteration</div>
                <div className="feature-sub">Upload new files any time (no backend required).</div>
              </div>
            </div>
          </div>
        </div>

        <div className="mini-muted" style={{ marginTop: 10 }}>
          Tip: keep columns simple (address_line_1, post_code, city, latitude, longitude, sum_insured, height_m).
        </div>
      </div>
    </div>
  );
}
