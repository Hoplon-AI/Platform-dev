// App.js
import React, { useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import Papa from "papaparse";
import * as XLSX from "xlsx";

import "./styles.css";
import LandingPage from "./LandingPage";
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";
import { RAW_PROPERTIES } from "./data/properties";

// Fix default Leaflet marker icons when bundling
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Tabs focused around ingestion & overview first
const TABS = [
  { id: "ingestion", label: "Ingestion & overview" },
  { id: "portfolio", label: "Portfolio explorer" },
  { id: "stock", label: "Stock listing (Doc A)" },
  { id: "highvalue", label: "High value (Doc B)" },
];

const unique = (arr) => [...new Set(arr)];

function App() {
  const [showLanding, setShowLanding] = useState(true);
  const [showLogin, setShowLogin] = useState(false);
  const [showRegister, setShowRegister] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [activeTab, setActiveTab] = useState("ingestion");

  // Filters (portfolio explorer)
  const [search, setSearch] = useState("");
  const [cityFilter, setCityFilter] = useState("All");
  const [riskFilter, setRiskFilter] = useState("All");
  const [tenureFilter, setTenureFilter] = useState("All");

  // Upload / ingestion state
  const [uploadedData, setUploadedData] = useState(null);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const fileInputRef = useRef(null);

  // ---------- Ingestion helpers (shared by CSV + Excel) ----------

  function handleParsedData(rows, columns) {
    const cleanedColumns = (columns || []).map((c) => c.trim());

    const cleanedData = rows.map((row) => {
      const newRow = {};
      cleanedColumns.forEach((col) => {
        newRow[col] = (row[col] ?? "").toString().trim();
      });
      return newRow;
    });

    setUploadedData({
      message: "File parsed successfully",
      columns: cleanedColumns,
      data: cleanedData,
      row_count: cleanedData.length,
    });

    setIsUploading(false);
  }

  function markFileParsed(file) {
    setUploadedFiles((prev) =>
      prev.map((f) => (f.name === file.name ? { ...f, status: "Parsed" } : f))
    );
  }

  // ---------- Ingestion: client-side CSV + Excel parsing ----------

  const parseFiles = (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    setIsUploading(true);
    setUploadError(null);

    const fileSummaries = files.map((f) => {
      const nameLower = f.name.toLowerCase();
      const isTabular =
        nameLower.endsWith(".csv") ||
        nameLower.endsWith(".xlsx") ||
        nameLower.endsWith(".xls");

      return {
        name: f.name,
        size: f.size,
        type: f.type || "unknown",
        status: isTabular ? "Parsing" : "Queued (unsupported type)",
      };
    });

    setUploadedFiles(fileSummaries);

    // take the first tabular file (CSV / Excel)
    const file = files.find((f) => {
      const nameLower = f.name.toLowerCase();
      return (
        nameLower.endsWith(".csv") ||
        nameLower.endsWith(".xlsx") ||
        nameLower.endsWith(".xls")
      );
    });

    if (!file) {
      setUploadedData(null);
      setIsUploading(false);
      return;
    }

    const nameLower = file.name.toLowerCase();

    // ---- CSV ----
    if (nameLower.endsWith(".csv")) {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: (results) => {
          const rows = results.data || [];
          const cols =
            results.meta?.fields && results.meta.fields.length
              ? results.meta.fields
              : Object.keys(rows[0] || {});
          handleParsedData(rows, cols);
          markFileParsed(file);
        },
        error: (err) => {
          setUploadError(err.message);
          setIsUploading(false);
        },
      });
      return;
    }

    // ---- Excel (.xlsx / .xls) ----
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const data = evt.target.result;
        const workbook = XLSX.read(data, { type: "binary" });

        // first sheet only for now
        const sheetName = workbook.SheetNames[0];
        const sheet = workbook.Sheets[sheetName];
        const json = XLSX.utils.sheet_to_json(sheet, { defval: "" });

        const columns = Object.keys(json[0] || {});
        handleParsedData(json, columns);
        markFileParsed(file);
      } catch (e) {
        setUploadError("Failed to parse Excel file.");
        setIsUploading(false);
      }
    };
    reader.onerror = () => {
      setUploadError("Failed to read Excel file.");
      setIsUploading(false);
    };
    reader.readAsBinaryString(file);
  };

  const handleFileInputChange = (e) => {
    if (!e.target.files?.length) return;
    parseFiles(e.target.files);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      parseFiles(e.dataTransfer.files);
      e.dataTransfer.clearData();
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  // ---------- Derived portfolio data (demo properties) ----------

  const cities = useMemo(() => unique(RAW_PROPERTIES.map((p) => p.city)), []);
  const riskBands = useMemo(
    () => unique(RAW_PROPERTIES.map((p) => p.riskBand)),
    []
  );
  const tenures = useMemo(
    () => unique(RAW_PROPERTIES.map((p) => p.occupancyType)),
    []
  );

  const filtered = useMemo(() => {
    let out = RAW_PROPERTIES.filter((p) => {
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
    });

    return out;
  }, [search, cityFilter, riskFilter, tenureFilter]);

  const edinburghProps = useMemo(
    () => RAW_PROPERTIES.filter((p) => p.city === "Edinburgh"),
    []
  );

  const edinburghCenter =
    edinburghProps.length > 0
      ? [
          edinburghProps.reduce((s, p) => s + p.lat, 0) / edinburghProps.length,
          edinburghProps.reduce((s, p) => s + p.lon, 0) / edinburghProps.length,
        ]
      : [55.9533, -3.1883];

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

  // Portfolio snapshot – uploaded SOV if present, else demo portfolio
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

        if (missingPostcode || missingAddress) {
          missingCore += 1;
        }
      });

      return {
        source: "Uploaded SOV",
        propertyCount: rows.length,
        totalValue: totalValue || null,
        missingCore,
      };
    }

    // fallback to demo RAW_PROPERTIES
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

  // ---------- Landing vs app ----------

  // Show landing page
  if (showLanding) {
    return (
      <LandingPage
        onGetStarted={() => {
          setShowLanding(false);
          setShowLogin(true);
          setShowRegister(false);
        }}
      />
    );
  }

  // Show register page
  if (showRegister && !isAuthenticated) {
    return (
      <RegisterPage
        onRegister={() => {
          setShowRegister(false);
          setShowLogin(true);
        }}
        onSwitchToLogin={() => {
          setShowRegister(false);
          setShowLogin(true);
        }}
      />
    );
  }

  // Show login page if not authenticated
  if (showLogin && !isAuthenticated) {
    return (
      <LoginPage
        onLogin={(success) => {
          if (success) {
            setIsAuthenticated(true);
            setShowLogin(false);
            setActiveTab("ingestion");
          }
        }}
        onSwitchToRegister={() => {
          setShowLogin(false);
          setShowRegister(true);
        }}
      />
    );
  }

  // Show main app if authenticated
  return (
    <div className="app-root">
      <div className="app-shell">
        {/* Header */}
        <header className="app-header">
          <button
            className="back-home-btn"
            onClick={() => {
              setShowLanding(true);
              setShowLogin(false);
              setIsAuthenticated(false);
            }}
          >
            ⟵ Back to Home
          </button>
          <div>
            <div className="app-badge">EquiRisk • Underwriter workspace</div>
            <h1 className="app-title">Exposure &amp; data quality cockpit</h1>
            <p className="app-subtitle">
              Drag and drop schedules of values, see what's been ingested,
              what's missing, and how the portfolio looks before touching price.
            </p>
          </div>
          <div className="app-meta">
            Ingestion-first MVP · Demo dataset when no SOV uploaded
          </div>
        </header>

        {/* Tabs */}
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

        {/* 1. Ingestion & overview */}
        {activeTab === "ingestion" && (
          <div style={{ padding: "30px 40px", background: "#f5f5f5" }}>
            <section className="card">
              <div className="card-header">
                <h2 className="card-title">Upload schedules of values</h2>
                <span className="card-badge">
                  Excel · CSV · PDF · Word (demo parses CSV &amp; Excel
                  client-side)
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
                {/* Drag & drop area */}
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
                    style={{
                      fontSize: 16,
                      fontWeight: 600,
                      marginBottom: 8,
                    }}
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
                    Or click to browse. EquiRisk ingests and normalises your
                    stock listings, loss runs and schedules of values, and
                    highlights missing or inconsistent information.
                  </div>
                  <div style={{ fontSize: 12, color: "#6b7280" }}>
                    In this MVP, CSV &amp; Excel are parsed client-side and
                    previewed. Other file types are shown as queued for
                    extraction.
                  </div>
                </div>

                {/* Ingestion status & portfolio snapshot */}
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

                    {isUploading && (
                      <div style={{ fontSize: 13, marginBottom: 8 }}>
                        Processing file…
                      </div>
                    )}

                    {uploadError && (
                      <div
                        style={{
                          fontSize: 12,
                          marginTop: 8,
                          padding: 8,
                          borderRadius: 6,
                          background: "#fee2e2",
                          color: "#b91c1c",
                        }}
                      >
                        Error: {uploadError}
                      </div>
                    )}

                    {!uploadedFiles.length && !isUploading && !uploadError && (
                      <div style={{ fontSize: 13, color: "#9ca3af" }}>
                        No files uploaded yet. Drop a stock listing or SOV to
                        begin.
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
                              alignItems: "center",
                              padding: "4px 0",
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
                                fontSize: 12,
                                color:
                                  f.status === "Parsed"
                                    ? "#16a34a"
                                    : f.status.startsWith("Queued")
                                    ? "#6b7280"
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
                        gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
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
                            : "Not available"}
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
                          Records with missing info
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
                      Underwriters start here: do we trust the schedule of
                      values? Are addresses, postcodes and sums insured
                      complete? Detailed rows and modelling come next.
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* Standardised SOV preview if a tabular file parsed */}
            {uploadedData && (
              <section className="card" style={{ marginTop: 20 }}>
                <div className="card-header">
                  <h2 className="card-title">Standardised SOV preview</h2>
                  <span className="card-badge">
                    Showing first 50 of {uploadedData.row_count} rows
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
                            <td key={col}>{row[col] ?? "—"}</td>
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

        {/* 2. Portfolio explorer */}
        {activeTab === "portfolio" && (
          <div className="app-layout">
            <aside className="sidebar-card">
              <h2 className="card-title">Portfolio explorer</h2>

              <div className="field">
                <label className="field-label">
                  Search (address, postcode, property ref)
                </label>
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="input"
                  placeholder="e.g. Caledonia, EH7, EXA1…"
                />
              </div>

              <div className="field-grid">
                <div className="field">
                  <label className="field-label">City</label>
                  <select
                    value={cityFilter}
                    onChange={(e) => setCityFilter(e.target.value)}
                    className="input"
                  >
                    <option value="All">All</option>
                    {cities.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label className="field-label">Risk band</label>
                  <select
                    value={riskFilter}
                    onChange={(e) => setRiskFilter(e.target.value)}
                    className="input"
                  >
                    <option value="All">All</option>
                    {riskBands.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="field">
                <label className="field-label">Occupancy / tenancy</label>
                <select
                  value={tenureFilter}
                  onChange={(e) => setTenureFilter(e.target.value)}
                  className="input"
                >
                  <option value="All">All</option>
                  {tenures.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label className="field-label">Note</label>
                <div className="field-note">
                  This explorer is secondary. The primary workflow is ingestion
                  and high-level portfolio overview. Detailed rows support
                  underwriter deep dives when needed.
                </div>
              </div>
            </aside>

            <main className="main-column">
              <section className="summary-grid">
                <div className="summary-card">
                  <div className="summary-label">Properties (demo)</div>
                  <div className="summary-value">{RAW_PROPERTIES.length}</div>
                  <div className="summary-footnote">
                    As per current sample portfolio
                  </div>
                </div>
                <div className="summary-card">
                  <div className="summary-label">Sum insured</div>
                  <div className="summary-value">
                    £
                    {(
                      RAW_PROPERTIES.reduce(
                        (s, p) => s + (p.sumInsured || 0),
                        0
                      ) / 1_000_000
                    ).toFixed(1)}
                    m
                  </div>
                  <div className="summary-footnote">
                    Aggregate declared values
                  </div>
                </div>
                <div className="summary-card">
                  <div className="summary-label">
                    High / Very High risk props
                  </div>
                  <div className="summary-value">
                    {
                      RAW_PROPERTIES.filter(
                        (p) =>
                          p.riskBand === "High" || p.riskBand === "Very High"
                      ).length
                    }
                  </div>
                  <div className="summary-footnote">
                    Based on deprivation, claims &amp; maintenance
                  </div>
                </div>
              </section>

              <section className="card map-card">
                <div className="card-header">
                  <h2 className="card-title">Edinburgh property view</h2>
                  <span className="card-badge">
                    {edinburghProps.length} demo properties
                  </span>
                </div>
                <div className="map-wrapper">
                  <MapContainer
                    center={edinburghCenter}
                    zoom={12}
                    style={{ height: "100%", width: "100%" }}
                    scrollWheelZoom={false}
                  >
                    <TileLayer
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    {edinburghProps.map((p) => (
                      <Marker key={p.id} position={[p.lat, p.lon]}>
                        <Popup>
                          <div className="popup">
                            <strong>
                              {p.address1} {p.address2}
                            </strong>
                            <br />
                            {p.postcode}
                            <br />
                            {p.propertyType} • {p.occupancyType}
                            <br />
                            Risk band: <strong>{p.riskBand}</strong>
                          </div>
                        </Popup>
                      </Marker>
                    ))}
                  </MapContainer>
                </div>
              </section>

              <section className="card">
                <div className="card-header">
                  <h2 className="card-title">
                    Property, exposure &amp; risk detail
                  </h2>
                  <span className="card-badge">
                    Showing {filtered.length} of {RAW_PROPERTIES.length}
                  </span>
                </div>

                <div className="table-wrapper">
                  <table className="risk-table">
                    <thead>
                      <tr>
                        <th>Property</th>
                        <th>Geo / Deprivation</th>
                        <th>Construction &amp; features</th>
                        <th>Perils &amp; claims</th>
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
                              {p.city}, {p.region} {p.postcode}
                            </div>
                            <div className="prop-sub">
                              {p.propertyType} • {p.occupancyType}
                            </div>
                            <div className="prop-meta">
                              Ref {p.propertyReference} · Block{" "}
                              {p.blockReference} · Units {p.numberOfUnits}
                            </div>
                          </td>

                          <td>
                            <div className="cell-strong">
                              Deprivation index:{" "}
                              <span>{p.deprivationIndex.toFixed(1)}</span>
                            </div>
                            <div className="cell-muted">
                              Void days last year: {p.voidDaysLastYear}
                            </div>
                            <div className="cell-meta">
                              lat {p.lat.toFixed(3)}, lon {p.lon.toFixed(3)}
                            </div>
                          </td>

                          <td>
                            <div className="cell-strong">
                              Construction: <span>{p.wallConstruction}</span>
                            </div>
                            <div className="cell-muted">
                              Roof: {p.roofConstruction}
                            </div>
                            <div className="cell-muted">
                              Floors: {p.numberOfStoreys} storeys, basement:{" "}
                              {p.basementLocation}
                            </div>
                            <div className="cell-muted">
                              Features: {p.securityFeatures}
                            </div>
                            <div className="cell-meta">
                              Age band: {p.ageBanding} · EPC {p.epcRating}
                            </div>
                          </td>

                          <td>
                            <div className="cell-strong">
                              Flood insured:{" "}
                              <span>{p.floodInsured ? "Yes" : "No"}</span>
                            </div>
                            <div className="cell-strong">
                              Storm insured:{" "}
                              <span>{p.stormInsured ? "Yes" : "No"}</span>
                            </div>
                            <div className="cell-muted">
                              Flood score: {p.floodScore.toFixed(2)}
                            </div>
                            <div className="cell-muted">
                              Crime index: {p.crimeIndex.toFixed(1)}
                            </div>
                            <div className="cell-muted">
                              Claim frequency: {p.claimFrequency.toFixed(2)} /
                              year
                            </div>
                          </td>
                        </tr>
                      ))}

                      {filtered.length === 0 && (
                        <tr>
                          <td colSpan={4} className="empty-row">
                            No properties match the current filters.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </main>
          </div>
        )}

        {/* 3. Stock listing – Doc A-style */}
        {activeTab === "stock" && (
          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-header">
              <h2 className="card-title">
                Stock listing – Document A structure
              </h2>
              <span className="card-badge">
                Simplified view of the June 24 stock listing format
              </span>
            </div>
            <div className="table-wrapper">
              <table className="risk-table">
                <thead>
                  <tr>
                    <th>Client / Policy</th>
                    <th>Property / Block</th>
                    <th>Occupancy</th>
                    <th>Units / Sum insured</th>
                    <th>Construction &amp; age</th>
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
                        <div className="cell-strong">
                          Occupancy: <span>{p.occupancyType}</span>
                        </div>
                        <div className="cell-muted">
                          Avid property type: {p.avidPropertyType}
                        </div>
                      </td>
                      <td>
                        <div className="cell-strong">
                          Units: <span>{p.numberOfUnits}</span>
                        </div>
                        <div className="cell-muted">
                          Sum insured: £{p.sumInsured.toLocaleString("en-GB")}
                        </div>
                        <div className="cell-meta">
                          Basis: {p.sumInsuredType}
                        </div>
                      </td>
                      <td>
                        <div className="cell-strong">
                          Year built: <span>{p.yearBuilt}</span>
                        </div>
                        <div className="cell-muted">
                          Age band: {p.ageBanding}
                        </div>
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

            <div className="card-header">
              <h3 className="card-title">Validation snapshots</h3>
            </div>
            <div className="table-wrapper">
              <table className="risk-table">
                <thead>
                  <tr>
                    <th>By tenancy / ownership</th>
                    <th>Units</th>
                    <th>Sum insured (£)</th>
                    <th>By block</th>
                    <th>Units</th>
                    <th>Sum insured (£)</th>
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
                      <td>{byBlock[idx] ? byBlock[idx].block : ""}</td>
                      <td>{byBlock[idx] ? byBlock[idx].units : ""}</td>
                      <td>
                        {byBlock[idx]
                          ? "£" +
                            byBlock[idx].sumInsured.toLocaleString("en-GB", {
                              maximumFractionDigits: 0,
                            })
                          : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 4. High value – Doc B-style */}
        {activeTab === "highvalue" && (
          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-header">
              <h2 className="card-title">
                High value blocks – Document B view
              </h2>
              <span className="card-badge">
                Pulling out properties with Document B-style information
              </span>
            </div>
            <div className="table-wrapper">
              <table className="risk-table">
                <thead>
                  <tr>
                    <th>Block / Policy</th>
                    <th>High value attributes</th>
                    <th>Fire risk management</th>
                    <th>Evacuation &amp; EWS</th>
                    <th>Claims &amp; risk</th>
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
                          Sum insured: £{p.sumInsured.toLocaleString("en-GB")}
                        </div>
                      </td>
                      <td>
                        <div className="cell-strong">
                          Storeys above ground:{" "}
                          <span>{p.floorsAboveGround}</span>
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
                        <div className="cell-strong">Fire risk management</div>
                        <div className="cell-muted">
                          {p.fireRiskManagementSummary}
                        </div>
                      </td>
                      <td>
                        <div className="cell-strong">
                          EWS / façade status:{" "}
                          <span>{p.ewsStatus || "N/A"}</span>
                        </div>
                        <div className="cell-muted">
                          Evacuation strategy: {p.evacuationStrategy}
                        </div>
                      </td>
                      <td>
                        <div className="cell-strong">
                          Risk band: <span>{p.riskBand}</span>
                        </div>
                        <div className="cell-muted">
                          Claim frequency: {p.claimFrequency.toFixed(2)} / year
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
              <h3 className="card-title">Document B notes (summary)</h3>
            </div>
            <div style={{ padding: "10px 18px 16px", fontSize: 12 }}>
              This view mirrors the intent of Document B: to capture
              high-resolution information for complex or high-value blocks,
              including construction features, fire safety measures and façade /
              EWS status. It sits alongside, not instead of, the stock listing.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

