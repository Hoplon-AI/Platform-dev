import React, { useEffect, useMemo, useRef, useState } from "react";

import PortfolioMap from "../components/PortfolioMap.jsx";
import PropertyDetails from "../components/PropertyDetails.jsx";
import { PortfolioInsightsPanel } from "../components/PortfolioInsights.jsx";
import { blockStreetText, blockDisplayAddress } from "../utils/blockModel.js";

const fmtMoney = (n) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  return x.toLocaleString(undefined, { maximumFractionDigits: 0 });
};

const hasValidLatLon = (lat, lon) => {
  const la = Number(lat);
  const lo = Number(lon);
  return (
    Number.isFinite(la) && Number.isFinite(lo) &&
    la !== 0 && lo !== 0 &&
    la >= 49.0 && la <= 61.5 &&
    lo >= -8.8 && lo <= 2.8
  );
};

const normaliseKey = (value) => String(value ?? "").trim().toLowerCase();

const sameProperty = (a, b) => {
  if (!a || !b) return false;

  return (
    (a.id && b.id && String(a.id) === String(b.id)) ||
    (a.property_id && b.property_id && String(a.property_id) === String(b.property_id)) ||
    (a.property_reference &&
      b.property_reference &&
      String(a.property_reference) === String(b.property_reference)) ||
    (a.uprn && b.uprn && String(a.uprn) === String(b.uprn))
  );
};

const sameBlock = (a, b) => {
  if (!a || !b) return false;

  return (
    (a.id && b.id && String(a.id) === String(b.id)) ||
    (a.block_id && b.block_id && String(a.block_id) === String(b.block_id)) ||
    (a.label && b.label && String(a.label) === String(b.label)) ||
    (a.name && b.name && String(a.name) === String(b.name)) ||
    (a.block_reference &&
      b.block_reference &&
      String(a.block_reference) === String(b.block_reference)) ||
    (a.parent_uprn && b.parent_uprn && String(a.parent_uprn) === String(b.parent_uprn))
  );
};

const inferPortfolioClass = (property) => {
  const propertyType = String(property?.property_type ?? property?.type ?? "").toLowerCase();
  const builtForm = String(property?.built_form ?? "").toLowerCase();
  const address = String(
    property?.address_line_1 ?? property?.address ?? property?.property_reference ?? ""
  ).toLowerCase();

  const combined = `${propertyType} ${builtForm} ${address}`;

  if (
    propertyType.includes("lock up") ||
    propertyType.includes("lockup") ||
    propertyType.includes("office") ||
    propertyType.includes("commercial") ||
    propertyType.includes("mixed use")
  ) {
    return "Other";
  }

  if (
    combined.includes("flat") ||
    combined.includes("apartment") ||
    combined.includes("maisonette") ||
    combined.includes("tenement")
  ) {
    return "Flats";
  }

  if (
    combined.includes("house") ||
    combined.includes("bungalow") ||
    combined.includes("terrace") ||
    combined.includes("semi") ||
    combined.includes("detached")
  ) {
    return "Houses";
  }

  return "Other";
};

const buildBreakdown = (items, keyFn, valueFn) => {
  const grouped = new Map();

  (items || []).forEach((item) => {
    const key = keyFn(item) || "Not recorded";
    if (!grouped.has(key)) {
      grouped.set(key, {
        label: key,
        count: 0,
        totalValue: 0,
      });
    }

    const entry = grouped.get(key);
    entry.count += 1;
    entry.totalValue += Number(valueFn(item) || 0);
  });

  return Array.from(grouped.values()).sort((a, b) => {
    if (b.totalValue !== a.totalValue) return b.totalValue - a.totalValue;
    return b.count - a.count;
  });
};

const normaliseActions = (value) => {
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  if (!value) return [];
  return [String(value)];
};

const getFireDocumentRisk = (doc) =>
  doc?.risk_level ??
  doc?.rag_status ??
  doc?.raw_rating ??
  doc?.external_wall_risk ??
  doc?.building_risk_rating ??
  doc?.overall_risk_rating ??
  doc?.risk_rating ??
  null;

const getFireRiskBand = (doc) => {
  const text = String(getFireDocumentRisk(doc) ?? "").toLowerCase();
  if (
    text.includes("red") ||
    text.includes("high") ||
    text.includes("intolerable") ||
    text.includes("not acceptable")
  ) {
    return "Red";
  }
  if (
    text.includes("amber") ||
    text.includes("medium") ||
    text.includes("moderate") ||
    text.includes("tolerable")
  ) {
    return "Amber";
  }
  if (
    text.includes("green") ||
    text.includes("low") ||
    text.includes("acceptable") ||
    text.includes("broadly acceptable")
  ) {
    return "Green";
  }
  return "Unknown";
};

