// Popup HTML builders and handler wiring for PortfolioMap markers.
import {
  getRiskBand,
  getPropertyCategoryLabel,
  fmtMoney,
  getPropertyLabel,
  floodColor,
  worstFloodBand,
} from "../../utils/mapHelpers.js";
import { getFireRiskBand, heightCategory } from "../../utils/blockModel.js";

// A coloured pill chip: label on top, value below, tinted by risk band.
const riskChip = (label, value, color) => `
  <div style="flex:1 1 0;min-width:64px;border-left:3px solid ${color};background:${color}14;border-radius:5px;padding:4px 7px;">
    <div style="font-size:10px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;color:#64748b;">${label}</div>
    <div style="font-size:12px;font-weight:700;color:#0f172a;line-height:1.3;">${value}</div>
  </div>`;

const FIRE_BAND = {
  Red:     { text: "High",   color: "#ef4444" },
  Amber:   { text: "Medium", color: "#f59e0b" },
  Green:   { text: "Low",    color: "#22c55e" },
  Unknown: { text: "No data", color: "#94a3b8" },
};

// The risk strip shown only on the risk map: Fire · Flood · Height · Listed.
export const buildBlockRiskStripHtml = (point) => {
  const block = point.raw || {};
  const fra = FIRE_BAND[getFireRiskBand(block.latest_fra)] || FIRE_BAND.Unknown;
  const fraew = FIRE_BAND[getFireRiskBand(block.latest_fraew)] || FIRE_BAND.Unknown;

  const flood = worstFloodBand(block.properties);
  const floodValue = flood || "No data";

  const h = Number(block.maxHeight ?? point.storeys);
  const heightCat = heightCategory(block.maxHeight);
  const heightColor = !Number.isFinite(h) || h <= 0 ? "#94a3b8"
    : h >= 18 ? "#ef4444" : h >= 11 ? "#f59e0b" : "#64748b";

  const listedValue = block.isListed ? (block.listedGrade ? `Grade ${block.listedGrade}` : "Yes") : "No";
  const chips = [
    riskChip("FRA", fra.text, fra.color),
    riskChip("FRAEW", fraew.text, fraew.color),
    riskChip("Flood", floodValue, floodColor(flood)),
    riskChip("Height", heightCat || "No data", heightColor),
    riskChip("Listed", listedValue, block.isListed ? "#7c3aed" : "#94a3b8"),
  ];

  return `<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;">${chips.join("")}</div>`;
};

export const getPropertyPopupHtml = (point) => {
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

export const buildFlatListPopupHtml = (point, showRiskStrip = false) => {
  const flats = point.raw?.properties || [];
  const rep = point.raw?.representativeProperty;
  const rawAddr = rep?.address || rep?.address_line_1 || "";
  const addr = rawAddr.replace(/^(flat|apartment|unit|apt)[^,]*,\s*/i, "").trim();
  const postcode = rep?.post_code || rep?.postcode || "";
  const addrLine = [addr, postcode].filter(Boolean).join(" ");
  // Risk map: address + risk strip only, no flat list.
  if (showRiskStrip) {
    return `
      <div style="min-width:230px;max-width:300px">
        <div style="font-weight:700;font-size:13px;color:#0f172a;margin-bottom:8px">${addrLine || point.name}</div>
        ${buildBlockRiskStripHtml(point)}
      </div>`;
  }
  const items = flats.map((p, i) => {
    const label = getPropertyLabel(p, i);
    return `<div class="flat-row" data-idx="${i}" style="padding:7px 8px;cursor:pointer;border-radius:6px;font-size:13px;color:#0f172a;line-height:1.4">${label}</div>`;
  }).join("");
  return `
    <div style="min-width:230px;max-width:300px">
      <div style="margin-bottom:8px;padding-bottom:7px;border-bottom:1px solid #e2e8f0">
        <div style="font-weight:700;font-size:13px;color:#0f172a">${addrLine || point.name}</div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-top:4px">
          <span style="font-size:12px;color:#64748b">${flats.length} properties · Block ${point.name}</span>
          <span class="block-view-btn" style="font-size:12px;color:#2563eb;cursor:pointer;font-weight:600">Block view</span>
        </div>
      </div>
      <div style="max-height:220px;overflow-y:auto">${items}</div>
    </div>`;
};

export const attachFlatListPopupHandlers = (marker, point, onSelectProperty) => {
  marker.on("popupopen", (e) => {
    const container = e.popup.getElement();
    if (!container) return;
    container.querySelectorAll(".flat-row").forEach((el) => {
      el.addEventListener("mouseenter", () => { el.style.background = "#f1f5f9"; });
      el.addEventListener("mouseleave", () => { el.style.background = ""; });
      el.addEventListener("click", () => {
        const idx = parseInt(el.dataset.idx, 10);
        const flats = point.raw?.properties || [];
        if (flats[idx]) {
          onSelectProperty?.(flats[idx]);
          marker.closePopup();
        }
      });
    });
    const blockBtn = container.querySelector(".block-view-btn");
    if (blockBtn) {
      blockBtn.addEventListener("click", () => {
        onSelectProperty?.(null);
        marker.closePopup();
      });
    }
  });
};
