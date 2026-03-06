// src/utils/ingestion.js
/* eslint-disable no-useless-escape */

const UK_BOUNDS = {
  minLat: 49.0,
  maxLat: 61.0,
  minLon: -8.6,
  maxLon: 2.6,
};

const REQUIRED_FIELDS = [
  "address_line_1",
  "post_code",
  "city",
  "latitude",
  "longitude",
  "sum_insured",
  "property_type",
  "height_m",
];

const toSnake = (s) =>
  String(s || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^\w]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");

const normalizeHeader = (h) => {
  const key = toSnake(h);

  const ALIASES = {
    id: "id",
    property_id: "id",
    ref: "id",
    reference: "id",
    council_reference: "council_reference",
    council_ref: "council_reference",

    uprn: "uprn",
    u_p_r_n: "uprn",
    unique_property_reference_number: "uprn",
    unique_property_reference: "uprn",
    property_uprn: "uprn",
    asset_uprn: "uprn",

    address: "address_line_1",
    address1: "address_line_1",
    address_line1: "address_line_1",
    address_line_1: "address_line_1",
    address_1: "address_line_1",

    address2: "address_line_2",
    address_line2: "address_line_2",
    address_line_2: "address_line_2",
    address_2: "address_line_2",

    postcode: "post_code",
    post_code: "post_code",
    zip: "post_code",

    city: "city",
    town: "city",

    lat: "latitude",
    latitude: "latitude",
    lon: "longitude",
    long: "longitude",
    longitude: "longitude",

    suminsured: "sum_insured",
    sum_insured: "sum_insured",
    tsi: "sum_insured",
    total_sum_insured: "sum_insured",
    declared_value: "sum_insured",
    declared_value_with_full_vat: "sum_insured",

    propertytype: "property_type",
    property_type: "property_type",
    asset_type: "property_type",

    occupancy: "occupancy_type",
    occupancy_type: "occupancy_type",
    tenure: "occupancy_type",

    flats: "number_of_flats",
    number_of_flats: "number_of_flats",
    no_of_flats: "number_of_flats",

    height: "height_m",
    height_m: "height_m",
    building_height: "height_m",
    building_height_m: "height_m",

    year_built: "year_built",
    construction: "construction",
    construction_type: "construction",

    readiness_score: "readiness_score",
    readiness_band: "readiness_band",
  };

  return ALIASES[key] || key;
};

const parseNumber = (v) => {
  if (v === null || v === undefined) return null;
  const s = String(v).trim();
  if (!s) return null;

  const cleaned = s.replace(/[£$,]/g, "").replace(/\s/g, "");
  const x = Number(cleaned);
  return Number.isFinite(x) ? x : null;
};

const safeStr = (v) => {
  if (v === null || v === undefined) return "";
  return String(v).trim();
};

const isLikelyUkCoord = (lat, lon) => {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;
  return (
    lat >= UK_BOUNDS.minLat &&
    lat <= UK_BOUNDS.maxLat &&
    lon >= UK_BOUNDS.minLon &&
    lon <= UK_BOUNDS.maxLon
  );
};

const isPresent = (v) => {
  if (v === null || v === undefined) return false;
  if (typeof v === "string") return v.trim().length > 0;
  if (typeof v === "number") return Number.isFinite(v);
  return true;
};

const pct = (count, total) => {
  if (!total) return 0;
  return Math.round((count / total) * 100);
};

const computeReadiness = (obj) => {
  const missing = [];

  for (const k of REQUIRED_FIELDS) {
    const v = obj[k];
    const missingField =
      v === null ||
      v === undefined ||
      (typeof v === "string" && !v.trim()) ||
      (typeof v === "number" && !Number.isFinite(v));

    if (missingField) missing.push(k);
  }

  const total = REQUIRED_FIELDS.length;
  const score = Math.max(0, Math.round(100 * (1 - missing.length / total)));

  let band = "Red";
  if (score >= 80) band = "Green";
  else if (score >= 50) band = "Amber";

  return { score, band, missing };
};

const splitCsvLine = (line) => {
  const out = [];
  let cur = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];

    if (ch === '"' && line[i + 1] === '"') {
      cur += '"';
      i++;
      continue;
    }

    if (ch === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (ch === "," && !inQuotes) {
      out.push(cur);
      cur = "";
      continue;
    }

    cur += ch;
  }

  out.push(cur);
  return out.map((s) => s.trim());
};

const parseCsvText = (text) => {
  const lines = String(text || "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .filter((l) => l.trim().length > 0);

  if (lines.length < 2) return [];

  const headersRaw = splitCsvLine(lines[0]);
  const headers = headersRaw.map(normalizeHeader);

  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = splitCsvLine(lines[i]);
    const row = {};
    headers.forEach((h, idx) => {
      row[h] = cols[idx] ?? "";
    });
    rows.push(row);
  }

  return rows;
};

const parseXlsxFile = async (file) => {
  let XLSX;
  try {
    XLSX = await import("xlsx");
  } catch (e) {
    throw new Error("XLSX support requires the 'xlsx' package. Install it with: npm i xlsx");
  }

  const buf = await file.arrayBuffer();
  const wb = XLSX.read(buf, { type: "array" });

  const sheetName = wb.SheetNames?.[0];
  if (!sheetName) return [];

  const ws = wb.Sheets[sheetName];
  const grid = XLSX.utils.sheet_to_json(ws, { header: 1, raw: false });

  if (!grid || grid.length < 2) return [];

  const headersRaw = grid[0].map((h) => String(h || ""));
  const headers = headersRaw.map(normalizeHeader);

  const rows = [];
  for (let i = 1; i < grid.length; i++) {
    const arr = grid[i] || [];
    if (arr.every((x) => String(x ?? "").trim() === "")) continue;

    const row = {};
    headers.forEach((h, idx) => {
      row[h] = arr[idx] ?? "";
    });
    rows.push(row);
  }

  return rows;
};

