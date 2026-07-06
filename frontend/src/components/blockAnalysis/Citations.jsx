import { useState } from "react";
import { Tip } from "./primitives";
import { isLowConfidence } from "./citationsModel";

// Extraction provenance UI: per-field source marks ("p.2 ✓"), a confidence
// badge for section headers, and a collapsible extraction-warnings panel.
// All data comes from the citations / validation_warnings / confidence
// fields on fra_features / fraew_features (chunks 1+2 of the extraction
// grounding work). Documents processed before that ship simply have no
// citations — every component here renders nothing in that case.

// ---------------------------------------------------------------- SourceMark

// Per-field source pill after a cited value: "p.2 ✓" (verified) or
// "Low · p.2 ⚠" (needs review). No numbers — the tier comes from our
// verification metric, not the model's self-report. Hover always shows the
// verbatim source text; low-confidence fields also state why they are low.
export function SourceMark({ cite }) {
  if (!cite || (!cite.pg && !cite.q)) return null;
  const verified = cite.verified === true;
  const low = isLowConfidence(cite);
  const page = cite.found_page ?? cite.pg;

  const tone = low
    ? { bg: "#fef2f2", fg: "#991b1b", bd: "#fecaca" }
    : verified
    ? { bg: "#f0fdf4", fg: "#166534", bd: "#bbf7d0" }
    : { bg: "#f1f5f9", fg: "#475569", bd: "#e2e8f0" };

  const parts = [];
  if (low) {
    const why = (cite.reasons || []).filter(Boolean);
    parts.push(`Low confidence — ${why.length ? why.join("; ") : "check this value against the source PDF"}.`);
  }
  parts.push(
    verified
      ? `Source (page ${page ?? "—"}): “${cite.snippet || cite.q}”`
      : cite.verified === false
      ? `The model cited “${cite.q || "—"}”${cite.pg ? ` on page ${cite.pg}` : ""}, but this text could not be found in the document.`
      : `Cited from page ${page ?? "—"}: “${cite.q || "—"}” (not verified against the source).`
  );

  return (
    <Tip text={parts.join(" ")} align="right">
      <span
        style={{
          display: "inline-flex", alignItems: "center", gap: 3,
          marginLeft: 6, padding: "1px 7px", borderRadius: 999,
          fontSize: 10.5, fontWeight: 700, cursor: "help", whiteSpace: "nowrap",
          background: tone.bg, color: tone.fg, border: `1px solid ${tone.bd}`,
        }}
      >
        {low ? "Low · " : null}
        {page ? `p.${page}` : "src"} {low ? "⚠" : verified ? "✓" : "?"}
      </span>
    </Tip>
  );
}

// ---------------------------------------------------------------- ConfidenceBadge

