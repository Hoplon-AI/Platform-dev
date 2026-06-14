import React, { useCallback, useMemo, useRef, useState } from "react";

function StepCard({ number, title, subtitle, state = "upcoming" }) {
  return (
    <div
      className={`step ${state === "active" ? "step-active" : ""} ${
        state === "done" ? "step-done" : ""
      }`}
    >
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

const DOCUMENT_COPY = {
  sov: {
    kicker: "Portfolio ingestion",
    title: "Upload your portfolio data",
    subtitle:
      "Upload the SoV, let the API ingest it, then move directly into portfolio and block analysis.",
    cardTitle: "Upload SoV",
    cardSubtitle:
      "Drag and drop a schedule of values file, or browse from your computer.",
    pill: "Excel / CSV",
    accept: ".csv,.xlsx,.xls",
    dropTitle: "Drag & drop your SoV file here",
    dropSub: "or click to browse from your computer",
    supported: "Supported: Excel (.xlsx / .xls) and CSV",
    readyLabel: "Portfolio loaded",
  },
  pdf: {
    kicker: "Fire risk evidence ingestion",
    title: "Upload FRA / FRAEW evidence",
    subtitle:
      "Upload fire risk evidence separately from the SoV. The backend extracts FRA / FRAEW fields and links them to the selected block or property.",
    cardTitle: "Upload FRA / FRAEW PDF",
    cardSubtitle:
      "Drag and drop a fire risk PDF, or browse from your computer.",
    pill: "PDF",
    accept: ".pdf,application/pdf",
    dropTitle: "Drag & drop your FRA / FRAEW PDF here",
    dropSub: "or click to browse from your computer",
    supported: "Supported: PDF only",
    readyLabel: "PDF extracted",
  },
};

export default function IngestionPage({
  onFilesSelected,
  pipelineStep,
  ingestionSummary,
  uploadError,
  isUploading,
  uploadMode = "sov",
  pdfDocumentType = "fra",
  onPdfDocumentTypeChange,
  selectedBlockReference = "",
  onSelectedBlockReferenceChange,
  selectedPropertyId = "",
  onSelectedPropertyIdChange,
  latestFireRiskPayload = null,
}) {
  const inputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);

  const isPdfMode = uploadMode === "pdf" || uploadMode === "fire";
  const modeKey = isPdfMode ? "pdf" : "sov";
  const copy = DOCUMENT_COPY[modeKey];

  const steps = useMemo(() => {
    if (isPdfMode) {
      return [
        {
          n: 1,
          title: "Upload evidence",
          sub: "Submit FRA / FRAEW PDF",
        },
        {
          n: 2,
          title: "Backend extraction",
          sub: "Extract risk fields from PDF",
        },
        {
          n: 3,
          title: "Dashboard linkage",
          sub: "Patch linked block / property",
        },
      ];
    }

    return [
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
    ];
  }, [isPdfMode]);

  const hasCompletedUpload = isPdfMode ? Boolean(latestFireRiskPayload) : Boolean(ingestionSummary);

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

      if (isUploading) return;

      const files = event.dataTransfer?.files;
      if (files && files.length) {
        onFilesSelected?.(files);
      }
    },
    [isUploading, onFilesSelected]
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

  const latestPdfType =
    latestFireRiskPayload?.document_type?.toUpperCase?.() ||
    pdfDocumentType?.toUpperCase?.() ||
    "PDF";

  return (
    <div className="page pad-xl">
      <div className="ingestion-shell">
        <div className="ingestion-head">
          <div className="ingestion-kicker">{copy.kicker}</div>
          <h1 className="ingestion-title">{copy.title}</h1>
          <p className="ingestion-subtitle">{copy.subtitle}</p>
          <div className="ingestion-head-tags">
            {isPdfMode ? (
              <>
                <span className="pill pill-soft">FRA</span>
                <span className="pill pill-soft">FRAEW</span>
                <span className="pill pill-soft">PDF extraction</span>
              </>
            ) : (
              <>
                <span className="pill pill-soft">CSV</span>
                <span className="pill pill-soft">XLSX</span>
                <span className="pill pill-soft">Backend-connected</span>
              </>
            )}
          </div>
        </div>

        <div className="stepper">
          <StepCard
            number={1}
            title={steps[0].title}
            subtitle={steps[0].sub}
            state={isUploading ? "done" : "active"}
          />
          <StepCard
            number={2}
            title={steps[1].title}
            subtitle={steps[1].sub}
            state={isUploading ? "active" : hasCompletedUpload ? "done" : "upcoming"}
          />
          <StepCard
            number={3}
            title={steps[2].title}
            subtitle={steps[2].sub}
            state={hasCompletedUpload ? "done" : "upcoming"}
          />
        </div>

        <div className="card card-lg ingestion-main-card">
          <div className="card-header row-between">
            <div>
              <div className="card-title">{copy.cardTitle}</div>
              <div className="card-subtitle">{copy.cardSubtitle}</div>
            </div>
            <span className="pill pill-muted">{copy.pill}</span>
          </div>

          <div className="card-body">
            {isPdfMode ? (
              <div
                className="card card-soft"
                style={{ marginBottom: 16, border: "1px solid rgba(124,58,237,0.18)" }}
              >
                <div className="card-body">
                  <div className="mini-title">PDF linkage</div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "180px minmax(0, 1fr) minmax(0, 1fr)",
                      gap: 12,
                      alignItems: "end",
                      marginTop: 10,
                    }}
                  >
                    <label style={{ display: "grid", gap: 6, fontWeight: 700 }}>
                      Document type
                      <select
                        className="input"
                        value={pdfDocumentType}
                        disabled={isUploading}
                        onChange={(event) => onPdfDocumentTypeChange?.(event.target.value)}
                      >
                        <option value="fra">FRA</option>
                        <option value="fraew">FRAEW</option>
                      </select>
                    </label>

                    <label style={{ display: "grid", gap: 6, fontWeight: 700 }}>
                      Block reference
                      <input
                        className="input"
                        value={selectedBlockReference}
                        disabled={isUploading}
                        onChange={(event) =>
                          onSelectedBlockReferenceChange?.(event.target.value)
                        }
                        placeholder="Example: Block A / 02BR"
                      />
                    </label>

                    <label style={{ display: "grid", gap: 6, fontWeight: 700 }}>
                      Property ID / UPRN
                      <input
                        className="input"
                        value={selectedPropertyId}
                        disabled={isUploading}
                        onChange={(event) => onSelectedPropertyIdChange?.(event.target.value)}
                        placeholder="Optional direct property linkage"
                      />
                    </label>
                  </div>

                  <div className="mini-muted" style={{ marginTop: 10 }}>
                    The backend endpoint expects document_type=fra or document_type=fraew as a query parameter.
                    Block reference and property ID are optional linkage hints.
                  </div>
                </div>
              </div>
            ) : null}

            <input
              ref={inputRef}
              type="file"
              accept={copy.accept}
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
                  <div className="dropzone-title">{copy.dropTitle}</div>
                  <div className="dropzone-sub">{copy.dropSub}</div>
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

              <div className="dropzone-foot">{copy.supported}</div>
            </div>

            {uploadError ? (
              <div className="alert alert-error" style={{ marginTop: 16 }}>
                {uploadError}
              </div>
            ) : null}

            <div className="ingestion-grid">
              <div className="card card-soft">
                <div className="card-body">
                  <div className="mini-title">
                    {isPdfMode ? "Best results when PDFs include" : "Best results when your SoV includes"}
                  </div>
                  <ul className="mini-list">
                    {isPdfMode ? (
                      <>
                        <ChecklistItem>clear assessment date and assessor details</ChecklistItem>
                        <ChecklistItem>overall FRA / FRAEW risk rating</ChecklistItem>
                        <ChecklistItem>significant findings and required actions</ChecklistItem>
                        <ChecklistItem>block reference, property ID, address, or UPRN where available</ChecklistItem>
                      </>
                    ) : (
                      <>
                        <ChecklistItem>address line, town / city, and postcode</ChecklistItem>
                        <ChecklistItem>sum insured and property type</ChecklistItem>
                        <ChecklistItem>height / storeys where available</ChecklistItem>
                        <ChecklistItem>UPRN or block reference if you already have it</ChecklistItem>
                      </>
                    )}
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
                          : hasCompletedUpload
                          ? "pill-good"
                          : "pill-muted"
                      }`}
                    >
                      {isUploading ? "Processing" : hasCompletedUpload ? "Ready" : "Waiting"}
                    </span>

                    <span className="pipeline-step">
                      {pipelineStep || "Waiting for upload"}
                    </span>
                  </div>

                  <div className="mini-muted">
                    {isPdfMode
                      ? "The backend validates the PDF, extracts text, calls the FRA/FRAEW processor, and returns a fire_risk_payload for dashboard linkage."
                      : "The backend validates format, normalizes fields, writes the ingested rows, and prepares the portfolio dashboard."}
                  </div>
                </div>
              </div>
            </div>

            <div className="section">
              <div className="section-head">
                <div className="section-title">
                  {isPdfMode ? "PDF extraction summary" : "Upload summary"}
                </div>
                {hasCompletedUpload ? (
                  <span className="pill pill-good">{copy.readyLabel}</span>
                ) : null}
              </div>

              {isPdfMode ? (
                !latestFireRiskPayload ? (
                  <div className="mini-muted">
                    Upload a FRA / FRAEW PDF to see the extracted fire risk payload and linkage status.
                  </div>
                ) : (
                  <div className="summary-grid">
                    <SummaryTile label="Document" value={latestPdfType} />
                    <SummaryTile label="Upload ID" value={latestFireRiskPayload.upload_id || "—"} wide />
                    <SummaryTile label="Feature ID" value={latestFireRiskPayload.feature_id || "—"} />
                    <SummaryTile label="Block ID" value={latestFireRiskPayload.block_id || "—"} />
                    <SummaryTile label="Property ID" value={latestFireRiskPayload.property_id || "—"} />
                    <SummaryTile
                      label="FRA risk"
                      value={
                        latestFireRiskPayload.fra?.risk_level ||
                        latestFireRiskPayload.fra?.raw_rating ||
                        "—"
                      }
                    />
                    <SummaryTile
                      label="FRAEW risk"
                      value={
                        latestFireRiskPayload.fraew?.risk_level ||
                        latestFireRiskPayload.fraew?.raw_rating ||
                        "—"
                      }
                    />
                    <SummaryTile
                      label="Errors"
                      value={
                        Array.isArray(latestFireRiskPayload.extraction_errors) &&
                        latestFireRiskPayload.extraction_errors.length
                          ? latestFireRiskPayload.extraction_errors.length
                          : "None"
                      }
                    />
                  </div>
                )
              ) : !ingestionSummary ? (
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
                      value={`£${Number(ingestionSummary.totalValue || 0).toLocaleString(
                        undefined,
                        {
                          maximumFractionDigits: 0,
                        }
                      )}`}
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
                <div className="feature-title">
                  {isPdfMode ? "PDF-specific pipeline" : "Backend-led ingestion"}
                </div>
                <div className="feature-sub">
                  {isPdfMode
                    ? "FRA and FRAEW uploads use the backend PDF extraction route, not the SoV spreadsheet path."
                    : "The frontend now follows the backend contract rather than relying on local-only parsing."}
                </div>
              </div>

              <div className="feature">
                <div className="feature-title">
                  {isPdfMode ? "Block/property linkage" : "Portfolio-first flow"}
                </div>
                <div className="feature-sub">
                  {isPdfMode
                    ? "Provide a block reference or property ID so the dashboard can patch the extracted risk evidence into the current portfolio."
                    : "Uploading is the entry point into block analysis, mapping, and underwriting review."}
                </div>
              </div>

              <div className="feature">
                <div className="feature-title">
                  {isPdfMode ? "Dashboard-ready evidence" : "Geo-ready model"}
                </div>
                <div className="feature-sub">
                  {isPdfMode
                    ? "Returned FRA / FRAEW fields are shown in evidence summaries, block rows, and property details."
                    : "The dashboard can consume UPRN, block, coordinate, and enrichment fields as they arrive."}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mini-muted" style={{ marginTop: 10 }}>
          {isPdfMode
            ? "Tip: upload the SoV first, then upload FRA/FRAEW PDFs so evidence can be linked to known blocks and properties."
            : "Tip: keep your SoV columns clear and consistent. The backend can normalize aliases, but cleaner data produces better portfolio and geo analysis."}
        </div>
      </div>
    </div>
  );
}
