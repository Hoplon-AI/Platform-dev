import { useState } from "react";
import { fmt, isPresent } from "../../utils/blockModel";
import { PdfThumbnail } from "./primitives";
import { openSourceDocument } from "./openSourceDocument";

// One source-document row in Data Provenance — PDF thumbnail + meta + View button.
// Whole card is clickable; hover lifts it. Local hover state (inline styles can't do :hover).
export default function ProvenanceCard({ doc }) {
  const [hover, setHover] = useState(false);
  const uploadId = doc.upload_id || doc.raw?.upload_id;
  const conf = isPresent(doc.raw?.extraction_confidence)
    ? `Confidence ${fmt(doc.raw.extraction_confidence, 2)}`
    : null;
  const typeLabel = doc.document_type === "FRA"
    ? "Fire Risk Assessment"
    : doc.document_type === "FRAEW"
    ? "External Wall Appraisal"
    : doc.document_type;
  const clickable = Boolean(uploadId);

  return (
    <div
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onClick={clickable ? () => openSourceDocument(uploadId, doc.filename) : undefined}
      onKeyDown={clickable ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openSourceDocument(uploadId, doc.filename); } } : undefined}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex", alignItems: "center", gap: 16,
        padding: "14px 16px",
        border: `1px solid ${hover && clickable ? "var(--terracotta, #B8564B)" : "var(--border, #DED7CC)"}`,
        borderRadius: 14,
        background: hover && clickable ? "#FFFDFB" : "#fff",
        boxShadow: hover && clickable ? "0 6px 18px -8px rgba(184,86,75,0.28)" : "0 1px 2px rgba(30,50,70,0.04)",
        cursor: clickable ? "pointer" : "default",
        transition: "border-color 0.18s, box-shadow 0.18s, background 0.18s, transform 0.18s",
        transform: hover && clickable ? "translateY(-1px)" : "none",
      }}
    >
      <PdfThumbnail />

      {/* Meta */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{
            padding: "2px 9px", borderRadius: 999, fontSize: 10.5, fontWeight: 800, letterSpacing: "0.04em",
            background: "var(--navy, #1E3246)", color: "#fff", whiteSpace: "nowrap",
          }}>{doc.document_type}</span>
          <span style={{ fontSize: 12, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {typeLabel}
          </span>
        </div>
        <div style={{
          fontSize: 14, fontWeight: 600, color: "var(--navy, #1E3246)", lineHeight: 1.35,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }} title={doc.filename}>
          {doc.filename || "Source document"}
        </div>
        {conf && (
          <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 2 }}>{conf}</div>
        )}
      </div>

      {/* Action */}
      {clickable ? (
        <span style={{
          flexShrink: 0, display: "inline-flex", alignItems: "center", gap: 6,
          fontSize: 13, fontWeight: 700, whiteSpace: "nowrap",
          padding: "8px 16px", borderRadius: 10,
          background: hover ? "var(--terracotta, #B8564B)" : "var(--blush, #F7E4D5)",
          color: hover ? "#fff" : "var(--terracotta-2, #9A463D)",
          transition: "background 0.18s, color 0.18s",
        }}>
          View PDF
          <span aria-hidden style={{ fontSize: 14 }}>↗</span>
        </span>
      ) : (
        <span style={{ flexShrink: 0, fontSize: 12, color: "var(--muted)" }}>No source file</span>
      )}
    </div>
  );
}
