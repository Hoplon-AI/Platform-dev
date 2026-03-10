import React, { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { computeReadiness, readinessColor } from "../utils/readiness.js";

const fmt = (n, digits = 4) => {
  const x = Number(n);
  return Number.isFinite(x) ? x.toFixed(digits) : "—";
};

function num(v) {
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

function getLatLon(row) {
  // support many header styles
  const lat = num(row.lat ?? row.latitude ?? row.Latitude ?? row.LATITUDE);
  const lon = num(row.lon ?? row.lng ?? row.longitude ?? row.Longitude ?? row.LONGITUDE);
  if (lat == null || lon == null) return null;
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return [lat, lon];
}

function sumInsuredValue(row) {
  const v = row.sum_insured ?? row.sumInsured ?? row.SumInsured ?? row["sum insured"] ?? row["Sum Insured"];
  const x = Number(String(v).replace(/[£,]/g, ""));
  return Number.isFinite(x) ? x : 0;
}

export default function PortfolioMap({ rows, onSelectProperty, selectedProperty }) {
  const mapDivRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);

  const points = useMemo(() => {
    return (rows || [])
      .map((r, idx) => {
        const ll = getLatLon(r);
        if (!ll) return null;
        const readiness = computeReadiness(r);
        return {
          id: r.id ?? r.property_id ?? r.property_reference ?? r.council_reference ?? idx,
          row: r,
          lat: ll[0],
          lon: ll[1],
          readiness,
          sumInsured: sumInsuredValue(r),
        };
      })
      .filter(Boolean);
  }, [rows]);

  // Create map once (component lifetime)
  useEffect(() => {
    if (!mapDivRef.current || mapRef.current) return;

    const map = L.map(mapDivRef.current, {
      scrollWheelZoom: false,
      zoomControl: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
    }).addTo(map);

    map.setView([54.5, -3], 5);

    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);

    // Initial invalidate helps Leaflet inside flex/cards
    setTimeout(() => map.invalidateSize(), 150);
  }, []);

  // Update markers when points change
  useEffect(() => {
    if (!mapRef.current || !layerRef.current) return;

    const map = mapRef.current;
    const layer = layerRef.current;
    layer.clearLayers();

    if (!points.length) {
      // keep a sane default view
      map.setView([54.5, -3], 5);
      setTimeout(() => map.invalidateSize(), 80);
      return;
    }

    const bounds = [];

    points.forEach((p) => {
      const color = readinessColor(p.readiness.score);

      // radius from sum insured (clamped)
      const base = Math.sqrt(Math.max(0, p.sumInsured)) / 4000;
      const radius = Math.max(6, Math.min(22, 6 + base));

      const circle = L.circleMarker([p.lat, p.lon], {
        radius,
        color,
        weight: 2,
        opacity: 0.95,
        fillColor: color,
        fillOpacity: 0.55,
      });

      circle.on("click", () => {
        // Zoom to selection + open detail panel via callback
        map.flyTo([p.lat, p.lon], Math.max(map.getZoom(), 10), { duration: 0.6 });
        onSelectProperty?.({
          ...p.row,
          __readiness: p.readiness,
          __lat: p.lat,
          __lon: p.lon,
        });
      });

      circle.bindTooltip(
        `Property · readiness ${p.readiness.score}`,
        { direction: "top", sticky: true, opacity: 0.9 }
      );

      circle.addTo(layer);
      bounds.push([p.lat, p.lon]);
    });

    // Fit bounds on first load / data change
    const b = L.latLngBounds(bounds);
    map.fitBounds(b.pad(0.25), { animate: false });

    // Leaflet needs this after DOM paint
    setTimeout(() => map.invalidateSize(), 80);
  }, [points, onSelectProperty]);

  // If a property is selected externally, flyTo it (nice UX)
  useEffect(() => {
    if (!mapRef.current || !selectedProperty) return;
    const lat = selectedProperty.__lat ?? num(selectedProperty.lat ?? selectedProperty.latitude);
    const lon = selectedProperty.__lon ?? num(selectedProperty.lon ?? selectedProperty.longitude);
    if (lat == null || lon == null) return;

    mapRef.current.flyTo([lat, lon], Math.max(mapRef.current.getZoom(), 10), { duration: 0.55 });
  }, [selectedProperty]);

  // IMPORTANT: when the map container becomes visible again, Leaflet can go blank if size isn’t invalidated.
  // Call invalidate on mount AND whenever the window resizes.
  useEffect(() => {
    const onResize = () => mapRef.current?.invalidateSize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <div
      ref={mapDivRef}
      style={{
        height: 520,
        width: "100%",
        borderRadius: 14,
        overflow: "hidden",
        background: "#e5eefc",
      }}
    />
  );
}
