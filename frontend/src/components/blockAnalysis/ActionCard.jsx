import { useState } from "react";
import { ActionSource } from "./Citations";

export function ActionCard({ a }) {
  const [open, setOpen] = useState(false);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const pr = String(a.priority ?? "").toLowerCase();
  const overdue = a.due_date && new Date(a.due_date) < today && String(a.status ?? "").toLowerCase() !== "completed";

  const prTone = pr === "high"
    ? { bg: "#fee2e2", fg: "#991b1b", border: "#fca5a5" }
    : pr === "medium" || pr === "med"
    ? { bg: "#fef3c7", fg: "#92400e", border: "#fde68a" }
    : { bg: "#f1f5f9", fg: "#475569", border: "#e2e8f0" };

  const description = a.description ?? a.action ?? a.finding ?? a.recommendation ?? "";

  // Split description into issue (first ~2 sentences) and action (rest)
  const sentences = description.split(/(?<=[.!?])\s+/);
  const preview = sentences.slice(0, 2).join(" ");
  const hasMore = sentences.length > 2;

  return (
    <div
      style={{
        border: `1px solid ${overdue ? "#fca5a5" : prTone.border}`,
        borderRadius: 10,
        overflow: "hidden",
        background: overdue ? "#fff9f9" : "#fff",
      }}
    >
      {/* ── Header row — always visible, click to expand ── */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", textAlign: "left", background: "none", border: "none",
          cursor: "pointer", padding: "10px 12px",
          display: "flex", gap: 10, alignItems: "flex-start",
        }}
      >
        {/* Priority badge */}
        {pr && (
          <span style={{
            padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700,
            background: prTone.bg, color: prTone.fg, textTransform: "capitalize",
            whiteSpace: "nowrap", marginTop: 1, flexShrink: 0,
          }}>{pr}</span>
        )}

        {/* Issue ref + preview */}
        <span style={{ flex: 1, minWidth: 0 }}>
          {(a.issue_ref || a.source_verified === true) && (
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", display: "block", marginBottom: 2 }}>
              {a.issue_ref}
              {a.hazard_type ? ` · ${a.hazard_type}` : ""}
              {a.source_verified === true && (
                <span style={{ color: "#166534" }} title={`Verified verbatim in source PDF (page ${a.source_page ?? a.pg ?? "?"})`}>
                  {a.issue_ref || a.hazard_type ? " · " : ""}✓ p.{a.source_page ?? a.pg}
                </span>
              )}
            </span>
          )}
          <span style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.5 }}>
            {open ? description : (hasMore ? `${preview}…` : preview)}
          </span>
        </span>

        {/* Due date + expand chevron */}
        <span style={{ flexShrink: 0, textAlign: "right" }}>
          <span style={{
            fontSize: 12, fontWeight: 600, display: "block",
            color: overdue ? "#991b1b" : "var(--muted)",
          }}>
            {a.due_date ? (overdue ? `⚠ Overdue` : a.due_date) : "No date"}
          </span>
          {a.due_date && overdue && (
            <span style={{ fontSize: 11, color: "var(--muted)", display: "block" }}>{a.due_date}</span>
          )}
          <span style={{ fontSize: 11, color: "var(--muted)", display: "block", marginTop: 4 }}>
            {open ? "▲ less" : "▼ more"}
          </span>
        </span>
      </button>

      {/* ── Expanded detail panel ── */}
      {open && (
        <div style={{
          borderTop: "1px solid var(--border-soft, #eef2f7)",
          padding: "12px 14px",
          background: "#f9fafb",
          display: "flex", flexDirection: "column", gap: 8,
        }}>
          {/* Full description already shown above — show meta fields here */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 16px" }}>
            {a.status && (
              <div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Status</div>
                <div style={{ fontSize: 13, color: "var(--text)", textTransform: "capitalize" }}>{a.status}</div>
              </div>
            )}
            {a.responsible && (
              <div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Responsible</div>
                <div style={{ fontSize: 13, color: "var(--text)" }}>{a.responsible}</div>
              </div>
            )}
            {a.hazard_type && (
              <div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Hazard type</div>
                <div style={{ fontSize: 13, color: "var(--text)" }}>{a.hazard_type}</div>
              </div>
            )}
            {a.due_date && (
              <div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Due date</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: overdue ? "#991b1b" : "var(--text)" }}>
                  {overdue ? `⚠ ${a.due_date} (Overdue)` : a.due_date}
                </div>
              </div>
            )}
          </div>
          <ActionSource a={a} />
        </div>
      )}
    </div>
  );
}

export function ActionList({ items, max = 8 }) {
  if (!items?.length) return null;
  return (
    <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
      {items.slice(0, max).map((a, i) => (
        <ActionCard key={i} a={a} />
      ))}
      {items.length > max && (
        <div style={{ fontSize: 12, color: "var(--muted)", padding: "4px 0" }}>
          +{items.length - max} more actions…
        </div>
      )}
    </div>
  );
}
