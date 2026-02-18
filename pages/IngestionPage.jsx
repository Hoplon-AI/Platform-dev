import React, { useRef, useState } from "react";

export default function IngestionPage({
  onFilesSelected,
  pipelineStep,
  ingestionSummary,
}) {
  const fileRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const openFile = () => fileRef.current.click();

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) {
      onFilesSelected(e.dataTransfer.files);
    }
  };

  return (
    <div className="ingestion-wrapper">

      {/* Hidden input */}
      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".csv,.xlsx,.xls,.pdf,.docx,.zip"
        hidden
        onChange={(e) => onFilesSelected(e.target.files)}
      />

      {/* Header */}
      <div className="page-header">
        <h1 className="page-title">Upload Your Portfolio Data</h1>
        <div className="page-strapline">Premium Intelligence</div>
        <p className="page-subtitle">
          Get your insurance submission ready in three simple steps
        </p>
      </div>

      {/* Steps */}
      <div className="journey-steps">
        {["Upload SoV", "Portfolio Overview", "Data Quality"].map((s, i) => (
          <div className="journey-step" key={i}>
            <div className={`step-number ${i === 0 ? "active" : "pending"}`}>
              {i + 1}
            </div>
            <div className="step-title">{s}</div>
          </div>
        ))}
      </div>

      {/* Upload Card */}
      <div className="upload-card">
        <div
          className={`upload-zone ${dragOver ? "dragover" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={openFile}
        >
          <div className="upload-icon">📤</div>

          <div className="upload-title">Drag & drop your files here</div>
          <div className="upload-subtitle">
            or click to browse from your computer
          </div>

          <div className="upload-actions">
            <button className="btn btn-primary" type="button">
              Browse Files
            </button>

            <button className="btn btn-secondary" type="button">
              Download Template
            </button>
          </div>

          <div className="upload-formats">
            Supported: Excel (.xlsx, .xls), CSV, PDF, DOCX, ZIP
          </div>
        </div>

        {/* Processing */}
        {pipelineStep && (
          <div className="ingestion-progress active">
            <div className="ingestion-title">
              Processing your files... — {pipelineStep}
            </div>

            {ingestionSummary && (
              <div className="ingestion-stats">
                <div className="ingestion-stat">
                  <div className="ingestion-stat-value">
                    {ingestionSummary.propertyCount}
                  </div>
                  <div className="ingestion-stat-label">Properties</div>
                </div>

                <div className="ingestion-stat">
                  <div className="ingestion-stat-value">
                    £{(ingestionSummary.totalValue / 1e6).toFixed(1)}m
                  </div>
                  <div className="ingestion-stat-label">Total Value</div>
                </div>

                <div className="ingestion-stat">
                  <div className="ingestion-stat-value">
                    {ingestionSummary.missingCore}
                  </div>
                  <div className="ingestion-stat-label">Missing Core</div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
