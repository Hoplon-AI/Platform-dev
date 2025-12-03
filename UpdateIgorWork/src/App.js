// App.js – complete, fixed version

import React, { useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import Papa from "papaparse";

import "./styles.css";
import LandingPage from "./LandingPage";
import { RAW_PROPERTIES } from "./data/properties";

// Fix default Leaflet marker icons
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Tabs
const TABS = [
  { id: "ingestion", label: "Ingestion & overview" },
  { id: "portfolio", label: "Underwriter dashboard" },
  { id: "stock", label: "Stock listing (Doc A)" },
  { id: "highvalue", label: "High value (Doc B)" },
];

const unique = (arr) => [...new Set(arr)];

const RISK_BAND_SCORE = {
  Low: 0.35,
  Medium: 0.55,
  High: 0.75,
  "Very High": 0.9,
};

function getRiskScore(property) {
  return RISK_BAND_SCORE[property.riskBand] ?? 0.55;
}

function App() {
  const [showLanding, setShowLanding] = useState(true);
  const [activeTab, setActiveTab] = useState("ingestion");

  // Filters
  const [search, setSearch] = useState("");
  const [cityFilter, setCityFilter] = useState("All");
  const [riskFilter, setRiskFilter] = useState("All");
  const [tenureFilter, setTenureFilter] = useState("All");

  // Upload state
  const [uploadedData, setUploadedData] = useState(null);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [pipelineStep, setPipelineStep] = useState(null);

  const fileInputRef = useRef(null);

  // ----------------------------
  //        INGESTION PIPELINE
  // ----------------------------

  const PIPELINE_STEPS = [
    "Queued",
    "Checking file format",
    "Extracting text / structured content",
    "Normalising headings",
    "Identifying address + postcode",
    "Detecting sum insured fields",
    "Parsing rows",
    "Cleaning inconsistencies",
    "Running analytics",
    "Finalising",
    "Complete",
  ];

  const runIngestionPipeline = async () => {
    setPipelineStep("Queued");
    for (let i = 1; i < PIPELINE_STEPS.length; i++) {
      // simulate async stages
      // eslint-disable-next-line no-await-in-loop
      await new Promise((res) => setTimeout(res, 450));
      setPipelineStep(PIPELINE_STEPS[i]);
    }
  };

  const parseCSV = (file) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const cleanedColumns = Object.keys(results.data[0] || {}).map((col) =>
          col.trim()
        );

        const cleanedData = results.data.map((row) => {
          const newRow = {};
          cleanedColumns.forEach((col) => {
            newRow[col] = (row[col] ?? "").toString().trim();
          });
          return newRow;
        });

        setUploadedData({
          columns: cleanedColumns,
          data: cleanedData,
          row_count: cleanedData.length,
        });
      },
      error: (err) => {
        setUploadError(err.message);
      },
    });
  };

  const handleFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    setUploadError(null);
    setUploadedFiles(
      files.map((f) => ({
        name: f.name,
        size: f.size,
        type: f.type || "unknown",
        status: "Queued",
      }))
    );
    setIsUploading(true);

    const csvFile = files.find((f) => f.name.toLowerCase().endsWith(".csv"));
    if (!csvFile) {
      setUploadedData(null);
      setIsUploading(false);
      return;
    }

    await runIngestionPipeline(csvFile);
    parseCSV(csvFile);

    setIsUploading(false);
    setUploadedFiles((prev) =>
      prev.map((f) =>
        f.name === csvFile.name ? { ...f, status: "Complete" } : f
      )
    );
  };

  const handleFileInputChange = (e) => {
    if (!e.target.files?.length) return;
    handleFiles(e.target.files);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
      e.dataTransfer.clearData();
    }
  };

  const handleDragOver = (e) => e.preventDefault();

  // ----------------------------
  //       PORTFOLIO DERIVED DATA
  // ----------------------------

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
        const fullAddress =
          `${p.address1} ${p.address2} ${p.address3}`.toLowerCase();
        const q = search.toLowerCase();

        const matchesSearch =
          !q ||
          fullAddress.includes(q) ||
          p.postcode.toLowerCase().includes(q) ||
          (p.propertyReference || "").toLowerCase().includes(q);

        const matchesCity = cityFilter === "All" || p.city === cityFilter;
        const matchesRisk = riskFilter === "All" || p.riskBand === riskFilter;
        const matchesTenure =
          tenureFilter === "All" || p.occupancyType === tenureFilter;

        return matchesSearch && matchesCity && matchesRisk && matchesTenure;
      }),
    [search, cityFilter, riskFilter, tenureFilter]
  );

  const highValueProps = useMemo(
    () => RAW_PROPERTIES.filter((p) => !!p.docBRef),
    []
  );

  const byOccupancy = useMemo(() => {
    const map = new Map();
    RAW_PROPERTIES.forEach((p) => {
      const key = p.occupancyType || "Unknown";
      const prev = map.get(key) || { units: 0, sum: 0 };
      map.set(key, {
        units: prev.units + (p.numberOfUnits || 0),
        sum: prev.sum + (p.sumInsured || 0),
      });
    });
    return Array.from(map.entries()).map(([k, v]) => ({
      occupancy: k,
      units: v.units,
      sumInsured: v.sum,
    }));
  }, []);

  const byBlock = useMemo(() => {
    const map = new Map();
    RAW_PROPERTIES.forEach((p) => {
      const key = p.blockReference || "Unknown";
      const prev = map.get(key) || { units: 0, sum: 0 };
      map.set(key, {
        units: prev.units + (p.numberOfUnits || 0),
        sum: prev.sum + (p.sumInsured || 0),
      });
    });
    return Array.from(map.entries()).map(([k, v]) => ({
      block: k,
      units: v.units,
      sumInsured: v.sum,
    }));
  }, []);

  // Dashboard metrics
  const dashboardMetrics = useMemo(() => {
    const props = RAW_PROPERTIES;
    const count = props.length || 1;

    let totalValue = 0;
    let riskSum = 0;
    let flatRoofCount = 0;
    let basementCount = 0;
    let balconyCount = 0;

    props.forEach((p) => {
      totalValue += p.sumInsured || 0;
      riskSum += getRiskScore(p);

      if ((p.roofConstruction || "").toLowerCase().includes("flat"))
        flatRoofCount += 1;
      if (p.basementLocation && p.basementLocation.toLowerCase() !== "none")
        basementCount += 1;
      if ((p.propertyType || "").toLowerCase().includes("flat"))
        balconyCount += 1;
    });

    const avgRiskScore = riskSum / count;
    const riskLabel =
      avgRiskScore < 0.4 ? "Low" : avgRiskScore < 0.65 ? "Moderate" : "High";

    const combustibilityHotspots = Math.round(
      (props.filter((p) =>
        (p.claddingType || p.wallConstruction || "")
          .toLowerCase()
          .includes("cladding")
      ).length /
        count) *
        100
    );

    const fireHotspots = Math.round(
      (props.filter((p) =>
        (p.fireProtection || "").toLowerCase().includes("battery")
      ).length /
        count) *
        100
    );

    const floodHotspots = Math.round(
      (props.filter((p) => (p.floodScore || 0) > 0.5).length / count) * 100
    );

    const maintenanceIssues = Math.round(
      (props.filter((p) => (p.maintenanceScore || 0) < 6).length / count) * 100
    );

    return {
      totalValue,
      propertyCount: props.length,
      avgRiskScore,
      riskLabel,
      flatRoofPct: Math.round((flatRoofCount / count) * 100),
      basementPct: Math.round((basementCount / count) * 100),
      balconyPct: Math.round((balconyCount / count) * 100),
      combustibilityHotspots,
      fireHotspots,
      floodHotspots,
      maintenanceIssues,
    };
  }, []);

  // Map city summary
  const citySummary = useMemo(() => {
    const map = new Map();
    RAW_PROPERTIES.forEach((p) => {
      if (!p.city) return;
      if (!map.has(p.city)) {
        map.set(p.city, {
          city: p.city,
          count: 0,
          totalValue: 0,
          riskSum: 0,
          lat: 0,
          lon: 0,
        });
      }
      const entry = map.get(p.city);
      entry.count += 1;
      entry.totalValue += p.sumInsured || 0;
      entry.riskSum += getRiskScore(p);
      entry.lat += p.lat;
      entry.lon += p.lon;
    });

    return [...map.values()].map((c) => ({
      ...c,
      avgRisk: c.riskSum / c.count,
      lat: c.lat / c.count,
      lon: c.lon / c.count,
    }));
  }, []);

  // Portfolio snapshot
  const portfolioSnapshot = useMemo(() => {
    if (uploadedData && uploadedData.data.length) {
      const rows = uploadedData.data;
      const colsLower = uploadedData.columns.map((c) => c.toLowerCase());

      const sumColIndex = colsLower.findIndex(
        (c) => c.includes("sum") && c.includes("insured")
      );
      const postcodeIndex = colsLower.findIndex((c) => c.includes("postcode"));
      const addressIndex = colsLower.findIndex((c) => c.includes("address"));

      let totalValue = 0;
      let missingCore = 0;

      rows.forEach((row) => {
        if (sumColIndex !== -1) {
          const key = uploadedData.columns[sumColIndex];
          const raw = row[key] ?? "";
          const numeric = parseFloat(String(raw).replace(/[^0-9.]/g, ""));
          if (!Number.isNaN(numeric)) totalValue += numeric;
        }

        const postcodeKey =
          postcodeIndex !== -1 ? uploadedData.columns[postcodeIndex] : null;
        const addressKey =
          addressIndex !== -1 ? uploadedData.columns[addressIndex] : null;

        const missingPostcode = !postcodeKey || !row[postcodeKey];
        const missingAddress = !addressKey || !row[addressKey];

        if (missingPostcode || missingAddress) missingCore += 1;
      });

      return {
        source: "Uploaded SOV",
        propertyCount: rows.length,
        totalValue: totalValue || null,
        missingCore,
      };
    }

    const rows = RAW_PROPERTIES;
    const propertyCount = rows.length;
    const totalValue = rows.reduce((s, p) => s + (p.sumInsured || 0), 0);
    const missingCore = rows.filter(
      (p) => !p.postcode || !p.address1 || !p.sumInsured
    ).length;

    return {
      source: "Demo portfolio",
      propertyCount,
      totalValue,
      missingCore,
    };
  }, [uploadedData]);

  // ----------------------------
  //      LANDING PAGE SWITCH
  // ----------------------------

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

  // ----------------------------
  //         MAIN APP UI
  // ----------------------------

  return (
    <div className="app-root">
      <div className="app-shell">
        {/* HEADER */}
        <header className="app-header">
          <button
            className="back-home-btn"
            onClick={() => setShowLanding(true)}
          >
            ⟵ Back to Home
          </button>

          <div>
            <div className="app-badge">EquiRisk • Underwriter workspace</div>
            <h1 className="app-title">Exposure &amp; Data Quality Cockpit</h1>
            <p className="app-subtitle">
              Drag &amp; drop schedules of values, see ingestion progress,
              understand missing info, and assess exposure before touching
              pricing.
            </p>
          </div>

          <div className="app-meta">
            Ingestion-first MVP · Demo dataset used when no SOV uploaded
          </div>
        </header>

        {/* TABS */}
        <nav className="tab-bar">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`tab ${activeTab === tab.id ? "tab-active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* TAB 1: INGESTION */}
        {activeTab === "ingestion" && (
          <div style={{ padding: "30px 40px", background: "#f5f5f5" }}>
            <section className="card">
              <div className="card-header">
                <h2 className="card-title">Upload schedules of values</h2>
                <span className="card-badge">
                  Excel · CSV · PDF · Word (CSV parsed client-side)
                </span>
              </div>

              <div
                style={{
                  padding: 24,
                  display: "flex",
                  gap: 24,
                  flexWrap: "wrap",
                }}
              >
                {/* DRAG & DROP */}
                <div
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    flex: 2,
                    minWidth: 280,
                    border: "2px dashed #c7d2fe",
                    borderRadius: 12,
                    padding: 32,
                    textAlign: "center",
                    background: "#eef2ff",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="file"
                    multiple
                    accept=".csv,.xlsx,.xls,.pdf,.doc,.docx"
                    ref={fileInputRef}
                    style={{ display: "none" }}
                    onChange={handleFileInputChange}
                  />

                  <div
                    style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}
                  >
                    Drag &amp; drop SOV files here
                  </div>

                  <div
                    style={{
                      fontSize: 13,
                      color: "#4b5563",
                      marginBottom: 12,
                    }}
                  >
                    EquiRisk extracts, cleans, normalises and analyses your
                    stock listing / SOV automatically.
                  </div>

                  <div style={{ fontSize: 12, color: "#6b7280" }}>
                    Pipeline includes AI extraction, address normalisation,
                    missing value detection, and exposure cleansing.
                  </div>
                </div>

                {/* INGESTION STATUS */}
                <div style={{ flex: 1.4, minWidth: 260 }}>
                  <div
                    style={{
                      marginBottom: 16,
                      padding: 16,
                      borderRadius: 12,
                      border: "1px solid #e5e7eb",
                      background: "#fff",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        marginBottom: 8,
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                        color: "#6b7280",
                      }}
                    >
                      Ingestion status
                    </div>

                    {isUploading && pipelineStep && (
                      <div
                        style={{
                          padding: 12,
                          background: "#eef2ff",
                          borderRadius: 8,
                          marginBottom: 10,
                          fontSize: 13,
                          border: "1px solid #c7d2fe",
                        }}
                      >
                        <strong>{pipelineStep}</strong>
                        <div
                          style={{
                            marginTop: 8,
                            width: "100%",
                            height: 6,
                            background: "#e0e7ff",
                            borderRadius: 4,
                          }}
                        >
                          <div
                            style={{
                              width: `${
                                (PIPELINE_STEPS.indexOf(pipelineStep) /
                                  (PIPELINE_STEPS.length - 1)) *
                                100
                              }%`,
                              height: "100%",
                              background: "#4f46e5",
                              borderRadius: 4,
                              transition: "width 0.4s ease",
                            }}
                          />
                        </div>
                      </div>
                    )}

                    {uploadError && (
                      <div
                        style={{
                          background: "#fee2e2",
                          padding: 10,
                          borderRadius: 6,
                          color: "#b91c1c",
                          fontSize: 12,
                        }}
                      >
                        Error: {uploadError}
                      </div>
                    )}

                    {!uploadedFiles.length && !isUploading && !uploadError && (
                      <div style={{ fontSize: 13, color: "#9ca3af" }}>
                        No files uploaded yet.
                      </div>
                    )}

                    {uploadedFiles.length > 0 && (
                      <ul
                        style={{
                          listStyle: "none",
                          padding: 0,
                          margin: 0,
                          fontSize: 13,
                        }}
                      >
                        {uploadedFiles.map((f) => (
                          <li
                            key={f.name}
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              padding: "6px 0",
                            }}
                          >
                            <span>
                              {f.name}{" "}
                              <span style={{ color: "#9ca3af" }}>
                                ({Math.round(f.size / 1024)} KB)
                              </span>
                            </span>
                            <span
                              style={{
                                color:
                                  f.status === "Complete"
                                    ? "#16a34a"
                                    : "#4f46e5",
                              }}
                            >
                              {f.status}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  {/* PORTFOLIO SNAPSHOT */}
                  <div
                    style={{
                      padding: 16,
                      borderRadius: 12,
                      border: "1px solid #e5e7eb",
                      background: "#fff",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        marginBottom: 8,
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                        color: "#6b7280",
                      }}
                    >
                      Portfolio snapshot
                    </div>

                    <div
                      style={{
                        fontSize: 12,
                        color: "#9ca3af",
                        marginBottom: 12,
                      }}
                    >
                      Source: {portfolioSnapshot.source}
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(3, 1fr)",
                        gap: 12,
                      }}
                    >
                      <div>
                        <div
                          style={{
                            fontSize: 11,
                            textTransform: "uppercase",
                            letterSpacing: "0.06em",
                            color: "#9ca3af",
                            marginBottom: 4,
                          }}
                        >
                          Properties
                        </div>
                        <div
                          style={{
                            fontSize: 22,
                            fontWeight: 700,
                            color: "#111827",
                          }}
                        >
                          {portfolioSnapshot.propertyCount}
                        </div>
                      </div>

                      <div>
                        <div
                          style={{
                            fontSize: 11,
                            textTransform: "uppercase",
                            letterSpacing: "0.06em",
                            color: "#9ca3af",
                            marginBottom: 4,
                          }}
                        >
                          Total value
                        </div>
                        <div
                          style={{
                            fontSize: 18,
                            fontWeight: 600,
                            color: "#111827",
                          }}
                        >
                          {portfolioSnapshot.totalValue
                            ? `£${(
                                portfolioSnapshot.totalValue / 1_000_000
                              ).toFixed(1)}m`
                            : "—"}
                        </div>
                      </div>

                      <div>
                        <div
                          style={{
                            fontSize: 11,
                            textTransform: "uppercase",
                            letterSpacing: "0.06em",
                            color: "#9ca3af",
                            marginBottom: 4,
                          }}
                        >
                          Missing core
                        </div>
                        <div
                          style={{
                            fontSize: 22,
                            fontWeight: 700,
                            color:
                              portfolioSnapshot.missingCore > 0
                                ? "#b91c1c"
                                : "#16a34a",
                          }}
                        >
                          {portfolioSnapshot.missingCore}
                        </div>
                      </div>
                    </div>

                    <div
                      style={{
                        marginTop: 10,
                        fontSize: 11,
                        color: "#6b7280",
                      }}
                    >
                      Underwriters begin here: do we trust this SOV?
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* CSV PREVIEW */}
            {uploadedData && (
              <section className="card" style={{ marginTop: 20 }}>
                <div className="card-header">
                  <h2 className="card-title">Standardised SOV preview</h2>
                  <span className="card-badge">
                    Showing first 50 rows of {uploadedData.row_count}
                  </span>
                </div>

                <div className="table-wrapper">
                  <table className="risk-table">
                    <thead>
                      <tr>
                        {uploadedData.columns.map((col) => (
                          <th key={col}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {uploadedData.data.slice(0, 50).map((row, idx) => (
                        <tr key={idx}>
                          {uploadedData.columns.map((col) => (
                            <td key={col}>{row[col] || "—"}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </div>
        )}

        {/* TAB 2: UNDERWRITER DASHBOARD */}
        {activeTab === "portfolio" && (
          <div style={{ padding: "30px 40px", background: "#f5f5f5" }}>
            {/* KPI SUMMARY */}
            <section className="summary-grid">
              <div className="summary-card">
                <div className="summary-label">Total insured value</div>
                <div className="summary-value">
                  £{(dashboardMetrics.totalValue / 1_000_000_000).toFixed(2)}bn
                </div>
                <div className="summary-footnote">
                  Across {dashboardMetrics.propertyCount} properties
                </div>
              </div>

              <div className="summary-card">
                <div className="summary-label">Average risk score</div>
                <div className="summary-value">
                  {dashboardMetrics.avgRiskScore.toFixed(2)}
                </div>
                <div className="summary-footnote">
                  {dashboardMetrics.riskLabel}
                </div>
              </div>

              <div className="summary-card">
                <div className="summary-label">Flat roofs</div>
                <div className="summary-value">
                  {dashboardMetrics.flatRoofPct}%
                </div>
                <div className="summary-footnote">
                  Concentration of flat roofs
                </div>
              </div>
            </section>

            {/* MIDROW: CRV/ERV + MAP */}
            <section
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1.6fr",
                gap: 20,
                marginTop: 20,
              }}
            >
              {/* CRV vs ERV */}
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">
                    Reinstatement value comparison (demo)
                  </h2>
                  <span className="card-badge">CRV vs ERV</span>
                </div>

                <div style={{ padding: 20 }}>
                  {[
                    { label: "Current (CRV)", pct: 68, colour: "#c7d2fe" },
                    { label: "Estimated (ERV)", pct: 75, colour: "#4f46e5" },
                  ].map((bar) => (
                    <div key={bar.label} style={{ marginBottom: 16 }}>
                      <div style={{ marginBottom: 4 }}>{bar.label}</div>

                      <div
                        style={{
                          height: 10,
                          borderRadius: 999,
                          background: "#e5e7eb",
                        }}
                      >
                        <div
                          style={{
                            height: "100%",
                            width: `${bar.pct}%`,
                            borderRadius: 999,
                            background: bar.colour,
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

              {/* MAP */}
              <section className="card map-card">
                <div className="card-header">
                  <h2 className="card-title">Regional risk &amp; exposure</h2>
                  <span className="card-badge">
                    Bubble = exposure · Colour = risk
                  </span>
                </div>

                <div className="map-wrapper" style={{ height: 260 }}>
                  <MapContainer
                    center={[54.5, -3]}
                    zoom={5}
                    style={{ height: "100%", width: "100%" }}
                    scrollWheelZoom={false}
                  >
                    <TileLayer
                      attribution="&copy; OpenStreetMap"
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />

                    {citySummary.map((c) => (
                      <Marker key={c.city} position={[c.lat, c.lon]}>
                        <Popup>
                          <strong>{c.city}</strong> <br />
                          Properties: {c.count}
                          <br />
                          Value: £{(c.totalValue / 1_000_000).toFixed(1)}m
                          <br />
                          Avg risk: {c.avgRisk.toFixed(2)}
                        </Popup>
                      </Marker>
                    ))}
                  </MapContainer>
                </div>
              </section>
            </section>

            {/* PERIL + FEATURES + MAINTENANCE */}
            <section
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 1fr",
                gap: 20,
                marginTop: 20,
              }}
            >
              {/* PERIL */}
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">Peril risk distribution</h2>
                </div>

                <div style={{ padding: 20 }}>
                  {[
                    {
                      label: "Combustibility",
                      value: dashboardMetrics.combustibilityHotspots,
                    },
                    {
                      label: "Fire exposure",
                      value: dashboardMetrics.fireHotspots,
                    },
                    {
                      label: "Flood exposure",
                      value: dashboardMetrics.floodHotspots,
                    },
                    {
                      label: "Flat roofs",
                      value: dashboardMetrics.flatRoofPct,
                    },
                  ].map((i) => (
                    <div key={i.label} style={{ marginBottom: 12 }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <span>{i.label}</span>
                        <span>{i.value}%</span>
                      </div>

                      <div
                        style={{
                          height: 8,
                          borderRadius: 999,
                          background: "#e5e7eb",
                          marginTop: 4,
                        }}
                      >
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

              {/* FEATURES */}
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">Property features</h2>
                </div>

                <div style={{ padding: 20, fontSize: 13 }}>
                  <div style={{ marginBottom: 12 }}>
                    <div className="cell-strong">
                      Properties with balconies (proxy)
                    </div>
                    <div className="summary-value" style={{ fontSize: 24 }}>
                      {dashboardMetrics.balconyPct}%
                    </div>
                    <div className="summary-footnote">
                      Flats / high-rise used as proxy
                    </div>
                  </div>

                  <div>
                    <div className="cell-strong">Basements present</div>
                    <div className="summary-value" style={{ fontSize: 24 }}>
                      {dashboardMetrics.basementPct}%
                    </div>
                    <div className="summary-footnote">
                      Flood / escape-of-water sensitivity
                    </div>
                  </div>
                </div>
              </div>

              {/* MAINTENANCE */}
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">Maintenance hotspots</h2>
                </div>

                <div style={{ padding: 20 }}>
                  {[
                    {
                      label: "Low maintenance score",
                      value: dashboardMetrics.maintenanceIssues,
                    },
                  ].map((i) => (
                    <div key={i.label} style={{ marginBottom: 12 }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <span>{i.label}</span>
                        <span>{i.value}%</span>
                      </div>

                      <div
                        style={{
                          height: 8,
                          borderRadius: 999,
                          background: "#e5e7eb",
                          marginTop: 4,
                        }}
                      >
                        <div
                          style={{
                            height: "100%",
                            width: `${i.value}%`,
                            background: "#10b981",
                            borderRadius: 999,
                          }}
                        />
                      </div>
                    </div>
                  ))}

                  <div className="summary-footnote">
                    Helps target survey / capex interventions.
                  </div>
                </div>
              </div>
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
                            {p.address1} {p.address2}
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
                            Deprivation index: {p.deprivationIndex.toFixed(1)}
                          </div>
                          <div className="cell-muted">
                            Crime index: {p.crimeIndex.toFixed(1)}
                          </div>
                          <div className="cell-muted">
                            Void days: {p.voidDaysLastYear}
                          </div>
                          <div className="cell-meta">
                            lat {p.lat.toFixed(3)}, lon {p.lon.toFixed(3)}
                          </div>
                        </td>

                        <td>
                          <div className="cell-strong">
                            Walls: {p.wallConstruction}
                          </div>
                          <div className="cell-muted">
                            Roof: {p.roofConstruction}
                          </div>
                          <div className="cell-muted">
                            Storeys: {p.numberOfStoreys}
                          </div>
                          <div className="cell-muted">EPC: {p.epcRating}</div>
                        </td>

                        <td>
                          <div className="cell-strong">
                            Flood insured: {p.floodInsured ? "Yes" : "No"}
                          </div>
                          <div className="cell-muted">
                            Storm insured: {p.stormInsured ? "Yes" : "No"}
                          </div>
                          <div className="cell-muted">
                            Flood score: {p.floodScore.toFixed(2)}
                          </div>
                          <div className="cell-muted">
                            Claim frequency: {p.claimFrequency.toFixed(2)} / yr
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

        {/* TAB 3: STOCK LISTING (DOC A) */}
        {activeTab === "stock" && (
          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-header">
              <h2 className="card-title">Stock Listing (Document A)</h2>
              <span className="card-badge">
                Normalised structure based on Doc A (June 2024)
              </span>
            </div>

            <div className="table-wrapper">
              <table className="risk-table">
                <thead>
                  <tr>
                    <th>Client</th>
                    <th>Property</th>
                    <th>Occupancy</th>
                    <th>Units / Value</th>
                    <th>Construction</th>
                  </tr>
                </thead>

                <tbody>
                  {RAW_PROPERTIES.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <div className="cell-strong">
                          {p.clientName || "Client"}
                        </div>
                        <div className="cell-muted">
                          Policy: {p.policyReference}
                        </div>
                        <div className="cell-meta">{p.productType}</div>
                      </td>

                      <td>
                        <div className="prop-main">
                          {p.address1} {p.address2}
                        </div>
                        <div className="prop-sub">
                          Ref {p.propertyReference} · Block {p.blockReference}
                        </div>
                        <div className="prop-meta">
                          {p.city} {p.postcode}
                        </div>
                      </td>

                      <td>
                        <div className="cell-strong">{p.occupancyType}</div>
                        <div className="cell-muted">
                          Property: {p.avidPropertyType}
                        </div>
                      </td>

                      <td>
                        <div className="cell-strong">
                          Units: {p.numberOfUnits}
                        </div>
                        <div className="cell-muted">
                          Sum insured: £{p.sumInsured.toLocaleString("en-GB")}
                        </div>
                        <div className="cell-meta">{p.sumInsuredType}</div>
                      </td>

                      <td>
                        <div className="cell-strong">Year: {p.yearBuilt}</div>
                        <div className="cell-muted">Age: {p.ageBanding}</div>
                        <div className="cell-muted">
                          Walls: {p.wallConstruction}
                        </div>
                        <div className="cell-muted">
                          Roof: {p.roofConstruction}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* SUMMARY */}
            <div className="card-header">
              <h3 className="card-title">Portfolio totals</h3>
            </div>

            <div className="table-wrapper">
              <table className="risk-table">
                <thead>
                  <tr>
                    <th>Tenure</th>
                    <th>Units</th>
                    <th>Sum insured</th>
                    <th>Block</th>
                    <th>Units</th>
                    <th>Sum insured</th>
                  </tr>
                </thead>

                <tbody>
                  {byOccupancy.map((occ, idx) => (
                    <tr key={occ.occupancy}>
                      <td>{occ.occupancy}</td>
                      <td>{occ.units}</td>
                      <td>
                        £
                        {occ.sumInsured.toLocaleString("en-GB", {
                          maximumFractionDigits: 0,
                        })}
                      </td>

                      <td>{byBlock[idx]?.block}</td>
                      <td>{byBlock[idx]?.units}</td>
                      <td>
                        £
                        {byBlock[idx]?.sumInsured.toLocaleString("en-GB", {
                          maximumFractionDigits: 0,
                        })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 4: HIGH VALUE (DOC B) */}
        {activeTab === "highvalue" && (
          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-header">
              <h2 className="card-title">High Value Blocks (Document B)</h2>
              <span className="card-badge">
                Complex blocks with enhanced data
              </span>
            </div>

            <div className="table-wrapper">
              <table className="risk-table">
                <thead>
                  <tr>
                    <th>Block</th>
                    <th>Attributes</th>
                    <th>Fire</th>
                    <th>Façade / EWS</th>
                    <th>Claims</th>
                  </tr>
                </thead>

                <tbody>
                  {highValueProps.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <div className="prop-main">{p.address1}</div>
                        <div className="prop-sub">
                          {p.city} {p.postcode}
                        </div>
                        <div className="prop-meta">
                          Ref {p.docBRef} · Policy {p.policyReference}
                        </div>
                        <div className="prop-meta">
                          SI £{p.sumInsured.toLocaleString("en-GB")}
                        </div>
                      </td>

                      <td>
                        <div className="cell-strong">
                          Floors above ground: {p.floorsAboveGround}
                        </div>
                        <div className="cell-muted">
                          Below ground: {p.floorsBelowGround}
                        </div>
                        <div className="cell-muted">
                          Construction: {p.wallConstruction}
                        </div>
                        <div className="cell-muted">
                          Cladding: {p.claddingType}
                        </div>
                      </td>

                      <td>
                        <div className="cell-strong">Fire management</div>
                        <div className="cell-muted">
                          {p.fireRiskManagementSummary}
                        </div>
                      </td>

                      <td>
                        <div className="cell-strong">
                          EWS: {p.ewsStatus || "N/A"}
                        </div>
                        <div className="cell-muted">
                          Evacuation: {p.evacuationStrategy}
                        </div>
                      </td>

                      <td>
                        <div className="cell-strong">Risk: {p.riskBand}</div>
                        <div className="cell-muted">
                          Claims: {p.claimFrequency.toFixed(2)} /yr
                        </div>
                        <div className="cell-meta">
                          Last claim: {p.lastClaimDate || "None"}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="card-header">
              <h3 className="card-title">Document B intent</h3>
            </div>

            <div style={{ padding: 20, fontSize: 12 }}>
              Document B captures high-resolution information for complex
              blocks: construction, cladding, fire measures, EWS status, and
              evacuation strategies. This enables underwriters to evaluate
              multi-variable risk in minutes rather than days.
            </div>
          </div>
        )}
        {/* END highvalue tab */}
      </div>
      {/* END app-shell */}
    </div>
  );
}

export default App;
