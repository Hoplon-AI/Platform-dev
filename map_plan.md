# Plan: Separate Risk Map page with toggleable risk layers

> Self-contained build plan. A fresh chat can execute this without prior context.
> Scope confirmed with the user: **portfolio-scoped MVP, frontend-only.**

---

## 1. Context & goal

EquiRisk wants a **new, separate full-page map** ("Risk Map") that shows the
portfolio's properties with **toggleable risk overlays** (flood, geology, radon)
and lets the user **color the properties by a risk dimension** (flood band /
readiness / listed status). It is a pitch-ready demonstration of spatial risk
intelligence using free, open (OGL) government datasets.

This is **almost entirely a reuse job** — the data and the map stack already
exist. The new work is: a layer control, a handful of verified WMS overlay
configs, a risk-color toggle, and a thin new page wired into the nav.

### What already exists (do NOT rebuild)

- **Enriched data already exposed.** `GET /api/v1/portfolios/properties`
  (`backend/api/v1/portfolios_router.py`, the SELECT around line 214) already
  returns, per property: `flood_risk_band`, `flood_risk_source`,
  `x_coordinate` / `y_coordinate` (British National Grid, EPSG:27700), `uprn`,
  `parent_uprn`, `height_max_m`, `building_footprint_m2`, `is_listed`,
  `listed_grade`, `epc_rating`, `postcode`, `country_code`. The enrichment
  worker (`backend/workers/enrichment_worker.py`) already calls
  `backend/geo/uprn_maps/flood_risk.py` and persists the flood band.
  **➜ No backend changes are required for this feature.**
- **Map stack already installed & working.**
  `frontend/src/components/PortfolioMap.jsx` is **raw Leaflet** (uses `L.map`,
  `L.tileLayer`, `L.layerGroup` directly — NOT the react-leaflet JSX
  components, despite react-leaflet being a dependency). This matters: it means
  toggleable layers are added with native **`L.control.layers()`** +
  **`L.tileLayer.wms()`** — **no new npm dependency**.
  Already in `package.json`: `leaflet@1.9.4`, `react-leaflet@5.0.0`,
  `proj4@2.20.8` (BNG↔WGS84), `leaflet.markercluster@1.5.3`, `supercluster`.
- **Reusable frontend utilities:**
  - `frontend/src/utils/normalise.js` → `normaliseProperty()` maps any backend
    row shape into a consistent frontend object (coords via `resolveCoordinates`,
    `flood_risk_band`, `readiness_score`/`readiness_band`, `is_listed`, etc.).
  - `frontend/src/utils/mapHelpers.js` → `getPropertyLatLon`, `readinessColor`,
    `readinessBandFromScore`, `riskColor`, `getPropertyId`, `getPropertyLabel`,
    `buildPropertyFeatureAssignments` (matches properties to footprint polygons),
    etc.
  - `frontend/src/constants/map.js` → `DEFAULT_CENTER`, zoom levels,
    `BUILDINGS_URL` (`/buildings_cathcart.geojson`), `PROPERTY_TYPE_COLORS`.
  - `frontend/src/components/map/markerIcons.js`, `.../popups.js`.
- **Navigation is state-driven (no react-router).** `App.jsx` holds
  `const [activeNav, setActiveNav] = useState("uploads")` and renders pages
  conditionally (`if (activeNav === "overview") return <PortfolioDashboard/>`,
  etc., around lines 674–768). `Sidebar.jsx` calls `onNavigate("...")`.
  Existing nav keys: `uploads`, `overview`, `insights`, `block-analysis`.

### Scope decisions (confirmed with user)

- **Portfolio-scoped, frontend-only MVP.** Show the user's enriched properties
  with external risk overlays. **Do NOT** build the HMLR INSPIRE GML→PostGIS
  pipeline or a click-anywhere property-fetch endpoint (YAGNI for MVP — we
  already have building footprints via the static `/buildings_cathcart.geojson`
  and, if ever needed, `backend/geo/uprn_maps/uprn_to_height.get_building_from_coords`
  returns NGD footprint GeoJSON).
- **Overlays for MVP:** flood (SEPA/EA/NRW), BGS geology, BGS radon, plus
  risk-colored property footprints.

> ⚠️ **Demo-critical detail:** the test portfolio **Cathcart** is in
> **Glasgow = Scotland**. The **England EA** flood layer will NOT cover it.
> The **SEPA (Scotland)** flood layer is the one that actually renders over the
> demo data. Make SEPA the default/visible flood overlay for the demo.

---

## 2. Verified external WMS endpoints

All checked **live against GetCapabilities (June 2026)**. All OGL / free for
commercial use. All serve transparent `image/png`.

