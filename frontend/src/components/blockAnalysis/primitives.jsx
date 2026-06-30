import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { isPresent } from "../../utils/blockModel";

// A small PDF-document thumbnail (pure SVG) — a page with a red PDF tab and
// faux text lines. Gives each provenance card a recognisable "source file" visual.
export function PdfThumbnail() {
  return (
    <svg width="46" height="58" viewBox="0 0 46 58" fill="none" style={{ flexShrink: 0, filter: "drop-shadow(0 2px 4px rgba(30,50,70,0.12))" }}>
      {/* page */}
      <path d="M4 3a3 3 0 0 1 3-3h24l11 11v44a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V3Z" fill="#fff" stroke="#E2DACE" strokeWidth="1" />
      {/* folded corner */}
      <path d="M31 0l11 11H34a3 3 0 0 1-3-3V0Z" fill="#F1ECE4" />
      {/* faux text lines */}
      <rect x="10" y="20" width="20" height="2.4" rx="1.2" fill="#D8D2C8" />
      <rect x="10" y="26" width="26" height="2.4" rx="1.2" fill="#D8D2C8" />
      <rect x="10" y="32" width="22" height="2.4" rx="1.2" fill="#D8D2C8" />
      {/* red PDF tab */}
      <rect x="6" y="40" width="26" height="13" rx="2.5" fill="#B8564B" />
      <text x="19" y="49.5" textAnchor="middle" fontSize="8" fontWeight="700" fill="#fff" fontFamily="Arial, sans-serif">PDF</text>
    </svg>
  );
}

// ---------------------------------------------------------------- tooltips

const TIP_WIDTH = 248;

// Tooltip rendered via a portal with position:fixed so it escapes the
// `overflow:hidden` on .card (and any scroll container) instead of being clipped,
// and is clamped to the viewport so it never runs off an edge.
export function Tip({ text, children, align = "left" }) {
  const ref = useRef(null);
  const [pos, setPos] = useState(null);
  if (!text) return children;

  const open = () => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    const maxLeft = window.innerWidth - TIP_WIDTH - 8;
    const left = align === "right" ? r.right - TIP_WIDTH : r.left;
    setPos({ top: r.bottom + 6, left: Math.max(8, Math.min(left, maxLeft)) });
  };

  return (
    <span
      ref={ref}
      style={{ display: "inline-flex", alignItems: "center" }}
      onMouseEnter={open}
      onMouseLeave={() => setPos(null)}
    >
      {children}
      {pos &&
        createPortal(
          <span
            role="tooltip"
            style={{
              position: "fixed", top: pos.top, left: pos.left, width: TIP_WIDTH, zIndex: 1000,
              background: "#0f172a", color: "#f8fafc", fontSize: 12, fontWeight: 400, lineHeight: 1.5,
              padding: "9px 11px", borderRadius: 8, boxShadow: "0 10px 30px rgba(15,23,42,0.28)",
              pointerEvents: "none", textTransform: "none", letterSpacing: 0,
            }}
          >
            {text}
          </span>,
          document.body
        )}
    </span>
  );
}

export function InfoTip({ text, children, align }) {
  return (
    <Tip text={text} align={align}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 5, cursor: "help" }}>
        {children}
        <span
          aria-hidden
          style={{
            width: 14, height: 14, borderRadius: 999, border: "1px solid currentColor", opacity: 0.55,
            fontSize: 9, fontWeight: 800, display: "inline-flex", alignItems: "center", justifyContent: "center",
            lineHeight: 1, fontStyle: "italic",
          }}
        >
          i
        </span>
      </span>
    </Tip>
  );
}

// ---------------------------------------------------------------- primitives

export function Pill({ children, cls = "pill-muted" }) {
  return <span className={`pill ${cls}`}>{children}</span>;
}

// Colored Yes/No for the computed in-date status.
export function InDateBadge({ status }) {
  if (!status || status.inDate === null) return <span style={{ color: "var(--muted)" }}>—</span>;
  const estimated = status.basis === "assessment+5y";
  return (
    <span style={{ color: status.inDate ? "#166534" : "#991b1b", fontWeight: 700 }}>
      {status.inDate ? "Yes" : "No"}
      {estimated ? <span style={{ color: "var(--muted)", fontWeight: 600 }}> (est.)</span> : null}
    </span>
  );
}

