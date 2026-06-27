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
  getPropertyDisplayColor,
  getFeatureIdentifier,
  getSelectedBlockPropertyPoints,
  getSelectedBlockBounds,
  getFitBoundsForMode,
  buildPropertyFeatureAssignments,
  buildBlockTooltipHtml,
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
          color: readinessColor(readinessBand),
          propertyCategory: inferPropertyCategory(property),
          propertyCategoryLabel: getPropertyCategoryLabel(property),
          sumInsured: getPropertyValue(property),
          raw: { ...property, __lat: latLon[0], __lon: latLon[1] },
        };
      })
      .filter(Boolean);
  }, [properties]);

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
    }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd",
      maxZoom: 20,
      crossOrigin: "anonymous",
      keepBuffer: 4,
      attribution: "&copy; OpenStreetMap &copy; CARTO",
    }).addTo(map);

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
        const marker = L.marker([point.lat, point.lon], {
          icon: createBlockCountIcon(point, currentZoom, isSelected),
          keyboard: false,
          zIndexOffset: baseZ,
          _units: point.units,
          _ringColor: riskColor(point.raw),
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
          buildBlockTooltipHtml(point),
          { direction: "top", sticky: true, opacity: 0.97 }
        );
        marker.bindPopup(buildFlatListPopupHtml(point), { maxWidth: 320 });
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
                  ? getPropertyDisplayColor(assignedPoint.raw, isSelected)
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
            color: isSelected ? "#1d4ed8" : getPropertyDisplayColor(point.raw, false),
            weight: isSelected ? 3 : 2,
            fillColor: getPropertyDisplayColor(point.raw, isSelected),
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
  }, [activeMode, onSelectProperty, propertyPoints, selectedBlock, selectedProperty]);

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
      }}
    />
  );
}
