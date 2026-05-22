import React, { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const DEFAULT_CENTER = [54.5, -3];
const DEFAULT_ZOOM = 5;
const CLUSTER_ZOOM = 13;
const BLOCK_ZOOM = 18;
const FOCUSED_ZOOM = 19;
const CONTEXT_BLOCK_ZOOM = 16.5;
const CONTEXT_BLOCK_FADE_START_ZOOM = 18;
const CONTEXT_BLOCK_HIDE_ZOOM = 18.25;
const BUILDINGS_URL = "/buildings_cathcart.geojson";

const UK_LAT_BOUNDS = { min: 49.0, max: 61.5 };
const UK_LON_BOUNDS = { min: -8.8, max: 2.8 };

const PROPERTY_TYPE_COLORS = {
  flats: "#8b5cf6",
  houses: "#22c55e",
  commercial: "#f59e0b",
  mixed: "#3b82f6",
  other: "#64748b",
};

const fmtMoney = (n) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  return `£${x.toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;
};

const toNumberOrNull = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const isWithinUkBounds = (lat, lon) => {
  const safeLat = Number(lat);
  const safeLon = Number(lon);
  return (
    Number.isFinite(safeLat) &&
    Number.isFinite(safeLon) &&
    safeLat >= UK_LAT_BOUNDS.min &&
    safeLat <= UK_LAT_BOUNDS.max &&
    safeLon >= UK_LON_BOUNDS.min &&
    safeLon <= UK_LON_BOUNDS.max
  );
};

const normaliseLatLon = (lat, lon) => {
  const safeLat = Number(lat);
  const safeLon = Number(lon);
  if (
    !Number.isFinite(safeLat) ||
    !Number.isFinite(safeLon) ||
    safeLat === 0 ||
    safeLon === 0 ||
    !isWithinUkBounds(safeLat, safeLon)
  ) {
    return null;
  }
  return [safeLat, safeLon];
};

const readinessBandFromScore = (score) => {
  const s = Number(score) || 0;
  if (s >= 80) return "Green";
  if (s >= 50) return "Amber";
  return "Red";
};

const readinessColor = (bandOrScore) => {
  const b = String(bandOrScore ?? "").toLowerCase();
  if (b.includes("green")) return "#22c55e";
  if (b.includes("amber") || b.includes("yellow")) return "#f59e0b";
  if (b.includes("red")) return "#ef4444";

  const numeric = Number(bandOrScore);
  if (Number.isFinite(numeric)) return readinessColor(readinessBandFromScore(numeric));
  return "#64748b";
};

const getRiskBand = (entity) => {
  const fra = entity?.latest_fra ?? entity?.fire_documents?.fra ?? null;
  const fraew = entity?.latest_fraew ?? entity?.fire_documents?.fraew ?? null;
  const fraRisk = String(fra?.risk_level ?? fra?.rag_status ?? fra?.raw_rating ?? "").toLowerCase();
  const fraewRisk = String(fraew?.risk_level ?? fraew?.rag_status ?? fraew?.raw_rating ?? "").toLowerCase();
  const combined = `${fraRisk} ${fraewRisk}`;

  if (
    combined.includes("red") ||
    combined.includes("high") ||
    combined.includes("not acceptable") ||
    combined.includes("intolerable")
  ) return "Red";

  if (
    combined.includes("amber") ||
    combined.includes("medium") ||
    combined.includes("moderate") ||
    combined.includes("tolerable")
  ) return "Amber";

  if (
    combined.includes("green") ||
    combined.includes("low") ||
    combined.includes("acceptable") ||
    combined.includes("broadly acceptable")
  ) return "Green";

  return null;
};

const riskColor = (entity) => {
  const band = getRiskBand(entity);
  if (band === "Red") return "#ef4444";
  if (band === "Amber") return "#f59e0b";
  if (band === "Green") return "#22c55e";
  return "#64748b";
};

const sameProperty = (a, b) => {
  if (!a || !b) return false;
  return (
    (a.id && b.id && String(a.id) === String(b.id)) ||
    (a.property_id && b.property_id && String(a.property_id) === String(b.property_id)) ||
    (a.property_reference && b.property_reference && String(a.property_reference) === String(b.property_reference)) ||
    (a.uprn && b.uprn && String(a.uprn) === String(b.uprn))
  );
};

const sameBlock = (a, b) => {
  if (!a || !b) return false;
  return (
    (a.id && b.id && String(a.id) === String(b.id)) ||
    (a.block_id && b.block_id && String(a.block_id) === String(b.block_id)) ||
    (a.label && b.label && String(a.label) === String(b.label)) ||
    (a.name && b.name && String(a.name) === String(b.name)) ||
    (a.parent_uprn && b.parent_uprn && String(a.parent_uprn) === String(b.parent_uprn))
  );
};

const getPropertyLatLon = (row) => {
  const directLat =
    toNumberOrNull(row?.latitude) ??
    toNumberOrNull(row?.lat) ??
    toNumberOrNull(row?.location?.latitude) ??
    toNumberOrNull(row?.__lat);

  const directLon =
    toNumberOrNull(row?.longitude) ??
    toNumberOrNull(row?.lon) ??
    toNumberOrNull(row?.lng) ??
    toNumberOrNull(row?.location?.longitude) ??
    toNumberOrNull(row?.__lon);

  return normaliseLatLon(directLat, directLon);
};

const getBlockLatLon = (block) => {
  const directLat =
    toNumberOrNull(block?.lat) ??
    toNumberOrNull(block?.latitude) ??
    toNumberOrNull(block?.centroid_lat) ??
    toNumberOrNull(block?.center_lat) ??
    toNumberOrNull(block?.centre_lat) ??
    toNumberOrNull(block?.__lat);

  const directLon =
    toNumberOrNull(block?.lon) ??
    toNumberOrNull(block?.longitude) ??
    toNumberOrNull(block?.lng) ??
    toNumberOrNull(block?.centroid_lon) ??
    toNumberOrNull(block?.centroid_lng) ??
    toNumberOrNull(block?.center_lon) ??
    toNumberOrNull(block?.centre_lon) ??
    toNumberOrNull(block?.__lon);

  return normaliseLatLon(directLat, directLon);
};

const getPropertyReadiness = (row) =>
  toNumberOrNull(row?.readiness_score) ??
  toNumberOrNull(row?.readinessScore) ??
  toNumberOrNull(row?.score) ??
  0;

const getPropertyBand = (row) =>
  row?.readiness_band ?? row?.readinessBand ?? readinessBandFromScore(getPropertyReadiness(row));

const getPropertyId = (row, idx) =>
  row?.id ?? row?.property_id ?? row?.propertyId ?? row?.property_reference ?? row?.uprn ?? `property-${idx + 1}`;

const getPropertyLabel = (row, idx) =>
  row?.address_line_1 ?? row?.address1 ?? row?.address ?? row?.property_reference ?? row?.block_reference ?? row?.uprn ?? `Property ${idx + 1}`;

const getPropertyValue = (row) =>
  toNumberOrNull(row?.sum_insured) ??
  toNumberOrNull(row?.sumInsured) ??
  toNumberOrNull(row?.total_sum_insured) ??
  toNumberOrNull(row?.tiv) ??
  0;

const getBlockId = (block, idx) =>
  block?.id ?? block?.block_id ?? block?.parent_uprn ?? block?.name ?? block?.label ?? `block-${idx + 1}`;

const getBlockName = (block, idx) =>
  block?.label ?? block?.name ?? block?.block_reference ?? block?.parent_uprn ?? `Block ${idx + 1}`;

const getBlockUnits = (block) =>
  toNumberOrNull(block?.count) ??
  toNumberOrNull(block?.unit_count) ??
  toNumberOrNull(block?.units) ??
  toNumberOrNull(block?.property_count) ??
  0;

const getBlockValue = (block) =>
  toNumberOrNull(block?.totalValue) ??
  toNumberOrNull(block?.total_sum_insured) ??
  toNumberOrNull(block?.total_si) ??
  toNumberOrNull(block?.sum_insured) ??
  0;

const getBlockStoreys = (block) =>
  toNumberOrNull(block?.maxHeight) ??
  toNumberOrNull(block?.max_storeys) ??
  toNumberOrNull(block?.storeys) ??
  null;

const getBlockPropertyCount = (block) =>
  Array.isArray(block?.properties) ? block.properties.length : getBlockUnits(block);

const inferPropertyCategory = (row) => {
  const propertyType = String(row?.property_type ?? row?.propertyType ?? row?.type ?? "").toLowerCase();
  const builtForm = String(row?.built_form ?? row?.builtForm ?? "").toLowerCase();
  const occupancy = String(row?.occupancy_type ?? row?.occupancyType ?? row?.occupancy ?? "").toLowerCase();
  const address = String(row?.address_line_1 ?? row?.address1 ?? row?.address ?? row?.property_reference ?? "").toLowerCase();
  const combined = `${propertyType} ${builtForm} ${occupancy} ${address}`;

  if (combined.includes("flat") || combined.includes("apartment") || combined.includes("maisonette")) return "flats";
  if (combined.includes("house") || combined.includes("bungalow") || combined.includes("terrace") || combined.includes("semi") || combined.includes("detached")) return "houses";
  if (combined.includes("retail") || combined.includes("shop") || combined.includes("office") || combined.includes("commercial") || combined.includes("industrial")) return "commercial";
  if (combined.includes("mixed")) return "mixed";
  return "other";
};

const getPropertyCategoryLabel = (row) => {
  const category = inferPropertyCategory(row);
  if (category === "flats") return "Flats";
  if (category === "houses") return "Houses";
  if (category === "commercial") return "Commercial";
  if (category === "mixed") return "Mixed use";
  return "Other";
};

const getPropertyDisplayColor = (row, isSelected) => {
  if (isSelected) return "#1d4ed8";
  return PROPERTY_TYPE_COLORS[inferPropertyCategory(row)] || PROPERTY_TYPE_COLORS.other;
};

const getBlockCircleSize = (units, zoom, isSelected) => {
  const safeUnits = Math.max(1, Number(units) || 1);
  if (zoom <= 7) return isSelected ? 54 : 44;
  if (zoom <= 9) return Math.min(isSelected ? 64 : 58, 34 + Math.sqrt(safeUnits) * 5);
  if (zoom <= 11) return Math.min(isSelected ? 72 : 64, 38 + Math.sqrt(safeUnits) * 6);
  return Math.min(isSelected ? 78 : 70, 42 + Math.sqrt(safeUnits) * 6.5);
};

const formatCountLabel = (count) => {
  const safe = Number(count) || 0;
  if (safe >= 1000) {
    const compact = safe / 1000;
    return Number.isInteger(compact) ? `${compact}k` : `${compact.toFixed(1)}k`;
  }
  return String(safe);
};

const createBlockCountIcon = (point, zoom, isSelected, opacity = 1, scale = 1) => {
  const ringColor = isSelected ? "#1d4ed8" : riskColor(point.raw);
  const size = Math.max(30, getBlockCircleSize(point.units, zoom, isSelected) * scale);
  const fontSize = size >= 68 ? 15 : size >= 56 ? 14 : 13;

  return L.divIcon({
    className: "portfolio-block-count-icon",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `
      <div style="
        width:${size}px;
        height:${size}px;
        border-radius:999px;
        background:rgba(255,255,255,0.94);
        border:3px solid ${ringColor};
        box-shadow:0 10px 24px rgba(15,23,42,0.14);
        display:flex;
        align-items:center;
        justify-content:center;
        font-weight:800;
        font-size:${fontSize}px;
        color:#0f172a;
        backdrop-filter:blur(8px);
        opacity:${opacity};
        transform:scale(${scale});
        transform-origin:center;
        transition:opacity 80ms linear, transform 80ms linear;
      ">${formatCountLabel(point.units)}</div>
    `,
  });
};

const getContextBlockVisibility = (zoom) => {
  if (zoom >= CONTEXT_BLOCK_HIDE_ZOOM) return { visible: false, opacity: 0, scale: 0.72 };
  if (zoom <= CONTEXT_BLOCK_ZOOM) return { visible: true, opacity: 0.92, scale: 1 };

  const fadeRange = CONTEXT_BLOCK_FADE_START_ZOOM - CONTEXT_BLOCK_ZOOM;
  const progress = Math.max(
    0,
    Math.min(1, (CONTEXT_BLOCK_FADE_START_ZOOM - zoom) / fadeRange)
  );

  return {
    visible: progress > 0.02,
    opacity: Math.max(0.18, progress * 0.9),
    scale: 0.72 + progress * 0.28,
  };
};

const getPropertyDotSize = (point, isSelected) => {
  const base = Math.max(10, Math.min(22, 10 + Math.sqrt(Math.max(Number(point.sumInsured) || 0, 1)) / 900));
  return isSelected ? base + 4 : base;
};

const createPropertyDotIcon = (point, isSelected) => {
  const size = getPropertyDotSize(point, isSelected);
  const fill = getPropertyDisplayColor(point.raw, isSelected);

  return L.divIcon({
    className: "portfolio-property-dot-wrap",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `
      <div style="
        width:${size}px;
        height:${size}px;
        border-radius:999px;
        background:${fill};
        border:2px solid white;
        box-shadow:${
          isSelected
            ? "0 0 0 5px rgba(29,78,216,0.18), 0 10px 22px rgba(29,78,216,0.22)"
            : "0 0 0 2px rgba(15,23,42,0.08), 0 6px 12px rgba(15,23,42,0.10)"
        };
      "></div>
    `,
  });
};

const getPropertyPopupHtml = (point) => {
  const risk = getRiskBand(point.raw);
  return `
    <div style="min-width:220px;">
      <div style="font-weight:700; margin-bottom:6px;">${point.label}</div>
      <div>Type: ${getPropertyCategoryLabel(point.raw)}</div>
      <div>Sum insured: ${fmtMoney(point.sumInsured)}</div>
      <div>Readiness: ${point.readinessScore ?? "—"} (${point.readinessBand})</div>
      <div>Fire risk: ${risk || "—"}</div>
      <div>Lat: ${point.lat.toFixed(5)}</div>
      <div>Lon: ${point.lon.toFixed(5)}</div>
    </div>
  `;
};

const getBlockPopupHtml = (point) => `
  <div style="min-width:240px;">
    <div style="font-weight:700; margin-bottom:6px;">${point.name}</div>
    <div>Properties: ${getBlockPropertyCount(point.raw) || 0}</div>
    <div>Total insured value: ${fmtMoney(point.totalValue)}</div>
    <div>Height: ${Number.isFinite(point.storeys) && point.storeys > 0 ? `${point.storeys.toFixed(1)} m` : "—"}</div>
    <div>Readiness: ${point.readinessScore ?? "—"}${point.readinessBand ? ` (${point.readinessBand})` : ""}</div>
    <div>Fire risk: ${getRiskBand(point.raw) || "—"}</div>
  </div>
`;

const flattenCoords = (coords, out = []) => {
  if (!Array.isArray(coords)) return out;
  if (coords.length >= 2 && typeof coords[0] === "number" && typeof coords[1] === "number") {
    out.push([coords[1], coords[0]]);
    return out;
  }
  coords.forEach((child) => flattenCoords(child, out));
  return out;
};

const getFeatureLatLngBounds = (feature) => {
  const latLngs = flattenCoords(feature?.geometry?.coordinates || []);
  if (!latLngs.length) return null;
  try {
    const bounds = L.latLngBounds(latLngs);
    return bounds.isValid() ? bounds : null;
  } catch {
    return null;
  }
};

const getFeatureCenter = (feature) => {
  const bounds = getFeatureLatLngBounds(feature);
  if (!bounds) return null;
  const center = bounds.getCenter();
  return { lat: center.lat, lon: center.lng };
};

const getFeatureIdentifier = (feature, fallbackIndex = 0) =>
  feature?.id ??
  feature?.properties?.id ??
  feature?.properties?.osm_id ??
  feature?.properties?.osm_way_id ??
  feature?.properties?.way_id ??
  feature?.properties?.objectid ??
  feature?.properties?.osm_uid ??
  feature?.properties?.["@id"] ??
  `feature-${fallbackIndex}`;

const distanceBetweenLatLon = (a, b) => {
  if (!a || !b) return Infinity;
  const latA = Number(a.lat ?? a[0]);
  const lonA = Number(a.lon ?? a.lng ?? a[1]);
  const latB = Number(b.lat ?? b[0]);
  const lonB = Number(b.lon ?? b.lng ?? b[1]);
  return Math.hypot(latA - latB, lonA - lonB);
};

const getSelectedBlockPropertyPoints = (selectedBlock, propertyPoints) => {
  if (!selectedBlock) return [];

  if (Array.isArray(selectedBlock?.properties)) {
    const explicit = propertyPoints.filter((point) =>
      selectedBlock.properties.some((property) => sameProperty(property, point.raw))
    );
    if (explicit.length) return explicit;
  }

  const blockLatLon = getBlockLatLon(selectedBlock);
  if (!blockLatLon) return [];
  return propertyPoints.filter((point) => distanceBetweenLatLon(point, blockLatLon) <= 0.0025);
};

const getSelectedBlockBounds = (selectedBlock, propertyPoints) => {
  if (!selectedBlock) return null;

  const explicitPoints = getSelectedBlockPropertyPoints(selectedBlock, propertyPoints);
  if (explicitPoints.length) {
    return L.latLngBounds(explicitPoints.map((p) => [p.lat, p.lon])).pad(0.12);
  }

  const blockLatLon = getBlockLatLon(selectedBlock);
  if (blockLatLon) return L.latLngBounds([blockLatLon, blockLatLon]).pad(0.006);
  return null;
};

const getMainClusterPoints = (points) => {
  if (!points.length) return [];
  if (points.length === 1) return points;

  const candidates = points.map((point) => {
    const neighbours = points.filter((other) => distanceBetweenLatLon(point, other) <= 0.08);
    const unitWeight = neighbours.reduce((sum, item) => sum + Math.max(1, Number(item.units) || 1), 0);
    return { neighbours, score: neighbours.length * 1000 + unitWeight };
  });

  const best = candidates.sort((a, b) => b.score - a.score)[0];
  const core = best?.neighbours?.length ? best.neighbours : points;

  const center = core.reduce(
    (acc, point) => ({ lat: acc.lat + point.lat / core.length, lon: acc.lon + point.lon / core.length }),
    { lat: 0, lon: 0 }
  );

  const expanded = points.filter((point) => distanceBetweenLatLon(point, center) <= 0.16);
  return expanded.length >= core.length ? expanded : core;
};

const getFitBoundsForMode = ({ activeMode, blockPoints, propertyPoints, selectedBlock, selectedProperty }) => {
  if (activeMode === "properties") {
    if (selectedProperty) {
      const latLon = getPropertyLatLon(selectedProperty);
      return latLon ? [latLon] : propertyPoints.map((point) => [point.lat, point.lon]);
    }

    const selectedBlockBounds = getSelectedBlockBounds(selectedBlock, propertyPoints);
    if (selectedBlockBounds?.isValid()) {
      return [selectedBlockBounds.getSouthWest(), selectedBlockBounds.getNorthEast()].map((p) => [p.lat, p.lng]);
    }

    return propertyPoints.map((point) => [point.lat, point.lon]);
  }

  if (selectedBlock) {
    const latLon = getBlockLatLon(selectedBlock);
    return latLon ? [latLon] : [];
  }

  return getMainClusterPoints(blockPoints).map((point) => [point.lat, point.lon]);
};

const buildPropertyFeatureAssignments = ({ sourceFeatures, targetPropertyPoints, selectedBounds }) => {
  if (!sourceFeatures?.length || !targetPropertyPoints.length || !selectedBounds) {
    return { features: [], assignments: new Map(), unmatchedPoints: targetPropertyPoints };
  }

  const expandedBounds = selectedBounds.pad(0.7);
  const nearbyFeatures = sourceFeatures.filter((feature) => {
    const bounds = getFeatureLatLngBounds(feature);
    return bounds ? expandedBounds.intersects(bounds) : false;
  });

  const usedFeatureIds = new Set();
  const assignments = new Map();
  const selectedFeatures = [];
  const unmatchedPoints = [];

  targetPropertyPoints.forEach((propertyPoint) => {
    let bestFeature = null;
    let bestIndex = -1;
    let bestDistance = Infinity;

    nearbyFeatures.forEach((feature, index) => {
      const featureId = getFeatureIdentifier(feature, index);
      if (usedFeatureIds.has(featureId)) return;

      const center = getFeatureCenter(feature);
      if (!center) return;

      const distance = distanceBetweenLatLon(propertyPoint, center);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestFeature = feature;
        bestIndex = index;
      }
    });

    if (bestFeature && bestDistance <= 0.0045) {
      const featureId = getFeatureIdentifier(bestFeature, bestIndex);
      usedFeatureIds.add(featureId);
      assignments.set(featureId, propertyPoint);
      selectedFeatures.push(bestFeature);
    } else {
      unmatchedPoints.push(propertyPoint);
    }
  });

  return { features: selectedFeatures, assignments, unmatchedPoints };
};

export default function PortfolioMap({
  properties = [],
  blocks = [],
  selectedProperty = null,
  selectedBlock = null,
  onSelectProperty,
  onSelectBlock,
  viewMode = "blocks",
}) {
  const mapDivRef = useRef(null);
  const mapRef = useRef(null);
  const pointLayerRef = useRef(null);
  const buildingsLayerRef = useRef(null);
  const overviewBlockLayerRef = useRef(null);
  const selectedMarkerRef = useRef(null);
  const lastFitSignatureRef = useRef("");
  const lastSelectionSignatureRef = useRef("");
  const buildingsGeojsonCacheRef = useRef(null);
  const buildingsFetchPromiseRef = useRef(null);

  const propertyPoints = useMemo(() => {
    return (properties || [])
      .map((property, idx) => {
        const latLon = getPropertyLatLon(property);
        if (!latLon) return null;

        const readinessScore = getPropertyReadiness(property);
        const readinessBand = getPropertyBand(property);

        return {
          id: getPropertyId(property, idx),
          label: getPropertyLabel(property, idx),
          lat: latLon[0],
          lon: latLon[1],
          readinessScore,
          readinessBand,
          color: readinessColor(readinessBand),
          propertyCategory: inferPropertyCategory(property),
          propertyCategoryLabel: getPropertyCategoryLabel(property),
          sumInsured: getPropertyValue(property),
          raw: { ...property, __lat: latLon[0], __lon: latLon[1] },
        };
      })
      .filter(Boolean);
  }, [properties]);

  const blockPoints = useMemo(() => {
    return (blocks || [])
      .map((block, idx) => {
        const latLon = getBlockLatLon(block);
        if (!latLon) return null;

        const units = getBlockUnits(block);
        const totalValue = getBlockValue(block);
        const readinessScore = toNumberOrNull(block?.avgReadiness) ?? toNumberOrNull(block?.readiness_score) ?? null;
        const readinessBand = block?.readiness_band ?? (Number.isFinite(readinessScore) ? readinessBandFromScore(readinessScore) : "Amber");

        return {
          id: getBlockId(block, idx),
          name: getBlockName(block, idx),
          lat: latLon[0],
          lon: latLon[1],
          units,
          totalValue,
          storeys: getBlockStoreys(block),
          readinessScore,
          readinessBand,
          color: readinessColor(readinessBand),
          raw: { ...block, __lat: latLon[0], __lon: latLon[1] },
        };
      })
      .filter(Boolean);
  }, [blocks]);

  const activeMode = viewMode === "properties" ? "properties" : "blocks";
  const visiblePoints = activeMode === "blocks" ? blockPoints : propertyPoints;

  useLayoutEffect(() => {
    if (!mapDivRef.current || mapRef.current) return;

    const map = L.map(mapDivRef.current, {
      scrollWheelZoom: false,
      zoomControl: true,
      attributionControl: false,
    }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd",
      maxZoom: 20,
      crossOrigin: "anonymous",
      keepBuffer: 4,
      attribution: "&copy; OpenStreetMap &copy; CARTO",
    }).addTo(map);

    mapRef.current = map;
    buildingsLayerRef.current = L.layerGroup().addTo(map);
    overviewBlockLayerRef.current = L.layerGroup().addTo(map);
    pointLayerRef.current = L.layerGroup().addTo(map);

    // Staggered invalidateSize to handle grid/flex layout settling
    setTimeout(() => map.invalidateSize(), 0);
    setTimeout(() => map.invalidateSize(), 120);
    setTimeout(() => map.invalidateSize(), 400);
  }, []);

  useEffect(() => {
    const onResize = () => mapRef.current?.invalidateSize();
    window.addEventListener("resize", onResize);

    // ResizeObserver catches layout changes (grid settling, sidebar toggle, etc.)
    let ro = null;
    if (typeof ResizeObserver !== "undefined" && mapDivRef.current) {
      ro = new ResizeObserver(() => {
        mapRef.current?.invalidateSize();
      });
      ro.observe(mapDivRef.current);
    }

    return () => {
      window.removeEventListener("resize", onResize);
      ro?.disconnect();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const pointLayer = pointLayerRef.current;
    const buildingsLayer = buildingsLayerRef.current;
    const overviewBlockLayer = overviewBlockLayerRef.current;
    if (!map || !pointLayer || !buildingsLayer || !overviewBlockLayer) return;

    selectedMarkerRef.current = null;
    pointLayer.clearLayers();
    overviewBlockLayer.clearLayers();

    if (!visiblePoints.length) {
      lastFitSignatureRef.current = "";
      buildingsLayer.clearLayers();
      map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
      setTimeout(() => map.invalidateSize(), 80);
      return;
    }

    const currentZoom = map.getZoom();

    if (activeMode === "blocks") {
      buildingsLayer.clearLayers();
      overviewBlockLayer.clearLayers();

      blockPoints.forEach((point) => {
        const isSelected = sameBlock(selectedBlock, point.raw);
        const marker = L.marker([point.lat, point.lon], {
          icon: createBlockCountIcon(point, currentZoom, isSelected),
          keyboard: false,
        });

        marker.on("click", () => {
          onSelectBlock?.(point.raw);
          onSelectProperty?.(null);
        });

        marker.bindTooltip(
          `${point.name} · ${getBlockPropertyCount(point.raw) || 0} properties · ${fmtMoney(point.totalValue)}`,
          { direction: "top", sticky: true, opacity: 0.95 }
        );

        marker.bindPopup(getBlockPopupHtml(point));
        marker.addTo(pointLayer);
        if (isSelected) selectedMarkerRef.current = marker;
      });
    } else {
      propertyPoints.forEach((point) => {
        const isSelected = sameProperty(selectedProperty, point.raw);
        const marker = L.marker([point.lat, point.lon], {
          icon: createPropertyDotIcon(point, isSelected),
          keyboard: false,
          zIndexOffset: isSelected ? 1000 : 500,
        });

        marker.on("click", () => onSelectProperty?.(point.raw));
        marker.bindTooltip(`${point.label} · ${point.propertyCategoryLabel}`, {
          direction: "top",
          sticky: true,
          opacity: 0.95,
        });
        marker.bindPopup(getPropertyPopupHtml(point));
        marker.addTo(pointLayer);
        if (isSelected) selectedMarkerRef.current = marker;
      });
    }

    const fitBounds = getFitBoundsForMode({
      activeMode,
      blockPoints,
      propertyPoints,
      selectedBlock,
      selectedProperty,
    });

    if (fitBounds.length) {
      const signature = JSON.stringify([
        activeMode,
        selectedBlock?.id ?? selectedBlock?.block_id ?? selectedBlock?.label ?? null,
        selectedProperty?.id ?? selectedProperty?.property_id ?? selectedProperty?.property_reference ?? selectedProperty?.uprn ?? null,
        fitBounds,
      ]);

      if (lastFitSignatureRef.current !== signature) {
        const leafletBounds = L.latLngBounds(fitBounds);
        if (leafletBounds.isValid()) {
          if (activeMode === "properties") {
            map.flyToBounds(leafletBounds.pad(selectedProperty ? 0.08 : 0.16), {
              duration: 0.55,
              maxZoom: selectedProperty ? FOCUSED_ZOOM : BLOCK_ZOOM,
            });
          } else if (selectedBlock) {
            map.flyToBounds(leafletBounds.pad(0.02), {
              duration: 0.45,
              maxZoom: BLOCK_ZOOM,
            });
          } else {
            map.fitBounds(leafletBounds.pad(0.24), {
              animate: false,
              maxZoom: CLUSTER_ZOOM,
            });
          }
          lastFitSignatureRef.current = signature;
        }
      }
    }

    map.invalidateSize();
    setTimeout(() => map.invalidateSize(), 80);
    setTimeout(() => map.invalidateSize(), 300);
  }, [
    activeMode,
    blockPoints,
    onSelectBlock,
    onSelectProperty,
    propertyPoints,
    selectedBlock,
    selectedProperty,
    visiblePoints.length,
  ]);

  useEffect(() => {
    const map = mapRef.current;
    const overviewBlockLayer = overviewBlockLayerRef.current;
    if (!map || !overviewBlockLayer) return;

    const renderContextBlocks = () => {
      overviewBlockLayer.clearLayers();

      if (activeMode !== "properties" || !selectedBlock || !blockPoints.length) return;

      const zoom = map.getZoom();
      const visibility = getContextBlockVisibility(zoom);
      if (!visibility.visible) return;

      blockPoints.forEach((point) => {
        const isSelected = sameBlock(selectedBlock, point.raw);
        const marker = L.marker([point.lat, point.lon], {
          icon: createBlockCountIcon(
            point,
            zoom,
            isSelected,
            isSelected ? Math.min(1, visibility.opacity + 0.08) : visibility.opacity,
            isSelected ? Math.min(1.08, visibility.scale + 0.04) : visibility.scale
          ),
          keyboard: false,
          zIndexOffset: isSelected ? 760 : 260,
        });

        marker.on("click", () => {
          onSelectBlock?.(point.raw);
          onSelectProperty?.(null);
          lastFitSignatureRef.current = "";
        });

        marker.bindTooltip(
          `${point.name} · ${getBlockPropertyCount(point.raw) || 0} properties · ${fmtMoney(point.totalValue)}`,
          { direction: "top", sticky: true, opacity: 0.95 }
        );

        marker.addTo(overviewBlockLayer);
      });
    };

    renderContextBlocks();
    map.on("zoom zoomend moveend", renderContextBlocks);

    return () => {
      map.off("zoom zoomend moveend", renderContextBlocks);
      overviewBlockLayer.clearLayers();
    };
  }, [activeMode, blockPoints, onSelectBlock, onSelectProperty, selectedBlock]);

  useEffect(() => {
    const map = mapRef.current;
    const buildingsLayer = buildingsLayerRef.current;
    if (!map || !buildingsLayer) return;

    const shouldShowBuildings = activeMode === "properties" && selectedBlock && propertyPoints.length > 0;

    if (!shouldShowBuildings) {
      buildingsLayer.clearLayers();
      return;
    }

    let isCancelled = false;

    const renderBuildings = async () => {
      try {
        if (!buildingsGeojsonCacheRef.current) {
          if (!buildingsFetchPromiseRef.current) {
            buildingsFetchPromiseRef.current = fetch(BUILDINGS_URL).then((res) => {
              if (!res.ok) throw new Error(`Failed to load buildings GeoJSON: ${res.status}`);
              return res.json();
            });
          }
          buildingsGeojsonCacheRef.current = await buildingsFetchPromiseRef.current;
        }

        if (isCancelled) return;

        const source = buildingsGeojsonCacheRef.current;
        const targetPropertyPoints = getSelectedBlockPropertyPoints(selectedBlock, propertyPoints);
        const selectedBounds = getSelectedBlockBounds(selectedBlock, propertyPoints);
        buildingsLayer.clearLayers();

        if (!source?.features?.length || !selectedBounds || !targetPropertyPoints.length) return;

        const { features, assignments, unmatchedPoints } = buildPropertyFeatureAssignments({
          sourceFeatures: source.features,
          targetPropertyPoints,
          selectedBounds,
        });

        if (features.length) {
          const geoJsonLayer = L.geoJSON(
            { type: "FeatureCollection", features },
            {
              style: (feature) => {
                const featureId = getFeatureIdentifier(feature);
                const assignedPoint = assignments.get(featureId) || null;
                const isSelected = assignedPoint && selectedProperty ? sameProperty(assignedPoint.raw, selectedProperty) : false;
                const fillColor = assignedPoint
                  ? getPropertyDisplayColor(assignedPoint.raw, isSelected)
                  : PROPERTY_TYPE_COLORS.other;

                return {
                  color: isSelected ? "#1d4ed8" : fillColor,
                  weight: isSelected ? 3 : 2,
                  fillColor,
                  fillOpacity: isSelected ? 0.68 : 0.42,
                  opacity: 0.95,
                };
              },
              onEachFeature: (feature, layer) => {
                const featureId = getFeatureIdentifier(feature);
                const assignedPoint = assignments.get(featureId) || null;
                if (!assignedPoint) return;

                layer.on({
                  click: () => onSelectProperty?.(assignedPoint.raw),
                  mouseover: () => {
                    layer.setStyle({ weight: 3, color: "#0f172a", fillOpacity: 0.72 });
                    layer.bringToFront();
                  },
                  mouseout: () => {
                    if (geoJsonLayer.resetStyle) geoJsonLayer.resetStyle(layer);
                  },
                });

                layer.bindTooltip(`${assignedPoint.label} · ${getPropertyCategoryLabel(assignedPoint.raw)}`, {
                  direction: "top",
                  sticky: true,
                  opacity: 0.95,
                });
              },
            }
          );

          geoJsonLayer.addTo(buildingsLayer);
        }

        // If OSM has no matching footprint for a property, show only a small dot.
        // This avoids fake square/grid polygons while still keeping every property visible.
        unmatchedPoints.forEach((point) => {
          const isSelected = selectedProperty ? sameProperty(point.raw, selectedProperty) : false;
          const circle = L.circleMarker([point.lat, point.lon], {
            radius: isSelected ? 7 : 5,
            color: isSelected ? "#1d4ed8" : getPropertyDisplayColor(point.raw, false),
            weight: isSelected ? 3 : 2,
            fillColor: getPropertyDisplayColor(point.raw, isSelected),
            fillOpacity: 0.8,
          });

          circle.on("click", () => onSelectProperty?.(point.raw));
          circle.bindTooltip(`${point.label} · ${getPropertyCategoryLabel(point.raw)}`, {
            direction: "top",
            sticky: true,
            opacity: 0.95,
          });
          circle.addTo(buildingsLayer);
        });
      } catch (error) {
        console.error("Buildings layer load failed:", error);
        buildingsLayer.clearLayers();
      }
    };

    renderBuildings();

    return () => {
      isCancelled = true;
    };
  }, [activeMode, onSelectProperty, propertyPoints, selectedBlock, selectedProperty]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (activeMode === "properties" && selectedProperty) {
      const latLon = getPropertyLatLon(selectedProperty);
      if (!latLon) return;

      const selectionSignature = `property:${
        selectedProperty.id ??
        selectedProperty.property_id ??
        selectedProperty.property_reference ??
        selectedProperty.uprn ??
        ""
      }`;

      if (lastSelectionSignatureRef.current !== selectionSignature) {
        lastSelectionSignatureRef.current = selectionSignature;
        map.flyTo(latLon, Math.max(map.getZoom(), FOCUSED_ZOOM), { duration: 0.45 });
      }

      setTimeout(() => selectedMarkerRef.current?.openPopup(), 320);
      return;
    }

    if (!selectedBlock && !selectedProperty) {
      lastSelectionSignatureRef.current = "";
    }
  }, [activeMode, selectedBlock, selectedProperty, propertyPoints]);

  return (
    <div
      ref={mapDivRef}
      className="portfolio-map-canvas"
      style={{
        height: 620,
        width: "100%",
        borderRadius: 22,
        overflow: "hidden",
        background: "#eef3f8",
        border: "1px solid rgba(15,23,42,0.08)",
      }}
    />
  );
}
