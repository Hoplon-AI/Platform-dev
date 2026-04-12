import React, { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const DEFAULT_CENTER = [54.5, -3];
const DEFAULT_ZOOM = 5;

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

const getPropertyLatLon = (row) => {
  const directLat =
    toNumberOrNull(row.latitude) ??
    toNumberOrNull(row.lat) ??
    toNumberOrNull(row.location?.latitude) ??
    toNumberOrNull(row.__lat);

  const directLon =
    toNumberOrNull(row.longitude) ??
    toNumberOrNull(row.lon) ??
    toNumberOrNull(row.lng) ??
    toNumberOrNull(row.location?.longitude) ??
    toNumberOrNull(row.__lon);

  const fallbackY =
    toNumberOrNull(row.y_coordinate) ??
    toNumberOrNull(row.y);

  const fallbackX =
    toNumberOrNull(row.x_coordinate) ??
    toNumberOrNull(row.x);

  const lat = directLat ?? (looksLikeLatitude(fallbackY) ? fallbackY : null);
  const lon = directLon ?? (looksLikeLongitude(fallbackX) ? fallbackX : null);

  if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat === 0 || lon === 0) {
    return null;
  }

  return [lat, lon];
};

const getBlockLatLon = (block) => {
  const lat =
    toNumberOrNull(block.lat) ??
    toNumberOrNull(block.latitude) ??
    toNumberOrNull(block.centroid_lat) ??
    toNumberOrNull(block.center_lat) ??
    toNumberOrNull(block.centre_lat) ??
    toNumberOrNull(block.__lat);

  const lon =
    toNumberOrNull(block.lon) ??
    toNumberOrNull(block.longitude) ??
    toNumberOrNull(block.lng) ??
    toNumberOrNull(block.centroid_lon) ??
    toNumberOrNull(block.centroid_lng) ??
    toNumberOrNull(block.center_lon) ??
    toNumberOrNull(block.centre_lon) ??
    toNumberOrNull(block.__lon);

  if (Number.isFinite(lat) && Number.isFinite(lon) && lat !== 0 && lon !== 0) {
    return [lat, lon];
  }

  const fallbackY =
    toNumberOrNull(block.y_coordinate) ??
    toNumberOrNull(block.y);

  const fallbackX =
    toNumberOrNull(block.x_coordinate) ??
    toNumberOrNull(block.x);

  const fy = looksLikeLatitude(fallbackY) ? fallbackY : null;
  const fx = looksLikeLongitude(fallbackX) ? fallbackX : null;

  if (Number.isFinite(fy) && Number.isFinite(fx) && fy !== 0 && fx !== 0) {
    return [fy, fx];
  }

  return null;
};

const getPropertyReadiness = (row) => {
  return (
    toNumberOrNull(row.readiness_score) ??
    toNumberOrNull(row.readinessScore) ??
    toNumberOrNull(row.score) ??
    0
  );
};

const getPropertyBand = (row) => {
  return (
    row.readiness_band ??
    row.readinessBand ??
    readinessBandFromScore(getPropertyReadiness(row))
  );
};

const getPropertyId = (row, idx) => {
  return (
    row.id ??
    row.property_id ??
    row.propertyId ??
    row.property_reference ??
    row.uprn ??
    `property-${idx + 1}`
  );
};

const getPropertyLabel = (row, idx) => {
  return (
    row.address_line_1 ??
    row.address1 ??
    row.address ??
    row.property_reference ??
    row.block_reference ??
    row.uprn ??
    `Property ${idx + 1}`
  );
};

const getPropertyValue = (row) => {
  return (
    toNumberOrNull(row.sum_insured) ??
    toNumberOrNull(row.sumInsured) ??
    toNumberOrNull(row.total_sum_insured) ??
    toNumberOrNull(row.tiv) ??
    0
  );
};

const getBlockId = (block, idx) => {
  return (
    block.id ??
    block.block_id ??
    block.parent_uprn ??
    block.name ??
    block.label ??
    `block-${idx + 1}`
  );
};

const getBlockName = (block, idx) => {
  return (
    block.label ??
    block.name ??
    block.block_reference ??
    block.parent_uprn ??
    `Block ${idx + 1}`
  );
};

const getBlockUnits = (block) => {
  return (
    toNumberOrNull(block.count) ??
    toNumberOrNull(block.unit_count) ??
    toNumberOrNull(block.units) ??
    toNumberOrNull(block.property_count) ??
    0
  );
};

const getBlockValue = (block) => {
  return (
    toNumberOrNull(block.totalValue) ??
    toNumberOrNull(block.total_sum_insured) ??
    toNumberOrNull(block.total_si) ??
    toNumberOrNull(block.sum_insured) ??
    0
  );
};

