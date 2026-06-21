import React, { useMemo } from "react";

/* ========================= HELPERS ========================= */

const fmt = (n, digits = 2) => {
  const x = Number(n);
  return Number.isFinite(x) ? x.toFixed(digits) : "—";
};

const fmtMoney = (n, digits = 0) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  return `£${x.toLocaleString("en-GB", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })}`;
};

const toNumberOrNull = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const isPresent = (value) => {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "boolean") return true;
  if (Array.isArray(value)) return value.length > 0;
  return true;
};

const asArray = (value) => {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value === "string") return value.trim() ? [value.trim()] : [];
  return [value];
};

const truncate = (value, maxLength = 140) => {
  const text = String(value ?? "").trim();
  if (!text) return "—";
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
};

const bandMeta = (bandOrScore) => {
  const text = String(bandOrScore ?? "").toLowerCase();

  if (
    text.includes("green") ||
    text.includes("low risk") ||
    text.includes("low") ||
    text.includes("acceptable") ||
    text.includes("broadly acceptable")
  ) {
    return { label: "Low Risk", cls: "band-green" };
  }
  if (
    text.includes("amber") ||
    text.includes("yellow") ||
    text.includes("medium") ||
    text.includes("moderate") ||
    text.includes("tolerable")
  ) {
    return { label: "Medium Risk", cls: "band-yellow" };
  }
  if (
    text.includes("red") ||
    text.includes("high risk") ||
    text.includes("high") ||
    text.includes("intolerable") ||
    text.includes("not acceptable")
  ) {
    return { label: "High Risk", cls: "band-red" };
  }

  const numeric = Number(bandOrScore);
  if (Number.isFinite(numeric)) {
    if (numeric >= 80) return { label: "Low Risk", cls: "band-green" };
    if (numeric >= 50) return { label: "Medium Risk", cls: "band-yellow" };
    return { label: "High Risk", cls: "band-red" };
  }

  return { label: "Unknown", cls: "band-muted" };
};

const getDisplayAddress = (property) => {
  const line1 =
    property?.address_line_1 ??
    property?.address1 ??
    property?.address ??
    property?.property_address ??
    "—";

  const line2 =
    property?.address_line_2 ??
    property?.address2 ??
    property?.address_2 ??
    "";

  const city =
    property?.city ??
    property?.town ??
    property?.locality ??
    property?.address_3 ??
    "";

  const postcode =
    property?.post_code ??
    property?.postcode ??
    property?.zip ??
    "";

  return { line1, line2, city, postcode };
};

const getLatLon = (property) => {
  const directLat =
    toNumberOrNull(property?.latitude) ??
    toNumberOrNull(property?.lat) ??
    toNumberOrNull(property?.__lat);

  const directLon =
    toNumberOrNull(property?.longitude) ??
    toNumberOrNull(property?.lon) ??
    toNumberOrNull(property?.lng) ??
    toNumberOrNull(property?.__lon);

  const fallbackY =
    toNumberOrNull(property?.y_coordinate) ??
    toNumberOrNull(property?.y);

  const fallbackX =
    toNumberOrNull(property?.x_coordinate) ??
    toNumberOrNull(property?.x);

  const lat = directLat ?? fallbackY;
  const lon = directLon ?? fallbackX;

  const validLat = Number.isFinite(lat) && lat !== 0;
  const validLon = Number.isFinite(lon) && lon !== 0;

  return {
    lat: validLat ? lat : null,
    lon: validLon ? lon : null,
  };
};

