import React, { useEffect, useMemo, useRef, useState } from "react";

import LoginPage from "./pages/LoginPage.jsx";
import IngestionPage from "./pages/IngestionLandingPage.jsx";
import PortfolioDashboard from "./pages/PortfolioDashboard.jsx";
import PortfolioInsightsPage from "./pages/PortfolioInsightsPage.jsx";
import BlockAnalysisPage from "./pages/BlockAnalysisPage.jsx";
import FullMapPage from "./pages/FullMapPage.jsx";
import Sidebar from "./components/Sidebar.jsx";

import { getIngestionSummary } from "./utils/ingestion";
import { collectFireDocuments } from "./utils/blockModel";
import {
  normaliseFireRiskPayload,
  normaliseBackendIngestionResult,
  attachSingleFirePayloadToPortfolio,
  mergeFireDocumentsIntoPortfolio,
  getPortfolioIdFromResult,
} from "./utils/normalise.js";
import { apiFetch, API_BASE_URL as CLIENT_API_BASE_URL } from "./services/apiClient";

// Single source of truth — same default as apiClient.js ("http://localhost:8000").
// Previously this fell back to "" which silently blocked the fire-documents fetch
// (the !API_BASE_URL guard) while apiFetch-based calls still worked.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || CLIENT_API_BASE_URL;

