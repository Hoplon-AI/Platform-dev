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
import PropertyDetails from "../components/PropertyDetails";

// ---------------------------------------------------------------- page

export default function BlockAnalysisPage({ ingestionResult, latestFireRiskPayload = null, onUploadNew, haName = "" }) {
  const [query, setQuery] = useState("");
  const [bandFilter, setBandFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all"); // all | block | standalone
  const [sort, setSort] = useState({ key: null, dir: "desc" });
  const [selectedId, setSelectedId] = useState(null);
  const [selectedProperty, setSelectedProperty] = useState(null);

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

  const standaloneCount = useMemo(
    () => blocks.filter((b) => b.asset_type === "standalone").length,
    [blocks]
  );

  // Per-type tallies: real blocks vs each standalone dwelling form.
  const typeCounts = useMemo(() => {
    const c = { block: 0, house: 0, bungalow: 0, flat: 0, other: 0 };
    for (const b of blocks) {
      if (b.asset_type === "standalone") {
        if (c[b.dwelling_form] !== undefined) c[b.dwelling_form]++;
        else c.other++;
      } else {
        c.block++;
      }
    }
    return c;
  }, [blocks]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return blocks.filter((b) => {
      if (q && !blockStreetText(b).includes(q)) return false;
      if (bandFilter !== "all" && (blockOverallBand(b) || "none") !== bandFilter) return false;
      if (typeFilter !== "all") {
        if (typeFilter === "block") {
          if (b.asset_type === "standalone") return false;
        } else if (!(b.asset_type === "standalone" && b.dwelling_form === typeFilter)) {
          return false;
        }
      }
      return true;
    });
  }, [blocks, query, bandFilter, typeFilter]);

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
            <div className="page-title">Property Analysis</div>
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
  const pickType = (id) => setTypeFilter((f) => (f === id ? "all" : id));

  // ---- Individual property analysis (property row clicked in a dossier) ----
  if (selected && selectedProperty) {
    const addr =
      selectedProperty.address_line_1 ||
      selectedProperty.address ||
      selectedProperty.property_reference ||
      "Property";
    return (
      <>
        <div className="main-head">
          <div>
            <button
              type="button"
              className="ba-back"
              onClick={() => {
                setSelectedProperty(null);
                if (selected.asset_type === "standalone") setSelectedId(null);
              }}
            >
              ← Back to {selected.asset_type === "standalone" ? "list" : `block ${selected.name}`}
            </button>
            <div className="page-title" style={{ marginTop: 6 }}>{addr}</div>
            <div className="page-sub">
              Individual property analysis
              {selectedProperty.post_code ? ` · ${selectedProperty.post_code}` : ""}
              {selectedProperty.uprn ? ` · UPRN ${selectedProperty.uprn}` : ""}
            </div>
          </div>
        </div>
        <div className="content-wrap">
          <div className="card">
            <div className="card-body" style={{ maxWidth: 720 }}>
              <PropertyDetails
                property={selectedProperty}
                selectedBlock={selected.asset_type === "standalone" ? null : selected}
                onSelectProperty={setSelectedProperty}
              />
            </div>
          </div>
        </div>
      </>
    );
  }

  // ---- Dedicated full-page block detail (shown when a row is clicked) ----
  if (selected) {
    const overall = blockOverallBand(selected);
    const { street, postcode } = blockDisplayAddress(selected);
    const isStandalone = selected.asset_type === "standalone";
    return (
      <>
        <div className="main-head">
          <div>
            <button
              type="button"
              className="ba-back"
              onClick={() => { setSelectedId(null); setSelectedProperty(null); }}
            >
              ← Back to list
            </button>
            <div className="page-title" style={{ marginTop: 6 }}>{street}</div>
            <div className="page-sub">
              {isStandalone
                ? `Standalone ${selected.dwelling_form || "dwelling"} — not part of a block`
                : `Block ${selected.name}`}
              {postcode ? ` · ${postcode}` : ""}
              {selected.parent_uprn ? ` · UPRN ${selected.parent_uprn}` : ""}
            </div>
          </div>
          <span className={`pill ${bandClass(overall)}`} style={{ fontSize: 13, padding: "8px 14px" }}>
            {bandVerdict(overall)}
          </span>
        </div>
        <div className="content-wrap">
          <Dossier block={selected} onSelectProperty={setSelectedProperty} />
        </div>
      </>
    );
  }

  return (
    <>
      <div className="main-head">
        <div>
          <div className="page-title">Property Analysis</div>
          {haName && (
            <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
              For: <strong style={{ color: "var(--terracotta)" }}>{haName}</strong>
            </div>
          )}
          <div className="page-sub">Every block and standalone dwelling with address, type, size, UPRN and FRA / FRAEW fire-risk banding. Click a row for the full risk profile.</div>
        </div>
        <span className="pill pill-muted">
          {standaloneCount > 0
            ? `${blocks.length - standaloneCount} blocks · ${standaloneCount} standalone`
            : `${blocks.length} blocks`}
        </span>
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
                {standaloneCount > 0 && (
                  <>
                    <StatChip
                      label="Blocks"
                      active={typeFilter === "block"}
                      count={typeCounts.block}
                      onClick={() => pickType("block")}
                    />
                    {typeCounts.house > 0 && (
                      <StatChip label="Houses" active={typeFilter === "house"} count={typeCounts.house} onClick={() => pickType("house")} />
                    )}
                    {typeCounts.bungalow > 0 && (
                      <StatChip label="Bungalows" active={typeFilter === "bungalow"} count={typeCounts.bungalow} onClick={() => pickType("bungalow")} />
                    )}
                    {typeCounts.flat > 0 && (
                      <StatChip label="Standalone flats" active={typeFilter === "flat"} count={typeCounts.flat} onClick={() => pickType("flat")} />
                    )}
                  </>
                )}
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
            <BlockTable
              blocks={visible}
              selectedId={null}
              onSelect={(id) => { setSelectedProperty(null); setSelectedId(id); }}
              sort={sort}
              onSort={toggleSort}
            />
          )}
        </div>
      </div>
    </>
  );
}