const getBlockStoreys = (block) => {
  return (
    toNumberOrNull(block.maxHeight) ??
    toNumberOrNull(block.max_storeys) ??
    toNumberOrNull(block.storeys) ??
    null
  );
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
  const layerRef = useRef(null);
  const lastFitSignatureRef = useRef("");

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
          toNumberOrNull(block.avgReadiness) ??
          toNumberOrNull(block.readiness_score) ??
          null;

        const readinessBand =
          block.readiness_band ??
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

  const activeMode = viewMode === "blocks" ? "blocks" : "properties";
  const visiblePoints = activeMode === "blocks" ? blockPoints : propertyPoints;

  useEffect(() => {
    if (!mapDivRef.current || mapRef.current) return;

    const map = L.map(mapDivRef.current, {
      scrollWheelZoom: false,
      zoomControl: true,
    }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
    }).addTo(map);

    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);

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
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    if (!visiblePoints.length) {
      lastFitSignatureRef.current = "";
      map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
      setTimeout(() => map.invalidateSize(), 80);
      return;
    }

    const bounds = [];

    if (activeMode === "blocks") {
      blockPoints.forEach((point) => {
        const isSelected = sameBlock(selectedBlock, point.raw);

        const radius = Math.max(
          10,
          Math.min(26, 10 + Math.sqrt(Math.max(point.units, 1)) * 2)
        );

        const marker = L.circleMarker([point.lat, point.lon], {
          radius,
          color: isSelected ? "#1d4ed8" : point.color,
          weight: isSelected ? 4 : 2,
          fillColor: point.color,
          fillOpacity: 0.35,
        });

        marker.on("click", () => {
          onSelectBlock?.(point.raw);
          if (typeof onSelectProperty === "function") {
            onSelectProperty(null);
          }
        });

        marker.bindTooltip(
          `${point.name} · ${point.units || 0} properties · ${fmtMoney(point.totalValue)}`,
          {
            direction: "top",
            sticky: true,
            opacity: 0.95,
          }
        );

        marker.bindPopup(`
          <div style="min-width: 220px;">
            <div style="font-weight: 700; margin-bottom: 6px;">${point.name}</div>
            <div>Properties: ${point.units || 0}</div>
            <div>Total insured value: ${fmtMoney(point.totalValue)}</div>
            <div>Height: ${point.storeys ?? "—"}</div>
            <div>Readiness: ${point.readinessScore ?? "—"}${
              point.readinessBand ? ` (${point.readinessBand})` : ""
            }</div>
          </div>
        `);

        marker.addTo(layer);
        bounds.push([point.lat, point.lon]);
      });
    } else {
      propertyPoints.forEach((point) => {
        const isSelected = sameProperty(selectedProperty, point.raw);

        const radius = Math.max(
          6,
          Math.min(18, Math.sqrt((Number(point.sumInsured) || 0) / 250000) || 6)
        );

        const marker = L.circleMarker([point.lat, point.lon], {
          radius,
          color: isSelected ? "#1d4ed8" : point.color,
          weight: isSelected ? 3 : 2,
          fillColor: point.color,
          fillOpacity: 0.55,
        });

        marker.on("click", () => {
          onSelectProperty?.(point.raw);
        });

        marker.bindTooltip(
          `${point.label} · readiness ${point.readinessScore ?? "—"}`,
          {
            direction: "top",
            sticky: true,
            opacity: 0.95,
          }
        );

        marker.bindPopup(`
          <div style="min-width: 220px;">
            <div style="font-weight: 700; margin-bottom: 6px;">${point.label}</div>
            <div>Sum insured: ${fmtMoney(point.sumInsured)}</div>
            <div>Readiness: ${point.readinessScore ?? "—"} (${point.readinessBand})</div>
            <div>Lat: ${point.lat.toFixed(5)}</div>
            <div>Lon: ${point.lon.toFixed(5)}</div>
          </div>
        `);

        marker.addTo(layer);
        bounds.push([point.lat, point.lon]);
      });
    }

    if (!selectedBlock && !selectedProperty && bounds.length) {
      const signature = JSON.stringify(bounds);
      if (lastFitSignatureRef.current !== signature) {
        const leafletBounds = L.latLngBounds(bounds);
        if (leafletBounds.isValid()) {
          map.fitBounds(leafletBounds.pad(0.18), { animate: false });
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
    if (!map) return;

    if (activeMode === "blocks" && selectedBlock) {
      const latLon = getBlockLatLon(selectedBlock);
      if (latLon) {
        map.flyTo(latLon, Math.max(map.getZoom(), 13), { duration: 0.45 });
      }
      return;
    }

    if (activeMode === "properties" && selectedProperty) {
      const latLon = getPropertyLatLon(selectedProperty);
      if (latLon) {
        map.flyTo(latLon, Math.max(map.getZoom(), 14), { duration: 0.45 });
      }
    }
  }, [activeMode, selectedBlock, selectedProperty]);

  return (
    <div
      ref={mapDivRef}
      className="portfolio-map-canvas"
      style={{
        height: 560,
        width: "100%",
        borderRadius: 18,
        overflow: "hidden",
        background: "#e5eefc",
      }}
    />
  );
}