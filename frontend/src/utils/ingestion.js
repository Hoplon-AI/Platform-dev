// src/utils/ingestion.js

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
  "sum_insured",
];

const toSnake = (value) =>
  String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^\w]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");

const normalizeHeader = (header) => {
  const key = toSnake(header);

  const aliases = {
    id: "id",
    property_id: "property_id",
    propertyid: "property_id",
    property_reference: "property_reference",
    propertyreference: "property_reference",
    reference: "property_reference",
    ref: "property_reference",
    council_reference: "property_reference",
    council_ref: "property_reference",

    uprn: "uprn",
    u_p_r_n: "uprn",
    unique_property_reference_number: "uprn",
    unique_property_reference: "uprn",
    parent_uprn: "parent_uprn",
    parentuprn: "parent_uprn",

    block_reference: "block_reference",
    blockreference: "block_reference",
    block_name: "block_reference",
    blockname: "block_reference",

    address: "address_line_1",
    property_address: "address_line_1",
    address1: "address_line_1",
    address_line1: "address_line_1",
    address_line_1: "address_line_1",
    address_1: "address_line_1",

    address2: "address_line_2",
    address_line2: "address_line_2",
    address_line_2: "address_line_2",
    address_2: "address_line_2",

    address3: "address_3",
    address_line3: "address_3",
    address_line_3: "address_3",
    address_3: "address_3",

    city: "city",
    town: "city",
    locality: "city",

    postcode: "post_code",
    post_code: "post_code",
    zip: "post_code",

    latitude: "latitude",
    lat: "latitude",
    y_coordinate: "y_coordinate",
    y: "y_coordinate",

    longitude: "longitude",
    lon: "longitude",
    lng: "longitude",
    long: "longitude",
    x_coordinate: "x_coordinate",
    x: "x_coordinate",

    suminsured: "sum_insured",
    sum_insured: "sum_insured",
    total_sum_insured: "sum_insured",
    declared_value: "sum_insured",
    declared_value_with_full_vat: "sum_insured",
    tiv: "sum_insured",

    propertytype: "property_type",
    property_type: "property_type",
    type: "property_type",
    asset_type: "property_type",

    occupancy: "occupancy_type",
    occupancy_type: "occupancy_type",
    tenure: "occupancy_type",

    height: "height_m",
    height_m: "height_m",
    building_height: "height_m",
    building_height_m: "height_m",
    height_max_m: "height_m",

    storeys: "storeys",
    max_storeys: "storeys",
    floors: "storeys",
    numberoffloors: "storeys",

    units: "units",
    unit_count: "units",
    number_of_flats: "units",
    flats: "units",
    no_of_flats: "units",

    year_built: "year_of_build",
    year_of_build: "year_of_build",
    yearbuilt: "year_of_build",

    wall_construction: "wall_construction",
    roof_construction: "roof_construction",

    readiness_score: "readiness_score",
    readiness_band: "readiness_band",

    uprn_match_score: "uprn_match_score",
    match_score: "uprn_match_score",
    uprn_match_description: "uprn_match_description",
    match_description: "uprn_match_description",
  };

  return aliases[key] || key;
};

const safeStr = (value) => {
  if (value === null || value === undefined) return "";
  return String(value).trim();
};

const parseNumber = (value) => {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim();
  if (!raw) return null;

  const cleaned = raw.replace(/[£,$,\s]/g, "");
  const parsed = Number(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
};

const isPresent = (value) => {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (typeof value === "number") return Number.isFinite(value);
  return true;
};

const pct = (count, total) => {
  if (!total) return 0;
  return Math.round((count / total) * 100);
};

const looksLikeLatitude = (value) => {
  const n = Number(value);
  return Number.isFinite(n) && n >= -90 && n <= 90;
};

const looksLikeLongitude = (value) => {
  const n = Number(value);
  return Number.isFinite(n) && n >= -180 && n <= 180;
};

const isWithinUkBounds = (lat, lon) => {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;

  return (
    lat >= UK_BOUNDS.minLat &&
    lat <= UK_BOUNDS.maxLat &&
    lon >= UK_BOUNDS.minLon &&
    lon <= UK_BOUNDS.maxLon
  );
};

const computeReadiness = (property) => {
  const missing = [];

  for (const field of REQUIRED_FIELDS) {
    if (!isPresent(property[field])) {
      missing.push(field);
    }
  }

  const hasCoords = Number.isFinite(property.latitude) && Number.isFinite(property.longitude);
  if (!hasCoords) {
    missing.push("latitude");
    missing.push("longitude");
  }

  if (!isPresent(property.property_type)) {
    missing.push("property_type");
  }

  if (!isPresent(property.height_m)) {
    missing.push("height_m");
  }

  const uniqueMissing = [...new Set(missing)];

  const totalChecks = 7;
  const score = Math.max(
    0,
    Math.round(((totalChecks - uniqueMissing.length) / totalChecks) * 100)
  );

  let band = "Red";
  if (score >= 80) band = "Green";
  else if (score >= 50) band = "Amber";

  return {
    score,
    band,
    missing: uniqueMissing,
  };
};

const splitCsvLine = (line) => {
  const result = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];

    if (char === '"' && line[i + 1] === '"') {
      current += '"';
      i += 1;
      continue;
    }

    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (char === "," && !inQuotes) {
      result.push(current);
      current = "";
      continue;
    }

    current += char;
  }

  result.push(current);
  return result.map((item) => item.trim());
};

