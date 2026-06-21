import React, { useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ProcessingSteps from "../components/ProcessingSteps";

type UploadStage = "SOV" | "FRA" | "FRAEW";

type IngestionSummary = {
  source?: string;
  propertyCount?: number;
  blockCount?: number;
  totalValue?: number;
  mappableCount?: number;
  geoCompletenessPct?: number;
  sovCompletenessPct?: number;
  avgReadiness?: number;
  uprnMatchPct?: number;
};

type FireRiskPayload = {
  document_type?: string;
  block_reference?: string;
  fra?: { risk_level?: string; raw_rating?: string };
  fraew?: { risk_level?: string; raw_rating?: string };
};

type UploadedDocument = {
  id: string;
  name: string;
  type: string;
  linked: string;
  rating?: string | null;
};

type IngestionLandingPageProps = {
  hasSovData?: boolean;
  isUploading?: boolean;
  uploadError?: string | null;
  pipelineStep?: string | null;
  ingestionSummary?: IngestionSummary | null;
  latestFireRiskPayload?: FireRiskPayload | null;
  documents?: UploadedDocument[];
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
    explainer: string;
  }
> = {
  SOV: {
    title: "Upload Schedule of Values",
    subtitle: "Start here. This creates the portfolio, properties, and block records used by later evidence uploads.",
    formats: "Excel (.xlsx / .xls) or CSV",
    badge: "Required first",
    explainer: "Creates the portfolio — properties, blocks and sums insured — that every later upload attaches to.",
  },
  FRA: {
    title: "Upload FRA evidence",
    subtitle: "Attach Fire Risk Assessment PDFs to the blocks created from the SoV upload.",
    formats: "PDF only",
    badge: "Requires SoV",
    explainer: "AI extracts risk ratings, fire safety measures and outstanding actions, matched to each block.",
  },
  FRAEW: {
    title: "Upload FRAEW evidence",
    subtitle: "Attach external wall fire review reports after the SoV has loaded the block data.",
    formats: "PDF only",
    badge: "Requires SoV",
    explainer: "Captures cladding, insulation and external wall risks for building-level fire scoring.",
  },
};

const railTitles: Record<UploadStage, string> = {
  SOV: "Schedule of Values",
  FRA: "Fire Risk Assessment",
  FRAEW: "External Wall Review",
};

const STAGES: UploadStage[] = ["SOV", "FRA", "FRAEW"];

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

const fmtInt = (value?: number | null) => Number(value || 0).toLocaleString();

const fmtMoney = (value?: number | null) => {
  const n = Number(value || 0);
  if (n >= 1e9) return `£${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `£${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `£${Math.round(n / 1e3)}k`;
  return `£${n.toLocaleString()}`;
};

const readinessBand = (score: number) => {
  if (score >= 80) return "green";
  if (score >= 50) return "amber";
  return "red";
};

const typeLabel = (type: string) => {
  const t = (type || "").toUpperCase();
  if (t === "SOV") return "SoV";
  return t || "Doc";
};

type FileFormat = "xls" | "csv" | "pdf" | "doc";

const fileFormat = (doc: UploadedDocument): FileFormat => {
  const name = (doc.name || "").toLowerCase();
  if (name.endsWith(".csv")) return "csv";
  if (name.endsWith(".xlsx") || name.endsWith(".xls") || name.endsWith(".xlsm"))
    return "xls";
  if (name.endsWith(".pdf")) return "pdf";
  const t = (doc.type || "").toUpperCase();
  if (t === "SOV") return "xls";
  if (t === "FRA" || t === "FRAEW" || t === "FIRE") return "pdf";
  return "doc";
};

const riskTone = (rating?: string | null) => {
  const r = (rating || "").toLowerCase();
  if (/(high|substantial|intolerable|severe|\bred\b|p2|p3)/.test(r)) return "red";
  if (/(moderate|medium|tolerable|\bamber\b|p1)/.test(r)) return "amber";
  if (/(low|trivial|negligible|\bgreen\b|acceptable)/.test(r)) return "green";
  return "neutral";
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

function IconBuilding() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="4" y="3" width="16" height="18" rx="1.5" />
      <path d="M9 7h.01M15 7h.01M9 11h.01M15 11h.01M9 15h.01M15 15h.01" />
    </svg>
  );
}

function IconLayers() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="m3 13 9 5 9-5" />
    </svg>
  );
}

function IconPound() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M8 21h10M8 21c1.6-1 2-2.4 2-4v-4M8 13h6M9.5 13c-.3-1.3-1-2.5-1-4a3.5 3.5 0 0 1 6.6-1.6" />
    </svg>
  );
}

