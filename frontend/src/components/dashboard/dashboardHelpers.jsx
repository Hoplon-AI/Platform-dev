// Non-component helpers for the portfolio dashboard: KPI icon set + the
// fire-risk subtitle renderer. Kept separate from DashboardWidgets so that file
// only exports components (React Fast Refresh requirement).
import { HoverTooltip } from "./DashboardWidgets.jsx";

// Lightweight inline stroke icons (lucide-style) for the KPI cards.
export const KPI_ICONS = {
  value: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 7V5a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h14a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H5a2 2 0 0 1-2-2V6" />
      <circle cx="16" cy="12" r="1.4" />
    </svg>
  ),
  blocks: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 21h18" /><path d="M5 21V7l7-4 7 4v14" /><path d="M9 9h.01M15 9h.01M9 13h.01M15 13h.01M9 17h.01M15 17h.01" />
    </svg>
  ),
  fra: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
    </svg>
  ),
  fraew: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="1.5" /><path d="M3 9h18M3 14h18M8 4v5m8-5v5m-4 5v6m-4-6h8" />
    </svg>
  ),
  enhanced: (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4z" /><path d="M19 14l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" />
    </svg>
  ),
};

// Renders high-risk / medium-risk badges for a fire-evidence card.
// Returns null when there are no red/amber blocks so the card shows no zeroes.
export function fireRiskSubtitle(counts) {
  if (!counts || (counts.red <= 0 && counts.amber <= 0 && counts.green <= 0)) return null;
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
      {counts.red > 0 ? (
        <HoverTooltip
          tip="Block rated Red — high fire risk"
          badgeStyle={{ padding: "2px 8px", borderRadius: 6, background: "rgba(225,29,72,0.09)", border: "1px solid rgba(225,29,72,0.28)", fontWeight: 600, fontSize: 13, color: "var(--navy)", cursor: "default" }}
        >
          {counts.red} high-risk
        </HoverTooltip>
      ) : null}
      {counts.amber > 0 ? (
        <HoverTooltip
          tip="Block rated Amber — medium fire risk"
          badgeStyle={{ padding: "2px 8px", borderRadius: 6, background: "rgba(245,158,11,0.10)", border: "1px solid rgba(245,158,11,0.30)", fontWeight: 600, fontSize: 13, color: "var(--navy)", cursor: "default" }}
        >
          {counts.amber} mid-risk
        </HoverTooltip>
      ) : null}
      {counts.green > 0 ? (
        <HoverTooltip
          tip="Block rated Green — low fire risk"
          badgeStyle={{ padding: "2px 8px", borderRadius: 6, background: "rgba(34,197,94,0.10)", border: "1px solid rgba(34,197,94,0.30)", fontWeight: 600, fontSize: 13, color: "var(--navy)", cursor: "default" }}
        >
          {counts.green} low-risk
        </HoverTooltip>
      ) : null}
    </span>
  );
}
