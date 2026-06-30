// Leaflet divIcon builders and sizing/visibility helpers for PortfolioMap markers.
import L from "leaflet";
import {
  RISK_PRIORITY,
  CONTEXT_BLOCK_ZOOM,
  CONTEXT_BLOCK_FADE_START_ZOOM,
  CONTEXT_BLOCK_HIDE_ZOOM,
} from "../../constants/map.js";
import { riskColor, getPropertyDisplayColor } from "../../utils/mapHelpers.js";

export const getBlockCircleSize = (units, zoom, isSelected) => {
  const safeUnits = Math.max(1, Number(units) || 1);
  if (zoom <= 7) return isSelected ? 54 : 44;
  if (zoom <= 9) return Math.min(isSelected ? 64 : 58, 34 + Math.sqrt(safeUnits) * 5);
  if (zoom <= 11) return Math.min(isSelected ? 72 : 64, 38 + Math.sqrt(safeUnits) * 6);
  return Math.min(isSelected ? 78 : 70, 42 + Math.sqrt(safeUnits) * 6.5);
};

export const formatCountLabel = (count) => {
  const safe = Number(count) || 0;
  if (safe >= 1000) {
    const compact = safe / 1000;
    return Number.isInteger(compact) ? `${compact}k` : `${compact.toFixed(1)}k`;
  }
  return String(safe);
};

export const createClusterIcon = (cluster) => {
  const markers = cluster.getAllChildMarkers();
  const totalUnits = markers.reduce((sum, m) => sum + (m.options._units || 0), 0);
  const ringColor = markers.reduce((best, m) => {
    const c = m.options._ringColor || "#64748b";
    return (RISK_PRIORITY[c] ?? 0) > (RISK_PRIORITY[best] ?? 0) ? c : best;
  }, "#64748b");
  const count = totalUnits || cluster.getChildCount();
  const size = Math.min(72, 44 + Math.sqrt(count) * 2.2);
  const fontSize = size >= 64 ? 15 : size >= 52 ? 14 : 13;
  return L.divIcon({
    className: "portfolio-block-count-icon",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `<div style="
      width:${size}px;height:${size}px;border-radius:999px;
      background:rgba(255,255,255,0.94);border:3px solid ${ringColor};
      box-shadow:0 10px 24px rgba(15,23,42,0.14);
      display:flex;align-items:center;justify-content:center;
      font-weight:800;font-size:${fontSize}px;color:#0f172a;
      backdrop-filter:blur(8px);
    ">${formatCountLabel(count)}</div>`,
  });
};

export const createBlockCountIcon = (point, zoom, isSelected, opacity = 1, scale = 1) => {
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

export const getContextBlockVisibility = (zoom) => {
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

export const getPropertyDotSize = (point, isSelected) => {
  const base = Math.max(10, Math.min(22, 10 + Math.sqrt(Math.max(Number(point.sumInsured) || 0, 1)) / 900));
  return isSelected ? base + 4 : base;
};

export const createPropertyDotIcon = (point, isSelected) => {
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
