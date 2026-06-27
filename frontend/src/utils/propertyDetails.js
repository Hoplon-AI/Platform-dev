// Pure helper functions for PropertyDetails (formatting, normalisation, extraction).

export const fmt = (n, digits = 2) => {
  const x = Number(n);
  return Number.isFinite(x) ? x.toFixed(digits) : "—";
};

export const fmtMoney = (n, digits = 0) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  return `£${x.toLocaleString("en-GB", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })}`;
};

export const toNumberOrNull = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

export const isPresent = (value) => {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "boolean") return true;
  if (Array.isArray(value)) return value.length > 0;
  return true;
};

export const asArray = (value) => {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value === "string") return value.trim() ? [value.trim()] : [];
  return [value];
};

export const truncate = (value, maxLength = 140) => {
  const text = String(value ?? "").trim();
  if (!text) return "—";
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
};

export const bandMeta = (bandOrScore) => {
  const text = String(bandOrScore ?? "").toLowerCase();

  if (
    text.includes("green") ||
    text.includes("low risk") ||
    text.includes("low") ||
    text.includes("acceptable") ||
    text.includes("broadly acceptable")
  ) {
    return { label: "Low Risk", cls: "band-green" };
  }
  if (
    text.includes("amber") ||
    text.includes("yellow") ||
    text.includes("medium") ||
    text.includes("moderate") ||
    text.includes("tolerable")
  ) {
    return { label: "Medium Risk", cls: "band-yellow" };
  }
  if (
    text.includes("red") ||
    text.includes("high risk") ||
    text.includes("high") ||
    text.includes("intolerable") ||
    text.includes("not acceptable")
  ) {
    return { label: "High Risk", cls: "band-red" };
  }

  const numeric = Number(bandOrScore);
  if (Number.isFinite(numeric)) {
    if (numeric >= 80) return { label: "Low Risk", cls: "band-green" };
    if (numeric >= 50) return { label: "Medium Risk", cls: "band-yellow" };
    return { label: "High Risk", cls: "band-red" };
  }

  return { label: "Unknown", cls: "band-muted" };
};

export const getDisplayAddress = (property) => {
  const line1 =
    property?.address_line_1 ??
    property?.address1 ??
    property?.address ??
    property?.property_address ??
    "—";

  const line2 =
    property?.address_line_2 ??
    property?.address2 ??
    property?.address_2 ??
    "";

  const city =
    property?.city ??
    property?.town ??
    property?.locality ??
    property?.address_3 ??
    "";

  const postcode =
    property?.post_code ??
    property?.postcode ??
    property?.zip ??
    "";

  return { line1, line2, city, postcode };
};

export const getLatLon = (property) => {
  const directLat =
    toNumberOrNull(property?.latitude) ??
    toNumberOrNull(property?.lat) ??
    toNumberOrNull(property?.__lat);

  const directLon =
    toNumberOrNull(property?.longitude) ??
    toNumberOrNull(property?.lon) ??
    toNumberOrNull(property?.lng) ??
    toNumberOrNull(property?.__lon);

  const fallbackY =
    toNumberOrNull(property?.y_coordinate) ??
    toNumberOrNull(property?.y);

  const fallbackX =
    toNumberOrNull(property?.x_coordinate) ??
    toNumberOrNull(property?.x);

  const lat = directLat ?? fallbackY;
  const lon = directLon ?? fallbackX;

  const validLat = Number.isFinite(lat) && lat !== 0;
  const validLon = Number.isFinite(lon) && lon !== 0;

  return {
    lat: validLat ? lat : null,
    lon: validLon ? lon : null,
  };
};

export const getSovValues = (property) => {
  return {
    sumInsured:
      toNumberOrNull(property?.sum_insured) ??
      toNumberOrNull(property?.sumInsured) ??
      toNumberOrNull(property?.total_sum_insured) ??
      toNumberOrNull(property?.tiv),

    propertyType:
      property?.property_type ??
      property?.propertyType ??
      property?.type ??
      "—",

    occupancy:
      property?.occupancy_type ??
      property?.occupancyType ??
      property?.occupancy ??
      "—",

    height:
      toNumberOrNull(property?.height_m) ??
      toNumberOrNull(property?.height) ??
      toNumberOrNull(property?.height_max_m) ??
      toNumberOrNull(property?.building_height_m),

    storeys:
      toNumberOrNull(property?.storeys) ??
      toNumberOrNull(property?.max_storeys),

    units:
      toNumberOrNull(property?.units) ??
      toNumberOrNull(property?.unit_count) ??
      toNumberOrNull(property?.number_of_flats),

    yearBuilt:
      toNumberOrNull(property?.year_of_build) ??
      toNumberOrNull(property?.year_built),
  };
};

