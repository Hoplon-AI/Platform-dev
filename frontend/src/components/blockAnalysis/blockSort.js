// Risk-band ordering + sort comparator for the Block Analysis table.
import { blockDisplayAddress, getFireRiskBand } from "../../utils/blockModel";

// Risk-band ordering for sorting (Red worst → none).
export const BAND_WEIGHT = { Red: 3, Amber: 2, Green: 1 };
export const bandWeight = (band) => BAND_WEIGHT[band] || 0;
export const accentClass = (band) => ({ Red: "r-red", Amber: "r-amber", Green: "r-green" }[band] || "");

// Display label for the Type column: "Block" or the standalone dwelling form.
export const assetTypeLabel = (b) =>
  b.asset_type === "standalone"
    ? (b.dwelling_form ? b.dwelling_form.charAt(0).toUpperCase() + b.dwelling_form.slice(1).replace("_", " ") : "Standalone")
    : "Block";

// Comparator for the sortable columns.
export function compareBlocks(a, b, key) {
  switch (key) {
    case "address":
      return blockDisplayAddress(a).street.localeCompare(blockDisplayAddress(b).street);
    case "type":
      return assetTypeLabel(a).localeCompare(assetTypeLabel(b));
    case "flats":
      return (a.count || 0) - (b.count || 0);
    case "fra":
      return bandWeight(getFireRiskBand(a.latest_fra)) - bandWeight(getFireRiskBand(b.latest_fra));
    case "fraew":
      return bandWeight(getFireRiskBand(a.latest_fraew)) - bandWeight(getFireRiskBand(b.latest_fraew));
    default:
      return 0;
  }
}
