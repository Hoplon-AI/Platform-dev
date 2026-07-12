// Normalisation helpers: shape backend payloads (properties, fire docs) for the UI.
import { resolveCoordinates, readinessBandFromScore, toNumberOrNull } from "./coordinates.js";

export const normaliseKey = (value) => String(value ?? "").trim().toLowerCase();

export const normaliseFireRiskPayload = (payload) => {
  if (!payload) return null;

  const fireRiskPayload = payload.fire_risk_payload ?? payload;
  const documentType = String(
    fireRiskPayload.document_type ?? payload.document_type ?? ""
  ).toLowerCase();

  return {
    ...fireRiskPayload,
    document_type: documentType,
    upload_id: fireRiskPayload.upload_id ?? payload.upload_id ?? null,
    feature_id: fireRiskPayload.feature_id ?? payload.feature_id ?? null,
    block_id: fireRiskPayload.block_id ?? payload.block_id ?? null,
    block_reference:
      fireRiskPayload.block_reference ??
      payload.block_reference ??
      fireRiskPayload.block_name ??
      payload.block_name ??
      null,
    property_id: fireRiskPayload.property_id ?? payload.property_id ?? null,
    filename: fireRiskPayload.filename ?? payload.filename ?? null,
  };
};

export const normaliseProperty = (row, index = 0) => {
  const fallbackY = toNumberOrNull(row.y_coordinate) ?? toNumberOrNull(row.y);
  const fallbackX = toNumberOrNull(row.x_coordinate) ?? toNumberOrNull(row.x);
  const { latitude, longitude, coordinate_source } = resolveCoordinates(row);

  const readinessScore =
    toNumberOrNull(row.readiness_score) ??
    toNumberOrNull(row.readinessScore) ??
    toNumberOrNull(row.score) ??
    0;

  const hasValidCoords =
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    latitude !== 0 &&
    longitude !== 0;

  return {
    id:
      row.id ??
      row.property_id ??
      row.propertyId ??
      row.uprn ??
      row.property_reference ??
      row.address_line_1 ??
      row.address1 ??
      row.address ??
      `property-${index + 1}`,

    property_id: row.property_id ?? row.propertyId ?? "",
    property_reference: row.property_reference ?? row.propertyReference ?? "",
    address_line_1:
      row.address_line_1 ?? row.address1 ?? row.address ?? row.property_address ?? "",
    address_line_2: row.address_line_2 ?? row.address2 ?? row.address_2 ?? "",
    address_3: row.address_3 ?? row.address3 ?? "",
    city: row.city ?? row.town ?? row.locality ?? row.address_3 ?? "",
    post_code: row.post_code ?? row.postcode ?? row.zip ?? "",
    uprn: row.uprn ?? row.UPRN ?? "",
    parent_uprn: row.parent_uprn ?? "",
    block_reference: row.block_reference ?? row.block_name ?? row.block_id ?? "",
    uprn_match_score: toNumberOrNull(row.uprn_match_score) ?? toNumberOrNull(row.match_score),
    uprn_match_description: row.uprn_match_description ?? row.match_description ?? "",

    latitude,
    longitude,
    x_coordinate: fallbackX,
    y_coordinate: fallbackY,
    coordinate_source,
    hasValidCoords,

    sum_insured:
      toNumberOrNull(row.sum_insured) ??
      toNumberOrNull(row.sumInsured) ??
      toNumberOrNull(row.total_sum_insured) ??
      toNumberOrNull(row.tiv) ??
      0,

    property_type: row.property_type ?? row.propertyType ?? row.type ?? "",
    dwelling_form: row.dwelling_form ?? "",
    is_standalone:
      typeof row.is_standalone === "boolean" ? row.is_standalone : row.is_standalone ?? null,
    occupancy_type: row.occupancy_type ?? row.occupancyType ?? row.occupancy ?? "",
    height_m:
      toNumberOrNull(row.height_m) ??
      toNumberOrNull(row.height) ??
      toNumberOrNull(row.height_max_m) ??
      toNumberOrNull(row.building_height_m),
    storeys: toNumberOrNull(row.storeys) ?? toNumberOrNull(row.max_storeys),
    units:
      toNumberOrNull(row.units) ??
      toNumberOrNull(row.unit_count) ??
      toNumberOrNull(row.number_of_flats),
    year_of_build: toNumberOrNull(row.year_of_build) ?? toNumberOrNull(row.year_built),

    wall_construction: row.wall_construction ?? "",
    roof_construction: row.roof_construction ?? "",
    built_form: row.built_form ?? "",
    total_floor_area_m2: toNumberOrNull(row.total_floor_area_m2),
    main_fuel: row.main_fuel ?? "",
    epc_rating: row.epc_rating ?? "",
    epc_potential_rating: row.epc_potential_rating ?? "",
    epc_lodgement_date: row.epc_lodgement_date ?? "",
    country_code: row.country_code ?? "",
    height_roofbase_m: toNumberOrNull(row.height_roofbase_m),
    height_confidence: row.height_confidence ?? "",
    building_footprint_m2: toNumberOrNull(row.building_footprint_m2),
    is_listed: typeof row.is_listed === "boolean" ? row.is_listed : row.is_listed ?? null,
    listed_grade: row.listed_grade ?? "",
    listed_name: row.listed_name ?? "",
    listed_reference: row.listed_reference ?? "",
    flood_risk_band: row.flood_risk_band ?? "",
    flood_risk_source: row.flood_risk_source ?? "",
    uprn_confidence: row.uprn_confidence ?? "",
    enrichment_status: row.enrichment_status ?? "",
    enrichment_source: row.enrichment_source ?? "",
    enriched_at: row.enriched_at ?? null,

    readiness_score: readinessScore,
    readiness_band:
      row.readiness_band ?? row.readinessBand ?? readinessBandFromScore(readinessScore),
    missing_fields:
      row.missing_fields ?? row.missingFields ?? row.validation?.missing_fields ?? [],

    latest_fra: row.latest_fra ?? row.fire_documents?.fra ?? null,
    latest_fraew: row.latest_fraew ?? row.fire_documents?.fraew ?? null,
    fire_documents: row.fire_documents ?? null,

    raw: row.raw ?? row,
  };
};

