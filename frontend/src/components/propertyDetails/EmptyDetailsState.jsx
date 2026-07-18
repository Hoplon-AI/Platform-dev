// Placeholder/instructional panel shown when no property or block is selected.
import React from "react";

export default function EmptyDetailsState({ legendCounts = null }) {
  // Real block counts by worst FRA/FRAEW band; falls back to em-dash if not supplied.
  const c = legendCounts || {};
  const n = (v) => (Number.isFinite(v) ? v : "—");
  const numStep = (n, text) => (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
      <span
        style={{
          flexShrink: 0,
          width: 26,
          height: 26,
          borderRadius: 999,
          background: "rgba(184,86,75,0.12)",
          color: "var(--terracotta-2, #9A463D)",
          fontSize: 12,
          fontWeight: 700,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {n}
      </span>
      <span style={{ fontSize: 14, color: "var(--text, #1E3246)", lineHeight: 1.55 }}>{text}</span>
    </div>
  );

  const legendRow = (color, label, count) => (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <span
        style={{
          flexShrink: 0,
          width: 30,
          height: 30,
          borderRadius: 999,
          background: "#fff",
          color: "var(--navy, #1E3246)",
          fontSize: 12,
          fontWeight: 700,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: `2.5px solid ${color}`,
          boxSizing: "border-box",
        }}
      >
        {count}
      </span>
      <span style={{ fontSize: 13, color: "var(--muted, #6B6560)", whiteSpace: "nowrap" }}>{label}</span>
    </div>
  );

  const infoItem = (icon, label) => (
    <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
      <span
        style={{
          flexShrink: 0,
          width: 32,
          height: 32,
          borderRadius: 9,
          background: "rgba(184,86,75,0.10)",
          color: "var(--terracotta-2, #9A463D)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {icon}
      </span>
      <span style={{ fontSize: 13.5, color: "var(--text, #1E3246)" }}>{label}</span>
    </div>
  );

  const ic = (children) => (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", justifyContent: "space-between", gap: 26, padding: "32px 16px 32px" }}>
      <div>
        <div className="tag" style={{ marginBottom: 16 }}>How to explore</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {numStep("1", "Click a block on the map for its summary.")}
          {numStep("2", "Click the same block again to list every flat inside it.")}
        </div>
      </div>

      <div>
        <div className="tag" style={{ marginBottom: 16 }}>What each summary shows</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "18px 10px" }}>
          {infoItem(ic(<><path d="M18 7c0-5.333-8-5.333-8 0" /><path d="M10 7v14" /><path d="M6 21h12" /><path d="M6 13h10" /></>), "Insured value")}
          {infoItem(ic(<><path d="M12 3v18" /><path d="m8 7 4-4 4 4" /><path d="m8 17 4 4 4-4" /></>), "Height & storeys")}
          {infoItem(ic(<><path d="M3 9.5 12 3l9 6.5" /><path d="M5 10v10h14V10" /></>), "Flats in the block")}
          {infoItem(ic(<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />), "FRA fire risk")}
          {infoItem(ic(<><rect x="3" y="4" width="18" height="16" rx="1" /><path d="M3 9h18M3 14h18M8 4v5m8-5v5m-4 5v6m-4-6h8" /></>), "FRAEW wall risk")}
          {infoItem(ic(<><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z" /><circle cx="12" cy="10" r="3" /></>), "Location & UPRN")}
          {infoItem(ic(<><path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 1.3 0 1.9-.5 2.5-1" /><path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 1.3 0 1.9-.5 2.5-1" /><path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 1.3 0 1.9-.5 2.5-1" /></>), "Flood risk score")}
          {infoItem(ic(<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="m9 12 2 2 4-4" /></>), "UPRN match confidence")}
          {infoItem(ic(<><path d="m12.8 2.2a2 2 0 0 0-1.6 0L2.6 6.1a1 1 0 0 0 0 1.8l8.6 3.9a2 2 0 0 0 1.6 0l8.6-3.9a1 1 0 0 0 0-1.8Z" /><path d="m22 17.7-9.2 4.1a2 2 0 0 1-1.6 0L2 17.7" /><path d="m22 12.7-9.2 4.1a2 2 0 0 1-1.6 0L2 12.7" /></>), "Construction materials")}
        </div>
      </div>

      <div style={{ background: "var(--warm-bg-2, #F3EFE8)", border: "1px solid var(--border-line, #DED7CC)", borderRadius: 12, padding: "20px 22px" }}>
        <div className="tag" style={{ marginBottom: 18 }}>Map legend</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "14px 12px" }}>
          {legendRow("#ef4444", "High risk", n(c.Red))}
          {legendRow("#f59e0b", "Medium risk", n(c.Amber))}
          {legendRow("#22c55e", "Low risk", n(c.Green))}
          {legendRow("#64748b", "No evidence", n(c.none))}
        </div>
        <p style={{ margin: "16px 0 0", fontSize: 13, color: "var(--muted, #6B6560)", lineHeight: 1.55 }}>
          Marker colour reflects the worst FRA / FRAEW rating linked to the block.
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--border-line, #DED7CC)" }}>
          <span
            style={{
              flexShrink: 0,
              width: 30,
              height: 30,
              borderRadius: 999,
              background: "#fff",
              color: "var(--navy, #1E3246)",
              fontSize: 12,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "2.5px solid #64748b",
              boxSizing: "border-box",
            }}
          >
            12
          </span>
          <span style={{ fontSize: 13, color: "var(--muted, #6B6560)", lineHeight: 1.55 }}>
            Each circle is a block; the number shows how many flats it contains.
          </span>
        </div>
      </div>
    </div>
  );
}
