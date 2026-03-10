// src/utils/uprn.js

// If your backend is on a different port/host, change this.
// If you're proxying via Vite, you can set it to "" and use "/api/..."
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export function normalizePostcode(pc) {
  return (pc || "").toString().trim().toUpperCase().replace(/\s+/g, " ");
}

export function buildAddressLine(p) {
  // Use what you already store from ingestion (try to be robust)
  const a1 = p.address1 || p.address_line_1 || "";
  const a2 = p.address2 || p.address_line_2 || "";
  const city = p.city || "";
  const parts = [a1, a2, city].map((x) => (x || "").toString().trim()).filter(Boolean);
  return parts.join(", ");
}

// Calls backend UPRN matcher
export async function matchUPRN({ address, postcode }, { signal } = {}) {
  const payload = {
    address: (address || "").toString().trim(),
    postcode: normalizePostcode(postcode),
  };

  if (!payload.address || !payload.postcode) {
    return {
      error: "Missing address or postcode",
      request: payload,
      data: null,
    };
  }

  const res = await fetch(`${API_BASE}/api/v1/geo/uprn/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    return {
      error: `UPRN API error (${res.status}) ${text}`.trim(),
      request: payload,
      data: null,
    };
  }

  const data = await res.json();
  return { error: null, request: payload, data };
}

// Convenience: map backend band -> UI label + colour class name
export function bandMeta(band) {
  const b = (band || "").toString().toUpperCase();
  if (b.includes("HIGH") || b.includes("GREEN")) return { label: "Green", cls: "band-green" };
  if (b.includes("MED") || b.includes("YELLOW")) return { label: "Yellow", cls: "band-yellow" };
  return { label: "Red", cls: "band-red" };
}
