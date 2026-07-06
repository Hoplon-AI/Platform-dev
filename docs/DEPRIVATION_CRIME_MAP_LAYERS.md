# Deprivation & Crime Map Layers (GB)

Risk-map overlays showing **deprivation** and **crime** across Great Britain, per
nation. All sources are **free and OGL-licensed** (no API key). Rendered on the
full-screen risk map (`FullMapPage`) in the **Deprivation** group of the layer
picker.

> **One-line summary:** each layer is a *relative ranking* (quintile) of small
> areas within a single nation, from the national deprivation index. Only
> Scotland publishes a literal crime *rate*; England and Wales publish ranks
> only.

---

## 1. What's on the map

| Nation | Overall deprivation | Crime | Small-area unit |
|--------|--------------------|-------|-----------------|
| **Scotland** | SIMD 2020 (overall) | SIMD 2020 — Crime domain | Data zone (6,976) |
| **England** | IMD 2019 (overall) | IMD 2019 — Crime domain | LSOA (32,844) |
| **Wales** | WIMD 2019 (overall) | WIMD 2019 — Community Safety | LSOA (1,909) |

All six live under one group in the top-right picker, each tagged with a coverage
badge. Northern Ireland is not covered (no portfolio demand yet; NIMDM 2017 would
be the source — see §6).

### Reading direction (consistent across all layers)

**Rank 1 = worst** (most deprived / highest crime). Quintile 1 = the worst 20% of
small areas *in that nation*, quintile 5 = the best 20%. The choropleth uses one
blue→green ramp (dark blue = quintile 1 = worst) so all nations read the same way.

### ⚠️ Cross-border comparability caveat

Each index is a **within-nation relative ranking** built by a different
government, in a different year (Scotland 2020, England/Wales 2019), from
different indicators. **A Scottish quintile-1 datazone is not directly comparable
to an English quintile-1 LSOA.** For a UK-wide portfolio spanning borders, treat
these as three separate national views, not one continuous scale. A harmonised
UK index is a post-MVP option (§6).

---

## 2. How the data sources work

Three different service transports feed the layers. This matters because each
returns something different and is wired differently in code.

### 2a. WMS — server-rendered tiles (overall SIMD & overall WIMD)

`GetMap` returns a **pre-styled PNG tile**. The server does the colouring; the
client just displays image tiles. No per-area data reaches the browser, so
**there is no hover tooltip and no access to the underlying numbers**.

- **Scotland overall** — `maps.gov.scot/.../PeopleSociety/MapServer/WMSServer`, layer `SIMD2020` (CRS 4326).
- **Wales overall** — `datamap.gov.wales/geoserver/inspire-wg/ows`, layer `inspire-wg:wimd2019_overall` (CRS 3857).
- Legend via the server's own `GetLegendGraphic` PNG, or a static `legendItems`/`legendText` we author.

### 2b. ArcGIS FeatureServer query — GeoJSON polygons (Scotland crime, England overall + crime)

`.../FeatureServer/<id>/query?...&f=geojson` returns a **GeoJSON FeatureCollection**
of polygons *with attributes*. We fetch only the current viewport (bbox envelope)
and colour the polygons client-side. Because we hold the data, we get **hover
tooltips and the real field values**.

Request shape (used by `type: "arcgis"` entries):

```
?where=1=1
&geometry=<west>,<south>,<east>,<north>&geometryType=esriGeometryEnvelope
&inSR=4326&outSR=4326&spatialRel=esriSpatialRelIntersects
&outFields=<field>,<nameField>[,<rateField>]
&returnGeometry=true&f=geojson
```

| Source | Endpoint (FeatureServer layer) | Key fields | Cap/req |
|--------|-------------------------------|-----------|---------|
| Scotland SIMD | `maps.gov.scot/.../PeopleSociety/MapServer/7/query` | `crimerank` (1–6976), `crimerate` (crimes/10k), `crimecount`, `dzname`; overall `quintilev2`/`decilev2` | 1,000 |
| England IMD | `services-eu1.arcgis.com/EbKcOS6EXZroSyoi/.../Indices_of_Multiple_Deprivation_(IMD)_2019/FeatureServer/0/query` | `IMD_Rank`/`IMD_Decile` (overall), `CriRank`/`CriDec`/`CriScore` (crime), `lsoa11nm` | 2,000 |

### 2c. GeoServer WFS GetFeature — GeoJSON polygons (Wales community safety)

GeoServer has no ArcGIS query endpoint, but its WFS returns GeoJSON. Same idea as
2b, different URL grammar (`type: "wfs"`):

