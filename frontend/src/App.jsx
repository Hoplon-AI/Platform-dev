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

const fmt = (n, digits = 4) => {
  const x = Number(n);
  return Number.isFinite(x) ? x.toFixed(digits) : "—";
};

const readinessBandFromScore = (score) => {
  const s = Number(score) || 0;
  if (s >= 80) return "Green";
  if (s >= 50) return "Amber";
  return "Red";
};

const readinessColor = (bandOrScore) => {
  const b = String(bandOrScore || "").toLowerCase();
  if (b.includes("green")) return "#22c55e";
  if (b.includes("amber") || b.includes("yellow")) return "#f59e0b";
  return "#ef4444";
};

function Donut({ value = 0 }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  const band = readinessBandFromScore(v);
  const color = readinessColor(band);

  return (
    <div className="donut">
      <div
        className="donut-ring"
        style={{
          background: `conic-gradient(${color} ${v}%, rgba(15,23,42,.10) 0)`,
        }}
      />
      <div className="donut-center">
        <div className="donut-value">{v}</div>
        <div className="donut-sub">/ 100</div>
      </div>
      <div className="donut-caption">
        <span className={`pill pill-${band.toLowerCase()}`}>{band}</span>
        <span className="muted">Readiness score</span>
      </div>
    </div>
  );
}