const getSovValues = (property) => {
  return {
    sumInsured:
      toNumberOrNull(property?.sum_insured) ??
      toNumberOrNull(property?.sumInsured) ??
      toNumberOrNull(property?.total_sum_insured) ??
      toNumberOrNull(property?.tiv),

    propertyType:
      property?.property_type ??
      property?.propertyType ??
      property?.type ??
      "—",

    occupancy:
      property?.occupancy_type ??
      property?.occupancyType ??
      property?.occupancy ??
      "—",

    height:
      toNumberOrNull(property?.height_m) ??
      toNumberOrNull(property?.height) ??
      toNumberOrNull(property?.height_max_m) ??
      toNumberOrNull(property?.building_height_m),

    storeys:
      toNumberOrNull(property?.storeys) ??
      toNumberOrNull(property?.max_storeys),

    units:
      toNumberOrNull(property?.units) ??
      toNumberOrNull(property?.unit_count) ??
      toNumberOrNull(property?.number_of_flats),

    yearBuilt:
      toNumberOrNull(property?.year_of_build) ??
      toNumberOrNull(property?.year_built),
  };
};

const normaliseFireDoc = (doc, type) => {
  if (!doc) return null;

  const raw = doc.raw && typeof doc.raw === "object" ? doc.raw : {};
  const merged = { ...raw, ...doc };

  return {
    ...merged,
    document_type: String(merged.document_type ?? type ?? "").toUpperCase(),
    risk_level:
      merged.risk_level ??
      merged.rag_status ??
      merged.raw_rating ??
      merged.overall_risk_rating ??
      merged.risk_rating ??
      merged.external_wall_risk ??
      merged.building_risk_rating ??
      null,
    summary:
      merged.summary ??
      merged.executive_summary ??
      merged.overview ??
      merged.findings_summary ??
      merged.significant_findings_summary ??
      "",
    recommendations:
      merged.recommendations ??
      merged.actions ??
      merged.action_items ??
      merged.remedial_actions ??
      merged.significant_findings ??
      [],
    feature_id: merged.feature_id ?? merged.id ?? merged.document_id ?? null,
    upload_id: merged.upload_id ?? null,
    filename: merged.filename ?? merged.source_filename ?? "Uploaded PDF",
  };
};

const getFireAssessment = (source) => {
  const fra = normaliseFireDoc(
    source?.latest_fra ??
      source?.fire_documents?.fra ??
      source?.fire_documents?.FRA ??
      source?.fra ??
      null,
    "FRA"
  );

  const fraew = normaliseFireDoc(
    source?.latest_fraew ??
      source?.fire_documents?.fraew ??
      source?.fire_documents?.FRAEW ??
      source?.fraew ??
      null,
    "FRAEW"
  );

  const all = [
    ...asArray(source?.fire_documents?.all),
    ...asArray(source?.fire_documents?.documents),
    ...asArray(source?.fire_documents),
  ]
    .filter((item) => typeof item === "object" && item !== null)
    .map((item) => normaliseFireDoc(item, item.document_type));

  return {
    fra,
    fraew,
    all,
    hasAny: Boolean(fra || fraew || all.length),
  };
};

const normaliseBooleanLabel = (value, yes = "Yes", no = "No") => {
  if (value === true) return yes;
  if (value === false) return no;
  if (typeof value === "string") {
    const lower = value.trim().toLowerCase();
    if (["true", "yes", "y", "1", "required", "present"].includes(lower)) return yes;
    if (["false", "no", "n", "0", "not required", "absent"].includes(lower)) return no;
  }
  return "—";
};

const normaliseFraActions = (fra) => {
  const actions = asArray(fra?.recommendations ?? fra?.actions ?? fra?.action_items);

  return {
    total: fra?.total_actions ?? fra?.total_action_count ?? (actions.length || "—"),
    overdue: fra?.overdue_actions ?? fra?.overdue_action_count ?? "—",
    outstanding:
      fra?.outstanding_actions ?? fra?.outstanding_action_count ?? "—",
    items: actions,
  };
};

const getFraewHeight = (fraew) =>
  toNumberOrNull(fraew?.building_height_m) ??
  toNumberOrNull(fraew?.building_height) ??
  toNumberOrNull(fraew?.height_m);

/* ========================= UI COMPONENTS ========================= */

function DetailRow({ label, value }) {
  return (
    <div className="details-sub" style={{ marginTop: 6 }}>
      <b>{label}:</b> {isPresent(value) ? value : "—"}
    </div>
  );
}

