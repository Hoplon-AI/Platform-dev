import React, { useEffect, useMemo, useRef, useState } from "react";
import proj4 from "proj4";

import Landingpage from "./landingpage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import IngestionPage from "./pages/IngestionLandingPage.tsx";
import PortfolioDashboard from "./pages/PortfolioDashboard.jsx";

import { getIngestionSummary } from "./utils/ingestion";
import { apiFetch } from "./services/apiClient";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

// EPSG:27700 (British National Grid) -> EPSG:4326 (WGS84)
proj4.defs(
  "EPSG:27700",
  "+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 " +
    "+x_0=400000 +y_0=-100000 +ellps=airy " +
    "+towgs84=446.448,-125.157,542.06,0.15,0.247,0.842,-20.489 " +
    "+units=m +no_defs"
);

const UK_LAT_BOUNDS = {
  min: 49.0,
  max: 61.5,
};

const UK_LON_BOUNDS = {
  min: -8.8,
  max: 2.8,
};

const OSGB_EASTING_BOUNDS = {
  min: 1,     // exclude 0: Number(null)=0, proj4(0,0) → lat≈49.7 lon≈-7.5 (Atlantic)
  max: 700000,
};

const OSGB_NORTHING_BOUNDS = {
  min: 1,     // same fix — reject null/missing coordinates
  max: 1300000,
};

const toNumberOrNull = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const normaliseKey = (value) => String(value ?? "").trim().toLowerCase();

const looksLikeLatitude = (value) => {
  const n = Number(value);
  return (
    Number.isFinite(n) &&
    n >= UK_LAT_BOUNDS.min &&
    n <= UK_LAT_BOUNDS.max &&
    n !== 0
  );
};

const looksLikeLongitude = (value) => {
  const n = Number(value);
  return (
    Number.isFinite(n) &&
    n >= UK_LON_BOUNDS.min &&
    n <= UK_LON_BOUNDS.max &&
    n !== 0
  );
};

const looksLikeBritishNationalGrid = (easting, northing) => {
  const e = Number(easting);
  const n = Number(northing);

  return (
    Number.isFinite(e) &&
    Number.isFinite(n) &&
    e > 0 &&
    e <= OSGB_EASTING_BOUNDS.max &&
    n > 0 &&
    n <= OSGB_NORTHING_BOUNDS.max
  );
};

const convertBritishNationalGridToLatLon = (easting, northing) => {
  try {
    if (!looksLikeBritishNationalGrid(easting, northing)) {
      return null;
    }

    const [lon, lat] = proj4("EPSG:27700", "EPSG:4326", [
      Number(easting),
      Number(northing),
    ]);

    if (!looksLikeLatitude(lat) || !looksLikeLongitude(lon)) {
      return null;
    }

    return { latitude: lat, longitude: lon };
  } catch (error) {
    console.warn("Failed to convert BNG to lat/lon:", error);
    return null;
  }
};

const resolveCoordinates = (row) => {
  const directLatitude =
    toNumberOrNull(row.latitude) ??
    toNumberOrNull(row.lat) ??
    toNumberOrNull(row.location?.latitude) ??
    toNumberOrNull(row.__lat);

  const directLongitude =
    toNumberOrNull(row.longitude) ??
    toNumberOrNull(row.lon) ??
    toNumberOrNull(row.lng) ??
    toNumberOrNull(row.location?.longitude) ??
    toNumberOrNull(row.__lon);

  if (looksLikeLatitude(directLatitude) && looksLikeLongitude(directLongitude)) {
    return {
      latitude: directLatitude,
      longitude: directLongitude,
      coordinate_source: "direct_lat_lon",
    };
  }

  if (looksLikeLatitude(directLongitude) && looksLikeLongitude(directLatitude)) {
    return {
      latitude: directLongitude,
      longitude: directLatitude,
      coordinate_source: "swapped_lat_lon",
    };
  }

  const fallbackNorthing = toNumberOrNull(row.y_coordinate) ?? toNumberOrNull(row.y);
  const fallbackEasting = toNumberOrNull(row.x_coordinate) ?? toNumberOrNull(row.x);

  if (looksLikeLatitude(fallbackNorthing) && looksLikeLongitude(fallbackEasting)) {
    return {
      latitude: fallbackNorthing,
      longitude: fallbackEasting,
      coordinate_source: "fallback_lat_lon",
    };
  }

  if (looksLikeLatitude(fallbackEasting) && looksLikeLongitude(fallbackNorthing)) {
    return {
      latitude: fallbackEasting,
      longitude: fallbackNorthing,
      coordinate_source: "swapped_fallback_lat_lon",
    };
  }

  const converted = convertBritishNationalGridToLatLon(fallbackEasting, fallbackNorthing);

  if (converted) {
    return {
      ...converted,
      coordinate_source: "osgb36_converted",
    };
  }

  return {
    latitude: null,
    longitude: null,
    coordinate_source: null,
  };
};

