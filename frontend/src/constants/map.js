// Map constants for PortfolioMap: zoom levels, bounds, colors, and risk priority.

export const DEFAULT_CENTER = [54.5, -3];
export const DEFAULT_ZOOM = 5;
export const CLUSTER_ZOOM = 13;
export const BLOCK_ZOOM = 18;
export const FOCUSED_ZOOM = 19;
export const POLYGON_ZOOM = 17; // risk map: switch block bubbles → footprint polygons at/above this zoom
export const CONTEXT_BLOCK_ZOOM = 16.5;
export const CONTEXT_BLOCK_FADE_START_ZOOM = 18.5;
export const CONTEXT_BLOCK_HIDE_ZOOM = 19;
export const BUILDINGS_URL = "/buildings_cathcart.geojson";

export const UK_LAT_BOUNDS = { min: 49.0, max: 61.5 };
export const UK_LON_BOUNDS = { min: -8.8, max: 2.8 };

export const PROPERTY_TYPE_COLORS = {
  flats: "#8b5cf6",
  houses: "#22c55e",
  commercial: "#f59e0b",
  mixed: "#3b82f6",
  other: "#64748b",
};

export const RISK_PRIORITY = { "#ef4444": 3, "#f59e0b": 2, "#22c55e": 1, "#64748b": 0 };
