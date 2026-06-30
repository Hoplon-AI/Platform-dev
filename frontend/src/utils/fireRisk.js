// Fire-risk + property/block helpers shared by the portfolio dashboard panels.

export const fmtMoney = (n) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  return x.toLocaleString(undefined, { maximumFractionDigits: 0 });
};

export const hasValidLatLon = (lat, lon) => {
  const la = Number(lat);
  const lo = Number(lon);
  return (
    Number.isFinite(la) && Number.isFinite(lo) &&
    la !== 0 && lo !== 0 &&
    la >= 49.0 && la <= 61.5 &&
    lo >= -8.8 && lo <= 2.8
  );
};

export const normaliseKey = (value) => String(value ?? "").trim().toLowerCase();

export const sameProperty = (a, b) => {
  if (!a || !b) return false;

  return (
    (a.id && b.id && String(a.id) === String(b.id)) ||
    (a.property_id && b.property_id && String(a.property_id) === String(b.property_id)) ||
    (a.property_reference &&
      b.property_reference &&
      String(a.property_reference) === String(b.property_reference)) ||
    (a.uprn && b.uprn && String(a.uprn) === String(b.uprn))
  );
};

export const sameBlock = (a, b) => {
  if (!a || !b) return false;

  return (
    (a.id && b.id && String(a.id) === String(b.id)) ||
    (a.block_id && b.block_id && String(a.block_id) === String(b.block_id)) ||
    (a.label && b.label && String(a.label) === String(b.label)) ||
    (a.name && b.name && String(a.name) === String(b.name)) ||
    (a.block_reference &&
      b.block_reference &&
      String(a.block_reference) === String(b.block_reference)) ||
    (a.parent_uprn && b.parent_uprn && String(a.parent_uprn) === String(b.parent_uprn))
  );
};

export const normaliseActions = (value) => {
  if (!value) return [];
  const arr = Array.isArray(value) ? value : [value];
  return arr.filter(Boolean).map((a) => {
    if (typeof a === "string") return a;
    // Action items are objects — extract a readable label rather than [object Object]
    return (
      a.description ??
      a.action ??
      a.finding ??
      a.recommendation ??
      a.issue_ref ??
      "Action"
    );
  });
};

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
  const text = String(getFireDocumentRisk(doc) ?? "").toLowerCase();
  if (
    text.includes("red") ||
    text.includes("high") ||
    text.includes("intolerable") ||
    text.includes("not acceptable")
  ) {
    return "Red";
  }
  if (
    text.includes("amber") ||
    text.includes("medium") ||
    text.includes("moderate") ||
    text.includes("tolerable")
  ) {
    return "Amber";
  }
  if (
    text.includes("green") ||
    text.includes("low") ||
    text.includes("acceptable") ||
    text.includes("broadly acceptable")
  ) {
    return "Green";
  }
  return "Unknown";
};

export const riskBadgeStyle = (band) => {
  if (band === "Red") return { background: "#fee2e2", color: "#991b1b" };
  if (band === "Amber") return { background: "#fef3c7", color: "#92400e" };
  if (band === "Green") return { background: "#dcfce7", color: "#166534" };
  return { background: "#e2e8f0", color: "#475569" };
};

export const normaliseFirePayloadToDocument = (payload, fallbackIndex = 0) => {
  if (!payload) return null;

  const firePayload = payload.fire_risk_payload ?? payload;
  const documentType = String(firePayload.document_type ?? payload.document_type ?? "").toUpperCase();
  const fra = firePayload.fra ?? null;
  const fraew = firePayload.fraew ?? null;
  const primary = documentType === "FRAEW" ? fraew : fra || fraew || firePayload;

  const riskLevel = getFireDocumentRisk(primary);
  const actions = normaliseActions(
    primary?.recommendations ??
      primary?.actions ??
      primary?.significant_findings ??
      primary?.remedial_actions ??
      primary?.action_items
  );

  return {
    id:
      firePayload.id ??
      firePayload.upload_id ??
      firePayload.feature_id ??
      `${documentType || "FIRE"}-${fallbackIndex + 1}`,
    upload_id: firePayload.upload_id ?? payload.upload_id ?? "",
    feature_id: firePayload.feature_id ?? payload.feature_id ?? "",
    filename: firePayload.filename ?? payload.filename ?? "Uploaded PDF",
    document_type: documentType || "FIRE",
    block_id: firePayload.block_id ?? payload.block_id ?? "",
    block_reference:
      firePayload.block_reference ??
      firePayload.block_id ??
      payload.block_reference ??
      payload.block_id ??
      "",
    property_id: firePayload.property_id ?? payload.property_id ?? "",
    risk_level: riskLevel,
    rag_status: riskLevel,
    summary: (() => {
      const txt =
        primary?.summary ??
        primary?.executive_summary ??
        primary?.findings_summary ??
        primary?.interim_measures_detail ??
        null;
      if (txt) return txt;
      // Build from structured fields when no free-text summary exists
      const parts = [];
      if (primary?.risk_rating) parts.push(`Risk rating: ${primary.risk_rating}.`);
      if (primary?.building_risk_rating) parts.push(`Building risk: ${primary.building_risk_rating}.`);
      if (primary?.evacuation_strategy) parts.push(`Evacuation: ${primary.evacuation_strategy.replace(/_/g, " ")}.`);
      if (primary?.total_action_count) {
        const overdue = primary.overdue_action_count ? ` (${primary.overdue_action_count} overdue)` : "";
        parts.push(`${primary.total_action_count} action item(s)${overdue}.`);
      }
      if (primary?.has_combustible_cladding) parts.push("Combustible cladding present.");
      if (primary?.has_sprinkler_system === false) parts.push("No sprinkler system.");
      if (primary?.has_fire_alarm_system === false) parts.push("No fire alarm system.");
      return parts.length > 0 ? parts.join(" ") : null;
    })(),
    actions,
    fra,
    fraew,
    raw: firePayload,
    created_at: payload.created_at ?? new Date().toISOString(),
  };
};

export const collectFireDocumentsFromIngestion = (ingestionResult, latestFireRiskPayload) => {
  const docs = [];

  const sourceItems = Array.isArray(ingestionResult?.fire_documents)
    ? ingestionResult.fire_documents
    : Array.isArray(ingestionResult?.raw?.fire_documents)
    ? ingestionResult.raw.fire_documents
    : [];

  sourceItems.forEach((item, index) => {
    const normalised = normaliseFirePayloadToDocument(item, index);
    if (normalised) docs.push(normalised);
  });


  const latest = normaliseFirePayloadToDocument(latestFireRiskPayload, docs.length);
  if (latest) docs.unshift(latest);

  // Dedup by the most stable identifier. The same document arrives from two sources
  // (latestFireRiskPayload from an upload + ingestionResult.fire_documents from the
  // API) with different shapes. upload_id is identical across both (same upload);
  // feature_id is NOT reliable (API returns fra_id AS feature_id, upload uses the
  // processor's feature_id). Prefix with document_type so an FRA and FRAEW never
  // collide. Fall back to block+filename only when no id is present.
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
