import React, { useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ProcessingSteps from "../components/ProcessingSteps";

type UploadStage = "SOV" | "FRA" | "FRAEW";

type IngestionLandingPageProps = {
  hasSovData?: boolean;
  isUploading?: boolean;
  uploadError?: string | null;
  pipelineStep?: string | null;
  selectedBlockReference?: string;
  selectedPropertyId?: string;
  onSelectedBlockReferenceChange?: (value: string) => void;
  onSelectedPropertyIdChange?: (value: string) => void;
  onFilesSelected?: (files: File[], stage: UploadStage) => void;
  stage?: UploadStage;
  onStageChange?: (stage: UploadStage) => void;
};

const stageCopy: Record<
  UploadStage,
  {
    title: string;
    subtitle: string;
    formats: string;
    badge: string;
  }
> = {
  SOV: {
    title: "Upload Schedule of Values",
    subtitle: "Start here. This creates the portfolio, properties, and block records used by later evidence uploads.",
    formats: "Excel (.xlsx / .xls) or CSV",
    badge: "Required first",
  },
  FRA: {
    title: "Upload FRA evidence",
    subtitle: "Attach Fire Risk Assessment PDFs to the blocks created from the SoV upload.",
    formats: "PDF only",
    badge: "Requires SoV",
  },
  FRAEW: {
    title: "Upload FRAEW evidence",
    subtitle: "Attach external wall fire review reports after the SoV has loaded the block data.",
    formats: "PDF only",
    badge: "Requires SoV",
  },
};

const pipelineStepsByStage: Record<string, string[]> = {
  SOV: [
    "Uploading file",
    "Validating format",
    "Parsing property schedule",
    "Detecting blocks",
    "Building portfolio",
    "Preparing dashboard",
    "Complete",
  ],
  FRA: [
    "Uploading document",
    "Extracting text from PDF",
    "Running AI analysis",
    "Identifying fire risk factors",
    "Scoring risk rating",
    "Saving to portfolio",
    "Complete",
  ],
  FRAEW: [
    "Uploading document",
    "Extracting text from PDF",
    "Running AI analysis",
    "Identifying cladding & wall risks",
    "Scoring building risk",
    "Saving to portfolio",
    "Complete",
  ],
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

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m5 13 4 4L19 7" />
    </svg>
  );
}

function IconLock() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
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

