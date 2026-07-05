import React, { useMemo } from "react";
import PortfolioMap from "../components/PortfolioMap.jsx";
import { WMS_LAYERS } from "../constants/wmsLayers.js";
import { buildBlocks } from "../utils/blockModel.js";

export default function FullMapPage({ properties = [] }) {
  const blocks = useMemo(() => buildBlocks(properties), [properties]);

  return (
    // Full-bleed map: fills the main column edge-to-edge below the 56px topbar
    <div style={{ position: "relative", height: "calc(100vh - 56px)" }}>
      <PortfolioMap
        properties={properties}
        blocks={blocks}
        overlays={WMS_LAYERS}
        neutralMarkers
        viewMode="blocks"
        canvasStyle={{ height: "100%", borderRadius: 0, border: "none" }}
      />

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
