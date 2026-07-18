// Left navigation sidebar: HA selector, workspace/analysis nav, user + sign-out.
import React from "react";

export default function Sidebar({
  accessibleHAs,
  selectedHaId,
  activeNav,
  ingestionResult,
  authUser,
  onSelectHa,
  onUploadDocuments,
  onNavigate,
  onSignOut,
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <img src="/logo.png" alt="EquiRisk" style={{ height: 36, width: "auto", display: "block", marginBottom: 8 }} />
        <div className="pill pill-muted">UNDERWRITER</div>
      </div>

      {accessibleHAs.length > 0 && (
        <div className="side-section">
          <div className="side-head">Housing Association</div>
          {accessibleHAs.length === 1 ? (
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", padding: "6px 10px", background: "var(--panel-soft)", borderRadius: 8, border: "1px solid var(--border-soft)" }}>
              {accessibleHAs[0].ha_name}
            </div>
          ) : (
            <select
              value={selectedHaId}
              onChange={(e) => onSelectHa(e.target.value)}
              style={{ width: "100%", padding: "6px 8px", fontSize: 13, borderRadius: 8, border: "1px solid var(--border)", background: "var(--panel)", color: "var(--text)", cursor: "pointer" }}
            >
              {accessibleHAs.map((ha) => (
                <option key={ha.ha_id} value={ha.ha_id}>{ha.ha_name}</option>
              ))}
            </select>
          )}
        </div>
      )}

      <div className="side-section">
        <div className="side-head">Portfolio Workspace</div>

        <button
          className={`side-link ${activeNav === "uploads" ? "active" : ""}`}
          onClick={onUploadDocuments}
        >
          Upload Documents
        </button>

        <button
          className={`side-link ${activeNav === "overview" ? "active" : ""}`}
          onClick={() => onNavigate("overview")}
          disabled={!ingestionResult}
        >
          Portfolio Overview
        </button>

        <button
          className={`side-link ${activeNav === "insights" ? "active" : ""}`}
          onClick={() => onNavigate("insights")}
          disabled={!ingestionResult}
        >
          Portfolio Insights
        </button>
      </div>

      <div className="side-section">
        <div className="side-head">Analysis</div>
        <button
          className={`side-link ${activeNav === "block-analysis" ? "active" : ""}`}
          onClick={() => onNavigate("block-analysis")}
          disabled={!ingestionResult}
        >
          Block Analysis
        </button>
        <button
          className={`side-link ${activeNav === "risk-map" ? "active" : ""}`}
          onClick={() => onNavigate("risk-map")}
          disabled={!ingestionResult}
        >
          Risk Map
        </button>
      </div>

      <div className="side-section dim">
        <div className="side-head">Coming soon</div>
        <div className="side-item">Evidence Summary</div>
        <div className="side-item">Documents</div>
      </div>

      <div className="side-bottom">
        {authUser && (
          <div style={{ marginBottom: 10, padding: "8px 10px", background: "var(--panel-soft)", borderRadius: 8, border: "1px solid var(--border-soft)" }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", lineHeight: 1.3, marginBottom: 2 }}>
              {authUser.full_name}
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)", lineHeight: 1.3 }}>
              {authUser.organisation}
            </div>
          </div>
        )}
        <button
          className="btn btn-ghost"
          style={{ width: "100%", textAlign: "left" }}
          onClick={onSignOut}
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