const parseCsvText = (text) => {
  const lines = String(text ?? "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .filter((line) => line.trim().length > 0);

  if (lines.length < 2) return [];

  const rawHeaders = splitCsvLine(lines[0]);
  const headers = rawHeaders.map(normalizeHeader);

  const rows = [];

  for (let i = 1; i < lines.length; i += 1) {
    const columns = splitCsvLine(lines[i]);
    const row = {};

    headers.forEach((header, index) => {
      row[header] = columns[index] ?? "";
    });

    rows.push(row);
  }

  return rows;
};

const parseXlsxFile = async (file) => {
  let XLSX;
  try {
    XLSX = await import("xlsx");
  } catch {
    throw new Error("Missing xlsx package. Run: npm install xlsx");
  }

  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const firstSheet = workbook.SheetNames?.[0];

  if (!firstSheet) return [];

  const worksheet = workbook.Sheets[firstSheet];
  const grid = XLSX.utils.sheet_to_json(worksheet, { header: 1, raw: false });

  if (!Array.isArray(grid) || grid.length < 2) return [];

  const rawHeaders = (grid[0] || []).map((header) => String(header ?? ""));
  const headers = rawHeaders.map(normalizeHeader);

  const rows = [];

  for (let i = 1; i < grid.length; i += 1) {
    const line = grid[i] || [];
    if (line.every((cell) => String(cell ?? "").trim() === "")) continue;

    const row = {};
    headers.forEach((header, index) => {
      row[header] = line[index] ?? "";
    });

    rows.push(row);
  }

  return rows;
};

const normalizeLocalRow = (row, index) => {
  const raw = { ...row };

  const directLatitude = parseNumber(row.latitude);
  const directLongitude = parseNumber(row.longitude);
  const fallbackY = parseNumber(row.y_coordinate);
  const fallbackX = parseNumber(row.x_coordinate);

  const latitude =
    directLatitude ??
    (looksLikeLatitude(fallbackY) ? fallbackY : null);

  const longitude =
    directLongitude ??
    (looksLikeLongitude(fallbackX) ? fallbackX : null);

  const hasValidCoords = isWithinUkBounds(latitude, longitude);

  const property = {
    id:
      safeStr(row.id) ||
      safeStr(row.property_id) ||
      safeStr(row.property_reference) ||
      safeStr(row.uprn) ||
      `ROW-${index + 1}`,

    property_id: safeStr(row.property_id),
    property_reference: safeStr(row.property_reference),

    address_line_1: safeStr(row.address_line_1),
    address_line_2: safeStr(row.address_line_2),
    address_3: safeStr(row.address_3),
    city: safeStr(row.city),
    post_code: safeStr(row.post_code),

    uprn: safeStr(row.uprn),
    parent_uprn: safeStr(row.parent_uprn),
    block_reference: safeStr(row.block_reference),

    latitude: hasValidCoords ? latitude : null,
    longitude: hasValidCoords ? longitude : null,
    x_coordinate: fallbackX,
    y_coordinate: fallbackY,
    hasValidCoords,

    sum_insured: parseNumber(row.sum_insured),
    property_type: safeStr(row.property_type),
    occupancy_type: safeStr(row.occupancy_type),
    height_m: parseNumber(row.height_m),
    storeys: parseNumber(row.storeys),
    units: parseNumber(row.units),
    year_of_build: parseNumber(row.year_of_build),

    wall_construction: safeStr(row.wall_construction),
    roof_construction: safeStr(row.roof_construction),

    uprn_match_score: parseNumber(row.uprn_match_score),
    uprn_match_description: safeStr(row.uprn_match_description),

    raw,
  };

  const providedReadinessScore = parseNumber(row.readiness_score);
  const providedReadinessBand = safeStr(row.readiness_band);
  const computedReadiness = computeReadiness(property);

  property.readiness_score = Number.isFinite(providedReadinessScore)
    ? Math.max(0, Math.min(100, Math.round(providedReadinessScore)))
    : computedReadiness.score;

  property.readiness_band =
    providedReadinessBand || computedReadiness.band;

  property.missing_fields = computedReadiness.missing;

  return property;
};

export const parsePortfolioFile = async (file, onSuccess, onError) => {
  try {
    const fileName = file?.name || "upload";
    const lower = fileName.toLowerCase();

    let rows = [];

    if (lower.endsWith(".csv")) {
      const text = await file.text();
      rows = parseCsvText(text);
    } else if (lower.endsWith(".xlsx") || lower.endsWith(".xls")) {
      rows = await parseXlsxFile(file);
    } else {
      throw new Error("Unsupported file type. Please upload a CSV, XLSX, or XLS file.");
    }

    const properties = rows.map((row, index) => normalizeLocalRow(row, index));
    const mappableCount = properties.filter((property) => property.hasValidCoords).length;
    const skippedInvalidCoords = properties.length - mappableCount;

    onSuccess?.({
      sourceName: fileName,
      properties,
      stats: {
        rowCount: properties.length,
        mappableCount,
        skippedInvalidCoords,
        totalValue: properties.reduce(
          (sum, property) => sum + (property.sum_insured || 0),
          0
        ),
      },
    });
  } catch (error) {
    onError?.(error?.message || String(error));
  }
};

const average = (values) => {
  const numeric = (values || [])
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value));

  if (!numeric.length) return null;
  return numeric.reduce((sum, value) => sum + value, 0) / numeric.length;
};