```
?service=WFS&version=2.0.0&request=GetFeature
&typeName=inspire-wg:wimd2019_community_safety
&outputFormat=application/json&srsName=EPSG:4326
&bbox=<south>,<west>,<north>,<east>,urn:ogc:def:crs:EPSG::4326
```

> **Axis-order gotcha:** WFS 2.0.0 with `EPSG:4326` expects the **bbox** as
> `lat,lon` (min-y, min-x, max-y, max-x) — hence the reversed order and the
> explicit `urn:...EPSG::4326`. The **output** GeoJSON is standard `lon,lat`,
> which Leaflet reads directly, so no coordinate flipping is needed on features.

Wales fields: `rank`, `decile`, **`quintile` (ready 1–5)**, `lsoa_name_en`,
`map_group`. No rate field.

---

## 3. Rates — what actually exists

"Crime rate" means different things per nation. Be precise with underwriters:

| Nation | Is there a literal rate? | What we show |
|--------|--------------------------|--------------|
| **Scotland** | **Yes** — `crimerate` = recorded SIMD crimes per **10,000 people** (violence, sexual offences, domestic housebreaking, vandalism, drug offences, common assault). | Tooltip: `<datazone> · quintile N · <rate> crimes per 10,000 people` |
| **England** | **No.** `CriScore` is a *standardised, shrinkage-estimated risk score* (national range ≈ −3.46 to +3.35), **not** a per-capita rate. Underlying indicators are rates but the published domain value is transformed. | Tooltip: `<LSOA> · quintile N` (no rate — none is honestly reportable) |
| **Wales** | **No.** Community-safety domain publishes rank/decile/quintile only. | Tooltip: `<LSOA> · quintile N` |

For **real, comparable recorded-crime rates in England & Wales**, the source is
`data.police.uk` (actual street-level crime counts) combined with an ONS
population denominator — a different build (§6).

---

## 4. How the code is set up

Two files, plus the page that mounts the map.

### `frontend/src/constants/wmsLayers.js` — single source of truth

Exports `WMS_LAYERS`, an array of layer configs. An entry is either a **WMS tile
layer** or a **vector choropleth**, distinguished by the `type` field:

```js
// WMS tile layer (no `type`)
{ key, group, label, coverage, url, layers, crs, oversample?, legendText?, legendItems?, attribution }

// Vector choropleth (type: "arcgis" | "wfs")
{
  key, group, label, coverage,
  type: "arcgis" | "wfs",
  url,
  // arcgis: field + rankMax (rank→quintile), outFields via nameField/rateField
  field?, rankMax?, nameField?, rateField?, rateUnit?,
  // wfs: typeName + a ready quintile field
  typeName?, quintileField?,
  minZoom,           // fetch gate (default 11)
  legendText, legendItems,
  attribution,
}
```

The file header documents the maintenance rule: if a layer goes blank/404, re-run
`GetCapabilities` and update the config — it's the single source of truth.

### `frontend/src/components/PortfolioMap.jsx` — the render engine

`overlays.forEach(cfg => …)` branches on transport:

- **WMS** → `L.tileLayer.wms(...)`, optional `oversample` (requests larger tiles
  to defeat server scale-gating), added to the map + a legend entry.
- **`type: "arcgis" | "wfs"`** → an `L.layerGroup` plus a `refresh()` that:
  1. returns early if the layer is off or `zoom < minZoom` (the **feature-cap
     safety gate** — a city viewport at z≥11 stays well under the 1,000–2,000
     per-request cap);
  2. builds the ArcGIS-envelope or WFS-bbox URL for the current viewport;
  3. `fetch()`es GeoJSON and renders `L.geoJSON` with a quintile-coloured `style`
     and a per-feature tooltip.
  `refresh()` is bound to the layer's `add` event and the map's `moveend`, so it
  re-queries as the user pans/zooms.

The quintile is computed by one shared helper:

```js
const quintileOf = (p) =>
  Math.min(5, Math.max(1,
    cfg.quintileField ? p[cfg.quintileField]           // Wales: ready 1–5
                      : Math.ceil(p[cfg.field] / bucket) // Scotland/England: rank → quintile
  ));
```

Both `arcgis` and `wfs` share the same choropleth styling, tooltip, picker
checkbox, and legend rendering. The picker is a native `<details>`/`<summary>`
grouped list (grouped by `cfg.group`); the legend control re-renders on
`overlayadd`/`overlayremove` and shows either `legendItems` swatches, a
`legendText` caption, or the server's `GetLegendGraphic` image.

