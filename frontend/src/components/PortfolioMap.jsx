import React, { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const DEFAULT_CENTER = [54.5, -3];
const DEFAULT_ZOOM = 5;
const FOCUSED_ZOOM = 15;
const BUILDINGS_URL = "/buildings_scotland_central.geojson";

const UK_LAT_BOUNDS = {
  min: 49.0,
  max: 61.5,
};

const UK_LON_BOUNDS = {
  min: -8.8,
  max: 2.8,
};

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

const looksLikeLatitude = (value) => {
  const n = Number(value);
  return Number.isFinite(n) && n >= -90 && n <= 90 && n !== 0;
};

const looksLikeLongitude = (value) => {
  const n = Number(value);
  return Number.isFinite(n) && n >= -180 && n <= 180 && n !== 0;
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
  if (Number.isFinite(numeric)) {
    return readinessColor(readinessBandFromScore(numeric));
  }

  return "#64748b";
};

const getRiskBand = (entity) => {
  const fra = entity?.latest_fra ?? entity?.fire_documents?.fra ?? null;
  const fraew = entity?.latest_fraew ?? entity?.fire_documents?.fraew ?? null;

  const fraRisk = String(
    fra?.risk_level ?? fra?.rag_status ?? fra?.raw_rating ?? ""
  ).toLowerCase();

  const fraewRisk = String(
    fraew?.risk_level ?? fraew?.rag_status ?? fraew?.raw_rating ?? ""
  ).toLowerCase();

  const combined = `${fraRisk} ${fraewRisk}`;

  if (
    combined.includes("red") ||
    combined.includes("high") ||
    combined.includes("not acceptable") ||
    combined.includes("intolerable")
  ) {
    return "Red";
  }

  if (
    combined.includes("amber") ||
    combined.includes("medium") ||
    combined.includes("moderate") ||
    combined.includes("tolerable")
  ) {
    return "Amber";
  }

  if (
    combined.includes("green") ||
    combined.includes("low") ||
    combined.includes("acceptable") ||
    combined.includes("broadly acceptable")
  ) {
    return "Green";
  }

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
    (a.id && b.id && a.id === b.id) ||
    (a.property_id && b.property_id && a.property_id === b.property_id) ||
    (a.property_reference &&
      b.property_reference &&
      a.property_reference === b.property_reference) ||
    (a.uprn && b.uprn && a.uprn === b.uprn)
  );
};

const sameBlock = (a, b) => {
  if (!a || !b) return false;

  return (
    (a.id && b.id && a.id === b.id) ||
    (a.block_id && b.block_id && a.block_id === b.block_id) ||
    (a.label && b.label && a.label === b.label) ||
    (a.name && b.name && a.name === b.name) ||
    (a.parent_uprn && b.parent_uprn && a.parent_uprn === b.parent_uprn)
  );
};

const normaliseLatLon = (lat, lon) => {
  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lon) ||
    lat === 0 ||
    lon === 0 ||
    !isWithinUkBounds(lat, lon)
  ) {
    return null;
  }

  return [lat, lon];
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

  const direct = normaliseLatLon(directLat, directLon);
  if (direct) return direct;

  const fallbackY = toNumberOrNull(row?.y_coordinate) ?? toNumberOrNull(row?.y);
  const fallbackX = toNumberOrNull(row?.x_coordinate) ?? toNumberOrNull(row?.x);

  const lat = looksLikeLatitude(fallbackY) ? fallbackY : null;
  const lon = looksLikeLongitude(fallbackX) ? fallbackX : null;

  return normaliseLatLon(lat, lon);
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

  const direct = normaliseLatLon(directLat, directLon);
  if (direct) return direct;

  const fallbackY =
    toNumberOrNull(block?.y_coordinate) ?? toNumberOrNull(block?.y);
  const fallbackX =
    toNumberOrNull(block?.x_coordinate) ?? toNumberOrNull(block?.x);

  const lat = looksLikeLatitude(fallbackY) ? fallbackY : null;
  const lon = looksLikeLongitude(fallbackX) ? fallbackX : null;

  return normaliseLatLon(lat, lon);
};

