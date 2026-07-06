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
    // ponytail: SEPA is ArcGIS (not GeoServer) so LEGEND_OPTIONS font-scaling is
    // ignored — its GetLegendGraphic PNG bakes in tiny text. Each flood layer is
    // one colour + one sentence, so a static legendText/legendColor (like BGS
    // above) renders crisp at any size. Colours read off the server PNG, wording
    // is SEPA's own. Verified Jul 2026.
    legendText: "Each year this area has a 10% chance of flooding.",
    legendColor: "#005ce6",
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
    legendText: "Each year this area has a 0.5% chance of flooding.",
    legendColor: "#00c5ff",
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
    legendText: "Each year this area has a 10% chance of flooding.",
    legendColor: "#8400a8",
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
    legendText: "Each year this area has a 0.5% chance of flooding.",
    legendColor: "#c500ff",
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
    legendText: "Each year this area has a 10% chance of flooding.",
    legendColor: "#2b9e0f",
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
    legendText: "Each year this area has a 0.5% chance of flooding.",
    legendColor: "#4cc900",
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
    legendText: "By the 2080s, each year this area may have a 0.5% chance of flooding.",
    legendColor: "#33518f",
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
    legendText: "By the 2070s, each year this area may have a 0.5% chance of flooding.",
    legendColor: "#4c0073",
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
    legendText: "By the 2080s, each year this area may have a 0.5% chance of flooding.",
    legendColor: "#00734c",
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
    // ponytail: ArcGIS again (tiny baked-in legend). SIMD is a 5-class quintile
    // ramp, so it gets legendItems (swatch + label per class) instead of a single
    // legendColor. Colours read off the server PNG. Quintile 1 = 20% most deprived
    // datazones in Scotland, 5 = least. Verified Jul 2026.
    legendText: "Quintile of the 2020 ranking (datazones):",
    legendItems: [
      { color: "#0766ab", label: "1 — most deprived" },
      { color: "#42a1ca", label: "2" },
      { color: "#7ccec4", label: "3" },
      { color: "#bae3bc", label: "4" },
      { color: "#f1fae8", label: "5 — least deprived" },
    ],
    attribution: "© Scottish Government / SIMD — OGL v3.0",
  },
  // ponytail: Scotland has NO crime-rate WMS (checked maps.gov.scot
  // CrimeJusticeSafety = police-division boundaries only, PeopleSociety = SIMD
  // aggregate only — Jul 2026). But the SIMD2020 FeatureServer layer exposes a
  // per-datazone `crimerank` (1 = worst) — the SIMD crime domain, i.e. relative
  // crime rate. So this is NOT a WMS tile layer: type "arcgis" fetches datazone
  // polygons by viewport bbox (f=geojson, no key, OGL) and PortfolioMap renders
  // a client-side quintile choropleth. Gated to zoom ≥ 11 to stay under the
  // 1000-feature query cap. Reuses SIMD's blue→green ramp for on-brand
  // consistency (red choropleth would breach the graphic standard).
  {
    key: "simd-crime-2020",
    group: "Deprivation",
    label: "SIMD 2020 — Crime domain (relative crime rate)",
    coverage: "Scotland",
    type: "arcgis",
    url: "https://maps.gov.scot/server/rest/services/ScotGov/PeopleSociety/MapServer/7/query",
    field: "crimerank", // 1 = most deprived (highest crime) … 6976 = least
    rankMax: 6976, // SIMD2020 datazone count — quintile buckets = rankMax/5
    nameField: "dzname",
    rateField: "crimerate", // recorded SIMD crimes per 10,000 people
    rateUnit: "crimes per 10,000 people",
    minZoom: 11,
    legendText: "Recorded SIMD crimes.Quintile of the 2020 ranking:",
    legendItems: [
      { color: "#0766ab", label: "1 — highest crime" },
      { color: "#42a1ca", label: "2" },
      { color: "#7ccec4", label: "3" },
      { color: "#bae3bc", label: "4" },
      { color: "#f1fae8", label: "5 — lowest crime" },
    ],
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
  // ponytail: Wales crime = the WIMD Community Safety domain. Rendered as a WFS
  // choropleth (type "wfs") rather than the flat WMS tile, so it gets the same
  // matching legend + hover as Scotland/England. GeoServer ships a ready 1–5
  // `quintile` field (no rank-bucketing needed). Like England, it's rank-based:
  // NO per-area crime rate exists — only rank/decile/quintile.
  {
    key: "wimd-crime-2019",
    group: "Deprivation",
    label: "WIMD 2019 — Community Safety (crime domain)",
    coverage: "Wales",
    type: "wfs",
    url: "https://datamap.gov.wales/geoserver/inspire-wg/ows",
    typeName: "inspire-wg:wimd2019_community_safety",
    quintileField: "quintile", // 1 = worst community safety … 5 = best
    nameField: "lsoa_name_en",
    minZoom: 11,
    legendText: "WIMD 2019 community-safety domain by LSOA. Each quintile = 20% of Wales's 1,909 LSOAs, ranked:",
    legendItems: [
      { color: "#0766ab", label: "1 — least safe 20%" },
      { color: "#42a1ca", label: "2 — 20–40%" },
      { color: "#7ccec4", label: "3 — middle 20%" },
      { color: "#bae3bc", label: "4 — 60–80%" },
      { color: "#f1fae8", label: "5 — safest 20%" },
    ],
    attribution: "© Welsh Government / WIMD 2019 — OGL v3.0",
  },
  // ponytail: England IMD 2019 — now wired via the same type "arcgis" choropleth
  // path as Scotland (the FeatureServer that closes the old "no clean WMS" TODO).
  // One FeatureServer, two domains: overall (IMD_Rank) + crime (CriRank), both
  // 1 = most deprived / highest crime over 32,844 LSOAs. No API key, OGL.
  {
    key: "imd-overall-2019",
    group: "Deprivation",
    label: "IMD 2019 — Index of Multiple Deprivation (overall)",
    coverage: "England",
    type: "arcgis",
    url: "https://services-eu1.arcgis.com/EbKcOS6EXZroSyoi/arcgis/rest/services/Indices_of_Multiple_Deprivation_(IMD)_2019/FeatureServer/0/query",
    field: "IMD_Rank", // 1 = most deprived … 32844 = least
    rankMax: 32844, // England LSOA count — quintile buckets = rankMax/5
    nameField: "lsoa11nm",
    minZoom: 11,
    legendText: "IMD 2019 overall deprivation. Each quintile = 20% of England's 32,844 LSOAs, ranked:",
    legendItems: [
      { color: "#0766ab", label: "1 — most deprived 20%" },
      { color: "#42a1ca", label: "2 — 20–40%" },
      { color: "#7ccec4", label: "3 — middle 20%" },
      { color: "#bae3bc", label: "4 — 60–80%" },
      { color: "#f1fae8", label: "5 — least deprived 20%" },
    ],
    attribution: "© MHCLG / IoD2019 — OGL v3.0",
  },
  {
    key: "imd-crime-2019",
    group: "Deprivation",
    label: "IMD 2019 — Crime domain (relative crime rate)",
    coverage: "England",
    type: "arcgis",
    url: "https://services-eu1.arcgis.com/EbKcOS6EXZroSyoi/arcgis/rest/services/Indices_of_Multiple_Deprivation_(IMD)_2019/FeatureServer/0/query",
    field: "CriRank", // 1 = highest crime … 32844 = lowest
    rankMax: 32844,
    nameField: "lsoa11nm",
    minZoom: 11,
    legendText: "IMD 2019 crime domain — recorded-crime risk. Each quintile = 20% of England's 32,844 LSOAs, ranked:",
    legendItems: [
      { color: "#0766ab", label: "1 — highest-crime 20%" },
      { color: "#42a1ca", label: "2 — 20–40%" },
      { color: "#7ccec4", label: "3 — middle 20%" },
      { color: "#bae3bc", label: "4 — 60–80%" },
      { color: "#f1fae8", label: "5 — lowest-crime 20%" },
    ],
    attribution: "© MHCLG / IoD2019 — OGL v3.0",
  },
];