// Section-header pill: qualitative extraction tier from OUR verification
// metric (coverage + citation verification + validation checks) — never a
// raw number and never the model's self-report. Documents processed before
// the grounding pipeline (validation_warnings === null) show a muted grey
// "Unverified" pill instead.
export function ConfidenceBadge({ doc }) {
  const conf = doc?.extraction_confidence;
  if (conf === null || conf === undefined) return null;
  const legacy = doc.validation_warnings === null || doc.validation_warnings === undefined;
  const warnings = doc.validation_warnings || [];
  const cites = doc.citations || {};
  const citeList = Object.values(cites);
  const verified = citeList.filter((c) => c?.verified === true).length;
  const lowFields = citeList.filter((c) => isLowConfidence(c)).length;

  if (legacy) {
    return (
      <Tip
        text="This document was processed before source verification existed, so its extraction was never checked against the PDF. Re-upload the document to get verified, per-field confidence."
        align="right"
      >
        <span
          onClick={(e) => e.stopPropagation()}
          style={{
            display: "inline-flex", alignItems: "center", gap: 5,
            padding: "3px 10px", borderRadius: 999, fontSize: 11.5, fontWeight: 700,
            background: "#f1f5f9", color: "#64748b", border: "1px solid #e2e8f0",
            cursor: "help", whiteSpace: "nowrap",
          }}
        >
          Extraction unverified
        </span>
      </Tip>
    );
  }

  const tier = conf >= 0.85 && lowFields === 0
    ? { label: "Extraction verified", icon: "✓", bg: "#f0fdf4", fg: "#166534", bd: "#bbf7d0" }
    : conf >= 0.6
    ? { label: "Extraction — needs review", icon: "⚠", bg: "#fffbeb", fg: "#92400e", bd: "#fde68a" }
    : { label: "Extraction — low confidence", icon: "⚠", bg: "#fef2f2", fg: "#991b1b", bd: "#fecaca" };

  const parts = [];
  if (citeList.length) parts.push(`${verified} of ${citeList.length} field citations verified verbatim against the PDF.`);
  if (lowFields) parts.push(`${lowFields} field${lowFields > 1 ? "s" : ""} flagged low confidence (shown in red below).`);
  parts.push(warnings.length ? `${warnings.length} extraction warning${warnings.length > 1 ? "s" : ""}.` : "No extraction warnings.");
  parts.push("Rated by our verification metric (source checks + validation), not the model's self-report.");

  return (
    <Tip text={parts.join(" ")} align="right">
      <span
        onClick={(e) => e.stopPropagation()}
        style={{
          display: "inline-flex", alignItems: "center", gap: 5,
          padding: "3px 10px", borderRadius: 999, fontSize: 11.5, fontWeight: 700,
          background: tier.bg, color: tier.fg, border: `1px solid ${tier.bd}`,
          cursor: "help", whiteSpace: "nowrap",
        }}
      >
        {tier.icon} {tier.label}
        {(warnings.length > 0 || lowFields > 0) && (
          <span style={{ fontWeight: 800 }}>· {warnings.length + lowFields}⚠</span>
        )}
      </span>
    </Tip>
  );
}

// ---------------------------------------------------------------- WarningsPanel

// Collapsible amber box listing what the pipeline repaired, dropped or could
// not verify while extracting this document. Hidden when there is nothing.
export function WarningsPanel({ warnings }) {
  const [open, setOpen] = useState(false);
  if (!warnings?.length) return null;
  const shown = open ? warnings : [];
  return (
    <div style={{ margin: "10px 0 4px", border: "1px solid #fde68a", background: "#fffbeb", borderRadius: 10, overflow: "hidden" }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%", textAlign: "left", background: "none", border: "none", cursor: "pointer",
          padding: "8px 12px", display: "flex", alignItems: "center", gap: 8,
          fontSize: 12.5, fontWeight: 700, color: "#92400e",
        }}
      >
        <span aria-hidden>⚠</span>
        {warnings.length} extraction warning{warnings.length > 1 ? "s" : ""} — data below may need review
        <span style={{ marginLeft: "auto", fontSize: 11, fontWeight: 600 }}>{open ? "▲ hide" : "▼ show"}</span>
      </button>
      {shown.length > 0 && (
        <div style={{ borderTop: "1px solid #fde68a", padding: "8px 12px", display: "flex", flexDirection: "column", gap: 5 }}>
          {shown.map((w, i) => (
            <div key={i} style={{ fontSize: 12, color: "#78350f", lineHeight: 1.45 }}>
              <span style={{ fontWeight: 700, fontFamily: "ui-monospace, monospace" }}>{w.field}</span>
              {" — "}{w.reason}
              {w.raw ? <span style={{ color: "#a16207" }}> (was: “{String(w.raw).slice(0, 60)}”)</span> : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- ActionSource

// One line in an expanded action card: where this action came from and
// whether its text was verified verbatim in the PDF.
export function ActionSource({ a }) {
  if (a?.source_verified === undefined && a?.pg === undefined) return null;
  if (a.source_verified === null || a.source_verified === undefined) {
    return a.pg ? (
      <span style={{ fontSize: 12, color: "var(--muted)" }}>Source: page {a.pg}</span>
    ) : null;
  }
  const verified = a.source_verified === true;
  const page = a.source_page ?? a.pg;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      fontSize: 12, fontWeight: 600,
      color: verified ? "#166534" : "#92400e",
    }}>
      {verified
        ? <>✓ Verified verbatim in document{page ? ` — page ${page}` : ""}</>
        : <>⚠ Text not found in document — review against the source PDF</>}
    </span>
  );
}
