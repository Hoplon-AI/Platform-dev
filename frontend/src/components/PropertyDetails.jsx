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
  return true;
};

const bandMeta = (bandOrScore) => {
  const text = String(bandOrScore ?? "").toLowerCase();

  if (
    text.includes("green") ||
    text.includes("low risk") ||
    text.includes("acceptable") ||
    text.includes("broadly acceptable")
  ) {
    return { label: "Low Risk", cls: "band-green" };
  }
  if (
    text.includes("amber") ||
    text.includes("medium") ||
    text.includes("moderate") ||
    text.includes("tolerable")
  ) {
    return { label: "Medium Risk", cls: "band-yellow" };
  }
  if (
    text.includes("red") ||
    text.includes("high risk") ||
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

const getFireAssessment = (source) => {
  const fra =
    source?.latest_fra ??
    source?.fire_documents?.fra ??
    source?.fra ??
    null;

  const fraew =
    source?.latest_fraew ??
    source?.fire_documents?.fraew ??
    source?.fraew ??
    null;

  return {
    fra,
    fraew,
    hasAny: Boolean(fra || fraew),
  };
};

const normaliseBooleanLabel = (value, yes = "Yes", no = "No") => {
  if (value === true) return yes;
  if (value === false) return no;
  return "—";
};

const normaliseFraActions = (fra) => {
  return {
    total: fra?.total_actions ?? fra?.total_action_count ?? "—",
    overdue: fra?.overdue_actions ?? fra?.overdue_action_count ?? "—",
    outstanding:
      fra?.outstanding_actions ?? fra?.outstanding_action_count ?? "—",
  };
};

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
              </div>

              <DetailRow
                label="Risk"
                value={fra?.risk_level ?? fra?.rag_status ?? fra?.raw_rating}
              />
              <DetailRow label="Assessment date" value={fra?.assessment_date} />
              <DetailRow label="Valid until" value={fra?.assessment_valid_until} />
              <DetailRow
                label="In date"
                value={normaliseBooleanLabel(fra?.is_in_date)}
              />
              <DetailRow label="Assessor" value={fra?.assessor_name} />
              <DetailRow label="Company" value={fra?.assessor_company} />
              <DetailRow label="Evacuation" value={fra?.evacuation_strategy} />
              <DetailRow label="Total actions" value={fraActions.total} />
              <DetailRow label="Overdue actions" value={fraActions.overdue} />
              <DetailRow label="Outstanding actions" value={fraActions.outstanding} />
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
              </div>

              <DetailRow
                label="Risk"
                value={fraew?.risk_level ?? fraew?.rag_status ?? fraew?.raw_rating}
              />
              <DetailRow label="Assessment date" value={fraew?.assessment_date} />
              <DetailRow label="Valid until" value={fraew?.assessment_valid_until} />
              <DetailRow
                label="In date"
                value={normaliseBooleanLabel(fraew?.is_in_date)}
              />
              <DetailRow
                label="Height"
                value={
                  Number.isFinite(Number(fraew?.building_height_m))
                    ? `${Number(fraew.building_height_m).toFixed(1)} m`
                    : "—"
                }
              />
              <DetailRow
                label="Combustible cladding"
                value={normaliseBooleanLabel(
                  fraew?.combustible_cladding ?? fraew?.has_combustible_cladding
                )}
              />
              <DetailRow
                label="PAS 9980 compliant"
                value={normaliseBooleanLabel(fraew?.pas_9980_compliant)}
              />
              <DetailRow
                label="Interim measures"
                value={normaliseBooleanLabel(
                  fraew?.interim_measures_required,
                  "Required",
                  "Not required"
                )}
              />
              <DetailRow
                label="Remediation required"
                value={normaliseBooleanLabel(
                  fraew?.remediation_required ?? fraew?.has_remedial_actions
                )}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function BlockPropertiesTable({ properties = [] }) {
  if (!properties.length) {
    return <div className="muted">No linked properties found for this block.</div>;
  }

  return (
    <div className="details-block">
      <div className="details-h">Contained properties</div>

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
            </tr>
          </thead>
          <tbody>
            {properties.map((item, index) => (
              <tr key={item.id || item.property_id || item.uprn || index}>
                <td>
                  {item.address_line_1 ||
                    item.property_reference ||
                    item.id ||
                    `Property ${index + 1}`}
                </td>
                <td>{item.uprn || "—"}</td>
                <td>{fmtMoney(item.sum_insured)}</td>
              </tr>
            ))}
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
      <div className="details-body">
        <div className="muted">Select a property to view details.</div>
      </div>
    );
  }

  if (blockMode && selectedBlock && !property) {
    return (
      <div className="details-body">
        <div className="details-block">
          <div className="details-h">Block</div>
          <div className="details-title">
            {selectedBlock.label || selectedBlock.name || "Unnamed block"}
          </div>

          <DetailRow label="Block reference" value={selectedBlock.block_reference} />
          <DetailRow label="Parent UPRN" value={selectedBlock.parent_uprn} />
          <DetailRow
            label="Properties"
            value={selectedBlock.count ?? selectedBlock.unit_count}
          />
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
            label="Average readiness"
            value={
              Number.isFinite(Number(selectedBlock.avgReadiness))
                ? `${Math.round(selectedBlock.avgReadiness)} / 100`
                : "—"
            }
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

        <BlockPropertiesTable properties={selectedBlock.properties || []} />
      </div>
    );
  }

  if (!property) {
    return (
      <div className="details-body">
        <div className="muted">No details available.</div>
      </div>
    );
  }

  return (
    <div className="details-body">
      <div className="details-block">
        <div className="details-h">Property</div>

        <div className="details-sub">
          {city || "—"} {postcode ? `· ${postcode}` : ""}
          {Number.isFinite(lat) && Number.isFinite(lon)
            ? ` · lat ${fmt(lat, 5)}, lon ${fmt(lon, 5)}`
            : " · no valid lat/lon"}
        </div>

        <div className="details-title">
          {line1 || "—"} {line2 || ""}
        </div>

        <DetailRow
          label="Property ref"
          value={property?.property_reference ?? property?.propertyReference ?? property?.id}
        />
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