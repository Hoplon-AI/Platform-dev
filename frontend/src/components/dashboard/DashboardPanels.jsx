// Larger composed panels for the portfolio dashboard.
import React, { useMemo, useState } from "react";

import { fmtMoney, getFireRiskBand } from "../../utils/fireRisk.js";
import { RiskBadge, MiniSummaryTable } from "./DashboardWidgets.jsx";

export function PortfolioAnalysisWindow({ tenancyRows, blockRows, propertyTypeRows, ageBandRows }) {
  const [collapsed, setCollapsed] = React.useState(false);
  return (
    <div className="card">
      <div
        className="card-header row-between"
        style={{ cursor: "pointer", userSelect: "none", paddingBottom: collapsed ? 16 : undefined }}
        onClick={() => setCollapsed((c) => !c)}
      >
        <div>
          <div className="card-title">Portfolio Analysis</div>
          <div className="card-subtitle">
            Compact whole-portfolio analysis for tenancy, block reference, property type, and age.
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="pill pill-muted">Whole SoV summary</span>
          <span className={`panel-chev${collapsed ? " is-collapsed" : ""}`} style={{ fontSize: 16, lineHeight: 1 }}>▾</span>
        </div>
      </div>

      <div
        style={{
          overflow: "hidden",
          maxHeight: collapsed ? 0 : 1000,
          transition: "max-height 0.35s ease",
        }}
      >
        <div className="card-body">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
              gap: 16,
            }}
          >
            <MiniSummaryTable
              title="By tenancy / ownership"
              rows={tenancyRows}
              columns={[
                { key: "label", label: "Type" },
                { key: "count", label: "Units" },
                { key: "totalValue", label: "Sum insured", render: (row) => `£${fmtMoney(row.totalValue)}` },
              ]}
            />

            <MiniSummaryTable
              title="By block reference"
              rows={blockRows}
              columns={[
                { key: "label", label: "Block" },
                { key: "count", label: "Units" },
                { key: "totalValue", label: "TIV", render: (row) => `£${fmtMoney(row.totalValue)}` },
              ]}
            />

            <MiniSummaryTable
              title="By property type"
              rows={propertyTypeRows}
              columns={[
                { key: "label", label: "Type" },
                { key: "count", label: "Units" },
                { key: "totalValue", label: "Sum insured", render: (row) => `£${fmtMoney(row.totalValue)}` },
              ]}
            />

            <MiniSummaryTable
              title="By age banding"
              rows={ageBandRows}
              columns={[
                { key: "label", label: "Age" },
                { key: "count", label: "Units" },
                { key: "totalValue", label: "Sum insured", render: (row) => `£${fmtMoney(row.totalValue)}` },
              ]}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export function FireEvidencePanel({ fireDocuments, loading, onUploadNew }) {
  const [collapsed, setCollapsed] = useState(false);

  const fireRiskSummary = useMemo(() => {
    const totals = { Red: 0, Amber: 0, Green: 0, Unknown: 0 };
    fireDocuments.forEach((doc) => {
      totals[getFireRiskBand(doc)] += 1;
    });
    return totals;
  }, [fireDocuments]);

  return (
    <div className="card">
      <div
        className="card-header row-between"
        style={{ cursor: "pointer", userSelect: "none", paddingBottom: collapsed ? 16 : undefined }}
        onClick={() => setCollapsed((c) => !c)}
      >
        <div>
          <div className="card-title">Fire risk evidence</div>
          <div className="card-subtitle">
            Upload FRA and FRAEW evidence after the SoV so documents can be matched against existing blocks and properties.
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="pill pill-muted">
            {loading ? "Refreshing…" : `${fireDocuments.length} documents`}
          </span>
          <span className={`panel-chev${collapsed ? " is-collapsed" : ""}`} style={{ fontSize: 16, lineHeight: 1 }}>▾</span>
        </div>
      </div>

      <div
        style={{
          overflow: "hidden",
          maxHeight: collapsed ? 0 : 1200,
          transition: "max-height 0.35s ease",
        }}
      >
      <div className="card-body">
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.4fr) minmax(280px, 0.9fr)",
          gap: 16,
          alignItems: "stretch",
          marginBottom: 16,
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
            gap: 12,
          }}
        >
          {Object.entries(fireRiskSummary).map(([band, count]) => (
            <div
              key={band}
              style={{
                border: "1px solid var(--border)",
                borderRadius: 16,
                padding: 14,
                background: "#fff",
              }}
            >
              <RiskBadge band={band} />
              <div style={{ fontSize: 24, fontWeight: 800, marginTop: 10 }}>{count}</div>
            </div>
          ))}
        </div>

        <div
          style={{
            border: "1px solid rgba(184,86,75,0.22)",
            borderRadius: 18,
            padding: 16,
            background: "linear-gradient(135deg, rgba(184,86,75,0.10), rgba(199,106,95,0.04))",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            gap: 14,
          }}
        >
          <div>
            <div style={{ fontWeight: 800, fontSize: 16 }}>Add fire evidence</div>
            <div className="muted" style={{ marginTop: 4 }}>
              FRA and FRAEW uploads should be added here after the SoV. The next upload screen will show the block reference and property matching fields.
            </div>
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onUploadNew?.("FRA")}
            >
              Upload FRA
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => onUploadNew?.("FRAEW")}
            >
              Upload FRAEW
            </button>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gap: 12 }}>
        {fireDocuments.length === 0 ? (
          <div
            style={{
              border: "1px dashed var(--border-line)",
              borderRadius: 16,
              padding: 16,
              background: "var(--panel-soft)",
            }}
          >
            <div style={{ fontWeight: 700 }}>No FRA / FRAEW documents uploaded yet.</div>
            <div className="muted" style={{ marginTop: 4 }}>
              Use the buttons above to add fire risk evidence against the matched blocks from the SoV.
            </div>
          </div>
        ) : (
          fireDocuments.map((doc) => {
            const band = getFireRiskBand(doc);
            return (
              <article
                key={doc.id}
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: 16,
                  padding: 14,
                  background: "#fff",
                }}
              >
                <div className="row-between" style={{ alignItems: "flex-start", gap: 12 }}>
                  <div>
                    <div style={{ fontWeight: 800 }}>{doc.document_type}</div>
                    <div className="muted">
                      {doc.filename} · Block {doc.block_reference || doc.block_id || "—"}
                    </div>
                  </div>
                  <RiskBadge band={band} />
                </div>
                <p className="muted" style={{ marginTop: 10 }}>{doc.summary}</p>
              </article>
            );
          })
        )}
      </div>
      </div>
      </div>
    </div>
  );
}

