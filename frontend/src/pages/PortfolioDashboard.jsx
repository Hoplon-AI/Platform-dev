import React, { useEffect, useMemo, useState } from "react";

import PortfolioMap from "../components/PortfolioMap.jsx";
import PropertyDetails from "../components/PropertyDetails.jsx";

const fmtMoney = (n) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  return x.toLocaleString(undefined, { maximumFractionDigits: 0 });
};

const toNumberOrNull = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const readinessColor = (bandOrScore) => {
  const b = String(bandOrScore || "").toLowerCase();
  if (b.includes("green")) return "#22c55e";
  if (b.includes("amber") || b.includes("yellow")) return "#f59e0b";
  return "#ef4444";
};

const bandFromScore = (score) => {
  const s = Number(score) || 0;
  if (s >= 80) return "Green";
  if (s >= 50) return "Amber";
  return "Red";
};

const riskBandFromFireDocs = (propertyOrBlock) => {
  const fra = propertyOrBlock?.latest_fra ?? propertyOrBlock?.fire_documents?.fra ?? null;
  const fraew = propertyOrBlock?.latest_fraew ?? propertyOrBlock?.fire_documents?.fraew ?? null;

  const fraRisk = String(
    fra?.risk_level ?? fra?.rag_status ?? fra?.raw_rating ?? ""
  ).toLowerCase();

  const fraewRisk = String(
    fraew?.risk_level ?? fraew?.rag_status ?? fraew?.raw_rating ?? ""
  ).toLowerCase();

  const combined = `${fraRisk} ${fraewRisk}`;

  if (
    combined.includes("red") ||
    combined.includes("high") ||
    combined.includes("not acceptable") ||
    combined.includes("intolerable")
  ) {
    return "Red";
  }

  if (
    combined.includes("amber") ||
    combined.includes("medium") ||
    combined.includes("moderate") ||
    combined.includes("tolerable")
  ) {
    return "Amber";
  }

  if (
    combined.includes("green") ||
    combined.includes("low") ||
    combined.includes("acceptable") ||
    combined.includes("broadly acceptable")
  ) {
    return "Green";
  }

  return null;
};

const hasValidLatLon = (lat, lon) =>
  Number.isFinite(Number(lat)) &&
  Number.isFinite(Number(lon)) &&
  Number(lat) !== 0 &&
  Number(lon) !== 0;

const sameProperty = (a, b) => {
  if (!a || !b) return false;

  return (
    (a.id && b.id && a.id === b.id) ||
    (a.property_id && b.property_id && a.property_id === b.property_id) ||
    (a.property_reference &&
      b.property_reference &&
      a.property_reference === b.property_reference) ||
    (a.uprn && b.uprn && a.uprn === b.uprn)
  );
};