function IconPin() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

function IconShield() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function IconSparkle() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 3v4M12 17v4M5 12H1M23 12h-4M6.3 6.3 3.5 3.5M20.5 20.5l-2.8-2.8M17.7 6.3l2.8-2.8M3.5 20.5l2.8-2.8" />
    </svg>
  );
}

function IconCheckMini() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
      <path d="m5 13 4 4L19 7" />
    </svg>
  );
}

function IconFile() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M9 13h6M9 17h6" />
    </svg>
  );
}

const FILE_FORMAT_COLOR: Record<FileFormat, string> = {
  xls: "#1D7A4C",
  csv: "#2F6FB0",
  pdf: "#C0392B",
  doc: "#6B7280",
};

function FileTypeIcon({ format }: { format: FileFormat }) {
  const fill = FILE_FORMAT_COLOR[format];
  return (
    <svg viewBox="0 0 32 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M6 1.5h14.5L30.5 11.5V36a2.5 2.5 0 0 1-2.5 2.5H6A2.5 2.5 0 0 1 3.5 36V4A2.5 2.5 0 0 1 6 1.5Z"
        fill="#FFFFFF"
        stroke="#D8D2C8"
        strokeWidth="1.6"
      />
      <path
        d="M20.5 1.5V9a2.5 2.5 0 0 0 2.5 2.5h7.5"
        fill="#F1ECE4"
        stroke="#D8D2C8"
        strokeWidth="1.6"
      />
      <rect x="2.5" y="22" width="27" height="13" rx="2.5" fill={fill} />
      <text
        x="16"
        y="31.4"
        textAnchor="middle"
        fontSize="8.5"
        fontWeight="700"
        letterSpacing="0.3"
        fill="#FFFFFF"
        fontFamily="Inter, system-ui, sans-serif"
      >
        {format.toUpperCase()}
      </text>
    </svg>
  );
}