export const normaliseFireDoc = (doc, type) => {
  if (!doc) return null;

  const raw = doc.raw && typeof doc.raw === "object" ? doc.raw : {};
  const merged = { ...raw, ...doc };

  return {
    ...merged,
    document_type: String(merged.document_type ?? type ?? "").toUpperCase(),
    risk_level:
      merged.risk_level ??
      merged.rag_status ??
      merged.raw_rating ??
      merged.overall_risk_rating ??
      merged.risk_rating ??
      merged.external_wall_risk ??
      merged.building_risk_rating ??
      null,
    summary:
      merged.summary ??
      merged.executive_summary ??
      merged.overview ??
      merged.findings_summary ??
      merged.significant_findings_summary ??
      "",
    recommendations:
      merged.recommendations ??
      merged.actions ??
      merged.action_items ??
      merged.remedial_actions ??
      merged.significant_findings ??
      [],
    feature_id: merged.feature_id ?? merged.id ?? merged.document_id ?? null,
    upload_id: merged.upload_id ?? null,
    filename: merged.filename ?? merged.source_filename ?? "Uploaded PDF",
  };
};

export const getFireAssessment = (source) => {
  const fra = normaliseFireDoc(
    source?.latest_fra ??
      source?.fire_documents?.fra ??
      source?.fire_documents?.FRA ??
      source?.fra ??
      null,
    "FRA"
  );

  const fraew = normaliseFireDoc(
    source?.latest_fraew ??
      source?.fire_documents?.fraew ??
      source?.fire_documents?.FRAEW ??
      source?.fraew ??
      null,
    "FRAEW"
  );

  const all = [
    ...asArray(source?.fire_documents?.all),
    ...asArray(source?.fire_documents?.documents),
    ...asArray(source?.fire_documents),
  ]
    .filter((item) => typeof item === "object" && item !== null)
    .map((item) => normaliseFireDoc(item, item.document_type));

  return {
    fra,
    fraew,
    all,
    hasAny: Boolean(fra || fraew || all.length),
  };
};

export const normaliseBooleanLabel = (value, yes = "Yes", no = "No") => {
  if (value === true) return yes;
  if (value === false) return no;
  if (typeof value === "string") {
    const lower = value.trim().toLowerCase();
    if (["true", "yes", "y", "1", "required", "present"].includes(lower)) return yes;
    if (["false", "no", "n", "0", "not required", "absent"].includes(lower)) return no;
  }
  return "—";
};

export const normaliseFraActions = (fra) => {
  const actions = asArray(fra?.recommendations ?? fra?.actions ?? fra?.action_items);

  return {
    total: fra?.total_actions ?? fra?.total_action_count ?? (actions.length || "—"),
    overdue: fra?.overdue_actions ?? fra?.overdue_action_count ?? "—",
    outstanding:
      fra?.outstanding_actions ?? fra?.outstanding_action_count ?? "—",
    items: actions,
  };
};

export const getFraewHeight = (fraew) =>
  toNumberOrNull(fraew?.building_height_m) ??
  toNumberOrNull(fraew?.building_height) ??
  toNumberOrNull(fraew?.height_m);

export const prettyText = (s) =>
  isPresent(s) ? String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "—";

// Worse of the FRA / FRAEW band, for the block-level overall badge.
export const worstBandMeta = (fra, fraew) => {
  const rank = { "band-red": 3, "band-amber": 2, "band-yellow": 2, "band-green": 1, "band-muted": 0 };
  const a = bandMeta(fra?.risk_level ?? fra?.rag_status ?? fra?.raw_rating);
  const b = bandMeta(fraew?.risk_level ?? fraew?.rag_status ?? fraew?.raw_rating ?? fraew?.building_risk_rating);
  return (rank[a.cls] ?? 0) >= (rank[b.cls] ?? 0) ? a : b;
};

// Action items are objects; show a CONCISE label in this compact side panel
// (issue ref + hazard category for FRA; a short action snippet for FRAEW). The
// full text lives on the Block Analysis page. Never stringify the raw object.
export const actionLabelShort = (item) => {
  if (typeof item === "string") return truncate(item, 90);
  if (!item || typeof item !== "object") return "";
  // Lead with the hazard category — meaningful to an underwriter at a glance.
  // The assessor's internal issue_ref (e.g. CPFS-01BR-001) is kept on the
  // Block Analysis detail cards, not here.
  if (item.hazard_type) return String(item.hazard_type);
  // FRAEW actions only have a long description — truncate hard.
  const text = item.action ?? item.description ?? item.finding ?? item.recommendation ?? "";
  return truncate(text, 90);
};