export const normaliseBackendIngestionResult = (payload, sourceName) => {
  const rawProperties =
    payload?.properties ??
    payload?.records ??
    payload?.items ??
    payload?.data ??
    payload?.results ??
    [];

  const properties = Array.isArray(rawProperties)
    ? rawProperties.map((row, index) => normaliseProperty(row, index))
    : [];

  const resolvedSource =
    payload?.source ??
    payload?.filename ??
    payload?.file_name ??
    payload?.document_name ??
    sourceName;

  return {
    source: resolvedSource,
    sourceName: resolvedSource,
    properties,
    raw: payload,
    summary: payload?.summary ?? null,
    status: payload?.status ?? null,
    upload_id: payload?.upload_id ?? null,
    feature_id: payload?.feature_id ?? null,
    portfolio_id:
      payload?.portfolio_id ??
      payload?.summary?.portfolio_id ??
      payload?.raw?.portfolio_id ??
      null,
    storage: payload?.storage ?? null,
    message: payload?.message ?? null,
    fire_risk_payload: payload?.fire_risk_payload ?? null,
    fire_documents: payload?.fire_documents ?? [],
    stats: {
      rowCount: properties.length,
      mappableCount: properties.filter((property) => property.hasValidCoords).length,
      skippedInvalidCoords: properties.filter((property) => !property.hasValidCoords).length,
      totalValue: properties.reduce(
        (sum, property) => sum + (Number(property.sum_insured) || 0),
        0
      ),
    },
  };
};

export const normaliseFireDocumentItem = (item, index = 0) => {
  const fra = item?.fra ?? item?.fire_documents?.fra ?? null;
  const fraew = item?.fraew ?? item?.fire_documents?.fraew ?? null;

  return {
    id:
      item?.id ??
      item?.upload_id ??
      item?.feature_id ??
      item?.property_id ??
      item?.property_reference ??
      item?.block_id ??
      `fire-doc-${index + 1}`,
    upload_id: item?.upload_id ?? "",
    feature_id: item?.feature_id ?? "",
    filename: item?.filename ?? "",
    property_id: item?.property_id ?? "",
    property_reference: item?.property_reference ?? "",
    block_id: item?.block_id ?? "",
    block_reference: item?.block_name ?? item?.block_reference ?? item?.block_id ?? "",
    address_line_1: item?.address ?? item?.address_line_1 ?? "",
    post_code: item?.postcode ?? item?.post_code ?? "",
    document_type: item?.document_type ?? (fraew ? "fraew" : fra ? "fra" : ""),
    fra,
    fraew,
    fire_documents: {
      fra,
      fraew,
    },
    raw: item,
  };
};

