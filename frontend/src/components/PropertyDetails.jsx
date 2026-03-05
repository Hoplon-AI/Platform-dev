import React, { useMemo } from "react";

const fmt = (n, digits = 2) => {
  const x = Number(n);
  return Number.isFinite(x) ? x.toFixed(digits) : "—";
};

const fmtMoney = (n, digits = 0) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  return x.toLocaleString("en-GB", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

function bandMeta(band) {
  const b = (band || "").toString().toUpperCase();
  if (b.includes("HIGH") || b.includes("GREEN")) return { label: "Green", cls: "band-green" };
  if (b.includes("MED") || b.includes("YELLOW")) return { label: "Yellow", cls: "band-yellow" };
  return { label: "Red", cls: "band-red" };
}

function readinessFromProperty(p) {
  const score =
    Number(p.readiness_score ?? p.readinessScore ?? p.readiness ?? p.data_readiness ?? NaN);
  const band =
    p.readiness_band ?? p.readinessBand ?? p.readiness_colour ?? p.readinessColor ?? "";

  if (!Number.isFinite(score) && band) {
    const b = band.toString().toLowerCase();
    if (b.includes("green")) return { score: 85, band: "Green" };
    if (b.includes("yellow")) return { score: 60, band: "Yellow" };
    if (b.includes("red")) return { score: 35, band: "Red" };
  }

  if (Number.isFinite(score)) {
    const inferred = score >= 80 ? "Green" : score >= 50 ? "Yellow" : "Red";
    return { score, band: band || inferred };
  }

  return { score: null, band: band || "—" };
}

function RawFieldsTableInline({ raw }) {
  const rows = useMemo(() => {
    if (!raw || typeof raw !== "object") return [];
    return Object.entries(raw)
      .filter(([k]) => !String(k).startsWith("__")) // hide internal ids
      .map(([k, v]) => {
        let value = v;
        if (value === null || value === undefined || value === "") value = "—";
        else if (typeof value === "object") value = JSON.stringify(value);
        return { key: k, value: String(value) };
      });
  }, [raw]);

  if (!rows.length) return <div className="muted">No raw fields available.</div>;

  return (
    <div className="table-scroll">
      <table className="raw-table">
        <thead>
          <tr>
            <th style={{ width: "44%" }}>Field</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td style={{ fontWeight: 700 }}>{r.key}</td>
              <td className="mono" style={{ whiteSpace: "pre-wrap" }}>{r.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PropertyDetails({ property, uprnResult, uprnLoading, uprnError }) {
  const readiness = useMemo(() => (property ? readinessFromProperty(property) : null), [property]);

  const lat = property?.lat ?? property?.latitude;
  const lon = property?.lon ?? property?.longitude;

  const postcode = property?.postcode ?? property?.post_code ?? "—";
  const city = property?.city ?? "—";
  const address1 = property?.address1 ?? property?.address_line_1 ?? "—";
  const address2 = property?.address2 ?? property?.address_line_2 ?? "";

  const sumInsured =
    property?.sumInsured ??
    property?.sum_insured ??
    property?.total_sum_insured ??
    property?.value ??
    null;

  const propertyType = property?.propertyType ?? property?.property_type ?? "—";
  const occupancy =
    property?.occupancyType ??
    property?.occupancy_type ??
    property?.occupancy ??
    "—";

  const flats = property?.numberOfFlats ?? property?.number_of_flats ?? property?.flats ?? "—";

  const uprnBest = uprnResult?.best_match || null;
  const uprnCandidates = uprnResult?.candidates || [];
  const uprnWarnings = uprnResult?.warnings || [];
  const uprnBand = useMemo(() => bandMeta(uprnBest?.confidence_band), [uprnBest]);

  if (!property) {
    return (
      <div className="details-empty">
        Click a property circle on the map to view SOV + property details here.
      </div>
    );
  }

  return (
    <div className="details">
      <div className="details-section">
        <div className="details-h">
          <div>
            <div className="details-title">Property</div>
            <div className="details-sub">
              {city} · {postcode} · lat {fmt(lat, 5)}, lon {fmt(lon, 5)}
            </div>
            <div className="details-addr">
              {address1} {address2 ? <span className="muted">· {address2}</span> : null}
            </div>
          </div>

          {readiness?.score != null && (
            <div className={`pill ${bandMeta(readiness.band).cls}`}>
              {Math.round(readiness.score)} / 100 ({readiness.band})
            </div>
          )}
        </div>
      </div>

      <div className="details-section">
        <div className="details-title">SOV</div>
        <div className="kv-grid">
          <div className="kv">
            <div className="kv-k">Sum insured</div>
            <div className="kv-v">£{fmtMoney(sumInsured, 0)}</div>
          </div>
          <div className="kv">
            <div className="kv-k">Property type</div>
            <div className="kv-v">{propertyType}</div>
          </div>
          <div className="kv">
            <div className="kv-k">Occupancy</div>
            <div className="kv-v">{occupancy}</div>
          </div>
          <div className="kv">
            <div className="kv-k">Number of flats</div>
            <div className="kv-v">{flats}</div>
          </div>
        </div>
      </div>

      <div className="details-section">
        <div className="details-title">UPRN match (backend)</div>

        {uprnLoading && <div className="pill">Matching UPRN…</div>}
        {uprnError && <div className="pill band-red" style={{ marginTop: 8 }}>{uprnError}</div>}

        {!uprnLoading && !uprnError && uprnResult && (
          <>
            {uprnBest ? (
              <div className="uprn-best">
                <div className="uprn-best-top">
                  <div>
                    <div className="uprn-uprn">
                      Best match: <span className="mono">{uprnBest.uprn}</span>
                    </div>
                    <div className="uprn-notes">{uprnBest.notes}</div>
                  </div>
                  <div className="uprn-score">
                    <div className={`pill ${uprnBand.cls}`}>
                      {uprnBand.label} · {uprnBest.confidence_score}
                    </div>
                    <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                      dist {uprnBest.distance_m}m · neighbors {uprnBest.neighbor_count}
                    </div>
                  </div>
                </div>

                {uprnWarnings.length > 0 && (
                  <div className="uprn-warn">
                    <div className="uprn-warn-title">Warnings</div>
                    <ul>
                      {uprnWarnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="pill band-yellow" style={{ marginTop: 8 }}>
                No best match returned (postcode missing from DB or no candidates).
              </div>
            )}

            {uprnCandidates.length > 0 && (
              <div className="uprn-table-wrap">
                <div className="uprn-table-title">Candidates</div>
                <div className="table-scroll">
                  <table className="uprn-table">
                    <thead>
                      <tr>
                        <th>UPRN</th>
                        <th>Band</th>
                        <th>Score</th>
                        <th>Dist (m)</th>
                        <th>Neighbors</th>
                        <th>Signals</th>
                      </tr>
                    </thead>
                    <tbody>
                      {uprnCandidates.map((c) => {
                        const meta = bandMeta(c.confidence_band);
                        return (
                          <tr key={c.uprn}>
                            <td className="mono">{c.uprn}</td>
                            <td><span className={`pill ${meta.cls}`}>{meta.label}</span></td>
                            <td>{c.confidence_score}</td>
                            <td>{c.distance_m}</td>
                            <td>{c.neighbor_count}</td>
                            <td className="muted">
                              pc {c.signals?.postcode ?? 0} · sp {c.signals?.spatial ?? 0} · den{" "}
                              {c.signals?.density ?? 0} · pen {c.signals?.penalties ?? 0}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="details-section">
        <div className="details-title">Raw fields (from upload)</div>
        <RawFieldsTableInline raw={property} />
      </div>
    </div>
  );
}
