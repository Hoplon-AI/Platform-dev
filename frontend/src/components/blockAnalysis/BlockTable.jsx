import {
  bandClass,
  blockDisplayAddress,
  getFireRiskBand,
  blockOverallBand,
} from "../../utils/blockModel";
import { RiskDot } from "./primitives";
import { accentClass, assetTypeLabel } from "./blockSort";

// Distinct colours per asset type so flats-in-blocks, houses and bungalows
// are distinguishable at a glance in the list.
const TYPE_PILL_STYLE = {
  Block:    { background: "rgba(59,130,246,0.10)",  border: "1px solid rgba(59,130,246,0.30)",  color: "#1d4ed8" },
  Flat:     { background: "rgba(139,92,246,0.10)",  border: "1px solid rgba(139,92,246,0.30)",  color: "#6d28d9" },
  House:    { background: "rgba(34,197,94,0.10)",   border: "1px solid rgba(34,197,94,0.30)",   color: "#15803d" },
  Bungalow: { background: "rgba(20,184,166,0.10)",  border: "1px solid rgba(20,184,166,0.35)",  color: "#0f766e" },
};

export function TypePill({ block }) {
  const label = assetTypeLabel(block);
  const style = TYPE_PILL_STYLE[label] || { background: "rgba(100,116,139,0.10)", border: "1px solid rgba(100,116,139,0.30)", color: "#475569" };
  return (
    <span
      className="pill"
      style={{ ...style, fontSize: 12, fontWeight: 600, padding: "3px 10px", borderRadius: 6 }}
    >
      {label}
    </span>
  );
}

// One band column cell: a colour pill with a status dot, or an em-dash when the
// block has no such document.
export function BandCell({ doc, band }) {
  if (!doc || !band) return <span className="ba-dash">—</span>;
  return (
    <span className={`pill ${bandClass(band)}`}>
      <RiskDot band={band} />
      {band}
    </span>
  );
}

export function SortHead({ label, col, sort, onSort, align = "left", width }) {
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
export function BlockTable({ blocks, selectedId, onSelect, sort, onSort }) {
  return (
    <div className="table-wrap" style={{ maxHeight: "calc(100vh - 300px)", overflowY: "auto" }}>
      <table className="ba-table">
        <thead>
          <tr>
            <SortHead label="Address" col="address" sort={sort} onSort={onSort} />
            <SortHead label="Type" col="type" sort={sort} onSort={onSort} align="center" width={110} />
            <SortHead label="Units" col="flats" sort={sort} onSort={onSort} align="center" width={90} />
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
                    {b.asset_type === "standalone"
                      ? `Standalone${postcode ? ` · ${postcode}` : ""}`
                      : `Block ${b.name}${postcode ? ` · ${postcode}` : ""}`}
                  </div>
                </td>
                <td style={{ textAlign: "center" }}>
                  <TypePill block={b} />
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
