// Small presentational primitives for PropertyDetails.
import React from "react";
import { isPresent, asArray, actionLabelShort } from "../../utils/propertyDetails.js";

export function DetailRow({ label, value }) {
  return (
    <div className="details-sub" style={{ marginTop: 6 }}>
      <b>{label}:</b> {isPresent(value) ? value : "—"}
    </div>
  );
}

export function KeyValueCard({ label, value }) {
  return (
    <div className="kv">
      <div className="kv-k">{label}</div>
      <div className="kv-v">{isPresent(value) ? value : "—"}</div>
    </div>
  );
}

export function BulletList({ items, max = 5 }) {
  const safeItems = asArray(items);
  if (!safeItems.length) return null;

  return (
    <ul style={{ margin: "8px 0 0 18px", padding: 0 }}>
      {safeItems.slice(0, max).map((item, index) => {
        const text = actionLabelShort(item);
        if (!text) return null;
        const pr = String(item?.priority ?? "").toLowerCase();
        return (
          <li key={index} style={{ marginBottom: 4 }}>
            {pr ? (
              <span style={{
                fontSize: 10, fontWeight: 700, textTransform: "capitalize",
                color: pr === "high" ? "#991b1b" : pr === "medium" || pr === "med" ? "#92400e" : "#64748b",
                marginRight: 6,
              }}>[{pr}]</span>
            ) : null}
            {text}
          </li>
        );
      })}
    </ul>
  );
}

// ✓ / ✕ chip for boolean facts. hazard=true => "present" is bad (red), else good (green).
export function Chip({ label, value, hazard = false }) {
  const present = value === true || value === "true" || value === 1 || value === "yes";
  const known = present || value === false || value === "false" || value === 0 || value === "no";
  let bg = "#f1f5f9", color = "#64748b", mark = "–";
  if (known) {
    mark = present ? "✓" : "✕";
    if (present) { bg = hazard ? "#fee2e2" : "#dcfce7"; color = hazard ? "#991b1b" : "#166534"; }
  }
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 9px", borderRadius: 999, fontSize: 11.5, fontWeight: 600, background: bg, color }}>
      <span style={{ fontWeight: 800 }}>{mark}</span>
      {label}
    </span>
  );
}

export function ChipRow({ children }) {
  return <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>{children}</div>;
}

export function MiniStat({ label, value, tone = "default" }) {
  const tones = {
    default: { bg: "var(--panel-soft, #f8fafc)", color: "var(--text)" },
    red: { bg: "#fef2f2", color: "#991b1b" },
    amber: { bg: "#fffbeb", color: "#92400e" },
  };
  const t = tones[tone] || tones.default;
  return (
    <div style={{ background: t.bg, borderRadius: 10, padding: "8px 10px", border: "1px solid var(--border-soft, #eef2f7)" }}>
      <div style={{ fontSize: 10.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)" }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 800, marginTop: 2, color: t.color }}>{isPresent(value) ? value : "—"}</div>
    </div>
  );
}

export function MeasureHead({ children }) {
  return <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--muted)", margin: "14px 0 2px" }}>{children}</div>;
}

// Renders label/value facts as a responsive grid of small cells (instead of stacked lines).
export function FactGrid({ items }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(118px, 1fr))", gap: 8 }}>
      {items.map((it, i) => (
        <div
          key={i}
          style={{ background: "var(--panel-soft, #f8fafc)", border: "1px solid var(--border-soft, #eef2f7)", borderRadius: 10, padding: "7px 10px", minWidth: 0 }}
        >
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {it.label}
          </div>
          <div style={{ fontSize: 12.5, fontWeight: 600, marginTop: 3, color: "var(--text)", overflowWrap: "anywhere" }}>
            {isPresent(it.value) ? it.value : "—"}
          </div>
        </div>
      ))}
    </div>
  );
}
