import { useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  buildBlocks,
  collectFireDocuments,
  blockOverallBand,
  summariseBlockRisk,
  assessmentStatus,
  inDateTip,
  bandVerdict,
  bandClass,
  blockStreetText,
  blockDisplayAddress,
  computeBlockAlerts,
  getFireRiskBand,
  getFireDocumentRisk,
  fraActionStats,
  actionLabel,
  getWallTypes,
  heightCategory,
  fmtMoney,
  fmt,
  titleCase,
  boolLabel,
  isPresent,
} from "../utils/blockModel";

// Plain-language explanations for jargon, surfaced on hover. "What it is + why it matters".
const G = {
  fra: "Fire Risk Assessment — reviews fire safety of the building's common and internal areas, required under the Regulatory Reform (Fire Safety) Order 2005.",
  fraew: "Fire Risk Appraisal of External Walls (PAS 9980) — assesses the cladding and external wall build-up for fire risk.",
  overall: "The worse of the FRA and FRAEW ratings — the headline fire-risk position for this block.",
  totalActions: "All remedial actions recommended by the latest FRA.",
  overdueActions: "FRA remedial actions past their due date and not completed. A backlog signals required fire-safety works are slipping.",
  noDateActions: "Actions with no due date set — they can't be tracked for compliance and usually need chasing.",
  highActions: "Actions the assessor flagged as high priority / urgent.",
  inDate: "Whether the assessment is still within its validity period (typically 5 years from the assessment date).",
  assessmentType: "FRA scope: Type 1 (common parts, non-destructive) through Type 4 (destructive, includes flats).",
  bsa2022: "Building Safety Act 2022 — imposes stricter duties on Higher-Risk Buildings (18m+ or 7+ storeys).",
  mor: "Mandatory Occurrence Report — a safety event that must be reported to the Building Safety Regulator.",
  evacuation: "Planned fire response: 'stay put' (defend in place) vs 'simultaneous' (evacuate everyone) vs 'phased'.",
  compartmentation: "Fire-resisting division of the building that contains fire and smoke to limit spread.",
  pas9980: "Whether the external-wall appraisal followed the PAS 9980:2022 methodology.",
  clause14: "PAS 9980 Clause 14 fire-engineering analysis — invoked when the standard appraisal is inconclusive.",
  combustible: "Any external wall material that can contribute to fire spread.",
  acm: "Aluminium Composite Material — the Grenfell-type cladding; the highest fire concern.",
  hpl: "High-Pressure Laminate cladding — combustible.",
  eps: "Expanded polystyrene insulation — combustible.",
  pir: "Polyisocyanurate insulation — combustible.",
  phenolic: "Phenolic foam insulation — combustible.",
  mineralWool: "Mineral wool insulation — non-combustible (a positive sign).",
  bs8414: "Large-scale fire-test evidence (BS 8414) for the cladding system — critical when combustible cladding sits above 18m.",
  br135: "BR 135 fire-performance criteria — the pass/fail basis for a BS 8414 test.",
  cavityBarriers: "Barriers inside wall cavities that stop hidden fire and smoke spread.",
  fireBreaks: "Fire-stopping at floor levels and party walls to limit vertical and lateral spread.",
  dryRiser: "An empty pipe firefighters charge with water on arrival (buildings up to ~50m).",
  wetRiser: "A permanently charged firefighting water main (taller buildings).",
  heightSurvey: "A measured survey is recommended to confirm building height — it determines which regulations apply.",
  intrusive: "Opening-up of the wall is recommended to confirm its actual construction.",
  asbestos: "Asbestos is suspected behind the cladding — affects how and when remediation can proceed.",
  listed: "Statutory heritage protection — can constrain or delay remediation works.",
  tiv: "Total Insured Value — the sum insured across all units in this block.",
  confidence: "How confident the AI extraction was in reading this document (0–1).",
};

// ---------------------------------------------------------------- tooltips

const TIP_WIDTH = 248;