function Stat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
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
      <style>{css}</style>

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

        <aside className="ingest-aside" aria-label="Upload context">
          {summary ? (
            <div className="aside-card aside-summary">
              <div className="aside-head">
                <span className="aside-kicker">Portfolio loaded</span>
                <h3 title={summary.source}>{summary.source || "Schedule of Values"}</h3>
              </div>

              <div className="stat-grid">
                <Stat icon={<IconBuilding />} label="Properties" value={fmtInt(summary.propertyCount)} />
                <Stat icon={<IconLayers />} label="Blocks" value={fmtInt(summary.blockCount)} />
                <Stat icon={<IconPound />} label="Total value" value={fmtMoney(summary.totalValue)} />
                <Stat icon={<IconPin />} label="Mappable" value={`${Number(summary.geoCompletenessPct || 0)}%`} />
              </div>

              <div className="readiness">
                <div className="readiness-top">
                  <span>Average readiness</span>
                  <strong>{avgReadiness}%</strong>
                </div>
                <div className="readiness-track">
                  <span className={`readiness-fill ${readinessBand(avgReadiness)}`} style={{ width: `${avgReadiness}%` }} />
                </div>
              </div>

              {lastEvidence && isEvidenceStage && (
                <div className="aside-evidence">
                  <span className="aside-evidence-tag">{lastEvidence.type}</span>
                  <div>
                    <strong>Last evidence · {lastEvidence.rating}</strong>
                    <span>Block {lastEvidence.block}</span>
                  </div>
                </div>
              )}

              {nextStepText && (
                <div className="aside-next">
                  <IconSparkle />
                  <p>{nextStepText}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="aside-card">
              <div className="aside-head">
                <span className="aside-kicker">Before you upload</span>
                <h3>What you'll need</h3>
              </div>
              <ul className="checklist">
                <li><span className="check-tick"><IconCheckMini /></span> A Schedule of Values export</li>
                <li><span className="check-tick"><IconCheckMini /></span> One row per property or unit</li>
                <li><span className="check-tick"><IconCheckMini /></span> Address and postcode columns</li>
                <li><span className="check-tick"><IconCheckMini /></span> Sum insured per record</li>
              </ul>
              <p className="aside-hint">
                Column names are matched automatically — there's no template to follow.
              </p>
            </div>
          )}

          <div className="aside-card aside-note">
            <span className="aside-note-icon"><IconShield /></span>
            <div>
              <strong>Your data stays private</strong>
              <span>Files are processed inside your tenant only and are never shared between housing associations.</span>
            </div>
          </div>
        </aside>
      </div>

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

const css = `
  .ingest {
    width: 100%;
    max-width: none;
    margin: 0;
    padding: 10px 0 40px;
    min-height: calc(100vh - 220px);
    font-family: var(--font-sans);
    color: var(--text);
    display: flex;
    flex-direction: column;
    gap: 26px;
  }

  /* ── Workbench: stepper rail + active panel + context aside ── */
  .ingest-workbench {
    display: grid;
    grid-template-columns: 248px minmax(0, 1fr) 380px;
    gap: 36px;
    align-items: start;
  }

  .ingest-rail {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 4px;
  }

  /* Vertical spine connecting the step nodes */
  .ingest-rail::before {
    content: '';
    position: absolute;
    left: 23px;
    top: 40px;
    bottom: 40px;
    width: 2px;
    background: var(--border-line);
    z-index: 0;
  }

  .rail-step {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 16px;
    border: 1px solid transparent;
    background: transparent;
    border-radius: var(--radius);
    text-align: left;
    cursor: pointer;
    transition: background 0.25s var(--ease), border-color 0.25s var(--ease), box-shadow 0.25s var(--ease);
  }

  .rail-step:hover:not(.locked):not(.active) {
    background: var(--warm-bg-2);
  }

  .rail-step.active {
    background: #fff;
    border-color: var(--border);
    box-shadow: var(--shadow-soft);
  }

  .rail-step.locked {
    cursor: not-allowed;
    opacity: 0.65;
  }

  .rail-node {
    width: 32px;
    height: 32px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--warm-bg-2);
    border: 1px solid var(--border-line);
    color: var(--slate-warm);
    font-family: var(--font-sans);
    font-weight: 700;
    font-size: 14px;
    flex-shrink: 0;
    transition: background 0.25s var(--ease), color 0.25s var(--ease), border-color 0.25s var(--ease);
  }

  .rail-node svg {
    width: 16px;
    height: 16px;
  }

  .rail-step.active .rail-node {
    background: var(--terracotta);
    border-color: var(--terracotta);
    color: #fff;
  }

  .rail-step.complete .rail-node {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }

  .rail-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .rail-text strong {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--navy);
    line-height: 1.25;
  }

  .rail-text span {
    margin-top: 3px;
    font-size: 12px;
    color: var(--muted);
  }

  .rail-step.active .rail-text span {
    color: var(--terracotta-2);
    font-weight: 600;
  }

  /* ── Active step panel ── */
  .ingest-panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-soft);
    padding: 32px 34px 36px;
  }

  .panel-eyebrow {
    font-size: 11.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--slate-warm);
    margin-bottom: 8px;
  }

  .panel-head h2 {
    margin: 0;
    font-family: var(--font-serif);
    font-size: 23px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--navy);
  }

  .panel-head p {
    margin: 8px 0 0;
    color: var(--muted);
    font-size: 14.5px;
    line-height: 1.55;
    max-width: 560px;
  }

  .panel-linkage {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-top: 22px;
  }

  .panel-linkage label span {
    display: block;
    margin-bottom: 6px;
    font-size: 12.5px;
    font-weight: 600;
    color: var(--text-light);
  }

  .panel-linkage input {
    width: 100%;
    min-height: 44px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 10px 12px;
    font-size: 14px;
    color: var(--text);
    outline: none;
    background: #fff;
    transition: border-color 0.18s ease, box-shadow 0.18s ease;
  }

  .panel-linkage input:focus {
    border-color: var(--terracotta);
    box-shadow: 0 0 0 3px rgba(184, 86, 75, 0.18);
  }

  .panel-linkage input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  /* ── Dropzone (centered upload target) ── */
  .dropzone {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    gap: 16px;
    margin-top: 24px;
    min-height: 280px;
    border: 1.5px dashed var(--border-line);
    border-radius: 18px;
    background: linear-gradient(180deg, #fffdfa 0%, var(--warm-bg) 100%);
    padding: 36px 28px;
    cursor: pointer;
    transition: border-color 0.2s var(--ease), background 0.2s var(--ease), box-shadow 0.2s var(--ease);
  }

  .dropzone:hover,
  .dropzone.dragover {
    border-color: var(--terracotta);
    background: var(--blush);
    box-shadow: 0 12px 28px -18px rgba(184, 86, 75, 0.4);
  }

  .dropzone.locked {
    cursor: not-allowed;
    opacity: 0.7;
    background: var(--warm-bg-2);
  }

  .dropzone.locked:hover {
    border-color: var(--border-line);
    background: var(--warm-bg-2);
    box-shadow: none;
  }

  .dropzone-icon {
    width: 64px;
    height: 64px;
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--primary-soft);
    color: var(--terracotta);
    flex-shrink: 0;
  }

  .dropzone-icon svg {
    width: 30px;
    height: 30px;
  }

  .dropzone-text strong {
    display: block;
    font-size: 18px;
    font-weight: 600;
    color: var(--navy);
  }

  .dropzone-text span {
    display: block;
    margin-top: 5px;
    font-size: 13.5px;
    color: var(--muted);
  }

  .dropzone .btn {
    margin-top: 4px;
  }

  /* ── Context aside (right column) ── */
  .ingest-aside {
    display: flex;
    flex-direction: column;
    gap: 18px;
    position: sticky;
    top: 12px;
  }

  .aside-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-soft);
    padding: 22px;
  }

  .aside-kicker {
    display: block;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--terracotta-2);
  }

  .aside-head h3 {
    margin: 7px 0 0;
    font-family: var(--font-serif);
    font-size: 18px;
    font-weight: 600;
    color: var(--navy);
    line-height: 1.3;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .stat-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 18px;
  }

  .stat {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px;
    border-radius: var(--radius-sm);
    background: var(--warm-bg);
    border: 1px solid var(--border-soft);
  }

  .stat-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: 9px;
    background: var(--primary-soft);
    color: var(--terracotta);
    flex-shrink: 0;
  }

  .stat-icon svg { width: 17px; height: 17px; }

  .stat-body { display: flex; flex-direction: column; min-width: 0; }

  .stat-body strong {
    font-size: 16px;
    font-weight: 700;
    color: var(--navy);
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
  }

  .stat-body span {
    margin-top: 2px;
    font-size: 11.5px;
    color: var(--muted);
  }

  .readiness { margin-top: 16px; }

  .readiness-top {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 7px;
  }

  .readiness-top span { font-size: 12.5px; color: var(--text-light); font-weight: 500; }
  .readiness-top strong { font-size: 14px; color: var(--navy); font-variant-numeric: tabular-nums; }

  .readiness-track {
    height: 8px;
    border-radius: 999px;
    background: var(--warm-bg-2);
    overflow: hidden;
  }

  .readiness-fill {
    display: block;
    height: 100%;
    border-radius: 999px;
    transition: width 0.5s var(--ease);
  }

  .readiness-fill.green { background: var(--accent); }
  .readiness-fill.amber { background: #C98A2B; }
  .readiness-fill.red { background: var(--terracotta); }

  .aside-evidence {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 16px;
    padding: 12px;
    border-radius: var(--radius-sm);
    background: var(--warm-bg);
    border: 1px solid var(--border-soft);
  }

  .aside-evidence-tag {
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: #fff;
    background: var(--navy);
    padding: 4px 8px;
    border-radius: 6px;
    flex-shrink: 0;
  }

  .aside-evidence div { display: flex; flex-direction: column; min-width: 0; }
  .aside-evidence strong { font-size: 13px; color: var(--navy); font-weight: 600; }
  .aside-evidence span { font-size: 12px; color: var(--muted); margin-top: 2px; }

  .aside-next {
    display: flex;
    gap: 10px;
    margin-top: 18px;
    padding-top: 16px;
    border-top: 1px solid var(--border-soft);
  }

  .aside-next svg {
    width: 16px;
    height: 16px;
    color: var(--terracotta);
    flex-shrink: 0;
    margin-top: 1px;
  }

  .aside-next p {
    margin: 0;
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--text-light);
  }

  /* Checklist (pre-upload state) */
  .checklist {
    list-style: none;
    margin: 18px 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 11px;
  }

  .checklist li {
    display: flex;
    align-items: center;
    gap: 11px;
    font-size: 13.5px;
    color: var(--text);
  }

  .check-tick {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
    flex-shrink: 0;
  }

  .check-tick svg { width: 13px; height: 13px; }

  .aside-hint {
    margin: 16px 0 0;
    padding-top: 14px;
    border-top: 1px solid var(--border-soft);
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--muted);
  }

  /* Privacy note card */
  .aside-note {
    display: flex;
    gap: 13px;
    align-items: flex-start;
  }

  .aside-note-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    border-radius: 11px;
    background: var(--accent-soft);
    color: var(--accent);
    flex-shrink: 0;
  }

  .aside-note-icon svg { width: 20px; height: 20px; }

  .aside-note strong {
    display: block;
    font-size: 13.5px;
    font-weight: 600;
    color: var(--navy);
  }

  .aside-note span {
    display: block;
    margin-top: 4px;
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--muted);
  }

  /* ── Error alert ── */
  .ingest-alert {
    border-radius: 14px;
    padding: 13px 16px;
    font-size: 14px;
    font-weight: 600;
    background: var(--danger-soft);
    color: #b91c1c;
    border: 1px solid #e8b9b1;
  }

  /* ── Document library (bottom region) ── */
  .ingest-documents {
    padding-top: 24px;
    border-top: 1px solid var(--border-soft);
  }

  .documents-head {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .documents-head h3 {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 6px 0 0;
    font-family: var(--font-serif);
    font-size: 20px;
    font-weight: 600;
    color: var(--navy);
  }

  .doc-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 24px;
    height: 22px;
    padding: 0 8px;
    border-radius: 999px;
    background: var(--primary-soft);
    color: var(--terracotta-2);
    font-family: var(--font-sans);
    font-size: 12.5px;
    font-weight: 700;
  }

  .documents-table {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-soft);
    overflow: hidden;
  }

  .doc-row {
    display: grid;
    grid-template-columns: minmax(0, 2.6fr) 120px minmax(0, 1.3fr) 150px;
    align-items: center;
    gap: 16px;
    padding: 14px 22px;
    border-bottom: 1px solid var(--border-soft);
  }

  .doc-row:last-child { border-bottom: none; }

  .doc-row-head {
    background: var(--warm-bg);
    padding-top: 12px;
    padding-bottom: 12px;
  }

  .doc-row-head span {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--slate-warm);
  }

  .doc-row:not(.doc-row-head) {
    transition: background 0.18s var(--ease);
  }

  .doc-row:not(.doc-row-head):hover {
    background: var(--warm-bg);
  }

  .doc-name {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }

  .doc-file {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    flex-shrink: 0;
  }

  .doc-file svg { width: 23px; height: 29px; display: block; }

  .doc-name-text {
    font-size: 14px;
    font-weight: 500;
    color: var(--navy);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .type-chip {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--warm-bg-2);
    color: var(--slate-warm);
    border: 1px solid var(--border-line);
  }

  .type-sov { background: var(--accent-soft); color: var(--accent); border-color: transparent; }
  .type-fra { background: var(--primary-soft); color: var(--terracotta-2); border-color: transparent; }
  .type-fraew { background: rgba(35, 37, 64, 0.08); color: var(--navy); border-color: transparent; }

  .doc-linked {
    font-size: 13.5px;
    color: var(--text-light);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rag-chip {
    display: inline-block;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 11px;
    border-radius: 999px;
    text-transform: capitalize;
  }

  .rag-chip.red { background: var(--danger-soft); color: #b04035; }
  .rag-chip.amber { background: #FBEAD2; color: #97631B; }
  .rag-chip.green { background: var(--accent-soft); color: var(--accent); }
  .rag-chip.neutral { background: var(--warm-bg-2); color: var(--slate-warm); }

  .doc-dash { color: var(--slate-light); }

  .documents-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 8px;
    padding: 48px 24px;
    background: var(--panel);
    border: 1.5px dashed var(--border-line);
    border-radius: var(--radius-lg);
  }

  .documents-empty-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 48px;
    border-radius: 14px;
    background: var(--warm-bg-2);
    color: var(--slate-light);
    margin-bottom: 4px;
  }

  .documents-empty-icon svg { width: 24px; height: 24px; }
  .documents-empty strong { font-size: 15px; color: var(--navy); font-weight: 600; }
  .documents-empty span { font-size: 13px; color: var(--muted); max-width: 380px; }

  .ingest-footnote {
    margin-top: auto;
    padding-top: 18px;
    text-align: right;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--slate-light);
  }

  /* ── Responsive ── */
  @media (max-width: 1180px) {
    .ingest-workbench {
      grid-template-columns: 220px minmax(0, 1fr);
    }

    .ingest-aside {
      grid-column: 1 / -1;
      flex-direction: row;
      position: static;
    }

    .ingest-aside .aside-card { flex: 1 1 0; }
  }

  @media (max-width: 900px) {
    .ingest {
      min-height: 0;
      justify-content: flex-start;
    }

    .ingest-workbench {
      grid-template-columns: 1fr;
    }

    .ingest-rail {
      flex-direction: row;
      flex-wrap: wrap;
    }

    .ingest-rail::before {
      display: none;
    }

    .rail-step {
      flex: 1 1 200px;
    }

    .ingest-aside {
      flex-direction: column;
    }

    .panel-linkage {
      grid-template-columns: 1fr;
    }

    .doc-row {
      grid-template-columns: minmax(0, 1.8fr) minmax(0, 1fr);
      gap: 10px 14px;
    }

    .doc-row > span:nth-child(3),
    .doc-row > span:nth-child(4) {
      display: none;
    }
  }
`;
