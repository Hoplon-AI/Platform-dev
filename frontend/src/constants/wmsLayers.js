// ponytail: WMS endpoints + layer names verified June 2026. Agencies rename
// services periodically. If a layer returns 404/blank, re-run
// GetCapabilities (append ?service=WMS&request=GetCapabilities) and update
// this file — it is the single source of truth.
// coverage: which nations the dataset actually covers — shown next to the
// layer name in the map's layer picker.
export const WMS_LAYERS = [
  // ponytail: EA and SEPA scale-gate flood detail at ~1:50k (~10 m/px) —
  // blank when zoomed out. oversample: 4 requests 4096px tiles so the server
  // thinks we're 4 zoom levels closer; drags visibility out to ~z10 (city).
  // Verified empirically July 2026; past z10 the servers refuse outright.
  {
    key: "sepa-flood-river-high",
    group: "Flood (Scotland)",
    label: "SEPA River Flood — High likelihood",
    coverage: "Scotland",
    url: "https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer",
    layers: "River_Flooding_High_Likelihood5469",
    crs: "4326",
    // ponytail: 3, not 4 — SEPA throttles concurrent requests (per-tile latency
    // triples under viewport load), so 4096px tiles made Scotland crawl.
    // 2048px halves wall time; costs one zoom level (visible ~z11 vs z10).
    oversample: 3,
    attribution: "© SEPA — OGL v3.0",
  },
  {
    key: "sepa-flood-river-med",
    group: "Flood (Scotland)",
    label: "SEPA River Flood — Medium likelihood",
    coverage: "Scotland",
    url: "https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer",
    layers: "River_Flooding_Medium_Likelihood22646",
    crs: "4326",
    oversample: 3,
    attribution: "© SEPA — OGL v3.0",
  },
  {
    key: "ea-flood-rofrs",
    group: "Flood (England)",
    label: "EA Risk of Flooding from Rivers & Sea",
    coverage: "England",
    url: "https://environment.data.gov.uk/spatialdata/nafra2-risk-of-flooding-from-rivers-and-sea/wms",
    layers: "rofrs_4band",
    crs: "3857",
    oversample: 4,
    attribution: "© Environment Agency — OGL v3.0",
  },
  {
    key: "nrw-fraw",
    group: "Flood (Wales)",
    // ponytail: NRW gates the OPPOSITE way — FRAW is a national-overview
    // product that renders zoomed OUT (national→~z12) and hides at street
    // zoom. No oversample: it would push the layer out of its scale window.
    label: "NRW Flood Risk — Rivers & Sea (national view)",
    coverage: "Wales",
    url: "https://datamap.gov.wales/geoserver/inspire-nrw/wms",
    layers: "inspire-nrw:NRW_FLOOD_RISK_FROM_RIVERS,inspire-nrw:NRW_FLOOD_RISK_FROM_SEA",
    crs: "3857",
    attribution: "© Natural Resources Wales — OGL v3.0",
  },
  {
    key: "bgs-bedrock",
    group: "Geology",
    label: "BGS Bedrock (1:50k)",
    coverage: "England · Scotland · Wales",
    url: "https://map.bgs.ac.uk/arcgis/services/BGS_Detailed_Geology/MapServer/WMSServer",
    layers: "BGS.50k.Bedrock",
    crs: "3857",
    oversample: 2,
    // ponytail: BGS geology has NO GetLegendGraphic (verified July 2026) — its
    // real key is hundreds of rock-unit classes. legendText → an instant static
    // caption, no failed network round-trip. Radon (below) keeps its server legend.
    legendText: "Each colour is a distinct bedrock unit (rock type & age) — full key at BGS.",
    attribution: "Contains British Geological Survey materials © UKRI 2026",
  },
  {
    key: "bgs-superficial",
    group: "Geology",
    label: "BGS Superficial deposits (1:50k)",
    coverage: "England · Scotland · Wales",
    url: "https://map.bgs.ac.uk/arcgis/services/BGS_Detailed_Geology/MapServer/WMSServer",
    layers: "BGS.50k.Superficial.deposits",
    crs: "3857",
    oversample: 2,
    legendText: "Each colour is a superficial deposit type (e.g. till, alluvium, sand & gravel) — full key at BGS.",
    attribution: "Contains British Geological Survey materials © UKRI 2026",
  },
  {
    key: "bgs-massmovement",
    group: "Geology",
    // ponytail: landslide polygons are sparse (most of GB has none) and BGS
    // styles them as faint hatching — full opacity, and blank ≠ broken.
    label: "BGS Mass movement / landslide (1:50k, sparse)",
    coverage: "England · Scotland · Wales",
    opacity: 1,
    // ponytail: 4 = 4096px tiles → visible from ~z9 (regional). Server hard-gates
    // at ~26 m/px, so no setting can make it show at national zoom. Sparse layer,
    // so most tiles compress to ~tens of KB.
    oversample: 4,
    url: "https://map.bgs.ac.uk/arcgis/services/BGS_Detailed_Geology/MapServer/WMSServer",
    layers: "BGS.50k.Mass.movement",
    crs: "3857",
    legendText: "Shaded areas are mapped landslide / mass-movement deposits (sparse — most of GB has none).",
    attribution: "Contains British Geological Survey materials © UKRI 2026",
  },
  {
    key: "bgs-radon",
    group: "Geology",
    label: "BGS Indicative Radon (1km)",
    coverage: "England · Scotland · Wales",
    url: "https://map.bgs.ac.uk/arcgis/services/GeoIndex_Onshore/radon/MapServer/WMSServer",
    layers: "Radon.1km",
    crs: "3857",
    attribution: "Contains British Geological Survey materials © UKRI 2026",
  },
  // ponytail: SIMD is the deprivation index that covers the demo (Cathcart =
  // Glasgow = Scotland). Like SEPA, this ArcGIS MapServer advertises ONLY
  // CRS:84/4326/27700 — NO 3857 — so crs MUST be "4326" or tiles come back
  // blank. Verified via GetCapabilities July 2026. LSOA/datazone polygons, so
  // it renders across zoom (no oversample needed).
  {
    key: "simd-2020",
    group: "Deprivation",
    label: "SIMD 2020 — Scottish Index of Multiple Deprivation",
    coverage: "Scotland",
    url: "https://maps.gov.scot/server/services/ScotGov/PeopleSociety/MapServer/WMSServer",
    layers: "SIMD2020",
    crs: "4326",
    attribution: "© Scottish Government / SIMD — OGL v3.0",
  },
  {
    key: "wimd-2019",
    group: "Deprivation",
    label: "WIMD 2019 — Welsh Index of Multiple Deprivation (overall)",
    coverage: "Wales",
    url: "https://datamap.gov.wales/geoserver/inspire-wg/ows",
    layers: "inspire-wg:wimd2019_overall",
    crs: "3857",
    attribution: "© Welsh Government / WIMD 2019 — OGL v3.0",
  },
  // ponytail: England IMD 2019 deliberately omitted — MHCLG/ONS publish it only
  // as an ArcGIS FeatureServer (data-communities.opendata.arcgis.com), not a
  // clean OGL WMS. Wiring it needs a vector/FeatureServer layer, not
  // L.tileLayer.wms — different code path. Add when an English portfolio is
  // demoed. See map_plan.md §4.
];
