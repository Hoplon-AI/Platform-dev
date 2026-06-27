import { useMemo, useState } from "react";
import {
  buildBlocks,
  collectFireDocuments,
  blockOverallBand,
  bandVerdict,
  bandClass,
  blockStreetText,
  blockDisplayAddress,
} from "../utils/blockModel";
import { StatChip } from "../components/blockAnalysis/primitives";
import { BlockTable } from "../components/blockAnalysis/BlockTable";
import { compareBlocks } from "../components/blockAnalysis/blockSort";
import Dossier from "../components/blockAnalysis/Dossier";

// ---------------------------------------------------------------- page

export default function BlockAnalysisPage({ ingestionResult, latestFireRiskPayload = null, onUploadNew, haName = "" }) {
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
            {haName && (
              <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                For: <strong style={{ color: "var(--terracotta)" }}>{haName}</strong>
              </div>
            )}
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
          {haName && (
            <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
              For: <strong style={{ color: "var(--terracotta)" }}>{haName}</strong>
            </div>
          )}
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
