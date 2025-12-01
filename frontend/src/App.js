// App.js
import React, { useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import Papa from "papaparse";
import * as XLSX from "xlsx";
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";

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
  { id: "analytics", label: "Analytics" },
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

  // Convert uploaded data to properties format, or use demo data
  const properties = useMemo(() => {
    if (uploadedData && uploadedData.data.length) {
      // Map uploaded data to property format
      return uploadedData.data.map((row, idx) => {
        // Helper to check if column is empty/missing in original data
        const isColMissing = (colName) => {
          const val = row[colName];
          return val === undefined || val === null || val === "" || String(val).trim() === "";
        };

        // Helper to get column value with fallback
        const getCol = (colName, fallback = "") => {
          return row[colName] !== undefined && row[colName] !== "" ? row[colName] : fallback;
        };

        // Parse numeric values safely
        const parseNum = (val, fallback = 0) => {
          const num = parseFloat(String(val).replace(/[^0-9.-]/g, ""));
          return isNaN(num) ? fallback : num;
        };

        const parseInt_ = (val, fallback = 0) => {
          const num = parseInt(String(val).replace(/[^0-9]/g, ""));
          return isNaN(num) ? fallback : num;
        };

        // Track if ANY critical fields are missing in original CSV
        const hasOriginalAddress = !isColMissing("address");
        const hasOriginalPostcode = !isColMissing("zip_code");
        const hasOriginalCity = !isColMissing("city");
        const hasOriginalRegion = !isColMissing("region");
        const hasOriginalLat = !isColMissing("lat");
        const hasOriginalLon = !isColMissing("lon");
        const hasOriginalBuildYear = !isColMissing("buildYear");
        const hasOriginalType = !isColMissing("type");
        const hasOriginalTenure = !isColMissing("tenure");
        const hasOriginalLandlord = !isColMissing("landlord");
        const hasOriginalEpcRating = !isColMissing("epcRating");
        const hasOriginalDeprivationIndex = !isColMissing("deprivationIndex");
        const hasOriginalFloodScore = !isColMissing("floodScore");
        const hasOriginalCrimeIndex = !isColMissing("crimeIndex");
        const hasOriginalClaimFrequency = !isColMissing("claimFrequency");
        const hasOriginalPurePremium = !isColMissing("purePremium") && parseNum(getCol("purePremium")) > 0;
        const hasOriginalRiskBand = !isColMissing("riskBand");
        const hasOriginalMaintenanceScore = !isColMissing("maintenanceScore");
        const hasOriginalVoidDays = !isColMissing("voidDaysLastYear");

        // Count how many critical fields are missing
        const missingFieldsCount = [
          hasOriginalAddress,
          hasOriginalPostcode,
          hasOriginalCity,
          hasOriginalRegion,
          hasOriginalLat,
          hasOriginalLon,
          hasOriginalBuildYear,
          hasOriginalType,
          hasOriginalTenure,
          hasOriginalLandlord,
          hasOriginalEpcRating,
          hasOriginalDeprivationIndex,
          hasOriginalFloodScore,
          hasOriginalCrimeIndex,
          hasOriginalClaimFrequency,
          hasOriginalPurePremium,
          hasOriginalRiskBand,
          hasOriginalMaintenanceScore,
          hasOriginalVoidDays
        ].filter(hasField => !hasField).length;

        // Map the uploaded CSV format to internal property structure
        const lat = parseNum(getCol("lat"), 55.9533 + (Math.random() - 0.5) * 0.1);
        const lon = parseNum(getCol("lon"), -3.1883 + (Math.random() - 0.5) * 0.1);

        return {
          id: getCol("id", `uploaded-${idx}`),
          uprn: getCol("uprn", ""),
          address1: getCol("address", `Property ${idx + 1}`),
          address2: "",
          address3: "",
          postcode: getCol("zip_code", "N/A"),
          city: getCol("city", "Unknown"),
          region: getCol("region", "Unknown"),
          propertyType: getCol("type", "Unknown"),
          propertyReference: getCol("id", `REF${idx + 1}`),
          blockReference: `BLK${idx + 1}`,
          occupancyType: getCol("tenure", "Unknown"),
          numberOfUnits: 1,
          sumInsured: parseNum(getCol("purePremium")) * 100 || 500000, // Estimate based on premium
          sumInsuredType: "Reinstatement",
          riskBand: getCol("riskBand", "Medium"),
          yearBuilt: parseInt_(getCol("buildYear"), 2000),
          ageBanding: calculateAgeBanding(parseInt_(getCol("buildYear"), 2000)),
          wallConstruction: "Unknown",
          roofConstruction: "Unknown",
          numberOfStoreys: 2,
          basementLocation: "None",
          securityFeatures: "Standard",
          epcRating: getCol("epcRating", "N/A"),
          deprivationIndex: parseNum(getCol("deprivationIndex"), 5.0),
          voidDaysLastYear: parseInt_(getCol("voidDaysLastYear"), 0),
          floodInsured: true,
          stormInsured: true,
          floodScore: parseNum(getCol("floodScore"), 0.5),
          crimeIndex: parseNum(getCol("crimeIndex"), 5.0),
          claimFrequency: parseNum(getCol("claimFrequency"), 0.1),
          expectedSeverity: parseNum(getCol("expectedSeverity"), 0),
          purePremium: parseNum(getCol("purePremium"), 0),
          maintenanceScore: parseNum(getCol("maintenanceScore"), 5.0),
          lastClaimDate: getCol("lastClaimDate", null),
          // Use uploaded coordinates or generate random ones around UK
          lat: lat,
          lon: lon,
          clientName: getCol("landlord", "Client"),
          policyReference: `POL-${getCol("id", idx + 1)}`,
          productType: "Property Insurance",
          avidPropertyType: getCol("type", "Unknown"),
          docBRef: "",
          floorsAboveGround: 2,
          floorsBelowGround: 0,
          claddingType: "N/A",
          fireRiskManagementSummary: "Standard measures",
          ewsStatus: "N/A",
          evacuationStrategy: "Standard",
          numberOfBedrooms: 2,
          listedBuilding: "Not listed",
          fireProtection: "Standard",
          alarms: "Standard",
          deductible: 2500,
          floodDeductible: 5000,
          stormDeductible: 2500,
          deductibleBasis: "Each and every loss",
          floorConstruction: "Unknown",
          // Track missing data - if ANY field is missing, flag this record
          _hasMissingData: missingFieldsCount > 0,
          _missingFieldsCount: missingFieldsCount,
        };
      });
    }
    return RAW_PROPERTIES;
  }, [uploadedData]);

  // Helper function to calculate age banding
  function calculateAgeBanding(year) {
    if (year < 1900) return "Pre-1900";
    if (year <= 1919) return "1901-1919";
    if (year <= 1944) return "1920-1944";
    if (year <= 1964) return "1945-1964";
    if (year <= 1980) return "1965-1980";
    if (year <= 1990) return "1981-1990";
    if (year <= 2000) return "1991-2000";
    if (year <= 2010) return "2001-2010";
    return "Post-2010";
  }

  const cities = useMemo(() => unique(properties.map((p) => p.city)), [properties]);
  const riskBands = useMemo(
    () => unique(properties.map((p) => p.riskBand)),
    [properties]
  );
  const tenures = useMemo(
    () => unique(properties.map((p) => p.occupancyType)),
    [properties]
  );

  const filtered = useMemo(() => {
    return properties.filter((p) => {
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
  }, [properties, search, cityFilter, riskFilter, tenureFilter]);

  const edinburghProps = useMemo(
    () => properties.filter((p) => p.city === "Edinburgh"),
    [properties]
  );

  const edinburghCenter =
    edinburghProps.length > 0
      ? [
          edinburghProps.reduce((s, p) => s + p.lat, 0) / edinburghProps.length,
          edinburghProps.reduce((s, p) => s + p.lon, 0) / edinburghProps.length,
        ]
      : [55.9533, -3.1883];

  const highValueProps = useMemo(
    () => properties.filter((p) => !!p.docBRef),
    [properties]
  );

  const byOccupancy = useMemo(() => {
    const map = new Map();
    properties.forEach((p) => {
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
  }, [properties]);

  const byBlock = useMemo(() => {
    const map = new Map();
    properties.forEach((p) => {
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
  }, [properties]);

  // Portfolio snapshot – uploaded SOV if present, else demo portfolio
  const portfolioSnapshot = useMemo(() => {
    const propertyCount = properties.length;
    const totalValue = properties.reduce((s, p) => s + (p.sumInsured || 0), 0);

    // Check for missing or invalid core fields
    const missingCore = properties.filter((p) => {
      // For uploaded data, use the tracking flag
      if (uploadedData && p._hasMissingData !== undefined) {
        return p._hasMissingData;
      }

      // For demo data, use the old logic
      const hasValidPostcode = p.postcode &&
        p.postcode !== "N/A" &&
        p.postcode !== "Unknown" &&
        p.postcode.trim() !== "";

      const hasValidAddress = p.address1 &&
        p.address1 !== "N/A" &&
        p.address1 !== "Unknown" &&
        !p.address1.startsWith("Property ") &&
        p.address1.trim() !== "";

      const hasValidSumInsured = p.sumInsured &&
        p.sumInsured > 0;

      return !hasValidPostcode || !hasValidAddress || !hasValidSumInsured;
    }).length;

    return {
      source: uploadedData ? "Uploaded SOV" : "Demo portfolio",
      propertyCount,
      totalValue,
      missingCore,
    };
  }, [properties, uploadedData]);

  // Analytics data for pie charts
  const propertyTypesData = useMemo(() => {
    const map = new Map();
    properties.forEach((p) => {
      const type = p.propertyType || "Unknown";
      map.set(type, (map.get(type) || 0) + 1);
    });
    return Array.from(map.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => a.name.localeCompare(b.name)); // Sort alphabetically
  }, [properties]);

  const epcRatingsData = useMemo(() => {
    const map = new Map();
    properties.forEach((p) => {
      const rating = p.epcRating || "N/A";
      map.set(rating, (map.get(rating) || 0) + 1);
    });
    return Array.from(map.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => a.name.localeCompare(b.name)); // Sort alphabetically
  }, [properties]);

  // Deprivation data grouped by intervals with step=1
  const deprivationData = useMemo(() => {
    const map = new Map();

    properties.forEach((p) => {
      const score = p.deprivationIndex || 0;
      const bucket = Math.floor(score);
      const rangeLabel = `${bucket}-${bucket + 1}`;

      const existing = map.get(rangeLabel) || { range: rangeLabel, count: 0, bucketStart: bucket };
      existing.count += 1;
      map.set(rangeLabel, existing);
    });

    return Array.from(map.values())
      .sort((a, b) => a.bucketStart - b.bucketStart);
  }, [properties]);

  // Colors for charts
  const PROPERTY_TYPE_COLORS = [
    "#4f46e5", "#7c3aed", "#2563eb", "#0891b2", "#059669",
    "#d97706", "#dc2626", "#ec4899", "#8b5cf6", "#06b6d4"
  ];

  const EPC_COLORS = [
    "#16a34a", "#65a30d", "#ca8a04", "#ea580c", "#dc2626",
    "#991b1b", "#6b7280", "#9ca3af", "#d1d5db", "#e5e7eb"
  ];

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
                  <div className="summary-label">Properties</div>
                  <div className="summary-value">{properties.length}</div>
                  <div className="summary-footnote">
                    {uploadedData ? "From uploaded file" : "Demo portfolio"}
                  </div>
                </div>
                <div className="summary-card">
                  <div className="summary-label">Sum insured</div>
                  <div className="summary-value">
                    £
                    {(
                      properties.reduce(
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
                      properties.filter(
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
                  <h2 className="card-title">
                    {edinburghProps.length > 0 ? `${edinburghProps[0].city} property view` : "Property map"}
                  </h2>
                  <span className="card-badge">
                    {edinburghProps.length} properties
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
                    Showing {filtered.length} of {properties.length}
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
                {uploadedData ? "From uploaded file" : "Demo data"}
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
                  {properties.map((p) => (
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
                {highValueProps.length > 0
                  ? `${highValueProps.length} high value properties`
                  : "No high value properties found"}
              </span>
            </div>
            {highValueProps.length > 0 ? (
              <>
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
              </>
            ) : (
              <div style={{ padding: "40px", textAlign: "center", color: "#6b7280" }}>
                <p>No high value properties with Document B information found in the current dataset.</p>
                <p style={{ fontSize: 12, marginTop: 8 }}>
                  High value properties require a "docBRef" field to be displayed here.
                </p>
              </div>
            )}
          </div>
        )}

        {/* 5. Analytics */}
        {activeTab === "analytics" && (
          <div style={{ padding: "30px 40px", background: "#f5f5f5" }}>
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Portfolio analytics</h2>
                <span className="card-badge">
                  {uploadedData ? "From uploaded file" : "Demo portfolio"}
                </span>
              </div>

              <div style={{ padding: "24px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>
                {/* Property Types Chart */}
                <div>
                  <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16, color: "#111827" }}>
                    Property types distribution
                  </h3>
                  <ResponsiveContainer width="100%" height={400}>
                    <PieChart>
                      <Pie
                        data={propertyTypesData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={120}
                        fill="#4f46e5"
                        label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
                        labelLine={false}
                      >
                        {propertyTypesData.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={PROPERTY_TYPE_COLORS[index % PROPERTY_TYPE_COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value) => [`${value} properties`, "Count"]}
                      />
                      <Legend
                        verticalAlign="bottom"
                        height={36}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {/* EPC Ratings Chart */}
                <div>
                  <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16, color: "#111827" }}>
                    EPC ratings distribution
                  </h3>
                  <ResponsiveContainer width="100%" height={400}>
                    <PieChart>
                      <Pie
                        data={epcRatingsData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={120}
                        fill="#16a34a"
                        label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
                        labelLine={false}
                      >
                        {epcRatingsData.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={EPC_COLORS[index % EPC_COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value) => [`${value} properties`, "Count"]}
                      />
                      <Legend
                        verticalAlign="bottom"
                        height={36}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Summary statistics and Deprivation Chart side by side */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32, marginTop: 20 }}>
              {/* Portfolio Summary */}
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">Portfolio summary</h2>
                </div>
                <div className="table-wrapper">
                  <table className="risk-table">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Total properties</td>
                        <td><strong>{properties.length}</strong></td>
                      </tr>
                      <tr>
                        <td>Unique property types</td>
                        <td><strong>{propertyTypesData.length}</strong></td>
                      </tr>
                      <tr>
                        <td>Unique EPC ratings</td>
                        <td><strong>{epcRatingsData.length}</strong></td>
                      </tr>
                      <tr>
                        <td>Total sum insured</td>
                        <td>
                          <strong>
                            £{(properties.reduce((s, p) => s + (p.sumInsured || 0), 0) / 1_000_000).toFixed(2)}m
                          </strong>
                        </td>
                      </tr>
                      <tr>
                        <td>Properties with missing data</td>
                        <td>
                          <strong style={{ color: portfolioSnapshot.missingCore > 0 ? "#dc2626" : "#16a34a" }}>
                            {portfolioSnapshot.missingCore}
                          </strong>
                        </td>
                      </tr>
                      <tr>
                        <td>High/Very High risk properties</td>
                        <td>
                          <strong>
                            {properties.filter((p) => p.riskBand === "High" || p.riskBand === "Very High").length}
                          </strong>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Deprivation Index Distribution Chart */}
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">Deprivation Index Distribution</h2>
                  <span className="card-badge">
                    Properties grouped by deprivation score ranges
                  </span>
                </div>
                <div style={{ padding: "24px" }}>
                  <ResponsiveContainer width="100%" height={400}>
                    <BarChart
                      data={deprivationData}
                      margin={{ top: 16, right: 16, bottom: 16, left: 16 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis
                        dataKey="range"
                        label={{ value: 'Deprivation Score Range', position: 'insideBottom', offset: -5 }}
                      />
                      <YAxis
                        label={{ value: 'Number of Properties', angle: -90, position: 'insideLeft' }}
                      />
                      <Tooltip
                        formatter={(value) => [`${value} properties`, "Count"]}
                        contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '6px' }}
                      />
                      <Bar
                        dataKey="count"
                        name="Properties"
                        fill="#4f46e5"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