// Tooltip rendered via a portal with position:fixed so it escapes the
// `overflow:hidden` on .card (and any scroll container) instead of being clipped,
// and is clamped to the viewport so it never runs off an edge.
function Tip({ text, children, align = "left" }) {
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

function InfoTip({ text, children, align }) {
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

function Pill({ children, cls = "pill-muted" }) {
  return <span className={`pill ${cls}`}>{children}</span>;
}

// Colored Yes/No for the computed in-date status.
function InDateBadge({ status }) {
  if (!status || status.inDate === null) return <span style={{ color: "var(--muted)" }}>—</span>;
  const estimated = status.basis === "assessment+5y";
  return (
    <span style={{ color: status.inDate ? "#166534" : "#991b1b", fontWeight: 700 }}>
      {status.inDate ? "Yes" : "No"}
      {estimated ? <span style={{ color: "var(--muted)", fontWeight: 600 }}> (est.)</span> : null}
    </span>
  );
}

function RiskDot({ band }) {
  const color = { Red: "#ef4444", Amber: "#f59e0b", Green: "#10b981" }[band] || "#cbd5e1";
  return <span style={{ width: 9, height: 9, borderRadius: 999, background: color, flexShrink: 0, display: "inline-block" }} title={band} />;
}

// Summary + filter chip in the toolbar (count of blocks in a band; click to filter).
function StatChip({ label, band, count, active, onClick }) {
  return (
    <button type="button" className={`ba-stat${active ? " is-active" : ""}`} onClick={onClick}>
      {band ? <RiskDot band={band} /> : null}
      {label}
      <span className="ba-stat-n">{count}</span>
    </button>
  );
}

// Presence/hazard chip with optional hover explanation. hazard=true => "present" is bad (red).
function Chip({ label, value, hazard = false, tip }) {
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

function StatTile({ label, value, sub, tone = "default", tip, tipAlign }) {
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

function KV({ label, value, tip }) {
  const labelEl = <span style={{ color: "var(--muted)", fontSize: 13 }}>{label}</span>;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "7px 0", borderBottom: "1px solid var(--border-soft, #eef2f7)" }}>
      {tip ? <InfoTip text={tip}>{labelEl}</InfoTip> : labelEl}
      <span style={{ fontWeight: 600, fontSize: 13, textAlign: "right", color: "var(--text)" }}>{isPresent(value) ? value : "—"}</span>
    </div>
  );
}

function Section({ title, subtitle, accessory, defaultOpen = false, children }) {
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

function ChipRow({ children }) {
  return <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 6 }}>{children}</div>;
}

function SubHead({ children, tip }) {
  const el = (
    <span style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--muted)" }}>
      {children}
    </span>
  );
  return <div style={{ margin: "16px 0 2px" }}>{tip ? <InfoTip text={tip}>{el}</InfoTip> : el}</div>;
}

function ActionCard({ a, index }) {
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
          {a.issue_ref && (
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", display: "block", marginBottom: 2 }}>
              {a.issue_ref}
              {a.hazard_type ? ` · ${a.hazard_type}` : ""}
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
        </div>
      )}
    </div>
  );
}

