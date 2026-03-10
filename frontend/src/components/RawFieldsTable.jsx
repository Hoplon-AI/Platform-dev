import React, { useMemo } from "react";

function prettifyKey(k) {
  return String(k)
    .replace(/^__/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function RawFieldsTable({ data }) {
  const rows = useMemo(() => {
    if (!data) return [];
    return Object.entries(data)
      .filter(([k]) => !String(k).startsWith("__")) // hide internal fields
      .map(([k, v]) => ({
        key: prettifyKey(k),
        rawKey: k,
        value: v == null || v === "" ? "—" : String(v),
      }))
      .sort((a, b) => a.key.localeCompare(b.key));
  }, [data]);

  return (
    <div
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: 12,
        overflow: "hidden",
        background: "white",
      }}
    >
      <div style={{ maxHeight: 320, overflow: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f9fafb" }}>
              <th style={th}>Field</th>
              <th style={th}>Value</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.rawKey}>
                <td style={tdKey}>{r.key}</td>
                <td style={tdVal}>{r.value}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td style={tdVal} colSpan={2}>
                  No fields to display.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const th = {
  textAlign: "left",
  fontSize: 12,
  color: "#6b7280",
  padding: "10px 12px",
  borderBottom: "1px solid #e5e7eb",
  position: "sticky",
  top: 0,
  zIndex: 1,
};

const tdKey = {
  padding: "10px 12px",
  borderBottom: "1px solid #f1f5f9",
  width: "42%",
  fontWeight: 700,
  fontSize: 13,
  color: "#111827",
  verticalAlign: "top",
};

const tdVal = {
  padding: "10px 12px",
  borderBottom: "1px solid #f1f5f9",
  fontSize: 13,
  color: "#111827",
  verticalAlign: "top",
  wordBreak: "break-word",
};