export default function App() {
  const [showLanding, setShowLanding] = useState(true);
  const [authUser, setAuthUser] = useState(null);
  const [activeNav, setActiveNav] = useState("uploads");
  // Mobile off-canvas drawer state — only relevant below the 900px breakpoint.
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Track which tabs have been opened. Once a tab is visited we keep it mounted
  // (just hidden) so its state — map position, selections, scroll — survives
  // switching tabs instead of resetting on every remount.
  const [visitedNav, setVisitedNav] = useState({ uploads: true });
  // View (center + zoom) handed from the dashboard mini-map to the risk map on
  // click-through, so the risk map opens where the user had zoomed.
  const [riskMapView, setRiskMapView] = useState(null);

  const openFullMap = (view) => {
    setRiskMapView(view ? { ...view } : null); // new object → forces re-apply
    setActiveNav("risk-map");
  };

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [pipelineStep, setPipelineStep] = useState(null);

  const [uploadMode, setUploadMode] = useState("sov");
  const [pdfDocumentType, setPdfDocumentType] = useState("fra");
  // Which upload stage the Upload Documents page should show (SOV / FRA / FRAEW).
  const [uploadStage, setUploadStage] = useState("SOV");
  const [selectedBlockReference, setSelectedBlockReference] = useState("");
  const [selectedPropertyId, setSelectedPropertyId] = useState("");

  const [accessibleHAs, setAccessibleHAs] = useState([]);
  const [selectedHaId, setSelectedHaId] = useState("ha_demo");

  const [ingestionResult, setIngestionResult] = useState(null);
  // Original SoV filename. Known only at upload time; the DB re-pull doesn't
  // return it, so persist it in sessionStorage to survive the re-pull + refresh.
  const sovFileNameRef = useRef(
    typeof window !== "undefined"
      ? window.sessionStorage.getItem("equirisk:sovFileName") || null
      : null
  );
  const [latestFireRiskPayload, setLatestFireRiskPayload] = useState(null);
  const [fireDocumentsLoading, setFireDocumentsLoading] = useState(false);

  const ingestionSummary = useMemo(
    () => getIngestionSummary(ingestionResult),
    [ingestionResult]
  );

  // Flat list of every document ingested so far (SoV + FRA/FRAEW evidence),
  // shaped for the upload-page document summary table.
  const uploadedDocuments = useMemo(() => {
    if (!ingestionResult) return [];

    const docs = [];

    docs.push({
      id: "sov",
      name: ingestionSummary?.source || "Schedule of Values",
      type: "SOV",
      linked:
        ingestionSummary?.propertyCount != null
          ? `${ingestionSummary.propertyCount.toLocaleString()} properties`
          : "Portfolio",
      rating: null,
    });

    collectFireDocuments(ingestionResult, latestFireRiskPayload).forEach((d) => {
      docs.push({
        id: d.id,
        name: d.filename || "Uploaded PDF",
        type: d.document_type || "FIRE",
        linked: d.block_reference
          ? `Block ${d.block_reference}`
          : d.property_id
          ? `Property ${d.property_id}`
          : "Unlinked",
        rating: d.risk_level || null,
      });
    });

    return docs;
  }, [ingestionResult, ingestionSummary, latestFireRiskPayload]);

  const currentPortfolioId = useMemo(
    () => getPortfolioIdFromResult(ingestionResult),
    [ingestionResult]
  );

  useEffect(() => {
    console.log("API_BASE_URL =", API_BASE_URL);
  }, []);

  // Remember each tab once opened so kept-alive views stay mounted.
  useEffect(() => {
    setVisitedNav((v) => (v[activeNav] ? v : { ...v, [activeNav]: true }));
  }, [activeNav]);

  // Maps are hidden via display:none when inactive; nudge Leaflet to
  // recompute its size when reshown so tiles render at the right dimensions.
  useEffect(() => {
    if (activeNav !== "overview" && activeNav !== "risk-map") return;
    const t = setTimeout(() => window.dispatchEvent(new Event("resize")), 60);
    return () => clearTimeout(t);
  }, [activeNav]);

  // Recover the original SoV filename from the upload-audit log. Best-effort:
  // returns the most recent "property_schedule" submission's filename, or null.
  const fetchLatestSovFilename = async () => {
    try {
      const res = await apiFetch("/api/v1/upload/submissions?limit=50");
      const data = await res.json();
      const items = Array.isArray(data?.items) ? data.items : [];
      // Endpoint returns newest-first; take the first SoV submission.
      const sov = items.find((it) => it?.file_type === "property_schedule");
      const name = sov?.filename;
      return typeof name === "string" && name.trim() ? name : null;
    } catch (err) {
      console.warn("[fetchLatestSovFilename] Failed:", err);
      return null;
    }
  };

  // Fetch the list of HAs this underwriter has access to.
  const fetchAccessibleHAs = async () => {
    try {
      const res = await apiFetch("/api/v1/underwriter/home");
      const data = await res.json();
      const portfolios = data?.portfolios || [];
      const seen = new Set();
      const has = [];
      for (const p of portfolios) {
        if (!seen.has(p.ha_id)) {
          seen.add(p.ha_id);
          has.push({ ha_id: p.ha_id, ha_name: p.ha_name });
        }
      }
      if (has.length > 0) {
        setAccessibleHAs(has);
        setSelectedHaId((prev) => (has.find((h) => h.ha_id === prev) ? prev : has[0].ha_id));
      } else {
        setAccessibleHAs([{ ha_id: "ha_demo", ha_name: "Albyn Housing Association" }]);
        setSelectedHaId("ha_demo");
      }
    } catch {
      setAccessibleHAs([{ ha_id: "ha_demo", ha_name: "Albyn Housing Association" }]);
      setSelectedHaId("ha_demo");
    }
  };

  const loadPropertiesFromApi = async (overridePortfolioId = null, overrideHaId = null) => {
    try {
      // Backend returns ONE portfolio (latest for the HA by default) — pass the
      // explicit portfolio when we have it (e.g. straight after an upload).
      // overrideHaId dodges the stale closure when called right after setSelectedHaId.
      const haId = overrideHaId ?? selectedHaId;
      const params = new URLSearchParams();
      if (haId) params.set("ha_id", haId);
      if (overridePortfolioId) params.set("portfolio_id", overridePortfolioId);
      const qs = params.toString();
      const res = await apiFetch(`/api/v1/portfolios/properties${qs ? `?${qs}` : ""}`);
      const rawRows = await res.json();
      if (Array.isArray(rawRows) && rawRows.length > 0) {
        // The properties endpoint doesn't carry the original SoV filename.
        // Prefer the name captured this session; otherwise recover it from the
        // upload-audit log (survives hard refresh / a fresh tab).
        const sovName =
          sovFileNameRef.current || (await fetchLatestSovFilename()) || "Portfolio";
        if (sovName !== "Portfolio") {
          sovFileNameRef.current = sovName;
        }
        // Read portfolio_id from the RAW rows before normalisation —
        // normaliseProperty doesn't copy portfolio_id so we must read it here.
        const portfolioId =
          overridePortfolioId ??
          rawRows[0]?.portfolio_id ??
          null;
        // Normalise rows for the rest of the app
        const properties = rawRows;
        const normalised = normaliseBackendIngestionResult(
          { properties, status: "success", portfolio_id: portfolioId },
          sovName
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
        // Re-hydrate accessible HAs + portfolio from DB.
        fetchAccessibleHAs();
        loadPropertiesFromApi();
      } catch {
        // corrupted storage — ignore
      }
    }
  }, []);

  // The embedded holding page (public/holding.html) posts this when its
  // "Login / Register" CTA is clicked — leave the landing and enter the app.
  useEffect(() => {
    const onMsg = (e) => {
      if (e?.data === "equirisk-enter-app") setShowLanding(false);
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
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

    // For SoV, real enrichment progress drives the later steps (3→6). Cap the
    // canned timers at step 2 so they can't overshoot to the end and then jump
    // BACKWARDS when enrichment progress (starting near 0) takes over.
    const maxFakeSteps = docType === "sov" ? 2 : steps.length;

    steps.slice(1, maxFakeSteps).forEach((step, i) => {
      const id = setTimeout(() => setPipelineStep(step), 3500 * (i + 1));
      pipelineTimersRef.current.push(id);
    });
  };

  // After an SoV upload, the backend enriches a capped batch of properties in
  // the background. We keep the loading screen up and poll the enrichment job
  // status until it reports complete/failed (not every row gets enriched — we
  // just wait for the process to finish), with a safety timeout so the UI can
  // never hang if the job never reports.
  const waitForEnrichment = async (haId) => {
    const POLL_MS = 3000;
    // No wall-clock cap: we WAIT until the job reports complete/failed (i.e. all
    // target properties processed). The only escape hatch is a true stall — no
    // new property finishing for STALL_MS — so a dead backend can't hang the UI
    // forever, but a slow-but-progressing run always finishes all of them first.
    const STALL_MS = 180000; // 3 min with zero progress = give up
    setPipelineStep("Enriching properties");
    let lastProcessed = -1;
    let lastProgressAt = Date.now();

    while (true) {
      await new Promise((resolve) => setTimeout(resolve, POLL_MS));
      try {
        const res = await apiFetch(`/api/v1/enrich/${haId}/status`);
        const data = await res.json();
        const counts = data?.counts || {};
        const processed = (counts.enriched || 0) + (counts.failed || 0);
        const target = data?.target || 0;
        // Encode processed/target so the step indicator can advance smoothly.
        setPipelineStep(
          target > 0
            ? `Enriching properties — ${processed}/${target}`
            : processed > 0
            ? `Enriching properties — ${processed} processed`
            : "Enriching properties"
        );
        // Terminal: the job finished everything it was going to process.
        if (data?.job_status === "complete" || data?.job_status === "failed") {
          return data;
        }
        // Progress watchdog — reset the clock whenever a property completes.
        if (processed > lastProcessed) {
          lastProcessed = processed;
          lastProgressAt = Date.now();
        } else if (Date.now() - lastProgressAt > STALL_MS) {
          console.warn("[waitForEnrichment] no progress for 3 min — opening dashboard");
          return data;
        }
      } catch (err) {
        console.warn("[waitForEnrichment] status poll failed:", err);
      }
    }
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
      // fireDocsPayload is a list ({ items: [...] }); latestFireRiskPayload must
      // hold a SINGLE doc (the side panel + collectFireDocuments expect one).
      // Use the most-recent item; null if there are none.
      const items = Array.isArray(fireDocsPayload?.items) ? fireDocsPayload.items : [];
      setLatestFireRiskPayload(items.length ? items[0] : null);
    }

    return fireDocsPayload;
  };

  useEffect(() => {
    if (!currentPortfolioId || !API_BASE_URL || !ingestionResult) return;

    refetchFireDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPortfolioId]);

  // Re-pull FRA/FRAEW whenever the user opens Overview or Block Analysis, so newly
  // uploaded fire documents appear without a manual page refresh.
  useEffect(() => {
    if (!currentPortfolioId || !API_BASE_URL || !ingestionResult) return;
    if (activeNav === "overview" || activeNav === "block-analysis") {
      refetchFireDocuments();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeNav]);

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
      if (selectedHaId) query.set("ha_id", selectedHaId);

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
        // Remember the real SoV filename so it survives the post-enrichment
        // DB re-pull (loadPropertiesFromApi) and a later hard refresh.
        sovFileNameRef.current = file.name;
        if (typeof window !== "undefined") {
          window.sessionStorage.setItem("equirisk:sovFileName", file.name);
        }
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

        // Show the un-enriched data immediately as a fallback, then wait for the
        // background enrichment job to finish before revealing the dashboard.
        setIngestionResult(normalised);
        setLatestFireRiskPayload(normalised.fire_risk_payload ?? null);

        // Stop the fake timed pipeline steps; from here we track REAL enrichment.
        pipelineTimersRef.current.forEach((id) => clearTimeout(id));
        pipelineTimersRef.current = [];

        // Keep the loading screen up until enrichment completes.
        const haId = payload?.ha_id || selectedHaId || "ha_demo";
        await waitForEnrichment(haId);

        // Re-pull rows so the dashboard opens with enriched coords + blocks.
        // Pass portfolio_id from the upload response so we restore the right portfolio.
        await loadPropertiesFromApi(payload?.portfolio_id ?? null);

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

        // Prefer the portfolio_id the backend resolved for this FRA/FRAEW — it's
        // always present, unlike the closure-captured currentPortfolioId which can
        // be stale, which is why new uploads previously only showed after a refresh.
        const portfolioId =
          payload?.portfolio_id ??
          currentPortfolioId ??
          getPortfolioIdFromResult(ingestionResult);

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

  const handleUploadNew = (stage = "SOV") => {
    const next = String(stage || "SOV").toUpperCase();
    setUploadStage(["SOV", "FRA", "FRAEW"].includes(next) ? next : "SOV");
    setActiveNav("uploads");
    setUploadError(null);
    setPipelineStep(null);
  };

  // "Upload Documents" routes to the next document still needed: SoV -> FRA -> FRAEW.
  // Once a full set exists it falls back to the FRA evidence stage.
  const goToNextUpload = () => {
    if (!ingestionResult) return handleUploadNew("SOV");
    const docs = collectFireDocuments(ingestionResult, latestFireRiskPayload);
    const hasFra = docs.some((d) => d.document_type === "FRA");
    const hasFraew = docs.some((d) => d.document_type === "FRAEW");
    handleUploadNew(!hasFra ? "FRA" : !hasFraew ? "FRAEW" : "FRA");
  };

  if (showLanding) {
    return (
      <iframe
        title="EquiRisk — Premium Intelligence"
        src="/holding.html"
        style={{ position: "fixed", inset: 0, width: "100%", height: "100%", border: "none" }}
      />
    );
  }

  if (!authUser) {
    return (
      <LoginPage
        onLogin={(user) => {
          setAuthUser(user);
          setActiveNav("uploads");
          fetchAccessibleHAs();
          loadPropertiesFromApi();
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
        <button
          className="nav-toggle"
          onClick={() => setSidebarOpen(true)}
          aria-label="Open navigation"
        >
          ☰
        </button>
        <div className="topbar-left">Upload SOVs, analyse exposure, assess portfolio risk.</div>
        <div className="topbar-right">{loadedMeta}</div>
      </div>

      <div className="shell">
        {sidebarOpen && (
          <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />
        )}
        <Sidebar
          accessibleHAs={accessibleHAs}
          selectedHaId={selectedHaId}
          activeNav={activeNav}
          ingestionResult={ingestionResult}
          authUser={authUser}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onSelectHa={(haId) => {
            setSelectedHaId(haId);
            setIngestionResult(null);
            setActiveNav("uploads");
            setUploadStage("SOV");
            setSidebarOpen(false);
            // Load the new HA's latest portfolio — switching must never leave
            // the workspace empty when the HA already has data.
            loadPropertiesFromApi(null, haId);
          }}
          onUploadDocuments={() => {
            setSidebarOpen(false);
            goToNextUpload();
          }}
          onNavigate={(nav) => {
            setActiveNav(nav);
            setSidebarOpen(false);
          }}
          onSignOut={() => {
            localStorage.removeItem("equirisk_token");
            localStorage.removeItem("equirisk_user");
            sessionStorage.removeItem("equirisk_token");
            sessionStorage.removeItem("equirisk_user");
            sessionStorage.removeItem("equirisk:sovFileName");
            sovFileNameRef.current = null;
            setSidebarOpen(false);
            setAuthUser(null);
            setIngestionResult(null);
            setAccessibleHAs([]);
            setSelectedHaId("ha_demo");
            setShowLanding(true);
          }}
        />

        <main className={activeNav === "risk-map" ? "main main--map" : "main"}>
          {activeNav === "uploads" && (
            <>
              <div className="main-head">
                <div>
                  <div className="tag">Portfolio ingestion</div>
                  <div className="page-title">Upload your <em>portfolio</em></div>
                  {accessibleHAs.find((h) => h.ha_id === selectedHaId)?.ha_name && (
                    <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                      For: <strong style={{ color: "var(--terracotta)" }}>{accessibleHAs.find((h) => h.ha_id === selectedHaId)?.ha_name}</strong>
                    </div>
                  )}
                </div>
              </div>

              <IngestionPage
                stage={uploadStage}
                onStageChange={setUploadStage}
                hasSovData={Boolean(ingestionResult)}
                haId={selectedHaId}
                haName={accessibleHAs.find((h) => h.ha_id === selectedHaId)?.ha_name || authUser?.organisation || ""}
                isUploading={isUploading}
                uploadError={uploadError}
                pipelineStep={pipelineStep}
                ingestionSummary={ingestionSummary}
                latestFireRiskPayload={latestFireRiskPayload}
                documents={uploadedDocuments}
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


            </>
          )}

          {(visitedNav.overview || activeNav === "overview") && (
            <div style={{ display: activeNav === "overview" ? "block" : "none" }}>
              <PortfolioDashboard
                ingestionResult={ingestionResult}
                ingestionSummary={ingestionSummary}
                onUploadNew={handleUploadNew}
                latestFireRiskPayload={latestFireRiskPayload}
                fireDocumentsLoading={fireDocumentsLoading}
                refetchFireDocuments={refetchFireDocuments}
                portfolioId={getPortfolioIdFromResult(ingestionResult)}
                onLoadMapData={loadPropertiesFromApi}
                onOpenFullMap={openFullMap}
                haName={accessibleHAs.find((h) => h.ha_id === selectedHaId)?.ha_name || authUser?.organisation || ""}
              />
            </div>
          )}

          {(visitedNav.insights || activeNav === "insights") && (
            <div style={{ display: activeNav === "insights" ? "block" : "none" }}>
              <PortfolioInsightsPage
                ingestionResult={ingestionResult}
                onUploadNew={handleUploadNew}
                haName={accessibleHAs.find((h) => h.ha_id === selectedHaId)?.ha_name || authUser?.organisation || ""}
              />
            </div>
          )}

          {(visitedNav["block-analysis"] || activeNav === "block-analysis") && (
            <div style={{ display: activeNav === "block-analysis" ? "block" : "none" }}>
              <BlockAnalysisPage
                ingestionResult={ingestionResult}
                latestFireRiskPayload={latestFireRiskPayload}
                onUploadNew={handleUploadNew}
                haName={accessibleHAs.find((h) => h.ha_id === selectedHaId)?.ha_name || authUser?.organisation || ""}
              />
            </div>
          )}

          {(visitedNav["risk-map"] || activeNav === "risk-map") && (
            <div style={{ display: activeNav === "risk-map" ? "block" : "none" }}>
              <FullMapPage
                properties={ingestionResult?.properties ?? []}
                initialView={riskMapView}
              />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