const riskBadgeStyle = (band) => {
  if (band === "Red") return { background: "#fee2e2", color: "#991b1b" };
  if (band === "Amber") return { background: "#fef3c7", color: "#92400e" };
  if (band === "Green") return { background: "#dcfce7", color: "#166534" };
  return { background: "#e2e8f0", color: "#475569" };
};

const normaliseFirePayloadToDocument = (payload, fallbackIndex = 0) => {
  if (!payload) return null;

  const firePayload = payload.fire_risk_payload ?? payload;
  const documentType = String(firePayload.document_type ?? payload.document_type ?? "").toUpperCase();
  const fra = firePayload.fra ?? null;
  const fraew = firePayload.fraew ?? null;
  const primary = documentType === "FRAEW" ? fraew : fra || fraew || firePayload;

  const riskLevel = getFireDocumentRisk(primary);
  const actions = normaliseActions(
    primary?.recommendations ??
      primary?.actions ??
      primary?.significant_findings ??
      primary?.remedial_actions ??
      primary?.action_items
  );

  return {
    id:
      firePayload.id ??
      firePayload.upload_id ??
      firePayload.feature_id ??
      `${documentType || "FIRE"}-${fallbackIndex + 1}`,
    upload_id: firePayload.upload_id ?? payload.upload_id ?? "",
    feature_id: firePayload.feature_id ?? payload.feature_id ?? "",
    filename: firePayload.filename ?? payload.filename ?? "Uploaded PDF",
    document_type: documentType || "FIRE",
    block_id: firePayload.block_id ?? payload.block_id ?? "",
    block_reference:
      firePayload.block_reference ??
      firePayload.block_id ??
      payload.block_reference ??
      payload.block_id ??
      "",
    property_id: firePayload.property_id ?? payload.property_id ?? "",
    risk_level: riskLevel,
    rag_status: riskLevel,
    summary: (() => {
      const txt =
        primary?.summary ??
        primary?.executive_summary ??
        primary?.findings_summary ??
        primary?.interim_measures_detail ??
        null;
      if (txt) return txt;
      // Build from structured fields when no free-text summary exists
      const parts = [];
      if (primary?.risk_rating) parts.push(`Risk rating: ${primary.risk_rating}.`);
      if (primary?.building_risk_rating) parts.push(`Building risk: ${primary.building_risk_rating}.`);
      if (primary?.evacuation_strategy) parts.push(`Evacuation: ${primary.evacuation_strategy.replace(/_/g, " ")}.`);
      if (primary?.total_action_count) {
        const overdue = primary.overdue_action_count ? ` (${primary.overdue_action_count} overdue)` : "";
        parts.push(`${primary.total_action_count} action item(s)${overdue}.`);
      }
      if (primary?.has_combustible_cladding) parts.push("Combustible cladding present.");
      if (primary?.has_sprinkler_system === false) parts.push("No sprinkler system.");
      if (primary?.has_fire_alarm_system === false) parts.push("No fire alarm system.");
      return parts.length > 0 ? parts.join(" ") : null;
    })(),
    actions,
    fra,
    fraew,
    raw: firePayload,
    created_at: payload.created_at ?? new Date().toISOString(),
  };
};