const sameBlock = (a, b) => {
  if (!a || !b) return false;

  return (
    (a.id && b.id && a.id === b.id) ||
    (a.block_id && b.block_id && a.block_id === b.block_id) ||
    (a.label && b.label && a.label === b.label) ||
    (a.name && b.name && a.name === b.name) ||
    (a.parent_uprn && b.parent_uprn && a.parent_uprn === b.parent_uprn)
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
    combined.includes("flat") ||
    combined.includes("apartment") ||
    combined.includes("maisonette")
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

function KpiCard({ title, value, subtitle, tone = "default" }) {
  return (
    <div className={`dashboard-card dashboard-card-${tone}`}>
      <div className="dashboard-card-title">{title}</div>
      <div className="dashboard-card-value">{value}</div>
      {subtitle ? <div className="dashboard-card-sub">{subtitle}</div> : null}
    </div>
  );
}

function ConfidenceBar({ label, value }) {
  const safeValue = Math.max(0, Math.min(100, Number(value) || 0));

  return (
    <div className="bar">
      <div className="bar-top">
        <div className="bar-label">{label}</div>
        <div className="bar-value">{safeValue}%</div>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${safeValue}%` }} />
      </div>
    </div>
  );
}

function WorkspaceTabs({ activeTab, onChange }) {
  const tabs = [
    { id: "overview", label: "Portfolio overview" },
    { id: "block-analysis", label: "Block analysis" },
  ];

  return (
    <div
      className="card"
      style={{
        padding: 12,
        display: "flex",
        gap: 8,
        alignItems: "center",
        flexWrap: "wrap",
      }}
    >
      {tabs.map((tab) => {
        const active = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            className={`btn ${active ? "btn-primary" : ""}`}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

function PortfolioCompositionCard({ properties, blocks }) {
  const totalUnits = properties.length;

  const houses = properties.filter((p) => inferPortfolioClass(p) === "Houses");
  const flats = properties.filter((p) => inferPortfolioClass(p) === "Flats");
  const other = properties.filter((p) => inferPortfolioClass(p) === "Other");

  const blockCount = blocks.length;
  const thirdPartyLikeBlocks = blocks.filter(
    (block) => !block.parent_uprn && block.count > 1
  ).length;

  const renderRow = (label, count, total, tone = "#64748b", meta = null) => {
    const pct = total > 0 ? Math.round((count / total) * 100) : 0;
    return (
      <div style={{ marginBottom: 14 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "16px 1fr auto",
            gap: 10,
            alignItems: "center",
            marginBottom: 6,
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: 999,
              background: tone,
              marginLeft: 4,
            }}
          />
          <div style={{ fontWeight: 600 }}>{label}</div>
          <div className="muted">
            {count} {label === "Blocks" ? "blocks" : "units"} / {pct}%
          </div>
        </div>

        <div
          style={{
            height: 8,
            background: "rgba(15,23,42,0.08)",
            borderRadius: 999,
            overflow: "hidden",
            marginLeft: 26,
          }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: "100%",
              background: tone,
              borderRadius: 999,
            }}
          />
        </div>

        {meta ? (
          <div className="muted" style={{ marginTop: 6, marginLeft: 26 }}>
            {meta}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div className="card">
      <div className="card-header row-between">
        <div>
          <div className="card-title">Portfolio Composition</div>
          <div className="card-subtitle">
            Summary split for the whole ingested SoV rather than raw row-by-row
            tables.
          </div>
        </div>
        <span className="pill pill-muted">{totalUnits} units</span>
      </div>

      {renderRow("Houses", houses.length, totalUnits, "#3b82f6")}
      {renderRow("Flats", flats.length, totalUnits, "#6366f1")}
      {renderRow(
        "Blocks",
        blockCount,
        Math.max(blockCount, 1),
        "#f59e0b",
        `${thirdPartyLikeBlocks} grouped blocks without clear parent UPRN`
      )}

      {other.length > 0 ? (
        <div
          style={{
            marginTop: 8,
            padding: 12,
            borderRadius: 12,
            background: "rgba(245,158,11,0.12)",
            border: "1px solid rgba(245,158,11,0.22)",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Other asset types</div>
          <div className="muted">
            {other.length} properties could not be cleanly classified as houses
            or flats from the current SoV fields.
          </div>
        </div>
      ) : null}
    </div>
  );
}

function FireRiskOverviewCard({ blocks }) {
  const redBlocks = blocks.filter((b) => riskBandFromFireDocs(b) === "Red").length;
  const amberBlocks = blocks.filter((b) => riskBandFromFireDocs(b) === "Amber").length;
  const greenBlocks = blocks.filter((b) => riskBandFromFireDocs(b) === "Green").length;
  const unassessedBlocks = blocks.length - redBlocks - amberBlocks - greenBlocks;

  const overdueActions = blocks.reduce((sum, block) => {
    const fra = block.latest_fra ?? block.fire_documents?.fra;
    return sum + (Number(fra?.overdue_actions ?? fra?.overdue_action_count) || 0);
  }, 0);

  const noDateActions = blocks.reduce((sum, block) => {
    const fra = block.latest_fra ?? block.fire_documents?.fra;
    return sum + (Number(fra?.no_date_actions ?? fra?.no_date_action_count) || 0);
  }, 0);

  const inProgressActions = blocks.reduce((sum, block) => {
    const fra = block.latest_fra ?? block.fire_documents?.fra;
    return sum + (Number(fra?.outstanding_actions ?? fra?.outstanding_action_count) || 0);
  }, 0);

  const itemStyle = (tone) => ({
    padding: 12,
    borderRadius: 12,
    background: `${tone}16`,
    border: `1px solid ${tone}33`,
  });

  return (
    <div className="card">
      <div className="card-header row-between">
        <div>
          <div className="card-title">FRA Status & Remediation</div>
          <div className="card-subtitle">
            Portfolio-level summary of linked FRA and FRAEW extraction results.
          </div>
        </div>
        <span className="pill pill-muted">{blocks.length} blocks</span>
      </div>

      <div style={{ display: "grid", gap: 10 }}>
        <div
          style={{
            padding: 12,
            borderRadius: 12,
            background: "rgba(239,68,68,0.12)",
            border: "1px solid rgba(239,68,68,0.2)",
            display: "flex",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ fontWeight: 700 }}>RED</div>
          <div>{redBlocks} blocks</div>
        </div>

        <div
          style={{
            padding: 12,
            borderRadius: 12,
            background: "rgba(245,158,11,0.12)",
            border: "1px solid rgba(245,158,11,0.2)",
            display: "flex",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ fontWeight: 700 }}>AMBER</div>
          <div>{amberBlocks} blocks</div>
        </div>

        <div
          style={{
            padding: 12,
            borderRadius: 12,
            background: "rgba(34,197,94,0.12)",
            border: "1px solid rgba(34,197,94,0.2)",
            display: "flex",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ fontWeight: 700 }}>GREEN</div>
          <div>{greenBlocks} blocks</div>
        </div>

        <div
          style={{
            padding: 12,
            borderRadius: 12,
            background: "rgba(100,116,139,0.10)",
            border: "1px solid rgba(100,116,139,0.15)",
            display: "flex",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ fontWeight: 700 }}>UNASSESSED</div>
          <div>{unassessedBlocks} blocks</div>
        </div>
      </div>

      <div
        style={{
          marginTop: 16,
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 12,
        }}
      >
        <div style={itemStyle("#ef4444")}>
          <div className="dashboard-card-value" style={{ fontSize: 24 }}>
            {overdueActions}
          </div>
          <div className="muted">Overdue</div>
        </div>
        <div style={itemStyle("#f59e0b")}>
          <div className="dashboard-card-value" style={{ fontSize: 24 }}>
            {noDateActions}
          </div>
          <div className="muted">No date</div>
        </div>
        <div style={itemStyle("#64748b")}>
          <div className="dashboard-card-value" style={{ fontSize: 24 }}>
            {inProgressActions}
          </div>
          <div className="muted">In progress</div>
        </div>
      </div>
    </div>
  );
}

function MiniSummaryTable({ title, subtitle, rows, columns }) {
  return (
    <div
      style={{
        background: "rgba(15,23,42,0.02)",
        border: "1px solid rgba(15,23,42,0.06)",
        borderRadius: 16,
        padding: 14,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{title}</div>
      {subtitle ? (
        <div className="muted" style={{ marginBottom: 10 }}>
          {subtitle}
        </div>
      ) : null}

      {!rows.length ? (
        <div className="muted">No data available.</div>
      ) : (
        <div className="table-wrap">
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

function PortfolioAnalysisWindow({
  tenancyRows,
  blockRows,
  propertyTypeRows,
  ageBandRows,
}) {
  return (
    <div className="card">
      <div className="card-header row-between">
        <div>
          <div className="card-title">Portfolio Analysis</div>
          <div className="card-subtitle">
            Compact whole-portfolio analysis for tenancy, block reference,
            property type, and age.
          </div>
        </div>
        <span className="pill pill-muted">Whole SoV summary</span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 16,
        }}
      >
        <MiniSummaryTable
          title="By tenancy / ownership"
          rows={tenancyRows.slice(0, 6)}
          columns={[
            { key: "label", label: "Type" },
            { key: "count", label: "Units" },
            {
              key: "totalValue",
              label: "Sum insured",
              render: (row) => `£${fmtMoney(row.totalValue)}`,
            },
          ]}
        />

        <MiniSummaryTable
          title="By block reference"
          rows={blockRows.slice(0, 6)}
          columns={[
            { key: "label", label: "Block" },
            { key: "count", label: "Units" },
            {
              key: "totalValue",
              label: "TIV",
              render: (row) => `£${fmtMoney(row.totalValue)}`,
            },
          ]}
        />

        <MiniSummaryTable
          title="By property type"
          rows={propertyTypeRows.slice(0, 6)}
          columns={[
            { key: "label", label: "Type" },
            { key: "count", label: "Units" },
            {
              key: "totalValue",
              label: "Sum insured",
              render: (row) => `£${fmtMoney(row.totalValue)}`,
            },
          ]}
        />

        <MiniSummaryTable
          title="By age banding"
          rows={ageBandRows.slice(0, 6)}
          columns={[
            { key: "label", label: "Age" },
            { key: "count", label: "Units" },
            {
              key: "totalValue",
              label: "Sum insured",
              render: (row) => `£${fmtMoney(row.totalValue)}`,
            },
          ]}
        />
      </div>
    </div>
  );
}

function FireDocsPanel({
  latestFireRiskPayload,
  fireDocumentsLoading,
  selectedProperty,
  selectedBlock,
}) {
  const fra =
    latestFireRiskPayload?.fra ||
    selectedProperty?.latest_fra ||
    selectedProperty?.fire_documents?.fra ||
    selectedBlock?.latest_fra ||
    selectedBlock?.fire_documents?.fra ||
    null;

  const fraew =
    latestFireRiskPayload?.fraew ||
    selectedProperty?.latest_fraew ||
    selectedProperty?.fire_documents?.fraew ||
    selectedBlock?.latest_fraew ||
    selectedBlock?.fire_documents?.fraew ||
    null;

  const extractionErrors = latestFireRiskPayload?.extraction_errors || [];

  if (!fra && !fraew && !fireDocumentsLoading && !latestFireRiskPayload) {
    return (
      <div className="card">
        <div className="card-header row-between">
          <div>
            <div className="card-title">Fire risk documents</div>
            <div className="card-subtitle">
              Upload FRA or FRAEW PDFs to surface extracted fire-risk data here.
            </div>
          </div>
          <span className="pill pill-muted">Awaiting PDF</span>
        </div>
        <div className="muted">
          No FRA or FRAEW results are attached yet for the current selection.
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header row-between">
        <div>
          <div className="card-title">Fire risk documents</div>
          <div className="card-subtitle">
            FRA and FRAEW extraction results linked to the selected block or
            property.
          </div>
        </div>
        <span className="pill pill-muted">
          {fireDocumentsLoading ? "Loading…" : "PDF linked"}
        </span>
      </div>

      {extractionErrors.length > 0 && (
        <div className="pill band-red" style={{ marginBottom: 12 }}>
          {extractionErrors.join(" · ")}
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 16,
        }}
      >
        <div className="details-block">
          <div className="details-h">FRA</div>
          <div className="details-sub">
            <b>Risk:</b>{" "}
            {fra?.risk_level || fra?.rag_status || fra?.raw_rating || "—"}
          </div>
          <div className="details-sub">
            <b>Assessment date:</b> {fra?.assessment_date || "—"}
          </div>
          <div className="details-sub">
            <b>Valid until:</b> {fra?.assessment_valid_until || "—"}
          </div>
          <div className="details-sub">
            <b>In date:</b>{" "}
            {fra?.is_in_date === true ? "Yes" : fra?.is_in_date === false ? "No" : "—"}
          </div>
          <div className="details-sub">
            <b>Assessor:</b> {fra?.assessor_name || "—"}
          </div>
          <div className="details-sub">
            <b>Company:</b> {fra?.assessor_company || "—"}
          </div>
          <div className="details-sub">
            <b>Evacuation:</b> {fra?.evacuation_strategy || "—"}
          </div>
          <div className="details-sub">
            <b>Total actions:</b>{" "}
            {fra?.total_actions ?? fra?.total_action_count ?? "—"}
          </div>
          <div className="details-sub">
            <b>Overdue actions:</b>{" "}
            {fra?.overdue_actions ?? fra?.overdue_action_count ?? "—"}
          </div>
        </div>

        <div className="details-block">
          <div className="details-h">FRAEW</div>
          <div className="details-sub">
            <b>Risk:</b>{" "}
            {fraew?.risk_level || fraew?.rag_status || fraew?.raw_rating || "—"}
          </div>
          <div className="details-sub">
            <b>Assessment date:</b> {fraew?.assessment_date || "—"}
          </div>
          <div className="details-sub">
            <b>Valid until:</b> {fraew?.assessment_valid_until || "—"}
          </div>
          <div className="details-sub">
            <b>In date:</b>{" "}
            {fraew?.is_in_date === true
              ? "Yes"
              : fraew?.is_in_date === false
              ? "No"
              : "—"}
          </div>
          <div className="details-sub">
            <b>Height:</b>{" "}
            {Number.isFinite(Number(fraew?.building_height_m))
              ? `${Number(fraew.building_height_m).toFixed(1)} m`
              : "—"}
          </div>
          <div className="details-sub">
            <b>Combustible cladding:</b>{" "}
            {fraew?.combustible_cladding === true ||
            fraew?.has_combustible_cladding === true
              ? "Yes"
              : fraew?.combustible_cladding === false ||
                fraew?.has_combustible_cladding === false
              ? "No"
              : "—"}
          </div>
          <div className="details-sub">
            <b>PAS 9980 compliant:</b>{" "}
            {fraew?.pas_9980_compliant === true
              ? "Yes"
              : fraew?.pas_9980_compliant === false
              ? "No"
              : "—"}
          </div>
          <div className="details-sub">
            <b>Interim measures:</b>{" "}
            {fraew?.interim_measures_required === true
              ? "Required"
              : fraew?.interim_measures_required === false
              ? "Not required"
              : "—"}
          </div>
          <div className="details-sub">
            <b>Remediation required:</b>{" "}
            {fraew?.remediation_required === true ||
            fraew?.has_remedial_actions === true
              ? "Yes"
              : fraew?.remediation_required === false ||
                fraew?.has_remedial_actions === false
              ? "No"
              : "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

function BlockListPanel({
  blocks,
  selectedBlockId,
  onSelectBlock,
  selectedProperty,
}) {
  return (
    <div className="card">
      <div className="card-header row-between">
        <div>
          <div className="card-title">Block analysis list</div>
          <div className="card-subtitle">
            Drill into grouped blocks without rendering the whole SoV as a long
            table.
          </div>
        </div>
        <span className="pill pill-muted">
          Top {Math.min(blocks.length, 20)} blocks
        </span>
      </div>

      {!blocks.length ? (
        <div className="muted">No block-level groups are available yet.</div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Block</th>
                <th>Properties</th>
                <th>Total value</th>
                <th>Fire risk</th>
                <th>Max height</th>
              </tr>
            </thead>
            <tbody>
              {blocks.slice(0, 20).map((block) => {
                const fireRisk = riskBandFromFireDocs(block);
                return (
                  <tr
                    key={block.id}
                    onClick={() => onSelectBlock?.(block)}
                    style={{
                      cursor: "pointer",
                      background:
                        selectedBlockId === block.id && !selectedProperty
                          ? "rgba(59,130,246,0.08)"
                          : "transparent",
                    }}
                  >
                    <td>{block.label}</td>
                    <td>{block.count}</td>
                    <td>£{fmtMoney(block.totalValue)}</td>
                    <td>
                      {fireRisk ? (
                        <span
                          className="pill"
                          style={{
                            background: `${readinessColor(fireRisk)}22`,
                            color: readinessColor(fireRisk),
                            border: `1px solid ${readinessColor(fireRisk)}33`,
                          }}
                        >
                          {fireRisk}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      {Number.isFinite(Number(block.maxHeight))
                        ? `${Number(block.maxHeight).toFixed(1)} m`
                        : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function DocumentPanel() {
  return (
    <div className="card">
      <div className="card-header row-between">
        <div>
          <div className="card-title">Documents & exports</div>
          <div className="card-subtitle">
            Hook these buttons to your export router once wired.
          </div>
        </div>
        <span className="pill pill-muted">Backend-ready</span>
      </div>

      <div className="document-grid">
        <button className="btn">Export Underwriter Pack</button>
        <button className="btn">Export Doc A</button>
        <button className="btn">Export Doc B</button>
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
}) {
  const properties = ingestionResult?.properties || [];
  const [workspaceTab, setWorkspaceTab] = useState("overview");
  const [selectedBlock, setSelectedBlock] = useState(null);
  const [selectedProperty, setSelectedProperty] = useState(null);

  const blocks = useMemo(() => {
    if (!properties.length) return [];

    const grouped = new Map();

    properties.forEach((property) => {
      const key =
        property.block_reference ||
        property.parent_uprn ||
        property.uprn ||
        property.property_reference ||
        property.id;

      if (!grouped.has(key)) {
        grouped.set(key, []);
      }

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

        const totalValue = items.reduce(
          (sum, p) => sum + (Number(p.sum_insured) || 0),
          0
        );

        const avgReadiness =
          items.reduce((sum, p) => sum + (Number(p.readiness_score) || 0), 0) /
          Math.max(items.length, 1);

        const maxHeight = items.reduce((max, p) => {
          const height = Number(p.height_m);
          return Number.isFinite(height) ? Math.max(max, height) : max;
        }, 0);

        const representativeProperty =
          mappable[0] || items.find((p) => p.uprn) || items[0] || null;

        const latestFra =
          items.find((p) => p.latest_fra)?.latest_fra ||
          items.find((p) => p.fire_documents?.fra)?.fire_documents?.fra ||
          null;

        const latestFraew =
          items.find((p) => p.latest_fraew)?.latest_fraew ||
          items.find((p) => p.fire_documents?.fraew)?.fire_documents?.fraew ||
          null;

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
          avgReadiness,
          maxHeight,
          parent_uprn:
            items.find((p) => p.parent_uprn)?.parent_uprn ||
            items.find((p) => p.uprn)?.uprn ||
            null,
          block_reference: key || "",
          representativeProperty,
          latest_fra: latestFra,
          latest_fraew: latestFraew,
          fire_documents: {
            fra: latestFra,
            fraew: latestFraew,
          },
        };
      })
      .filter((block) => block.hasValidCoords)
      .sort((a, b) => b.totalValue - a.totalValue);
  }, [properties]);

  const tenancyRows = useMemo(
    () =>
      buildBreakdown(
        properties,
        (property) => property.occupancy_type || "Not recorded",
        (property) => property.sum_insured
      ),
    [properties]
  );

  const blockRows = useMemo(
    () =>
      blocks.map((block) => ({
        label: block.label || "Unassigned block",
        count: block.count || 0,
        totalValue: block.totalValue || 0,
      })),
    [blocks]
  );

  const propertyTypeRows = useMemo(
    () =>
      buildBreakdown(
        properties,
        (property) => property.property_type || inferPortfolioClass(property),
        (property) => property.sum_insured
      ),
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

  useEffect(() => {
    if (!properties.length) {
      setSelectedBlock(null);
      setSelectedProperty(null);
      return;
    }

    if (selectedProperty) {
      const matchingProperty = properties.find((p) => sameProperty(p, selectedProperty));
      if (!matchingProperty) {
        setSelectedProperty(null);
      }
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
      return (
        blocks.find((block) =>
          block.properties.some((p) => sameProperty(p, resolvedSelectedProperty))
        ) || null
      );
    }

    if (!selectedBlock) return null;
    return blocks.find((b) => sameBlock(b, selectedBlock)) || null;
  }, [blocks, selectedBlock, resolvedSelectedProperty]);

  const selectedBlockId = resolvedSelectedBlock?.id ?? null;

  const avgReadiness = ingestionSummary?.avgReadiness ?? 0;
  const uprnMatchPct = ingestionSummary?.uprnMatchPct ?? 0;
  const addrCompletenessPct = ingestionSummary?.addrCompletenessPct ?? 0;
  const geoCompletenessPct = ingestionSummary?.geoCompletenessPct ?? 0;
  const sovCompletenessPct = ingestionSummary?.sovCompletenessPct ?? 0;

  const highRiseBlocks = blocks.filter((b) => Number(b.maxHeight) > 18).length;
  const amberBlocks = blocks.filter(
    (b) => Number(b.maxHeight) > 11 && Number(b.maxHeight) <= 18
  ).length;

  const mappedBlocksCount = blocks.filter((b) => b.hasValidCoords).length;
  const blocksWithFireDocs = blocks.filter((b) => b.latest_fra || b.latest_fraew).length;
  const redFireRiskCount = properties.filter(
    (p) => riskBandFromFireDocs(p) === "Red"
  ).length;

  const handleSelectBlock = (block) => {
    if (!block) {
      setSelectedBlock(null);
      setSelectedProperty(null);
      return;
    }

    const matchingBlock = blocks.find((b) => sameBlock(b, block)) || block;
    setSelectedBlock(matchingBlock);
    setSelectedProperty(null);
    setWorkspaceTab("block-analysis");
  };

  const handleSelectProperty = (property) => {
    if (!property) {
      setSelectedProperty(null);
      return;
    }

    const matchingProperty =
      properties.find((p) => sameProperty(p, property)) || property;
    setSelectedProperty(matchingProperty);

    const parentBlock =
      blocks.find((block) =>
        block.properties.some((p) => sameProperty(p, matchingProperty))
      ) || null;

    setSelectedBlock(parentBlock);
    setWorkspaceTab("block-analysis");
  };

  const handleClearMapSelection = () => {
    setSelectedBlock(null);
    setSelectedProperty(null);
  };

  if (!ingestionSummary) {
    return (
      <div className="content-wrap">
        <div className="card">
          <div className="empty-state">
            No portfolio loaded yet. Upload an SoV file to begin.
          </div>
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary" onClick={onUploadNew}>
              Upload SoV
            </button>
          </div>
        </div>
      </div>
    );
  }

  const showOverview = workspaceTab === "overview";
  const showBlockAnalysis = workspaceTab === "block-analysis";

  const hasActiveBlockSelection = Boolean(resolvedSelectedBlock);
  const hasActivePropertySelection = Boolean(resolvedSelectedProperty);

  const overviewMapMode = hasActiveBlockSelection ? "properties" : "blocks";
  const blockAnalysisMapMode = hasActiveBlockSelection ? "properties" : "blocks";

  const overviewMapProperties =
    overviewMapMode === "properties"
      ? resolvedSelectedBlock?.properties || []
      : properties;

  const blockAnalysisMapProperties =
    blockAnalysisMapMode === "properties"
      ? resolvedSelectedBlock?.properties || []
      : properties;

  return (
    <div className="content-wrap">
      <div className="main-head">
        <div>
          <div className="page-title">Portfolio Overview</div>
          <div className="page-sub">
            Underwriter-focused dashboard using ingested portfolio, enrichment,
            block grouping, and linked fire-risk PDFs.
          </div>
        </div>

        <div className="actions">
          <button className="btn" onClick={onUploadNew}>
            Upload new SoV
          </button>
          <button className="btn btn-primary">Flag for review</button>
        </div>
      </div>

      <div className="card banner">
        <div className="banner-left">
          <div
            className="pill"
            style={{
              background: `${readinessColor(avgReadiness)}22`,
              color: readinessColor(avgReadiness),
              border: `1px solid ${readinessColor(avgReadiness)}33`,
            }}
          >
            {bandFromScore(avgReadiness).toUpperCase()}
          </div>

          <div className="banner-title">Portfolio underwriting snapshot</div>

          <div className="banner-sub">
            This view shows portfolio value, UPRN confidence, mappable coverage,
            block spatial analysis, and attached FRA/FRAEW extraction results.
          </div>

          <div className="banner-actions">
            <button className="btn btn-primary">Generate action plan</button>
            <button className="btn">Open evidence summary</button>
          </div>
        </div>

        <div className="banner-right">
          <div className="donut">
            <div
              className="donut-ring"
              style={{
                background: `conic-gradient(${readinessColor(
                  avgReadiness
                )} ${avgReadiness}%, rgba(15,23,42,.10) 0)`,
              }}
            />
            <div className="donut-center">
              <div className="donut-value">{avgReadiness}</div>
              <div className="donut-sub">/ 100</div>
            </div>
            <div className="donut-caption">
              <span
                className="pill"
                style={{
                  background: `${readinessColor(avgReadiness)}22`,
                  color: readinessColor(avgReadiness),
                }}
              >
                {bandFromScore(avgReadiness)}
              </span>
              <span className="muted">Portfolio readiness</span>
            </div>
          </div>
        </div>
      </div>

      <div className="dashboard-grid">
        <KpiCard
          title="Total insured value"
          value={`£${fmtMoney(ingestionSummary.totalValue)}`}
          subtitle={`Across ${ingestionSummary.propertyCount} properties`}
        />
        <KpiCard
          title="Blocks detected"
          value={blocks.length}
          subtitle={`${highRiseBlocks} high-rise · ${amberBlocks} mid-rise`}
          tone="blue"
        />
        <KpiCard
          title="UPRN coverage"
          value={`${uprnMatchPct}%`}
          subtitle="Matched properties with UPRN present"
          tone="green"
        />
        <KpiCard
          title="Fire-risk PDFs linked"
          value={blocksWithFireDocs}
          subtitle={`${redFireRiskCount} red-risk properties flagged`}
          tone="amber"
        />
      </div>

      <div className="card confidence-card">
        <div className="card-header row-between">
          <div>
            <div className="card-title">Confidence & completeness</div>
            <div className="card-subtitle">
              Mapped directly from your ingestion utilities and linked document
              extraction fields.
            </div>
          </div>
          <span className="pill pill-muted">Portfolio QA</span>
        </div>

        <div className="bars">
          <ConfidenceBar
            label="Addresses & UPRN verification"
            value={Math.round((addrCompletenessPct + uprnMatchPct) / 2)}
          />
          <ConfidenceBar label="Geo coverage" value={geoCompletenessPct} />
          <ConfidenceBar label="SOV completeness" value={sovCompletenessPct} />
        </div>
      </div>

      <WorkspaceTabs activeTab={workspaceTab} onChange={setWorkspaceTab} />

      {showOverview && (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 16,
            }}
          >
            <PortfolioCompositionCard properties={properties} blocks={blocks} />
            <FireRiskOverviewCard blocks={blocks} />
          </div>

          <PortfolioAnalysisWindow
            tenancyRows={tenancyRows}
            blockRows={blockRows}
            propertyTypeRows={propertyTypeRows}
            ageBandRows={ageBandRows}
          />

          <FireDocsPanel
            latestFireRiskPayload={latestFireRiskPayload}
            fireDocumentsLoading={fireDocumentsLoading}
            selectedProperty={resolvedSelectedProperty}
            selectedBlock={resolvedSelectedBlock}
          />

          <div className="two-col">
            <div className="card">
              <div className="card-header row-between">
                <div>
                  <div className="card-title">Block analysis map</div>
                  <div className="card-subtitle">
                    Clustered map view aligned to the latest feedback style,
                    with clear block counts at map level and colour-coded
                    properties once a block is selected.
                  </div>
                </div>
                <span className="pill pill-muted">
                  {mappedBlocksCount} mapped blocks
                </span>
              </div>

              <div className="map-wrap">
                <PortfolioMap
                  properties={overviewMapProperties}
                  blocks={blocks}
                  viewMode={overviewMapMode}
                  selectedBlock={resolvedSelectedBlock}
                  selectedProperty={resolvedSelectedProperty}
                  onSelectBlock={handleSelectBlock}
                  onSelectProperty={handleSelectProperty}
                />
              </div>

              <div
                className="map-foot"
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
                <span>
                  {overviewMapMode === "properties"
                    ? "Zoomed into the selected block. Coloured property dots show the property mix inside that block."
                    : "Click a block circle on the map to inspect that block in detail."}
                </span>

                {hasActiveBlockSelection ? (
                  <button className="btn" onClick={handleClearMapSelection}>
                    Back to blocks
                  </button>
                ) : null}
              </div>
            </div>

            <div className="card">
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
                    ? "Block selected"
                    : "None"}
                </span>
              </div>

              <div
                className="details-body"
                style={{
                  maxHeight: 620,
                  overflowY: "auto",
                  paddingRight: 6,
                }}
              >
                <PropertyDetails
                  property={resolvedSelectedProperty}
                  selectedBlock={resolvedSelectedBlock}
                  blockMode={!resolvedSelectedProperty}
                />
              </div>
            </div>
          </div>

          <DocumentPanel />
        </>
      )}

      {showBlockAnalysis && (
        <>
          <div className="two-col">
            <div className="card">
              <div className="card-header row-between">
                <div>
                  <div className="card-title">Block analysis map</div>
                  <div className="card-subtitle">
                    Clustered portfolio map with count-led block circles at
                    outset, then colour-coded properties inside the selected
                    block.
                  </div>
                </div>
                <span className="pill pill-muted">
                  {mappedBlocksCount} mapped blocks
                </span>
              </div>

              <div className="map-wrap">
                <PortfolioMap
                  properties={blockAnalysisMapProperties}
                  blocks={blocks}
                  viewMode={blockAnalysisMapMode}
                  selectedBlock={resolvedSelectedBlock}
                  selectedProperty={resolvedSelectedProperty}
                  onSelectBlock={handleSelectBlock}
                  onSelectProperty={handleSelectProperty}
                />
              </div>

              <div
                className="map-foot"
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
                <span>
                  {blockAnalysisMapMode === "properties"
                    ? "Zoomed into the selected block. Property membership and coloured property types are shown on the map and in the right-hand panel."
                    : "Click a block to inspect that block circle. Property membership is shown in the right-hand details panel."}
                </span>

                {hasActiveBlockSelection ? (
                  <button className="btn" onClick={handleClearMapSelection}>
                    Back to blocks
                  </button>
                ) : null}
              </div>
            </div>

            <div className="card">
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
                    ? "Block selected"
                    : "None"}
                </span>
              </div>

              <div
                className="details-body"
                style={{
                  maxHeight: 620,
                  overflowY: "auto",
                  paddingRight: 6,
                }}
              >
                <PropertyDetails
                  property={resolvedSelectedProperty}
                  selectedBlock={resolvedSelectedBlock}
                  blockMode={!resolvedSelectedProperty}
                />
              </div>
            </div>
          </div>

          <FireDocsPanel
            latestFireRiskPayload={latestFireRiskPayload}
            fireDocumentsLoading={fireDocumentsLoading}
            selectedProperty={resolvedSelectedProperty}
            selectedBlock={resolvedSelectedBlock}
          />

          <BlockListPanel
            blocks={blocks}
            selectedBlockId={selectedBlockId}
            onSelectBlock={handleSelectBlock}
            selectedProperty={resolvedSelectedProperty}
          />
        </>
      )}
    </div>
  );
}