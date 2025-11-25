// App.js
import React, { useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import LandingPage from "./LandingPage";
import  { RAW_PROPERTIES } from "./data/properties";


// Fix default Leaflet marker icons when bundling
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});


const TABS = [
  { id: "portfolio", label: "Portfolio view" },
  { id: "stock", label: "Stock listing (Doc A)" },
  { id: "highvalue", label: "High value (Doc B)" },
  { id: "upload", label: "Upload CSV" },
];

const unique = (arr) => [...new Set(arr)];

function App() {
  // All hooks must be at the top level of the component
  const [showLanding, setShowLanding] = useState(true);
  const [activeTab, setActiveTab] = useState("portfolio");
  const [search, setSearch] = useState("");
  const [cityFilter, setCityFilter] = useState("All");
  const [riskFilter, setRiskFilter] = useState("All");
  const [tenureFilter, setTenureFilter] = useState("All");
  const [maxPremium, setMaxPremium] = useState(700);
  const [minEpc, setMinEpc] = useState("Any");
  const [sortBy, setSortBy] = useState("purePremiumDesc");
  const [uploadedData, setUploadedData] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("http://localhost:8000/upload-csv", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Upload failed");
      }

      const result = await response.json();
      setUploadedData(result);
    } catch (error) {
      setUploadError(error.message);
    } finally {
      setIsUploading(false);
    }
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

  const filtered = useMemo(() => {
    const epcOrder = ["A", "B", "C", "D", "E", "F", "G"];
    const minEpcIndex = epcOrder.indexOf(minEpc);

    let out = RAW_PROPERTIES.filter((p) => {
      const fullAddress =
        `${p.address1} ${p.address2} ${p.address3}`.toLowerCase();
      const matchesSearch =
        !search ||
        fullAddress.includes(search.toLowerCase()) ||
        p.postcode.toLowerCase().includes(search.toLowerCase()) ||
        (p.propertyReference || "")
          .toLowerCase()
          .includes(search.toLowerCase());
      const matchesCity = cityFilter === "All" || p.city === cityFilter;
      const matchesRisk = riskFilter === "All" || p.riskBand === riskFilter;
      const matchesTenure =
        tenureFilter === "All" || p.occupancyType === tenureFilter;
      const matchesPremium = p.purePremium <= maxPremium;
      const matchesEpc =
        minEpc === "Any" || epcOrder.indexOf(p.epcRating) <= minEpcIndex;

      return (
        matchesSearch &&
        matchesCity &&
        matchesRisk &&
        matchesTenure &&
        matchesPremium &&
        matchesEpc
      );
    });

    out = [...out].sort((a, b) => {
      switch (sortBy) {
        case "purePremiumDesc":
          return b.purePremium - a.purePremium;
        case "purePremiumAsc":
          return a.purePremium - b.purePremium;
        case "claimFrequencyDesc":
          return b.claimFrequency - a.claimFrequency;
        case "deprivationDesc":
          return b.deprivationIndex - a.deprivationIndex;
        default:
          return 0;
      }
    });

    return out;
  }, [
    search,
    cityFilter,
    riskFilter,
    tenureFilter,
    maxPremium,
    minEpc,
    sortBy,
  ]);

  const summary = useMemo(() => {
    if (!filtered.length) return null;
    const n = filtered.length;
    const totalPremium = filtered.reduce((s, p) => s + p.purePremium, 0);
    const avgPremium = totalPremium / n;
    const avgFrequency = filtered.reduce((s, p) => s + p.claimFrequency, 0) / n;
    const highRiskCount = filtered.filter(
      (p) => p.riskBand === "High" || p.riskBand === "Very High"
    ).length;
    const totalSumInsured = filtered.reduce(
      (s, p) => s + (p.sumInsured || 0),
      0
    );
    return {
      n,
      avgPremium,
      avgFrequency,
      highRiskCount,
      totalSumInsured,
    };
  }, [filtered]);

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

  // Simple Doc A validation-style aggregates (mimicking the pivot)
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

  // Conditional rendering - AFTER all hooks
  if (showLanding) {
    return <LandingPage onGetStarted={() => setShowLanding(false)} />;
  }

  return (
    <div className="app-root">
      <div className="app-shell">
        {/* Header */}
        <header className="app-header">
          <div>
            <div className="app-badge">Hoplon • Underwriter dashboard</div>
            <h1 className="app-title">Property &amp; risk workspace</h1>
            <p className="app-subtitle">
              Integrated view of the stock listing (Document A), high-value
              blocks (Document B) and portfolio risk telemetry. Built for
              underwriters to interrogate values, perils and completeness.
            </p>
          </div>
          <div className="app-meta">
            Demo dataset · Mirrors Document A &amp; B structure
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

        {/* Layout varies by tab */}
        {activeTab === "portfolio" && (
          <div className="app-layout">
            {/* Filters */}
            <aside className="sidebar-card">
              <h2 className="card-title">Filters</h2>

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
                <label className="field-label">Max pure premium (£)</label>
                <input
                  type="range"
                  min={50}
                  max={700}
                  step={10}
                  value={maxPremium}
                  onChange={(e) => setMaxPremium(Number(e.target.value))}
                  className="range"
                />
                <div className="range-value">≤ £{maxPremium}</div>
              </div>

              <div className="field">
                <label className="field-label">Minimum EPC rating</label>
                <select
                  value={minEpc}
                  onChange={(e) => setMinEpc(e.target.value)}
                  className="input"
                >
                  <option value="Any">Any</option>
                  <option value="A">A</option>
                  <option value="B">B or better</option>
                  <option value="C">C or better</option>
                  <option value="D">D or better</option>
                </select>
              </div>

              <div className="field">
                <label className="field-label">Sort by</label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="input"
                >
                  <option value="purePremiumDesc">
                    Pure premium (high → low)
                  </option>
                  <option value="purePremiumAsc">
                    Pure premium (low → high)
                  </option>
                  <option value="claimFrequencyDesc">
                    Claim frequency (high → low)
                  </option>
                  <option value="deprivationDesc">
                    Deprivation index (high → low)
                  </option>
                </select>
              </div>

              <div className="field">
                <label className="field-label">Data quality notes</label>
                <div className="field-note">
                  All information to be included where available. Best
                  endeavours should be used to populate missing fields, in line
                  with Document A notes.
                </div>
              </div>
            </aside>

            {/* Main column: summary + map + detailed table */}
            <main className="main-column">
              {/* Summary cards */}
              {summary && (
                <section className="summary-grid">
                  <div className="summary-card">
                    <div className="summary-label">Properties in view</div>
                    <div className="summary-value">{summary.n}</div>
                    <div className="summary-footnote">
                      out of {RAW_PROPERTIES.length} in this demo portfolio
                    </div>
                  </div>
                  <div className="summary-card">
                    <div className="summary-label">Avg pure premium</div>
                    <div className="summary-value">
                      £{summary.avgPremium.toFixed(0)}
                    </div>
                    <div className="summary-footnote">
                      modelled annual technical rate
                    </div>
                  </div>
                  <div className="summary-card">
                    <div className="summary-label">Sum insured in view</div>
                    <div className="summary-value">
                      £{(summary.totalSumInsured / 1_000_000).toFixed(1)}m
                    </div>
                    <div className="summary-footnote">
                      aggregate declared values for filtered properties
                    </div>
                  </div>
                </section>
              )}

              {/* Edinburgh Map */}
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
                            <br />
                            Pure premium: £{p.purePremium.toFixed(0)}
                          </div>
                        </Popup>
                      </Marker>
                    ))}
                  </MapContainer>
                </div>
              </section>

              {/* Detailed table – merged technical view */}
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
                        <th>Property (Doc A)</th>
                        <th>Geo / Deprivation</th>
                        <th>Construction &amp; features</th>
                        <th>Perils &amp; claims</th>
                        <th>Risk metrics</th>
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
                            <div className="prop-meta">
                              Sum insured: £
                              {p.sumInsured.toLocaleString("en-GB")} (
                              {p.sumInsuredType})
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
                            <div className="pill pill-risk">
                              <span
                                className={`pill-dot pill-dot-${p.riskBand
                                  .toLowerCase()
                                  .replace(" ", "")}`}
                              />
                              {p.riskBand} risk
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
                            <div className="cell-meta">
                              Last claim: {p.lastClaimDate || "None"}
                            </div>
                          </td>

                          <td>
                            <div className="cell-strong">
                              Pure premium: £{p.purePremium.toFixed(0)}
                            </div>
                            <div className="cell-muted">
                              Expected severity: £
                              {p.expectedSeverity.toLocaleString("en-GB")}
                            </div>
                            <div className="cell-muted">
                              Maintenance score: {p.maintenanceScore.toFixed(1)}
                            </div>
                            <div className="cell-muted flags-label">
                              Underwriter flags:
                            </div>
                            <ul className="flags-list">
                              {p.deprivationIndex > 8 && (
                                <li>High deprivation area</li>
                              )}
                              {p.floodScore > 0.5 && (
                                <li>Elevated flood risk</li>
                              )}
                              {p.claimFrequency > 0.2 && (
                                <li>Frequent claims history</li>
                              )}
                              {p.maintenanceScore < 6 && (
                                <li>Maintenance concerns</li>
                              )}
                              {p.deprivationIndex <= 8 &&
                                p.floodScore <= 0.5 &&
                                p.claimFrequency <= 0.2 &&
                                p.maintenanceScore >= 6 && <li>None</li>}
                            </ul>
                          </td>
                        </tr>
                      ))}

                      {filtered.length === 0 && (
                        <tr>
                          <td colSpan={5} className="empty-row">
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

        {/* Stock listing tab – closer to Document A layout */}
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

            {/* Very light validation summary, echoing the pivot */}
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

        {/* High value tab – Document B-flavoured */}
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
                          Pure premium: £{p.purePremium.toFixed(0)}
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
              including construction features, fire safety measures and
              remediation status (for example EWS, ACM/HPL panels). It is
              designed to sit alongside the stock listing, not replace it.
            </div>
          </div>
        )}

        {activeTab === "upload" && (
  <div className="card" style={{ marginTop: 20 }}>
    <div className="card-header">
      <h2 className="card-title">Upload CSV File</h2>
      <span className="card-badge">
        Upload and standardize property data
      </span>
    </div>

    <div style={{ padding: "20px" }}>
      {/* File upload input */}
      <div className="field">
        <label className="field-label">Select CSV File</label>
        <input
          type="file"
          accept=".csv"
          onChange={handleFileUpload}
          disabled={isUploading}
          className="input"
          style={{ padding: "8px" }}
        />
      </div>

      {/* Loading indicator */}
      {isUploading && (
        <div style={{ marginTop: 20, textAlign: "center" }}>
          <p>Processing file...</p>
        </div>
      )}

      {/* Error message */}
      {uploadError && (
        <div
          style={{
            marginTop: 20,
            padding: 15,
            backgroundColor: "#fee",
            borderRadius: 4,
            color: "#c00",
          }}
        >
          <strong>Error:</strong> {uploadError}
        </div>
      )}

      {/* Success message and data display */}
      {uploadedData && !isUploading && (
        <div style={{ marginTop: 20 }}>
          <div
            style={{
              padding: 15,
              backgroundColor: "#efe",
              borderRadius: 4,
              marginBottom: 20,
            }}
          >
            <strong>✓ Success!</strong> {uploadedData.message}
            <br />
            <small>File: {uploadedData.original_filename}</small>
          </div>

          {/* Column mapping info */}
          {Object.keys(uploadedData.column_mapping).length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <h3 className="card-title">Standardized Columns</h3>
              <table className="risk-table">
                <thead>
                  <tr>
                    <th>Original Column</th>
                    <th>Standardized Column</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(uploadedData.column_mapping).map(
                    ([original, standardized]) => (
                      <tr key={original}>
                        <td>{original}</td>
                        <td>
                          <strong>{standardized}</strong>
                        </td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Display standardized data */}
          <div>
            <h3 className="card-title">Standardized Data Preview</h3>
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
            {uploadedData.row_count > 50 && (
              <p style={{ marginTop: 10, fontSize: 12, color: "#666" }}>
                Showing first 50 of {uploadedData.row_count} rows
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  </div>
)}
      </div>
    </div>
  );
}

export default App;
