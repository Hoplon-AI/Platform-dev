import React, { useMemo, useState } from "react";
import PortfolioMap from "../components/PortfolioMap.jsx";
import { WMS_LAYERS } from "../constants/wmsLayers.js";
import { buildBlocks } from "../utils/blockModel.js";

const COLOR_MODES = [
  { key: "flood",     label: "Flood risk" },
  { key: "readiness", label: "Readiness" },
  { key: "listed",    label: "Listed" },
];

const FLOOD_LEGEND = [
  { color: "#ef4444", label: "High" },
  { color: "#f59e0b", label: "Medium" },
  { color: "#fbbf24", label: "Low" },
  { color: "#22c55e", label: "Very low" },
  { color: "#94a3b8", label: "Unknown" },
];
const READINESS_LEGEND = [
  { color: "#22c55e", label: "Green (≥80)" },
  { color: "#f59e0b", label: "Amber (50–79)" },
  { color: "#ef4444", label: "Red (<50)" },
];
const LISTED_LEGEND = [
  { color: "#7c3aed", label: "Listed" },
  { color: "#94a3b8", label: "Not listed" },
];

const LEGENDS = { flood: FLOOD_LEGEND, readiness: READINESS_LEGEND, listed: LISTED_LEGEND };

export default function FullMapPage({ properties = [] }) {
  const [colorBy, setColorBy] = useState("flood");
  const blocks = useMemo(() => buildBlocks(properties), [properties]);

  return (
    // Full-bleed map: fills the main column edge-to-edge below the 56px topbar
    <div style={{ position: "relative", height: "calc(100vh - 56px)" }}>
      <PortfolioMap
        properties={properties}
        blocks={blocks}
        overlays={WMS_LAYERS}
        colorBy={colorBy}
        viewMode="blocks"
        canvasStyle={{ height: "100%", borderRadius: 0, border: "none" }}
      />

      {/* Floating colour-by + legend panel (left of Leaflet's zoom control) */}
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
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>Colour by:</span>
        {COLOR_MODES.map((m) => (
          <button
            key={m.key}
            onClick={() => setColorBy(m.key)}
            aria-pressed={colorBy === m.key}
            className="btn"
            style={{
              padding: "4px 12px",
              fontSize: 13,
              fontWeight: colorBy === m.key ? 700 : 400,
              background: colorBy === m.key ? "var(--navy, #1e3a5f)" : "var(--panel-soft)",
              color: colorBy === m.key ? "#fff" : "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              cursor: "pointer",
            }}
          >
            {m.label}
          </button>
        ))}

        <div style={{ display: "flex", gap: 6, alignItems: "center", marginLeft: 8, flexWrap: "wrap" }}>
          {LEGENDS[colorBy].map((item) => (
            <span key={item.label} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "var(--text)" }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: item.color, display: "inline-block", flexShrink: 0 }} />
              {item.label}
            </span>
          ))}
        </div>
      </div>

      <p
        style={{
          position: "absolute",
          bottom: 4,
          left: 8,
          zIndex: 1000,
          fontSize: 11,
          color: "var(--muted)",
          background: "rgba(255,255,255,0.85)",
          borderRadius: 6,
          padding: "2px 8px",
          margin: 0,
        }}
      >
        Risk overlays use generalised open (OGL) datasets for demonstration — not property-precise underwriting data.
      </p>
    </div>
  );
}
