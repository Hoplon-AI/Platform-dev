import React, { useMemo } from "react";

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

  if (text.includes("green") || text.includes("high")) {
    return { label: "Green", cls: "band-green" };
  }
  if (text.includes("amber") || text.includes("yellow") || text.includes("medium")) {
    return { label: "Amber", cls: "band-yellow" };
  }
  if (text.includes("red") || text.includes("low")) {
    return { label: "Red", cls: "band-red" };
  }

  const numeric = Number(bandOrScore);
  if (Number.isFinite(numeric)) {
    if (numeric >= 80) return { label: "Green", cls: "band-green" };
    if (numeric >= 50) return { label: "Amber", cls: "band-yellow" };
    return { label: "Red", cls: "band-red" };
  }

  return { label: "Unknown", cls: "band-muted" };
};

const getReadiness = (property) => {
  const score =
    toNumberOrNull(property?.readiness_score) ??
    toNumberOrNull(property?.readinessScore) ??
    toNumberOrNull(property?.score) ??
    null;

  const band =
    property?.readiness_band ??
    property?.readinessBand ??
    (Number.isFinite(score)
      ? score >= 80
        ? "Green"
        : score >= 50
        ? "Amber"
        : "Red"
      : "Unknown");

  const missing = Array.isArray(property?.missing_fields)
    ? property.missing_fields
    : Array.isArray(property?.missingFields)
    ? property.missingFields
    : Array.isArray(property?.validation?.missing_fields)
    ? property.validation.missing_fields
    : [];

  return { score, band, missing };
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

    wallConstruction:
      property?.wall_construction ?? "—",

    roofConstruction:
      property?.roof_construction ?? "—",

    builtForm:
      property?.built_form ?? "—",

    totalFloorArea:
      toNumberOrNull(property?.total_floor_area_m2),

    mainFuel:
      property?.main_fuel ?? "—",

    epcRating:
      property?.epc_rating ?? "—",

    epcPotentialRating:
      property?.epc_potential_rating ?? "—",

    epcLodgementDate:
      property?.epc_lodgement_date ?? "—",

    heightRoofbase:
      toNumberOrNull(property?.height_roofbase_m),

    heightConfidence:
      property?.height_confidence ?? "—",

    footprint:
      toNumberOrNull(property?.building_footprint_m2),
  };
};

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

