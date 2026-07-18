import React, { useMemo, useState } from "react";
import PortfolioMap from "../components/PortfolioMap.jsx";
import { WMS_LAYERS } from "../constants/wmsLayers.js";
import { buildBlocks } from "../utils/blockModel.js";

const RISK_MODES = [
  { key: "none",   label: "None" },
  { key: "fra",    label: "FRA" },
  { key: "fraew",  label: "FRAEW" },
  { key: "flood",  label: "Flood" },
  { key: "height", label: "Height" },
  { key: "listed", label: "Listed" },
];

// Legend swatches per mode — mirror blockRingColor() in mapHelpers.js.
const FIRE_LEGEND = [{ c: "#ef4444", l: "High" }, { c: "#f59e0b", l: "Medium" }, { c: "#22c55e", l: "Low" }, { c: "#94a3b8", l: "No data" }];
const RISK_LEGENDS = {
  none:   [],
  fra:    FIRE_LEGEND,
  fraew:  FIRE_LEGEND,
  flood:  [{ c: "#ef4444", l: "High" }, { c: "#f59e0b", l: "Medium" }, { c: "#fbbf24", l: "Low" }, { c: "#22c55e", l: "Very low" }, { c: "#94a3b8", l: "Unknown" }],
  height: [{ c: "#ef4444", l: "≥18m" }, { c: "#f59e0b", l: "11–18m" }, { c: "#64748b", l: "<11m" }, { c: "#94a3b8", l: "No data" }],
  listed: [{ c: "#7c3aed", l: "Listed" }, { c: "#94a3b8", l: "Not listed" }],
};

export default function FullMapPage({ properties = [], initialView = null }) {
  const [riskColorBy, setRiskColorBy] = useState("none");
  const blocks = useMemo(() => buildBlocks(properties), [properties]);

  return (
    // Full-bleed map: fills the main column edge-to-edge below the 56px topbar
    <div style={{ position: "relative", height: "calc(100vh - 56px)" }}>
      <PortfolioMap
        properties={properties}
        blocks={blocks}
        overlays={WMS_LAYERS}
        riskColorBy={riskColorBy}
        viewMode="blocks"
        canvasStyle={{ height: "100%", borderRadius: 0, border: "none" }}
        viewOverride={initialView}
      />

      {/* Colour blocks by risk type (left of Leaflet's zoom control) */}
      <div
        style={{
          position: "absolute",
          top: 12,
          left: 56,
          zIndex: 1000,
          display: "flex",
          gap: 8,
          alignItems: "center",
          flexWrap: "wrap",
          background: "rgba(255,255,255,0.92)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: "8px 12px",
          boxShadow: "0 2px 8px rgba(15,23,42,0.10)",
          maxWidth: "calc(100% - 260px)",
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>Colour by risk:</span>
        {RISK_MODES.map((m) => (
          <button
            key={m.key}
            onClick={() => setRiskColorBy(m.key)}
            aria-pressed={riskColorBy === m.key}
            className="btn"
            style={{
              padding: "4px 12px",
              fontSize: 13,
              fontWeight: riskColorBy === m.key ? 700 : 400,
              background: riskColorBy === m.key ? "var(--navy, #1e3a5f)" : "var(--panel-soft)",
              color: riskColorBy === m.key ? "#fff" : "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              cursor: "pointer",
            }}
          >
            {m.label}
          </button>
        ))}

        {RISK_LEGENDS[riskColorBy].length > 0 && (
          <div style={{ display: "flex", gap: 6, alignItems: "center", marginLeft: 8, flexWrap: "wrap" }}>
            {RISK_LEGENDS[riskColorBy].map((item) => (
              <span key={item.l} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "var(--text)" }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: item.c, display: "inline-block", flexShrink: 0 }} />
                {item.l}
              </span>
            ))}
            {riskColorBy === "height" && (
              <span style={{ fontSize: 11, color: "var(--muted)", marginLeft: 4 }}>
                (Scotland: ≥11m = High)
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
