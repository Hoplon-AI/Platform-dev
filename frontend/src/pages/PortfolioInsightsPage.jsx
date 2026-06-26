import React, { useMemo } from "react";

import { PortfolioInsightsPanel } from "../components/PortfolioInsights.jsx";
import { PortfolioAnalysisWindow } from "./PortfolioDashboard.jsx";
import {
  inferPortfolioClass,
  buildBreakdown,
  buildBlockRows,
  ageBandKey,
} from "../utils/portfolioBreakdown.js";

export default function PortfolioInsightsPage({ ingestionResult, onUploadNew }) {
  const properties = ingestionResult?.properties || [];

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

  if (!properties.length) {
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
        </div>
      </div>

      <PortfolioInsightsPanel properties={properties} />

      <PortfolioAnalysisWindow
        tenancyRows={tenancyRows}
        blockRows={blockRows}
        propertyTypeRows={propertyTypeRows}
        ageBandRows={ageBandRows}
      />
    </div>
  );
}