function ActionList({ items, max = 8 }) {
  if (!items?.length) return null;
  return (
    <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
      {items.slice(0, max).map((a, i) => (
        <ActionCard key={i} a={a} index={i} />
      ))}
      {items.length > max && (
        <div style={{ fontSize: 12, color: "var(--muted)", padding: "4px 0" }}>
          +{items.length - max} more actions…
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- dossier

function Dossier({ block }) {
  const fra = block.latest_fra;
  const fraew = block.latest_fraew;
  const { band: overall, reasons } = useMemo(() => summariseBlockRisk(block), [block]);
  const { street, postcode } = blockDisplayAddress(block);
  const alerts = useMemo(() => computeBlockAlerts(block), [block]);
  const stats = useMemo(() => fraActionStats(fra), [fra]);
  const fraewStats = useMemo(() => fraActionStats(fraew), [fraew]);
  const wallTypes = useMemo(() => getWallTypes(fraew), [fraew]);
  const fraStatus = useMemo(() => assessmentStatus(fra), [fra]);
  const fraewStatus = useMemo(() => assessmentStatus(fraew), [fraew]);

  const hCat = heightCategory(block.maxHeight) || (fraew?.building_height_category && titleCase(fraew.building_height_category));
  const fraBand = getFireRiskBand(fra);
  const fraewBand = getFireRiskBand(fraew);
  const bandColor = { Red: "#ef4444", Amber: "#f59e0b", Green: "#10b981" }[overall] || "#94a3b8";
  const toneOf = (b) => ({ Red: "red", Amber: "amber", Green: "green" }[b] || "default");
  const alertTone = {
    red: { bg: "#fef2f2", bd: "#fecaca", fg: "#991b1b" },
    amber: { bg: "#fffbeb", bd: "#fde68a", fg: "#92400e" },
    info: { bg: "#eff6ff", bd: "#bfdbfe", fg: "#1e40af" },
  };
  const sortedAlerts = [...alerts].sort((a, b) => ({ red: 0, amber: 1, info: 2 }[a.tone] - { red: 0, amber: 1, info: 2 }[b.tone]));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Hero */}
      <div className="card" style={{ borderLeft: `5px solid ${bandColor}` }}>
        <div className="card-body">
          <div className="row-between" style={{ alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1.15 }}>{street}</div>
              <div style={{ color: "var(--muted)", marginTop: 4, fontSize: 14 }}>
                Block {block.name}{postcode ? ` · ${postcode}` : ""}{block.parent_uprn ? ` · UPRN ${block.parent_uprn}` : ""}
              </div>
            </div>
            <Tip text={G.overall}>
              <span className={`pill ${bandClass(overall)}`} style={{ fontSize: 13, padding: "8px 14px", cursor: "help" }}>{bandVerdict(overall)}</span>
            </Tip>
          </div>

          {/* Why */}
          <div style={{ marginTop: 12, fontSize: 13.5, color: "var(--text-light, #475569)", background: "var(--panel-soft, #f8fafc)", border: "1px solid var(--border-soft, #eef2f7)", borderRadius: 10, padding: "10px 12px" }}>
            {reasons.length ? (
              <><b style={{ color: "var(--text)" }}>Driven by:</b> {reasons.join(" · ")}</>
            ) : (
              <>No significant fire-risk concerns recorded for this block.</>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 10, marginTop: 16 }}>
            <StatTile label="Units" value={block.count} />
            <StatTile label="Max height" value={block.maxHeight > 0 ? `${fmt(block.maxHeight, 1)} m` : "—"} sub={hCat || undefined} />
            <StatTile label="Total insured" value={`£${fmtMoney(block.totalValue)}`} tip={G.tiv} tipAlign="right" />
            <StatTile label="FRA" value={fra ? fraBand : "None"} tone={toneOf(fraBand)} tip={G.fra} tipAlign="right" />
            <StatTile label="FRAEW" value={fraew ? fraewBand : "None"} tone={toneOf(fraewBand)} tip={G.fraew} tipAlign="right" />
            <StatTile label="Overdue actions" value={stats.overdue} tone={stats.overdue > 0 ? "red" : "default"} tip={G.overdueActions} tipAlign="right" />
          </div>
        </div>
      </div>

      {/* Alerts */}
      <div className="card">
        <div className="card-body">
          <div className="card-title" style={{ marginBottom: 10 }}>Risk flags</div>
          {sortedAlerts.length === 0 ? (
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "#166534", fontWeight: 600, fontSize: 14 }}>✓ No critical flags identified.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {sortedAlerts.map((a, i) => {
                const t = alertTone[a.tone] || alertTone.info;
                return (
                  <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", background: t.bg, border: `1px solid ${t.bd}`, color: t.fg, borderRadius: 10, padding: "9px 12px", fontSize: 13, fontWeight: 600 }}>
                    <span style={{ fontWeight: 800 }}>{a.tone === "info" ? "ⓘ" : "⚠"}</span>
                    <span>{a.text}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Building & construction */}
      <Section title="Building & construction" subtitle="Physical characteristics from the SoV + enrichment" defaultOpen>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "0 24px" }}>
          <div>
            <KV label="Units" value={block.count} />
            <KV label="Max height" value={block.maxHeight > 0 ? `${fmt(block.maxHeight, 1)} m` : "—"} />
            <KV label="Height category" value={hCat} />
            <KV label="Max storeys" value={block.maxStoreys > 0 ? block.maxStoreys : "—"} />
            <KV label="Build year" value={block.buildYear} />
          </div>
          <div>
            <KV label="Total insured value" value={`£${fmtMoney(block.totalValue)}`} tip={G.tiv} />
            <KV label="Listed building" value={block.isListed ? `Yes${block.listedGrade ? ` (Grade ${block.listedGrade})` : ""}` : "No"} tip={G.listed} />
            <KV label="Parent UPRN" value={block.parent_uprn} />
            <KV label="Coordinates" value={block.hasValidCoords ? `${fmt(block.lat, 5)}, ${fmt(block.lon, 5)}` : "—"} />
          </div>
        </div>
      </Section>

      {/* FRA */}
      <Section title="Fire Risk Assessment (FRA)" subtitle="Internal / common-parts fire safety" defaultOpen accessory={<span className={`pill ${bandClass(fraBand)}`}>{fra ? fraBand : "None"}</span>}>
        {!fra ? (
          <div className="muted">No FRA linked to this block.</div>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "0 24px" }}>
              <div>
                <KV label="Risk rating" value={getFireDocumentRisk(fra)} />
                <KV label="Assessment type" value={fra.fra_assessment_type} tip={G.assessmentType} />
                <KV label="Assessment date" value={fra.assessment_date} />
                <KV label="Valid until" value={fra.assessment_valid_until} />
                <KV label="In date" value={<InDateBadge status={fraStatus} />} tip={inDateTip(fraStatus)} />
              </div>
              <div>
                <KV label="Assessor" value={fra.assessor_name} />
                <KV label="Company" value={fra.assessor_company} />
                <KV label="Evacuation strategy" value={fra.evacuation_strategy ? titleCase(fra.evacuation_strategy) : null} tip={G.evacuation} />
                <KV label="BSA 2022 applicable" value={boolLabel(fra.bsa_2022_applicable)} tip={G.bsa2022} />
                <KV label="MOR event noted" value={boolLabel(fra.mandatory_occurrence_noted)} tip={G.mor} />
              </div>
            </div>

            <SubHead tip={G.compartmentation}>Fire safety measures</SubHead>
            <ChipRow>
              <Chip label="Sprinklers" value={fra.has_sprinkler_system ?? fra.sprinkler_system} />
              <Chip label="Smoke detection" value={fra.has_smoke_detection ?? fra.smoke_detection} />
              <Chip label="Fire alarm" value={fra.has_fire_alarm_system ?? fra.fire_alarm_system} />
              <Chip label="Fire doors" value={fra.has_fire_doors ?? fra.fire_doors} />
              <Chip label="Compartmentation" value={fra.has_compartmentation ?? fra.compartmentation} tip={G.compartmentation} />
              <Chip label="Emergency lighting" value={fra.has_emergency_lighting} />
              <Chip label="Dry riser" value={fra.has_dry_riser} tip={G.dryRiser} />
              <Chip label="Wet riser" value={fra.has_wet_riser} tip={G.wetRiser} />
            </ChipRow>

            <SubHead>Remedial actions</SubHead>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10 }}>
              <StatTile label="Total" value={stats.total} tip={G.totalActions} />
              <StatTile label="Overdue" value={stats.overdue} tone={stats.overdue > 0 ? "red" : "default"} tip={G.overdueActions} />
              <StatTile label="No date" value={stats.noDate} tone={stats.noDate > 0 ? "amber" : "default"} tip={G.noDateActions} tipAlign="right" />
              <StatTile label="High priority" value={stats.high} tone={stats.high > 0 ? "amber" : "default"} tip={G.highActions} tipAlign="right" />
            </div>
            <ActionList items={stats.items} max={20} />
            {fra.summary ? <div style={{ marginTop: 12, fontSize: 13, color: "var(--text-light, #475569)" }}><b>Summary:</b> {fra.summary}</div> : null}
          </>
        )}
      </Section>

      {/* FRAEW */}
      <Section title="External Wall System (FRAEW)" subtitle="Cladding, insulation & PAS 9980 appraisal" defaultOpen accessory={<span className={`pill ${bandClass(fraewBand)}`}>{fraew ? fraewBand : "None"}</span>}>
        {!fraew ? (
          <div className="muted">No FRAEW linked to this block.</div>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "0 24px" }}>
              <div>
                <KV label="Building risk rating" value={fraew.building_risk_rating ?? getFireDocumentRisk(fraew)} />
                <KV label="PAS 9980 compliant" value={boolLabel(fraew.pas_9980_compliant)} tip={G.pas9980} />
                <KV label="Clause 14 applied" value={boolLabel(fraew.clause_14_applied)} tip={G.clause14} />
                <KV label="Assessment date" value={fraew.assessment_date} />
                <KV label="Valid until" value={fraew.assessment_valid_until} />
                <KV label="In date" value={<InDateBadge status={fraewStatus} />} tip={inDateTip(fraewStatus)} />
              </div>
              <div>
                <KV label="Building height" value={fraew.building_height_m ? `${fmt(fraew.building_height_m, 1)} m` : null} />
                <KV label="Construction frame" value={fraew.construction_frame_type} />
                <KV label="Retrofit year" value={fraew.retrofit_year} />
                <KV label="Remediation required" value={boolLabel(fraew.has_remedial_actions ?? fraew.remediation_required)} />
                <KV label="Interim measures" value={boolLabel(fraew.interim_measures_required, "Required", "Not required")} />
                <KV label="Assessor" value={fraew.assessor_name} />
              </div>
            </div>

            <SubHead tip={G.combustible}>Cladding & insulation</SubHead>
            <ChipRow>
              <Chip label="Combustible cladding" value={fraew.has_combustible_cladding ?? fraew.combustible_cladding} hazard tip={G.combustible} />
              <Chip label="ACM" value={fraew.aluminium_composite_cladding} hazard tip={G.acm} />
              <Chip label="HPL" value={fraew.hpl_cladding_present} hazard tip={G.hpl} />
              <Chip label="Timber" value={fraew.timber_cladding_present} hazard />
              <Chip label="EPS" value={fraew.eps_insulation_present} hazard tip={G.eps} />
              <Chip label="PIR" value={fraew.pir_insulation_present} hazard tip={G.pir} />
              <Chip label="Phenolic" value={fraew.phenolic_insulation_present} hazard tip={G.phenolic} />
              <Chip label="Mineral wool" value={fraew.mineral_wool_insulation_present} tip={G.mineralWool} />
            </ChipRow>

            <SubHead tip={G.fireBreaks}>Protections & compliance</SubHead>
            <ChipRow>
              <Chip label="Cavity barriers" value={fraew.cavity_barriers_present} tip={G.cavityBarriers} />
              <Chip label="Fire breaks (floors)" value={fraew.fire_breaks_floor_level} tip={G.fireBreaks} />
              <Chip label="Fire breaks (party walls)" value={fraew.fire_breaks_party_walls} tip={G.fireBreaks} />
              <Chip label="BS 8414 evidence" value={fraew.bs8414_test_evidence} tip={G.bs8414} />
              <Chip label="BR 135 criteria" value={fraew.br135_criteria_met} tip={G.br135} />
              <Chip label="Dry riser" value={fraew.dry_riser_present} tip={G.dryRiser} />
              <Chip label="Wet riser" value={fraew.wet_riser_present} tip={G.wetRiser} />
            </ChipRow>

            <SubHead>Recommended further investigation</SubHead>
            <ChipRow>
              <Chip label="Height survey" value={fraew.height_survey_recommended} hazard tip={G.heightSurvey} />
              <Chip label="Fire door survey" value={fraew.fire_door_survey_recommended} hazard />
              <Chip label="Intrusive investigation" value={fraew.intrusive_investigation_recommended} hazard tip={G.intrusive} />
              <Chip label="Asbestos suspected" value={fraew.asbestos_suspected} hazard tip={G.asbestos} />
            </ChipRow>

            {wallTypes.length > 0 && (
              <>
                <SubHead>Wall types ({wallTypes.length})</SubHead>
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th>Ref</th><th>Description</th><th>Coverage</th><th>Insulation</th><th>Risk</th></tr></thead>
                    <tbody>
                      {wallTypes.map((w, i) => (
                        <tr key={i}>
                          <td>{w.type_ref ?? `Type ${i + 1}`}</td>
                          <td>{w.description ?? "—"}</td>
                          <td>{isPresent(w.coverage_percent) ? `${w.coverage_percent}%` : "—"}</td>
                          <td>{w.insulation_type ? titleCase(w.insulation_type) : "—"}</td>
                          <td>{w.overall_risk ? titleCase(w.overall_risk) : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
            {fraewStats.items.length > 0 && (
              <>
                <SubHead>Remedial actions</SubHead>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10 }}>
                  <StatTile label="Total" value={fraewStats.total} tip={G.totalActions} />
                  <StatTile label="Overdue" value={fraewStats.overdue} tone={fraewStats.overdue > 0 ? "red" : "default"} tip={G.overdueActions} />
                  <StatTile label="No date" value={fraewStats.noDate} tone={fraewStats.noDate > 0 ? "amber" : "default"} tip={G.noDateActions} tipAlign="right" />
                  <StatTile label="High priority" value={fraewStats.high} tone={fraewStats.high > 0 ? "amber" : "default"} tip={G.highActions} tipAlign="right" />
                </div>
                <ActionList items={fraewStats.items} max={20} />
              </>
            )}
            {fraew.interim_measures_detail ? <div style={{ marginTop: 12, fontSize: 13, color: "var(--text-light, #475569)" }}><b>Interim measures:</b> {fraew.interim_measures_detail}</div> : null}
            {fraew.summary ? <div style={{ marginTop: 8, fontSize: 13, color: "var(--text-light, #475569)" }}><b>Summary:</b> {fraew.summary}</div> : null}
          </>
        )}
      </Section>

      {/* Properties */}
      <Section title="Properties in this block" subtitle={`${block.count} unit${block.count === 1 ? "" : "s"}`} accessory={<Pill>{block.count}</Pill>}>
        <div className="table-wrap" style={{ maxHeight: 420, overflowY: "auto" }}>
          <table className="table">
            <thead><tr><th>Address</th><th>UPRN</th><th>Sum insured</th><th>FRA</th><th>FRAEW</th></tr></thead>
            <tbody>
              {block.properties.map((p, i) => {
                const pf = getFireRiskBand(p.latest_fra);
                const pfe = getFireRiskBand(p.latest_fraew);
                return (
                  <tr key={p.id ?? p.property_reference ?? i}>
                    <td>{p.address_line_1 || p.address || p.property_reference || `Property ${i + 1}`}</td>
                    <td>{p.uprn ?? "—"}</td>
                    <td>£{fmtMoney(p.sum_insured)}</td>
                    <td>{p.latest_fra ? <span className={`pill ${bandClass(pf)}`}>{pf}</span> : "—"}</td>
                    <td>{p.latest_fraew ? <span className={`pill ${bandClass(pfe)}`}>{pfe}</span> : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Provenance */}
      <Section title="Data provenance" subtitle="Source documents & extraction confidence">
        {block.linkedDocs?.length ? (
          <div>
            {block.linkedDocs.map((d, i) => (
              <KV key={i} label={`${d.document_type} · ${d.filename}`} tip={G.confidence} value={isPresent(d.raw?.extraction_confidence) ? `confidence ${fmt(d.raw.extraction_confidence, 2)}` : (getFireDocumentRisk(d) || "linked")} />
            ))}
          </div>
        ) : (
          <div className="muted">No fire-risk documents linked to this block yet.</div>
        )}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- block list

// Risk-band ordering for sorting (Red worst → none).
const BAND_WEIGHT = { Red: 3, Amber: 2, Green: 1 };
const bandWeight = (band) => BAND_WEIGHT[band] || 0;
const accentClass = (band) => ({ Red: "r-red", Amber: "r-amber", Green: "r-green" }[band] || "");

// One band column cell: a colour pill with a status dot, or an em-dash when the
// block has no such document.
function BandCell({ doc, band }) {
  if (!doc || !band) return <span className="ba-dash">—</span>;
  return (
    <span className={`pill ${bandClass(band)}`}>
      <RiskDot band={band} />
      {band}
    </span>
  );
}

function SortHead({ label, col, sort, onSort, align = "left", width }) {
  const active = sort.key === col;
  return (
    <th
      className={`is-sortable${active ? " is-sorted" : ""}`}
      style={{ textAlign: align, width }}
      onClick={() => onSort(col)}
    >
      {label}
      <span className="ba-arrow">{active ? (sort.dir === "asc" ? "▲" : "▼") : "↕"}</span>
    </th>
  );
}

// Flat list of every block: Address · Flats · UPRN · FRA band · FRAEW band.
// A left accent bar encodes the block's overall (worst) band; rows drill into the dossier.
function BlockTable({ blocks, selectedId, onSelect, sort, onSort }) {
  return (
    <div className="table-wrap" style={{ maxHeight: "calc(100vh - 300px)", overflowY: "auto" }}>
      <table className="ba-table">
        <thead>
          <tr>
            <SortHead label="Address" col="address" sort={sort} onSort={onSort} />
            <SortHead label="Flats" col="flats" sort={sort} onSort={onSort} align="center" width={90} />
            <th>UPRN</th>
            <SortHead label="FRA" col="fra" sort={sort} onSort={onSort} align="center" width={120} />
            <SortHead label="FRAEW" col="fraew" sort={sort} onSort={onSort} align="center" width={120} />
            <th style={{ width: 44 }} aria-label="open" />
          </tr>
        </thead>
        <tbody>
          {blocks.map((b) => {
            const { street, postcode } = blockDisplayAddress(b);
            const fraBand = getFireRiskBand(b.latest_fra);
            const fraewBand = getFireRiskBand(b.latest_fraew);
            const overall = blockOverallBand(b);
            const active = b.id === selectedId;
            return (
              <tr key={b.id} className={active ? "is-active" : undefined} onClick={() => onSelect(b.id)}>
                <td className={`ba-accent ${accentClass(overall)}`}>
                  <div className="ba-addr">{street}</div>
                  <div className="ba-addr-sub">
                    Block {b.name}{postcode ? ` · ${postcode}` : ""}
                  </div>
                </td>
                <td style={{ textAlign: "center" }}>
                  <span className="ba-flats">{b.count}</span>
                </td>
                <td><span className="ba-uprn">{b.parent_uprn ?? <span className="ba-dash">—</span>}</span></td>
                <td style={{ textAlign: "center" }}><BandCell doc={b.latest_fra} band={fraBand} /></td>
                <td style={{ textAlign: "center" }}><BandCell doc={b.latest_fraew} band={fraewBand} /></td>
                <td style={{ textAlign: "center" }}>
                  <span className="ba-chev" aria-hidden>›</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Comparator for the sortable columns.
function compareBlocks(a, b, key) {
  switch (key) {
    case "address":
      return blockDisplayAddress(a).street.localeCompare(blockDisplayAddress(b).street);
    case "flats":
      return (a.count || 0) - (b.count || 0);
    case "fra":
      return bandWeight(getFireRiskBand(a.latest_fra)) - bandWeight(getFireRiskBand(b.latest_fra));
    case "fraew":
      return bandWeight(getFireRiskBand(a.latest_fraew)) - bandWeight(getFireRiskBand(b.latest_fraew));
    default:
      return 0;
  }
}

// ---------------------------------------------------------------- page

export default function BlockAnalysisPage({ ingestionResult, latestFireRiskPayload = null, onUploadNew }) {
  const [query, setQuery] = useState("");
  const [bandFilter, setBandFilter] = useState("all");
  const [sort, setSort] = useState({ key: null, dir: "desc" });
  const [selectedId, setSelectedId] = useState(null);

  const fireDocuments = useMemo(() => collectFireDocuments(ingestionResult, latestFireRiskPayload), [ingestionResult, latestFireRiskPayload]);
  const blocks = useMemo(() => buildBlocks(ingestionResult?.properties || [], fireDocuments), [ingestionResult, fireDocuments]);

  // Overall-band tallies for the summary / filter chips (whole portfolio).
  const counts = useMemo(() => {
    const c = { all: blocks.length, Red: 0, Amber: 0, Green: 0, none: 0 };
    for (const b of blocks) {
      const ob = blockOverallBand(b);
      if (ob === "Red") c.Red++;
      else if (ob === "Amber") c.Amber++;
      else if (ob === "Green") c.Green++;
      else c.none++;
    }
    return c;
  }, [blocks]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return blocks.filter((b) => {
      if (q && !blockStreetText(b).includes(q)) return false;
      if (bandFilter !== "all" && (blockOverallBand(b) || "none") !== bandFilter) return false;
      return true;
    });
  }, [blocks, query, bandFilter]);

  // Sorted view — defaults to the risk-first order from buildBlocks until a column is picked.
  const visible = useMemo(() => {
    if (!sort.key) return filtered;
    const dir = sort.dir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => dir * compareBlocks(a, b, sort.key));
  }, [filtered, sort]);

  const toggleSort = (key) =>
    setSort((s) =>
      s.key === key
        ? { key, dir: s.dir === "asc" ? "desc" : "asc" }
        : { key, dir: key === "address" ? "asc" : "desc" }
    );

  // The detail dossier only opens when a row is explicitly clicked — the list
  // is the primary view, so nothing is auto-selected.
  const selected = useMemo(
    () => (selectedId ? blocks.find((b) => b.id === selectedId) || null : null),
    [blocks, selectedId]
  );

  if (!ingestionResult || !blocks.length) {
    return (
      <>
        <div className="main-head">
          <div>
            <div className="page-title">Block Analysis</div>
            <div className="page-sub">Search a block by street and review its full risk profile.</div>
          </div>
        </div>
        <div className="content-wrap">
          <div className="card">
            <div className="empty-state">
              No portfolio loaded yet. Upload a Schedule of Values to populate blocks.
              <div style={{ marginTop: 14 }}>
                <button className="btn btn-primary" onClick={() => onUploadNew?.("SOV")}>Upload SoV</button>
              </div>
            </div>
          </div>
        </div>
      </>
    );
  }

  const pickBand = (id) => setBandFilter((f) => (f === id ? "all" : id));

  // ---- Dedicated full-page block detail (shown when a row is clicked) ----
  if (selected) {
    const overall = blockOverallBand(selected);
    const { street, postcode } = blockDisplayAddress(selected);
    return (
      <>
        <div className="main-head">
          <div>
            <button type="button" className="ba-back" onClick={() => setSelectedId(null)}>
              ← Back to blocks
            </button>
            <div className="page-title" style={{ marginTop: 6 }}>{street}</div>
            <div className="page-sub">
              Block {selected.name}
              {postcode ? ` · ${postcode}` : ""}
              {selected.parent_uprn ? ` · UPRN ${selected.parent_uprn}` : ""}
            </div>
          </div>
          <span className={`pill ${bandClass(overall)}`} style={{ fontSize: 13, padding: "8px 14px" }}>
            {bandVerdict(overall)}
          </span>
        </div>
        <div className="content-wrap">
          <Dossier block={selected} />
        </div>
      </>
    );
  }

  return (
    <>
      <div className="main-head">
        <div>
          <div className="page-title">Block Analysis</div>
          <div className="page-sub">Every block with address, size, UPRN and FRA / FRAEW fire-risk banding. Click a row for the full risk profile.</div>
        </div>
        <span className="pill pill-muted">{blocks.length} blocks</span>
      </div>

      <div className="content-wrap">
        {/* Block list */}
        <div className="card">
          <div className="card-body">
            <div className="ba-toolbar">
              <div className="ba-search">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round">
                  <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <input className="input" type="text" placeholder="Search by street, postcode or block…" value={query} onChange={(e) => setQuery(e.target.value)} />
              </div>
              <div className="ba-stats">
                <StatChip label="All" active={bandFilter === "all"} count={counts.all} onClick={() => pickBand("all")} />
                <StatChip label="High risk" band="Red" active={bandFilter === "Red"} count={counts.Red} onClick={() => pickBand("Red")} />
                <StatChip label="Medium risk" band="Amber" active={bandFilter === "Amber"} count={counts.Amber} onClick={() => pickBand("Amber")} />
                <StatChip label="Low risk" band="Green" active={bandFilter === "Green"} count={counts.Green} onClick={() => pickBand("Green")} />
                <StatChip label="Unrated" active={bandFilter === "none"} count={counts.none} onClick={() => pickBand("none")} />
              </div>
            </div>
          </div>

          <div className="ba-meta">
            {visible.length} {visible.length === 1 ? "block" : "blocks"}
            {query ? ` matching “${query}”` : ""}
            {bandFilter !== "all" ? ` · ${bandFilter === "none" ? "unrated" : bandFilter} only` : ""}
            {sort.key ? ` · sorted by ${sort.key} (${sort.dir})` : " · sorted by risk"}
          </div>

          {visible.length === 0 ? (
            <div className="card-body"><div className="muted">No blocks match your search or filters.</div></div>
          ) : (
            <BlockTable blocks={visible} selectedId={null} onSelect={setSelectedId} sort={sort} onSort={toggleSort} />
          )}
        </div>
      </div>
    </>
  );
}