const readinessBandFromScore = (score) => {
  const s = Number(score) || 0;
  if (s >= 80) return "Green";
  if (s >= 50) return "Amber";
  return "Red";
};

const normaliseFireRiskPayload = (payload) => {
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

const normaliseProperty = (row, index = 0) => {
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

const normaliseBackendIngestionResult = (payload, sourceName) => {
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

const normaliseFireDocumentItem = (item, index = 0) => {
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

const attachSingleFirePayloadToPortfolio = (existingResult, firePayload) => {
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

const mergeFireDocumentsIntoPortfolio = (existingResult, fireDocumentsPayload) => {
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

const getPortfolioIdFromResult = (result) => {
  return (
    result?.portfolio_id ??
    result?.summary?.portfolio_id ??
    result?.raw?.portfolio_id ??
    null
  );
};

export default function App() {
  const [showLanding, setShowLanding] = useState(true);
  const [authUser, setAuthUser] = useState(null);
  const [activeNav, setActiveNav] = useState("uploads");

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [pipelineStep, setPipelineStep] = useState(null);

  const [uploadMode, setUploadMode] = useState("sov");
  const [pdfDocumentType, setPdfDocumentType] = useState("fra");
  const [selectedBlockReference, setSelectedBlockReference] = useState("");
  const [selectedPropertyId, setSelectedPropertyId] = useState("");

  const [ingestionResult, setIngestionResult] = useState(null);
  const [latestFireRiskPayload, setLatestFireRiskPayload] = useState(null);
  const [fireDocumentsLoading, setFireDocumentsLoading] = useState(false);

  const ingestionSummary = useMemo(
    () => getIngestionSummary(ingestionResult),
    [ingestionResult]
  );

  const currentPortfolioId = useMemo(
    () => getPortfolioIdFromResult(ingestionResult),
    [ingestionResult]
  );

  useEffect(() => {
    console.log("API_BASE_URL =", API_BASE_URL);
  }, []);

  const loadPropertiesFromApi = async () => {
    try {
      const res = await apiFetch("/api/v1/portfolios/properties");
      const properties = await res.json();
      if (Array.isArray(properties) && properties.length > 0) {
        const normalised = normaliseBackendIngestionResult(
          { properties, status: "success" },
          "Portfolio"
        );
        setIngestionResult(normalised);
        // Do NOT redirect here — navigation is controlled by explicit user actions
        // (SoV upload → overview, login → uploads, hard refresh → stays on uploads)
      }
    } catch (err) {
      console.error("[loadPropertiesFromApi] Failed:", err);
    }
  };

  // Restore session from storage on mount
  useEffect(() => {
    const token =
      localStorage.getItem("equirisk_token") ||
      sessionStorage.getItem("equirisk_token");
    const raw =
      localStorage.getItem("equirisk_user") ||
      sessionStorage.getItem("equirisk_user");
    if (token && raw) {
      try {
        const user = JSON.parse(raw);
        setAuthUser(user);
        setShowLanding(false);
        // Demo mode: do NOT pre-load portfolio from DB on session restore.
        // Data lives in React state for this session only.
      } catch {
        // corrupted storage — ignore
      }
    }
  }, []);

  useEffect(() => {
    if (!API_BASE_URL) return;

    fetch(`${API_BASE_URL}/health`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Health check failed: ${res.status}`);
        }
        return res.json();
      })
      .then((data) => console.log("Backend health:", data))
      .catch((err) => console.error("Backend error:", err));
  }, []);

  const pipelineTimersRef = useRef([]);

  const STAGE_PIPELINE_STEPS = {
    sov: [
      "Uploading file",
      "Validating format",
      "Parsing property schedule",
      "Detecting blocks",
      "Building portfolio",
      "Preparing dashboard",
    ],
    fra: [
      "Uploading document",
      "Extracting text from PDF",
      "Running AI analysis",
      "Identifying fire risk factors",
      "Scoring risk rating",
      "Saving to portfolio",
    ],
    fraew: [
      "Uploading document",
      "Extracting text from PDF",
      "Running AI analysis",
      "Identifying cladding & wall risks",
      "Scoring building risk",
      "Saving to portfolio",
    ],
  };

  const runPipeline = (docType = "sov") => {
    // Cancel any previous timers so they can't fire after backend finishes
    pipelineTimersRef.current.forEach((id) => clearTimeout(id));
    pipelineTimersRef.current = [];

    const steps = STAGE_PIPELINE_STEPS[docType] ?? STAGE_PIPELINE_STEPS.sov;
    setPipelineStep(steps[0]);

    steps.slice(1).forEach((step, i) => {
      const id = setTimeout(() => setPipelineStep(step), 3500 * (i + 1));
      pipelineTimersRef.current.push(id);
    });
  };

  const fetchFireDocuments = async (portfolioId) => {
    if (!API_BASE_URL || !portfolioId) return null;

    setFireDocumentsLoading(true);

    try {
      const fireToken =
        localStorage.getItem("equirisk_token") ||
        sessionStorage.getItem("equirisk_token");
      const response = await fetch(
        `${API_BASE_URL}/api/v1/underwriter/portfolios/${portfolioId}/fire-documents`,
        { headers: fireToken ? { Authorization: `Bearer ${fireToken}` } : {} }
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload?.detail ||
            payload?.error ||
            `Failed to fetch fire documents (${response.status})`
        );
      }

      return payload;
    } catch (error) {
      console.error("Failed to fetch fire documents:", error);
      return null;
    } finally {
      setFireDocumentsLoading(false);
    }
  };

  const refetchFireDocuments = async () => {
    const portfolioId = currentPortfolioId ?? getPortfolioIdFromResult(ingestionResult);
    if (!portfolioId) return null;

    const fireDocsPayload = await fetchFireDocuments(portfolioId);

    if (fireDocsPayload) {
      setIngestionResult((prev) => mergeFireDocumentsIntoPortfolio(prev, fireDocsPayload));
      setLatestFireRiskPayload(fireDocsPayload);
    }

    return fireDocsPayload;
  };

  useEffect(() => {
    if (!currentPortfolioId || !API_BASE_URL || !ingestionResult) return;

    refetchFireDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPortfolioId]);

  const handleFiles = async (fileList, stageOverride = null) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    const file = files[0];

    // Compute documentType early so runPipeline gets the right steps
    const stage = String(stageOverride || "").toUpperCase();
    const documentType =
      stage === "FRA"   ? "fra"
      : stage === "FRAEW" ? "fraew"
      : stage === "SOV"   ? "sov"
      : uploadMode === "fire" ? pdfDocumentType
      : "sov";

    setUploadError(null);
    setIsUploading(true);
    runPipeline(documentType);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const isPdfMode = documentType === "fra" || documentType === "fraew";

      const query = new URLSearchParams();
      query.set("document_type", documentType);

      if (isPdfMode && selectedBlockReference.trim()) {
        query.set("block_reference", selectedBlockReference.trim());
      }

      if (isPdfMode && selectedPropertyId.trim()) {
        query.set("property_id", selectedPropertyId.trim());
      }

      const uploadToken =
        localStorage.getItem("equirisk_token") ||
        sessionStorage.getItem("equirisk_token");
      const response = await fetch(
        `${API_BASE_URL}/api/v1/upload/ingest?${query.toString()}`,
        {
          method: "POST",
          body: formData,
          headers: uploadToken ? { Authorization: `Bearer ${uploadToken}` } : {},
        }
      );

      const contentType = response.headers.get("content-type") || "";
      const payload = contentType.includes("application/json")
        ? await response.json()
        : await response.text();

      if (!response.ok) {
        const message =
          typeof payload === "string"
            ? payload
            : payload?.detail ?? payload?.error ?? JSON.stringify(payload);
        throw new Error(`Upload failed (${response.status}): ${message}`);
      }

      if (
        typeof payload !== "object" ||
        payload === null ||
        (payload?.status !== "success" && payload?.success !== true)
      ) {
        throw new Error("Backend returned an unexpected response.");
      }

      console.log("Backend ingestion result:", payload);

      if (!isPdfMode) {
        const normalised = normaliseBackendIngestionResult(payload, file.name);

        console.log("Normalised ingestion result:", normalised);
        console.log(
          "Mappable properties:",
          normalised.properties.filter((property) => property.hasValidCoords).length
        );
        console.log(
          "Coordinate source sample:",
          normalised.properties.slice(0, 10).map((property) => ({
            id: property.id,
            x: property.x_coordinate,
            y: property.y_coordinate,
            lat: property.latitude,
            lon: property.longitude,
            source: property.coordinate_source,
            hasValidCoords: property.hasValidCoords,
          }))
        );

        setIngestionResult(normalised);
        setLatestFireRiskPayload(normalised.fire_risk_payload ?? null);
        setActiveNav("overview");
      } else {
        const normalisedFirePayload = {
          ...normaliseFireRiskPayload(payload),
          filename: file.name,
          block_reference:
            payload?.fire_risk_payload?.block_reference ??
            payload?.block_reference ??
            selectedBlockReference.trim(),
          property_id:
            payload?.fire_risk_payload?.property_id ??
            payload?.property_id ??
            selectedPropertyId.trim(),
        };

        setLatestFireRiskPayload(normalisedFirePayload);

        setIngestionResult((prev) =>
          attachSingleFirePayloadToPortfolio(prev, normalisedFirePayload)
        );

        const portfolioId = currentPortfolioId ?? getPortfolioIdFromResult(ingestionResult);

        if (portfolioId) {
          const fireDocsPayload = await fetchFireDocuments(portfolioId);

          if (fireDocsPayload) {
            setIngestionResult((prev) =>
              mergeFireDocumentsIntoPortfolio(prev, fireDocsPayload)
            );
          }
        }

        setActiveNav("overview");
      }

      // Cancel any remaining fake-step timers before showing Complete
      pipelineTimersRef.current.forEach((id) => clearTimeout(id));
      pipelineTimersRef.current = [];

      setPipelineStep("Complete");

      setTimeout(() => {
        setPipelineStep(null);
      }, 2200);
    } catch (err) {
      console.error("Backend ingestion error:", err);
      setUploadError(err?.message || "Upload failed");
      setPipelineStep(null);
    } finally {
      setIsUploading(false);
    }
  };

  const handleUploadNew = () => {
    setActiveNav("uploads");
    setUploadError(null);
    setPipelineStep(null);
  };

  if (showLanding) {
    return (
      <Landingpage
        onGetStarted={() => {
          setShowLanding(false);
        }}
      />
    );
  }

  if (!authUser) {
    return (
      <LoginPage
        onLogin={(user) => {
          setAuthUser(user);
          setActiveNav("uploads");
          // Demo mode: start with empty state, let Ewan upload fresh.
        }}
      />
    );
  }

  const loadedMeta = ingestionSummary
    ? `Loaded: ${ingestionSummary.source} · Properties: ${
        ingestionSummary.propertyCount
      } · Value: £${Number(ingestionSummary.totalValue || 0).toLocaleString(undefined, {
        maximumFractionDigits: 0,
      })}`
    : "Upload a file to begin";

  return (
    <div className="app">
      <div className="topbar">
        <div className="topbar-left">Upload SOVs, analyse exposure, assess portfolio risk.</div>
        <div className="topbar-right">{loadedMeta}</div>
      </div>

      <div className="shell">
        <aside className="sidebar">
          <div className="brand">
            <img src="/logo.png" alt="EquiRisk" style={{ height: 36, width: "auto", display: "block", marginBottom: 8 }} />
            <div className="pill pill-muted">UNDERWRITER</div>
          </div>

          <div className="side-section">
            <div className="side-head">Portfolio Workspace</div>

            <button
              className={`side-link ${activeNav === "overview" ? "active" : ""}`}
              onClick={() => setActiveNav("overview")}
              disabled={!ingestionResult}
            >
              Portfolio Overview
            </button>

            <button
              className={`side-link ${activeNav === "uploads" ? "active" : ""}`}
              onClick={() => setActiveNav("uploads")}
            >
              Upload Documents
            </button>
          </div>

          <div className="side-section dim">
            <div className="side-head">Analysis</div>
            <div className="side-item">Evidence Summary</div>
            <div className="side-item">Block Analysis</div>
            <div className="side-item">Documents</div>
          </div>

          <div className="side-bottom">
            {authUser && (
              <div style={{ marginBottom: 10, padding: "8px 10px", background: "var(--panel-soft)", borderRadius: 8, border: "1px solid var(--border-soft)" }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", lineHeight: 1.3, marginBottom: 2 }}>
                  {authUser.full_name}
                </div>
                <div style={{ fontSize: 11, color: "var(--muted)", lineHeight: 1.3 }}>
                  {authUser.organisation}
                </div>
              </div>
            )}
            <button
              className="btn btn-ghost"
              style={{ width: "100%", textAlign: "left" }}
              onClick={() => {
                localStorage.removeItem("equirisk_token");
                localStorage.removeItem("equirisk_user");
                sessionStorage.removeItem("equirisk_token");
                sessionStorage.removeItem("equirisk_user");
                setAuthUser(null);
                setIngestionResult(null);
                setShowLanding(true);
              }}
            >
              Sign out
            </button>
          </div>
        </aside>

        <main className="main">
          {activeNav === "uploads" && (
            <>
              <div className="main-head">
                <div>
                  <div className="page-title">Upload Documents</div>
                  <div className="page-sub">
                    Start with an SoV, then add FRA and FRAEW evidence against the matched blocks.
                  </div>
                </div>
              </div>

              <IngestionPage
                hasSovData={Boolean(ingestionResult)}
                isUploading={isUploading}
                uploadError={uploadError}
                pipelineStep={pipelineStep}
                ingestionSummary={ingestionSummary}
                latestFireRiskPayload={latestFireRiskPayload}
                selectedBlockReference={selectedBlockReference}
                onSelectedBlockReferenceChange={setSelectedBlockReference}
                selectedPropertyId={selectedPropertyId}
                onSelectedPropertyIdChange={setSelectedPropertyId}
                onFilesSelected={(files, stage) => {
                  const nextStage = String(stage || "SOV").toUpperCase();

                  if (nextStage === "SOV") {
                    setUploadMode("sov");
                    handleFiles(files, "SOV");
                    return;
                  }

                  setUploadMode("fire");

                  if (nextStage === "FRA") {
                    setPdfDocumentType("fra");
                    handleFiles(files, "FRA");
                    return;
                  }

                  if (nextStage === "FRAEW") {
                    setPdfDocumentType("fraew");
                    handleFiles(files, "FRAEW");
                  }
                }}
              />

              {latestFireRiskPayload && (
                <div className="card" style={{ marginTop: 16 }}>
                  <div className="card-header row-between">
                    <div>
                      <div className="card-title">Latest PDF extraction</div>
                      <div className="card-subtitle">
                        Returned from the most recent FRA / FRAEW upload.
                      </div>
                    </div>
                    <span className="pill pill-muted">
                      {latestFireRiskPayload.document_type?.toUpperCase() || "PDF"}
                    </span>
                  </div>

                  <div className="table-wrap">
                    <table className="table">
                      <tbody>
                        <tr>
                          <td className="td-key">Upload ID</td>
                          <td>{latestFireRiskPayload.upload_id || "—"}</td>
                        </tr>
                        <tr>
                          <td className="td-key">Feature ID</td>
                          <td>{latestFireRiskPayload.feature_id || "—"}</td>
                        </tr>
                        <tr>
                          <td className="td-key">Block reference</td>
                          <td>{latestFireRiskPayload.block_reference || "—"}</td>
                        </tr>
                        <tr>
                          <td className="td-key">Block ID</td>
                          <td>{latestFireRiskPayload.block_id || "—"}</td>
                        </tr>
                        <tr>
                          <td className="td-key">Property ID</td>
                          <td>{latestFireRiskPayload.property_id || "—"}</td>
                        </tr>
                        <tr>
                          <td className="td-key">Extraction errors</td>
                          <td>
                            {Array.isArray(latestFireRiskPayload.extraction_errors) &&
                            latestFireRiskPayload.extraction_errors.length
                              ? latestFireRiskPayload.extraction_errors.join(" · ")
                              : "None"}
                          </td>
                        </tr>
                        <tr>
                          <td className="td-key">FRA risk</td>
                          <td>
                            {latestFireRiskPayload.fra?.risk_level ||
                              latestFireRiskPayload.fra?.raw_rating ||
                              "—"}
                          </td>
                        </tr>
                        <tr>
                          <td className="td-key">FRAEW risk</td>
                          <td>
                            {latestFireRiskPayload.fraew?.risk_level ||
                              latestFireRiskPayload.fraew?.raw_rating ||
                              "—"}
                          </td>
                        </tr>
                        <tr>
                          <td className="td-key">Remediation required</td>
                          <td>
                            {latestFireRiskPayload.fraew?.remediation_required === true
                              ? "Yes"
                              : latestFireRiskPayload.fraew?.remediation_required === false
                              ? "No"
                              : "—"}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}

          {activeNav === "overview" && (
            <PortfolioDashboard
              ingestionResult={ingestionResult}
              ingestionSummary={ingestionSummary}
              onUploadNew={handleUploadNew}
              latestFireRiskPayload={latestFireRiskPayload}
              fireDocumentsLoading={fireDocumentsLoading}
              refetchFireDocuments={refetchFireDocuments}
              portfolioId={getPortfolioIdFromResult(ingestionResult)}
              onLoadMapData={loadPropertiesFromApi}
            />
          )}
        </main>
      </div>
    </div>
  );
}
