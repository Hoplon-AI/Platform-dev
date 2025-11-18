// App.js
import React, { useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./styles.css";

// Fix default Leaflet marker icons when bundling
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// ---------- Demo merged dataset ----------
const RAW_PROPERTIES = [
  {
    id: 1,
    uprn: "100012345001",
    address: "12 Caledonia Street",
    city: "Edinburgh",
    region: "Scotland",
    postcode: "EH7 5QX",
    lat: 55.957,
    lon: -3.177,
    buildYear: 1935,
    type: "Tenement Flat",
    tenure: "Social Rent",
    landlord: "Forth Housing Association",
    epcRating: "D",
    deprivationIndex: 8.2,
    floodScore: 0.7,
    crimeIndex: 6.1,
    lastClaimDate: "2023-11-02",
    claimFrequency: 0.18,
    expectedSeverity: 2200,
    purePremium: 396,
    maintenanceScore: 6.5,
    voidDaysLastYear: 12,
    riskBand: "High",
  },
  {
    id: 2,
    uprn: "100012345002",
    address: "5 Meadow Close",
    city: "Edinburgh",
    region: "Scotland",
    postcode: "EH11 3PL",
    lat: 55.935,
    lon: -3.244,
    buildYear: 2004,
    type: "Terraced House",
    tenure: "Social Rent",
    landlord: "Lothian Homes",
    epcRating: "B",
    deprivationIndex: 3.2,
    floodScore: 0.15,
    crimeIndex: 4.0,
    lastClaimDate: "2021-05-14",
    claimFrequency: 0.05,
    expectedSeverity: 1800,
    purePremium: 120,
    maintenanceScore: 8.1,
    voidDaysLastYear: 3,
    riskBand: "Low",
  },
  {
    id: 3,
    uprn: "100012345003",
    address: "27 Riverside Court",
    city: "Glasgow",
    region: "Scotland",
    postcode: "G5 9AB",
    lat: 55.847,
    lon: -4.259,
    buildYear: 1988,
    type: "High-Rise Flat",
    tenure: "Social Rent",
    landlord: "Clyde Housing",
    epcRating: "C",
    deprivationIndex: 9.0,
    floodScore: 0.55,
    crimeIndex: 7.8,
    lastClaimDate: "2024-01-10",
    claimFrequency: 0.25,
    expectedSeverity: 2600,
    purePremium: 520,
    maintenanceScore: 5.2,
    voidDaysLastYear: 25,
    riskBand: "Very High",
  },
  {
    id: 4,
    uprn: "100012345004",
    address: "3 Bramble Grove",
    city: "Newcastle",
    region: "North East",
    postcode: "NE4 7RT",
    lat: 54.974,
    lon: -1.632,
    buildYear: 1975,
    type: "Semi-Detached",
    tenure: "Private Rent",
    landlord: "Private Landlord",
    epcRating: "C",
    deprivationIndex: 5.5,
    floodScore: 0.25,
    crimeIndex: 5.1,
    lastClaimDate: "2022-08-03",
    claimFrequency: 0.12,
    expectedSeverity: 2100,
    purePremium: 252,
    maintenanceScore: 7.3,
    voidDaysLastYear: 7,
    riskBand: "Medium",
  },
  {
    id: 5,
    uprn: "100012345005",
    address: "84 Oakview Crescent",
    city: "Leeds",
    region: "Yorkshire",
    postcode: "LS9 8FG",
    lat: 53.805,
    lon: -1.508,
    buildYear: 2015,
    type: "Apartment Block",
    tenure: "Student Accommodation",
    landlord: "CampusLiving",
    epcRating: "A",
    deprivationIndex: 4.1,
    floodScore: 0.1,
    crimeIndex: 4.8,
    lastClaimDate: "2020-02-18",
    claimFrequency: 0.03,
    expectedSeverity: 2000,
    purePremium: 84,
    maintenanceScore: 8.8,
    voidDaysLastYear: 0,
    riskBand: "Low",
  },
  {
    id: 6,
    uprn: "100012345006",
    address: "102 Dockside Row",
    city: "Liverpool",
    region: "North West",
    postcode: "L3 2HB",
    lat: 53.408,
    lon: -2.999,
    buildYear: 1968,
    type: "Tower Block",
    tenure: "Social Rent",
    landlord: "Mersey Homes",
    epcRating: "E",
    deprivationIndex: 9.3,
    floodScore: 0.4,
    crimeIndex: 8.2,
    lastClaimDate: "2023-04-09",
    claimFrequency: 0.32,
    expectedSeverity: 2800,
    purePremium: 700,
    maintenanceScore: 4.9,
    voidDaysLastYear: 40,
    riskBand: "Very High",
  },
  {
    id: 7,
    uprn: "100012345007",
    address: "6 Willowbank Terrace",
    city: "Glasgow",
    region: "Scotland",
    postcode: "G20 6NB",
    lat: 55.876,
    lon: -4.279,
    buildYear: 1905,
    type: "Tenement Flat",
    tenure: "Mid-Market Rent",
    landlord: "Kelvin Associations",
    epcRating: "D",
    deprivationIndex: 6.7,
    floodScore: 0.35,
    crimeIndex: 6.9,
    lastClaimDate: "2022-11-21",
    claimFrequency: 0.16,
    expectedSeverity: 2300,
    purePremium: 368,
    maintenanceScore: 6.1,
    voidDaysLastYear: 10,
    riskBand: "High",
  },
  {
    id: 8,
    uprn: "100012345008",
    address: "41 Harbour View",
    city: "Cardiff",
    region: "Wales",
    postcode: "CF10 4DJ",
    lat: 51.462,
    lon: -3.162,
    buildYear: 2008,
    type: "Apartment Block",
    tenure: "Private Rent",
    landlord: "Bay Lettings",
    epcRating: "B",
    deprivationIndex: 2.9,
    floodScore: 0.3,
    crimeIndex: 3.9,
    lastClaimDate: "2021-09-02",
    claimFrequency: 0.06,
    expectedSeverity: 1700,
    purePremium: 122,
    maintenanceScore: 8.2,
    voidDaysLastYear: 4,
    riskBand: "Low",
  },
  {
    id: 9,
    uprn: "100012345009",
    address: "19 Ffordd y Parc",
    city: "Swansea",
    region: "Wales",
    postcode: "SA6 8EH",
    lat: 51.659,
    lon: -3.935,
    buildYear: 1972,
    type: "Terraced House",
    tenure: "Social Rent",
    landlord: "West Glamorgan Homes",
    epcRating: "C",
    deprivationIndex: 7.4,
    floodScore: 0.6,
    crimeIndex: 5.7,
    lastClaimDate: "2023-02-15",
    claimFrequency: 0.21,
    expectedSeverity: 1900,
    purePremium: 399,
    maintenanceScore: 6.0,
    voidDaysLastYear: 18,
    riskBand: "High",
  },
  {
    id: 10,
    uprn: "100012345010",
    address: "2 Parkside Lane",
    city: "Manchester",
    region: "North West",
    postcode: "M14 5LP",
    lat: 53.453,
    lon: -2.219,
    buildYear: 1999,
    type: "HMO",
    tenure: "Student Accommodation",
    landlord: "Urban Student Lets",
    epcRating: "C",
    deprivationIndex: 6.0,
    floodScore: 0.2,
    crimeIndex: 7.1,
    lastClaimDate: "2022-03-28",
    claimFrequency: 0.17,
    expectedSeverity: 2100,
    purePremium: 357,
    maintenanceScore: 6.8,
    voidDaysLastYear: 5,
    riskBand: "Medium",
  },
  {
    id: 11,
    uprn: "100012345011",
    address: "58 Orchard Way",
    city: "Bristol",
    region: "South West",
    postcode: "BS5 8DA",
    lat: 51.468,
    lon: -2.547,
    buildYear: 1954,
    type: "Semi-Detached",
    tenure: "Social Rent",
    landlord: "Avon Housing",
    epcRating: "D",
    deprivationIndex: 5.9,
    floodScore: 0.18,
    crimeIndex: 5.4,
    lastClaimDate: "2020-12-10",
    claimFrequency: 0.09,
    expectedSeverity: 1900,
    purePremium: 171,
    maintenanceScore: 7.1,
    voidDaysLastYear: 9,
    riskBand: "Medium",
  },
  {
    id: 12,
    uprn: "100012345012",
    address: "12 Fenbrook Close",
    city: "Cambridge",
    region: "East of England",
    postcode: "CB4 1LR",
    lat: 52.219,
    lon: 0.142,
    buildYear: 2018,
    type: "Terraced House",
    tenure: "Shared Ownership",
    landlord: "Fenland Homes",
    epcRating: "A",
    deprivationIndex: 1.8,
    floodScore: 0.05,
    crimeIndex: 2.3,
    lastClaimDate: "2019-07-01",
    claimFrequency: 0.02,
    expectedSeverity: 2100,
    purePremium: 50,
    maintenanceScore: 9.1,
    voidDaysLastYear: 0,
    riskBand: "Low",
  },
  {
    id: 13,
    uprn: "100012345013",
    address: "73 Eastgate Tower",
    city: "London",
    region: "London",
    postcode: "E1 3QA",
    lat: 51.514,
    lon: -0.055,
    buildYear: 1964,
    type: "High-Rise Flat",
    tenure: "Social Rent",
    landlord: "City Homes",
    epcRating: "E",
    deprivationIndex: 8.8,
    floodScore: 0.25,
    crimeIndex: 9.1,
    lastClaimDate: "2024-03-05",
    claimFrequency: 0.29,
    expectedSeverity: 3000,
    purePremium: 630,
    maintenanceScore: 5.0,
    voidDaysLastYear: 30,
    riskBand: "Very High",
  },
  {
    id: 14,
    uprn: "100012345014",
    address: "4 Greenvale Close",
    city: "York",
    region: "Yorkshire",
    postcode: "YO10 5SQ",
    lat: 53.951,
    lon: -1.058,
    buildYear: 1983,
    type: "Detached",
    tenure: "Private Rent",
    landlord: "Private Landlord",
    epcRating: "B",
    deprivationIndex: 2.5,
    floodScore: 0.22,
    crimeIndex: 3.1,
    lastClaimDate: "2018-11-12",
    claimFrequency: 0.03,
    expectedSeverity: 2500,
    purePremium: 95,
    maintenanceScore: 8.4,
    voidDaysLastYear: 2,
    riskBand: "Low",
  },
  {
    id: 15,
    uprn: "100012345015",
    address: "9 Moorfield Court",
    city: "Sheffield",
    region: "Yorkshire",
    postcode: "S5 7HR",
    lat: 53.419,
    lon: -1.458,
    buildYear: 1970,
    type: "Low-Rise Block",
    tenure: "Social Rent",
    landlord: "Steel City Housing",
    epcRating: "D",
    deprivationIndex: 7.9,
    floodScore: 0.45,
    crimeIndex: 6.5,
    lastClaimDate: "2023-06-16",
    claimFrequency: 0.22,
    expectedSeverity: 2050,
    purePremium: 451,
    maintenanceScore: 5.7,
    voidDaysLastYear: 22,
    riskBand: "High",
  },
];

const unique = (arr) => [...new Set(arr)];

function App() {
  const [search, setSearch] = useState("");
  const [cityFilter, setCityFilter] = useState("All");
  const [riskFilter, setRiskFilter] = useState("All");
  const [tenureFilter, setTenureFilter] = useState("All");
  const [maxPremium, setMaxPremium] = useState(700);
  const [minEpc, setMinEpc] = useState("Any");
  const [sortBy, setSortBy] = useState("purePremiumDesc");

  const cities = useMemo(() => unique(RAW_PROPERTIES.map((p) => p.city)), []);
  const riskBands = useMemo(
    () => unique(RAW_PROPERTIES.map((p) => p.riskBand)),
    []
  );
  const tenures = useMemo(
    () => unique(RAW_PROPERTIES.map((p) => p.tenure)),
    []
  );

  const filtered = useMemo(() => {
    const epcOrder = ["A", "B", "C", "D", "E", "F", "G"];
    const minEpcIndex = epcOrder.indexOf(minEpc);

    let out = RAW_PROPERTIES.filter((p) => {
      const matchesSearch =
        !search ||
        p.address.toLowerCase().includes(search.toLowerCase()) ||
        p.postcode.toLowerCase().includes(search.toLowerCase()) ||
        p.uprn.includes(search);
      const matchesCity = cityFilter === "All" || p.city === cityFilter;
      const matchesRisk = riskFilter === "All" || p.riskBand === riskFilter;
      const matchesTenure = tenureFilter === "All" || p.tenure === tenureFilter;
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
    return {
      n,
      avgPremium,
      avgFrequency,
      highRiskCount,
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

  return (
    <div className="app-root">
      <div className="app-shell">
        {/* Header */}
        <header className="app-header">
          <div>
            <div className="app-badge">Hoplon • Internal Prototype</div>
            <h1 className="app-title">Property Risk Explorer</h1>
            <p className="app-subtitle">
              Slice a demo housing portfolio by geography, risk band and tenure.
              Inspect the technical drivers behind each property’s modelled
              risk.
            </p>
          </div>
          <div className="app-meta">Demo dataset · Not real properties</div>
        </header>

        {/* Layout */}
        <div className="app-layout">
          {/* Filters */}
          <aside className="sidebar-card">
            <h2 className="card-title">Filters</h2>

            <div className="field">
              <label className="field-label">
                Search (address, postcode, UPRN)
              </label>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input"
                placeholder="e.g. Caledonia, EH7, 1000123…"
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
              <label className="field-label">Tenure</label>
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
          </aside>

          {/* Main content */}
          <main className="main-column">
            {/* Summary cards */}
            {summary && (
              <section className="summary-grid">
                <div className="summary-card">
                  <div className="summary-label">Properties in view</div>
                  <div className="summary-value">{summary.n}</div>
                  <div className="summary-footnote">
                    out of {RAW_PROPERTIES.length} in portfolio
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
                  <div className="summary-label">High / very-high risk</div>
                  <div className="summary-value">{summary.highRiskCount}</div>
                  <div className="summary-footnote">
                    properties flagged for enhanced underwriting
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
                          <strong>{p.address}</strong>
                          <br />
                          {p.postcode}
                          <br />
                          {p.type} • {p.tenure}
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

            {/* Table */}
            <section className="card">
              <div className="card-header">
                <h2 className="card-title">Property &amp; risk detail</h2>
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
                      <th>Hazards</th>
                      <th>Claims</th>
                      <th>Risk metrics</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <div className="prop-main">{p.address}</div>
                          <div className="prop-sub">
                            {p.city}, {p.region} {p.postcode}
                          </div>
                          <div className="prop-sub">
                            {p.type} • {p.tenure}
                          </div>
                          <div className="prop-meta">
                            UPRN {p.uprn} · Built {p.buildYear} · EPC{" "}
                            {p.epcRating}
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
                            Flood score: <span>{p.floodScore.toFixed(2)}</span>
                          </div>
                          <div className="cell-strong">
                            Crime index: <span>{p.crimeIndex.toFixed(1)}</span>
                          </div>
                          <div className="cell-muted">
                            Maintenance score: {p.maintenanceScore.toFixed(1)}
                          </div>
                        </td>

                        <td>
                          <div className="cell-strong">
                            Claim frequency:{" "}
                            <span>{p.claimFrequency.toFixed(2)}</span> / year
                          </div>
                          <div className="cell-strong">
                            Expected severity:{" "}
                            <span>
                              £{p.expectedSeverity.toLocaleString("en-GB")}
                            </span>
                          </div>
                          <div className="cell-muted">
                            Last claim: {p.lastClaimDate || "None"}
                          </div>
                        </td>

                        <td>
                          <div className="cell-strong">
                            Pure premium: £{p.purePremium.toFixed(0)}
                          </div>
                          <div className="cell-muted">
                            Roughly frequency × severity × loading
                          </div>
                          <div className="cell-muted flags-label">
                            Underwriter flags:
                          </div>
                          <ul className="flags-list">
                            {p.deprivationIndex > 8 && (
                              <li>High deprivation area</li>
                            )}
                            {p.floodScore > 0.5 && <li>Elevated flood risk</li>}
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
      </div>
    </div>
  );
}

export default App;