const getPropertyReadiness = (row) => {
  return (
    toNumberOrNull(row?.readiness_score) ??
    toNumberOrNull(row?.readinessScore) ??
    toNumberOrNull(row?.score) ??
    0
  );
};

const getPropertyBand = (row) => {
  return (
    row?.readiness_band ??
    row?.readinessBand ??
    readinessBandFromScore(getPropertyReadiness(row))
  );
};

const getPropertyId = (row, idx) => {
  return (
    row?.id ??
    row?.property_id ??
    row?.propertyId ??
    row?.property_reference ??
    row?.uprn ??
    `property-${idx + 1}`
  );
};

const getPropertyLabel = (row, idx) => {
  return (
    row?.address_line_1 ??
    row?.address1 ??
    row?.address ??
    row?.property_reference ??
    row?.block_reference ??
    row?.uprn ??
    `Property ${idx + 1}`
  );
};

const getPropertyValue = (row) => {
  return (
    toNumberOrNull(row?.sum_insured) ??
    toNumberOrNull(row?.sumInsured) ??
    toNumberOrNull(row?.total_sum_insured) ??
    toNumberOrNull(row?.tiv) ??
    0
  );
};

const getBlockId = (block, idx) => {
  return (
    block?.id ??
    block?.block_id ??
    block?.parent_uprn ??
    block?.name ??
    block?.label ??
    `block-${idx + 1}`
  );
};

const getBlockName = (block, idx) => {
  return (
    block?.label ??
    block?.name ??
    block?.block_reference ??
    block?.parent_uprn ??
    `Block ${idx + 1}`
  );
};

const getBlockUnits = (block) => {
  return (
    toNumberOrNull(block?.count) ??
    toNumberOrNull(block?.unit_count) ??
    toNumberOrNull(block?.units) ??
    toNumberOrNull(block?.property_count) ??
    0
  );
};

const getBlockValue = (block) => {
  return (
    toNumberOrNull(block?.totalValue) ??
    toNumberOrNull(block?.total_sum_insured) ??
    toNumberOrNull(block?.total_si) ??
    toNumberOrNull(block?.sum_insured) ??
    0
  );
};

const getBlockStoreys = (block) => {
  return (
    toNumberOrNull(block?.maxHeight) ??
    toNumberOrNull(block?.max_storeys) ??
    toNumberOrNull(block?.storeys) ??
    null
  );
};

const getBlockPropertyCount = (block) => {
  return Array.isArray(block?.properties)
    ? block.properties.length
    : getBlockUnits(block);
};

const inferPropertyCategory = (row) => {
  const propertyType = String(
    row?.property_type ?? row?.propertyType ?? row?.type ?? ""
  ).toLowerCase();

  const builtForm = String(
    row?.built_form ?? row?.builtForm ?? ""
  ).toLowerCase();

  const occupancy = String(
    row?.occupancy_type ?? row?.occupancyType ?? row?.occupancy ?? ""
  ).toLowerCase();

  const address = String(
    row?.address_line_1 ??
      row?.address1 ??
      row?.address ??
      row?.property_reference ??
      ""
  ).toLowerCase();

  const combined = `${propertyType} ${builtForm} ${occupancy} ${address}`;

  if (
    combined.includes("flat") ||
    combined.includes("apartment") ||
    combined.includes("maisonette")
  ) {
    return "flats";
  }

  if (
    combined.includes("house") ||
    combined.includes("bungalow") ||
    combined.includes("terrace") ||
    combined.includes("semi") ||
    combined.includes("detached")
  ) {
    return "houses";
  }

  if (
    combined.includes("retail") ||
    combined.includes("shop") ||
    combined.includes("office") ||
    combined.includes("commercial") ||
    combined.includes("industrial")
  ) {
    return "commercial";
  }

  if (combined.includes("mixed")) {
    return "mixed";
  }

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
  return (
    PROPERTY_TYPE_COLORS[inferPropertyCategory(row)] || PROPERTY_TYPE_COLORS.other
  );
};