| Layer | Endpoint (WMSServer) | WMS layer name(s) | CRS |
|---|---|---|---|
| **Flood — Scotland (SEPA)** ⭐ demo | `https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer` | `River_Flooding_High_Likelihood5469`, `River_Flooding_Medium_Likelihood22646`, `River_Flooding_Low_Likelihood52415`, `Coastal_Flooding_High_Likelihood21000`, `Coastal_Flooding_Medium_Likelihood21859`, `Coastal_Flooding_Low_Likelihood29650` | **EPSG:4326 ONLY** — must set `crs: L.CRS.EPSG4326` (no 3857) |
| **Flood — England (EA NaFRA2)** | `https://environment.data.gov.uk/spatialdata/nafra2-risk-of-flooding-from-rivers-and-sea/wms` | `rofrs_4band` | EPSG:3857 ok |
| **Geology — BGS 1:50k** | `https://map.bgs.ac.uk/arcgis/services/BGS_Detailed_Geology/MapServer/WMSServer` | `BGS.50k.Bedrock`, `BGS.50k.Superficial.deposits`, `BGS.50k.Mass.movement` | EPSG:3857 ok |
| **Radon — BGS** | `https://map.bgs.ac.uk/arcgis/services/GeoIndex_Onshore/radon/MapServer/WMSServer` | `Radon.1km` | EPSG:3857 ok |
| Flood — Wales (NRW) *(optional)* | `https://datamap.gov.wales/geoserver/inspire-nrw/wms` | verify at impl — WFS typenames listed in `backend/geo/uprn_maps/flood_risk.py:106` | verify |

Notes:
- BGS layers and the SEPA/radon services only render within certain zoom ranges
  (BGS radon ~1:100k–1:25k; geology when zoomed in). Expect blank tiles when
  zoomed far out — that's normal, not a bug.
- The SEPA CRS quirk is the single most likely thing to break. Leaflet defaults
  to `L.CRS.EPSG3857`; SEPA's WMS does not advertise 3857, so its tiles come
  back blank/erroring unless that one layer is created with
  `crs: L.CRS.EPSG4326` (Leaflet then issues WMS 1.3.0 requests in 4326).

**Mandatory attributions** (add to the Leaflet attribution control):
- BGS: `Contains British Geological Survey materials © UKRI 2026`
- EA: `© Environment Agency — Open Government Licence v3.0`
- SEPA: `© SEPA — Open Government Licence v3.0`

`// ponytail: WMS endpoints + layer names verified June 2026. Agencies rename`
`// services periodically. If a layer returns 404/blank, re-run`
`// GetCapabilities (append ?service=WMS&request=GetCapabilities) and update`
`// wmsLayers.js — that file is the single source of truth, the calibration knob.`

---

## 3. Implementation

Five files: **2 new, 3 small edits.** No new dependencies. No backend changes.

### 3.1 NEW — `frontend/src/constants/wmsLayers.js`

Single source of truth for overlay configs. Export the verified table as data:

```js
// Verified WMS overlay configs (GetCapabilities, June 2026). See map_plan.md.
// crs: '4326' forces L.CRS.EPSG4326 (required for SEPA, which has no 3857).
export const WMS_LAYERS = [
  {
    key: "sepa-flood-river-high",
    group: "Flood (Scotland)",
    label: "SEPA River Flood — High likelihood",
    url: "https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer",
    layers: "River_Flooding_High_Likelihood5469",
    crs: "4326",
    defaultOn: true, // demo is in Scotland
    attribution: "© SEPA — OGL v3.0",
  },
  {
    key: "sepa-flood-river-med",
    group: "Flood (Scotland)",
    label: "SEPA River Flood — Medium likelihood",
    url: "https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer",
    layers: "River_Flooding_Medium_Likelihood22646",
    crs: "4326",
    attribution: "© SEPA — OGL v3.0",
  },
  {
    key: "ea-flood-rofrs",
    group: "Flood (England)",
    label: "EA Risk of Flooding from Rivers & Sea",
    url: "https://environment.data.gov.uk/spatialdata/nafra2-risk-of-flooding-from-rivers-and-sea/wms",
    layers: "rofrs_4band",
    crs: "3857",
    attribution: "© Environment Agency — OGL v3.0",
  },
  {
    key: "bgs-bedrock",
    group: "Geology",
    label: "BGS Bedrock (1:50k)",
    url: "https://map.bgs.ac.uk/arcgis/services/BGS_Detailed_Geology/MapServer/WMSServer",
    layers: "BGS.50k.Bedrock",
    crs: "3857",
    attribution: "Contains British Geological Survey materials © UKRI 2026",
  },
  {
    key: "bgs-superficial",
    group: "Geology",
    label: "BGS Superficial deposits (1:50k)",
    url: "https://map.bgs.ac.uk/arcgis/services/BGS_Detailed_Geology/MapServer/WMSServer",
    layers: "BGS.50k.Superficial.deposits",
    crs: "3857",
    attribution: "Contains British Geological Survey materials © UKRI 2026",
  },
  {
    key: "bgs-massmovement",
    group: "Geology",
    label: "BGS Mass movement / landslide (1:50k)",
    url: "https://map.bgs.ac.uk/arcgis/services/BGS_Detailed_Geology/MapServer/WMSServer",
    layers: "BGS.50k.Mass.movement",
    crs: "3857",
    attribution: "Contains British Geological Survey materials © UKRI 2026",
  },
  {
    key: "bgs-radon",
    group: "Geology",
    label: "BGS Indicative Radon (1km)",
    url: "https://map.bgs.ac.uk/arcgis/services/GeoIndex_Onshore/radon/MapServer/WMSServer",
    layers: "Radon.1km",
    crs: "3857",
    attribution: "Contains British Geological Survey materials © UKRI 2026",
  },
];
```

