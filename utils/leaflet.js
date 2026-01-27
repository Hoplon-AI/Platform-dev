import L from "leaflet";

/**
 * Fix default Leaflet marker icons for Vite / React builds
 */
export function configureLeafletIcons() {
  delete L.Icon.Default.prototype._getIconUrl;

  L.Icon.Default.mergeOptions({
    iconRetinaUrl:
      "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  });
}

/**
 * Create exposure-weighted city marker size (optional future use)
 */
export function getMarkerRadius(value) {
  if (!value) return 8;

  if (value > 50_000_000) return 20;
  if (value > 10_000_000) return 16;
  if (value > 1_000_000) return 12;

  return 8;
}
