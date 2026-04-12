import React, { useEffect, useMemo, useState } from "react";

import LandingPage from "./Landingpage.jsx";
import IngestionPage from "./pages/IngestionPage.jsx";
import PortfolioDashboard from "./pages/PortfolioDashboard.jsx";

import { getIngestionSummary } from "./utils/ingestion";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

const toNumberOrNull = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const looksLikeLatitude = (value) => {
  const n = Number(value);
  return Number.isFinite(n) && n >= -90 && n <= 90 && n !== 0;
};

const looksLikeLongitude = (value) => {
  const n = Number(value);
  return Number.isFinite(n) && n >= -180 && n <= 180 && n !== 0;
};

const readinessBandFromScore = (score) => {
  const s = Number(score) || 0;
  if (s >= 80) return "Green";
  if (s >= 50) return "Amber";
  return "Red";
};

const normaliseProperty = (row, index = 0) => {
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

  const fallbackY =
    toNumberOrNull(row.y_coordinate) ??
    toNumberOrNull(row.y);

  const fallbackX =
    toNumberOrNull(row.x_coordinate) ??
    toNumberOrNull(row.x);

  const latitude =
    directLatitude ??
    (looksLikeLatitude(fallbackY) ? fallbackY : null);

  const longitude =
    directLongitude ??
    (looksLikeLongitude(fallbackX) ? fallbackX : null);

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

    property_id:
      row.property_id ??
      row.propertyId ??
      "",

    property_reference:
      row.property_reference ??
      row.propertyReference ??
      "",

    address_line_1:
      row.address_line_1 ??
      row.address1 ??
      row.address ??
      row.property_address ??
      "",

    address_line_2:
      row.address_line_2 ??
      row.address2 ??
      row.address_2 ??
      "",

    address_3:
      row.address_3 ??
      row.address3 ??
      "",

    city:
      row.city ??
      row.town ??
      row.locality ??
      row.address_3 ??
      "",

    post_code:
      row.post_code ??
      row.postcode ??
      row.zip ??
      "",

    uprn:
      row.uprn ??
      row.UPRN ??
      "",

    parent_uprn:
      row.parent_uprn ??
      "",

    block_reference:
      row.block_reference ??
      "",

    uprn_match_score:
      toNumberOrNull(row.uprn_match_score) ??
      toNumberOrNull(row.match_score),

    uprn_match_description:
      row.uprn_match_description ??
      row.match_description ??
      "",

    latitude,
    longitude,
    x_coordinate: fallbackX,
    y_coordinate: fallbackY,
    hasValidCoords,

    sum_insured:
      toNumberOrNull(row.sum_insured) ??
      toNumberOrNull(row.sumInsured) ??
      toNumberOrNull(row.total_sum_insured) ??
      toNumberOrNull(row.tiv) ??
      0,

    property_type:
      row.property_type ??
      row.propertyType ??
      row.type ??
      "",

    occupancy_type:
      row.occupancy_type ??
      row.occupancyType ??
      row.occupancy ??
      "",

    height_m:
      toNumberOrNull(row.height_m) ??
      toNumberOrNull(row.height) ??
      toNumberOrNull(row.height_max_m) ??
      toNumberOrNull(row.building_height_m),

    storeys:
      toNumberOrNull(row.storeys) ??
      toNumberOrNull(row.max_storeys),

    units:
      toNumberOrNull(row.units) ??
      toNumberOrNull(row.unit_count) ??
      toNumberOrNull(row.number_of_flats),

    year_of_build:
      toNumberOrNull(row.year_of_build) ??
      toNumberOrNull(row.year_built),

    wall_construction:
      row.wall_construction ?? "",

    roof_construction:
      row.roof_construction ?? "",

    built_form:
      row.built_form ?? "",

    total_floor_area_m2:
      toNumberOrNull(row.total_floor_area_m2),

    main_fuel:
      row.main_fuel ?? "",

    epc_rating:
      row.epc_rating ?? "",

    epc_potential_rating:
      row.epc_potential_rating ?? "",

    epc_lodgement_date:
      row.epc_lodgement_date ?? "",

    country_code:
      row.country_code ?? "",

    height_roofbase_m:
      toNumberOrNull(row.height_roofbase_m),

    height_confidence:
      row.height_confidence ?? "",

    building_footprint_m2:
      toNumberOrNull(row.building_footprint_m2),

    is_listed:
      typeof row.is_listed === "boolean" ? row.is_listed : row.is_listed ?? null,

    listed_grade:
      row.listed_grade ?? "",

    listed_name:
      row.listed_name ?? "",

    listed_reference:
      row.listed_reference ?? "",

    enrichment_status:
      row.enrichment_status ?? "",

    enrichment_source:
      row.enrichment_source ?? "",

    enriched_at:
      row.enriched_at ?? null,

    readiness_score: readinessScore,
    readiness_band:
      row.readiness_band ??
      row.readinessBand ??
      readinessBandFromScore(readinessScore),

    missing_fields:
      row.missing_fields ??
      row.missingFields ??
      row.validation?.missing_fields ??
      [],

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
    storage: payload?.storage ?? null,
    message: payload?.message ?? null,
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

export default function App() {
  const [showLanding, setShowLanding] = useState(true);
  const [activeNav, setActiveNav] = useState("uploads");

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [pipelineStep, setPipelineStep] = useState(null);

  const [ingestionResult, setIngestionResult] = useState(null);

  const ingestionSummary = useMemo(
    () => getIngestionSummary(ingestionResult),
    [ingestionResult]
  );

  useEffect(() => {
    console.log("API_BASE_URL =", API_BASE_URL);
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

  const PIPELINE_STEPS = [
    "Queued",
    "Checking file format",
    "Uploading file",
    "Running backend ingestion",
    "Normalising response",
    "Preparing portfolio dashboard",
    "Finalising",
    "Complete",
  ];

  const runPipeline = () => {
    setPipelineStep(PIPELINE_STEPS[0]);
    PIPELINE_STEPS.slice(1).forEach((step, i) => {
      setTimeout(() => setPipelineStep(step), 380 * (i + 1));
    });
  };

  const handleFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    const file = files[0];

    setUploadError(null);
    setIsUploading(true);
    runPipeline();

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        `${API_BASE_URL}/api/v1/upload/ingest?document_type=sov`,
        {
          method: "POST",
          body: formData,
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
            : payload?.detail ??
              payload?.error ??
              JSON.stringify(payload);
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

      const normalised = normaliseBackendIngestionResult(payload, file.name);

      setIngestionResult(normalised);
      setActiveNav("overview");
      setPipelineStep("Complete");

      setTimeout(() => {
        setPipelineStep(null);
      }, 900);
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
      <LandingPage
        onGetStarted={() => {
          setShowLanding(false);
          setActiveNav("uploads");
        }}
      />
    );
  }

  const loadedMeta = ingestionSummary
    ? `Loaded: ${ingestionSummary.source} · Properties: ${ingestionSummary.propertyCount} · Value: £${Number(
        ingestionSummary.totalValue || 0
      ).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    : "Upload a file to begin";

  return (
    <div className="app">
      <div className="topbar">
        <div className="topbar-left">
          Upload SOVs, analyse exposure, assess portfolio risk.
        </div>
        <div className="topbar-right">{loadedMeta}</div>
      </div>

      <div className="shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-title">EquiRisk</div>
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
              Upload SoV
            </button>
          </div>

          <div className="side-section dim">
            <div className="side-head">Analysis</div>
            <div className="side-item">Evidence Summary</div>
            <div className="side-item">Block Analysis</div>
            <div className="side-item">Documents</div>
          </div>

          <div className="side-bottom">
            <button
              className="btn btn-ghost"
              onClick={() => setShowLanding(true)}
            >
              ⟵ Back
            </button>
          </div>
        </aside>

        <main className="main">
          {activeNav === "uploads" && (
            <>
              <div className="main-head">
                <div>
                  <div className="page-title">Upload SoV</div>
                  <div className="page-sub">
                    Upload an SOV-style file. The backend ingests it, normalizes the
                    rows, and prepares the portfolio dashboard.
                  </div>
                </div>
              </div>

              <IngestionPage
                onFilesSelected={handleFiles}
                pipelineStep={pipelineStep}
                ingestionSummary={ingestionSummary}
                uploadError={uploadError}
                isUploading={isUploading}
              />
            </>
          )}

          {activeNav === "overview" && (
            <PortfolioDashboard
              ingestionResult={ingestionResult}
              ingestionSummary={ingestionSummary}
              onUploadNew={handleUploadNew}
            />
          )}
        </main>
      </div>
    </div>
  );
}