export function UnderwriterDocumentsPanel({ portfolioId, propertyCount, properties, blocks, onExport }) {
  const enrichedCount = properties.filter(p => p.uprn || p.enrichment_status === "enriched").length;
  const docACompletion = propertyCount > 0 ? Math.min(100, Math.round(((enrichedCount + (propertyCount - enrichedCount) * 0.6) / propertyCount) * 100)) : 0;

  // Client-side blocks use maxHeight (from enrichment) and count (units) — not height_max_m/unit_count
  const highValueBlocks = blocks.filter(b => (b.maxHeight || 0) >= 18);
  const blocksWithData = blocks.filter(b => (b.maxHeight || 0) > 0);
  const docBCompletion = blocks.length > 0 ? Math.round((blocksWithData.length / blocks.length) * 100) : 0;

  const completionColor = (pct) => {
    if (pct >= 90) return { bg: "var(--accent-soft)", color: "#2f6b4f" };
    if (pct >= 70) return { bg: "var(--warning-soft)", color: "#8a6420" };
    return { bg: "var(--danger-soft)", color: "var(--terracotta-2)" };
  };

  return (
    <div className="card" style={{ marginTop: 20, padding: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <div style={{ fontFamily: "var(--font-serif)", fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em", color: "var(--navy)", marginBottom: 4 }}>Underwriter Working Documents</div>
          <div style={{ fontSize: 13, color: "var(--muted)" }}>Pre-populated from HA submission data</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--muted)", flexShrink: 0 }}>
          <span>Export using:</span>
          <select style={{ border: "1px solid var(--border)", borderRadius: 10, padding: "5px 10px", fontSize: 13, background: "#fff", cursor: "pointer", color: "var(--text)" }}>
            <option>Aviva Doc A v2.1</option>
          </select>
        </div>
      </div>

      {/* Doc cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Doc A */}
        <div className="doc-card" style={{ padding: "20px 24px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 20, minWidth: 0 }}>
          <div style={{ display: "flex", gap: 14, alignItems: "flex-start", minWidth: 0 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: "rgba(184,86,75,0.10)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#B8564B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 15, color: "var(--text)", marginBottom: 4 }}>Document A — Stock Listing</div>
              <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>{propertyCount} properties · 35 fields populated</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 999, background: completionColor(docACompletion).bg, color: completionColor(docACompletion).color }}>{docACompletion}% complete</span>
                <span style={{ fontSize: 11, fontWeight: 500, padding: "3px 10px", borderRadius: 999, background: "rgba(184,86,75,0.12)", color: "var(--terracotta-2)" }}>Aviva format</span>
              </div>
            </div>
          </div>
          <button
            className="btn"
            onClick={() => onExport("doc-a")}
            disabled={!portfolioId}
            style={{ whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 6, flexShrink: 0, padding: "8px 16px" }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Download .xlsx
          </button>
        </div>

        {/* Doc B */}
        <div className="doc-card" style={{ padding: "20px 24px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 20, minWidth: 0 }}>
          <div style={{ display: "flex", gap: 14, alignItems: "flex-start", minWidth: 0 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: "#F7ECD6", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#C8923E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6M9 12h6M9 15h4"/>
              </svg>
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 15, color: "var(--text)", marginBottom: 4 }}>Document B — High Value</div>
              <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>{highValueBlocks.length} block{highValueBlocks.length !== 1 ? "s" : ""} (18m+) · 65 fields populated</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 999, background: completionColor(docBCompletion).bg, color: completionColor(docBCompletion).color }}>{docBCompletion}% complete</span>
                <span style={{ fontSize: 11, fontWeight: 500, padding: "3px 10px", borderRadius: 999, background: "rgba(184,86,75,0.12)", color: "var(--terracotta-2)" }}>Aviva format</span>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
            <select style={{ border: "1px solid var(--border)", borderRadius: 10, padding: "7px 10px", fontSize: 13, background: "#fff", cursor: "pointer", color: "var(--text)" }}>
              <option>Aviva v3.0</option>
            </select>
            <button
              className="btn btn-primary"
              onClick={() => onExport("doc-b")}
              disabled={!portfolioId}
              style={{ whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 6, padding: "8px 16px" }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              Download
            </button>
          </div>
        </div>
      </div>

    </div>
  );
}