export const attachSingleFirePayloadToPortfolio = (existingResult, firePayload) => {
  if (!existingResult || !firePayload) return existingResult;

  const documentType = String(firePayload.document_type ?? "").toLowerCase();
  const uploadedDoc = {
    ...firePayload,
    document_type: documentType,
    fra: firePayload.fra ?? null,
    fraew: firePayload.fraew ?? null,
  };

  const targetPropertyId = normaliseKey(uploadedDoc.property_id);
  const targetBlock = normaliseKey(uploadedDoc.block_reference ?? uploadedDoc.block_id ?? "");

  const updatedProperties = (existingResult.properties || []).map((property) => {
    const propertyAliases = [
      property.id,
      property.property_id,
      property.property_reference,
      property.uprn,
    ]
      .map(normaliseKey)
      .filter(Boolean);

    const blockAliases = [property.block_reference, property.parent_uprn, property.uprn]
      .map(normaliseKey)
      .filter(Boolean);

    const propertyMatch = targetPropertyId && propertyAliases.includes(targetPropertyId);
    const blockMatch = targetBlock && blockAliases.includes(targetBlock);

    if (!propertyMatch && !blockMatch) return property;

    const currentFireDocs = property.fire_documents || {};
    const nextFireDocs = {
      ...currentFireDocs,
      fra:
        documentType === "fra"
          ? uploadedDoc.fra ?? uploadedDoc
          : currentFireDocs.fra ?? property.latest_fra ?? null,
      fraew:
        documentType === "fraew"
          ? uploadedDoc.fraew ?? uploadedDoc
          : currentFireDocs.fraew ?? property.latest_fraew ?? null,
    };

    return {
      ...property,
      fire_documents: nextFireDocs,
      latest_fra: nextFireDocs.fra,
      latest_fraew: nextFireDocs.fraew,
    };
  });

  return {
    ...existingResult,
    properties: updatedProperties,
    fire_risk_payload: uploadedDoc,
    fire_documents: [uploadedDoc, ...(existingResult.fire_documents || [])],
  };
};

export const mergeFireDocumentsIntoPortfolio = (existingResult, fireDocumentsPayload) => {
  if (!existingResult) return existingResult;

  const items = Array.isArray(fireDocumentsPayload?.items)
    ? fireDocumentsPayload.items
    : Array.isArray(fireDocumentsPayload)
    ? fireDocumentsPayload
    : [];

  if (!items.length) {
    return {
      ...existingResult,
      fire_documents: [],
    };
  }

  const normalisedItems = items.map((item, index) => normaliseFireDocumentItem(item, index));

  const fireByPropertyId = new Map();
  const fireByReference = new Map();
  const fireByBlock = new Map();

  normalisedItems.forEach((item) => {
    if (item.property_id) {
      fireByPropertyId.set(normaliseKey(item.property_id), item);
    }
    if (item.property_reference) {
      fireByReference.set(normaliseKey(item.property_reference), item);
    }
    if (item.block_reference) {
      fireByBlock.set(normaliseKey(item.block_reference), item);
    }
    if (item.block_id) {
      fireByBlock.set(normaliseKey(item.block_id), item);
    }
  });

  const mergedProperties = (existingResult.properties || []).map((property) => {
    const fromId =
      property.property_id && fireByPropertyId.get(normaliseKey(property.property_id));
    const fromRef =
      property.property_reference &&
      fireByReference.get(normaliseKey(property.property_reference));
    const fromBlock =
      property.block_reference && fireByBlock.get(normaliseKey(property.block_reference));

    const fireDoc = fromId || fromRef || fromBlock || null;

    if (!fireDoc) {
      return property;
    }

    return {
      ...property,
      fire_documents: fireDoc.fire_documents,
      latest_fra: fireDoc.fire_documents?.fra ?? null,
      latest_fraew: fireDoc.fire_documents?.fraew ?? null,
    };
  });

  return {
    ...existingResult,
    fire_documents: normalisedItems,
    properties: mergedProperties,
  };
};

export const getPortfolioIdFromResult = (result) => {
  return (
    result?.portfolio_id ??
    result?.summary?.portfolio_id ??
    result?.raw?.portfolio_id ??
    null
  );
};
