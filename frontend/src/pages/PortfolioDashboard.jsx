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

function BlockTable({ blocks, onSelectBlock, selectedBlockId }) {
  if (!blocks.length) {
    return <div className="muted">No block-level groups are available yet.</div>;
  }

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Block</th>
            <th>Properties</th>
            <th>Total value</th>
            <th>Avg readiness</th>
            <th>Max height</th>
          </tr>
        </thead>
        <tbody>
          {blocks.map((block) => (
            <tr
              key={block.id}
              onClick={() => onSelectBlock?.(block)}
              style={{
                cursor: "pointer",
                background:
                  selectedBlockId === block.id ? "rgba(59,130,246,0.08)" : "transparent",
              }}
            >
              <td>{block.label}</td>
              <td>{block.count}</td>
              <td>£{fmtMoney(block.totalValue)}</td>
              <td>{Math.round(block.avgReadiness || 0)}</td>
              <td>
                {Number.isFinite(Number(block.maxHeight))
                  ? `${Number(block.maxHeight).toFixed(1)} m`
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PropertyTable({ properties, onSelectProperty, selectedPropertyId }) {
  if (!properties.length) {
    return <div className="muted">No properties to display.</div>;
  }

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Property</th>
            <th>Postcode</th>
            <th>UPRN</th>
            <th>Value</th>
            <th>Readiness</th>
            <th>Block</th>
          </tr>
        </thead>
        <tbody>
          {properties.map((p) => (
            <tr
              key={p.id}
              onClick={() => onSelectProperty?.(p)}
              style={{
                cursor: "pointer",
                background:
                  selectedPropertyId === p.id ? "rgba(59,130,246,0.08)" : "transparent",
              }}
            >
              <td>{p.address_line_1 || p.property_reference || p.id}</td>
              <td>{p.post_code || "—"}</td>
              <td>{p.uprn || "—"}</td>
              <td>£{fmtMoney(p.sum_insured)}</td>
              <td>
                <span
                  className="pill"
                  style={{
                    background: `${readinessColor(p.readiness_band)}22`,
                    color: readinessColor(p.readiness_band),
                    border: `1px solid ${readinessColor(p.readiness_band)}33`,
                  }}
                >
                  {Math.round(Number(p.readiness_score) || 0)} ·{" "}
                  {p.readiness_band || bandFromScore(p.readiness_score)}
                </span>
              </td>
              <td>{p.block_reference || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
}) {
  const properties = ingestionResult?.properties || [];

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
        const mappable = items.filter(
          (p) =>
            p.hasValidCoords &&
            Number.isFinite(Number(p.latitude)) &&
            Number.isFinite(Number(p.longitude)) &&
            Number(p.latitude) !== 0 &&
            Number(p.longitude) !== 0
        );

        const lat =
          mappable.length > 0
            ? mappable.reduce((sum, p) => sum + Number(p.latitude || 0), 0) /
              mappable.length
            : null;

        const lon =
          mappable.length > 0
            ? mappable.reduce((sum, p) => sum + Number(p.longitude || 0), 0) /
              mappable.length
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

        return {
          id: key,
          label: key || "Unassigned block",
          properties: items,
          count: items.length,
          lat,
          lon,
          __lat: lat,
          __lon: lon,
          hasValidCoords:
            Number.isFinite(Number(lat)) &&
            Number.isFinite(Number(lon)) &&
            Number(lat) !== 0 &&
            Number(lon) !== 0,
          totalValue,
          avgReadiness,
          maxHeight,
          parent_uprn:
            items.find((p) => p.parent_uprn)?.parent_uprn ||
            items.find((p) => p.uprn)?.uprn ||
            null,
        };
      })
      .filter((block) => block.hasValidCoords)
      .sort((a, b) => b.totalValue - a.totalValue);
  }, [properties]);

  const [selectedBlock, setSelectedBlock] = useState(null);
  const [selectedProperty, setSelectedProperty] = useState(null);

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

  useEffect(() => {
    if (!blocks.length) {
      setSelectedBlock(null);
      if (!properties.length) {
        setSelectedProperty(null);
      }
      return;
    }

    if (!selectedBlock && !selectedProperty) {
      setSelectedBlock(blocks[0]);
    }
  }, [blocks, selectedBlock, selectedProperty, properties.length]);

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

  const handleSelectProperty = (property) => {
    if (!property) {
      setSelectedProperty(null);
      return;
    }

    const matchingProperty = properties.find((p) => sameProperty(p, property)) || property;
    setSelectedProperty(matchingProperty);

    const parentBlock =
      blocks.find((block) =>
        block.properties.some((p) => sameProperty(p, matchingProperty))
      ) || null;

    setSelectedBlock(parentBlock);
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

  return (
    <div className="content-wrap">
      <div className="main-head">
        <div>
          <div className="page-title">Portfolio Overview</div>
          <div className="page-sub">
            Underwriter-focused dashboard using ingested portfolio, enrichment, and block grouping.
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
            This view is aligned to your backend ingestion flow, showing portfolio value,
            UPRN confidence, mappable coverage, and block-based spatial analysis.
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
          title="Mappable locations"
          value={ingestionSummary.mappableCount}
          subtitle={`Invalid coords skipped: ${ingestionSummary.skippedInvalidCoords}`}
          tone="amber"
        />
      </div>

      <div className="card confidence-card">
        <div className="card-header row-between">
          <div>
            <div className="card-title">Confidence & completeness</div>
            <div className="card-subtitle">
              Mapped directly from your ingestion utilities and backend-ready fields.
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

      <div className="two-col">
        <div className="card">
          <div className="card-header row-between">
            <div>
              <div className="card-title">Block analysis map</div>
              <div className="card-subtitle">
                Block-centric mapping using grouped properties and geo-ready backend data.
              </div>
            </div>

            <span className="pill pill-muted">{mappedBlocksCount} mapped blocks</span>
          </div>

          <div className="map-wrap">
            <PortfolioMap
              properties={properties}
              blocks={blocks}
              viewMode={resolvedSelectedProperty ? "properties" : "blocks"}
              selectedBlock={resolvedSelectedBlock}
              selectedProperty={resolvedSelectedProperty}
              onSelectBlock={handleSelectBlock}
              onSelectProperty={handleSelectProperty}
            />
          </div>

          <div className="map-foot">
            Click a block to inspect the cluster, then select a property from the property table for full detail.
          </div>
        </div>

        <div className="card">
          <div className="card-header row-between">
            <div className="card-title">
              {resolvedSelectedProperty ? "Selected property details" : "Selected block details"}
            </div>
            <span className="pill pill-muted">
              {resolvedSelectedProperty ? "Property selected" : resolvedSelectedBlock ? "Block selected" : "None"}
            </span>
          </div>

          <div className="details-body">
            <PropertyDetails
              property={resolvedSelectedProperty}
              selectedBlock={resolvedSelectedBlock}
              blockMode={!resolvedSelectedProperty}
            />
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header row-between">
          <div>
            <div className="card-title">Block table</div>
            <div className="card-subtitle">
              Underwriting view of grouped properties.
            </div>
          </div>
          <span className="pill pill-muted">Grouped by block / parent reference</span>
        </div>

        <BlockTable
          blocks={blocks}
          selectedBlockId={selectedBlockId}
          onSelectBlock={handleSelectBlock}
        />
      </div>

      <div className="card">
        <div className="card-header row-between">
          <div>
            <div className="card-title">Property schedule</div>
            <div className="card-subtitle">
              Detailed per-property view from uploaded and normalised backend rows.
            </div>
          </div>
          <span className="pill pill-muted">{properties.length} rows</span>
        </div>

        <PropertyTable
          properties={properties}
          selectedPropertyId={resolvedSelectedProperty?.id}
          onSelectProperty={handleSelectProperty}
        />
      </div>

      <DocumentPanel />
    </div>
  );
}