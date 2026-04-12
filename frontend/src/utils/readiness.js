// src/utils/readiness.js

const toNumberOrNull = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const isPresent = (value) => {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (typeof value === "number") return Number.isFinite(value);
  return true;
};

const get = (row, key) => {
  switch (key) {
    case "address_line_1":
      return (
        row.address_line_1 ??
        row.address1 ??
        row.address ??
        row.property_address ??
        row["address line 1"]
      );

    case "post_code":
      return row.post_code ?? row.postcode ?? row.Postcode ?? row["post code"];

    case "city":
      return row.city ?? row.town ?? row.locality ?? row.City;

    case "latitude":
      return (
        row.latitude ??
        row.lat ??
        row.Latitude ??
        row.LATITUDE
      );

    case "longitude":
      return (
        row.longitude ??
        row.lon ??
        row.lng ??
        row.Longitude ??
        row.LONGITUDE
      );

    case "x_coordinate":
      return row.x_coordinate ?? row.x;

    case "y_coordinate":
      return row.y_coordinate ?? row.y;

    case "sum_insured":
      return (
        row.sum_insured ??
        row.sumInsured ??
        row.SumInsured ??
        row.total_sum_insured ??
        row.tiv ??
        row["sum insured"] ??
        row["Sum Insured"]
      );

    case "property_type":
      return row.property_type ?? row.propertyType ?? row.type;

    case "height_m":
      return (
        row.height_m ??
        row.height ??
        row.height_max_m ??
        row.building_height_m
      );

    case "uprn":
      return row.uprn ?? row.UPRN;

    case "block_reference":
      return row.block_reference ?? row.blockReference;

    case "uprn_match_score":
      return row.uprn_match_score ?? row.match_score;

    default:
      return row[key];
  }
};

const looksLikeLatitude = (value) => {
  const n = Number(value);
  return Number.isFinite(n) && n >= -90 && n <= 90;
};

const looksLikeLongitude = (value) => {
  const n = Number(value);
  return Number.isFinite(n) && n >= -180 && n <= 180;
};

export function computeReadiness(row) {
  const missing = [];

  const address = get(row, "address_line_1");
  const postcode = get(row, "post_code");
  const city = get(row, "city");
  const sumInsured = get(row, "sum_insured");
  const propertyType = get(row, "property_type");
  const height = get(row, "height_m");
  const uprn = get(row, "uprn");
  const blockReference = get(row, "block_reference");
  const uprnMatchScore = toNumberOrNull(get(row, "uprn_match_score"));

  const directLat = toNumberOrNull(get(row, "latitude"));
  const directLon = toNumberOrNull(get(row, "longitude"));
  const fallbackY = toNumberOrNull(get(row, "y_coordinate"));
  const fallbackX = toNumberOrNull(get(row, "x_coordinate"));

  const lat = Number.isFinite(directLat)
    ? directLat
    : looksLikeLatitude(fallbackY)
    ? fallbackY
    : null;

  const lon = Number.isFinite(directLon)
    ? directLon
    : looksLikeLongitude(fallbackX)
    ? fallbackX
    : null;

  if (!isPresent(address)) missing.push("address_line_1");
  if (!isPresent(postcode)) missing.push("post_code");
  if (!isPresent(city)) missing.push("city");
  if (!Number.isFinite(lat)) missing.push("latitude");
  if (!Number.isFinite(lon)) missing.push("longitude");
  if (!isPresent(sumInsured)) missing.push("sum_insured");
  if (!isPresent(propertyType)) missing.push("property_type");
  if (!isPresent(height)) missing.push("height_m");

  let score = 100;

  const weights = {
    address_line_1: 10,
    post_code: 10,
    city: 8,
    latitude: 18,
    longitude: 18,
    sum_insured: 16,
    property_type: 10,
    height_m: 10,
  };

  missing.forEach((field) => {
    score -= weights[field] ?? 10;
  });

  if (isPresent(uprn)) score += 6;
  if (isPresent(blockReference)) score += 3;
  if (Number.isFinite(uprnMatchScore)) {
    if (uprnMatchScore >= 0.85) score += 6;
    else if (uprnMatchScore >= 0.65) score += 3;
  }

  score = Math.max(0, Math.min(100, Math.round(score)));

  return {
    score,
    missing,
    hasValidCoords: Number.isFinite(lat) && Number.isFinite(lon),
    hasUPRN: isPresent(uprn),
    hasBlockReference: isPresent(blockReference),
  };
}

export function readinessBand(score) {
  const n = Number(score) || 0;
  if (n >= 80) return "Green";
  if (n >= 50) return "Amber";
  return "Red";
}

export function readinessColor(scoreOrBand) {
  const text = String(scoreOrBand ?? "").toLowerCase();

  if (text.includes("green")) return "#22c55e";
  if (text.includes("amber") || text.includes("yellow")) return "#f59e0b";
  if (text.includes("red")) return "#ef4444";

  const numeric = Number(scoreOrBand);
  if (Number.isFinite(numeric)) {
    if (numeric >= 80) return "#22c55e";
    if (numeric >= 50) return "#f59e0b";
    return "#ef4444";
  }

  return "#64748b";
}