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
  // ponytail: surface-water is the biggest flood gap — most UK flood claims are
  // pluvial, not fluvial. Same SEPA MapServer/CRS/scale-gating as river, so it
  // inherits crs 4326 + oversample 3. Layer names verified via GetCapabilities
  // July 2026. High+Med only, mirroring the river pair (Low adds little signal).
  {
    key: "sepa-flood-surface-high",
    group: "Flood (Scotland)",
    label: "SEPA Surface Water Flood — High likelihood",
    coverage: "Scotland",
    url: "https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer",
    layers: "Surface_Water_and_Small_Watercourses_Flooding_High_Likelihood39344",
    crs: "4326",
    oversample: 3,
    attribution: "© SEPA — OGL v3.0",
  },
  {
    key: "sepa-flood-surface-med",
    group: "Flood (Scotland)",
    label: "SEPA Surface Water Flood — Medium likelihood",
    coverage: "Scotland",
    url: "https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer",
    layers: "Surface_Water_and_Small_Watercourses_Flooding_Medium_Likelihood29035",
    crs: "4326",
    oversample: 3,
    attribution: "© SEPA — OGL v3.0",
  },
  {
    key: "sepa-flood-coastal-high",
    group: "Flood (Scotland)",
    label: "SEPA Coastal Flood — High likelihood",
    coverage: "Scotland",
    url: "https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer",
    layers: "Coastal_Flooding_High_Likelihood21000",
    crs: "4326",
    oversample: 3,
    attribution: "© SEPA — OGL v3.0",
  },
  {
    key: "sepa-flood-coastal-med",
    group: "Flood (Scotland)",
    label: "SEPA Coastal Flood — Medium likelihood",
    coverage: "Scotland",
    url: "https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer",
    layers: "Coastal_Flooding_Medium_Likelihood21859",
    crs: "4326",
    oversample: 3,
    attribution: "© SEPA — OGL v3.0",
  },
  // ponytail: SEPA "Future_*" layers are the climate-change projection (uplift
  // applied) — the present-day-vs-future story underwriters care about. Only
  // Medium likelihood is published for the future scenario. Same endpoint/CRS/
  // scale-gating as present-day SEPA. Names verified via GetCapabilities Jul 2026.
  {
    key: "sepa-flood-river-future",
    group: "Flood (Scotland)",
    label: "SEPA River Flood — Medium (climate change)",
    coverage: "Scotland",
    url: "https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer",
    layers: "Future_Flood_Maps_River_Medium_Likelihood63924",
    crs: "4326",
    oversample: 3,
    attribution: "© SEPA — OGL v3.0",
  },
  {
    key: "sepa-flood-surface-future",
    group: "Flood (Scotland)",
    label: "SEPA Surface Water Flood — Medium (climate change)",
    coverage: "Scotland",
    url: "https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer",
    layers: "Future_Surface_Water_and_Small_Watercourses_Medium_Likelihood58784",
    crs: "4326",
    oversample: 3,
    attribution: "© SEPA — OGL v3.0",
  },
  {
    key: "sepa-flood-coastal-future",
    group: "Flood (Scotland)",
    label: "SEPA Coastal Flood — Medium (climate change)",
    coverage: "Scotland",
    url: "https://map.sepa.org.uk/server/services/Open/Flood_Maps/MapServer/WMSServer",
    layers: "Future_Flood_Maps_Coastal_Medium_Likelihood10441",
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
  // ponytail: EA NaFRA2 surface-water — no "_4band" variant exists for surface
  // water (unlike rivers/sea), so the renderable likelihood layer is bare
  // "rofsw". Same CRS/oversample as the river layer above. Verified Jul 2026.
  {
    key: "ea-flood-rofsw",
    group: "Flood (England)",
    label: "EA Risk of Flooding from Surface Water",
    coverage: "England",
    url: "https://environment.data.gov.uk/spatialdata/nafra2-risk-of-flooding-from-surface-water/wms",
    layers: "rofsw",
    crs: "3857",
    oversample: 4,
    attribution: "© Environment Agency — OGL v3.0",
  },
  // ponytail: EA climate-change scenario = the "cc01" suffix (upper-end epsilon
  // uplift). River keeps its 4band; surface water is bare "rofsw_cc01".
  {
    key: "ea-flood-rofrs-cc",
    group: "Flood (England)",
    label: "EA Rivers & Sea — climate change",
    coverage: "England",
    url: "https://environment.data.gov.uk/spatialdata/nafra2-risk-of-flooding-from-rivers-and-sea-climate-change/wms",
    layers: "rofrs_cc01_4band",
    crs: "3857",
    oversample: 4,
    attribution: "© Environment Agency — OGL v3.0",
  },
  {
    key: "ea-flood-rofsw-cc",
    group: "Flood (England)",
    label: "EA Surface Water — climate change",
    coverage: "England",
    url: "https://environment.data.gov.uk/spatialdata/nafra2-risk-of-flooding-from-surface-water-climate-change/wms",
    layers: "rofsw_cc01",
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
  // ponytail: NRW surface-water FRAW — same national-overview scale-gating as
  // the rivers/sea layer above, so no oversample. NRW publishes NO climate-
  // change flood WMS (checked GetCapabilities Jul 2026) — hence Wales has
  // present-day only, unlike Scotland/England.
  {
    key: "nrw-fraw-surface",
    group: "Flood (Wales)",
    label: "NRW Flood Risk — Surface Water (national view)",
    coverage: "Wales",
    url: "https://datamap.gov.wales/geoserver/inspire-nrw/wms",
    layers: "inspire-nrw:NRW_FLOOD_RISK_FROM_SURFACE_WATER_SMALL_WATERCOURSES",
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
