// Popup HTML builders and handler wiring for PortfolioMap markers.
import {
  getRiskBand,
  getPropertyCategoryLabel,
  fmtMoney,
  getPropertyLabel,
} from "../../utils/mapHelpers.js";

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

export const buildFlatListPopupHtml = (point) => {
  const flats = point.raw?.properties || [];
  const rep = point.raw?.representativeProperty;
  const rawAddr = rep?.address || rep?.address_line_1 || "";
  const addr = rawAddr.replace(/^(flat|apartment|unit|apt)[^,]*,\s*/i, "").trim();
  const postcode = rep?.post_code || rep?.postcode || "";
  const addrLine = [addr, postcode].filter(Boolean).join(" ");
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
