// src/utils/uprn.js

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export function normalizePostcode(postcode) {
  return String(postcode || "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, " ")
    .replace(/(.+)([A-Z0-9]{3})$/, (_match, outward, inward) => {
      const cleanOutward = String(outward || "").replace(/\s+/g, "");
      return cleanOutward ? `${cleanOutward} ${inward}` : inward;
    });
}

export function buildAddressLine(property) {
  if (!property || typeof property !== "object") return "";

  const parts = [
    property.address_line_1,
    property.address_line_2,
    property.address_3,
    property.city,
  ]
    .map((value) => String(value || "").trim())
    .filter(Boolean);

  return parts.join(", ");
}

function toJsonSafeError(error, fallback = "Unknown error") {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error?.message) return error.message;
  return fallback;
}

function extractPayloadError(payload, response) {
  if (typeof payload === "string" && payload.trim()) {
    return payload.trim();
  }

  if (payload && typeof payload === "object") {
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail.trim();
    }

    if (typeof payload.error === "string" && payload.error.trim()) {
      return payload.error.trim();
    }

    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item?.msg) return item.msg;
          return JSON.stringify(item);
        })
        .join("; ");
    }

    return JSON.stringify(payload);
  }

  return `Request failed (${response?.status || "unknown"})`;
}

export async function matchUPRN(
  { address, postcode },
  { signal } = {}
) {
  const payload = {
    address: String(address || "").trim(),
    postcode: normalizePostcode(postcode),
  };

  if (!payload.address || !payload.postcode) {
    return {
      error: "Missing address or postcode",
      request: payload,
      data: null,
    };
  }

  let response;
  let body;

  try {
    response = await fetch(`${API_BASE}/api/v1/geo/uprn/match`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (error) {
    return {
      error: toJsonSafeError(error, "Failed to reach backend"),
      request: payload,
      data: null,
    };
  }

  try {
    const contentType = response.headers.get("content-type") || "";
    body = contentType.includes("application/json")
      ? await response.json()
      : await response.text();
  } catch {
    body = null;
  }

  if (!response.ok) {
    return {
      error: extractPayloadError(body, response),
      request: payload,
      data: null,
    };
  }

  return {
    error: null,
    request: payload,
    data: body,
  };
}

export function bandMeta(band) {
  const normalized = String(band || "").trim().toUpperCase();

  if (
    normalized.includes("HIGH") ||
    normalized.includes("GREEN") ||
    normalized === "A"
  ) {
    return {
      label: "Green",
      cls: "band-green",
    };
  }

  if (
    normalized.includes("MED") ||
    normalized.includes("AMBER") ||
    normalized.includes("YELLOW") ||
    normalized === "B"
  ) {
    return {
      label: "Amber",
      cls: "band-amber",
    };
  }

  return {
    label: normalized ? "Red" : "Unknown",
    cls: normalized ? "band-red" : "band-muted",
  };
}

export function normalizeUPRNResult(result) {
  const data = result?.data || result || {};
  const bestMatch =
    data.best_match ||
    data.bestMatch ||
    null;

  const candidates = Array.isArray(data.candidates) ? data.candidates : [];
  const warnings = Array.isArray(data.warnings) ? data.warnings : [];

  return {
    best_match: bestMatch,
    candidates,
    warnings,
    raw: data,
  };
}