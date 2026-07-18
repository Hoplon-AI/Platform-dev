// Block data + risk model helpers for the Block Analysis page.
// Mirrors the client-side block assembly used by PortfolioDashboard so the
// page works off already-loaded portfolio data (no extra backend dependency).

// ---------- formatting ----------

export const isPresent = (v) =>
  v !== null && v !== undefined && !(typeof v === "string" && v.trim() === "");

export const fmtMoney = (n) => {
  const num = Number(n);
  if (!Number.isFinite(num)) return "—";
  return num.toLocaleString("en-GB", { maximumFractionDigits: 0 });
};

export const fmt = (n, dp = 1) => {
  const num = Number(n);
  if (!Number.isFinite(num)) return "—";
  return num.toFixed(dp);
};

export const titleCase = (s) =>
  isPresent(s)
    ? String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : "—";

// Strip a leading "Flat 3, " / "Apartment 2, " so the street reads cleanly.
export const cleanAddress = (s) =>
  isPresent(s)
    ? String(s).replace(/^(flat|apartment|unit|apt)[^,]*,\s*/i, "").trim()
    : "";

export const boolLabel = (v, yes = "Yes", no = "No") => {
  if (v === true || v === "true" || v === 1 || v === "yes") return yes;
  if (v === false || v === "false" || v === 0 || v === "no") return no;
  return "—";
};

// "good" | "bad" | "unknown" — used to colour present/absent risk chips.
export const boolTone = (v) => {
  if (v === true || v === "true" || v === 1 || v === "yes") return "yes";
  if (v === false || v === "false" || v === 0 || v === "no") return "no";
  return "unknown";
};

const normaliseKey = (value) =>
  isPresent(value) ? String(value).trim().toLowerCase() : "";

const hasValidLatLon = (lat, lon) => {
  const la = Number(lat);
  const lo = Number(lon);
  return Number.isFinite(la) && Number.isFinite(lo) && (la !== 0 || lo !== 0);
};

// ---------- RAG / fire-risk bands ----------

export const getFireDocumentRisk = (doc) =>
  doc?.risk_level ??
  doc?.rag_status ??
  doc?.raw_rating ??
  doc?.external_wall_risk ??
  doc?.building_risk_rating ??
  doc?.overall_risk_rating ??
  doc?.risk_rating ??
  null;

export const getFireRiskBand = (doc) => {
  if (!doc) return "Unknown";
  const text = String(getFireDocumentRisk(doc) ?? "").toLowerCase();
  if (!text) return "Unknown";
  if (
    text.includes("red") ||
    text.includes("high") ||
    text.includes("intolerable") ||
    text.includes("not acceptable") ||
    text.includes("substantial")
  )
    return "Red";
  if (
    text.includes("amber") ||
    text.includes("medium") ||
    text.includes("moderate") ||
    text.includes("tolerable")
  )
    return "Amber";
  if (
    text.includes("green") ||
    text.includes("low") ||
    text.includes("acceptable") ||
    text.includes("broadly acceptable") ||
    text.includes("negligible")
  )
    return "Green";
  return "Unknown";
};

const BAND_RANK = { Red: 3, Amber: 2, Green: 1, Unknown: 0 };

export const worstBand = (...bands) =>
  bands.reduce(
    (worst, b) => (BAND_RANK[b] > BAND_RANK[worst] ? b : worst),
    "Unknown"
  );

export const bandVerdict = (band) =>
  ({
    Red: "High risk",
    Amber: "Medium risk",
    Green: "Low risk",
    Unknown: "Unassessed",
  }[band] || "Unassessed");

// CSS class from global.css (.band-red / .band-amber / .band-green / .band-muted)
export const bandClass = (band) =>
  ({
    Red: "band-red",
    Amber: "band-amber",
    Green: "band-green",
    Unknown: "band-muted",
  }[band] || "band-muted");

// ---------- actions ----------

const asActionArray = (raw) => {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [raw];
    } catch {
      return [raw];
    }
  }
  return [];
};