const collectFireDocumentsFromIngestion = (ingestionResult, latestFireRiskPayload) => {
  const docs = [];

  const sourceItems = Array.isArray(ingestionResult?.fire_documents)
    ? ingestionResult.fire_documents
    : Array.isArray(ingestionResult?.raw?.fire_documents)
    ? ingestionResult.raw.fire_documents
    : [];

  sourceItems.forEach((item, index) => {
    const normalised = normaliseFirePayloadToDocument(item, index);
    if (normalised) docs.push(normalised);
  });


  const latest = normaliseFirePayloadToDocument(latestFireRiskPayload, docs.length);
  if (latest) docs.unshift(latest);

  const seen = new Set();
  return docs.filter((doc) => {
    const key = [doc.document_type, doc.upload_id, doc.feature_id, doc.block_reference, doc.filename]
      .map(normaliseKey)
      .join("|");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

function RiskBadge({ band }) {
  return (
    <span
      style={{
        ...riskBadgeStyle(band),
        borderRadius: 999,
        padding: "6px 10px",
        fontSize: 12,
        fontWeight: 800,
        whiteSpace: "nowrap",
      }}
    >
      {band}
    </span>
  );
}

function HoverTooltip({ children, tip, badgeStyle, tipWidth = 160 }) {
  const [visible, setVisible] = useState(false);
  return (
    <span
      style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      <span style={badgeStyle}>{children}</span>
      <span style={{
        position: "absolute",
        top: "calc(100% + 8px)",
        left: "50%",
        transform: "translateX(-50%)",
        width: tipWidth,
        background: "var(--panel)",
        color: "var(--text-light)",
        fontSize: 12,
        fontWeight: 400,
        lineHeight: 1.5,
        textTransform: "none",
        letterSpacing: "normal",
        borderRadius: 8,
        border: "1px solid var(--border, #e2e8f0)",
        padding: "9px 12px",
        pointerEvents: "none",
        zIndex: 50,
        boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
        opacity: visible ? 1 : 0,
        transition: "opacity 0.18s ease",
      }}>
        {tip}
      </span>
    </span>
  );
}

function KpiCard({ title, value, subtitle, tone = "default", icon = null }) {
  return (
    <div className={`dashboard-card dashboard-card-${tone}`}>
      {icon ? <div className="dashboard-card-icon">{icon}</div> : null}
      <div className="dashboard-card-title">{title}</div>
      <div className="dashboard-card-value">{value}</div>
      {subtitle ? <div className="dashboard-card-sub">{subtitle}</div> : null}
    </div>
  );
}

// Lightweight inline stroke icons (lucide-style) for the KPI cards.
const KPI_ICONS = {
  value: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 7V5a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h14a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H5a2 2 0 0 1-2-2V6" />
      <circle cx="16" cy="12" r="1.4" />
    </svg>
  ),
  blocks: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 21h18" /><path d="M5 21V7l7-4 7 4v14" /><path d="M9 9h.01M15 9h.01M9 13h.01M15 13h.01M9 17h.01M15 17h.01" />
    </svg>
  ),
  fra: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
    </svg>
  ),
  fraew: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="1.5" /><path d="M3 9h18M3 14h18M8 4v5m8-5v5m-4 5v6m-4-6h8" />
    </svg>
  ),
  enhanced: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4z" /><path d="M19 14l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" />
    </svg>
  ),
};

// Renders high-risk / medium-risk badges for a fire-evidence card.
// Returns null when there are no red/amber blocks so the card shows no zeroes.
function fireRiskSubtitle(counts) {
  if (!counts || (counts.red <= 0 && counts.amber <= 0 && counts.green <= 0)) return null;
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
      {counts.red > 0 ? (
        <HoverTooltip
          tip="Block rated Red — high fire risk"
          badgeStyle={{ padding: "2px 8px", borderRadius: 6, background: "rgba(225,29,72,0.09)", border: "1px solid rgba(225,29,72,0.28)", fontWeight: 600, fontSize: 13, color: "var(--navy)", cursor: "default" }}
        >
          {counts.red} high-risk
        </HoverTooltip>
      ) : null}
      {counts.amber > 0 ? (
        <HoverTooltip
          tip="Block rated Amber — medium fire risk"
          badgeStyle={{ padding: "2px 8px", borderRadius: 6, background: "rgba(245,158,11,0.10)", border: "1px solid rgba(245,158,11,0.30)", fontWeight: 600, fontSize: 13, color: "var(--navy)", cursor: "default" }}
        >
          {counts.amber} mid-risk
        </HoverTooltip>
      ) : null}
      {counts.green > 0 ? (
        <HoverTooltip
          tip="Block rated Green — low fire risk"
          badgeStyle={{ padding: "2px 8px", borderRadius: 6, background: "rgba(34,197,94,0.10)", border: "1px solid rgba(34,197,94,0.30)", fontWeight: 600, fontSize: 13, color: "var(--navy)", cursor: "default" }}
        >
          {counts.green} low-risk
        </HoverTooltip>
      ) : null}
    </span>
  );
}