function RawFieldsTableInline({ raw }) {
  const rows = useMemo(() => {
    if (!raw || typeof raw !== "object") return [];

    return Object.entries(raw)
      .filter(([key]) => !String(key).startsWith("__"))
      .map(([key, value]) => {
        let rendered = value;

        if (rendered === null || rendered === undefined || rendered === "") {
          rendered = "—";
        } else if (typeof rendered === "object") {
          try {
            rendered = JSON.stringify(rendered);
          } catch {
            rendered = String(rendered);
          }
        } else {
          rendered = String(rendered);
        }

        return { key, value: rendered };
      })
      .sort((a, b) => a.key.localeCompare(b.key));
  }, [raw]);

  if (!rows.length) {
    return <div className="muted">No raw fields available.</div>;
  }

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td className="td-key">{row.key}</td>
              <td style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {row.value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PropertyDetails({
  property,
  selectedBlock = null,
  blockMode = false,
  uprnResult = null,
  uprnLoading = false,
  uprnError = null,
}) {
  const readiness = useMemo(() => getReadiness(property), [property]);
  const readinessMeta = useMemo(
    () => bandMeta(readiness.band || readiness.score),
    [readiness]
  );

  const { lat, lon } = useMemo(() => getLatLon(property), [property]);
  const { line1, line2, city, postcode } = useMemo(
    () => getDisplayAddress(property),
    [property]
  );
  const sov = useMemo(() => getSovValues(property), [property]);

  const propertyReference =
    property?.property_reference ??
    property?.propertyReference ??
    property?.id ??
    null;

  const uprn =
    property?.uprn ??
    property?.UPRN ??
    null;

  const parentUprn =
    property?.parent_uprn ??
    null;

  const blockReference =
    property?.block_reference ??
    selectedBlock?.label ??
    selectedBlock?.name ??
    selectedBlock?.block_reference ??
    null;

  const uprnMatchScore =
    toNumberOrNull(property?.uprn_match_score) ??
    toNumberOrNull(property?.match_score);

  const uprnMatchDescription =
    property?.uprn_match_description ??
    property?.match_description ??
    "";

  const isListed =
    typeof property?.is_listed === "boolean"
      ? property.is_listed
      : property?.is_listed ?? null;

  const listedGrade = property?.listed_grade ?? null;
  const listedName = property?.listed_name ?? null;
  const listedReference = property?.listed_reference ?? null;
  const enrichmentStatus = property?.enrichment_status ?? null;
  const enrichmentSource = property?.enrichment_source ?? null;
  const enrichedAt = property?.enriched_at ?? null;
  const countryCode = property?.country_code ?? null;

  const bestUprn = uprnResult?.data?.best_match ?? uprnResult?.best_match ?? null;
  const uprnCandidates = uprnResult?.data?.candidates ?? uprnResult?.candidates ?? [];
  const uprnWarnings = uprnResult?.data?.warnings ?? uprnResult?.warnings ?? [];
  const uprnBestMeta = bandMeta(bestUprn?.confidence_band);

  if (!property && !blockMode) {
    return (
      <div className="details-body">
        <div className="muted">
          Click a property row or map marker to view SOV and geo-enrichment details here.
        </div>
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

          <DetailRow label="Parent UPRN" value={selectedBlock.parent_uprn} />
          <DetailRow label="Properties" value={selectedBlock.count ?? selectedBlock.unit_count} />
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
        </div>

        <div className="details-block">
          <div className="details-h">Geo analysis</div>
          <div className="muted">
            Select a property from the property table to inspect property-level SOV fields,
            enrichment fields, and raw uploaded values.
          </div>
        </div>
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

        {propertyReference && <DetailRow label="Property ref" value={propertyReference} />}
        {uprn && <DetailRow label="UPRN" value={uprn} />}
        {parentUprn && <DetailRow label="Parent UPRN" value={parentUprn} />}
        {blockReference && <DetailRow label="Block" value={blockReference} />}
        {countryCode && <DetailRow label="Country code" value={countryCode} />}

        {Number.isFinite(uprnMatchScore) && (
          <div className="details-sub" style={{ marginTop: 6 }}>
            <b>UPRN match score:</b> {fmt(uprnMatchScore, 2)}
            {uprnMatchDescription ? ` · ${uprnMatchDescription}` : ""}
          </div>
        )}
      </div>

      <div className="details-block">
        <div className="details-h">Readiness</div>

        <div className="readiness-row">
          <span className={`pill ${readinessMeta.cls}`}>
            {Number.isFinite(readiness.score)
              ? `${Math.round(readiness.score)} / 100`
              : "—"}{" "}
            ({readinessMeta.label})
          </span>
        </div>

        {readiness.missing.length > 0 ? (
          <div className="muted" style={{ marginTop: 8 }}>
            <b>Missing:</b> {readiness.missing.join(", ")}
          </div>
        ) : (
          <div className="muted" style={{ marginTop: 8 }}>
            No missing core fields detected.
          </div>
        )}
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
          <KeyValueCard label="Wall construction" value={sov.wallConstruction} />
          <KeyValueCard label="Roof construction" value={sov.roofConstruction} />
          <KeyValueCard label="Built form" value={sov.builtForm} />
          <KeyValueCard
            label="Floor area"
            value={Number.isFinite(sov.totalFloorArea) ? `${fmt(sov.totalFloorArea, 1)} m²` : "—"}
          />
          <KeyValueCard label="Main fuel" value={sov.mainFuel} />
        </div>
      </div>

      <div className="details-block">
        <div className="details-h">Enrichment</div>

        <div className="kv-grid">
          <KeyValueCard label="EPC rating" value={sov.epcRating} />
          <KeyValueCard label="EPC potential" value={sov.epcPotentialRating} />
          <KeyValueCard label="EPC lodgement date" value={sov.epcLodgementDate} />
          <KeyValueCard
            label="Roof base height"
            value={Number.isFinite(sov.heightRoofbase) ? `${fmt(sov.heightRoofbase, 1)} m` : "—"}
          />
          <KeyValueCard label="Height confidence" value={sov.heightConfidence} />
          <KeyValueCard
            label="Footprint"
            value={Number.isFinite(sov.footprint) ? `${fmt(sov.footprint, 1)} m²` : "—"}
          />
          <KeyValueCard
            label="Listed"
            value={
              isListed === true ? "Yes" : isListed === false ? "No" : "—"
            }
          />
          <KeyValueCard label="Listed grade" value={listedGrade} />
          <KeyValueCard label="Listed name" value={listedName} />
          <KeyValueCard label="Listed reference" value={listedReference} />
          <KeyValueCard label="Enrichment status" value={enrichmentStatus} />
          <KeyValueCard label="Enrichment source" value={enrichmentSource} />
          <KeyValueCard label="Enriched at" value={enrichedAt} />
        </div>
      </div>

      <div className="details-block">
        <div className="details-h">UPRN confidence</div>

        {uprnLoading && <div className="pill">Matching UPRN…</div>}

        {uprnError && (
          <div className="pill band-red" style={{ marginTop: 8 }}>
            {uprnError}
          </div>
        )}

        {!uprnLoading && !uprnError && bestUprn && (
          <div style={{ marginTop: 8 }}>
            <div className="details-sub">
              <b>Best match:</b> {bestUprn.uprn || "—"}
            </div>
            <div className="details-sub">
              <b>Confidence:</b>{" "}
              <span className={`pill ${uprnBestMeta.cls}`}>
                {uprnBestMeta.label} · {bestUprn.confidence_score ?? "—"}
              </span>
            </div>
            <div className="details-sub">
              <b>Distance:</b> {bestUprn.distance_m ?? "—"} m
            </div>
            <div className="details-sub">
              <b>Neighbours:</b> {bestUprn.neighbor_count ?? "—"}
            </div>
            {bestUprn.notes && (
              <div className="muted" style={{ marginTop: 8 }}>
                {bestUprn.notes}
              </div>
            )}
          </div>
        )}

        {!uprnLoading && !uprnError && !bestUprn && uprnResult && (
          <div className="muted" style={{ marginTop: 8 }}>
            No best UPRN match returned for this property.
          </div>
        )}

        {!uprnLoading && !uprnError && uprnWarnings.length > 0 && (
          <div className="muted" style={{ marginTop: 10 }}>
            <b>Warnings:</b> {uprnWarnings.join(" · ")}
          </div>
        )}

        {!uprnLoading &&
          !uprnError &&
          Array.isArray(uprnCandidates) &&
          uprnCandidates.length > 0 && (
            <div style={{ marginTop: 12 }} className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>UPRN</th>
                    <th>Band</th>
                    <th>Score</th>
                    <th>Dist (m)</th>
                    <th>Neighbours</th>
                  </tr>
                </thead>
                <tbody>
                  {uprnCandidates.slice(0, 10).map((candidate, idx) => {
                    const meta = bandMeta(candidate.confidence_band);
                    return (
                      <tr key={candidate.uprn || idx}>
                        <td className="td-key">{candidate.uprn || "—"}</td>
                        <td>
                          <span className={`pill ${meta.cls}`}>{meta.label}</span>
                        </td>
                        <td>{candidate.confidence_score ?? "—"}</td>
                        <td>{candidate.distance_m ?? "—"}</td>
                        <td>{candidate.neighbor_count ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
      </div>

      <div className="details-block">
        <div className="details-h">Raw fields</div>
        <RawFieldsTableInline raw={property?.raw ?? property} />
      </div>
    </div>
  );
}