// Pure helpers for PortfolioMap: formatting, bounds/coord normalisation, risk/readiness
// banding, data-extraction accessors, category inference, and geometry helpers.
import L from "leaflet";
import { UK_LAT_BOUNDS, UK_LON_BOUNDS, PROPERTY_TYPE_COLORS } from "../constants/map.js";

export const fmtMoney = (n) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  return `£${x.toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;
};

export const toNumberOrNull = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

export const isWithinUkBounds = (lat, lon) => {
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

export const normaliseLatLon = (lat, lon) => {
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

export const readinessBandFromScore = (score) => {
  const s = Number(score) || 0;
  if (s >= 80) return "Green";
  if (s >= 50) return "Amber";
  return "Red";
};

export const readinessColor = (bandOrScore) => {
  const b = String(bandOrScore ?? "").toLowerCase();
  if (b.includes("green")) return "#22c55e";
  if (b.includes("amber") || b.includes("yellow")) return "#f59e0b";
  if (b.includes("red")) return "#ef4444";

  const numeric = Number(bandOrScore);
  if (Number.isFinite(numeric)) return readinessColor(readinessBandFromScore(numeric));
  return "#64748b";
};

export const getRiskBand = (entity) => {
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

export const riskColor = (entity) => {
  const band = getRiskBand(entity);
  if (band === "Red") return "#ef4444";
  if (band === "Amber") return "#f59e0b";
  if (band === "Green") return "#22c55e";
  return "#64748b";
};

export const sameProperty = (a, b) => {
  if (!a || !b) return false;
  return (
    (a.id && b.id && String(a.id) === String(b.id)) ||
    (a.property_id && b.property_id && String(a.property_id) === String(b.property_id)) ||
    (a.property_reference && b.property_reference && String(a.property_reference) === String(b.property_reference)) ||
    (a.uprn && b.uprn && String(a.uprn) === String(b.uprn))
  );
};

export const sameBlock = (a, b) => {
  if (!a || !b) return false;
  return (
    (a.id && b.id && String(a.id) === String(b.id)) ||
    (a.block_id && b.block_id && String(a.block_id) === String(b.block_id)) ||
    (a.label && b.label && String(a.label) === String(b.label)) ||
    (a.name && b.name && String(a.name) === String(b.name)) ||
    (a.parent_uprn && b.parent_uprn && String(a.parent_uprn) === String(b.parent_uprn))
  );
};

export const getPropertyLatLon = (row) => {
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

export const getBlockLatLon = (block) => {
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

export const getPropertyReadiness = (row) =>
  toNumberOrNull(row?.readiness_score) ??
  toNumberOrNull(row?.readinessScore) ??
  toNumberOrNull(row?.score) ??
  0;

export const getPropertyBand = (row) =>
  row?.readiness_band ?? row?.readinessBand ?? readinessBandFromScore(getPropertyReadiness(row));

export const getPropertyId = (row, idx) =>
  row?.id ?? row?.property_id ?? row?.propertyId ?? row?.property_reference ?? row?.uprn ?? `property-${idx + 1}`;

export const getPropertyLabel = (row, idx) =>
  row?.address_line_1 ?? row?.address1 ?? row?.address ?? row?.property_reference ?? row?.block_reference ?? row?.uprn ?? `Property ${idx + 1}`;

export const getPropertyValue = (row) =>
  toNumberOrNull(row?.sum_insured) ??
  toNumberOrNull(row?.sumInsured) ??
  toNumberOrNull(row?.total_sum_insured) ??
  toNumberOrNull(row?.tiv) ??
  0;

export const getBlockId = (block, idx) =>
  block?.id ?? block?.block_id ?? block?.parent_uprn ?? block?.name ?? block?.label ?? `block-${idx + 1}`;

export const getBlockName = (block, idx) =>
  block?.label ?? block?.name ?? block?.block_reference ?? block?.parent_uprn ?? `Block ${idx + 1}`;

export const getBlockUnits = (block) =>
  toNumberOrNull(block?.count) ??
  toNumberOrNull(block?.unit_count) ??
  toNumberOrNull(block?.units) ??
  toNumberOrNull(block?.property_count) ??
  0;

export const getBlockValue = (block) =>
  toNumberOrNull(block?.totalValue) ??
  toNumberOrNull(block?.total_sum_insured) ??
  toNumberOrNull(block?.total_si) ??
  toNumberOrNull(block?.sum_insured) ??
  0;

export const getBlockStoreys = (block) =>
  toNumberOrNull(block?.maxHeight) ??
  toNumberOrNull(block?.max_storeys) ??
  toNumberOrNull(block?.storeys) ??
  null;

export const getBlockPropertyCount = (block) =>
  Array.isArray(block?.properties) ? block.properties.length : getBlockUnits(block);

export const inferPropertyCategory = (row) => {
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

export const getPropertyCategoryLabel = (row) => {
  const category = inferPropertyCategory(row);
  if (category === "flats") return "Flats";
  if (category === "houses") return "Houses";
  if (category === "commercial") return "Commercial";
  if (category === "mixed") return "Mixed use";
  return "Other";
};

export const getPropertyDisplayColor = (row, isSelected) => {
  if (isSelected) return "#1d4ed8";
  return PROPERTY_TYPE_COLORS[inferPropertyCategory(row)] || PROPERTY_TYPE_COLORS.other;
};

export const flattenCoords = (coords, out = []) => {
  if (!Array.isArray(coords)) return out;
  if (coords.length >= 2 && typeof coords[0] === "number" && typeof coords[1] === "number") {
    out.push([coords[1], coords[0]]);
    return out;
  }
  coords.forEach((child) => flattenCoords(child, out));
  return out;
};

export const getFeatureLatLngBounds = (feature) => {
  const latLngs = flattenCoords(feature?.geometry?.coordinates || []);
  if (!latLngs.length) return null;
  try {
    const bounds = L.latLngBounds(latLngs);
    return bounds.isValid() ? bounds : null;
  } catch {
    return null;
  }
};

export const getFeatureCenter = (feature) => {
  const bounds = getFeatureLatLngBounds(feature);
  if (!bounds) return null;
  const center = bounds.getCenter();
  return { lat: center.lat, lon: center.lng };
};

export const getFeatureIdentifier = (feature, fallbackIndex = 0) =>
  feature?.id ??
  feature?.properties?.id ??
  feature?.properties?.osm_id ??
  feature?.properties?.osm_way_id ??
  feature?.properties?.way_id ??
  feature?.properties?.objectid ??
  feature?.properties?.osm_uid ??
  feature?.properties?.["@id"] ??
  `feature-${fallbackIndex}`;

export const distanceBetweenLatLon = (a, b) => {
  if (!a || !b) return Infinity;
  const latA = Number(a.lat ?? a[0]);
  const lonA = Number(a.lon ?? a.lng ?? a[1]);
  const latB = Number(b.lat ?? b[0]);
  const lonB = Number(b.lon ?? b.lng ?? b[1]);
  return Math.hypot(latA - latB, lonA - lonB);
};

export const getSelectedBlockPropertyPoints = (selectedBlock, propertyPoints) => {
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

export const getSelectedBlockBounds = (selectedBlock, propertyPoints) => {
  if (!selectedBlock) return null;

  const explicitPoints = getSelectedBlockPropertyPoints(selectedBlock, propertyPoints);
  if (explicitPoints.length) {
    return L.latLngBounds(explicitPoints.map((p) => [p.lat, p.lon])).pad(0.12);
  }

  const blockLatLon = getBlockLatLon(selectedBlock);
  if (blockLatLon) return L.latLngBounds([blockLatLon, blockLatLon]).pad(0.006);
  return null;
};

export const getMainClusterPoints = (points) => {
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

export const getFitBoundsForMode = ({ activeMode, blockPoints, propertyPoints, selectedBlock, selectedProperty }) => {
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

export const buildPropertyFeatureAssignments = ({ sourceFeatures, targetPropertyPoints, selectedBounds }) => {
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

// Block hover-tooltip HTML, shared by the main block layer and the context-block layer.
export const buildBlockTooltipHtml = (point) => {
  const rep = point.raw?.representativeProperty;
  const rawAddr = rep?.address || rep?.address_line_1 || "";
  const addr = rawAddr.replace(/^(flat|apartment|unit|apt)[^,]*,\s*/i, "").trim() || point.name;
  const postcode = rep?.postcode ? ` ${rep.postcode}` : "";
  const count = getBlockPropertyCount(point.raw) || 0;
  const h = Number.isFinite(point.storeys) && point.storeys > 0 ? point.storeys : null;
  const heightStr = h ? `${h.toFixed(1)} m` : "—";
  const risk = h > 18 ? "High-risk" : h > 11 ? "Mid-risk" : "Low-risk";
  const riskColor = h > 18 ? "rgba(225,29,72,0.75)" : h > 11 ? "rgba(245,158,11,0.85)" : "rgba(100,116,139,0.75)";
  return `<div style="min-width:160px;line-height:1.6"><div style="font-weight:700;margin-bottom:2px">${addr}${postcode}</div><div style="color:#64748b">${count} properties · ${fmtMoney(point.totalValue)}</div><div style="color:#64748b">${heightStr} · <span style="color:${riskColor};font-weight:600">${h ? risk : "—"}</span></div><div style="margin-top:6px;padding-top:5px;border-top:1px solid #e2e8f0;display:flex;flex-direction:column;gap:1px"><span style="font-size:11px;color:#94a3b8">1× click → block summary</span><span style="font-size:11px;color:#94a3b8">2× click → flat list</span></div></div>`;
};
