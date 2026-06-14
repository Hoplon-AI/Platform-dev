import React, { useEffect, useMemo, useState } from "react";

import PortfolioMap from "../components/PortfolioMap.jsx";
import PropertyDetails from "../components/PropertyDetails.jsx";

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
    summary:
      primary?.summary ??
      primary?.executive_summary ??
      primary?.findings_summary ??
      primary?.interim_measures_detail ??
      "No summary extracted.",
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

function KpiCard({ title, value, subtitle, tone = "default" }) {
  return (
    <div className={`dashboard-card dashboard-card-${tone}`}>
      <div className="dashboard-card-title">{title}</div>
      <div className="dashboard-card-value">{value}</div>
      {subtitle ? <div className="dashboard-card-sub">{subtitle}</div> : null}
    </div>
  );
}

function PortfolioCompositionCard({ properties, blocks, onSelectBlock, selectedBlock }) {
  const [flatsOpen, setFlatsOpen] = useState(false);
  const [blocksOpen, setBlocksOpen] = useState(false);
  const [blocksSearch, setBlocksSearch] = useState("");
  const [blocksSearchDebounced, setBlocksSearchDebounced] = useState("");
  const [otherOpen, setOtherOpen] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setBlocksSearchDebounced(blocksSearch), 150);
    return () => clearTimeout(t);
  }, [blocksSearch]);

  const totalUnits = properties.length;
  const houses = properties.filter((p) => inferPortfolioClass(p) === "Houses");
  const flats = properties.filter((p) => inferPortfolioClass(p) === "Flats");
  const other = properties.filter((p) => inferPortfolioClass(p) === "Other");
  const blockCount = blocks.length;
  const thirdPartyLikeBlocks = blocks.filter(
    (block) => !block.parent_uprn && block.count > 1
  ).length;

  const typeBreakdown = (items) => {
    const counts = new Map();
    items.forEach((p) => {
      const key = p.property_type || p.type || "Unknown";
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([label, count]) => ({ label, count }));
  };

  const flatTypeBreakdown = useMemo(() => typeBreakdown(flats), [flats]);
  const otherTypeBreakdown = useMemo(() => typeBreakdown(other), [other]);

  const renderRow = (label, count, _total, tone = "#64748b", meta = null) => (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "16px 1fr auto", gap: 10, alignItems: "center" }}>
        <div style={{ width: 8, height: 8, borderRadius: 999, background: tone, marginLeft: 4 }} />
        <div style={{ fontWeight: 600 }}>{label}</div>
        <div className="muted">{count} {label === "Blocks" ? "blocks" : "units"}</div>
      </div>
      {meta ? <div className="muted" style={{ marginTop: 6, marginLeft: 26 }}>{meta}</div> : null}
    </div>
  );

  const renderExpandableRow = (label, items, tone, open, setOpen) => (
    <div style={{ marginBottom: 14 }}>
      <div
        style={{ display: "grid", gridTemplateColumns: "16px 1fr auto auto", gap: 10, alignItems: "center", cursor: "pointer", userSelect: "none" }}
        onClick={() => setOpen((o) => !o)}
      >
        <div style={{ width: 8, height: 8, borderRadius: 999, background: tone, marginLeft: 4 }} />
        <div style={{ fontWeight: 600 }}>{label}</div>
        <div className="muted">{items.length} units</div>
        <div className="muted" style={{ fontSize: 11, paddingRight: 2 }}>{open ? "▲" : "▼"}</div>
      </div>
      {open && (
        <div style={{ marginTop: 8, marginLeft: 26, borderLeft: `2px solid ${tone}33`, paddingLeft: 12, paddingRight: 18 }}>
          {typeBreakdown(items).map(({ label: subLabel, count }) => (
            <div key={subLabel} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", fontSize: 13 }}>
              <span className="muted">{subLabel}</span>
              <span className="muted">{count}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="card" style={{ height: "100%" }}>
      <div className="card-header row-between">
        <div>
          <div className="card-title">Portfolio Composition</div>
          {/* <div className="card-subtitle">
            Summary split for the whole ingested SoV rather than raw row-by-row tables.
          </div> */}
        </div>
        <span className="pill pill-muted">{totalUnits} units</span>
      </div>

      <div className="card-body">
        {renderRow("Houses", houses.length, totalUnits, "#3b82f6")}
        {renderExpandableRow("Flats", flats, "#6366f1", flatsOpen, setFlatsOpen)}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{ display: "grid", gridTemplateColumns: "16px 1fr auto auto", gap: 10, alignItems: "center", cursor: "pointer", userSelect: "none" }}
            onClick={() => setBlocksOpen((o) => !o)}
          >
            <div style={{ width: 8, height: 8, borderRadius: 999, background: "#f59e0b", marginLeft: 4 }} />
            <div style={{ fontWeight: 600 }}>Blocks</div>
            <div className="muted">{blockCount} blocks</div>
            <div className="muted" style={{ fontSize: 11, paddingRight: 2 }}>{blocksOpen ? "▲" : "▼"}</div>
          </div>
          {blocksOpen && (
            <div style={{ marginTop: 8, marginLeft: 26 }}>
              <input
                type="text"
                placeholder="Search block ID…"
                value={blocksSearch}
                onChange={(e) => setBlocksSearch(e.target.value)}
                style={{
                  width: "100%",
                  padding: "5px 10px",
                  marginBottom: 8,
                  fontSize: 13,
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                  background: "var(--panel)",
                  color: "var(--text)",
                  boxSizing: "border-box",
                  outline: "none",
                }}
              />
              <div style={{ borderLeft: "2px solid rgba(245,158,11,0.3)", paddingLeft: 12, paddingRight: 18, maxHeight: 288, overflowY: "auto" }}>
                {blocks
                  .filter((block) => {
                    const id = block.label || block.name || block.block_reference || block.block_id || block.id || "";
                    return id.toLowerCase().includes(blocksSearchDebounced.toLowerCase());
                  })
                  .map((block) => {
                    const id = block.label || block.name || block.block_reference || block.block_id || block.id || "—";
                    const isSelected = selectedBlock && (
                      (selectedBlock.id && selectedBlock.id === block.id) ||
                      (selectedBlock.label && selectedBlock.label === block.label)
                    );
                    return (
                      <div
                        key={block.id || block.block_id || id}
                        onClick={() => onSelectBlock?.(block)}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          padding: "5px 6px",
                          fontSize: 13,
                          borderRadius: 6,
                          cursor: "pointer",
                          background: isSelected ? "rgba(245,158,11,0.12)" : "transparent",
                          fontWeight: isSelected ? 600 : 400,
                        }}
                      >
                        <span style={{ color: isSelected ? "#b45309" : undefined }}>{id}</span>
                        <span className="muted">{block.count ?? 0}</span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
        </div>
        {other.length > 0 && renderExpandableRow("Other", other, "#64748b", otherOpen, setOtherOpen)}

        {thirdPartyLikeBlocks > 0 && (
          <div
            style={{
              marginTop: 8,
              padding: "10px 14px",
              borderRadius: 10,
              background: "rgba(245,158,11,0.10)",
              border: "1px solid rgba(245,158,11,0.30)",
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 13, color: "var(--muted)" }}>
              {thirdPartyLikeBlocks} blocks were grouped without clear parent UPRN
            </div>
          </div>
        )}
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
  return (
    <div className="card">
      <div className="card-header row-between">
        <div>
          <div className="card-title">Portfolio Analysis</div>
          <div className="card-subtitle">
            Compact whole-portfolio analysis for tenancy, block reference, property type, and age.
          </div>
        </div>
        <span className="pill pill-muted">Whole SoV summary</span>
      </div>

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
  );
}

function FireEvidencePanel({ fireDocuments, loading, onUploadNew }) {
  const fireRiskSummary = useMemo(() => {
    const totals = { Red: 0, Amber: 0, Green: 0, Unknown: 0 };
    fireDocuments.forEach((doc) => {
      totals[getFireRiskBand(doc)] += 1;
    });
    return totals;
  }, [fireDocuments]);

  return (
    <div className="card">
      <div className="card-header row-between">
        <div>
          <div className="card-title">Fire risk evidence</div>
          <div className="card-subtitle">
            Upload FRA and FRAEW evidence after the SoV so documents can be matched against existing blocks and properties.
          </div>
        </div>
        <span className="pill pill-muted">
          {loading ? "Refreshing…" : `${fireDocuments.length} documents`}
        </span>
      </div>

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
                border: "1px solid rgba(148,163,184,0.22)",
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
            border: "1px solid rgba(37,99,235,0.22)",
            borderRadius: 18,
            padding: 16,
            background: "linear-gradient(135deg, rgba(37,99,235,0.08), rgba(16,185,129,0.08))",
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
              border: "1px dashed rgba(148,163,184,0.45)",
              borderRadius: 16,
              padding: 16,
              background: "rgba(248,250,252,0.8)",
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
                  border: "1px solid rgba(148,163,184,0.22)",
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
  );
}

function BlockListPanel({ blocks, selectedBlockId, onSelectBlock, selectedProperty }) {
  const [search, setSearch] = useState("");
  const [searchDebounced, setSearchDebounced] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setSearchDebounced(search), 150);
    return () => clearTimeout(t);
  }, [search]);

  const filteredBlocks = searchDebounced
    ? blocks.filter((b) => (b.label || b.name || "").toLowerCase().includes(searchDebounced.toLowerCase()))
    : blocks;

  return (
    <div className="card">
      <div className="card-header row-between">
        <div>
          <div className="card-title">Block analysis list</div>
          <div className="card-subtitle">
            Drill into grouped blocks without rendering the whole SoV as a long table.
          </div>
        </div>
        <span className="pill pill-muted">{blocks.length} blocks</span>
      </div>

      <div className="card-body">
        <input
          type="text"
          placeholder="Search block…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: "100%",
            padding: "6px 12px",
            marginBottom: 12,
            fontSize: 13,
            borderRadius: 6,
            border: "1px solid var(--border)",
            background: "var(--panel)",
            color: "var(--text)",
            boxSizing: "border-box",
            outline: "none",
          }}
        />
        {!blocks.length ? (
          <div className="muted">No block-level groups are available yet.</div>
        ) : (
          <div className="table-wrap" style={{ maxHeight: 510, minHeight: 510, overflowY: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Block</th>
                  <th>Properties</th>
                  <th>Total value</th>
                  <th>Max height</th>
                  <th>FRA</th>
                  <th>FRAEW</th>
                </tr>
              </thead>
              <tbody>
                {filteredBlocks.map((block) => (
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
                      {Number.isFinite(Number(block.maxHeight))
                        ? `${Number(block.maxHeight).toFixed(1)} m`
                        : "—"}
                    </td>
                    <td>{block.latest_fra ? <RiskBadge band={getFireRiskBand(block.latest_fra)} /> : "—"}</td>
                    <td>{block.latest_fraew ? <RiskBadge band={getFireRiskBand(block.latest_fraew)} /> : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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
  const [mapFocusBlockId, setMapFocusBlockId] = useState(null);
  const [mapDataLoading, setMapDataLoading] = useState(false);

  // Fall back to ha_demo portfolio ID if ingestionResult doesn't carry one
  const resolvedPortfolioId = portfolioId || (ingestionSummary ? "11111111-1111-1111-1111-111111111111" : null);

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
      setMapFocusBlockId(null);
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
        setMapFocusBlockId(null);
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
  const highRiseBlocks = blocks.filter((b) => Number(b.maxHeight) > 18).length;
  const amberBlocks = blocks.filter((b) => Number(b.maxHeight) > 11 && Number(b.maxHeight) <= 18).length;
  const mappedBlocksCount = blocks.filter((b) => b.hasValidCoords).length;

  const fireRiskCounts = useMemo(() => {
    return blocks.reduce(
      (acc, block) => {
        const docs = [block.latest_fra, block.latest_fraew].filter(Boolean);
        const hasRed = docs.some((doc) => getFireRiskBand(doc) === "Red");
        const hasAmber = docs.some((doc) => getFireRiskBand(doc) === "Amber");
        const hasGreen = docs.some((doc) => getFireRiskBand(doc) === "Green");
        if (hasRed) acc.red += 1;
        else if (hasAmber) acc.amber += 1;
        else if (hasGreen) acc.green += 1;
        else acc.unlinked += 1;
        return acc;
      },
      { red: 0, amber: 0, green: 0, unlinked: 0 }
    );
  }, [blocks]);

  // Called by list panels (BlockListPanel, PortfolioCompositionCard) — updates details only, no map zoom
  const handleSelectBlock = (block) => {
    if (!block) {
      setSelectedBlock(null);
      setSelectedProperty(null);
      return;
    }
    const matchingBlock = blocks.find((b) => sameBlock(b, block)) || block;
    setSelectedBlock(matchingBlock);
    setSelectedProperty(null);
  };

  // Called by PortfolioMap — updates details AND zooms map into that block's properties
  const handleMapSelectBlock = (block) => {
    if (!block) {
      setSelectedBlock(null);
      setSelectedProperty(null);
      setMapFocusBlockId(null);
      return;
    }
    const matchingBlock = blocks.find((b) => sameBlock(b, block)) || block;
    setSelectedBlock(matchingBlock);
    setSelectedProperty(null);
    setMapFocusBlockId(matchingBlock.id ?? null);
  };

  const handleSelectProperty = (property) => {
    if (!property) {
      setSelectedProperty(null);
      return;
    }
    const matchingProperty = properties.find((p) => sameProperty(p, property)) || property;
    setSelectedProperty(matchingProperty);
    const parentBlock = blocks.find((block) => block.properties.some((p) => sameProperty(p, matchingProperty))) || null;
    setSelectedBlock(parentBlock);
    setMapFocusBlockId(parentBlock?.id ?? null);
  };

  const handleClearMapSelection = () => {
    setSelectedBlock(null);
    setSelectedProperty(null);
    setMapFocusBlockId(null);
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
  const mapFocusBlock = mapFocusBlockId ? blocks.find((b) => b.id === mapFocusBlockId) ?? null : null;
  const mapMode = mapFocusBlock ? "properties" : "blocks";
  const mapProperties = mapMode === "properties" ? mapFocusBlock?.properties || [] : properties;

  return (
    <div className="content-wrap">
      <div className="main-head">
        <div>
          <div className="page-title">Portfolio Overview</div>
          <div className="page-sub">
            Underwriter-focused dashboard using ingested portfolio, enrichment, block grouping, fire risk evidence, and map analysis.
          </div>
        </div>

        <div className="actions" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {typeof refetchFireDocuments === "function" ? (
            <button className="btn" onClick={refetchFireDocuments} disabled={fireDocumentsLoading}>
              {fireDocumentsLoading ? "Refreshing…" : "Refresh fire evidence"}
            </button>
          ) : null}
          <button className="btn" onClick={() => onUploadNew?.("SOV")}>Upload SoV</button>
          <button className="btn btn-primary" onClick={() => onUploadNew?.("FRA")}>Upload FRA / FRAEW</button>
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
          title="Fire evidence"
          value={fireDocuments.length}
          subtitle={`${fireRiskCounts.red} red · ${fireRiskCounts.amber} amber blocks`}
          tone="amber"
        />
        <KpiCard
          title="Mappable coverage"
          value={`${geoCompletenessPct}%`}
          subtitle={`${mappedBlocksCount} mapped blocks`}
          tone="green"
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
        <div style={{ display: "grid", gap: 16 }}>
          <PortfolioCompositionCard properties={properties} blocks={blocks} onSelectBlock={handleSelectBlock} selectedBlock={resolvedSelectedBlock} />

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
                  ? `Block : ${resolvedSelectedBlock?.block_id ?? resolvedSelectedBlock?.id ?? resolvedSelectedBlock?.name ?? "?"}`
                  : "None"}
              </span>
            </div>

            <div className="details-body" style={{ maxHeight: 420, overflowY: "auto", paddingRight: 6 }}>
              <PropertyDetails
                property={resolvedSelectedProperty}
                selectedBlock={resolvedSelectedBlock}
                blockMode={!resolvedSelectedProperty}
              />
            </div>
          </div>
        </div>

        <div className="card" style={{ minHeight: 760, overflow: "visible", isolation: "isolate" }}>
          <div className="card-header row-between">
            <div>
              <div className="card-title">Block analysis map</div>
              <div className="card-subtitle">
                Clustered map view with clear block counts at map level and colour-coded properties once a block is selected.
              </div>
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

          <div className="map-wrap">
            <PortfolioMap
              properties={mapProperties}
              blocks={blocks}
              viewMode={mapMode}
              selectedBlock={resolvedSelectedBlock}
              selectedProperty={resolvedSelectedProperty}
              onSelectBlock={handleMapSelectBlock}
              onSelectProperty={handleSelectProperty}
            />
          </div>

          <div
            className="map-foot"
            style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}
          >
            <span>
              {mapFocusBlock
                ? `Zoomed into block ${mapFocusBlock.label ?? ""}. Coloured dots show the property mix inside.`
                : "Click a block circle on the map to zoom in and inspect its properties."}
            </span>

            {mapFocusBlock ? (
              <button className="btn" onClick={handleClearMapSelection}>Clear selection</button>
            ) : null}
          </div>
        </div>
      </div>

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

      <BlockListPanel
        blocks={blocks}
        selectedBlockId={selectedBlockId}
        onSelectBlock={handleSelectBlock}
        selectedProperty={resolvedSelectedProperty}
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

  const highValueBlocks = blocks.filter(b => (b.height_max_m || 0) >= 18);
  const blocksWithData = blocks.filter(b => b.height_max_m || b.unit_count);
  const docBCompletion = blocks.length > 0 ? Math.round((blocksWithData.length / blocks.length) * 100) : 0;

  const completionColor = (pct) => {
    if (pct >= 90) return { bg: "#dcfce7", color: "#16a34a" };
    if (pct >= 70) return { bg: "#fef9c3", color: "#ca8a04" };
    return { bg: "#fee2e2", color: "#dc2626" };
  };

  return (
    <div className="card" style={{ marginTop: 24, padding: 28 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#111827", marginBottom: 4 }}>Underwriter Working Documents</div>
          <div style={{ fontSize: 13, color: "#6b7280" }}>Pre-populated from HA submission data</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#6b7280", flexShrink: 0 }}>
          <span>Export using:</span>
          <select style={{ border: "1px solid #d1d5db", borderRadius: 7, padding: "5px 10px", fontSize: 13, background: "#fff", cursor: "pointer", color: "#374151" }}>
            <option>Aviva Doc A v2.1</option>
          </select>
        </div>
      </div>

      {/* Doc cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Doc A */}
        <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: "20px 24px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 20, minWidth: 0 }}>
          <div style={{ display: "flex", gap: 14, alignItems: "flex-start", minWidth: 0 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: "#eff6ff", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 14, color: "#111827", marginBottom: 4 }}>Document A — Stock Listing</div>
              <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 10 }}>{propertyCount} properties · 35 fields populated</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 20, background: completionColor(docACompletion).bg, color: completionColor(docACompletion).color }}>{docACompletion}% complete</span>
                <span style={{ fontSize: 11, fontWeight: 500, padding: "3px 10px", borderRadius: 20, background: "#eff6ff", color: "#3b82f6" }}>Aviva format</span>
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
        <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: "20px 24px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 20, minWidth: 0 }}>
          <div style={{ display: "flex", gap: 14, alignItems: "flex-start", minWidth: 0 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: "#fffbeb", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6M9 12h6M9 15h4"/>
              </svg>
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 14, color: "#111827", marginBottom: 4 }}>Document B — High Value</div>
              <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 10 }}>{highValueBlocks.length} block{highValueBlocks.length !== 1 ? "s" : ""} (18m+) · 65 fields populated</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 20, background: completionColor(docBCompletion).bg, color: completionColor(docBCompletion).color }}>{docBCompletion}% complete</span>
                <span style={{ fontSize: 11, fontWeight: 500, padding: "3px 10px", borderRadius: 20, background: "#eff6ff", color: "#3b82f6" }}>Aviva format</span>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
            <select style={{ border: "1px solid #d1d5db", borderRadius: 7, padding: "7px 10px", fontSize: 13, background: "#fff", cursor: "pointer", color: "#374151" }}>
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
