// src/App.jsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import LandingPage from "./Landingpage.jsx";
import IngestionPage from "./pages/IngestionPage.jsx";

import { configureLeafletIcons } from "./utils/leaflet";
import { parsePortfolioFile, getIngestionSummary } from "./utils/ingestion";

configureLeafletIcons();

const fmtMoney = (n) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  return x.toLocaleString(undefined, { maximumFractionDigits: 0 });
};

const fmt = (n, digits = 5) => {
  const x = Number(n);
  return Number.isFinite(x) ? x.toFixed(digits) : "—";
};

const readinessColor = (band) => {
  const b = String(band || "").toLowerCase();
  if (b.includes("green")) return "#22c55e";
  if (b.includes("yellow")) return "#f59e0b";
  return "#ef4444";
};

function RawFieldsTable({ raw }) {
  const entries = useMemo(() => {
    if (!raw) return [];
    return Object.entries(raw)
      .map(([k, v]) => [String(k), String(v ?? "")])
      .sort((a, b) => a[0].localeCompare(b[0]));
  }, [raw]);

  if (!entries.length) return null;

  return (
    <div className="uw-section">
      <div className="uw-h">Raw fields (from upload)</div>
      <div
        style={{
          border: "1px solid #e6e8f2",
          borderRadius: 14,
          overflow: "hidden",
          background: "#fff",
        }}
      >
        <table className="uw-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([k, v]) => (
              <tr key={k}>
                <td className="uw-field">{k}</td>
                <td>{v || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function App() {
  // ✅ bring back landing/home
  const [showLanding, setShowLanding] = useState(true);

  // left nav: "overview" | "upload"
  const [activeNav, setActiveNav] = useState("overview");
  // inner tab: "analysis" | "map"
  const [activeTab, setActiveTab] = useState("map");

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [pipelineStep, setPipelineStep] = useState(null);

  const [ingestionResult, setIngestionResult] = useState(null);
  const ingestionSummary = useMemo(
    () => getIngestionSummary(ingestionResult),
    [ingestionResult]
  );

  const [selectedProperty, setSelectedProperty] = useState(null);

  const properties = useMemo(() => ingestionResult?.properties || [], [ingestionResult]);
  const mappable = useMemo(
    () => properties.filter((p) => p.hasValidCoords),
    [properties]
  );

  // -------- Leaflet (single map) --------
  const mapDivRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);

  const ensureMap = () => {
    if (!mapDivRef.current) return;
    if (mapRef.current) return;

    const map = L.map(mapDivRef.current, {
      scrollWheelZoom: false,
      zoomControl: true,
    }).setView([54.5, -3], 5);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
    }).addTo(map);

    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
  };

  const invalidateMap = () => {
    const map = mapRef.current;
    if (!map) return;
    setTimeout(() => map.invalidateSize(true), 80);
  };

  const renderMarkers = (list) => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    list.forEach((p) => {
      const lat = Number(p.latitude);
      const lon = Number(p.longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

      const color = readinessColor(p.readiness_band);
      const radius = Math.max(
        6,
        Math.min(18, Math.sqrt((Number(p.sum_insured) || 0) / 250000) || 6)
      );

      const isSelected = selectedProperty?.id === p.id;

      const circle = L.circleMarker([lat, lon], {
        radius,
        color: isSelected ? "#1d4ed8" : color,
        weight: isSelected ? 3 : 2,
        fillColor: color,
        fillOpacity: 0.6,
      });

      circle.on("click", () => {
        setSelectedProperty(p);
        map.setView([lat, lon], 13, { animate: true });
      });

      const label = p.address_line_1 || p.post_code || p.city || p.id;
      circle.bindTooltip(`${label} · readiness ${p.readiness_score ?? "—"}`, {
        direction: "top",
        sticky: true,
        opacity: 0.95,
      });

      circle.addTo(layer);
    });

    // Fit bounds if no selection
    if (!selectedProperty && list.length > 0) {
      const coords = list
        .map((p) => [Number(p.latitude), Number(p.longitude)])
        .filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b));
      if (coords.length) {
        const bounds = L.latLngBounds(coords);
        if (bounds.isValid()) map.fitBounds(bounds.pad(0.15));
      }
    }
  };

  // ✅ IMPORTANT:
  // Keep map DOM mounted always; but when dashboard is shown, make sure map exists and is sized.
  useEffect(() => {
    if (showLanding) return;
    if (activeNav !== "overview") return;
    ensureMap();
    invalidateMap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showLanding, activeNav]);

  // Re-render markers whenever dataset changes OR selection changes
  useEffect(() => {
    if (showLanding) return;
    if (activeNav !== "overview") return;
    ensureMap();
    renderMarkers(mappable);
    invalidateMap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showLanding, activeNav, mappable, selectedProperty]);

  // If a property is selected, zoom it
  useEffect(() => {
    if (!selectedProperty) return;
    const map = mapRef.current;
    if (!map) return;
    const lat = Number(selectedProperty.latitude);
    const lon = Number(selectedProperty.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
    map.setView([lat, lon], 13, { animate: true });
  }, [selectedProperty]);

  // -------- upload pipeline --------
  const PIPELINE_STEPS = [
    "Queued",
    "Checking file format",
    "Reading file",
    "Normalising columns",
    "Coercing types",
    "Computing readiness scores",
    "Filtering invalid coordinates",
    "Finalising",
    "Complete",
  ];

  const runPipeline = () => {
    setPipelineStep(PIPELINE_STEPS[0]);
    PIPELINE_STEPS.slice(1).forEach((step, i) => {
      setTimeout(() => setPipelineStep(step), 450 * (i + 1));
    });
  };

  const handleFiles = (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    const file = files[0];

    setUploadError(null);
    setIsUploading(true);
    runPipeline();

    parsePortfolioFile(
      file,
      (result) => {
        setSelectedProperty(null);
        setIngestionResult(result);
        setIsUploading(false);

        // After upload: go to dashboard map
        setShowLanding(false);
        setActiveNav("overview");
        setActiveTab("map");

        // Ensure map is valid and markers render after layout settles
        setTimeout(() => {
          ensureMap();
          renderMarkers(result?.properties?.filter((p) => p.hasValidCoords) || []);
          invalidateMap();
        }, 150);

        setTimeout(() => setPipelineStep(null), 800);
      },
      (err) => {
        setUploadError(err);
        setIsUploading(false);
      }
    );
  };

  // -------- computed metrics --------
  const totalValue = ingestionSummary?.totalValue ?? 0;
  const avgReadiness = useMemo(() => {
    if (!mappable.length) return 0;
    const s = mappable.reduce((acc, p) => acc + (Number(p.readiness_score) || 0), 0);
    return Math.round(s / mappable.length);
  }, [mappable]);

  const loadedMeta = ingestionSummary
    ? `Loaded: ${ingestionSummary.source} · Properties: ${ingestionSummary.propertyCount} · Value: £${fmtMoney(
        totalValue
      )}`
    : "Upload a file to begin";

  const p = selectedProperty;

  // ✅ Landing page restored
  if (showLanding) {
    return (
      <LandingPage
        onGetStarted={() => {
          setShowLanding(false);
          setActiveNav("upload"); // take them to upload first
        }}
      />
    );
  }

  return (
    <div className="uw-shell">
      {/* SIDEBAR */}
      <aside className="uw-sidebar">
        <div className="uw-brand">EquiRisk</div>
        <div className="uw-badge">UNDERWRITER</div>

        <div className="uw-nav">
          <div className="uw-nav-title">Portfolio Overview</div>
          <button
            className={`uw-nav-btn ${activeNav === "overview" ? "active" : ""}`}
            onClick={() => setActiveNav("overview")}
          >
            Portfolio Overview
          </button>
          <button
            className={`uw-nav-btn ${activeNav === "upload" ? "active" : ""}`}
            onClick={() => setActiveNav("upload")}
          >
            Upload SoV
          </button>

          <div className="uw-sidebar-divider" />

          <button className="uw-nav-btn" disabled style={{ opacity: 0.55 }}>
            Shared Portfolios
          </button>
          <button className="uw-nav-btn" disabled style={{ opacity: 0.55 }}>
            Evidence Summary
          </button>
          <button className="uw-nav-btn" disabled style={{ opacity: 0.55 }}>
            Block Analysis
          </button>

          <div className="uw-sidebar-divider" />

          <button className="uw-nav-btn" disabled style={{ opacity: 0.55 }}>
            Settings
          </button>
        </div>

        <div className="uw-sidebar-footer">
          <button className="uw-back" onClick={() => setShowLanding(true)}>
            ⟵ Back
          </button>
        </div>
      </aside>

      {/* MAIN */}
      <main className="uw-main">
        <div className="uw-topbar">
          <div className="uw-topbar-left">
            Upload SOVs, analyse exposure, assess portfolio risk.
          </div>
          <div className="uw-topbar-right">{loadedMeta}</div>
        </div>

        <div className="uw-content">
          {/* ✅ Keep BOTH mounted; only toggle display (Leaflet stability) */}
          <div style={{ display: activeNav === "upload" ? "block" : "none" }}>
            <IngestionPage
              onFilesSelected={handleFiles}
              pipelineStep={pipelineStep}
              ingestionSummary={ingestionSummary}
              uploadError={uploadError}
              isUploading={isUploading}
            />
          </div>

          <div style={{ display: activeNav === "overview" ? "block" : "none" }}>
            <div className="uw-head">
              <div>
                <h1 className="uw-title">Portfolio Overview</h1>
                <p className="uw-subtitle">
                  What’s in the submission and where it is (based on your uploaded SoV).
                </p>
              </div>

              <div className="uw-actions">
                <button className="uw-btn" onClick={() => setActiveNav("upload")}>
                  Upload new SoV
                </button>
                <button
                  className="uw-btn primary"
                  onClick={() => {
                    setActiveTab("map");
                    ensureMap();
                    invalidateMap();
                  }}
                >
                  View on map
                </button>
              </div>
            </div>

            <div className="uw-metrics">
              <div className="uw-metric">
                <div className="uw-metric-k">Total insured value</div>
                <div className="uw-metric-v">£{fmtMoney(totalValue)}</div>
                <div className="uw-metric-sub">
                  Across {ingestionSummary?.propertyCount ?? 0} properties
                </div>
              </div>

              <div className="uw-metric">
                <div className="uw-metric-k">Avg readiness</div>
                <div className="uw-metric-v">{avgReadiness || 0}</div>
                <div className="uw-metric-sub">
                  Green ≥ 80 · Yellow ≥ 50 · Red &lt; 50
                </div>
              </div>

              <div className="uw-metric">
                <div className="uw-metric-k">Mappable locations</div>
                <div className="uw-metric-v">{ingestionSummary?.mappableCount ?? 0}</div>
                <div className="uw-metric-sub">
                  Invalid coords skipped: {ingestionSummary?.skippedInvalidCoords ?? 0}
                </div>
              </div>
            </div>

            <div className="uw-tabs">
              <button
                className={`uw-tab ${activeTab === "analysis" ? "active" : ""}`}
                onClick={() => setActiveTab("analysis")}
              >
                Portfolio Analysis
              </button>
              <button
                className={`uw-tab ${activeTab === "map" ? "active" : ""}`}
                onClick={() => {
                  setActiveTab("map");
                  ensureMap();
                  invalidateMap();
                }}
              >
                Portfolio Map
              </button>
            </div>

            {/* ✅ Keep BOTH mounted (map must stay mounted) */}
            <div style={{ display: activeTab === "analysis" ? "block" : "none" }}>
              <div className="uw-card" style={{ marginTop: 14 }}>
                <div className="uw-card-head">
                  <h2 className="uw-card-title">Portfolio analysis</h2>
                  <span className="uw-chip">Coming soon</span>
                </div>
                <div className="uw-card-body">
                  <div className="uw-muted">
                    We’ll add analysis widgets here next (risk bands, missing fields breakdown, etc).
                  </div>
                </div>
              </div>
            </div>

            <div style={{ display: activeTab === "map" ? "block" : "none" }}>
              <div className="uw-grid" style={{ marginTop: 14 }}>
                <div className="uw-card">
                  <div className="uw-card-head">
                    <h2 className="uw-card-title">Portfolio map</h2>
                    <span className="uw-chip">
                      Readiness: green ≥ 80 • yellow ≥ 50 • red &lt; 50
                    </span>
                  </div>
                  <div className="uw-card-body">
                    <div className="uw-map-box">
                      <div ref={mapDivRef} className="uw-map-inner" />
                    </div>

                    <div style={{ marginTop: 10 }} className="uw-muted">
                      Mappable: {ingestionSummary?.mappableCount ?? 0} • Invalid coords skipped:{" "}
                      {ingestionSummary?.skippedInvalidCoords ?? 0}
                    </div>
                  </div>
                </div>

                <div className="uw-card">
                  <div className="uw-card-head">
                    <h2 className="uw-card-title">Details</h2>
                    <span className="uw-chip">{p ? "Selected" : "Click a circle"}</span>
                  </div>

                  <div className="uw-card-body">
                    {!p ? (
                      <div className="uw-muted">
                        Click a property circle on the map to zoom in and view SOV + property details here.
                      </div>
                    ) : (
                      <>
                        <div className="uw-h">Property</div>
                        <div className="uw-muted" style={{ marginBottom: 6 }}>
                          {p.city || "—"} {p.post_code ? `· ${p.post_code}` : ""} · lat{" "}
                          {fmt(p.latitude)} , lon {fmt(p.longitude)}
                        </div>
                        <div style={{ fontWeight: 950, fontSize: 14 }}>
                          {p.address_line_1 || "—"} {p.address_line_2 || ""}
                        </div>

                        <div className="uw-section">
                          <div className="uw-h">Readiness</div>
                          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                            <span
                              className="uw-dot"
                              style={{ background: readinessColor(p.readiness_band) }}
                            />
                            <div style={{ fontWeight: 950 }}>
                              {p.readiness_score ?? "—"} / 100{" "}
                              <span className="uw-muted" style={{ fontWeight: 800 }}>
                                ({p.readiness_band || "—"})
                              </span>
                            </div>
                          </div>

                          {(p.missing_fields || []).length > 0 ? (
                            <div className="uw-muted" style={{ marginTop: 6 }}>
                              Missing: <b>{(p.missing_fields || []).join(", ")}</b>
                            </div>
                          ) : (
                            <div className="uw-muted" style={{ marginTop: 6 }}>
                              No missing core fields detected.
                            </div>
                          )}
                        </div>

                        <div className="uw-section">
                          <div className="uw-h">SOV</div>

                          <div className="uw-row2">
                            <div>
                              <div className="uw-k">Sum insured</div>
                              <div className="uw-v">
                                {Number.isFinite(Number(p.sum_insured))
                                  ? `£${fmtMoney(p.sum_insured)}`
                                  : "—"}
                              </div>
                            </div>

                            <div>
                              <div className="uw-k">Property type</div>
                              <div className="uw-v">{p.property_type || "—"}</div>
                            </div>

                            <div>
                              <div className="uw-k">Occupancy</div>
                              <div className="uw-v">{p.occupancy_type || "—"}</div>
                            </div>

                            <div>
                              <div className="uw-k">Height</div>
                              <div className="uw-v">
                                {Number.isFinite(Number(p.height_m))
                                  ? `${Number(p.height_m).toFixed(1)} m`
                                  : "—"}
                              </div>
                            </div>

                            <div>
                              <div className="uw-k">Number of flats</div>
                              <div className="uw-v">
                                {Number.isFinite(Number(p.number_of_flats))
                                  ? String(Math.round(Number(p.number_of_flats)))
                                  : "—"}
                              </div>
                            </div>

                            <div>
                              <div className="uw-k">Construction</div>
                              <div className="uw-v">{p.construction || "—"}</div>
                            </div>
                          </div>
                        </div>

                        <RawFieldsTable raw={p.raw} />
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* NOTE: map stays mounted in DOM above; tab toggling is display-only */}
          </div>
        </div>
      </main>
    </div>
  );
}
