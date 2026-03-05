// src/pages/IngestionPage.jsx
import React, { useCallback, useMemo, useRef, useState } from "react";

function SummaryTable({ items }) {
  if (!items?.length) return null;

  return (
    <div className="uw-summary">
      <div className="uw-summary-title">Ingestion summary</div>
      <div className="uw-summary-grid">
        {items.map(({ k, v }) => (
          <div key={k} className="uw-summary-row">
            <div className="uw-summary-k">{k}</div>
            <div className="uw-summary-v">{v}</div>
          </div>
        ))}
      </div>
    </div>
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

  const pickFiles = () => inputRef.current?.click();

  const handleInput = (e) => {
    const files = e.target.files;
    if (files && files.length) onFilesSelected?.(files);
    e.target.value = "";
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

  const summaryItems = useMemo(() => {
    if (!ingestionSummary) return null;
    return [
      { k: "Source", v: ingestionSummary.source || "—" },
      { k: "Rows", v: ingestionSummary.propertyCount ?? "—" },
      { k: "Mappable", v: ingestionSummary.mappableCount ?? "—" },
      { k: "Invalid coords", v: ingestionSummary.skippedInvalidCoords ?? "—" },
    ];
  }, [ingestionSummary]);

  return (
    <div className="uw-upload-wrap">
      <div className="uw-upload-hero">
        <div>
          <div className="uw-upload-title">Upload SoV</div>
          <div className="uw-upload-subtitle">
            Upload an SOV-style file. We’ll normalise fields (address, postcode, lat/lon, sum insured,
            height) and compute a readiness score.
          </div>
        </div>
        <div className="uw-chip">Supported: CSV, XLSX</div>
      </div>

      <div className="uw-card">
        <div className="uw-card-head">
          <h2 className="uw-card-title">Upload your portfolio data</h2>
          <span className="uw-chip">CSV / XLSX</span>
        </div>

        <div className="uw-card-body">
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            onChange={handleInput}
            style={{ display: "none" }}
          />

          <div
            className={`uw-dropzone ${dragActive ? "active" : ""}`}
            onClick={pickFiles}
            onDragEnter={onDrag}
            onDragOver={onDrag}
            onDragLeave={onDrag}
            onDrop={onDrop}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") pickFiles();
            }}
          >
            <div className="uw-dropzone-inner">
              <div className="uw-dropzone-icon">⬆︎</div>
              <div className="uw-dropzone-text">
                <div className="uw-dropzone-h">Drag &amp; drop your file here</div>
                <div className="uw-dropzone-p">or click to browse from your computer</div>
              </div>

              <button
                type="button"
                className="uw-btn primary"
                onClick={(e) => {
                  e.stopPropagation();
                  pickFiles();
                }}
                disabled={isUploading}
              >
                {isUploading ? "Uploading..." : "Browse files"}
              </button>
            </div>
          </div>

          {/* Info row (Tip) */}
          <div className="uw-info-row">
            <div className="uw-info-dot">i</div>
            <div className="uw-info-text">
              Tip: include <b>latitude</b>, <b>longitude</b> and <b>height_m</b> columns for best results.
            </div>
          </div>

          {/* Pipeline row */}
          {pipelineStep && (
            <div className="uw-pipeline">
              <div className="uw-pipeline-left">
                <div className="uw-pipeline-label">Pipeline</div>
                <div className="uw-pipeline-step">{pipelineStep}</div>
              </div>
              <span className="uw-chip subtle">{isUploading ? "Running" : "Complete"}</span>
            </div>
          )}

          {uploadError && (
            <div className="uw-alert error">
              <b>Upload error:</b> {uploadError}
            </div>
          )}

          {/* Summary table */}
          {summaryItems && <SummaryTable items={summaryItems} />}

          {summaryItems && (
            <div className="uw-muted" style={{ marginTop: 10 }}>
              After upload, you’ll be taken to the Portfolio Overview automatically.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