const getBlockCircleSize = (units, zoom, isSelected) => {
  const safeUnits = Math.max(1, Number(units) || 1);

  if (zoom <= 7) {
    return isSelected ? 54 : 44;
  }
  if (zoom <= 9) {
    return Math.min(isSelected ? 64 : 58, 34 + Math.sqrt(safeUnits) * 5);
  }
  if (zoom <= 11) {
    return Math.min(isSelected ? 72 : 64, 38 + Math.sqrt(safeUnits) * 6);
  }
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

const createBlockCountIcon = (point, zoom, isSelected) => {
  const ringColor = isSelected ? "#1d4ed8" : riskColor(point.raw);
  const size = getBlockCircleSize(point.units, zoom, isSelected);
  const fontSize = size >= 68 ? 15 : size >= 56 ? 14 : 13;
  const label = formatCountLabel(point.units);

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
      ">
        ${label}
      </div>
    `,
  });
};

const getPropertyDotSize = (point, isSelected) => {
  const base =
    Math.max(
      10,
      Math.min(
        22,
        10 + Math.sqrt(Math.max(Number(point.sumInsured) || 0, 1)) / 900
      )
    ) || 10;

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
  const propertyTypeLabel = getPropertyCategoryLabel(point.raw);

  return `
    <div style="min-width:220px;">
      <div style="font-weight:700; margin-bottom:6px;">${point.label}</div>
      <div>Type: ${propertyTypeLabel}</div>
      <div>Sum insured: ${fmtMoney(point.sumInsured)}</div>
      <div>Readiness: ${point.readinessScore ?? "—"} (${point.readinessBand})</div>
      <div>Fire risk: ${risk || "—"}</div>
      <div>Lat: ${point.lat.toFixed(5)}</div>
      <div>Lon: ${point.lon.toFixed(5)}</div>
    </div>
  `;
};

const getBlockPopupHtml = (point) => {
  return `
    <div style="min-width:240px;">
      <div style="font-weight:700; margin-bottom:6px;">${point.name}</div>
      <div>Properties: ${getBlockPropertyCount(point.raw) || 0}</div>
      <div>Total insured value: ${fmtMoney(point.totalValue)}</div>
      <div>Height: ${
        Number.isFinite(point.storeys) && point.storeys > 0
          ? `${point.storeys.toFixed(1)} m`
          : "—"
      }</div>
      <div>Readiness: ${point.readinessScore ?? "—"}${
        point.readinessBand ? ` (${point.readinessBand})` : ""
      }</div>
      <div>Fire risk: ${getRiskBand(point.raw) || "—"}</div>
    </div>
  `;
};

const flattenCoords = (coords, out = []) => {
  if (!Array.isArray(coords)) return out;

  if (
    coords.length >= 2 &&
    typeof coords[0] === "number" &&
    typeof coords[1] === "number"
  ) {
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

const getFeatureIdentifier = (feature, fallbackIndex = 0) => {
  return (
    feature?.properties?.id ??
    feature?.properties?.osm_id ??
    feature?.properties?.osm_way_id ??
    feature?.properties?.way_id ??
    feature?.properties?.objectid ??
    feature?.properties?.osm_uid ??
    `feature-${fallbackIndex}`
  );
};

const getPointIdentifier = (point) => {
  return (
    point?.raw?.id ??
    point?.raw?.property_id ??
    point?.raw?.property_reference ??
    point?.raw?.uprn ??
    point?.id ??
    null
  );
};

const getNearestPropertyPoint = (feature, propertyPoints) => {
  const bounds = getFeatureLatLngBounds(feature);
  if (!bounds || !propertyPoints.length) return null;

  const center = bounds.getCenter();
  let best = null;
  let bestDistance = Infinity;

  propertyPoints.forEach((point) => {
    const distance = Math.hypot(point.lat - center.lat, point.lon - center.lng);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = point;
    }
  });

  return best;
};

const getAssignedFeatureStyle = (assignedPoint, selectedProperty) => {
  const isSelected =
    assignedPoint && selectedProperty
      ? sameProperty(assignedPoint.raw, selectedProperty)
      : false;

  const fillColor = assignedPoint
    ? getPropertyDisplayColor(assignedPoint.raw, false)
    : PROPERTY_TYPE_COLORS.other;

  return {
    color: isSelected ? "#1d4ed8" : "rgba(15,23,42,0.28)",
    weight: isSelected ? 2.2 : 0.8,
    fillColor,
    fillOpacity: assignedPoint ? (isSelected ? 0.82 : 0.58) : 0.14,
  };
};

const getSelectedBlockBounds = (selectedBlock, propertyPoints) => {
  if (!selectedBlock) return null;

  const explicitPoints = propertyPoints.filter((point) => {
    return (
      Array.isArray(selectedBlock?.properties) &&
      selectedBlock.properties.some((p) => sameProperty(p, point.raw))
    );
  });

  if (explicitPoints.length) {
    return L.latLngBounds(explicitPoints.map((p) => [p.lat, p.lon])).pad(0.18);
  }

  const blockLatLon = getBlockLatLon(selectedBlock);
  if (blockLatLon) {
    const nearbyPoints = propertyPoints.filter((point) => {
      const dx = Math.abs(point.lat - blockLatLon[0]);
      const dy = Math.abs(point.lon - blockLatLon[1]);
      return dx <= 0.01 && dy <= 0.01;
    });

    if (nearbyPoints.length) {
      return L.latLngBounds(nearbyPoints.map((p) => [p.lat, p.lon])).pad(0.2);
    }

    return L.latLngBounds([blockLatLon, blockLatLon]).pad(0.01);
  }

  if (propertyPoints.length) {
    return L.latLngBounds(propertyPoints.map((p) => [p.lat, p.lon])).pad(0.2);
  }

  return null;
};

export default function PortfolioMap({
  properties = [],
  blocks = [],
  selectedProperty = null,
  selectedBlock = null,
  onSelectProperty,
  onSelectBlock,
  viewMode = "properties",
}) {
  const mapDivRef = useRef(null);
  const mapRef = useRef(null);
  const pointLayerRef = useRef(null);
  const buildingsLayerRef = useRef(null);
  const selectedMarkerRef = useRef(null);
  const lastFitSignatureRef = useRef("");
  const lastSelectionSignatureRef = useRef("");
  const zoomRef = useRef(DEFAULT_ZOOM);
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
          raw: {
            ...property,
            __lat: latLon[0],
            __lon: latLon[1],
          },
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
        const readinessScore =
          toNumberOrNull(block?.avgReadiness) ??
          toNumberOrNull(block?.readiness_score) ??
          null;

        const readinessBand =
          block?.readiness_band ??
          (Number.isFinite(readinessScore)
            ? readinessBandFromScore(readinessScore)
            : "Amber");

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
          raw: {
            ...block,
            __lat: latLon[0],
            __lon: latLon[1],
          },
        };
      })
      .filter(Boolean);
  }, [blocks]);

  const activeMode = viewMode === "properties" ? "properties" : "blocks";
  const visiblePoints = activeMode === "blocks" ? blockPoints : propertyPoints;

  useEffect(() => {
    if (!mapDivRef.current || mapRef.current) return;

    const map = L.map(mapDivRef.current, {
      scrollWheelZoom: false,
      zoomControl: true,
      attributionControl: false,
    }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd",
      maxZoom: 20,
      attribution: "&copy; OpenStreetMap &copy; CARTO",
    }).addTo(map);

    map.on("zoomend", () => {
      zoomRef.current = map.getZoom();
    });

    mapRef.current = map;
    pointLayerRef.current = L.layerGroup().addTo(map);
    buildingsLayerRef.current = L.layerGroup().addTo(map);

    setTimeout(() => {
      map.invalidateSize();
    }, 120);
  }, []);

  useEffect(() => {
    const onResize = () => {
      mapRef.current?.invalidateSize();
    };

    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const pointLayer = pointLayerRef.current;
    const buildingsLayer = buildingsLayerRef.current;
    if (!map || !pointLayer || !buildingsLayer) return;

    selectedMarkerRef.current = null;
    pointLayer.clearLayers();

    if (!visiblePoints.length) {
      lastFitSignatureRef.current = "";
      buildingsLayer.clearLayers();
      map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
      setTimeout(() => map.invalidateSize(), 80);
      return;
    }

    const bounds = [];
    const currentZoom = map.getZoom();

    if (activeMode === "blocks") {
      buildingsLayer.clearLayers();

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
          `${point.name} · ${getBlockPropertyCount(point.raw) || 0} properties · ${fmtMoney(
            point.totalValue
          )}`,
          {
            direction: "top",
            sticky: true,
            opacity: 0.95,
          }
        );

        marker.bindPopup(getBlockPopupHtml(point));
        marker.addTo(pointLayer);

        if (isSelected) {
          selectedMarkerRef.current = marker;
        }

        bounds.push([point.lat, point.lon]);
      });
    } else {
      propertyPoints.forEach((point) => {
        const isSelected = sameProperty(selectedProperty, point.raw);

        const marker = L.marker([point.lat, point.lon], {
          icon: createPropertyDotIcon(point, isSelected),
          keyboard: false,
        });

        marker.on("click", () => {
          onSelectProperty?.(point.raw);
        });

        marker.bindTooltip(
          `${point.label} · ${point.propertyCategoryLabel} · readiness ${
            point.readinessScore ?? "—"
          }`,
          {
            direction: "top",
            sticky: true,
            opacity: 0.95,
          }
        );

        marker.bindPopup(getPropertyPopupHtml(point));
        marker.addTo(pointLayer);

        if (isSelected) {
          selectedMarkerRef.current = marker;
        }

        bounds.push([point.lat, point.lon]);
      });
    }

    const shouldFitToVisiblePoints =
      (activeMode === "blocks" && !selectedBlock && !selectedProperty) ||
      (activeMode === "properties" && !selectedProperty);

    if (shouldFitToVisiblePoints && bounds.length) {
      const signature = JSON.stringify([activeMode, bounds]);
      if (lastFitSignatureRef.current !== signature) {
        const leafletBounds = L.latLngBounds(bounds);
        if (leafletBounds.isValid()) {
          map.fitBounds(leafletBounds.pad(activeMode === "properties" ? 0.24 : 0.12), {
            animate: false,
            maxZoom: activeMode === "properties" ? FOCUSED_ZOOM : undefined,
          });
          lastFitSignatureRef.current = signature;
        }
      }
    }

    setTimeout(() => map.invalidateSize(), 80);
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
    const buildingsLayer = buildingsLayerRef.current;

    if (!map || !buildingsLayer) return;

    const shouldShowBuildings =
      activeMode === "properties" && selectedBlock && propertyPoints.length > 0;

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
              if (!res.ok) {
                throw new Error(`Failed to load buildings GeoJSON: ${res.status}`);
              }
              return res.json();
            });
          }
          buildingsGeojsonCacheRef.current = await buildingsFetchPromiseRef.current;
        }

        if (isCancelled) return;

        const source = buildingsGeojsonCacheRef.current;
        const selectedBounds = getSelectedBlockBounds(selectedBlock, propertyPoints);

        buildingsLayer.clearLayers();

        if (!source?.features?.length || !selectedBounds) {
          return;
        }

        const filteredFeatures = source.features.filter((feature) => {
          const bounds = getFeatureLatLngBounds(feature);
          return bounds ? selectedBounds.intersects(bounds) : false;
        });

        if (!filteredFeatures.length) {
          return;
        }

        const featureAssignments = new Map();

filteredFeatures.forEach((feature, index) => {
  const nearest = getNearestPropertyPoint(feature, propertyPoints);
  if (!nearest) return;

  featureAssignments.set(getFeatureIdentifier(feature, index), nearest);
});
        const geoJsonLayer = L.geoJSON(
          {
            type: "FeatureCollection",
            features: filteredFeatures,
          },
          {
            style: (feature) => {
              const featureId = getFeatureIdentifier(feature);
              const assignedPoint = featureAssignments.get(featureId) || null;
              return getAssignedFeatureStyle(assignedPoint, selectedProperty);
            },
            onEachFeature: (feature, layer) => {
              const featureId = getFeatureIdentifier(feature);
              const assignedPoint = featureAssignments.get(featureId) || null;
              const typeLabel = assignedPoint
                ? getPropertyCategoryLabel(assignedPoint.raw)
                : "Other";

              layer.on({
                click: () => {
                  if (assignedPoint) {
                    onSelectProperty?.(assignedPoint.raw);
                  }
                },
                mouseover: () => {
                  const isSelected =
                    assignedPoint &&
                    selectedProperty &&
                    sameProperty(assignedPoint.raw, selectedProperty);

                  layer.setStyle({
                    weight: 2,
                    color: "#0f172a",
                    fillOpacity: assignedPoint ? (isSelected ? 0.84 : 0.7) : 0.18,
                  });
                },
                mouseout: () => {
                  if (geoJsonLayer.resetStyle) {
                    geoJsonLayer.resetStyle(layer);
                  }
                },
              });

              layer.bindTooltip(
                assignedPoint
                  ? `${assignedPoint.label} · ${typeLabel}`
                  : "Building footprint",
                {
                  direction: "top",
                  sticky: true,
                  opacity: 0.95,
                }
              );
            },
          }
        );

        geoJsonLayer.addTo(buildingsLayer);
      } catch (error) {
        console.error("Buildings layer load failed:", error);
        buildingsLayer.clearLayers();
      }
    };

    renderBuildings();

    return () => {
      isCancelled = true;
    };
  }, [
    activeMode,
    onSelectProperty,
    propertyPoints,
    selectedBlock,
    selectedProperty,
  ]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (activeMode === "blocks" && selectedBlock) {
      const latLon = getBlockLatLon(selectedBlock);
      if (!latLon) return;

      const selectionSignature = `block:${
        selectedBlock.id ?? selectedBlock.block_id ?? selectedBlock.label ?? ""
      }`;

      if (lastSelectionSignatureRef.current === selectionSignature) {
        selectedMarkerRef.current?.openPopup();
        return;
      }

      lastSelectionSignatureRef.current = selectionSignature;

      map.flyTo(latLon, Math.max(map.getZoom(), FOCUSED_ZOOM), {
        duration: 0.45,
      });

      setTimeout(() => {
        selectedMarkerRef.current?.openPopup();
      }, 320);

      return;
    }

    if (activeMode === "properties") {
      if (selectedProperty) {
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
          map.flyTo(latLon, Math.max(map.getZoom(), FOCUSED_ZOOM), {
            duration: 0.45,
          });
        }

        setTimeout(() => {
          selectedMarkerRef.current?.openPopup();
        }, 320);
        return;
      }

      if (propertyPoints.length) {
        const selectionSignature = `property-group:${
          selectedBlock?.id ?? selectedBlock?.block_id ?? selectedBlock?.label ?? "group"
        }:${propertyPoints.length}`;

        if (lastSelectionSignatureRef.current !== selectionSignature) {
          lastSelectionSignatureRef.current = selectionSignature;

          const bounds = L.latLngBounds(
            propertyPoints.map((point) => [point.lat, point.lon])
          );

          if (bounds.isValid()) {
            map.flyToBounds(bounds.pad(0.24), {
              duration: 0.55,
              maxZoom: FOCUSED_ZOOM,
            });
          } else if (propertyPoints[0]) {
            map.flyTo([propertyPoints[0].lat, propertyPoints[0].lon], FOCUSED_ZOOM, {
              duration: 0.45,
            });
          }
        }

        return;
      }
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