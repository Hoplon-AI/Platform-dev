import React, { useEffect, useMemo, useRef, useState } from "react";

import PortfolioMap from "../components/PortfolioMap.jsx";
import PropertyDetails from "../components/PropertyDetails.jsx";
import {
  fmtMoney,
  hasValidLatLon,
  normaliseKey,
  sameProperty,
  sameBlock,
  getFireRiskBand,
  collectFireDocumentsFromIngestion,
} from "../utils/fireRisk.js";
import {
  KpiCard,
  HoverTooltip,
} from "../components/dashboard/DashboardWidgets.jsx";
import { KPI_ICONS, fireRiskSubtitle } from "../components/dashboard/dashboardHelpers.jsx";
import { blockOverallBand } from "../utils/blockModel.js";
import {
  FireEvidencePanel,
  UnderwriterDocumentsPanel,
} from "../components/dashboard/DashboardPanels.jsx";

export { PortfolioAnalysisWindow } from "../components/dashboard/DashboardPanels.jsx";

export default function PortfolioDashboard({
  ingestionResult,
  ingestionSummary,
  onUploadNew,
  latestFireRiskPayload = null,
  fireDocumentsLoading = false,
  refetchFireDocuments,
  portfolioId = null,
  onLoadMapData,
  onOpenFullMap,
  haName = "",
}) {
  const properties = ingestionResult?.properties || [];
  const miniMapViewRef = useRef(null);
  const [selectedBlock, setSelectedBlock] = useState(null);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [mapDataLoading, setMapDataLoading] = useState(false);
  const [suppressMapFit, setSuppressMapFit] = useState(false);

  const resolvedPortfolioId = portfolioId || null;

  const fireDocuments = useMemo(
    () => collectFireDocumentsFromIngestion(ingestionResult, latestFireRiskPayload),
    [ingestionResult, latestFireRiskPayload]
  );

  const baseBlocks = useMemo(() => {
    if (!properties.length) return [];

    const grouped = new Map();

    properties.forEach((property) => {
      const key =
        property.block_reference ||
        property.parent_uprn ||
        property.uprn ||
        property.property_reference ||
        property.id;

      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(property);
    });

    return Array.from(grouped.entries())
      .map(([key, items]) => {
        const mappable = items.filter((p) => hasValidLatLon(p.latitude, p.longitude));
        const lat =
          mappable.length > 0
            ? mappable.reduce((sum, p) => sum + Number(p.latitude), 0) / mappable.length
            : null;
        const lon =
          mappable.length > 0
            ? mappable.reduce((sum, p) => sum + Number(p.longitude), 0) / mappable.length
            : null;
        const totalValue = items.reduce((sum, p) => sum + (Number(p.sum_insured) || 0), 0);
        const maxHeight = items.reduce((max, p) => {
          const height = Number(p.height_m);
          return Number.isFinite(height) ? Math.max(max, height) : max;
        }, 0);
        const representativeProperty = mappable[0] || items.find((p) => p.uprn) || items[0] || null;

        return {
          id: key,
          block_id: key,
          label: key || "Unassigned block",
          name: key || "Unassigned block",
          properties: items,
          count: items.length,
          lat,
          lon,
          latitude: lat,
          longitude: lon,
          __lat: lat,
          __lon: lon,
          hasValidCoords: hasValidLatLon(lat, lon),
          totalValue,
          maxHeight,
          parent_uprn:
            items.find((p) => p.parent_uprn)?.parent_uprn ||
            items.find((p) => p.uprn)?.uprn ||
            null,
          block_reference: key || "",
          representativeProperty,
          // ponytail: flats in a block share a footprint — take the first present.
          geometry: items.find((p) => p.building_geometry)?.building_geometry ?? null,
        };
      })
      .sort((a, b) => b.totalValue - a.totalValue);
  }, [properties]);

  const blocks = useMemo(() => {
    return baseBlocks.map((block) => {
      const blockAliases = [
        block.id,
        block.block_id,
        block.label,
        block.name,
        block.block_reference,
        block.parent_uprn,
      ]
        .map(normaliseKey)
        .filter(Boolean);

      const linkedDocs = fireDocuments.filter((doc) => {
        const docBlock = normaliseKey(doc.block_reference || doc.block_id);
        const docProperty = normaliseKey(doc.property_id);
        const blockMatch = docBlock && blockAliases.includes(docBlock);
        const propertyMatch =
          docProperty &&
          block.properties.some((property) =>
            [property.id, property.property_id, property.property_reference, property.uprn]
              .map(normaliseKey)
              .filter(Boolean)
              .includes(docProperty)
          );
        return blockMatch || propertyMatch;
      });

      const propertyFra = block.properties.find((p) => p.latest_fra)?.latest_fra ?? null;
      const propertyFraew = block.properties.find((p) => p.latest_fraew)?.latest_fraew ?? null;
      const latestFraDoc = linkedDocs.find((doc) => doc.document_type === "FRA") ?? null;
      const latestFraewDoc = linkedDocs.find((doc) => doc.document_type === "FRAEW") ?? null;
      const latestFra = latestFraDoc?.fra ?? latestFraDoc ?? propertyFra;
      const latestFraew = latestFraewDoc?.fraew ?? latestFraewDoc ?? propertyFraew;

      return {
        ...block,
        latest_fra: latestFra,
        latest_fraew: latestFraew,
        fire_documents: {
          fra: latestFra,
          fraew: latestFraew,
          all: linkedDocs,
        },
      };
    });
  }, [baseBlocks, fireDocuments]);

  // Auto-poll for enriched coordinates after SoV upload.
  // Fires every 15s while properties exist but none have coords, up to 3 minutes.
  useEffect(() => {
    if (typeof onLoadMapData !== "function") return;
    if (!properties.length) return;

    const hasAnyCoords = () => properties.some((p) => p.hasValidCoords);

    // Do an immediate fetch first
    if (!hasAnyCoords()) {
      setMapDataLoading(true);
      onLoadMapData().finally(() => setMapDataLoading(false));
    }

    // Then poll every 15s for up to 3 minutes (12 attempts)
    let attempts = 0;
    const MAX_ATTEMPTS = 12;
    const interval = setInterval(() => {
      if (hasAnyCoords() || attempts >= MAX_ATTEMPTS) {
        clearInterval(interval);
        return;
      }
      attempts++;
      onLoadMapData();
    }, 15000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLoadMapData = () => {
    if (typeof onLoadMapData !== "function" || mapDataLoading) return;
    setMapDataLoading(true);
    onLoadMapData().finally(() => setMapDataLoading(false));
  };

  useEffect(() => {
    if (!properties.length) {
      setSelectedBlock(null);
      setSelectedProperty(null);
      return;
    }

    if (selectedProperty) {
      const matchingProperty = properties.find((p) => sameProperty(p, selectedProperty));
      if (!matchingProperty) setSelectedProperty(null);
    }

    if (selectedBlock) {
      const matchingBlock = blocks.find((b) => sameBlock(b, selectedBlock));
      if (!matchingBlock) {
        setSelectedBlock(null);
      }
    }
  }, [properties, blocks, selectedProperty, selectedBlock]);

  const resolvedSelectedProperty = useMemo(() => {
    if (!selectedProperty) return null;
    return properties.find((p) => sameProperty(p, selectedProperty)) || null;
  }, [properties, selectedProperty]);

  const resolvedSelectedBlock = useMemo(() => {
    if (resolvedSelectedProperty) {
      return blocks.find((block) => block.properties.some((p) => sameProperty(p, resolvedSelectedProperty))) || null;
    }
    if (!selectedBlock) return null;
    return blocks.find((b) => sameBlock(b, selectedBlock)) || null;
  }, [blocks, selectedBlock, resolvedSelectedProperty]);

  const selectedBlockId = resolvedSelectedBlock?.id ?? null;
  const geoCompletenessPct = ingestionSummary?.geoCompletenessPct ?? 0;
  const highRiseBlocks = blocks.filter((b) => Number(b.maxHeight) >= 18 || Number(b.max_storeys) >= 7).length;
  const amberBlocks = blocks.filter((b) => (Number(b.maxHeight) >= 11 && Number(b.maxHeight) < 18) || (Number(b.max_storeys) >= 4 && Number(b.max_storeys) < 7)).length;
  const mappedBlocksCount = blocks.filter((b) => b.hasValidCoords).length;
  // Real block counts by worst FRA/FRAEW band for the map legend (High/Medium/Low/No evidence).
  const legendCounts = useMemo(() => {
    const c = { Red: 0, Amber: 0, Green: 0, none: 0 };
    for (const b of blocks) {
      const ob = blockOverallBand(b);
      if (ob === "Red") c.Red++;
      else if (ob === "Amber") c.Amber++;
      else if (ob === "Green") c.Green++;
      else c.none++;
    }
    return c;
  }, [blocks]);
  const enrichedPropertiesCount = properties.filter((p) => p.uprn || p.enrichment_status === "enriched").length;
  // Quality of the matches we made: share of enriched properties with a GREEN
  // (confident) OS Places UPRN match, not coverage over the whole portfolio.
  const greenMatchCount = properties.filter(
    (p) => String(p.uprn_confidence).trim().toLowerCase() === "green"
  ).length;
  const enrichedPropertiesPct =
    enrichedPropertiesCount > 0 ? Math.round((greenMatchCount / enrichedPropertiesCount) * 100) : 0;

  // Block-level RAG counts, split by evidence type (FRA vs FRAEW).
  const fireRiskCounts = useMemo(() => {
    const tally = (getDoc) =>
      blocks.reduce(
        (acc, block) => {
          const doc = getDoc(block);
          if (!doc) return acc;
          const band = getFireRiskBand(doc);
          if (band === "Red") acc.red += 1;
          else if (band === "Amber") acc.amber += 1;
          else if (band === "Green") acc.green += 1;
          return acc;
        },
        { red: 0, amber: 0, green: 0 }
      );
    return {
      fra: tally((b) => b.latest_fra),
      fraew: tally((b) => b.latest_fraew),
    };
  }, [blocks]);

  // Document counts per evidence type for the card headline values.
  const fireDocCounts = useMemo(() => {
    return fireDocuments.reduce(
      (acc, doc) => {
        const type = String(doc.document_type || "").toUpperCase();
        if (type === "FRA") acc.fra += 1;
        else if (type === "FRAEW") acc.fraew += 1;
        return acc;
      },
      { fra: 0, fraew: 0 }
    );
  }, [fireDocuments]);

  // Called by list panels and the map — selects the block for the details panel / flat-list popup (map stays in blocks view)
  const handleSelectBlock = (block) => {
    if (!block) {
      setSelectedBlock(null);
      setSelectedProperty(null);
      return;
    }
    setSuppressMapFit(true);
    const matchingBlock = blocks.find((b) => sameBlock(b, block)) || block;
    setSelectedBlock(matchingBlock);
    setSelectedProperty(null);
  };

  const handleSelectProperty = (property) => {
    if (!property) {
      setSuppressMapFit(true);
      setSelectedProperty(null);
      return;
    }
    setSuppressMapFit(true);
    const matchingProperty = properties.find((p) => sameProperty(p, property)) || property;
    setSelectedProperty(matchingProperty);
    const parentBlock = blocks.find((block) => block.properties.some((p) => sameProperty(p, matchingProperty))) || null;
    setSelectedBlock(parentBlock);
  };

  const handleClearMapSelection = () => {
    setSuppressMapFit(true);
    setSelectedBlock(null);
    setSelectedProperty(null);
  };

  const handleExport = async (docType) => {
    if (!resolvedPortfolioId) return;
    const url = `/api/v1/portfolios/${resolvedPortfolioId}/export/${docType}`;
    const token =
      localStorage.getItem("equirisk_token") ||
      sessionStorage.getItem("equirisk_token") ||
      "";
    try {
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const blob = await res.blob();
      const filename =
        res.headers.get("content-disposition")?.match(/filename="?([^"]+)"?/)?.[1] ||
        `${docType.replace("-", "_")}.xlsx`;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    } catch (err) {
      console.error("[handleExport]", err);
      alert(`Download failed: ${err.message}`);
    }
  };

  useEffect(() => {
    if (suppressMapFit) {
      const t = setTimeout(() => setSuppressMapFit(false), 50);
      return () => clearTimeout(t);
    }
  }, [suppressMapFit]);

  const detailsScrollRef = useRef(null);
  useEffect(() => {
    if (detailsScrollRef.current) {
      detailsScrollRef.current.scrollTop = 0;
    }
  }, [selectedProperty, selectedBlock]);

  if (!ingestionSummary) {
    return (
      <div className="content-wrap">
        <div className="card">
          <div className="empty-state">No portfolio loaded yet. Upload an SoV file to begin.</div>
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary" onClick={() => onUploadNew?.("SOV")}>Upload SoV</button>
          </div>
        </div>
      </div>
    );
  }

  const hasActiveBlockSelection = Boolean(resolvedSelectedBlock);
  const hasActivePropertySelection = Boolean(resolvedSelectedProperty);
  const mapMode = "blocks";
  const mapProperties = properties;

  return (
    <div className="content-wrap">
      <div className="main-head">
        <div>
          <div className="tag">Premium Intelligence</div>
          <div className="page-title">Portfolio <em>Overview</em></div>
          {haName && (
            <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
              For: <strong style={{ color: "var(--terracotta)" }}>{haName}</strong>
            </div>
          )}
        </div>

        <div className="actions" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {typeof refetchFireDocuments === "function" ? (
            <button className="btn" onClick={refetchFireDocuments} disabled={fireDocumentsLoading}>
              {fireDocumentsLoading ? "Refreshing…" : "Refresh fire evidence"}
            </button>
          ) : null}
          <button className="btn" onClick={() => onUploadNew?.("SOV")}>Upload SoV</button>
          <button className="btn btn-primary" onClick={() => onUploadNew?.("FRA")}>Upload FRA</button>
          <button className="btn btn-primary" onClick={() => onUploadNew?.("FRAEW")}>Upload FRAEW</button>
        </div>
      </div>

      <div className="dashboard-grid">
        <KpiCard
          title="Total insured value"
          value={`£${fmtMoney(ingestionSummary.totalValue)}`}
          subtitle={`Across ${ingestionSummary.propertyCount} properties`}
          icon={KPI_ICONS.value}
        />
        <KpiCard
          title={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              Flats spread across
              <HoverTooltip
                tip="Our engine groups the properties in your SoV by shared parent UPRN and address to detect the distinct blocks across your portfolio."
                tipWidth={280}
                badgeStyle={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 15, height: 15, borderRadius: 999, background: "rgba(184,86,75,0.12)", color: "var(--terracotta-2)", fontSize: 10, fontWeight: 700, fontStyle: "italic", cursor: "help" }}
              >
                i
              </HoverTooltip>
            </span>
          }
          value={blocks.length + " blocks"}
          subtitle={
            <span style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
              <HoverTooltip
                tip="18 m+ or 7+ storeys — higher-risk buildings under the Building Safety Act 2022 (England) and Building Safety category 1 in Wales. In Scotland the high-rise threshold is 11 m and above."
                badgeStyle={{ padding: "2px 8px", borderRadius: 6, background: "rgba(225,29,72,0.09)", border: "1px solid rgba(225,29,72,0.28)", fontWeight: 600, fontSize: 13, color: "var(--navy)", cursor: "default" }}
              >
                {highRiseBlocks} high-risk
              </HoverTooltip>
              <HoverTooltip
                tip="11–18 m or 4–6 storeys — medium-rise under Approved Document B (2022, England) and Building Safety category 2 in Wales. In Scotland these already meet the 11 m high-rise threshold."
                badgeStyle={{ padding: "2px 8px", borderRadius: 6, background: "rgba(245,158,11,0.10)", border: "1px solid rgba(245,158,11,0.30)", fontWeight: 600, fontSize: 13, color: "var(--navy)", cursor: "default" }}
              >
                {amberBlocks} mid-risk
              </HoverTooltip>
            </span>
          }
          tone="blue"
          icon={KPI_ICONS.blocks}
        />
        <KpiCard
          title={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              FRA evidence
              <HoverTooltip
                tip="Upload Fire Risk Assessment (FRA) reports for your blocks. Our engine reads each report and assigns the block its fire-risk rating based on the findings in the assessment."
                tipWidth={280}
                badgeStyle={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 15, height: 15, borderRadius: 999, background: "rgba(184,86,75,0.12)", color: "var(--terracotta-2)", fontSize: 10, fontWeight: 700, fontStyle: "italic", cursor: "help" }}
              >
                i
              </HoverTooltip>
            </span>
          }
          value={fireDocCounts.fra}
          subtitle={fireDocCounts.fra > 0 ? fireRiskSubtitle(fireRiskCounts.fra) : "No evidence uploaded"}
          tone="amber"
          icon={KPI_ICONS.fra}
        />
        <KpiCard
          title={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              FRAEW evidence
              <HoverTooltip
                tip="Upload Fire Risk Appraisal of External Walls (FRAEW) reports for your blocks. Our engine reads each report and assigns the block its external-wall (cladding) risk rating based on the findings."
                tipWidth={280}
                badgeStyle={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 15, height: 15, borderRadius: 999, background: "rgba(184,86,75,0.12)", color: "var(--terracotta-2)", fontSize: 10, fontWeight: 700, fontStyle: "italic", cursor: "help" }}
              >
                i
              </HoverTooltip>
            </span>
          }
          value={fireDocCounts.fraew}
          subtitle={fireDocCounts.fraew > 0 ? fireRiskSubtitle(fireRiskCounts.fraew) : "No evidence uploaded"}
          tone="amber"
          icon={KPI_ICONS.fraew}
        />
        <KpiCard
          title={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              UPRN match confidence
              <HoverTooltip
                tip="Of the properties we enriched, the share with a confident (green) UPRN match from their address — the high-quality matches we then enriched with trusted external data: coordinates, EPC rating, building height, flood risk and listed-building status."
                tipWidth={280}
                badgeStyle={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 15, height: 15, borderRadius: 999, background: "rgba(184,86,75,0.12)", color: "var(--terracotta-2)", fontSize: 10, fontWeight: 700, fontStyle: "italic", cursor: "help" }}
              >
                i
              </HoverTooltip>
            </span>
          }
          value={`${enrichedPropertiesPct}%`}
          subtitle={
            <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.35 }}>
              <span>{enrichedPropertiesCount} of {properties.length} properties now have <strong>improved</strong> data</span>
                <span>{greenMatchCount} of {enrichedPropertiesCount} improvements have a <strong>high-confidence</strong> rating</span>
            </span>
          }
          tone="green"
          icon={KPI_ICONS.enhanced}
        />
      </div>

      <div
        className="dashboard-composition-map"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.2fr)",
          gap: 16,
          alignItems: "start",
        }}
      >
        <div className="card" style={{ alignSelf: "stretch", display: "flex", flexDirection: "column", minHeight: 505, maxHeight: 830, overflow: "hidden" }}>
          <div className="card-header row-between">
            <div className="card-title">
              {hasActivePropertySelection
                ? "Selected property details"
                : hasActiveBlockSelection
                ? "Selected block details"
                : "Selection details"}
            </div>
            <span className="pill pill-muted">
              {hasActivePropertySelection
                ? "Property selected"
                : hasActiveBlockSelection
                ? `Block : ${resolvedSelectedBlock?.block_id ?? resolvedSelectedBlock?.id ?? resolvedSelectedBlock?.name ?? "?"}`
                : "None"}
            </span>
          </div>

          <div ref={detailsScrollRef} className="details-body" style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
            <PropertyDetails
              property={resolvedSelectedProperty}
              selectedBlock={resolvedSelectedBlock}
              blockMode={!resolvedSelectedProperty}
              onSelectProperty={handleSelectProperty}
              legendCounts={legendCounts}
            />
          </div>
        </div>

        <div className="card" style={{ minHeight: 760, overflow: "visible", isolation: "isolate" }}>
          <div className="card-header row-between">
            <div>
              <div className="card-title">Block analysis map</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="pill pill-muted">{mappedBlocksCount} mapped blocks</span>
              {typeof onOpenFullMap === "function" && (
                <button
                  className="btn btn-primary"
                  style={{ padding: "4px 10px", fontSize: 12 }}
                  onClick={() => onOpenFullMap(miniMapViewRef.current)}
                >
                  Open in full risk map ↗
                </button>
              )}
              {typeof onLoadMapData === "function" && (
                <button
                  className="btn"
                  style={{ padding: "4px 10px", fontSize: 12 }}
                  onClick={handleLoadMapData}
                  disabled={mapDataLoading}
                >
                  {mapDataLoading ? "Loading…" : "Refresh map"}
                </button>
              )}
            </div>
          </div>

          {mappedBlocksCount === 0 && !mapDataLoading && (
            <div style={{ padding: "10px 22px 0", fontSize: 13, color: "var(--muted)" }}>
              No block coordinates yet — enrichment may still be running.{" "}
              {typeof onLoadMapData === "function" && (
                <span
                  style={{ cursor: "pointer", textDecoration: "underline" }}
                  onClick={handleLoadMapData}
                >
                  Reload enriched data
                </span>
              )}
            </div>
          )}

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              margin: "12px 22px 0",
              padding: "9px 13px",
              borderRadius: 10,
              background: "var(--blush)",
              border: "1px solid var(--border-line)",
              color: "var(--navy)",
              fontSize: 12.5,
              lineHeight: 1.45,
            }}
          >
            <svg
              aria-hidden="true"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--terracotta-2)"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ flexShrink: 0 }}
            >
              <path d="M9 9l5 12 1.8-5.2L21 14z" />
              <path d="M7.2 2.2 8 5.1" />
              <path d="m5.1 7.2-2.9-.8" />
              <path d="M14 4.1 12 6" />
              <path d="m6 12-1.9 2" />
            </svg>
            <span>
              <strong style={{ fontWeight: 700 }}>Tip:</strong> click a block to see its summary, then click it again to list every flat inside it.
            </span>
          </div>

          <div className="map-wrap">
            <PortfolioMap
              properties={mapProperties}
              blocks={blocks}
              viewMode={mapMode}
              selectedBlock={resolvedSelectedBlock}
              selectedProperty={resolvedSelectedProperty}
              onSelectBlock={handleSelectBlock}
              onSelectProperty={handleSelectProperty}
              suppressFit={suppressMapFit}
              onViewChange={(v) => { miniMapViewRef.current = v; }}
            />
          </div>

          <div
            className="map-foot"
            style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}
          >
            <span>
              {hasActivePropertySelection
                ? `Viewing flat details for ${resolvedSelectedProperty?.block_reference ?? "selected block"}. Select another flat from the block popup or clear the selection.`
                : hasActiveBlockSelection
                ? "Block selected. Click the marker to open the flat list, or clear the selection below."
                : "Click a block circle on the map to inspect that block in detail."}
            </span>

            <button
              className="btn"
              onClick={handleClearMapSelection}
              style={{ visibility: hasActiveBlockSelection || hasActivePropertySelection ? "visible" : "hidden" }}
            >
              Clear selection
            </button>
          </div>
        </div>
      </div>

      <FireEvidencePanel
        fireDocuments={fireDocuments}
        loading={fireDocumentsLoading}
        onUploadNew={onUploadNew}
      />

      <UnderwriterDocumentsPanel
        portfolioId={resolvedPortfolioId}
        propertyCount={ingestionSummary?.propertyCount || 0}
        properties={properties}
        blocks={blocks}
        onExport={handleExport}
      />
    </div>
  );
}