### 3.2 EDIT — `frontend/src/components/PortfolioMap.jsx`

Add two **optional** props. The existing Portfolio Overview page passes neither,
so its behaviour is **unchanged** (regression-safe).

- **`overlays = []`** — when non-empty, build a layer control. Inside the init
  `useLayoutEffect` (currently around line 141, right after the CartoDB base
  tile layer is added) add:

  ```js
  if (overlays.length) {
    const cartodb = /* the L.tileLayer you just created — keep a ref to it */;
    const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: "© OpenStreetMap",
    });
    const overlayDict = {};
    overlays.forEach((cfg) => {
      const layer = L.tileLayer.wms(cfg.url, {
        layers: cfg.layers,
        format: "image/png",
        transparent: true,
        crs: cfg.crs === "4326" ? L.CRS.EPSG4326 : L.CRS.EPSG3857,
        opacity: 0.55,
        attribution: cfg.attribution,
      });
      overlayDict[cfg.label] = layer;
      if (cfg.defaultOn) layer.addTo(map);
    });
    L.control.layers({ "Light (CARTO)": cartodb, "OpenStreetMap": osm }, overlayDict,
      { collapsed: false, position: "topright" }).addTo(map);
  }
  ```

  Re-enable the attribution control for this page: the current init passes
  `attributionControl: false` (line 144). Either set it `true` when
  `overlays.length`, or add `L.control.attribution().addTo(map)` so the OGL
  credits show.

- **`colorBy = 'readiness'`** — one of `'readiness' | 'flood' | 'listed'`.
  Thread it into:
  - the `propertyPoints` useMemo (line ~81): replace
    `color: readinessColor(readinessBand)` with
    `color: colorForMode(property, colorBy)` (helper added in 3.3).
  - the footprint `style` callback (line ~456): replace the `fillColor` source
    (`getPropertyDisplayColor(assignedPoint.raw, isSelected)`) with
    `colorForMode(assignedPoint.raw, colorBy)` so footprints recolor too.
  - Add `colorBy` to the dependency arrays of the affected `useEffect`/`useMemo`.

Keep these additions gated behind the props — when `overlays` is empty and
`colorBy` is `'readiness'`, the component is byte-for-byte equivalent in
behaviour to today.

### 3.3 EDIT — `frontend/src/utils/mapHelpers.js`

Add color helpers (reuse the existing `readinessColor`):

```js
export function floodColor(band) {
  switch ((band || "").toLowerCase()) {
    case "high":     return "#ef4444";
    case "medium":   return "#f59e0b";
    case "low":      return "#fbbf24";
    case "very low": return "#22c55e";
    default:         return "#94a3b8"; // unknown / could not match
  }
}

// Dispatch marker/footprint fill color by the active "colorBy" mode.
export function colorForMode(raw, colorBy) {
  if (colorBy === "flood")  return floodColor(raw?.flood_risk_band);
  if (colorBy === "listed") return raw?.is_listed ? "#7c3aed" : "#94a3b8";
  return readinessColor(getPropertyBand(raw)); // 'readiness' (default)
}
```

### 3.4 NEW — `frontend/src/pages/FullMapPage.jsx`

Thin page. Reuses the **same normalised properties/blocks already in App
state** — no new fetch. Renders a full-height `PortfolioMap` with overlays +
a color-by toggle + legend + MVP disclaimer.

