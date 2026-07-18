// Left navigation sidebar: HA selector, workspace/analysis nav, user + sign-out.
// Styled after docs/golden-thread mockup: grouped white cards with red accent
// border on a cream rail. Becomes an off-canvas drawer below 900px.
import React from "react";

function NavItem({ active, disabled, onClick, children }) {
  return (
    <button
      className={`navitem ${active ? "active" : ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

export default function Sidebar({
  accessibleHAs,
  selectedHaId,
  activeNav,
  ingestionResult,
  authUser,
  open,
  onClose,
  onSelectHa,
  onUploadDocuments,
  onNavigate,
  onSignOut,
}) {
  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="sidebar-top">
        <span className="wordmark">EquiRisk</span>
        <button className="sidebar-close" onClick={onClose} aria-label="Close navigation">
          ✕
        </button>
      </div>
      <span className="role-chip">UNDERWRITER</span>

      {accessibleHAs.length > 0 && (
        <div className="navsec">
          <div className="navgroup">Housing Association</div>
          {accessibleHAs.length === 1 ? (
            <div className="navitem navitem-static">{accessibleHAs[0].ha_name}</div>
          ) : (
            <select
              className="nav-select"
              value={selectedHaId}
              onChange={(e) => onSelectHa(e.target.value)}
            >
              {accessibleHAs.map((ha) => (
                <option key={ha.ha_id} value={ha.ha_id}>{ha.ha_name}</option>
              ))}
            </select>
          )}
        </div>
      )}

      <div className="navsec">
        <div className="navgroup">Portfolio</div>
        <NavItem active={activeNav === "uploads"} onClick={onUploadDocuments}>
          Upload Documents
        </NavItem>
        <NavItem
          active={activeNav === "overview"}
          disabled={!ingestionResult}
          onClick={() => onNavigate("overview")}
        >
          Overview
        </NavItem>
        <NavItem
          active={activeNav === "insights"}
          disabled={!ingestionResult}
          onClick={() => onNavigate("insights")}
        >
          Insights
        </NavItem>
      </div>

      <div className="navsec">
        <div className="navgroup">Analysis</div>
        <NavItem
          active={activeNav === "block-analysis"}
          disabled={!ingestionResult}
          onClick={() => onNavigate("block-analysis")}
        >
          Property Analysis
        </NavItem>
        <NavItem
          active={activeNav === "risk-map"}
          disabled={!ingestionResult}
          onClick={() => onNavigate("risk-map")}
        >
          Risk Map
        </NavItem>
      </div>

      <div className="navsec">
        <div className="navgroup">Building Safety</div>
        <span className="navitem soon">Evidence Summary <i className="soon-tag">Soon</i></span>
        <span className="navitem soon">Documents <i className="soon-tag">Soon</i></span>
      </div>

      <div className="sidebar-bottom">
        {authUser && (
          <div className="userbox">
            <b>{authUser.full_name}</b>
            <span>{authUser.organisation}</span>
          </div>
        )}
        <button className="signout" onClick={onSignOut}>Sign out</button>
      </div>
    </aside>
  );
}
