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

              <DetailRow
                label="Risk"
                value={fra?.risk_level ?? fra?.rag_status ?? fra?.raw_rating}
              />
              <DetailRow label="Assessment date" value={fra?.assessment_date} />
              <DetailRow label="Valid until" value={fra?.assessment_valid_until} />
              <DetailRow label="Next review" value={fra?.next_review_date} />
              <DetailRow
                label="In date"
                value={normaliseBooleanLabel(fra?.is_in_date)}
              />
              <DetailRow label="Assessor" value={fra?.assessor_name} />
              <DetailRow label="Company" value={fra?.assessor_company} />
              <DetailRow label="Responsible person" value={fra?.responsible_person} />
              <DetailRow label="Evacuation" value={fra?.evacuation_strategy} />
              <DetailRow label="Fire doors" value={normaliseBooleanLabel(fra?.has_fire_doors ?? fra?.fire_doors)} />
              <DetailRow
                label="Compartmentation"
                value={normaliseBooleanLabel(fra?.has_compartmentation ?? fra?.compartmentation)}
              />
              <DetailRow
                label="Fire alarm"
                value={normaliseBooleanLabel(fra?.has_fire_alarm_system ?? fra?.fire_alarm_system)}
              />
              <DetailRow
                label="Smoke detection"
                value={normaliseBooleanLabel(fra?.has_smoke_detection ?? fra?.smoke_detection)}
              />
              <DetailRow
                label="Sprinklers"
                value={normaliseBooleanLabel(fra?.has_sprinkler_system ?? fra?.sprinkler_system)}
              />
              <DetailRow label="Total actions" value={fraActions.total} />
              <DetailRow label="Overdue actions" value={fraActions.overdue} />
              <DetailRow label="Outstanding actions" value={fraActions.outstanding} />

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

              <DetailRow
                label="Risk"
                value={fraew?.risk_level ?? fraew?.rag_status ?? fraew?.raw_rating}
              />
              <DetailRow
                label="External wall risk"
                value={fraew?.external_wall_risk ?? fraew?.building_risk_rating}
              />
              <DetailRow label="Assessment date" value={fraew?.assessment_date} />
              <DetailRow label="Valid until" value={fraew?.assessment_valid_until} />
              <DetailRow
                label="In date"
                value={normaliseBooleanLabel(fraew?.is_in_date)}
              />
              <DetailRow
                label="Height"
                value={Number.isFinite(fraewHeight) ? `${fmt(fraewHeight, 1)} m` : "—"}
              />
              <DetailRow label="Height category" value={fraew?.building_height_category} />
              <DetailRow label="Storeys" value={fraew?.num_storeys} />
              <DetailRow label="Units" value={fraew?.num_units} />
              <DetailRow label="Cladding type" value={fraew?.cladding_type} />
              <DetailRow
                label="Wall types"
                value={(() => {
                  let wt = fraew?.wall_types;
                  if (typeof wt === "string") { try { wt = JSON.parse(wt); } catch { return wt; } }
                  if (!Array.isArray(wt) || wt.length === 0) return "—";
                  return wt.map((w) => w?.type_ref ?? w).filter(Boolean).join(", ");
                })()}
              />
              <DetailRow
                label="Combustible cladding"
                value={normaliseBooleanLabel(
                  fraew?.combustible_cladding ?? fraew?.has_combustible_cladding
                )}
              />
              <DetailRow
                label="Cavity barriers"
                value={normaliseBooleanLabel(fraew?.cavity_barriers_present)}
              />
              <DetailRow
                label="PAS 9980 compliant"
                value={normaliseBooleanLabel(fraew?.pas_9980_compliant)}
              />
              <DetailRow label="PAS 9980 version" value={fraew?.pas_9980_version} />
              <DetailRow
                label="Interim measures"
                value={normaliseBooleanLabel(
                  fraew?.interim_measures_required,
                  "Required",
                  "Not required"
                )}
              />
              <DetailRow label="Interim detail" value={fraew?.interim_measures_detail} />
              <DetailRow
                label="Remediation required"
                value={normaliseBooleanLabel(
                  fraew?.remediation_required ?? fraew?.has_remedial_actions
                )}
              />
              <DetailRow
                label="Evacuation"
                value={fraew?.evacuation_strategy
                  ? fraew.evacuation_strategy.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
                  : "—"}
              />
              <DetailRow label="Dry riser" value={normaliseBooleanLabel(fraew?.dry_riser_present)} />
              <DetailRow label="Wet riser" value={normaliseBooleanLabel(fraew?.wet_riser_present)} />
              <DetailRow
                label="ADB compliant"
                value={fraew?.adb_compliant
                  ? fraew.adb_compliant.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
                  : "—"}
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
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10, backgroundColor: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.15)", borderRadius: 8, padding: "10px 12px" }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginTop: 2, flexShrink: 0 }}>
            <path d="M4 4l7 18 3-7 7-3z" />
          </svg>
          <p style={{ fontSize: 13, color: "#3b6fc4", margin: 0, lineHeight: 1.5 }}>
            Click any circle on the map to inspect a block's properties, value, height, and fire risk status.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10, backgroundColor: "rgba(148,163,184,0.07)", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 8, padding: "10px 12px" }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginTop: 2, flexShrink: 0 }}>
            <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
            <circle cx="3" cy="6" r="1" /><circle cx="3" cy="12" r="1" /><circle cx="3" cy="18" r="1" />
          </svg>
          <p style={{ fontSize: 13, color: "var(--text-light, #64748b)", margin: 0, lineHeight: 1.5 }}>
            Or search and click a block from the list in the summary above.
          </p>
        </div>
      </div>
    );
  }

  if (blockMode && selectedBlock && !property) {
    const rep = selectedBlock.representativeProperty;
    const rawAddr = rep?.address_line_1 || rep?.address || "";
    const blockAddr = rawAddr.replace(/^(flat|apartment|unit|apt)[^,]*,\s*/i, "").trim();
    const blockPostcode = rep?.post_code || rep?.postcode || "";
    const blockAddrDisplay = [blockAddr, blockPostcode].filter(Boolean).join(", ") || selectedBlock.name || selectedBlock.label;

    return (
      <div className="details-body">
        <div className="details-block">
          <div className="details-h">
            {blockAddrDisplay}
          </div>


          <DetailRow
            label="Total insured value"
            value={
              isPresent(selectedBlock.totalValue)
                ? fmtMoney(selectedBlock.totalValue)
                : isPresent(selectedBlock.total_sum_insured)
                ? fmtMoney(selectedBlock.total_sum_insured)
                : "—"
            }
          />
          <DetailRow
            label="Properties"
            value={selectedBlock.count ?? selectedBlock.unit_count}
          />
          <DetailRow
            label="Max height"
            value={
              Number.isFinite(Number(selectedBlock.maxHeight))
                ? `${fmt(selectedBlock.maxHeight, 1)} m`
                : Number.isFinite(Number(selectedBlock.max_storeys))
                ? selectedBlock.max_storeys
                : "—"
            }
          />
          <DetailRow label="Parent UPRN" value={selectedBlock.parent_uprn} />
          <DetailRow label="Block reference" value={selectedBlock.block_reference} />
          <DetailRow
            label="Coordinates"
            value={
              Number.isFinite(lat) && Number.isFinite(lon)
                ? `${fmt(lat, 5)}, ${fmt(lon, 5)}`
                : "—"
            }
          />
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
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10, backgroundColor: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.15)", borderRadius: 8, padding: "10px 12px" }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginTop: 2, flexShrink: 0 }}>
            <path d="M4 4l7 18 3-7 7-3z" />
          </svg>
          <p style={{ fontSize: 13, color: "#3b6fc4", margin: 0, lineHeight: 1.5 }}>
            Click any circle on the map to inspect a block's properties, value, height, and fire risk status.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10, backgroundColor: "rgba(148,163,184,0.07)", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 8, padding: "10px 12px" }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginTop: 2, flexShrink: 0 }}>
            <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
            <circle cx="3" cy="6" r="1" /><circle cx="3" cy="12" r="1" /><circle cx="3" cy="18" r="1" />
          </svg>
          <p style={{ fontSize: 13, color: "var(--text-light, #64748b)", margin: 0, lineHeight: 1.5 }}>
            Or search and click a block from the list in the summary above.
          </p>
        </div>
      </div>
    );
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
        <DetailRow label="UPRN" value={property?.uprn ?? property?.UPRN} />
        <DetailRow label="Parent UPRN" value={property?.parent_uprn} />
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
            label="Units / flats"
            value={Number.isFinite(sov.units) ? sov.units : "—"}
          />
          <KeyValueCard
            label="Year built"
            value={Number.isFinite(sov.yearBuilt) ? sov.yearBuilt : "—"}
          />
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