// Prefer denormalised counts on the doc; otherwise compute from action_items.
// Works for both FRA (action_items) and FRAEW (remedial_actions).
export const fraActionStats = (fra) => {
  const empty = { total: 0, overdue: 0, noDate: 0, high: 0, outstanding: 0, items: [] };
  if (!fra) return empty;

  const raw = asActionArray(
    fra.action_items ?? fra.remedial_actions ?? fra.actions ?? fra.recommendations ?? fra.significant_findings
  );
  const items = raw.map((it) => (typeof it === "string" ? { description: it } : it || {}));

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const status = (a) => String(a.status ?? "").toLowerCase();

  return {
    total: fra.total_action_count ?? items.length,
    overdue:
      fra.overdue_action_count ??
      items.filter(
        (a) => a.due_date && new Date(a.due_date) < today && status(a) !== "completed"
      ).length,
    noDate: fra.no_date_action_count ?? items.filter((a) => !a.due_date).length,
    high:
      fra.high_priority_action_count ??
      items.filter((a) => String(a.priority ?? "").toLowerCase() === "high").length,
    outstanding:
      fra.outstanding_action_count ??
      items.filter((a) => ["outstanding", "overdue"].includes(status(a))).length,
    items,
  };
};

export const actionLabel = (a) => {
  if (typeof a === "string") return a;
  return (
    a?.description ??
    a?.action ??
    a?.finding ??
    a?.issue_ref ??
    a?.recommendation ??
    "Action"
  );
};

// ---------- FRAEW wall types ----------

export const getWallTypes = (fraew) => {
  let wt = fraew?.wall_types;
  if (typeof wt === "string") {
    try {
      wt = JSON.parse(wt);
    } catch {
      return [];
    }
  }
  return Array.isArray(wt) ? wt : [];
};

// ---------- height ----------

// Descriptive height band. Scotland has a single 11m high-rise threshold, so
// everything 11m+ collapses to one band; England & Wales keep the 11m/18m/30m splits.
export const heightCategory = (m, isScot = false) => {
  const h = Number(m);
  if (!Number.isFinite(h) || h <= 0) return null;
  if (h < 11) return "Under 11m";
  if (isScot) return "11m+ (high-rise)";
  if (h < 18) return "11–18m";
  if (h < 30) return "18–30m";
  return "Over 30m";
};

// ---------- fire document collection (streamlined) ----------

const normaliseFireDoc = (payload, idx = 0) => {
  if (!payload) return null;
  const fp = payload.fire_risk_payload ?? payload;
  const documentType = String(fp.document_type ?? payload.document_type ?? "").toUpperCase();
  const fra = fp.fra ?? null;
  const fraew = fp.fraew ?? null;
  const primary = documentType === "FRAEW" ? fraew : fra || fraew || fp;
  const riskLevel = getFireDocumentRisk(primary);

  return {
    id: fp.id ?? fp.upload_id ?? fp.feature_id ?? `${documentType || "FIRE"}-${idx + 1}`,
    upload_id: fp.upload_id ?? payload.upload_id ?? "",
    feature_id: fp.feature_id ?? payload.feature_id ?? "",
    filename: fp.filename ?? payload.filename ?? "Uploaded PDF",
    document_type: documentType || "FIRE",
    block_reference: fp.block_reference ?? fp.block_id ?? payload.block_reference ?? payload.block_id ?? "",
    property_id: fp.property_id ?? payload.property_id ?? "",
    risk_level: riskLevel,
    rag_status: riskLevel,
    summary: (() => {
      const txt = primary?.summary ?? primary?.executive_summary ?? primary?.findings_summary ?? primary?.interim_measures_detail ?? null;
      if (txt) return txt;
      const parts = [];
      if (primary?.risk_rating) parts.push(`Risk rating: ${primary.risk_rating}.`);
      if (primary?.building_risk_rating) parts.push(`Building risk: ${primary.building_risk_rating}.`);
      if (primary?.evacuation_strategy) parts.push(`Evacuation: ${primary.evacuation_strategy.replace(/_/g, " ")}.`);
      if (primary?.total_action_count) {
        const overdue = primary.overdue_action_count ? ` (${primary.overdue_action_count} overdue)` : "";
        parts.push(`${primary.total_action_count} action item(s)${overdue}.`);
      }
      if (primary?.has_combustible_cladding) parts.push("Combustible cladding present.");
      return parts.length > 0 ? parts.join(" ") : "";
    })(),
    fra,
    fraew,
    raw: fp,
  };
};