### `frontend/src/pages/FullMapPage.jsx`

Passes `WMS_LAYERS` as the `overlays` prop. No per-layer logic here — adding a
layer is a config-only change in `wmsLayers.js` (except a genuinely new transport,
which needs a branch in `PortfolioMap.jsx`).

### Adding a new layer

- **New WMS or new arcgis/wfs layer for an existing transport** → add one object
  to `WMS_LAYERS`. No component change.
- **New transport** (e.g. vector tiles, our own API) → add a branch in the
  `overlays.forEach` in `PortfolioMap.jsx`.

---

## 5. Known limitations (MVP)

- **Coverage-gated.** Each dataset covers only its own nation; nothing renders
  outside it. (The demo portfolio `ha_demo` is Glasgow, so England/Wales layers
  are blank until you pan south.)
- **Zoom-gated to z≥11.** Below city zoom the vector layers clear, to respect the
  per-request feature cap. No national overview for the choropleths.
- **Per-viewport re-fetch.** Every pan/zoom hits the third-party service; no
  caching layer of our own. Fine for demo traffic, not for scale.
- **Visual only.** Deprivation/crime is *not* attached to properties or exported
  in Doc A/B — it's a map overlay, not enrichment data.
- **Not cross-comparable** across borders (see §1 caveat).

---

## 6. Post-MVP: paid / premium / higher-effort alternatives

### Free but higher-effort (recommended first steps)

1. **Real England & Wales crime rates — `data.police.uk`.** Free, OGL, no key.
   Returns actual recorded street-level crimes (points, monthly) by area/point.
   Compute a true rate = crimes in area ÷ ONS mid-year population. Covers
   England, Wales & NI (not Scotland). Build: a point/heatmap layer + a
   population denominator join — a new transport, not a choropleth field.
2. **Police Scotland recorded crime** (`statistics.gov.scot`) — recorded crime by
   council area / datazone, to complement the SIMD crime domain with current
   counts.
3. **Harmonised UK deprivation index** — the mySociety "Composite UK IMD"
   re-ranks all four nations onto one comparable decile scale (free). Solves the
   cross-border comparability caveat for mixed portfolios.
4. **Cache in our own stack.** Pull the FeatureServer/WFS polygons + attributes
   into Postgres (e.g. `silver.deprivation`) and serve via our own API / vector
   tiles. Removes the runtime third-party dependency, kills the 1,000-feature cap
   and zoom gate, and — most valuably — lets us **join deprivation/crime quintile
   to each property by UPRN→LSOA/datazone** and surface it in enrichment, Doc A/B,
   and portfolio insights.

### Commercial / underwriting-grade (paid)

5. **Verisk / LexisNexis Risk Solutions / CoreLogic** — property-level, multi-peril
   risk scores (crime, subsidence, flood, fire) built for insurers. The natural
   upgrade from "relative area quintile" to "underwriting-grade per-address score".
6. **CACI Acorn / Experian Mosaic** — geodemographic segmentation including crime
   propensity and household risk profiles, joinable by postcode/UPRN.
7. **Ordnance Survey premium** (we already hold OS keys) — authoritative boundary
   and address geometry for cleaner property↔area joins than open LSOA/datazone
   boundaries.
8. **JBA Risk Management / Perils** — primarily flood/cat but offer bundled
   multi-peril datasets if the risk model broadens.

### Priority recommendation

For the next iteration, do **#4 (cache + property join)** first — it turns these
from a demo map overlay into real enrichment data that flows into the underwriter
deliverables, and it removes the runtime dependency and caps. Layer **#1
(police.uk rates)** on top for genuine E&W crime rates. Defer commercial feeds
(#5–#8) until a customer needs per-address underwriting scores.

---

## References (all verified July 2026)

- **Scotland SIMD 2020** — `maps.gov.scot/server/rest/services/ScotGov/PeopleSociety/MapServer/7` · [simd.scot](https://simd.scot/)
- **England IoD 2019** — MHCLG FeatureServer (owner `gis@communities.gov.uk`), item `45e05901e0a14cca9ab180975e2e8194`
- **Wales WIMD 2019** — `datamap.gov.wales/geoserver/inspire-wg` · [DataMapWales](https://datamap.gov.wales/)
- **UK crime (E&W&NI)** — [data.police.uk/docs](https://data.police.uk/docs/)
- **Harmonised UK IMD** — mySociety Composite UK IMD
