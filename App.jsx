import React, { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import IngestionPage from "./pages/IngestionPage";

import LandingPage from "./Landingpage.jsx";
import { RAW_PROPERTIES } from "./data/properties";

import { configureLeafletIcons } from "./utils/leaflet";
import { computeDashboardMetrics, getRiskScore } from "./utils/risk";
import {
  parseCSVFile,
  getIngestionSummary,
  getPortfolioSnapshot,
} from "./utils/ingestion";

configureLeafletIcons();

// Tabs
const TABS = [
  { id: "ingestion", label: "Ingestion & overview" },
  { id: "portfolio", label: "Underwriter dashboard" },
  { id: "stock", label: "Stock listing (Doc A)" },
  { id: "highvalue", label: "High value (Doc B)" },
];

const unique = (arr) => [...new Set(arr)];

// ✅ Safe formatters (prevents blank screen from undefined.toFixed)
const fmt = (n, digits = 2) => {
  const x = Number(n);
  return Number.isFinite(x) ? x.toFixed(digits) : "—";
};
const fmtMoneyM = (n, digits = 1) => {
  const x = Number(n);
  return Number.isFinite(x) ? (x / 1_000_000).toFixed(digits) : "—";
};
const fmtMoneyBn = (n, digits = 2) => {
  const x = Number(n);
  return Number.isFinite(x) ? (x / 1_000_000_000).toFixed(digits) : "—";
};

function App() {
  const [showLanding, setShowLanding] = useState(true);
  const [activeTab, setActiveTab] = useState("ingestion");

  const [search, setSearch] = useState("");
  const [cityFilter, setCityFilter] = useState("All");
  const [riskFilter, setRiskFilter] = useState("All");
  const [tenureFilter, setTenureFilter] = useState("All");

  const [uploadedData, setUploadedData] = useState(null);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [pipelineStep, setPipelineStep] = useState(null);

  const fileInputRef = useRef(null);

  // Leaflet map refs
  const mapDivRef = useRef(null);
  const leafletMapRef = useRef(null);
  const markerLayerRef = useRef(null);

  const PIPELINE_STEPS = [
    "Queued",
    "Checking file format",
    "Extracting text",
    "Normalising headings",
    "Identifying address + postcode",
    "Detecting sum insured fields",
    "Parsing rows",
    "Cleaning inconsistencies",
    "Running analytics",
    "Finalising",
    "Complete",
  ];

  const runPipeline = () => {
    setPipelineStep(PIPELINE_STEPS[0]);
    PIPELINE_STEPS.slice(1).forEach((step, i) => {
      setTimeout(() => setPipelineStep(step), 500 * (i + 1));
    });
  };

  const handleFiles = (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    setUploadError(null);
    setUploadedFiles(files.map((f) => ({ name: f.name, size: f.size })));
    setIsUploading(true);

    const csv = files.find((f) => f.name.toLowerCase().endsWith(".csv"));
    if (!csv) {
      setUploadError("Only CSV supported in demo.");
      setIsUploading(false);
      return;
    }

    runPipeline();

    parseCSVFile(
      csv,
      (parsed) => setUploadedData(parsed),
      (err) => setUploadError(err)
    );

    setTimeout(() => setIsUploading(false), PIPELINE_STEPS.length * 500);
  };

  const cities = useMemo(() => unique(RAW_PROPERTIES.map((p) => p.city)), []);
  const riskBands = useMemo(
    () => unique(RAW_PROPERTIES.map((p) => p.riskBand)),
    []
  );
  const tenures = useMemo(
    () => unique(RAW_PROPERTIES.map((p) => p.occupancyType)),
    []
  );

  const filtered = useMemo(
    () =>
      RAW_PROPERTIES.filter((p) => {
        const q = search.toLowerCase();
        const addr = `${p.address1 || ""} ${p.postcode || ""}`.toLowerCase();

        return (
          (!q || addr.includes(q)) &&
          (cityFilter === "All" || p.city === cityFilter) &&
          (riskFilter === "All" || p.riskBand === riskFilter) &&
          (tenureFilter === "All" || p.occupancyType === tenureFilter)
        );
      }),
    [search, cityFilter, riskFilter, tenureFilter]
  );

  const dashboardMetrics = useMemo(
    () => computeDashboardMetrics(RAW_PROPERTIES),
    []
  );

  const ingestionSummary = useMemo(
    () => getIngestionSummary(uploadedData),
    [uploadedData]
  );

  const portfolioSnapshot = useMemo(() => {
    if (uploadedData) return getPortfolioSnapshot(uploadedData);

    const total = RAW_PROPERTIES.reduce((s, p) => s + (p.sumInsured || 0), 0);

    return {
      source: "Demo portfolio",
      propertyCount: RAW_PROPERTIES.length,
      totalValue: total,
      missingCore: RAW_PROPERTIES.filter(
        (p) => !p.postcode || !p.address1 || !p.sumInsured
      ).length,
    };
  }, [uploadedData]);

  const citySummary = useMemo(() => {
    const map = new Map();

    RAW_PROPERTIES.forEach((p) => {
      if (!p.city) return;

      if (!map.has(p.city)) {
        map.set(p.city, {
          city: p.city,
          count: 0,
          totalValue: 0,
          latSum: 0,
          lonSum: 0,
        });
      }

      const c = map.get(p.city);
      c.count++;
      c.totalValue += p.sumInsured || 0;
      c.latSum += Number(p.lat) || 0;
      c.lonSum += Number(p.lon) || 0;
    });

    return [...map.values()].map((c) => {
      const lat = c.count ? c.latSum / c.count : 54.5;
      const lon = c.count ? c.lonSum / c.count : -3;

      const avgRisk =
        c.count > 0
          ? RAW_PROPERTIES.filter((p) => p.city === c.city).reduce(
              (s, p) => s + Number(getRiskScore(p) || 0),
              0
            ) / c.count
          : 0;

      return { city: c.city, count: c.count, totalValue: c.totalValue, lat, lon, avgRisk };
    });
  }, []);

  // ✅ Leaflet map init + marker render (no react-leaflet)

  // Group properties per city for popup detail
const propertiesByCity = useMemo(() => {
  const map = {};
  RAW_PROPERTIES.forEach((p) => {
    if (!p.city) return;
    if (!map[p.city]) map[p.city] = [];
    map[p.city].push(p);
  });
  return map;
}, []);

/* ========================= MAP INITIALISATION ========================= */

// create map ONLY when portfolio tab is first opened
useEffect(() => {
  if (activeTab !== "portfolio") return;
  if (!mapDivRef.current) return;
  if (leafletMapRef.current) return;

  const map = L.map(mapDivRef.current, {
    scrollWheelZoom: false,
    zoomControl: true,
  }).setView([54.5, -3], 5);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  leafletMapRef.current = map;
  markerLayerRef.current = L.layerGroup().addTo(map);

  // first render fix (React layout timing)
  setTimeout(() => map.invalidateSize(), 150);

}, [activeTab]);


/* ========================= READINESS COLOUR ========================= */

const getReadinessColour = (p) => {
  let score = 0;

  if (p.postcode) score++;
  if (p.sumInsured) score++;
  if (p.epcRating) score++;
  if (p.wallConstruction) score++;
  if (p.roofConstruction) score++;
  if (p.numberOfStoreys != null) score++;
  if (p.floodScore != null) score++;

  if (score <= 2) return "#ef4444";   // red
  if (score <= 5) return "#f59e0b";   // yellow
  return "#22c55e";                   // green
};


/* ========================= PROPERTY MARKERS ========================= */

useEffect(() => {
  if (!leafletMapRef.current || !markerLayerRef.current) return;

  const layer = markerLayerRef.current;
  layer.clearLayers();

  RAW_PROPERTIES.forEach((p) => {
    if (!p.lat || !p.lon) return;

    const colour = getReadinessColour(p);

    const marker = L.circleMarker([p.lat, p.lon], {
      radius: 8,
      fillColor: colour,
      color: "#1f2937",
      weight: 1,
      fillOpacity: 0.9,
    });

    marker.bindPopup(`
      <div style="min-width:240px; font-size:13px;">
        <strong style="font-size:14px;">${p.address1 || "Unknown address"}</strong><br/>
        ${p.address2 || ""}<br/>
        <b>${p.city || ""} ${p.postcode || ""}</b>

        <hr/>

        <b>Property</b><br/>
        Type: ${p.propertyType || "—"}<br/>
        Tenure: ${p.occupancyType || "—"}<br/>
        Floors: ${p.numberOfStoreys ?? "—"}<br/>
        Flats: ${p.numberOfFlats ?? "—"}

        <hr/>

        <b>Construction</b><br/>
        Walls: ${p.wallConstruction || "—"}<br/>
        Roof: ${p.roofConstruction || "—"}<br/>
        EPC: ${p.epcRating || "—"}

        <hr/>

        <b>Risk</b><br/>
        Flood score: ${fmt(p.floodScore,2)}<br/>
        Claim frequency: ${fmt(p.claimFrequency,2)} /yr<br/>
        Risk band: ${p.riskBand || "—"}

        <hr/>

        <b>Location</b><br/>
        Lat: ${fmt(p.lat,5)}<br/>
        Lon: ${fmt(p.lon,5)}
      </div>
    `);

    marker.addTo(layer);
  });

}, [activeTab]);


/* ========================= TAB SWITCH FIX ========================= */

useEffect(() => {
  if (activeTab !== "portfolio") return;
  if (!leafletMapRef.current) return;

  setTimeout(() => {
    leafletMapRef.current.invalidateSize();
  }, 120);

}, [activeTab]);

  // Optional cleanup if you ever want map destroyed when leaving tab:
  // (keep it persistent for speed; uncomment to fully remove on tab switch)
  /*
  useEffect(() => {
    if (activeTab === "portfolio") return;
    if (leafletMapRef.current) {
      leafletMapRef.current.remove();
      leafletMapRef.current = null;
      markerLayerRef.current = null;
    }
  }, [activeTab]);
  */

  if (showLanding) {
    return (
      <LandingPage
        onGetStarted={() => {
          setShowLanding(false);
          setActiveTab("ingestion");
        }}
      />
    );
  }

  return (
    <div className="app-root">
      <div className="app-shell">
        <header className="app-header">
          <button className="back-home-btn" onClick={() => setShowLanding(true)}>
            ⟵ Back
          </button>

          <div>
            <div className="app-badge">EquiRisk</div>
            <h1 className="app-title">Exposure & Data Quality Cockpit</h1>
            <p className="app-subtitle">
              Upload SOVs, analyse exposure, assess portfolio risk.
            </p>
          </div>

          <div className="app-meta">
            Ingestion-first MVP · Demo dataset used when no SOV uploaded
          </div>
        </header>

        <nav className="tab-bar">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tab ${activeTab === t.id ? "tab-active" : ""}`}
              onClick={() => setActiveTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {/* -------------------- INGESTION -------------------- */}
        {activeTab === "ingestion" && (
  <IngestionPage
    onFilesSelected={handleFiles}
    pipelineStep={pipelineStep}
    ingestionSummary={ingestionSummary}
  />
)}

        {/* -------------------- UNDERWRITER DASHBOARD -------------------- */}
        {activeTab === "portfolio" && (
          <div style={{ padding: "30px 40px", background: "#f5f5f5" }}>
            {/* KPI SUMMARY */}
            <section className="summary-grid">
              <div className="summary-card">
                <div className="summary-label">Total insured value</div>
                <div className="summary-value">
                  £{fmtMoneyBn(dashboardMetrics.totalValue, 2)}bn
                </div>
                <div className="summary-footnote">
                  Across {dashboardMetrics.propertyCount} properties
                </div>
              </div>

              <div className="summary-card">
                <div className="summary-label">Average risk score</div>
                <div className="summary-value">{fmt(dashboardMetrics.avgRiskScore, 2)}</div>
                <div className="summary-footnote">{dashboardMetrics.riskLabel}</div>
              </div>

              <div className="summary-card">
                <div className="summary-label">Flat roofs</div>
                <div className="summary-value">{dashboardMetrics.flatRoofPct}%</div>
                <div className="summary-footnote">Concentration of flat roofs</div>
              </div>
            </section>

            {/* MIDROW */}
            <section
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1.6fr",
                gap: 20,
                marginTop: 20,
              }}
            >
              {/* LEFT */}
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                {/* CRV vs ERV */}
                <div className="card">
                  <div className="card-header">
                    <h2 className="card-title">Reinstatement value comparison (demo)</h2>
                    <span className="card-badge">CRV vs ERV</span>
                  </div>

                  <div style={{ padding: 20 }}>
                    {[
                      { label: "Current (CRV)", pct: 68 },
                      { label: "Estimated (ERV)", pct: 75 },
                    ].map((bar) => (
                      <div key={bar.label} style={{ marginBottom: 16 }}>
                        <div style={{ marginBottom: 6, fontSize: 13 }}>{bar.label}</div>
                        <div style={{ height: 10, borderRadius: 999, background: "#e5e7eb" }}>
                          <div
                            style={{
                              height: "100%",
                              width: `${bar.pct}%`,
                              borderRadius: 999,
                              background: "#4f46e5",
                            }}
                          />
                        </div>
                      </div>
                    ))}

                    <div
                      style={{
                        marginTop: 6,
                        fontSize: 12,
                        display: "flex",
                        justifyContent: "space-between",
                        color: "#6b7280",
                      }}
                    >
                      <span>Indicative uplift (demo)</span>
                      <span>+7–8%</span>
                    </div>
                  </div>
                </div>

                {/* PERIL + FEATURES + MAINTENANCE */}
                <section
                  style={{
                    display: "grid",
                    gridTemplateColumns: "2fr 1fr 1fr",
                    gap: 20,
                  }}
                >
                  <div className="card">
                    <div className="card-header">
                      <h2 className="card-title">Peril risk distribution</h2>
                    </div>

                    <div style={{ padding: 20 }}>
                      {[
                        { label: "Combustibility", value: dashboardMetrics.combustibilityHotspots },
                        { label: "Fire exposure", value: dashboardMetrics.fireHotspots },
                        { label: "Flood exposure", value: dashboardMetrics.floodHotspots },
                        { label: "Flat roofs", value: dashboardMetrics.flatRoofPct },
                      ].map((i) => (
                        <div key={i.label} style={{ marginBottom: 12 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                            <span>{i.label}</span>
                            <span>{i.value}%</span>
                          </div>
                          <div style={{ height: 8, borderRadius: 999, background: "#e5e7eb", marginTop: 6 }}>
                            <div
                              style={{
                                height: "100%",
                                width: `${i.value}%`,
                                background: "#4f46e5",
                                borderRadius: 999,
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="card">
                    <div className="card-header">
                      <h2 className="card-title">Property features</h2>
                    </div>

                    <div style={{ padding: 20, fontSize: 13 }}>
                      <div style={{ marginBottom: 14 }}>
                        <div style={{ fontWeight: 600, marginBottom: 6 }}>
                          Properties with balconies (proxy)
                        </div>
                        <div className="summary-value" style={{ fontSize: 24 }}>
                          {dashboardMetrics.balconyPct}%
                        </div>
                        <div className="summary-footnote">Flats / high-rise used as proxy</div>
                      </div>

                      <div>
                        <div style={{ fontWeight: 600, marginBottom: 6 }}>Basements present</div>
                        <div className="summary-value" style={{ fontSize: 24 }}>
                          {dashboardMetrics.basementPct}%
                        </div>
                        <div className="summary-footnote">Flood / escape-of-water sensitivity</div>
                      </div>
                    </div>
                  </div>

                  <div className="card">
                    <div className="card-header">
                      <h2 className="card-title">Maintenance hotspots</h2>
                    </div>

                    <div style={{ padding: 20 }}>
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                          <span>Low maintenance score</span>
                          <span>{dashboardMetrics.maintenanceIssues}%</span>
                        </div>

                        <div style={{ height: 8, borderRadius: 999, background: "#e5e7eb", marginTop: 6 }}>
                          <div
                            style={{
                              height: "100%",
                              width: `${dashboardMetrics.maintenanceIssues}%`,
                              background: "#10b981",
                              borderRadius: 999,
                            }}
                          />
                        </div>
                      </div>

                      <div style={{ fontSize: 12, color: "#6b7280" }}>
                        Helps target survey / capex interventions.
                      </div>
                    </div>
                  </div>
                </section>
              </div>

              {/* RIGHT: MAP (Leaflet) */}
              <section className="card map-card" style={{ display: "flex", flexDirection: "column" }}>
                <div className="card-header">
                  <h2 className="card-title">Regional risk &amp; exposure</h2>
                  <span className="card-badge">Bubble = exposure · Colour = risk</span>
                </div>

                <div className="map-wrapper" style={{ flex: 1, minHeight: 260 }}>
                  <div
                    ref={mapDivRef}
                    style={{ height: "100%", width: "100%", borderRadius: 12 }}
                  />
                </div>
              </section>
            </section>

            {/* DETAIL TABLE */}
            <section className="card" style={{ marginTop: 24 }}>
              <div className="card-header">
                <h2 className="card-title">Property detail (optional)</h2>

                <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                  <span className="filter-label">Filter</span>

                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="input"
                    placeholder="Search by address / postcode"
                    style={{ maxWidth: 240 }}
                  />

                  <select
                    value={cityFilter}
                    onChange={(e) => setCityFilter(e.target.value)}
                    className="input"
                    style={{ maxWidth: 160 }}
                  >
                    <option value="All">All cities</option>
                    {cities.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>

                  <select
                    value={riskFilter}
                    onChange={(e) => setRiskFilter(e.target.value)}
                    className="input"
                    style={{ maxWidth: 160 }}
                  >
                    <option value="All">All risk bands</option>
                    {riskBands.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>

                  <select
                    value={tenureFilter}
                    onChange={(e) => setTenureFilter(e.target.value)}
                    className="input"
                    style={{ maxWidth: 160 }}
                  >
                    <option value="All">All tenure</option>
                    {tenures.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="table-wrapper">
                <table className="risk-table">
                  <thead>
                    <tr>
                      <th>Property</th>
                      <th>Geo / Indices</th>
                      <th>Construction</th>
                      <th>Perils</th>
                    </tr>
                  </thead>

                  <tbody>
                    {filtered.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <div className="prop-main">
                            {p.address1} {p.address2 || ""}
                          </div>
                          <div className="prop-sub">
                            {p.city} {p.postcode}
                          </div>
                          <div className="prop-sub">
                            {p.propertyType} · {p.occupancyType}
                          </div>
                          <div className="prop-meta">
                            Ref {p.propertyReference} · Block {p.blockReference}
                          </div>
                        </td>

                        <td>
                          <div className="cell-strong">
                            Deprivation index: <span>{fmt(p.deprivationIndex, 1)}</span>
                          </div>
                          <div className="cell-muted">Crime index: {fmt(p.crimeIndex, 1)}</div>
                          <div className="cell-muted">Void days: {p.voidDaysLastYear ?? "—"}</div>
                          <div className="cell-meta">
                            lat {fmt(p.lat, 3)}, lon {fmt(p.lon, 3)}
                          </div>
                        </td>

                        <td>
                          <div className="cell-strong">Walls: {p.wallConstruction || "—"}</div>
                          <div className="cell-muted">Roof: {p.roofConstruction || "—"}</div>
                          <div className="cell-muted">Storeys: {p.numberOfStoreys ?? "—"}</div>
                          <div className="cell-muted">EPC: {p.epcRating || "—"}</div>
                        </td>

                        <td>
                          <div className="cell-strong">
                            Flood insured: {p.floodInsured ? "Yes" : "No"}
                          </div>
                          <div className="cell-muted">
                            Storm insured: {p.stormInsured ? "Yes" : "No"}
                          </div>
                          <div className="cell-muted">Flood score: {fmt(p.floodScore, 2)}</div>
                          <div className="cell-muted">
                            Claim frequency: {fmt(p.claimFrequency, 2)} / yr
                          </div>
                        </td>
                      </tr>
                    ))}

                    {filtered.length === 0 && (
                      <tr>
                        <td colSpan={4} className="empty-row">
                          No properties match the current filters
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}

        {/* -------------------- PLACEHOLDER TABS -------------------- */}
        {activeTab === "stock" && (
          <div style={{ padding: 40 }}>
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Stock listing (Doc A)</h2>
                <span className="card-badge">Placeholder</span>
              </div>
              <div style={{ padding: 24, color: "#6b7280" }}>
                Coming next — table view aligned to the “Doc A” layout.
              </div>
            </div>
          </div>
        )}

        {activeTab === "highvalue" && (
          <div style={{ padding: 40 }}>
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">High value (Doc B)</h2>
                <span className="card-badge">Placeholder</span>
              </div>
              <div style={{ padding: 24, color: "#6b7280" }}>
                Coming next — high value drill-down aligned to the “Doc B” layout.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
