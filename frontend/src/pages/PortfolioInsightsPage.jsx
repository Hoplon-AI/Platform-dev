import React, { useMemo, useState } from "react";

import { PortfolioInsightsPanel } from "../components/PortfolioInsights.jsx";
import { PortfolioAnalysisWindow } from "./PortfolioDashboard.jsx";
import {
  inferPortfolioClass,
  buildBreakdown,
  buildBlockRows,
  ageBandKey,
} from "../utils/portfolioBreakdown.js";

// Segment predicates — every chart on the page is rebuilt for the selected
// slice of the portfolio (blocks vs houses/bungalows vs flats).
const SEGMENTS = [
  { id: "all",    label: "All properties",      match: () => true },
  { id: "blocks", label: "Flats in blocks",      match: (p) => p.is_standalone !== true },
  { id: "houses", label: "Houses & bungalows",   match: (p) => ["house", "bungalow"].includes(p.dwelling_form) },
  { id: "flats",  label: "Flats & maisonettes",  match: (p) => ["flat", "maisonette"].includes(p.dwelling_form) },
];

export default function PortfolioInsightsPage({ ingestionResult, onUploadNew, haName = "" }) {
  const allProperties = ingestionResult?.properties || [];
  const [segmentId, setSegmentId] = useState("all");

  // Only offer segments that exist in this portfolio (block-only books just see "All").
  const availableSegments = useMemo(
    () =>
      SEGMENTS.filter(
        (s) => s.id === "all" || allProperties.some((p) => s.match(p))
      ),
    [allProperties]
  );

  const segment = availableSegments.find((s) => s.id === segmentId) || SEGMENTS[0];
  const properties = useMemo(
    () => (segment.id === "all" ? allProperties : allProperties.filter(segment.match)),
    [allProperties, segment]
  );

  const tenancyRows = useMemo(
    () => buildBreakdown(properties, (property) => property.occupancy_type || "Not recorded", (property) => property.sum_insured),
    [properties]
  );

  const blockRows = useMemo(() => buildBlockRows(properties), [properties]);

  const propertyTypeRows = useMemo(
    () => buildBreakdown(properties, (property) => property.property_type || inferPortfolioClass(property), (property) => property.sum_insured),
    [properties]
  );

  const ageBandRows = useMemo(
    () => buildBreakdown(properties, ageBandKey, (property) => property.sum_insured),
    [properties]
  );

  if (!allProperties.length) {
    return (
      <div className="content-wrap">
        <div className="card">
          <div className="empty-state">No portfolio loaded yet. Upload an SoV file to begin.</div>
          <div style={{ textAlign: "center", marginTop: 12 }}>
            <button className="btn btn-primary" onClick={() => onUploadNew?.("SOV")}>Upload SoV</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="content-wrap">
      <div className="main-head">
        <div>
          <div className="tag">Premium Intelligence</div>
          <div className="page-title">Portfolio <em>Insights</em></div>
          {haName && (
            <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
              For: <strong style={{ color: "var(--terracotta)" }}>{haName}</strong>
            </div>
          )}
        </div>
        {availableSegments.length > 1 && (
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--muted)" }}>
            Show insights for
            <select
              className="input"
              style={{ width: "auto", padding: "6px 10px", fontSize: 13, fontWeight: 600 }}
              value={segment.id}
              onChange={(e) => setSegmentId(e.target.value)}
            >
              {availableSegments.map((s) => {
                const n = s.id === "all" ? allProperties.length : allProperties.filter(s.match).length;
                return (
                  <option key={s.id} value={s.id}>
                    {s.label} ({n})
                  </option>
                );
              })}
            </select>
          </label>
        )}
      </div>

      {segment.id !== "all" && (
        <div className="muted" style={{ margin: "0 0 12px", fontSize: 13 }}>
          All charts below cover only <strong>{segment.label.toLowerCase()}</strong> — {properties.length} of {allProperties.length} properties.
        </div>
      )}

      {/* Property-type donut heading mirrors the "Show insights for" selection */}
      <PortfolioInsightsPanel
        properties={properties}
        segmentTitle={`${segment.label} (${properties.length})`}
      />

      <PortfolioAnalysisWindow
        tenancyRows={tenancyRows}
        blockRows={blockRows}
        propertyTypeRows={propertyTypeRows}
        ageBandRows={ageBandRows}
      />
    </div>
  );
}