export default function IngestionLandingPage({
  hasSovData = false,
  isUploading = false,
  uploadError = null,
  pipelineStep = null,
  selectedBlockReference = "",
  selectedPropertyId = "",
  onSelectedBlockReferenceChange,
  onSelectedPropertyIdChange,
  onFilesSelected,
  stage = "SOV",
  onStageChange,
}: IngestionLandingPageProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
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

  const handleFiles = (files: FileList | File[] | null) => {
    if (!files || files.length === 0 || isStageLocked || isUploading) return;
    onFilesSelected?.(Array.from(files), stage);
  };

  const browseFiles = () => {
    if (isStageLocked || isUploading) return;
    fileInputRef.current?.click();
  };

  return (
    <div className="ingestion-page">
      <style>{css}</style>

      <section className="hero-card">
        <div>
          <div className="eyebrow">Portfolio ingestion</div>
          <h1>Upload Your Portfolio Data</h1>
          <p>
            Upload the SoV first, then add FRA and FRAEW evidence against matched blocks.
          </p>
        </div>
        <div className={hasSovData ? "status-pill ready" : "status-pill waiting"}>
          {hasSovData ? "SoV loaded" : "Waiting for SoV"}
        </div>
      </section>

      <section className="journey-grid" aria-label="Upload journey">
        {(["SOV", "FRA", "FRAEW"] as UploadStage[]).map((item, index) => {
          const locked = item !== "SOV" && !hasSovData;
          const complete = item === "SOV" && hasSovData;
          const active = stage === item;

          return (
            <button
              key={item}
              type="button"
              className={`journey-card ${active ? "active" : ""} ${complete ? "complete" : ""} ${locked ? "locked" : ""}`}
              onClick={() => !locked && onStageChange?.(item)}
              disabled={locked}
            >
              <div className="journey-number">
                {complete ? <IconCheck /> : locked ? <IconLock /> : index + 1}
              </div>
              <div>
                <strong>{index + 1}. {stageCopy[item].title.replace(" evidence", "").replace("Schedule of Values", "SoV")}</strong>
                <span>{locked ? "Upload SoV first" : stageCopy[item].badge}</span>
              </div>
            </button>
          );
        })}
      </section>

      {isEvidenceStage && (
        <section className="linkage-card">
          <div className="linkage-copy">
            <h3>Link {stage} to portfolio data</h3>
            <p>
              Use the block reference from the SoV so the uploaded PDF appears on the correct dashboard block.
            </p>
          </div>

          <div className="linkage-fields">
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
        </section>
      )}

      <section
        className={`upload-zone ${isDragOver ? "dragover" : ""} ${isStageLocked ? "locked" : ""}`}
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

        <div className="upload-icon">
          {isStageLocked ? <IconLock /> : <IconUpload />}
        </div>

        <h2>{isStageLocked ? "Upload SoV before evidence PDFs" : activeCopy.title}</h2>
        <p>{isStageLocked ? "FRA and FRAEW files need block data from the SoV first." : activeCopy.subtitle}</p>

        <button className="primary-btn" type="button" disabled={isStageLocked || isUploading}>
          {isUploading ? "Uploading..." : "Browse files"}
        </button>

        <div className="formats">Supported: {activeCopy.formats}</div>
      </section>

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
                "linear-gradient(160deg, #f0f7ff 0%, #e8f2ff 50%, #dbeafe 100%)",
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
                background: "rgba(37, 99, 235, 0.07)",
                border: "1px solid rgba(37, 99, 235, 0.14)",
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
                  border: "1.5px solid rgba(37,99,235,0.2)",
                  borderTopColor: "#2563eb",
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#1d4ed8",
                  letterSpacing: "0.08em",
                  fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
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
                fontSize: 30,
                fontWeight: 700,
                letterSpacing: "-0.04em",
                color: "#1e3a8a",
                textAlign: "center",
                fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              }}
            >
              Quinn is Analysing your document
            </motion.h2>

            {/* Subtitle */}
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.24 }}
              style={{
                margin: "0 0 48px",
                fontSize: 15,
                color: "#4b72b0",
                textAlign: "center",
                fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
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

      {uploadError && <section className="error-card">{uploadError}</section>}

      <section className="guidance-card">
        <div>
          <strong>Recommended upload order</strong>
          <p>SoV creates the portfolio structure. FRA and FRAEW then attach evidence to blocks.</p>
        </div>
        <div className="guidance-list">
          <div><IconDoc /> Upload SoV first</div>
          <div><IconDoc /> Add FRA PDFs after blocks exist</div>
          <div><IconDoc /> Add FRAEW reports where available</div>
        </div>
      </section>
    </div>
  );
}

