// Table of properties contained within a block, for PropertyDetails.
import React from "react";
import { getFireAssessment, bandMeta, fmtMoney } from "../../utils/propertyDetails.js";

export default function BlockPropertiesTable({ properties = [], onSelectProperty }) {
  const [hoveredIndex, setHoveredIndex] = React.useState(null);

  if (!properties.length) {
    return <div className="muted">No linked properties found for this block.</div>;
  }

  return (
    <div className="details-block">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
        <div className="details-h" style={{ marginBottom: 0 }}>Contained properties</div>
        {onSelectProperty && (
          <span style={{ fontSize: 11, color: "var(--text-light, #94a3b8)" }}>Click row to view flat</span>
        )}
      </div>

      <div
        className="table-wrap"
        style={{
          maxHeight: 320,
          overflowY: "auto",
          overflowX: "hidden",
          border: "1px solid rgba(148,163,184,0.16)",
          borderRadius: 12,
        }}
      >
        <table className="table">
          <thead>
            <tr>
              <th>Property</th>
              <th>UPRN</th>
              <th>Value</th>
              <th>FRA</th>
              <th>FRAEW</th>
            </tr>
          </thead>
          <tbody>
            {properties.map((item, index) => {
              const fire = getFireAssessment(item);
              const fraMeta = bandMeta(fire.fra?.risk_level);
              const fraewMeta = bandMeta(fire.fraew?.risk_level);
              const isHovered = hoveredIndex === index;

              return (
                <tr
                  key={item.id || item.property_id || item.uprn || index}
                  onClick={() => onSelectProperty?.(item)}
                  onMouseEnter={() => setHoveredIndex(index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  style={{
                    cursor: onSelectProperty ? "pointer" : undefined,
                    background: isHovered ? "rgba(59,130,246,0.06)" : undefined,
                    transition: "background 0.12s ease",
                  }}
                >
                  <td>
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span>
                        {item.address_line_1 ||
                          item.property_reference ||
                          item.id ||
                          `Property ${index + 1}`}
                      </span>
                      <span style={{
                        opacity: isHovered ? 1 : 0,
                        transition: "opacity 0.12s ease",
                        color: "#3b82f6",
                        fontWeight: 600,
                        fontSize: 14,
                        lineHeight: 1,
                      }}>›</span>
                    </span>
                  </td>
                  <td>{item.uprn || "—"}</td>
                  <td>{fmtMoney(item.sum_insured)}</td>
                  <td>{fire.fra ? <span className={`pill ${fraMeta.cls}`}>{fraMeta.label}</span> : "—"}</td>
                  <td>{fire.fraew ? <span className={`pill ${fraewMeta.cls}`}>{fraewMeta.label}</span> : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
