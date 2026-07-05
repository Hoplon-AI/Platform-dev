import React, { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import "leaflet.markercluster";

import {
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  CLUSTER_ZOOM,
  BLOCK_ZOOM,
  FOCUSED_ZOOM,
  BUILDINGS_URL,
  PROPERTY_TYPE_COLORS,
} from "../constants/map.js";
import {
  toNumberOrNull,
  readinessColor,
  readinessBandFromScore,
  riskColor,
  sameProperty,
  sameBlock,
  getPropertyLatLon,
  getBlockLatLon,
  getPropertyReadiness,
  getPropertyBand,
  getPropertyId,
  getPropertyLabel,
  getPropertyValue,
  getBlockId,
  getBlockName,
  getBlockUnits,
  getBlockValue,
  getBlockStoreys,
  inferPropertyCategory,
  getPropertyCategoryLabel,
  getFeatureIdentifier,
  getSelectedBlockPropertyPoints,
  getSelectedBlockBounds,
  getFitBoundsForMode,
  buildPropertyFeatureAssignments,
  buildBlockTooltipHtml,
  colorForMode,
  blockRingColor,
} from "../utils/mapHelpers.js";
import {
  createClusterIcon,
  createBlockCountIcon,
  createPropertyDotIcon,
  getContextBlockVisibility,
} from "./map/markerIcons.js";
import {
  getPropertyPopupHtml,
  buildFlatListPopupHtml,
  attachFlatListPopupHandlers,
} from "./map/popups.js";

export default function PortfolioMap({
  properties = [],
  blocks = [],
  selectedProperty = null,
  selectedBlock = null,
  onSelectProperty,
  onSelectBlock,
  viewMode = "blocks",
  suppressFit = false,
  overlays = [],
  colorBy = "readiness",
  riskColorBy = null,
  canvasStyle = {},
}) {
  const mapDivRef = useRef(null);
  const mapRef = useRef(null);
  const pointLayerRef = useRef(null);
  const buildingsLayerRef = useRef(null);
  const overviewBlockLayerRef = useRef(null);
  const selectedMarkerRef = useRef(null);
  const lastFitSignatureRef = useRef("");
  const suppressFitRef = useRef(suppressFit);
  suppressFitRef.current = suppressFit;
  const lastSelectionSignatureRef = useRef("");
  const buildingsGeojsonCacheRef = useRef(null);
  const buildingsFetchPromiseRef = useRef(null);

  const propertyPoints = useMemo(() => {
    return (properties || [])
      .map((property, idx) => {
        const latLon = getPropertyLatLon(property);
        if (!latLon) return null;

        const readinessScore = getPropertyReadiness(property);
        const readinessBand = getPropertyBand(property);

        return {
          id: getPropertyId(property, idx),
          label: getPropertyLabel(property, idx),
          lat: latLon[0],
          lon: latLon[1],
          readinessScore,
          readinessBand,
          color: colorForMode(property, colorBy),
          propertyCategory: inferPropertyCategory(property),
          propertyCategoryLabel: getPropertyCategoryLabel(property),
          sumInsured: getPropertyValue(property),
          raw: { ...property, __lat: latLon[0], __lon: latLon[1] },
        };
      })
      .filter(Boolean);
  }, [properties, colorBy]);

  const blockPoints = useMemo(() => {
    return (blocks || [])
      .map((block, idx) => {
        const latLon = getBlockLatLon(block);
        if (!latLon) return null;

        const units = getBlockUnits(block);
        const totalValue = getBlockValue(block);
        const readinessScore = toNumberOrNull(block?.avgReadiness) ?? toNumberOrNull(block?.readiness_score) ?? null;
        const readinessBand = block?.readiness_band ?? (Number.isFinite(readinessScore) ? readinessBandFromScore(readinessScore) : "Amber");

        return {
          id: getBlockId(block, idx),
          name: getBlockName(block, idx),
          lat: latLon[0],
          lon: latLon[1],
          units,
          totalValue,
          storeys: getBlockStoreys(block),
          readinessScore,
          readinessBand,
          color: readinessColor(readinessBand),
          raw: { ...block, __lat: latLon[0], __lon: latLon[1] },
        };
      })
      .filter(Boolean);
  }, [blocks]);

  const activeMode = viewMode === "properties" ? "properties" : "blocks";
  const visiblePoints = activeMode === "blocks" ? blockPoints : propertyPoints;

  useLayoutEffect(() => {
    if (!mapDivRef.current || mapRef.current) return;

    const map = L.map(mapDivRef.current, {
      scrollWheelZoom: true,
      zoomControl: true,
      attributionControl: false,
      minZoom: 4, // stop zooming out far enough to see repeated globe copies
    }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd",
      maxZoom: 20,
      noWrap: true,
      crossOrigin: "anonymous",
      keepBuffer: 4,
      attribution: "&copy; OpenStreetMap &copy; CARTO",
    }).addTo(map);

    if (overlays.length) {
      const legendEntries = [];
      overlays.forEach((cfg) => {
        const n = cfg.oversample || 0;
        const layer = L.tileLayer.wms(cfg.url, {
          layers: cfg.layers,
          format: "image/png",
          transparent: true,
          crs: cfg.crs === "4326" ? L.CRS.EPSG4326 : L.CRS.EPSG3857,
          opacity: cfg.opacity ?? 0.55,
          attribution: cfg.attribution,
        });
        // ponytail: BGS scale-gates 1:50k layers (~26 m/px). Requesting a
        // 2^n-larger image for the same tile bbox makes the server compute a
        // finer scale and render n zoom levels earlier; the browser downscales
        // into the 256px slot. Same tile count, just heavier images.
        if (n) layer.wmsParams.width = layer.wmsParams.height = 256 * 2 ** n;
        // Leaflet layer-control labels accept HTML — append coverage badge
        const label = cfg.coverage
          ? `${cfg.label} <span style="font-size:11px;color:#94a3b8;">— ${cfg.coverage}</span>`
          : cfg.label;
        if (cfg.defaultOn) layer.addTo(map);
        // ponytail: use the WMS server's own GetLegendGraphic image instead of
        // hand-authoring a colour table per layer (SIMD deciles, flood bands,
        // geology's hundreds of rock types...). Servers that don't support it
        // (BGS geology) return no image → the row hides itself via onerror.
        const sep = cfg.url.includes("?") ? "&" : "?";
        legendEntries.push({
          layer,
          label: cfg.label,
          labelHtml: label,
          group: cfg.group || "Layers",
          legendText: cfg.legendText,
          legendColor: cfg.legendColor,
          legendItems: cfg.legendItems,
          legendUrl: `${cfg.url}${sep}service=WMS&request=GetLegendGraphic&version=1.3.0&format=image/png&layer=${encodeURIComponent(cfg.layers.split(",")[0])}`,
        });
      });
      // ponytail: L.control.layers renders a flat always-open list — 18 overlays
      // swamp the viewport. Native <details>/<summary> gives collapsible per-group
      // sections (grouped by cfg.group → SEPA/EA/BGS/etc.) with zero JS and zero
      // deps. Checkboxes toggle the WMS layer + fire the same overlayadd/remove
      // events the legend below already listens on, so the legend needs no change.
      const picker = L.control({ position: "topright" });
      picker.onAdd = () => {
        const div = L.DomUtil.create("div", "wms-picker");
        div.style.cssText =
          "background:rgba(255,255,255,0.95);border:1px solid #e2e8f0;border-radius:8px;padding:6px 8px;max-height:45vh;overflow:auto;box-shadow:0 1px 4px rgba(15,23,42,0.12);font-size:12px;max-width:480px;white-space:nowrap;";
        L.DomEvent.disableScrollPropagation(div);
        L.DomEvent.disableClickPropagation(div);
        const groups = [...new Set(legendEntries.map((e) => e.group))];
        div.innerHTML = groups
          .map((g) => {
            const rows = legendEntries
              .map((e, i) => ({ e, i }))
              .filter((x) => x.e.group === g)
              .map(({ e, i }) =>
                `<label style="display:flex;gap:6px;align-items:flex-start;padding:2px 0;cursor:pointer;"><input type="checkbox" data-idx="${i}"${map.hasLayer(e.layer) ? " checked" : ""} style="margin-top:2px;"><span>${e.labelHtml}</span></label>`
              )
              .join("");
            const open = legendEntries.some((e) => e.group === g && map.hasLayer(e.layer));
            return `<details${open ? " open" : ""} style="margin-bottom:4px;"><summary style="font-weight:600;cursor:pointer;">${g}</summary>${rows}</details>`;
          })
          .join("");
        div.querySelectorAll("input[type=checkbox]").forEach((cb) => {
          cb.addEventListener("change", () => {
            const { layer } = legendEntries[+cb.dataset.idx];
            if (cb.checked) { map.addLayer(layer); map.fire("overlayadd"); }
            else { map.removeLayer(layer); map.fire("overlayremove"); }
          });
        });
        return div;
      };
      picker.addTo(map);
      L.control.attribution({ prefix: false }).addTo(map);

      // ponytail: warm the browser cache for every legend PNG at mount, so the
      // first layer-toggle shows its legend instantly instead of paying a WMS
      // round-trip. Tiny (1–3 KB) images; the render() below reuses the cache.
      legendEntries.forEach((e) => { if (!e.legendText) new Image().src = e.legendUrl; });

      // Legend for whichever overlays are switched on; stacks below the layer
      // picker and re-renders on toggle.
      const legend = L.control({ position: "topright" });
      legend.onAdd = () => {
        const div = L.DomUtil.create("div", "wms-legend");
        div.style.cssText =
          "background:rgba(255,255,255,0.95);border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;margin-top:6px;max-height:45vh;overflow:auto;box-shadow:0 1px 4px rgba(15,23,42,0.12);font-size:14px;max-width:280px;";
        L.DomEvent.disableScrollPropagation(div);
        L.DomEvent.disableClickPropagation(div);
        const render = () => {
          const active = legendEntries.filter((e) => map.hasLayer(e.layer));
          div.style.display = active.length ? "block" : "none";
          div.innerHTML = active
            .map((e) => {
              const dot = (c) =>
                `<span style="display:inline-block;width:15px;height:15px;border-radius:3px;background:${c};border:1px solid rgba(15,23,42,0.15);margin-right:7px;vertical-align:-3px;flex:0 0 auto;"></span>`;
              let body;
              if (e.legendItems) {
                const cap = e.legendText ? `<div style="color:#475569;line-height:1.4;margin-bottom:3px;">${e.legendText}</div>` : "";
                const rows = e.legendItems
                  .map((it) => `<div style="display:flex;align-items:center;margin-top:3px;color:#475569;">${dot(it.color)}<span>${it.label}</span></div>`)
                  .join("");
                body = cap + rows;
              } else if (e.legendText) {
                body = `<div style="color:#475569;line-height:1.4;">${e.legendColor ? dot(e.legendColor) : ""}${e.legendText}</div>`;
              } else {
                body = `<img src="${e.legendUrl}" alt="" style="max-width:100%;display:block;" onerror="this.parentNode.style.display='none'">`;
              }
              return `<div style="margin-bottom:10px;"><div style="font-weight:600;margin-bottom:3px;">${e.label}</div>${body}</div>`;
            })
            .join("");
        };
        render();
        map.on("overlayadd overlayremove", render);
        return div;
      };
      legend.addTo(map);
    }

    mapRef.current = map;
    buildingsLayerRef.current = L.layerGroup().addTo(map);
    overviewBlockLayerRef.current = L.layerGroup().addTo(map);
    pointLayerRef.current = L.layerGroup().addTo(map);

    // Staggered invalidateSize to handle grid/flex layout settling
    setTimeout(() => map.invalidateSize(), 0);
    setTimeout(() => map.invalidateSize(), 120);
    setTimeout(() => map.invalidateSize(), 400);
    setTimeout(() => map.invalidateSize(), 1000);

    return () => {
      map.remove();
      mapRef.current = null;
      buildingsLayerRef.current = null;
      overviewBlockLayerRef.current = null;
      pointLayerRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onResize = () => mapRef.current?.invalidateSize();
    window.addEventListener("resize", onResize);

    // ResizeObserver catches layout changes (grid settling, sidebar toggle, etc.)
    let ro = null;
    if (typeof ResizeObserver !== "undefined" && mapDivRef.current) {
      ro = new ResizeObserver(() => {
        mapRef.current?.invalidateSize();
      });
      ro.observe(mapDivRef.current);
    }

    return () => {
      window.removeEventListener("resize", onResize);
      ro?.disconnect();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const pointLayer = pointLayerRef.current;
    const buildingsLayer = buildingsLayerRef.current;
    const overviewBlockLayer = overviewBlockLayerRef.current;
    if (!map || !pointLayer || !buildingsLayer || !overviewBlockLayer) return;

    selectedMarkerRef.current = null;
    pointLayer.clearLayers();
    overviewBlockLayer.clearLayers();

    if (!visiblePoints.length) {
      lastFitSignatureRef.current = "";
      buildingsLayer.clearLayers();
      setTimeout(() => map.invalidateSize(), 80);
      return;
    }

    const currentZoom = map.getZoom();

    if (activeMode === "blocks") {
      buildingsLayer.clearLayers();
      overviewBlockLayer.clearLayers();

      const clusterGroup = L.markerClusterGroup({
        iconCreateFunction: createClusterIcon,
        maxClusterRadius: (zoom) => {
          if (zoom <= 5)  return 160;
          if (zoom <= 7)  return 120;
          if (zoom <= 9)  return 90;
          if (zoom <= 11) return 60;
          return 40;
        },
        spiderfyOnMaxZoom: false,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: false,
        disableClusteringAtZoom: 13,
        animate: true,
      });

      clusterGroup.on("clusterclick", (e) => {
        const bounds = e.layer.getBounds();
        if (bounds.isValid()) {
          map.flyToBounds(bounds.pad(0.2), { duration: 0.5, maxZoom: 13 });
        }
      });

      blockPoints.forEach((point) => {
        const isSelected = sameBlock(selectedBlock, point.raw);
        const baseZ = isSelected ? 1000 : 0;
        const ring = riskColorBy ? blockRingColor(point.raw, riskColorBy) : null;
        const marker = L.marker([point.lat, point.lon], {
          icon: createBlockCountIcon(point, currentZoom, isSelected, 1, 1, ring),
          keyboard: false,
          zIndexOffset: baseZ,
          _units: point.units,
          _ringColor: ring || riskColor(point.raw),
        });

        marker.on("mouseover", () => marker.setZIndexOffset(10000));
        marker.on("mouseout", () => marker.setZIndexOffset(baseZ));
        marker.on("click", () => {
          if (!isSelected) {
            onSelectBlock?.(point.raw);
            onSelectProperty?.(null);
          }
        });
        marker.bindTooltip(
          buildBlockTooltipHtml(point, Boolean(riskColorBy)),
          { direction: "top", sticky: true, opacity: 0.97 }
        );
        marker.bindPopup(buildFlatListPopupHtml(point, Boolean(riskColorBy)), { maxWidth: 320 });
        attachFlatListPopupHandlers(marker, point, onSelectProperty);
        clusterGroup.addLayer(marker);
        if (isSelected) selectedMarkerRef.current = marker;
      });

      clusterGroup.addTo(pointLayer);
    } else {
      propertyPoints.forEach((point) => {
        const isSelected = sameProperty(selectedProperty, point.raw);
        const baseZ = isSelected ? 1000 : 0;
        const marker = L.marker([point.lat, point.lon], {
          icon: createPropertyDotIcon(point, isSelected),
          keyboard: false,
          zIndexOffset: baseZ,
        });

        marker.on("mouseover", () => marker.setZIndexOffset(10000));
        marker.on("mouseout", () => marker.setZIndexOffset(baseZ));
        marker.on("click", () => onSelectProperty?.(point.raw));
        marker.bindTooltip(`${point.label} · ${point.propertyCategoryLabel}`, {
          direction: "top",
          sticky: true,
          opacity: 0.95,
        });
        marker.bindPopup(getPropertyPopupHtml(point));
        marker.addTo(pointLayer);
        if (isSelected) selectedMarkerRef.current = marker;
      });
    }

    const fitBounds = getFitBoundsForMode({
      activeMode,
      blockPoints,
      propertyPoints,
      selectedBlock,
      selectedProperty,
    });

    if (fitBounds.length) {
      const signature = JSON.stringify([
        activeMode,
        selectedBlock?.id ?? selectedBlock?.block_id ?? selectedBlock?.label ?? null,
        selectedProperty?.id ?? selectedProperty?.property_id ?? selectedProperty?.property_reference ?? selectedProperty?.uprn ?? null,
        fitBounds,
      ]);

      if (lastFitSignatureRef.current !== signature) {
        lastFitSignatureRef.current = signature;

        if (!suppressFitRef.current) {
          const leafletBounds = L.latLngBounds(fitBounds);
          if (leafletBounds.isValid()) {
            if (activeMode === "properties") {
              map.flyToBounds(leafletBounds.pad(selectedProperty ? 0.08 : 0.16), {
                duration: 0.55,
                maxZoom: selectedProperty ? FOCUSED_ZOOM : BLOCK_ZOOM,
              });
            } else if (selectedBlock) {
              map.flyToBounds(leafletBounds.pad(0.02), {
                duration: 0.45,
                maxZoom: BLOCK_ZOOM,
              });
            } else {
              map.fitBounds(leafletBounds.pad(0.24), {
                animate: false,
                maxZoom: CLUSTER_ZOOM,
              });
            }
          }
        }
      }
    }

    map.invalidateSize();
    setTimeout(() => map.invalidateSize(), 80);
    setTimeout(() => map.invalidateSize(), 300);
  }, [
    activeMode,
    blockPoints,
    onSelectBlock,
    onSelectProperty,
    propertyPoints,
    selectedBlock,
    selectedProperty,
    visiblePoints.length,
    riskColorBy,
  ]);

  useEffect(() => {
    const map = mapRef.current;
    const overviewBlockLayer = overviewBlockLayerRef.current;
    if (!map || !overviewBlockLayer) return;

    const renderContextBlocks = () => {
      overviewBlockLayer.clearLayers();

      if (activeMode !== "properties" || !selectedBlock || !blockPoints.length) return;

      const zoom = map.getZoom();
      const visibility = getContextBlockVisibility(zoom);
      if (!visibility.visible) return;

      blockPoints.forEach((point) => {
        const isSelected = sameBlock(selectedBlock, point.raw);
        const baseZ = isSelected ? 760 : 260;
        const marker = L.marker([point.lat, point.lon], {
          icon: createBlockCountIcon(
            point,
            zoom,
            isSelected,
            isSelected ? Math.min(1, visibility.opacity + 0.08) : visibility.opacity,
            isSelected ? Math.min(1.08, visibility.scale + 0.04) : visibility.scale
          ),
          keyboard: false,
          zIndexOffset: baseZ,
        });

        marker.on("mouseover", () => marker.setZIndexOffset(10000));
        marker.on("mouseout", () => marker.setZIndexOffset(baseZ));
        marker.on("click", () => {
          if (!isSelected) {
            onSelectBlock?.(point.raw);
            onSelectProperty?.(null);
            lastFitSignatureRef.current = "";
          }
        });

        marker.bindTooltip(
          buildBlockTooltipHtml(point),
          { direction: "top", sticky: true, opacity: 0.97 }
        );

        marker.bindPopup(buildFlatListPopupHtml(point), { maxWidth: 320 });
        attachFlatListPopupHandlers(marker, point, onSelectProperty);
        marker.addTo(overviewBlockLayer);
      });
    };

    renderContextBlocks();
    map.on("zoom zoomend moveend", renderContextBlocks);

    return () => {
      map.off("zoom zoomend moveend", renderContextBlocks);
      overviewBlockLayer.clearLayers();
    };
  }, [activeMode, blockPoints, onSelectBlock, onSelectProperty, selectedBlock]);

  useEffect(() => {
    const map = mapRef.current;
    const buildingsLayer = buildingsLayerRef.current;
    if (!map || !buildingsLayer) return;

    const shouldShowBuildings = activeMode === "properties" && selectedBlock && propertyPoints.length > 0;

    if (!shouldShowBuildings) {
      buildingsLayer.clearLayers();
      return;
    }

    let isCancelled = false;

    const renderBuildings = async () => {
      try {
        if (!buildingsGeojsonCacheRef.current) {
          if (!buildingsFetchPromiseRef.current) {
            buildingsFetchPromiseRef.current = fetch(BUILDINGS_URL).then((res) => {
              if (!res.ok) throw new Error(`Failed to load buildings GeoJSON: ${res.status}`);
              return res.json();
            });
          }
          buildingsGeojsonCacheRef.current = await buildingsFetchPromiseRef.current;
        }

        if (isCancelled) return;

        const source = buildingsGeojsonCacheRef.current;
        const targetPropertyPoints = getSelectedBlockPropertyPoints(selectedBlock, propertyPoints);
        const selectedBounds = getSelectedBlockBounds(selectedBlock, propertyPoints);
        buildingsLayer.clearLayers();

        if (!source?.features?.length || !selectedBounds || !targetPropertyPoints.length) return;

        const { features, assignments, unmatchedPoints } = buildPropertyFeatureAssignments({
          sourceFeatures: source.features,
          targetPropertyPoints,
          selectedBounds,
        });

        if (features.length) {
          const geoJsonLayer = L.geoJSON(
            { type: "FeatureCollection", features },
            {
              style: (feature) => {
                const featureId = getFeatureIdentifier(feature);
                const assignedPoint = assignments.get(featureId) || null;
                const isSelected = assignedPoint && selectedProperty ? sameProperty(assignedPoint.raw, selectedProperty) : false;
                const fillColor = assignedPoint
                  ? colorForMode(assignedPoint.raw, colorBy)
                  : PROPERTY_TYPE_COLORS.other;

                return {
                  color: isSelected ? "#1d4ed8" : fillColor,
                  weight: isSelected ? 3 : 2,
                  fillColor,
                  fillOpacity: isSelected ? 0.68 : 0.42,
                  opacity: 0.95,
                };
              },
              onEachFeature: (feature, layer) => {
                const featureId = getFeatureIdentifier(feature);
                const assignedPoint = assignments.get(featureId) || null;
                if (!assignedPoint) return;

                layer.on({
                  click: () => onSelectProperty?.(assignedPoint.raw),
                  mouseover: () => {
                    layer.setStyle({ weight: 3, color: "#0f172a", fillOpacity: 0.72 });
                    layer.bringToFront();
                  },
                  mouseout: () => {
                    if (geoJsonLayer.resetStyle) geoJsonLayer.resetStyle(layer);
                  },
                });

                layer.bindTooltip(`${assignedPoint.label} · ${getPropertyCategoryLabel(assignedPoint.raw)}`, {
                  direction: "top",
                  sticky: true,
                  opacity: 0.95,
                });
              },
            }
          );

          geoJsonLayer.addTo(buildingsLayer);
        }

        // If OSM has no matching footprint for a property, show only a small dot.
        // This avoids fake square/grid polygons while still keeping every property visible.
        unmatchedPoints.forEach((point) => {
          const isSelected = selectedProperty ? sameProperty(point.raw, selectedProperty) : false;
          const circle = L.circleMarker([point.lat, point.lon], {
            radius: isSelected ? 7 : 5,
            color: isSelected ? "#1d4ed8" : colorForMode(point.raw, colorBy),
            weight: isSelected ? 3 : 2,
            fillColor: isSelected ? "#1d4ed8" : colorForMode(point.raw, colorBy),
            fillOpacity: 0.8,
          });

          circle.on("click", () => onSelectProperty?.(point.raw));
          circle.bindTooltip(`${point.label} · ${getPropertyCategoryLabel(point.raw)}`, {
            direction: "top",
            sticky: true,
            opacity: 0.95,
          });
          circle.addTo(buildingsLayer);
        });
      } catch (error) {
        console.error("Buildings layer load failed:", error);
        buildingsLayer.clearLayers();
      }
    };

    renderBuildings();

    return () => {
      isCancelled = true;
    };
  }, [activeMode, colorBy, onSelectProperty, propertyPoints, selectedBlock, selectedProperty]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (activeMode === "properties" && selectedProperty) {
      const latLon = getPropertyLatLon(selectedProperty);
      if (!latLon) return;

      const selectionSignature = `property:${
        selectedProperty.id ??
        selectedProperty.property_id ??
        selectedProperty.property_reference ??
        selectedProperty.uprn ??
        ""
      }`;

      if (lastSelectionSignatureRef.current !== selectionSignature) {
        lastSelectionSignatureRef.current = selectionSignature;
        map.flyTo(latLon, Math.max(map.getZoom(), FOCUSED_ZOOM), { duration: 0.45 });
      }

      setTimeout(() => selectedMarkerRef.current?.openPopup(), 320);
      return;
    }

    if (!selectedBlock && !selectedProperty) {
      lastSelectionSignatureRef.current = "";
    }
  }, [activeMode, selectedBlock, selectedProperty, propertyPoints]);

  return (
    <div
      ref={mapDivRef}
      className="portfolio-map-canvas"
      style={{
        height: 620,
        width: "100%",
        borderRadius: 22,
        overflow: "hidden",
        background: "#eef3f8",
        border: "1px solid rgba(15,23,42,0.08)",
        ...canvasStyle,
      }}
    />
  );
}