export function RiskDot({ band }) {
  const color = { Red: "#ef4444", Amber: "#f59e0b", Green: "#10b981" }[band] || "#cbd5e1";
  return <span style={{ width: 9, height: 9, borderRadius: 999, background: color, flexShrink: 0, display: "inline-block" }} title={band} />;
}

// Summary + filter chip in the toolbar (count of blocks in a band; click to filter).
export function StatChip({ label, band, count, active, onClick }) {
  return (
    <button type="button" className={`ba-stat${active ? " is-active" : ""}`} onClick={onClick}>
      {band ? <RiskDot band={band} /> : null}
      {label}
      <span className="ba-stat-n">{count}</span>
    </button>
  );
}

// Presence/hazard chip with optional hover explanation. hazard=true => "present" is bad (red).
export function Chip({ label, value, hazard = false, tip }) {
  const present = value === true || value === "true" || value === 1 || value === "yes";
  const known = present || value === false || value === "false" || value === 0 || value === "no";
  let bg = "#f1f5f9", color = "#64748b", mark = "–";
  if (known) {
    mark = present ? "✓" : "✕";
    if (present) { bg = hazard ? "#fee2e2" : "#dcfce7"; color = hazard ? "#991b1b" : "#166534"; }
    else { bg = "#f1f5f9"; color = "#64748b"; }
  }
  const chip = (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: bg, color, cursor: tip ? "help" : "default" }}>
      <span style={{ fontWeight: 800 }}>{mark}</span>
      {label}
    </span>
  );
  return tip ? <Tip text={tip}>{chip}</Tip> : chip;
}

export function StatTile({ label, value, sub, tone = "default", tip, tipAlign }) {
  const tones = {
    default: { bg: "var(--panel-soft, #f8fafc)", color: "var(--text)" },
    red: { bg: "#fef2f2", color: "#991b1b" },
    amber: { bg: "#fffbeb", color: "#92400e" },
    green: { bg: "#f0fdf4", color: "#166534" },
    blue: { bg: "#eff6ff", color: "#1e40af" },
  };
  const t = tones[tone] || tones.default;
  const labelEl = (
    <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--muted)" }}>
      {label}
    </span>
  );
  return (
    <div style={{ background: t.bg, borderRadius: 12, padding: "12px 14px", border: "1px solid var(--border-soft, #eef2f7)" }}>
      {tip ? <InfoTip text={tip} align={tipAlign}>{labelEl}</InfoTip> : labelEl}
      <div style={{ fontSize: 22, fontWeight: 800, marginTop: 4, color: t.color, lineHeight: 1.1 }}>{value}</div>
      {sub ? <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>{sub}</div> : null}
    </div>
  );
}

export function KV({ label, value, tip }) {
  const labelEl = <span style={{ color: "var(--muted)", fontSize: 13 }}>{label}</span>;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "7px 0", borderBottom: "1px solid var(--border-soft, #eef2f7)" }}>
      {tip ? <InfoTip text={tip}>{labelEl}</InfoTip> : labelEl}
      <span style={{ fontWeight: 600, fontSize: 13, textAlign: "right", color: "var(--text)" }}>{isPresent(value) ? value : "—"}</span>
    </div>
  );
}

export function Section({ title, subtitle, accessory, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="card">
      <div
        className="card-header row-between"
        style={{ cursor: "pointer", userSelect: "none", paddingBottom: open ? undefined : 16 }}
        onClick={() => setOpen((o) => !o)}
      >
        <div>
          <div className="card-title">{title}</div>
          {subtitle ? <div className="card-subtitle">{subtitle}</div> : null}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {accessory}
          <span style={{ fontSize: 18, lineHeight: 1, color: "var(--muted)" }}>{open ? "▾" : "▸"}</span>
        </div>
      </div>
      {open ? <div className="card-body" style={{ paddingTop: 4 }}>{children}</div> : null}
    </div>
  );
}

export function ChipRow({ children }) {
  return <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 6 }}>{children}</div>;
}

export function SubHead({ children, tip }) {
  const el = (
    <span style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--muted)" }}>
      {children}
    </span>
  );
  return <div style={{ margin: "16px 0 2px" }}>{tip ? <InfoTip text={tip}>{el}</InfoTip> : el}</div>;
}