function Bar({ label, value }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className="bar">
      <div className="bar-top">
        <div className="bar-label">{label}</div>
        <div className="bar-value">{v}%</div>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${v}%` }} />
      </div>
    </div>
  );
}

function RawFieldsTable({ raw }) {
  const entries = useMemo(() => {
    if (!raw) return [];
    return Object.entries(raw)
      .map(([k, v]) => [String(k), String(v ?? "")])
      .sort((a, b) => a[0].localeCompare(b[0]));
  }, [raw]);

  if (!entries.length) return null;

  return (
    <div className="raw-table">
      <div className="raw-title">Raw fields (from upload)</div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([k, v]) => (
              <tr key={k}>
                <td className="td-key">{k}</td>
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
  const [showLanding, setShowLanding] = useState(true);
  const [activeNav, setActiveNav] = useState("overview");

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [pipelineStep, setPipelineStep] = useState(null);

  const [ingestionResult, setIngestionResult] = useState(null);
  const ingestionSummary = useMemo(
    () => getIngestionSummary(ingestionResult),
    [ingestionResult]
  );

  const [selectedProperty, setSelectedProperty] = useState(null);
  const [mapVersion, setMapVersion] = useState(0);

  const PIPELINE_STEPS = [
    "Queued",
    "Checking file format",
    "Reading file",
    "Normalising columns",
    "Coercing types",
    "Computing readiness scores",
    "Finalising",
    "Complete",
  ];

  const runPipeline = () => {
    setPipelineStep(PIPELINE_STEPS[0]);
    PIPELINE_STEPS.slice(1).forEach((step, i) => {
      setTimeout(() => setPipelineStep(step), 380 * (i + 1));
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
        setIngestionResult(result);
        setSelectedProperty(null);
        setIsUploading(false);
        setPipelineStep("Complete");
        setActiveNav("overview");
        setMapVersion((v) => v + 1);
        setTimeout(() => setPipelineStep(null), 900);
      },
      (err) => {
        setUploadError(err);
        setIsUploading(false);
      }
    );
  };

  const properties = useMemo(() => ingestionResult?.properties || [], [ingestionResult]);
  const mappable = useMemo(
    () => properties.filter((p) => p.hasValidCoords),
    [properties]
  );

  const mapDivRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);

  const ensureMap = () => {
    if (!mapDivRef.current || mapRef.current) return;

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
    if (mapRef.current) {
      mapRef.current.invalidateSize(true);
    }
  };

  const renderMarkers = () => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    mappable.forEach((p) => {
      const lat = Number(p.latitude);
      const lon = Number(p.longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

      const band = p.readiness_band || readinessBandFromScore(p.readiness_score);
      const color = readinessColor(band);
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
        fillOpacity: 0.55,
      });

      circle.on("click", () => {
        setSelectedProperty(p);
        map.setView([lat, lon], 13, { animate: true });
      });

      const label = p.address_line_1 || p.post_code || p.city || p.uprn || p.id;

      circle.bindTooltip(`${label} · readiness ${p.readiness_score ?? "—"}`, {
        direction: "top",
        sticky: true,
        opacity: 0.95,
      });

      circle.addTo(layer);
    });

    if (!selectedProperty && mappable.length > 0) {
      const coords = mappable
        .map((p) => [Number(p.latitude), Number(p.longitude)])
        .filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b));

      if (coords.length) {
        const bounds = L.latLngBounds(coords);
        if (bounds.isValid()) map.fitBounds(bounds.pad(0.15));
      }
    }
  };

  useEffect(() => {
    if (activeNav !== "overview") return;
    ensureMap();
    setTimeout(() => invalidateMap(), 120);
  }, [activeNav]);

  useEffect(() => {
    if (activeNav !== "overview") return;
    ensureMap();
    setTimeout(() => {
      invalidateMap();
      renderMarkers();
    }, 80);
  }, [activeNav, mapVersion, mappable, selectedProperty]);

  useEffect(() => {
    if (!selectedProperty) return;
    const map = mapRef.current;
    const lat = Number(selectedProperty.latitude);
    const lon = Number(selectedProperty.longitude);
    if (!map || !Number.isFinite(lat) || !Number.isFinite(lon)) return;
    map.setView([lat, lon], 13, { animate: true });
  }, [selectedProperty]);

  if (showLanding) {
    return (
      <LandingPage
        onGetStarted={() => {
          setShowLanding(false);
          setActiveNav("uploads");
        }}
      />
    );
  }

  const loadedMeta = ingestionSummary
    ? `Loaded: ${ingestionSummary.source} · Properties: ${ingestionSummary.propertyCount} · Value: £${fmtMoney(
        ingestionSummary.totalValue
      )}`
    : "Upload a file to begin";

  const avgReadiness = ingestionSummary?.avgReadiness ?? 0;
  const uprnMatchPct = ingestionSummary?.uprnMatchPct ?? 0;

  const addrCompletenessPct = ingestionSummary?.addrCompletenessPct ?? 0;
  const geoCompletenessPct = ingestionSummary?.geoCompletenessPct ?? 0;
  const sovCompletenessPct = ingestionSummary?.sovCompletenessPct ?? 0;

  const p = selectedProperty;

  return (
    <div className="app">
      <div className="topbar">
        <div className="topbar-left">
          Upload SOVs, analyse exposure, assess portfolio risk.
        </div>
        <div className="topbar-right">{loadedMeta}</div>
      </div>

      <div className="shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-title">EquiRisk</div>
            <div className="pill pill-muted">UNDERWRITER</div>
          </div>

          <div className="side-section">
            <div className="side-head">Portfolio Overview</div>
            <button
              className={`side-link ${activeNav === "overview" ? "active" : ""}`}
              onClick={() => setActiveNav("overview")}
            >
              Portfolio Overview
            </button>
            <button
              className={`side-link ${activeNav === "uploads" ? "active" : ""}`}
              onClick={() => setActiveNav("uploads")}
            >
              Upload SoV
            </button>
          </div>

          <div className="side-section dim">
            <div className="side-head">Shared Portfolios</div>
            <div className="side-item">Evidence Summary</div>
            <div className="side-item">Block Analysis</div>
            <div className="side-item">Settings</div>
          </div>

          <div className="side-bottom">
            <button className="btn btn-ghost" onClick={() => setShowLanding(true)}>
              ⟵ Back
            </button>
          </div>
        </aside>

        <main className="main">
          <div className="main-head">
            <div>
              <div className="page-title">
                {activeNav === "overview" ? "Portfolio Overview" : "Upload SoV"}
              </div>
              <div className="page-sub">
                {activeNav === "overview"
                  ? "What’s in the submission and where it is (based on your uploaded SoV)."
                  : "Upload an SOV-style file. We’ll normalise fields and compute readiness."}
              </div>
            </div>

            <div className="actions">
              {activeNav === "overview" && (
                <>
                  <button className="btn" onClick={() => setActiveNav("uploads")}>
                    Upload new SoV
                  </button>
                  <button className="btn btn-primary" onClick={() => setActiveNav("overview")}>
                    View on map
                  </button>
                </>
              )}
            </div>
          </div>

          {activeNav === "uploads" && (
            <IngestionPage
              onFilesSelected={handleFiles}
              pipelineStep={pipelineStep}
              ingestionSummary={ingestionSummary}
              uploadError={uploadError}
              isUploading={isUploading}
            />
          )}

          {activeNav === "overview" && (
            <div className="content-wrap">
              {!ingestionSummary ? (
                <div className="card">
                  <div className="empty-state">
                    No portfolio loaded yet. Go to <b>Upload SoV</b> to ingest a file.
                  </div>
                </div>
              ) : (
                <>
                  <div className="card banner">
                    <div className="banner-left">
                      <div className="pill pill-amber">READY</div>
                      <div className="banner-title">Ready for quote submission</div>
                      <div className="banner-sub">
                        Your portfolio has minor evidence gaps but can be quoted. Improving
                        missing fields will move you toward <b>Green</b>.
                      </div>

                      <div className="banner-actions">
                        <button className="btn btn-primary">Generate Action Plan</button>
                        <button className="btn">Export Underwriter Pack</button>
                      </div>
                    </div>

                    <div className="banner-right">
                      <Donut value={avgReadiness} />
                    </div>
                  </div>

                  <div className="dashboard-grid">
                    <div className="dashboard-card">
                      <div className="dashboard-card-title">Total insured value</div>
                      <div className="dashboard-card-value">
                        £{fmtMoney(ingestionSummary.totalValue)}
                      </div>
                      <div className="dashboard-card-sub">
                        Across {ingestionSummary.propertyCount} properties
                      </div>
                    </div>

                    <div className="dashboard-card">
                      <div className="dashboard-card-title">UPRN match</div>
                      <div className="dashboard-card-value">{uprnMatchPct}%</div>
                      <div className="dashboard-card-sub">
                        Properties with UPRN present
                      </div>
                    </div>

                    <div className="dashboard-card">
                      <div className="dashboard-card-title">Mappable locations</div>
                      <div className="dashboard-card-value">
                        {ingestionSummary.mappableCount}
                      </div>
                      <div className="dashboard-card-sub">
                        Invalid coords skipped: {ingestionSummary.skippedInvalidCoords}
                      </div>
                    </div>
                  </div>

                  <div className="card confidence-card">
                    <div className="card-header row-between">
                      <div>
                        <div className="card-title">Confidence scores by domain</div>
                        <div className="card-subtitle">
                          Ongoing portfolio completeness metrics
                        </div>
                      </div>
                      <span className="pill pill-muted">MVP</span>
                    </div>

                    <div className="bars">
                      <Bar
                        label="Addresses & UPRN verification"
                        value={Math.round((addrCompletenessPct + uprnMatchPct) / 2)}
                      />
                      <Bar
                        label="Geo coverage (valid lat/lon)"
                        value={geoCompletenessPct}
                      />
                      <Bar
                        label="SOV core fields (sum insured, type, height)"
                        value={sovCompletenessPct}
                      />
                    </div>
                  </div>

                  <div className="two-col">
                    <div className="card">
                      <div className="card-header row-between">
                        <div className="card-title">Portfolio map</div>
                        <span className="pill pill-muted">
                          Readiness: green ≥ 80 • amber ≥ 50 • red &lt; 50
                        </span>
                      </div>

                      <div className="map-wrap">
                        <div key={`map-${mapVersion}`} ref={mapDivRef} className="map" />
                      </div>

                      <div className="map-foot">
                        Mappable: {ingestionSummary.mappableCount} • Invalid coords skipped:{" "}
                        {ingestionSummary.skippedInvalidCoords}
                      </div>
                    </div>

                    <div className="card">
                      <div className="card-header row-between">
                        <div className="card-title">Details</div>
                        <span className="pill pill-muted">
                          {p ? "Selected" : "Click a circle"}
                        </span>
                      </div>

                      <div className="details-body">
                        {!p ? (
                          <div className="muted">
                            Click a property circle on the map to zoom in and view SOV + property
                            details here.
                          </div>
                        ) : (
                          <>
                            <div className="details-block">
                              <div className="details-h">Property</div>
                              <div className="details-sub">
                                {p.city || "—"} {p.post_code ? `· ${p.post_code}` : ""}{" "}
                                {`· lat ${fmt(p.latitude, 5)}, lon ${fmt(p.longitude, 5)}`}
                              </div>
                              <div className="details-title">
                                {p.address_line_1 || "—"} {p.address_line_2 || ""}
                              </div>

                              {p.uprn && (
                                <div className="details-sub" style={{ marginTop: 6 }}>
                                  <b>UPRN:</b> {p.uprn}
                                </div>
                              )}
                            </div>

                            <div className="details-block">
                              <div className="details-h">Readiness</div>
                              <div className="readiness-row">
                                <span
                                  className="dot"
                                  style={{ background: readinessColor(p.readiness_band) }}
                                />
                                <div className="readiness-score">
                                  {p.readiness_score ?? "—"} / 100{" "}
                                  <span className="muted">
                                    ({p.readiness_band || readinessBandFromScore(p.readiness_score)})
                                  </span>
                                </div>
                              </div>
                              {(p.missing_fields || []).length > 0 ? (
                                <div className="muted" style={{ marginTop: 6 }}>
                                  <b>Missing:</b> {(p.missing_fields || []).join(", ")}
                                </div>
                              ) : (
                                <div className="muted" style={{ marginTop: 6 }}>
                                  No missing core fields detected.
                                </div>
                              )}
                            </div>

                            <div className="details-block">
                              <div className="details-h">SOV</div>
                              <div className="kv-grid">
                                <div className="kv">
                                  <div className="kv-k">Sum insured</div>
                                  <div className="kv-v">
                                    {Number.isFinite(Number(p.sum_insured))
                                      ? `£${fmtMoney(p.sum_insured)}`
                                      : "—"}
                                  </div>
                                </div>
                                <div className="kv">
                                  <div className="kv-k">Property type</div>
                                  <div className="kv-v">{p.property_type || "—"}</div>
                                </div>
                                <div className="kv">
                                  <div className="kv-k">Occupancy</div>
                                  <div className="kv-v">{p.occupancy_type || "—"}</div>
                                </div>
                                <div className="kv">
                                  <div className="kv-k">Height</div>
                                  <div className="kv-v">
                                    {Number.isFinite(Number(p.height_m))
                                      ? `${fmt(p.height_m, 1)} m`
                                      : "—"}
                                  </div>
                                </div>
                              </div>
                            </div>

                            <RawFieldsTable raw={p.raw} />
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