function MiniSummaryTable({ title, subtitle, rows, columns }) {
  return (
    <div
      style={{
        background: "var(--panel-soft)",
        border: "1px solid var(--border-soft)",
        borderRadius: 16,
        padding: 14,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{title}</div>
      {subtitle ? <div className="muted" style={{ marginBottom: 10 }}>{subtitle}</div> : null}

      {!rows.length ? (
        <div className="muted">No data available.</div>
      ) : (
        <div className="table-wrap" style={{ maxHeight: 260, overflowY: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column.key}>{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={`${row.label || row.block || idx}`}>
                  {columns.map((column) => (
                    <td key={column.key}>
                      {typeof column.render === "function"
                        ? column.render(row)
                        : row[column.key] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PortfolioAnalysisWindow({ tenancyRows, blockRows, propertyTypeRows, ageBandRows }) {
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

function FireEvidencePanel({ fireDocuments, loading, onUploadNew }) {
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
                {doc.actions?.length > 0 ? (
                  <ul style={{ margin: "8px 0 0 18px" }}>
                    {doc.actions.slice(0, 4).map((action, idx) => (
                      <li key={idx}>{action}</li>
                    ))}
                  </ul>
                ) : null}
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

export default function PortfolioDashboard({
  ingestionResult,
  ingestionSummary,
  onUploadNew,
  latestFireRiskPayload = null,
  fireDocumentsLoading = false,
  refetchFireDocuments,
  portfolioId = null,
  onLoadMapData,
}) {
  const properties = ingestionResult?.properties || [];
  const [selectedBlock, setSelectedBlock] = useState(null);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [mapDataLoading, setMapDataLoading] = useState(false);
  const [suppressMapFit, setSuppressMapFit] = useState(false);

  const resolvedPortfolioId = portfolioId || null;

  const fireDocuments = useMemo(
    () => collectFireDocumentsFromIngestion(ingestionResult, latestFireRiskPayload),
    [ingestionResult, latestFireRiskPayload]
  );

  const baseBlocks = useMemo(() => {
    if (!properties.length) return [];

    const grouped = new Map();

    properties.forEach((property) => {
      const key =
        property.block_reference ||
        property.parent_uprn ||
        property.uprn ||
        property.property_reference ||
        property.id;

      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(property);
    });

    return Array.from(grouped.entries())
      .map(([key, items]) => {
        const mappable = items.filter((p) => hasValidLatLon(p.latitude, p.longitude));
        const lat =
          mappable.length > 0
            ? mappable.reduce((sum, p) => sum + Number(p.latitude), 0) / mappable.length
            : null;
        const lon =
          mappable.length > 0
            ? mappable.reduce((sum, p) => sum + Number(p.longitude), 0) / mappable.length
            : null;
        const totalValue = items.reduce((sum, p) => sum + (Number(p.sum_insured) || 0), 0);
        const maxHeight = items.reduce((max, p) => {
          const height = Number(p.height_m);
          return Number.isFinite(height) ? Math.max(max, height) : max;
        }, 0);
        const representativeProperty = mappable[0] || items.find((p) => p.uprn) || items[0] || null;

        return {
          id: key,
          block_id: key,
          label: key || "Unassigned block",
          name: key || "Unassigned block",
          properties: items,
          count: items.length,
          lat,
          lon,
          latitude: lat,
          longitude: lon,
          __lat: lat,
          __lon: lon,
          hasValidCoords: hasValidLatLon(lat, lon),
          totalValue,
          maxHeight,
          parent_uprn:
            items.find((p) => p.parent_uprn)?.parent_uprn ||
            items.find((p) => p.uprn)?.uprn ||
            null,
          block_reference: key || "",
          representativeProperty,
        };
      })
      .sort((a, b) => b.totalValue - a.totalValue);
  }, [properties]);

  const blocks = useMemo(() => {
    return baseBlocks.map((block) => {
      const blockAliases = [
        block.id,
        block.block_id,
        block.label,
        block.name,
        block.block_reference,
        block.parent_uprn,
      ]
        .map(normaliseKey)
        .filter(Boolean);

      const linkedDocs = fireDocuments.filter((doc) => {
        const docBlock = normaliseKey(doc.block_reference || doc.block_id);
        const docProperty = normaliseKey(doc.property_id);
        const blockMatch = docBlock && blockAliases.includes(docBlock);
        const propertyMatch =
          docProperty &&
          block.properties.some((property) =>
            [property.id, property.property_id, property.property_reference, property.uprn]
              .map(normaliseKey)
              .filter(Boolean)
              .includes(docProperty)
          );
        return blockMatch || propertyMatch;
      });

      const propertyFra = block.properties.find((p) => p.latest_fra)?.latest_fra ?? null;
      const propertyFraew = block.properties.find((p) => p.latest_fraew)?.latest_fraew ?? null;
      const latestFraDoc = linkedDocs.find((doc) => doc.document_type === "FRA") ?? null;
      const latestFraewDoc = linkedDocs.find((doc) => doc.document_type === "FRAEW") ?? null;
      const latestFra = latestFraDoc?.fra ?? latestFraDoc ?? propertyFra;
      const latestFraew = latestFraewDoc?.fraew ?? latestFraewDoc ?? propertyFraew;

      return {
        ...block,
        latest_fra: latestFra,
        latest_fraew: latestFraew,
        fire_documents: {
          fra: latestFra,
          fraew: latestFraew,
          all: linkedDocs,
        },
      };
    });
  }, [baseBlocks, fireDocuments]);

  const tenancyRows = useMemo(
    () => buildBreakdown(properties, (property) => property.occupancy_type || "Not recorded", (property) => property.sum_insured),
    [properties]
  );

  const blockRows = useMemo(
    () => blocks.map((block) => ({ label: block.label || "Unassigned block", count: block.count || 0, totalValue: block.totalValue || 0 })),
    [blocks]
  );

  const propertyTypeRows = useMemo(
    () => buildBreakdown(properties, (property) => property.property_type || inferPortfolioClass(property), (property) => property.sum_insured),
    [properties]
  );

  const ageBandRows = useMemo(
    () =>
      buildBreakdown(
        properties,
        (property) => {
          if (property.year_of_build) {
            const year = Number(property.year_of_build);
            if (Number.isFinite(year)) {
              if (year < 1919) return "Pre-1919";
              if (year < 1945) return "1920-1944";
              if (year < 1980) return "1945-1979";
              if (year < 2001) return "1980-2000";
              return "2001+";
            }
          }
          return "Unknown";
        },
        (property) => property.sum_insured
      ),
    [properties]
  );

  // Auto-poll for enriched coordinates after SoV upload.
  // Fires every 15s while properties exist but none have coords, up to 3 minutes.
  useEffect(() => {
    if (typeof onLoadMapData !== "function") return;
    if (!properties.length) return;

    const hasAnyCoords = () => properties.some((p) => p.hasValidCoords);

    // Do an immediate fetch first
    if (!hasAnyCoords()) {
      setMapDataLoading(true);
      onLoadMapData().finally(() => setMapDataLoading(false));
    }

    // Then poll every 15s for up to 3 minutes (12 attempts)
    let attempts = 0;
    const MAX_ATTEMPTS = 12;
    const interval = setInterval(() => {
      if (hasAnyCoords() || attempts >= MAX_ATTEMPTS) {
        clearInterval(interval);
        return;
      }
      attempts++;
      onLoadMapData();
    }, 15000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLoadMapData = () => {
    if (typeof onLoadMapData !== "function" || mapDataLoading) return;
    setMapDataLoading(true);
    onLoadMapData().finally(() => setMapDataLoading(false));
  };

  useEffect(() => {
    if (!properties.length) {
      setSelectedBlock(null);
      setSelectedProperty(null);
      return;
    }

    if (selectedProperty) {
      const matchingProperty = properties.find((p) => sameProperty(p, selectedProperty));
      if (!matchingProperty) setSelectedProperty(null);
    }

    if (selectedBlock) {
      const matchingBlock = blocks.find((b) => sameBlock(b, selectedBlock));
      if (!matchingBlock) {
        setSelectedBlock(null);
      }
    }
  }, [properties, blocks, selectedProperty, selectedBlock]);

  const resolvedSelectedProperty = useMemo(() => {
    if (!selectedProperty) return null;
    return properties.find((p) => sameProperty(p, selectedProperty)) || null;
  }, [properties, selectedProperty]);

  const resolvedSelectedBlock = useMemo(() => {
    if (resolvedSelectedProperty) {
      return blocks.find((block) => block.properties.some((p) => sameProperty(p, resolvedSelectedProperty))) || null;
    }
    if (!selectedBlock) return null;
    return blocks.find((b) => sameBlock(b, selectedBlock)) || null;
  }, [blocks, selectedBlock, resolvedSelectedProperty]);

  const selectedBlockId = resolvedSelectedBlock?.id ?? null;
  const geoCompletenessPct = ingestionSummary?.geoCompletenessPct ?? 0;
  const highRiseBlocks = blocks.filter((b) => Number(b.maxHeight) >= 18 || Number(b.max_storeys) >= 7).length;
  const amberBlocks = blocks.filter((b) => (Number(b.maxHeight) >= 11 && Number(b.maxHeight) < 18) || (Number(b.max_storeys) >= 4 && Number(b.max_storeys) < 7)).length;
  const mappedBlocksCount = blocks.filter((b) => b.hasValidCoords).length;
  const enrichedPropertiesCount = properties.filter((p) => p.uprn || p.enrichment_status === "enriched").length;
  const enrichedPropertiesPct = properties.length > 0 ? Math.round((enrichedPropertiesCount / properties.length) * 100) : 0;

  // Block-level RAG counts, split by evidence type (FRA vs FRAEW).
  const fireRiskCounts = useMemo(() => {
    const tally = (getDoc) =>
      blocks.reduce(
        (acc, block) => {
          const doc = getDoc(block);
          if (!doc) return acc;
          const band = getFireRiskBand(doc);
          if (band === "Red") acc.red += 1;
          else if (band === "Amber") acc.amber += 1;
          else if (band === "Green") acc.green += 1;
          return acc;
        },
        { red: 0, amber: 0, green: 0 }
      );
    return {
      fra: tally((b) => b.latest_fra),
      fraew: tally((b) => b.latest_fraew),
    };
  }, [blocks]);

  // Document counts per evidence type for the card headline values.
  const fireDocCounts = useMemo(() => {
    return fireDocuments.reduce(
      (acc, doc) => {
        const type = String(doc.document_type || "").toUpperCase();
        if (type === "FRA") acc.fra += 1;
        else if (type === "FRAEW") acc.fraew += 1;
        return acc;
      },
      { fra: 0, fraew: 0 }
    );
  }, [fireDocuments]);

  // Called by list panels and the map — selects the block for the details panel / flat-list popup (map stays in blocks view)
  const handleSelectBlock = (block) => {
    if (!block) {
      setSelectedBlock(null);
      setSelectedProperty(null);
      return;
    }
    setSuppressMapFit(true);
    const matchingBlock = blocks.find((b) => sameBlock(b, block)) || block;
    setSelectedBlock(matchingBlock);
    setSelectedProperty(null);
  };

  const handleSelectProperty = (property) => {
    if (!property) {
      setSuppressMapFit(true);
      setSelectedProperty(null);
      return;
    }
    setSuppressMapFit(true);
    const matchingProperty = properties.find((p) => sameProperty(p, property)) || property;
    setSelectedProperty(matchingProperty);
    const parentBlock = blocks.find((block) => block.properties.some((p) => sameProperty(p, matchingProperty))) || null;
    setSelectedBlock(parentBlock);
  };

  const handleClearMapSelection = () => {
    setSuppressMapFit(true);
    setSelectedBlock(null);
    setSelectedProperty(null);
  };

  const handleExport = async (docType) => {
    if (!resolvedPortfolioId) return;
    const url = `/api/v1/portfolios/${resolvedPortfolioId}/export/${docType}`;
    const token =
      localStorage.getItem("equirisk_token") ||
      sessionStorage.getItem("equirisk_token") ||
      "";
    try {
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const blob = await res.blob();
      const filename =
        res.headers.get("content-disposition")?.match(/filename="?([^"]+)"?/)?.[1] ||
        `${docType.replace("-", "_")}.xlsx`;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    } catch (err) {
      console.error("[handleExport]", err);
      alert(`Download failed: ${err.message}`);
    }
  };

  useEffect(() => {
    if (suppressMapFit) {
      const t = setTimeout(() => setSuppressMapFit(false), 50);
      return () => clearTimeout(t);
    }
  }, [suppressMapFit]);

  const detailsScrollRef = useRef(null);
  useEffect(() => {
    if (detailsScrollRef.current) {
      detailsScrollRef.current.scrollTop = 0;
    }
  }, [selectedProperty, selectedBlock]);

  if (!ingestionSummary) {
    return (
      <div className="content-wrap">
        <div className="card">
          <div className="empty-state">No portfolio loaded yet. Upload an SoV file to begin.</div>
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary" onClick={() => onUploadNew?.("SOV")}>Upload SoV</button>
          </div>
        </div>
      </div>
    );
  }

  const hasActiveBlockSelection = Boolean(resolvedSelectedBlock);
  const hasActivePropertySelection = Boolean(resolvedSelectedProperty);
  const mapMode = "blocks";
  const mapProperties = properties;

  return (
    <div className="content-wrap">
      <div className="main-head">
        <div>
          <div className="tag">Premium Intelligence</div>
          <div className="page-title">Portfolio <em>Overview</em></div>
        </div>

        <div className="actions" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {typeof refetchFireDocuments === "function" ? (
            <button className="btn" onClick={refetchFireDocuments} disabled={fireDocumentsLoading}>
              {fireDocumentsLoading ? "Refreshing…" : "Refresh fire evidence"}
            </button>
          ) : null}
          <button className="btn" onClick={() => onUploadNew?.("SOV")}>Upload SoV</button>
          <button className="btn btn-primary" onClick={() => onUploadNew?.("FRA")}>Upload FRA</button>
          <button className="btn btn-primary" onClick={() => onUploadNew?.("FRAEW")}>Upload FRAEW</button>
        </div>
      </div>

      <div className="dashboard-grid">
        <KpiCard
          title="Total insured value"
          value={`£${fmtMoney(ingestionSummary.totalValue)}`}
          subtitle={`Across ${ingestionSummary.propertyCount} properties`}
          icon={KPI_ICONS.value}
        />
        <KpiCard
          title={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              Blocks detected
              <HoverTooltip
                tip="Our engine groups the properties in your SoV by shared parent UPRN and address to detect the distinct blocks across your portfolio."
                tipWidth={280}
                badgeStyle={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 15, height: 15, borderRadius: 999, background: "rgba(184,86,75,0.12)", color: "var(--terracotta-2)", fontSize: 10, fontWeight: 700, fontStyle: "italic", cursor: "help" }}
              >
                i
              </HoverTooltip>
            </span>
          }
          value={blocks.length}
          subtitle={
            <span style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
              <HoverTooltip
                tip="18 m+ or 7+ storeys — defined as higher-risk under the Building Safety Act 2022"
                badgeStyle={{ padding: "2px 8px", borderRadius: 6, background: "rgba(225,29,72,0.09)", border: "1px solid rgba(225,29,72,0.28)", fontWeight: 600, fontSize: 13, color: "var(--navy)", cursor: "default" }}
              >
                {highRiseBlocks} high-risk
              </HoverTooltip>
              <HoverTooltip
                tip="11–18 m or 4–6 storeys — medium-rise under Approved Document B (2022)"
                badgeStyle={{ padding: "2px 8px", borderRadius: 6, background: "rgba(245,158,11,0.10)", border: "1px solid rgba(245,158,11,0.30)", fontWeight: 600, fontSize: 13, color: "var(--navy)", cursor: "default" }}
              >
                {amberBlocks} mid-risk
              </HoverTooltip>
            </span>
          }
          tone="blue"
          icon={KPI_ICONS.blocks}
        />
        <KpiCard
          title={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              FRA evidence
              <HoverTooltip
                tip="Upload Fire Risk Assessment (FRA) reports for your blocks. Our engine reads each report and assigns the block its fire-risk rating based on the findings in the assessment."
                tipWidth={280}
                badgeStyle={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 15, height: 15, borderRadius: 999, background: "rgba(184,86,75,0.12)", color: "var(--terracotta-2)", fontSize: 10, fontWeight: 700, fontStyle: "italic", cursor: "help" }}
              >
                i
              </HoverTooltip>
            </span>
          }
          value={fireDocCounts.fra}
          subtitle={fireDocCounts.fra > 0 ? fireRiskSubtitle(fireRiskCounts.fra) : "No evidence uploaded"}
          tone="amber"
          icon={KPI_ICONS.fra}
        />
        <KpiCard
          title={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              FRAEW evidence
              <HoverTooltip
                tip="Upload Fire Risk Appraisal of External Walls (FRAEW) reports for your blocks. Our engine reads each report and assigns the block its external-wall (cladding) risk rating based on the findings."
                tipWidth={280}
                badgeStyle={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 15, height: 15, borderRadius: 999, background: "rgba(184,86,75,0.12)", color: "var(--terracotta-2)", fontSize: 10, fontWeight: 700, fontStyle: "italic", cursor: "help" }}
              >
                i
              </HoverTooltip>
            </span>
          }
          value={fireDocCounts.fraew}
          subtitle={fireDocCounts.fraew > 0 ? fireRiskSubtitle(fireRiskCounts.fraew) : "No evidence uploaded"}
          tone="amber"
          icon={KPI_ICONS.fraew}
        />
        <KpiCard
          title={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              Properties enhanced
              <HoverTooltip
                tip="The share of properties we matched to a verified UPRN from their address, then enriched with trusted external data — coordinates, EPC rating, building height, flood risk and listed-building status."
                tipWidth={280}
                badgeStyle={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 15, height: 15, borderRadius: 999, background: "rgba(184,86,75,0.12)", color: "var(--terracotta-2)", fontSize: 10, fontWeight: 700, fontStyle: "italic", cursor: "help" }}
              >
                i
              </HoverTooltip>
            </span>
          }
          value={`${enrichedPropertiesPct}%`}
          subtitle={`${enrichedPropertiesCount} of ${properties.length} properties`}
          tone="green"
          icon={KPI_ICONS.enhanced}
        />
      </div>

      <div
        className="dashboard-composition-map"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.2fr)",
          gap: 16,
          alignItems: "start",
        }}
      >
        <div className="card" style={{ alignSelf: "stretch", display: "flex", flexDirection: "column", minHeight: 505, maxHeight: 830, overflow: "hidden" }}>
          <div className="card-header row-between">
            <div className="card-title">
              {hasActivePropertySelection
                ? "Selected property details"
                : hasActiveBlockSelection
                ? "Selected block details"
                : "Selection details"}
            </div>
            <span className="pill pill-muted">
              {hasActivePropertySelection
                ? "Property selected"
                : hasActiveBlockSelection
                ? `Block : ${resolvedSelectedBlock?.block_id ?? resolvedSelectedBlock?.id ?? resolvedSelectedBlock?.name ?? "?"}`
                : "None"}
            </span>
          </div>

          <div ref={detailsScrollRef} className="details-body" style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
            <PropertyDetails
              property={resolvedSelectedProperty}
              selectedBlock={resolvedSelectedBlock}
              blockMode={!resolvedSelectedProperty}
              onSelectProperty={handleSelectProperty}
            />
          </div>
        </div>

        <div className="card" style={{ minHeight: 760, overflow: "visible", isolation: "isolate" }}>
          <div className="card-header row-between">
            <div>
              <div className="card-title">Block analysis map</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="pill pill-muted">{mappedBlocksCount} mapped blocks</span>
              {typeof onLoadMapData === "function" && (
                <button
                  className="btn"
                  style={{ padding: "4px 10px", fontSize: 12 }}
                  onClick={handleLoadMapData}
                  disabled={mapDataLoading}
                >
                  {mapDataLoading ? "Loading…" : "Refresh map"}
                </button>
              )}
            </div>
          </div>

          {mappedBlocksCount === 0 && !mapDataLoading && (
            <div style={{ padding: "10px 22px 0", fontSize: 13, color: "var(--muted)" }}>
              No block coordinates yet — enrichment may still be running.{" "}
              {typeof onLoadMapData === "function" && (
                <span
                  style={{ cursor: "pointer", textDecoration: "underline" }}
                  onClick={handleLoadMapData}
                >
                  Reload enriched data
                </span>
              )}
            </div>
          )}

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              margin: "12px 22px 0",
              padding: "9px 13px",
              borderRadius: 10,
              background: "var(--blush)",
              border: "1px solid var(--border-line)",
              color: "var(--navy)",
              fontSize: 12.5,
              lineHeight: 1.45,
            }}
          >
            <svg
              aria-hidden="true"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--terracotta-2)"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ flexShrink: 0 }}
            >
              <path d="M9 9l5 12 1.8-5.2L21 14z" />
              <path d="M7.2 2.2 8 5.1" />
              <path d="m5.1 7.2-2.9-.8" />
              <path d="M14 4.1 12 6" />
              <path d="m6 12-1.9 2" />
            </svg>
            <span>
              <strong style={{ fontWeight: 700 }}>Tip:</strong> click a block to see its summary, then click it again to list every flat inside it.
            </span>
          </div>

          <div className="map-wrap">
            <PortfolioMap
              properties={mapProperties}
              blocks={blocks}
              viewMode={mapMode}
              selectedBlock={resolvedSelectedBlock}
              selectedProperty={resolvedSelectedProperty}
              onSelectBlock={handleSelectBlock}
              onSelectProperty={handleSelectProperty}
              suppressFit={suppressMapFit}
            />
          </div>

          <div
            className="map-foot"
            style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}
          >
            <span>
              {hasActivePropertySelection
                ? `Viewing flat details for ${resolvedSelectedProperty?.block_reference ?? "selected block"}. Select another flat from the block popup or clear the selection.`
                : hasActiveBlockSelection
                ? "Block selected. Click the marker to open the flat list, or clear the selection below."
                : "Click a block circle on the map to inspect that block in detail."}
            </span>

            <button
              className="btn"
              onClick={handleClearMapSelection}
              style={{ visibility: hasActiveBlockSelection || hasActivePropertySelection ? "visible" : "hidden" }}
            >
              Clear selection
            </button>
          </div>
        </div>
      </div>

      <PortfolioInsightsPanel properties={properties} />

      <FireEvidencePanel
        fireDocuments={fireDocuments}
        loading={fireDocumentsLoading}
        onUploadNew={onUploadNew}
      />

      <PortfolioAnalysisWindow
        tenancyRows={tenancyRows}
        blockRows={blockRows}
        propertyTypeRows={propertyTypeRows}
        ageBandRows={ageBandRows}
      />

      <UnderwriterDocumentsPanel
        portfolioId={resolvedPortfolioId}
        propertyCount={ingestionSummary?.propertyCount || 0}
        properties={properties}
        blocks={blocks}
        onExport={handleExport}
      />
    </div>
  );
}

function UnderwriterDocumentsPanel({ portfolioId, propertyCount, properties, blocks, onExport }) {
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