function KeyValueCard({ label, value }) {
  return (
    <div className="kv">
      <div className="kv-k">{label}</div>
      <div className="kv-v">{isPresent(value) ? value : "—"}</div>
    </div>
  );
}

function BulletList({ items, max = 5 }) {
  const safeItems = asArray(items);
  if (!safeItems.length) return null;

  return (
    <ul style={{ margin: "8px 0 0 18px", padding: 0 }}>
      {safeItems.slice(0, max).map((item, index) => (
        <li key={`${String(item).slice(0, 20)}-${index}`} style={{ marginBottom: 4 }}>
          {truncate(item, 180)}
        </li>
      ))}
    </ul>
  );
}

// ✓ / ✕ chip for boolean facts. hazard=true => "present" is bad (red), else good (green).
function Chip({ label, value, hazard = false }) {
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

function ChipRow({ children }) {
  return <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>{children}</div>;
}

function MiniStat({ label, value, tone = "default" }) {
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

function MeasureHead({ children }) {
  return <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--muted)", margin: "14px 0 2px" }}>{children}</div>;
}

const prettyText = (s) =>
  isPresent(s) ? String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "—";

// Renders label/value facts as a responsive grid of small cells (instead of stacked lines).
function FactGrid({ items }) {
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

// Worse of the FRA / FRAEW band, for the block-level overall badge.
const worstBandMeta = (fra, fraew) => {
  const rank = { "band-red": 3, "band-amber": 2, "band-yellow": 2, "band-green": 1, "band-muted": 0 };
  const a = bandMeta(fra?.risk_level ?? fra?.rag_status ?? fra?.raw_rating);
  const b = bandMeta(fraew?.risk_level ?? fraew?.rag_status ?? fraew?.raw_rating ?? fraew?.building_risk_rating);
  return (rank[a.cls] ?? 0) >= (rank[b.cls] ?? 0) ? a : b;
};

function FireRiskSection({
  fra,
  fraew,
  emptyLabel = "No FRA / FRAEW data linked.",
}) {
  const fraMeta = bandMeta(
    fra?.risk_level ?? fra?.rag_status ?? fra?.raw_rating
  );
  const fraewMeta = bandMeta(
    fraew?.risk_level ?? fraew?.rag_status ?? fraew?.raw_rating
  );
  const fraActions = normaliseFraActions(fra);
  const fraewRecommendations = asArray(
    fraew?.recommendations ?? fraew?.actions ?? fraew?.remedial_actions
  );
  const fraewHeight = getFraewHeight(fraew);

  return (
    <div className="details-block">
      <div className="details-h">Fire Risk Assessment (FRA / FRAEW)</div>

      {!fra && !fraew && <div className="muted">{emptyLabel}</div>}

      {(fra || fraew) && (
        <div
          style={{
            display: "grid",
            gap: 12,
          }}
        >
          {fra && (
            <div
              style={{
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: 12,
                padding: 12,
                background: "#fff",
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  flexWrap: "wrap",
                  marginBottom: 8,
                }}
              >
                <span className={`pill ${fraMeta.cls}`}>{fraMeta.label}</span>
                <span className="pill pill-muted">FRA</span>
                {fra.extraction_confidence ? (
                  <span className="pill pill-muted">
                    confidence {fmt(fra.extraction_confidence, 2)}
                  </span>
                ) : null}
              </div>

              <FactGrid
                items={[
                  { label: "Risk", value: fra?.risk_level ?? fra?.rag_status ?? fra?.raw_rating },
                  { label: "Assessment date", value: fra?.assessment_date },
                  { label: "Valid until", value: fra?.assessment_valid_until },
                  { label: "Next review", value: fra?.next_review_date },
                  { label: "In date", value: normaliseBooleanLabel(fra?.is_in_date) },
                  { label: "Assessor", value: fra?.assessor_name },
                  { label: "Company", value: fra?.assessor_company },
                  { label: "Responsible person", value: fra?.responsible_person },
                  { label: "Evacuation", value: fra?.evacuation_strategy ? prettyText(fra.evacuation_strategy) : null },
                ]}
              />
              <MeasureHead>Fire safety measures</MeasureHead>
              <ChipRow>
                <Chip label="Sprinklers" value={fra?.has_sprinkler_system ?? fra?.sprinkler_system} />
                <Chip label="Smoke detection" value={fra?.has_smoke_detection ?? fra?.smoke_detection} />
                <Chip label="Fire alarm" value={fra?.has_fire_alarm_system ?? fra?.fire_alarm_system} />
                <Chip label="Fire doors" value={fra?.has_fire_doors ?? fra?.fire_doors} />
                <Chip label="Compartmentation" value={fra?.has_compartmentation ?? fra?.compartmentation} />
              </ChipRow>

              <MeasureHead>Remedial actions</MeasureHead>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
                <MiniStat label="Total" value={fraActions.total} />
                <MiniStat label="Overdue" value={fraActions.overdue} tone={Number(fraActions.overdue) > 0 ? "red" : "default"} />
                <MiniStat label="Outstanding" value={fraActions.outstanding} tone={Number(fraActions.outstanding) > 0 ? "amber" : "default"} />
              </div>

              {fra.summary ? (
                <div className="details-sub" style={{ marginTop: 10 }}>
                  <b>Summary:</b> {truncate(fra.summary, 240)}
                </div>
              ) : null}

              <BulletList items={fraActions.items} />
            </div>
          )}

          {fraew && (
            <div
              style={{
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: 12,
                padding: 12,
                background: "#fff",
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  flexWrap: "wrap",
                  marginBottom: 8,
                }}
              >
                <span className={`pill ${fraewMeta.cls}`}>{fraewMeta.label}</span>
                <span className="pill pill-muted">FRAEW</span>
                {fraew.extraction_confidence ? (
                  <span className="pill pill-muted">
                    confidence {fmt(fraew.extraction_confidence, 2)}
                  </span>
                ) : null}
              </div>

              <FactGrid
                items={[
                  { label: "Risk", value: fraew?.risk_level ?? fraew?.rag_status ?? fraew?.raw_rating },
                  { label: "External wall risk", value: fraew?.external_wall_risk ?? fraew?.building_risk_rating },
                  { label: "Assessment date", value: fraew?.assessment_date },
                  { label: "Valid until", value: fraew?.assessment_valid_until },
                  { label: "In date", value: normaliseBooleanLabel(fraew?.is_in_date) },
                  { label: "Height", value: Number.isFinite(fraewHeight) ? `${fmt(fraewHeight, 1)} m` : "—" },
                  { label: "Height category", value: fraew?.building_height_category ? String(fraew.building_height_category).replace(/_/g, " ") : null },
                  { label: "Storeys", value: fraew?.num_storeys },
                  { label: "Units", value: fraew?.num_units },
                  { label: "Cladding type", value: fraew?.cladding_type },
                  {
                    label: "Wall types",
                    value: (() => {
                      let wt = fraew?.wall_types;
                      if (typeof wt === "string") { try { wt = JSON.parse(wt); } catch { return wt; } }
                      if (!Array.isArray(wt) || wt.length === 0) return "—";
                      return wt.map((w) => w?.type_ref ?? w).filter(Boolean).join(", ");
                    })(),
                  },
                ]}
              />
              <MeasureHead>Cladding & protections</MeasureHead>
              <ChipRow>
                <Chip label="Combustible cladding" value={fraew?.has_combustible_cladding ?? fraew?.combustible_cladding} hazard />
                <Chip label="Cavity barriers" value={fraew?.cavity_barriers_present} />
                <Chip label="PAS 9980 compliant" value={fraew?.pas_9980_compliant} />
                <Chip label="Dry riser" value={fraew?.dry_riser_present} />
                <Chip label="Wet riser" value={fraew?.wet_riser_present} />
              </ChipRow>
              <FactGrid
                items={[
                  { label: "PAS 9980 version", value: fraew?.pas_9980_version },
                  { label: "Interim measures", value: normaliseBooleanLabel(fraew?.interim_measures_required, "Required", "Not required") },
                  { label: "Interim detail", value: fraew?.interim_measures_detail },
                  { label: "Remediation required", value: normaliseBooleanLabel(fraew?.remediation_required ?? fraew?.has_remedial_actions) },
                  { label: "Evacuation", value: fraew?.evacuation_strategy ? prettyText(fraew.evacuation_strategy) : null },
                  { label: "ADB compliant", value: fraew?.adb_compliant ? prettyText(fraew.adb_compliant) : null },
                ]}
              />

              {fraew.summary ? (
                <div className="details-sub" style={{ marginTop: 10 }}>
                  <b>Summary:</b> {truncate(fraew.summary, 240)}
                </div>
              ) : null}

              <BulletList items={fraewRecommendations} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function BlockPropertiesTable({ properties = [], onSelectProperty }) {
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

/* ===================== EMPTY STATE ====================== */

function EmptyDetailsState() {
  const numStep = (n, text) => (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
      <span
        style={{
          flexShrink: 0,
          width: 26,
          height: 26,
          borderRadius: 999,
          background: "rgba(184,86,75,0.12)",
          color: "var(--terracotta-2, #9A463D)",
          fontSize: 12,
          fontWeight: 700,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {n}
      </span>
      <span style={{ fontSize: 14, color: "var(--text, #1E3246)", lineHeight: 1.55 }}>{text}</span>
    </div>
  );

  const legendRow = (color, label, count) => (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <span
        style={{
          flexShrink: 0,
          width: 30,
          height: 30,
          borderRadius: 999,
          background: "#fff",
          color: "var(--navy, #1E3246)",
          fontSize: 12,
          fontWeight: 700,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: `2.5px solid ${color}`,
          boxSizing: "border-box",
        }}
      >
        {count}
      </span>
      <span style={{ fontSize: 13, color: "var(--muted, #6B6560)", whiteSpace: "nowrap" }}>{label}</span>
    </div>
  );

  const infoItem = (icon, label) => (
    <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
      <span
        style={{
          flexShrink: 0,
          width: 32,
          height: 32,
          borderRadius: 9,
          background: "rgba(184,86,75,0.10)",
          color: "var(--terracotta-2, #9A463D)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {icon}
      </span>
      <span style={{ fontSize: 13.5, color: "var(--text, #1E3246)" }}>{label}</span>
    </div>
  );

  const ic = (children) => (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", justifyContent: "space-between", gap: 26, padding: "32px 16px 32px" }}>
      <div>
        <div className="tag" style={{ marginBottom: 16 }}>How to explore</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {numStep("1", "Click a block on the map for its summary.")}
          {numStep("2", "Click the same block again to list every flat inside it.")}
        </div>
      </div>

      <div>
        <div className="tag" style={{ marginBottom: 16 }}>What each summary shows</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "18px 10px" }}>
          {infoItem(ic(<><path d="M18 7c0-5.333-8-5.333-8 0" /><path d="M10 7v14" /><path d="M6 21h12" /><path d="M6 13h10" /></>), "Insured value")}
          {infoItem(ic(<><path d="M12 3v18" /><path d="m8 7 4-4 4 4" /><path d="m8 17 4 4 4-4" /></>), "Height & storeys")}
          {infoItem(ic(<><path d="M3 9.5 12 3l9 6.5" /><path d="M5 10v10h14V10" /></>), "Flats in the block")}
          {infoItem(ic(<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />), "FRA fire risk")}
          {infoItem(ic(<><rect x="3" y="4" width="18" height="16" rx="1" /><path d="M3 9h18M3 14h18M8 4v5m8-5v5m-4 5v6m-4-6h8" /></>), "FRAEW wall risk")}
          {infoItem(ic(<><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z" /><circle cx="12" cy="10" r="3" /></>), "Location & UPRN")}
          {infoItem(ic(<><path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 1.3 0 1.9-.5 2.5-1" /><path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 1.3 0 1.9-.5 2.5-1" /><path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 1.3 0 1.9-.5 2.5-1" /></>), "Flood risk score")}
          {infoItem(ic(<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="m9 12 2 2 4-4" /></>), "UPRN match confidence")}
          {infoItem(ic(<><path d="m12.8 2.2a2 2 0 0 0-1.6 0L2.6 6.1a1 1 0 0 0 0 1.8l8.6 3.9a2 2 0 0 0 1.6 0l8.6-3.9a1 1 0 0 0 0-1.8Z" /><path d="m22 17.7-9.2 4.1a2 2 0 0 1-1.6 0L2 17.7" /><path d="m22 12.7-9.2 4.1a2 2 0 0 1-1.6 0L2 12.7" /></>), "Construction materials")}
        </div>
      </div>

      <div style={{ background: "var(--warm-bg-2, #F3EFE8)", border: "1px solid var(--border-line, #DED7CC)", borderRadius: 12, padding: "20px 22px" }}>
        <div className="tag" style={{ marginBottom: 18 }}>Map legend</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "14px 12px" }}>
          {legendRow("#ef4444", "High risk", 8)}
          {legendRow("#f59e0b", "Medium risk", 12)}
          {legendRow("#22c55e", "Low risk", 9)}
          {legendRow("#64748b", "No evidence", 10)}
        </div>
        <p style={{ margin: "16px 0 0", fontSize: 13, color: "var(--muted, #6B6560)", lineHeight: 1.55 }}>
          Marker colour reflects the worst FRA / FRAEW rating linked to the block.
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--border-line, #DED7CC)" }}>
          <span
            style={{
              flexShrink: 0,
              width: 30,
              height: 30,
              borderRadius: 999,
              background: "#fff",
              color: "var(--navy, #1E3246)",
              fontSize: 12,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "2.5px solid #64748b",
              boxSizing: "border-box",
            }}
          >
            12
          </span>
          <span style={{ fontSize: 13, color: "var(--muted, #6B6560)", lineHeight: 1.55 }}>
            Each circle is a block; the number shows how many flats it contains.
          </span>
        </div>
      </div>
    </div>
  );
}

/* ========================= MAIN ========================= */

export default function PropertyDetails({
  property,
  selectedBlock = null,
  blockMode = false,
  onSelectProperty,
}) {
  const activeSource = property || selectedBlock || {};

  const { line1, line2, city, postcode } = useMemo(
    () => getDisplayAddress(property || {}),
    [property]
  );

  const { lat, lon } = useMemo(() => getLatLon(activeSource), [activeSource]);

  const sov = useMemo(() => getSovValues(property || {}), [property]);

  const propertyFire = useMemo(() => getFireAssessment(property), [property]);
  const blockFire = useMemo(() => getFireAssessment(selectedBlock), [selectedBlock]);

  if (!property && !blockMode) {
    return <EmptyDetailsState />;
  }

  if (blockMode && selectedBlock && !property) {
    const rep = selectedBlock.representativeProperty;
    const rawAddr = rep?.address_line_1 || rep?.address || "";
    const blockAddr = rawAddr.replace(/^(flat|apartment|unit|apt)[^,]*,\s*/i, "").trim();
    const blockPostcode = rep?.post_code || rep?.postcode || "";
    const blockAddrDisplay = [blockAddr, blockPostcode].filter(Boolean).join(", ") || selectedBlock.name || selectedBlock.label;
    const blockOverall = worstBandMeta(blockFire.fra, blockFire.fraew);

    return (
      <div className="details-body">
        <div className="details-block">
          <div className="row-between" style={{ alignItems: "flex-start", gap: 8 }}>
            <div style={{ fontSize: 16, fontWeight: 800, lineHeight: 1.25, letterSpacing: "-0.01em" }}>{blockAddrDisplay}</div>
            <span className={`pill ${blockOverall.cls}`} style={{ whiteSpace: "nowrap" }}>{blockOverall.label}</span>
          </div>
          <div className="details-sub" style={{ marginTop: 3 }}>
            Block {selectedBlock.block_reference || selectedBlock.name}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 12 }}>
            <MiniStat
              label="Total insured"
              value={
                isPresent(selectedBlock.totalValue)
                  ? fmtMoney(selectedBlock.totalValue)
                  : isPresent(selectedBlock.total_sum_insured)
                  ? fmtMoney(selectedBlock.total_sum_insured)
                  : "—"
              }
            />
            <MiniStat label="Properties" value={selectedBlock.count ?? selectedBlock.unit_count} />
            <MiniStat
              label="Max height"
              value={
                Number.isFinite(Number(selectedBlock.maxHeight)) && Number(selectedBlock.maxHeight) > 0
                  ? `${fmt(selectedBlock.maxHeight, 1)} m`
                  : Number.isFinite(Number(selectedBlock.max_storeys))
                  ? `${selectedBlock.max_storeys} st.`
                  : "—"
              }
            />
            <MiniStat label="UPRN" value={isPresent(selectedBlock.parent_uprn) ? selectedBlock.parent_uprn : "—"} />
          </div>

          {Number.isFinite(lat) && Number.isFinite(lon) ? (
            <div className="details-sub" style={{ marginTop: 10 }}>Coordinates: {fmt(lat, 5)}, {fmt(lon, 5)}</div>
          ) : null}
        </div>

        <FireRiskSection
          fra={blockFire.fra}
          fraew={blockFire.fraew}
          emptyLabel="No FRA / FRAEW data linked to this block."
        />

        <BlockPropertiesTable properties={selectedBlock.properties || []} onSelectProperty={onSelectProperty} />
      </div>
    );
  }

  if (!property) {
    return <EmptyDetailsState />;
  }

  return (
    <div className="details-body">
      <div className="details-block">
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
          <div className="details-h" style={{ marginBottom: 0 }}>
            {[line1, line2].filter(Boolean).join(" ") || "—"}
          </div>
          {selectedBlock && (
            <button
              onClick={() => onSelectProperty?.(null)}
              style={{
                flexShrink: 0,
                fontSize: 12,
                padding: "3px 10px",
                borderRadius: 6,
                border: "1px solid var(--border, #e2e8f0)",
                background: "var(--panel, #fff)",
                color: "var(--text-light, #64748b)",
                cursor: "pointer",
                fontWeight: 500,
              }}
            >
              ← Block view
            </button>
          )}
        </div>

        <DetailRow
          label="Property ref"
          value={property?.property_reference ?? property?.propertyReference ?? property?.id}
        />
        <DetailRow label="Property ID" value={property?.property_id ?? property?.propertyId} />
        <DetailRow
          label="Block"
          value={
            property?.block_reference ??
            selectedBlock?.label ??
            selectedBlock?.name ??
            selectedBlock?.block_reference
          }
        />
      </div>

      <div className="details-block">
        <div className="details-h">SOV</div>

        <div className="kv-grid">
          <KeyValueCard
            label="Sum insured"
            value={Number.isFinite(sov.sumInsured) ? fmtMoney(sov.sumInsured) : "—"}
          />
          <KeyValueCard label="Property type" value={sov.propertyType} />
          <KeyValueCard label="Occupancy" value={sov.occupancy} />
          <KeyValueCard
            label="Height"
            value={Number.isFinite(sov.height) ? `${fmt(sov.height, 1)} m` : "—"}
          />
          <KeyValueCard
            label="Storeys"
            value={Number.isFinite(sov.storeys) ? sov.storeys : "—"}
          />
          <KeyValueCard
            label="Year built"
            value={Number.isFinite(sov.yearBuilt) ? sov.yearBuilt : "—"}
          />
          <KeyValueCard label="UPRN" value={property?.uprn ?? property?.UPRN} />
          <KeyValueCard label="Parent UPRN" value={property?.parent_uprn} />
          {isPresent(property?.flood_risk_band) ? (
            <KeyValueCard label="Flood risk" value={property.flood_risk_band} />
          ) : null}
        </div>
      </div>

      <FireRiskSection
        fra={propertyFire.fra}
        fraew={propertyFire.fraew}
        emptyLabel="No FRA / FRAEW data linked to this property."
      />
    </div>
  );
}
