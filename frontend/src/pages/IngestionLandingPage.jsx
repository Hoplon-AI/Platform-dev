import React, { useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ProcessingSteps from "../components/ProcessingSteps";
import "../styles/ingestion.css";
import {
  stageCopy,
  railTitles,
  STAGES,
  pipelineStepsByStage,
} from "../constants/ingestion";
import {
  fmtInt,
  fmtMoney,
  typeLabel,
  fileFormat,
  riskTone,
} from "../utils/ingestionFormatters";
import {
  IconUpload,
  IconCheck,
  IconLock,
  IconFile,
  FileTypeIcon,
} from "../components/ingestion/IngestionIcons";

function Stat({ icon, label, value }) {
  return (
    <div className="stat">
      <span className="stat-icon">{icon}</span>
      <span className="stat-body">
        <strong>{value}</strong>
        <span>{label}</span>
      </span>
    </div>
  );
}

export default function IngestionLandingPage({
  hasSovData = false,
  isUploading = false,
  uploadError = null,
  pipelineStep = null,
  ingestionSummary = null,
  latestFireRiskPayload = null,
  documents = [],
  selectedBlockReference = "",
  selectedPropertyId = "",
  onSelectedBlockReferenceChange,
  onSelectedPropertyIdChange,
  onFilesSelected,
  stage = "SOV",
  onStageChange,
  haName = "",
  haId = "",
}) {
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const activeCopy = stageCopy[stage];
  const isEvidenceStage = stage === "FRA" || stage === "FRAEW";
  const isStageLocked = isEvidenceStage && !hasSovData;

  const pipelineSteps = pipelineStepsByStage[stage] ?? pipelineStepsByStage.FRA;

  // App.jsx drives 8 fixed steps — map its progress ratio to display steps length
  const APP_TOTAL_STEPS = 8;
  const appStepNames = [
    "uploading document", "uploading file",
    "extracting text from pdf",
    "running ai analysis", "running backend ingestion",
    "identifying fire risk factors", "identifying cladding & wall risks",
    "identifying risk factors", "parsing property schedule",
    "scoring risk rating", "scoring building risk",
    "detecting blocks", "building portfolio",
    "validating format",
    "saving to portfolio",
    "preparing dashboard", "preparing portfolio dashboard",
    "finalising", "complete",
  ];

  const currentStepIndex = useMemo(() => {
    if (!pipelineStep) return -1;
    const lower = pipelineStep.toLowerCase();
    // First try exact match in display steps
    const exact = pipelineSteps.findIndex(s => s.toLowerCase() === lower);
    if (exact !== -1) return exact;
    // Enrichment runs after the canned steps and carries a dynamic suffix
    // ("Enriching properties — N/M"). Map its real progress across the back
    // portion of the steps so the bar climbs smoothly instead of snapping to
    // the last step (and never shows "Complete" until the job truly finishes).
    if (lower.startsWith("enriching")) {
      const m = lower.match(/(\d+)\s*\/\s*(\d+)/);
      const frac = m && Number(m[2]) > 0 ? Number(m[1]) / Number(m[2]) : 0;
      const startStep = Math.max(pipelineSteps.length - 5, 0); // e.g. "3 of 7"
      const lastBeforeComplete = pipelineSteps.length - 2;      // e.g. "6 of 7"
      const span = Math.max(lastBeforeComplete - startStep, 0);
      return Math.min(startStep + Math.round(frac * span), lastBeforeComplete);
    }
    // Fall back: find app step index and map proportionally
    const appIndex = appStepNames.indexOf(lower);
    if (appIndex === -1) return 0;
    return Math.min(
      Math.floor((appIndex / APP_TOTAL_STEPS) * pipelineSteps.length),
      pipelineSteps.length - 1
    );
  }, [pipelineStep, pipelineSteps]);

  const accept = stage === "SOV" ? ".xlsx,.xls,.csv" : ".pdf";

  const handleFiles = (files) => {
    if (!files || files.length === 0 || isStageLocked || isUploading) return;
    onFilesSelected?.(Array.from(files), stage);
  };

  const browseFiles = () => {
    if (isStageLocked || isUploading) return;
    fileInputRef.current?.click();
  };

  const stageIndex = STAGES.indexOf(stage);

  const summary = hasSovData ? ingestionSummary : null;
  const avgReadiness = Math.max(0, Math.min(100, Number(summary?.avgReadiness || 0)));

  const lastEvidence = useMemo(() => {
    if (!latestFireRiskPayload) return null;
    const type = (latestFireRiskPayload.document_type || "").toUpperCase();
    const rating =
      latestFireRiskPayload.fraew?.risk_level ||
      latestFireRiskPayload.fraew?.raw_rating ||
      latestFireRiskPayload.fra?.risk_level ||
      latestFireRiskPayload.fra?.raw_rating ||
      "Processed";
    return {
      type: type || "PDF",
      block: latestFireRiskPayload.block_reference || "—",
      rating,
    };
  }, [latestFireRiskPayload]);

  const nextStepText = !hasSovData
    ? null
    : stage === "SOV"
    ? "Next, attach FRA evidence to the blocks we just detected."
    : "Evidence links to blocks by reference — match it to your SoV block names.";

  return (
    <div className="ingest">
      <div className="ingest-workbench">
        <nav className="ingest-rail" aria-label="Upload journey">
          {STAGES.map((item, index) => {
            const locked = item !== "SOV" && !hasSovData;
            const complete = item === "SOV" && hasSovData;
            const active = stage === item;
            const shortTitle = railTitles[item];

            return (
              <button
                key={item}
                type="button"
                className={`rail-step ${active ? "active" : ""} ${complete ? "complete" : ""} ${locked ? "locked" : ""}`}
                onClick={() => !locked && onStageChange?.(item)}
                disabled={locked}
                aria-current={active ? "step" : undefined}
              >
                <span className="rail-node">
                  {complete ? <IconCheck /> : locked ? <IconLock /> : index + 1}
                </span>
                <span className="rail-text">
                  <strong>{shortTitle}</strong>
                  <span>{locked ? "Upload SoV first" : complete ? "Loaded" : stageCopy[item].badge}</span>
                </span>
              </button>
            );
          })}
        </nav>

        <section className="ingest-panel">
          <div className="panel-head">
            <div className="panel-eyebrow">Step {stageIndex + 1} of 3</div>
            <h2>{isStageLocked ? "Upload SoV before evidence PDFs" : activeCopy.title}</h2>
            <p>{isStageLocked ? "FRA and FRAEW files need block data from the SoV first." : activeCopy.subtitle}</p>
          </div>

          {isEvidenceStage && (
            <div className="panel-linkage">
              <label>
                <span>Block reference</span>
                <input
                  value={selectedBlockReference}
                  onChange={(e) => onSelectedBlockReferenceChange?.(e.target.value)}
                  placeholder="Example: 01BR"
                  disabled={isStageLocked || isUploading}
                />
              </label>

              <label>
                <span>Property ID / UPRN</span>
                <input
                  value={selectedPropertyId}
                  onChange={(e) => onSelectedPropertyIdChange?.(e.target.value)}
                  placeholder="Optional direct property linkage"
                  disabled={isStageLocked || isUploading}
                />
              </label>
            </div>
          )}

          <div
            className={`dropzone ${isDragOver ? "dragover" : ""} ${isStageLocked ? "locked" : ""}`}
            onClick={browseFiles}
            onDragOver={(e) => {
              e.preventDefault();
              if (!isStageLocked && !isUploading) setIsDragOver(true);
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
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={accept}
              style={{ display: "none" }}
              onChange={(e) => handleFiles(e.target.files)}
            />

            <div className="dropzone-icon">
              {isStageLocked ? <IconLock /> : <IconUpload />}
            </div>

            <div className="dropzone-text">
              <strong>{isStageLocked ? "Locked until SoV is loaded" : "Drag and drop, or browse"}</strong>
              <span>Supported: {activeCopy.formats}</span>
            </div>

            <button className="btn btn-primary" type="button" disabled={isStageLocked || isUploading}>
              {isUploading ? "Uploading…" : "Browse files"}
            </button>
          </div>
        </section>


      </div>

      {hasSovData && summary && (() => {
        const portfolioName = (summary.source || "Portfolio").replace(/\.[^/.]+$/, "");
        const readinessColour = avgReadiness >= 80
          ? "var(--accent)"
          : avgReadiness >= 50
          ? "var(--warning)"
          : "var(--danger)";
        return (
          <div className="portfolio-card">
            <div className="portfolio-card-header">
              <div>
                <div className="portfolio-card-kicker">Portfolio loaded</div>
                <h2 className="portfolio-card-title">{portfolioName}</h2>
                <div className="portfolio-card-sub">
                  {fmtInt(summary.propertyCount)} properties &nbsp;·&nbsp; {fmtInt(summary.blockCount)} blocks
                </div>
              </div>
            </div>

            <div className="portfolio-stats">
              <div className="portfolio-stat">
                <div className="portfolio-stat-icon">£</div>
                <div className="portfolio-stat-value">{fmtMoney(summary.totalValue)}</div>
                <div className="portfolio-stat-label">Total Value</div>
              </div>
              <div className="portfolio-stat">
                <div className="portfolio-stat-icon">⌂</div>
                <div className="portfolio-stat-value">{fmtInt(summary.propertyCount)}</div>
                <div className="portfolio-stat-label">Properties</div>
              </div>
              <div className="portfolio-stat">
                <div className="portfolio-stat-icon">◎</div>
                <div className="portfolio-stat-value">{summary.uprnMatchPct}%</div>
                <div className="portfolio-stat-label">UPRN Matched</div>
              </div>
              <div className="portfolio-stat">
                <div className="portfolio-stat-icon">
                  <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: readinessColour, marginRight: 2, verticalAlign: "middle" }} />
                </div>
                <div className="portfolio-stat-value">{avgReadiness}%</div>
                <div className="portfolio-stat-label">Data Readiness</div>
              </div>
            </div>

            {haName && (
              <div className="portfolio-card-footer">
                Uploaded for {haName}
              </div>
            )}
          </div>
        );
      })()}

      {uploadError && <div className="ingest-alert">{uploadError}</div>}

      <div className="ingest-documents">
        <div className="documents-head">
          <div>
            <span className="aside-kicker">Document library</span>
            <h3>
              Uploaded documents
              {documents.length > 0 && <span className="doc-count">{documents.length}</span>}
            </h3>
          </div>
        </div>

        {documents.length === 0 ? (
          <div className="documents-empty">
            <span className="documents-empty-icon"><IconFile /></span>
            <strong>No documents uploaded yet</strong>
            <span>Your Schedule of Values and FRA / FRAEW evidence will appear here as you upload them.</span>
          </div>
        ) : (
          <div className="documents-table">
            <div className="doc-row doc-row-head">
              <span>Document name</span>
              <span>Type</span>
              <span>Linked to</span>
              <span>Risk rating</span>
            </div>

            {documents.map((doc) => (
              <div className="doc-row" key={doc.id}>
                <span className="doc-name">
                  <span className="doc-file"><FileTypeIcon format={fileFormat(doc)} /></span>
                  <span className="doc-name-text" title={doc.name}>{doc.name}</span>
                </span>
                <span>
                  <span className={`type-chip type-${doc.type.toLowerCase()}`}>{typeLabel(doc.type)}</span>
                </span>
                <span className="doc-linked">{doc.linked}</span>
                <span>
                  {doc.rating ? (
                    <span className={`rag-chip ${riskTone(doc.rating)}`}>{doc.rating}</span>
                  ) : (
                    <span className="doc-dash">—</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="ingest-footnote">EquiRisk · Premium Intelligence</div>

      <AnimatePresence>
        {isUploading && (
          <motion.div
            key="processing-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 50,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              background:
                "linear-gradient(160deg, #FBFAF6 0%, var(--warm-bg) 45%, var(--blush) 100%)",
              padding: "40px 20px",
            }}
          >
            {/* AI badge */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.12 }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                background: "rgba(184, 86, 75, 0.08)",
                border: "1px solid rgba(184, 86, 75, 0.18)",
                borderRadius: 100,
                padding: "5px 14px",
                marginBottom: 26,
              }}
            >
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
                style={{
                  width: 11,
                  height: 11,
                  borderRadius: "50%",
                  border: "1.5px solid rgba(184, 86, 75, 0.25)",
                  borderTopColor: "var(--terracotta)",
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "var(--terracotta-2)",
                  letterSpacing: "0.08em",
                  fontFamily: "var(--font-sans)",
                  textTransform: "uppercase",
                }}
              >
                Quinn
              </span>
            </motion.div>

            {/* Title */}
            <motion.h2
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.18 }}
              style={{
                margin: "0 0 10px",
                fontSize: 32,
                fontWeight: 600,
                letterSpacing: "-0.02em",
                color: "var(--navy)",
                textAlign: "center",
                fontFamily: "var(--font-serif)",
              }}
            >
              Quinn is analysing your document
            </motion.h2>

            {/* Subtitle */}
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.24 }}
              style={{
                margin: "0 0 48px",
                fontSize: 15,
                color: "var(--muted)",
                textAlign: "center",
                fontFamily: "var(--font-sans)",
              }}
            >
              Extracting insights and building your portfolio
            </motion.p>

            {/* Steps */}
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.28 }}
              style={{ width: "100%", maxWidth: 460 }}
            >
              <ProcessingSteps
                steps={pipelineSteps}
                currentIndex={currentStepIndex}
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