const css = `
  .ingestion-page {
    max-width: 1180px;
    margin: 0 auto;
    padding: 12px 0 40px;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: #111827;
  }

  .hero-card {
    display: flex;
    justify-content: space-between;
    gap: 20px;
    align-items: flex-start;
    margin-bottom: 22px;
  }

  .eyebrow {
    color: #2563eb;
    font-size: 13px;
    font-weight: 800;
    margin-bottom: 8px;
  }

  .hero-card h1 {
    margin: 0;
    font-size: 34px;
    line-height: 1.1;
    letter-spacing: -0.04em;
  }

  .hero-card p {
    margin: 8px 0 0;
    color: #64748b;
    font-size: 15px;
  }

  .status-pill {
    padding: 8px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 800;
    white-space: nowrap;
    border: 1px solid;
  }

  .status-pill.ready {
    background: #dcfce7;
    color: #166534;
    border-color: #86efac;
  }

  .status-pill.waiting {
    background: #eff6ff;
    color: #1d4ed8;
    border-color: #bfdbfe;
  }

  .journey-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
    margin-bottom: 20px;
  }

  .journey-card {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 18px;
    border: 1px solid #e5e7eb;
    background: #ffffff;
    border-radius: 16px;
    text-align: left;
    cursor: pointer;
    box-shadow: 0 10px 25px rgba(15, 23, 42, 0.04);
  }

  .journey-card.active {
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
  }

  .journey-card.complete {
    border-color: #86efac;
    background: #f0fdf4;
  }

  .journey-card.locked {
    cursor: not-allowed;
    opacity: 0.72;
    background: #f8fafc;
  }

  .journey-number {
    width: 42px;
    height: 42px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #dbeafe;
    color: #2563eb;
    font-weight: 900;
    flex-shrink: 0;
  }

  .journey-number svg {
    width: 20px;
    height: 20px;
  }

  .journey-card strong,
  .journey-card span {
    display: block;
  }

  .journey-card strong {
    font-size: 15px;
  }

  .journey-card span {
    margin-top: 4px;
    font-size: 12px;
    color: #64748b;
  }

  .linkage-card {
    display: grid;
    grid-template-columns: 0.9fr 1.4fr;
    gap: 24px;
    padding: 22px;
    border: 1px solid #dbeafe;
    background: #f8fbff;
    border-radius: 18px;
    margin-bottom: 20px;
  }

  .linkage-card h3 {
    margin: 0 0 6px;
    font-size: 18px;
  }

  .linkage-card p {
    margin: 0;
    color: #64748b;
    font-size: 14px;
    line-height: 1.5;
  }

  .linkage-fields {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }

  .linkage-fields label span {
    display: block;
    margin-bottom: 6px;
    font-size: 13px;
    font-weight: 800;
    color: #334155;
  }

  .linkage-fields input {
    width: 100%;
    border: 1px solid #dbe3ef;
    border-radius: 12px;
    padding: 12px 14px;
    font-size: 14px;
    outline: none;
    background: #fff;
  }

  .linkage-fields input:focus {
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
  }

  .upload-zone {
    border: 2px dashed #cbd5e1;
    background: #ffffff;
    border-radius: 20px;
    padding: 44px 32px;
    text-align: center;
    cursor: pointer;
    transition: 0.2s ease;
  }

  .upload-zone.dragover,
  .upload-zone:hover {
    border-color: #2563eb;
    background: #eff6ff;
  }

  .upload-zone.locked {
    cursor: not-allowed;
    background: #f8fafc;
  }

  .upload-icon {
    width: 62px;
    height: 62px;
    margin: 0 auto 16px;
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #dbeafe;
    color: #2563eb;
  }

  .upload-icon svg {
    width: 30px;
    height: 30px;
  }

  .upload-zone h2 {
    margin: 0 0 8px;
    font-size: 24px;
    letter-spacing: -0.03em;
  }

  .upload-zone p {
    max-width: 560px;
    margin: 0 auto 20px;
    color: #64748b;
    line-height: 1.5;
  }

  .primary-btn {
    border: 0;
    border-radius: 12px;
    padding: 12px 22px;
    background: #2563eb;
    color: #fff;
    font-weight: 800;
    cursor: pointer;
  }

  .primary-btn:disabled {
    background: #94a3b8;
    cursor: not-allowed;
  }

  .formats {
    margin-top: 16px;
    font-size: 12px;
    color: #64748b;
  }

  .processing-card,
  .guidance-card,
  .error-card {
    margin-top: 22px;
    border-radius: 18px;
    padding: 20px;
  }



  .error-card {
    background: #fee2e2;
    border: 1px solid #fecaca;
    color: #991b1b;
    font-weight: 700;
  }

  .guidance-card {
    display: grid;
    grid-template-columns: 0.9fr 1.5fr;
    gap: 20px;
    background: #fffbeb;
    border: 1px solid #f59e0b;
  }

  .guidance-card p {
    margin: 6px 0 0;
    color: #92400e;
    font-size: 13px;
  }

  .guidance-list {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }

  .guidance-list div {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 700;
    color: #78350f;
  }

  .guidance-list svg {
    width: 16px;
    height: 16px;
    color: #d97706;
  }

  @media (max-width: 900px) {
    .hero-card,
    .processing-header,
    .guidance-card,
    .linkage-card {
      grid-template-columns: 1fr;
      flex-direction: column;
    }

    .journey-grid,
    .linkage-fields,
    .guidance-list {
      grid-template-columns: 1fr;
    }
  }
`;