export const collectFireDocuments = (ingestionResult, latestFireRiskPayload = null) => {
  const source = Array.isArray(ingestionResult?.fire_documents)
    ? ingestionResult.fire_documents
    : Array.isArray(ingestionResult?.raw?.fire_documents)
    ? ingestionResult.raw.fire_documents
    : [];

  const docs = source.map((item, i) => normaliseFireDoc(item, i)).filter(Boolean);
  const latest = normaliseFireDoc(latestFireRiskPayload, docs.length);
  if (latest) docs.unshift(latest);

  // Dedup by upload_id (identical across the upload + API sources); feature_id is
  // unreliable (API returns fra_id AS feature_id). Prefix with document_type so an
  // FRA and FRAEW never collide. Fall back to block+filename only when no id.
  const seen = new Set();
  return docs.filter((doc) => {
    const idPart =
      normaliseKey(doc.upload_id) ||
      normaliseKey(doc.feature_id) ||
      [doc.block_reference, doc.filename].map(normaliseKey).join("~");
    const key = `${normaliseKey(doc.document_type)}|${idPart}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

// ---------- block assembly ----------

export const buildBlocks = (properties = [], fireDocuments = []) => {
  if (!properties.length) return [];

  const grouped = new Map();
  properties.forEach((p) => {
    const key = p.block_reference || p.parent_uprn || p.uprn || p.property_reference || p.id;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(p);
  });

  const base = Array.from(grouped.entries()).map(([key, items]) => {
    const mappable = items.filter((p) => hasValidLatLon(p.latitude, p.longitude));
    const lat = mappable.length
      ? mappable.reduce((s, p) => s + Number(p.latitude), 0) / mappable.length
      : null;
    const lon = mappable.length
      ? mappable.reduce((s, p) => s + Number(p.longitude), 0) / mappable.length
      : null;
    const totalValue = items.reduce((s, p) => s + (Number(p.sum_insured) || 0), 0);
    const maxHeight = items.reduce((max, p) => {
      const h = Number(p.height_m ?? p.height_max_m ?? p.building_height_m);
      return Number.isFinite(h) ? Math.max(max, h) : max;
    }, 0);
    const representativeProperty = mappable[0] || items.find((p) => p.uprn) || items[0] || null;

    return {
      id: key,
      block_id: key,
      label: key || "Unassigned block",
      name: key || "Unassigned block",
      block_reference: key || "",
      properties: items,
      count: items.length,
      lat,
      lon,
      hasValidCoords: hasValidLatLon(lat, lon),
      totalValue,
      maxHeight,
      maxStoreys: items.reduce((max, p) => {
        const s = Number(p.storeys ?? p.max_storeys);
        return Number.isFinite(s) ? Math.max(max, s) : max;
      }, 0),
      buildYear:
        items.find((p) => isPresent(p.year_of_build ?? p.build_year))?.year_of_build ??
        items.find((p) => isPresent(p.build_year))?.build_year ??
        null,
      parent_uprn:
        items.find((p) => p.parent_uprn)?.parent_uprn ||
        items.find((p) => p.uprn)?.uprn ||
        null,
      isListed: items.some((p) => p.is_listed === true || p.listed_grade),
      listedGrade: items.find((p) => isPresent(p.listed_grade))?.listed_grade ?? null,
      // ponytail: flats in a block share a footprint — take the first; refine to
      // the parent_uprn's geometry if a block ever spans two buildings.
      geometry: items.find((p) => p.building_geometry)?.building_geometry ?? null,
      representativeProperty,
    };
  });

  return base
    .map((block) => {
      const aliases = [block.id, block.block_id, block.label, block.name, block.block_reference, block.parent_uprn]
        .map(normaliseKey)
        .filter(Boolean);

      const linkedDocs = fireDocuments.filter((doc) => {
        const docBlock = normaliseKey(doc.block_reference);
        const docProperty = normaliseKey(doc.property_id);
        const blockMatch = docBlock && aliases.includes(docBlock);
        const propertyMatch =
          docProperty &&
          block.properties.some((p) =>
            [p.id, p.property_id, p.property_reference, p.uprn].map(normaliseKey).filter(Boolean).includes(docProperty)
          );
        return blockMatch || propertyMatch;
      });

      const propertyFra = block.properties.find((p) => p.latest_fra)?.latest_fra ?? null;
      const propertyFraew = block.properties.find((p) => p.latest_fraew)?.latest_fraew ?? null;
      const fraDoc = linkedDocs.find((d) => d.document_type === "FRA") ?? null;
      const fraewDoc = linkedDocs.find((d) => d.document_type === "FRAEW") ?? null;

      return {
        ...block,
        latest_fra: fraDoc?.fra ?? fraDoc ?? propertyFra,
        latest_fraew: fraewDoc?.fraew ?? fraewDoc ?? propertyFraew,
        linkedDocs,
      };
    })
    .sort((a, b) => {
      const byBand = BAND_RANK[blockOverallBand(b)] - BAND_RANK[blockOverallBand(a)];
      if (byBand !== 0) return byBand;
      return b.totalValue - a.totalValue;
    });
};

// ---------- assessment validity ----------

const toDate = (v) => {
  if (!isPresent(v)) return null;
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
};

// Is an assessment still valid today? Best-effort from the dates available:
// explicit valid-until -> recommended next-review -> assessment date + 5 years
// -> the source document's own in-date flag. Returns { inDate, basis, date }.
export const assessmentStatus = (doc) => {
  if (!doc) return { inDate: null, basis: null, date: null };
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const at = (raw, basis) => {
    const d = toDate(raw);
    return d ? { inDate: d.getTime() >= today.getTime(), basis, date: raw } : null;
  };
  const byValidUntil = at(doc.assessment_valid_until, "valid-until");
  if (byValidUntil) return byValidUntil;
  const byReview = at(doc.next_review_date, "next-review");
  if (byReview) return byReview;
  const a = toDate(doc.assessment_date);
  if (a) {
    const exp = new Date(a);
    exp.setFullYear(exp.getFullYear() + 5);
    return { inDate: exp.getTime() >= today.getTime(), basis: "assessment+5y", date: doc.assessment_date };
  }
  if (doc.is_in_date === true || doc.is_in_date === false) return { inDate: doc.is_in_date, basis: "flag", date: null };
  return { inDate: null, basis: null, date: null };
};

// Plain-language explanation of how the in-date verdict was reached (for a tooltip).
export const inDateTip = (s) => {
  if (!s || s.inDate === null) return "No validity date recorded for this assessment.";
  if (s.basis === "valid-until")
    return s.inDate ? `Within validity — valid until ${s.date}.` : `Out of date — expired ${s.date}.`;
  if (s.basis === "next-review")
    return s.inDate
      ? `Within the assessor's recommended review date (${s.date}).`
      : `Overdue — recommended review date ${s.date} has passed.`;
  if (s.basis === "assessment+5y")
    return s.inDate
      ? `Estimated — no valid-until or review date was recorded, so this assumes the assessment (${s.date}) stays valid for 5 years. Verify against the source document.`
      : `Estimated — no valid-until or review date was recorded; assumed out of date (assessment ${s.date} + 5 years).`;
  return "Based on the source document's in-date flag.";
};

// ---------- derived risk ----------

export const blockOverallBand = (block) =>
  worstBand(getFireRiskBand(block?.latest_fra), getFireRiskBand(block?.latest_fraew));

// Overall band + a short plain-language list of what is driving it, for the hero.
export const summariseBlockRisk = (block) => {
  const band = blockOverallBand(block);
  const fra = block?.latest_fra;
  const fraew = block?.latest_fraew;
  const reasons = [];

  if (getFireRiskBand(fraew) === "Red") reasons.push("external wall (FRAEW) rated high");
  if (getFireRiskBand(fra) === "Red") reasons.push("fire risk (FRA) rated high");
  if (fraew?.aluminium_composite_cladding === true) reasons.push("ACM cladding present");
  else if (fraew?.has_combustible_cladding === true || fraew?.combustible_cladding === true)
    reasons.push("combustible cladding present");

  const stats = fraActionStats(fra);
  if (stats.overdue > 0) reasons.push(`${stats.overdue} overdue action${stats.overdue > 1 ? "s" : ""}`);
  if (fra && assessmentStatus(fra).inDate === false) reasons.push("FRA out of date");
  if (fraew && assessmentStatus(fraew).inDate === false) reasons.push("FRAEW out of date");

  if (!reasons.length) {
    if (getFireRiskBand(fraew) === "Amber") reasons.push("external wall (FRAEW) rated medium");
    if (getFireRiskBand(fra) === "Amber") reasons.push("fire risk (FRA) rated medium");
  }
  if (!fra && !fraew) reasons.push("no fire-risk assessments on record");

  return { band, reasons };
};

// Searchable text for a block: street/address of every flat + name + postcode.
export const blockStreetText = (block) => {
  const addrs = (block.properties || [])
    .map((p) => p.address_line_1 || p.address || p.address1 || "")
    .join(" ");
  const postcodes = (block.properties || [])
    .map((p) => p.post_code || p.postcode || "")
    .join(" ");
  return `${block.name} ${addrs} ${postcodes}`.toLowerCase();
};

export const blockDisplayAddress = (block) => {
  const rep = block.representativeProperty || {};
  const street = cleanAddress(rep.address_line_1 || rep.address || rep.address1) || block.name;
  const postcode = rep.post_code || rep.postcode || "";
  return { street, postcode };
};

// Auto-surfaced critical flags. Returns [{ tone: 'red'|'amber'|'info', text }].
export const computeBlockAlerts = (block) => {
  const alerts = [];
  const fra = block.latest_fra;
  const fraew = block.latest_fraew;

  if (!fra) alerts.push({ tone: "amber", text: "No FRA on record — block unassessed for fire risk." });
  if (!fraew) alerts.push({ tone: "info", text: "No FRAEW (external wall) assessment on record." });

  if (getFireRiskBand(fra) === "Red")
    alerts.push({ tone: "red", text: "FRA rated High / Red — urgent fire risk." });
  if (getFireRiskBand(fraew) === "Red")
    alerts.push({ tone: "red", text: "FRAEW rated High / Red — external wall risk." });

  if (fra && assessmentStatus(fra).inDate === false)
    alerts.push({ tone: "red", text: "FRA is out of date — reassessment required." });
  if (fraew && assessmentStatus(fraew).inDate === false)
    alerts.push({ tone: "amber", text: "FRAEW is out of date." });

  const stats = fraActionStats(fra);
  if (stats.overdue > 0)
    alerts.push({ tone: "red", text: `${stats.overdue} overdue FRA action${stats.overdue > 1 ? "s" : ""}.` });

  const combustible =
    fraew?.has_combustible_cladding === true || fraew?.combustible_cladding === true;
  const acm = fraew?.aluminium_composite_cladding === true;
  if (acm) alerts.push({ tone: "red", text: "ACM cladding present (Grenfell-type) — highest concern." });
  else if (combustible) alerts.push({ tone: "red", text: "Combustible cladding present." });

  const height = Number(block.maxHeight ?? fraew?.building_height_m);
  if (combustible && Number.isFinite(height) && height >= 18 && fraew?.bs8414_test_evidence !== true)
    alerts.push({ tone: "red", text: "Combustible cladding over 18m with no BS 8414 test evidence." });

  if (fraew?.asbestos_suspected === true)
    alerts.push({ tone: "amber", text: "Asbestos suspected behind cladding." });

  if (block.isListed)
    alerts.push({ tone: "info", text: `Listed building${block.listedGrade ? ` (Grade ${block.listedGrade})` : ""} — remediation constraints apply.` });

  return alerts;
};