export const getIngestionSummary = (ingestionResult) => {
  if (!ingestionResult) return null;

  const properties = Array.isArray(ingestionResult.properties)
    ? ingestionResult.properties
    : [];

  const total = properties.length;

  const backendSummary = ingestionResult.summary || ingestionResult.raw?.summary || null;
  const stats = ingestionResult.stats || {};

  const mappableCount =
    Number.isFinite(Number(stats.mappableCount))
      ? Number(stats.mappableCount)
      : properties.filter((property) => property.hasValidCoords).length;

  const skippedInvalidCoords =
    Number.isFinite(Number(stats.skippedInvalidCoords))
      ? Number(stats.skippedInvalidCoords)
      : Math.max(0, total - mappableCount);

  const totalValue =
    Number.isFinite(Number(stats.totalValue))
      ? Number(stats.totalValue)
      : properties.reduce(
          (sum, property) => sum + (Number(property.sum_insured) || 0),
          0
        );

  const avgReadinessRaw = average(properties.map((property) => property.readiness_score));
  const avgReadiness = Number.isFinite(avgReadinessRaw)
    ? Math.round(avgReadinessRaw)
    : 0;

  const uprnMatchedCount = properties.filter((property) => isPresent(property.uprn)).length;
  const uprnMatchPct = pct(uprnMatchedCount, total);

  const addressCompleteCount = properties.filter(
    (property) =>
      isPresent(property.address_line_1) &&
      isPresent(property.post_code) &&
      isPresent(property.city)
  ).length;
  const addrCompletenessPct = pct(addressCompleteCount, total);

  const geoCompletenessPct = pct(mappableCount, total);

  const sovCompleteCount = properties.filter(
    (property) =>
      isPresent(property.sum_insured) &&
      isPresent(property.property_type) &&
      isPresent(property.height_m)
  ).length;
  const sovCompletenessPct = pct(sovCompleteCount, total);

  const missingCore = properties.filter(
    (property) => Array.isArray(property.missing_fields) && property.missing_fields.length > 0
  ).length;

  const enrichedCount = properties.filter(
    (property) =>
      isPresent(property.uprn) ||
      isPresent(property.parent_uprn) ||
      isPresent(property.block_reference) ||
      isPresent(property.uprn_match_score)
  ).length;

  const blockCount = new Set(
    properties
      .map((property) => property.block_reference)
      .filter((value) => isPresent(value))
  ).size;

  const summary = {
    source:
      ingestionResult.source ||
      ingestionResult.sourceName ||
      ingestionResult.raw?.filename ||
      "Upload",

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

    enrichedCount,
    blockCount,

    backend: backendSummary,
  };

  if (backendSummary && typeof backendSummary === "object") {
    summary.processingReport = backendSummary;
  }

  return summary;
};

export const getPortfolioSnapshot = (ingestionResult) => {
  const summary = getIngestionSummary(ingestionResult);
  if (!summary) return null;

  return {
    source: summary.source,
    propertyCount: summary.propertyCount,
    totalValue: summary.totalValue,
    missingCore: summary.missingCore,
    avgReadiness: summary.avgReadiness,
    blockCount: summary.blockCount,
  };
};