```jsx
import React, { useState } from "react";
import PortfolioMap from "../components/PortfolioMap.jsx";
import { WMS_LAYERS } from "../constants/wmsLayers.js";

const COLOR_MODES = [
  { key: "readiness", label: "Readiness" },
  { key: "flood",     label: "Flood risk" },
  { key: "listed",    label: "Listed" },
];

export default function FullMapPage({ properties = [], blocks = [] }) {
  const [colorBy, setColorBy] = useState("flood"); // flood = most demo-relevant
  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
        <strong>Color properties by:</strong>
        {COLOR_MODES.map((m) => (
          <button key={m.key}
            onClick={() => setColorBy(m.key)}
            aria-pressed={colorBy === m.key}
            style={{ fontWeight: colorBy === m.key ? 700 : 400 }}>
            {m.label}
          </button>
        ))}
      </div>
      <PortfolioMap
        properties={properties}
        blocks={blocks}
        overlays={WMS_LAYERS}
        colorBy={colorBy}
        viewMode="properties"
      />
      {/* Legend reflecting colorBy + MVP disclaimer */}
      <p style={{ fontSize: 12, color: "#64748b", marginTop: 8 }}>
        Risk overlays use generalised open (OGL) datasets for demonstration —
        not property-precise underwriting data.
      </p>
    </div>
  );
}
```

(Match the surrounding pages' styling conventions — the above is structural,
not final styling. Add a small legend keyed to `colorBy` using the same colors
as `colorForMode`.)

### 3.5 WIRE NAV — `frontend/src/components/Sidebar.jsx` + `frontend/src/App.jsx`

- **Sidebar.jsx:** add a nav entry alongside the existing ones (around lines
  46–78), e.g. label "Risk Map", key `"risk-map"`, calling
  `onNavigate("risk-map")`.
- **App.jsx:** in the conditional render switch (around line 768) add:
  ```jsx
  if (activeNav === "risk-map")
    return <FullMapPage
      properties={ingestionResult?.properties ?? []}
      blocks={ingestionResult?.blocks ?? []} />;
  ```
  Pass whatever the dashboard already uses for normalised properties/blocks
  (confirm the exact prop name in App.jsx — the dashboard receives the same
  normalised `properties`). Import `FullMapPage` at the top.
  If App tracks visited tabs (`visitedNav`), add `"risk-map"` there too.

---

## 4. Deliberately skipped (add later, beyond MVP)

- **HMLR INSPIRE GML → PostGIS pipeline + click-anywhere property fetch.**
  Add when moving from portfolio-scoped to a general "click anywhere in the UK"
  explore map. We already have footprints for known portfolio units.
- **New backend endpoint.** Add only when a layer needs a server-side spatial
  join the existing `/properties` payload can't supply.
- **BGS premium GeoSure** (paid, 1:50k street-level subsidence/shrink-swell).
  Free BGS data is generalised; fine for the MVP demo.
- **Always-on portfolio-wide footprints.** The static `/buildings_cathcart.geojson`
  is Cathcart-only and footprints currently render on block-select to avoid
  loading thousands of polygons. Keep that behaviour.
- **Wales (NRW) flood overlay** — include only if a Welsh portfolio is demoed;
  verify the WMS endpoint/layer names at that point.

---

## 5. Verification (end-to-end)

1. Start services per `CLAUDE.md` (set env vars; `docker compose up -d`;
   `uvicorn backend.main:app --reload --port 8000`; in `frontend/`,
   `npm install` then `npm run dev`).
2. Load the `ha_demo` portfolio so the frontend holds normalised
   `properties`/`blocks`.
3. Click the new **Risk Map** sidebar entry → full-page map renders with
   Cathcart property markers.
4. Open the layer control (top-right) and toggle:
   - **SEPA River Flood** → blue flood polygons appear over Glasgow. **This is
     the key test of the EPSG:4326 CRS fix** — if blank, the SEPA layer was
     created with the default 3857 CRS.
   - **BGS Bedrock** and **BGS Radon** → raster overlays render once zoomed in
     (blank when zoomed far out is expected).
5. Use the **Color by** toggle → **Flood**: markers and footprints recolor by
   `flood_risk_band` (High=red … Very Low=green); legend updates. Try
   **Listed** and **Readiness** too.
6. Confirm the OGL attribution strings (BGS © UKRI, EA, SEPA) appear in the map
   corner.
7. Regression: open **Portfolio Overview** — its map is unchanged (it passes no
   `overlays`/`colorBy`).
8. `npm run lint` is clean.

---

## 6. Quick reference — files touched

| File | Change |
|---|---|
| `frontend/src/constants/wmsLayers.js` | **NEW** — verified WMS overlay configs |
| `frontend/src/components/PortfolioMap.jsx` | EDIT — optional `overlays` (layer control) + `colorBy` props |
| `frontend/src/utils/mapHelpers.js` | EDIT — `floodColor()`, `colorForMode()` |
| `frontend/src/pages/FullMapPage.jsx` | **NEW** — the Risk Map page |
| `frontend/src/components/Sidebar.jsx` | EDIT — "Risk Map" nav entry |
| `frontend/src/App.jsx` | EDIT — route `"risk-map"` → `<FullMapPage/>` |

No backend, DB, or dependency changes.
