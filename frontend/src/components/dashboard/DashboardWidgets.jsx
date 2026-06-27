// Small shared presentational pieces for the portfolio dashboard.
import React, { useState } from "react";

import { riskBadgeStyle } from "../../utils/fireRisk.js";

export function RiskBadge({ band }) {
  return (
    <span
      style={{
        ...riskBadgeStyle(band),
        borderRadius: 999,
        padding: "6px 10px",
        fontSize: 12,
        fontWeight: 800,
        whiteSpace: "nowrap",
      }}
    >
      {band}
    </span>
  );
}

export function HoverTooltip({ children, tip, badgeStyle, tipWidth = 160 }) {
  const [visible, setVisible] = useState(false);
  return (
    <span
      style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      <span style={badgeStyle}>{children}</span>
      <span style={{
        position: "absolute",
        top: "calc(100% + 8px)",
        left: "50%",
        transform: "translateX(-50%)",
        width: tipWidth,
        background: "var(--panel)",
        color: "var(--text-light)",
        fontSize: 12,
        fontWeight: 400,
        lineHeight: 1.5,
        textTransform: "none",
        letterSpacing: "normal",
        borderRadius: 8,
        border: "1px solid var(--border, #e2e8f0)",
        padding: "9px 12px",
        pointerEvents: "none",
        zIndex: 50,
        boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
        opacity: visible ? 1 : 0,
        transition: "opacity 0.18s ease",
      }}>
        {tip}
      </span>
    </span>
  );
}

export function KpiCard({ title, value, subtitle, tone = "default", icon = null }) {
  return (
    <div className={`dashboard-card dashboard-card-${tone}`}>
      {icon ? <div className="dashboard-card-icon">{icon}</div> : null}
      <div className="dashboard-card-title">{title}</div>
      <div className="dashboard-card-value">{value}</div>
      {subtitle ? <div className="dashboard-card-sub">{subtitle}</div> : null}
    </div>
  );
}

export function MiniSummaryTable({ title, subtitle, rows, columns }) {
  return (
    <div
      style={{
        background: "var(--panel-soft)",
        border: "1px solid var(--border-soft)",
        borderRadius: 16,
        padding: 14,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{title}</div>
      {subtitle ? <div className="muted" style={{ marginBottom: 10 }}>{subtitle}</div> : null}

      {!rows.length ? (
        <div className="muted">No data available.</div>
      ) : (
        <div className="table-wrap" style={{ maxHeight: 260, overflowY: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column.key}>{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={`${row.label || row.block || idx}`}>
                  {columns.map((column) => (
                    <td key={column.key}>
                      {typeof column.render === "function"
                        ? column.render(row)
                        : row[column.key] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