const normalizeRow = (row, idx) => {
  const raw = { ...row };

  const id =
    safeStr(row.id) ||
    safeStr(row.council_reference) ||
    safeStr(row.property_reference) ||
    safeStr(row.uprn) ||
    `ROW-${idx + 1}`;

  const latitude = parseNumber(row.latitude);
  const longitude = parseNumber(row.longitude);
  const sumInsured = parseNumber(row.sum_insured);
  const heightM = parseNumber(row.height_m);
  const uprn = safeStr(row.uprn);

  const base = {
    id,
    uprn,
    council_reference: safeStr(row.council_reference),

    address_line_1: safeStr(row.address_line_1),
    address_line_2: safeStr(row.address_line_2),
    city: safeStr(row.city),
    post_code: safeStr(row.post_code),

    latitude,
    longitude,

    sum_insured: sumInsured,
    property_type: safeStr(row.property_type),
    occupancy_type: safeStr(row.occupancy_type),
    number_of_flats: parseNumber(row.number_of_flats),

    height_m: heightM,
    year_built: parseNumber(row.year_built),
    construction: safeStr(row.construction),
  };

  const providedScore = parseNumber(row.readiness_score);
  const providedBand = safeStr(row.readiness_band);

  let readiness = computeReadiness(base);

  if (Number.isFinite(providedScore)) {
    const score = Math.max(0, Math.min(100, Math.round(providedScore)));
    let band = "Red";
    if (score >= 80) band = "Green";
    else if (score >= 50) band = "Amber";

    readiness = {
      score,
      band: providedBand || band,
      missing: readiness.missing,
    };
  } else if (providedBand) {
    readiness = { ...readiness, band: providedBand };
  }

  const hasValidCoords = isLikelyUkCoord(latitude, longitude);

  return {
    ...base,
    readiness_score: readiness.score,
    readiness_band: readiness.band,
    missing_fields: readiness.missing,
    hasValidCoords,
    raw,
  };
};

export const parsePortfolioFile = async (file, onSuccess, onError) => {
  try {
    const name = file?.name || "upload";
    const lower = name.toLowerCase();

    let rows = [];
    if (lower.endsWith(".csv")) {
      const text = await file.text();
      rows = parseCsvText(text);
    } else if (lower.endsWith(".xlsx") || lower.endsWith(".xls")) {
      rows = await parseXlsxFile(file);
    } else {
      throw new Error("Unsupported file type. Please upload a CSV or XLSX.");
    }

    const properties = rows.map((r, i) => normalizeRow(r, i));
    const skipped = properties.filter((p) => !p.hasValidCoords).length;

    onSuccess?.({
      sourceName: name,
      properties,
      stats: {
        rowCount: properties.length,
        mappableCount: properties.length - skipped,
        skippedInvalidCoords: skipped,
        totalValue: properties.reduce((s, p) => s + (p.sum_insured || 0), 0),
      },
    });
  } catch (e) {
    onError?.(e?.message || String(e));
  }
};

const avg = (nums) => {
  const list = (nums || []).filter((n) => Number.isFinite(Number(n))).map(Number);
  if (!list.length) return null;
  return list.reduce((a, b) => a + b, 0) / list.length;
};

export const getIngestionSummary = (ingestionResult) => {
  if (!ingestionResult?.properties) return null;

  const props = ingestionResult.properties;
  const total = props.length;

  const totalValue = props.reduce((s, p) => s + (p.sum_insured || 0), 0);
  const skippedInvalidCoords = ingestionResult.stats?.skippedInvalidCoords ?? 0;
  const mappableCount = ingestionResult.stats?.mappableCount ?? 0;

  const avgReadinessRaw = avg(props.map((p) => p.readiness_score));
  const avgReadiness = Number.isFinite(avgReadinessRaw) ? Math.round(avgReadinessRaw) : 0;

  const uprnMatchedCount = props.filter((p) => isPresent(p.uprn)).length;
  const uprnMatchPct = pct(uprnMatchedCount, total);

  // Address completeness: address line 1 + postcode + city all present
  const addressCompleteCount = props.filter(
    (p) =>
      isPresent(p.address_line_1) &&
      isPresent(p.post_code) &&
      isPresent(p.city)
  ).length;
  const addrCompletenessPct = pct(addressCompleteCount, total);

  // Geo completeness: valid lat/lon in UK bounds
  const geoCompletenessPct = pct(mappableCount, total);

  // SOV completeness: sum insured + property type + height present
  const sovCompleteCount = props.filter(
    (p) =>
      isPresent(p.sum_insured) &&
      isPresent(p.property_type) &&
      isPresent(p.height_m)
  ).length;
  const sovCompletenessPct = pct(sovCompleteCount, total);

  const missingCore = props.filter((p) => (p.missing_fields || []).length > 0).length;

  return {
    source: ingestionResult.sourceName,
    propertyCount: total,
    mappableCount,
    skippedInvalidCoords,
    totalValue,
    missingCore,

    avgReadiness,
    uprnMatchedCount,
    uprnMatchPct,

    addrCompletenessPct,
    geoCompletenessPct,
    sovCompletenessPct,
  };
};

export const getPortfolioSnapshot = (ingestionResult) => {
  if (!ingestionResult?.properties) return null;

  const props = ingestionResult.properties;
  const total = props.reduce((s, p) => s + (p.sum_insured || 0), 0);

  return {
    source: ingestionResult.sourceName,
    propertyCount: props.length,
    totalValue: total,
    missingCore: props.filter(
      (p) => !p.post_code || !p.address_line_1 || !p.sum_insured
    ).length,
  };
};
