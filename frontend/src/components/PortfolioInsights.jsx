import { useMemo, useState } from "react";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { isScotland } from "../utils/mapHelpers";

/* ─────────────────────────────────────────────────────────────────────────
   Portfolio Insights — composition & risk charts for the Portfolio Overview.

   Pure client-side aggregation over the `properties` array already in props.
   Categorical fields render as donuts, ordinal fields (age band, storeys) as
   bars. NULL/blank values are bucketed into an explicit "Unknown" slice so
   enrichment coverage is visible; a chart with no non-Unknown data is hidden.
   ───────────────────────────────────────────────────────────────────────── */

const UNKNOWN = "Unknown";
const UNKNOWN_COLOR = "#C4C0BB";
const NAVY = "#1E3246";

// Categorical palette from EquiRisk tokens. Navy leads (brand ink), terracotta
// kept late so red stays a small accent. Unknown always renders muted grey.
const PALETTE = [
  "#1E3246", // navy
  "#C8923E", // gold
  "#4F8A6B", // accent green
  "#7A8CA3", // slate
  "#B8564B", // terracotta (accent)
  "#A8B5A0", // sage
  "#C9A26B", // tan
  "#6B6560", // warm grey
];

const clean = (v) => {
  if (v === null || v === undefined) return null;
  const s = String(v).trim();
  return s ? s : null;
};

const pct = (v, total) => (total ? `${Math.round((v / total) * 100)}%` : "0%");

const sliceColor = (name, i) =>
  name === UNKNOWN ? UNKNOWN_COLOR : PALETTE[i % PALETTE.length];

function gbp(n) {
  if (!Number.isFinite(n)) return "—";
  if (n >= 1e6) return `£${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `£${Math.round(n / 1e3)}k`;
  return `£${Math.round(n)}`;
}

// Count properties by a bucket function. Null/blank → "Unknown". Sorted by
// count desc, with "Unknown" forced last.
function countBy(properties, keyFn) {
  const counts = new Map();
  for (const p of properties) {
    const key = keyFn(p) ?? UNKNOWN;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => {
      if (a.name === UNKNOWN) return 1;
      if (b.name === UNKNOWN) return -1;
      return b.value - a.value;
    });
}

// Re-order rows by an explicit band order (ordinal bars), Unknown last.
function ordered(rows, order) {
  const idx = (n) => {
    const i = order.indexOf(n);
    return i === -1 ? order.length : i;
  };
  return [...rows].sort((a, b) => idx(a.name) - idx(b.name));
}

const unknownOf = (rows) => rows.find((r) => r.name === UNKNOWN)?.value || 0;

// Collapse known wall-construction casing/whitespace variants so the donut
// doesn't split "Brick" / "brick" or "Sandstone/Brick" / "sandstone/Brick".
function normaliseWall(raw) {
  const s = clean(raw);
  if (!s) return null;
  const map = {
    "sandstone/brick": "Sandstone/Brick",
    brick: "Brick",
    sandstone: "Sandstone",
    "brick or block or stone": "Brick/Block/Stone",
    "other non-standard or system build": "Other / Non-standard",
    "timber or wood": "Timber",
  };
  return map[s.toLowerCase()] || s;
}

// Nation-aware high-rise risk band. England & Wales split at 11m and 18m
// (Low / Medium / High); Scotland has a single 11m threshold (Low / High).
function heightRiskBand(prop) {
  const v = Number(prop.height_m ?? prop.height_max_m);
  if (!Number.isFinite(v) || v <= 0) return null;
  if (isScotland(prop)) return v >= 11 ? "High" : "Low";
  if (v < 11) return "Low";
  if (v < 18) return "Medium";
  return "High";
}

// OS Places UPRN match confidence (GREEN/AMBER/LOW/RED) → readable labels.
function confidenceLabel(raw) {
  const s = clean(raw);
  if (!s) return null;
  const map = {
    green: "Confident match",
    amber: "Likely match",
    low: "Low confidence",
    red: "No reliable match",
  };
  return map[s.toLowerCase()] || s;
}

// RAG-semantic colours for the confidence donut (overrides the generic palette).
const CONFIDENCE_COLORS = {
  "Confident match": "#4F8A6B",
  "Likely match": "#C8923E",
  "Low confidence": "#C76A5F",
  "No reliable match": "#B8564B",
  [UNKNOWN]: UNKNOWN_COLOR,
};

// Flood risk is ordinal — colour as a green→red spectrum so risk reads visually
// (Very Low safest → High most severe). Bands: Very Low / Low / Medium / High.
const FLOOD_ORDER = ["Very Low", "Low", "Medium", "High", UNKNOWN];
const FLOOD_COLORS = {
  "Very Low": "#4F8A6B", // green
  Low: "#C8923E",        // gold
  Medium: "#C76A5F",     // terracotta
  High: "#B8564B",       // red
  [UNKNOWN]: UNKNOWN_COLOR,
};

// Building height risk band — fire-safety severity: Low green, Medium amber, High red.
const HEIGHT_ORDER = ["Low", "Medium", "High", UNKNOWN];
const HEIGHT_COLORS = {
  Low: "#4F8A6B",    // green
  Medium: "#C8923E", // amber
  High: "#B8564B",   // red
  [UNKNOWN]: UNKNOWN_COLOR,
};

// Same bands as the existing ageBandRows useMemo in PortfolioDashboard.jsx.
function ageBand(yob) {
  const year = Number(yob);
  if (!Number.isFinite(year) || year === 0) return null;
  if (year < 1919) return "Pre-1919";
  if (year < 1945) return "1920–1944";
  if (year < 1980) return "1945–1979";
  if (year < 2001) return "1980–2000";
  return "2001+";
}

const cardStyle = {
  background: "var(--panel-soft)",
  border: "1px solid var(--border-soft)",
  borderRadius: 16,
  padding: 14,
};
const chartTitleStyle = {
  fontWeight: 700,
  marginBottom: 8,
  fontSize: 14,
  color: "var(--text)",
};
const captionStyle = { marginTop: 10, fontSize: 11.5, color: "var(--muted)" };

function DonutLegend({ data, total, colorFor }) {
  return (
    <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 5 }}>
      {data.map((d, i) => (
        <div
          key={d.name}
          style={{
            display: "grid",
            gridTemplateColumns: "11px 1fr auto",
            gap: 8,
            alignItems: "center",
            fontSize: 12.5,
          }}
        >
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: 999,
              background: colorFor(d.name, i),
            }}
          />
          <span
            style={{
              color: "var(--text)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {d.name}
          </span>
          <span className="muted">
            {d.value} · {pct(d.value, total)}
          </span>
        </div>
      ))}
    </div>
  );
}

function DonutCard({ title, data, caption, colors, enrichedOnly }) {
  if (!data.some((d) => d.name !== UNKNOWN)) return null;
  // Enrichment-derived donuts: drop the "Unknown" (un-enriched) slice so the
  // percentages are relative to enriched properties only. The caption still
  // reports the base count.
  if (enrichedOnly) data = data.filter((d) => d.name !== UNKNOWN);
  const total = data.reduce((s, d) => s + d.value, 0);
  const colorFor = (name, i) =>
    colors && colors[name] ? colors[name] : sliceColor(name, i);
  return (
    <div style={cardStyle}>
      <div style={chartTitleStyle}>{title}</div>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={45}
            outerRadius={75}
            paddingAngle={1}
            stroke="none"
            isAnimationActive={false}
          >
            {data.map((d, i) => (
              <Cell key={d.name} fill={colorFor(d.name, i)} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, name) => [`${value} (${pct(value, total)})`, name]}
          />
        </PieChart>
      </ResponsiveContainer>
      <DonutLegend data={data} total={total} colorFor={colorFor} />
      {caption ? <div style={captionStyle}>{caption}</div> : null}
    </div>
  );
}

function BarCard({ title, data, caption, labelFormatter }) {
  if (!data.some((d) => d.name !== UNKNOWN)) return null;
  return (
    <div style={cardStyle}>
      <div style={chartTitleStyle}>{title}</div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <XAxis
            dataKey="name"
            interval={0}
            tick={{ fontSize: 11, fill: "#6B6560" }}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 11, fill: "#6B6560" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(30,50,70,0.05)" }}
            labelFormatter={labelFormatter}
            formatter={(value) => [value, "flats"]}
          />
          <Bar dataKey="value" radius={[6, 6, 0, 0]} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.name} fill={d.name === UNKNOWN ? UNKNOWN_COLOR : NAVY} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {caption ? <div style={captionStyle}>{caption}</div> : null}
    </div>
  );
}

function StatTile({ label, value }) {
  return (
    <div style={cardStyle}>
      <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 800, color: "var(--text)" }}>{value}</div>
    </div>
  );
}

export function PortfolioInsightsPanel({ properties }) {
  const model = useMemo(() => {
    const list = Array.isArray(properties) ? properties : [];
    const n = list.length;

    const propertyType = countBy(list, (p) => clean(p.property_type));
    const occupancy = countBy(list, (p) => clean(p.occupancy_type));
    const wall = countBy(list, (p) => normaliseWall(p.wall_construction));
    const roof = countBy(list, (p) => clean(p.roof_construction));
    // OS NGD constructionmaterial on its own (unmerged), enrichment-only.
    const osConstruction = countBy(list, (p) => normaliseWall(p.os_construction_material));

    const ageRows = ordered(
      countBy(list, (p) => ageBand(p.year_of_build)),
      ["Pre-1919", "1920–1944", "1945–1979", "1980–2000", "2001+", UNKNOWN]
    );

    const storeyRows = ordered(
      countBy(list, (p) => (clean(p.storeys) ? String(p.storeys) : null)),
      // numeric ascending order, Unknown forced last via ordered()'s fallback
      [...new Set(list.map((p) => clean(p.storeys)).filter(Boolean))]
        .map(Number)
        .filter(Number.isFinite)
        .sort((a, b) => a - b)
        .map(String)
    );

    const flood = ordered(
      countBy(list, (p) => clean(p.flood_risk_band)),
      FLOOD_ORDER
    );
    const height = ordered(countBy(list, heightRiskBand), HEIGHT_ORDER);
    const uprn = ordered(
      countBy(list, (p) => confidenceLabel(p.uprn_confidence)),
      [
        "Confident match",
        "Likely match",
        "Low confidence",
        "No reliable match",
        UNKNOWN,
      ]
    );

    const coverage = (rows) => {
      const known = n - unknownOf(rows);
      return n ? `Based on ${known} of ${n} properties (${pct(known, n)} enriched)` : null;
    };

    const sums = list.map((p) => Number(p.sum_insured)).filter(Number.isFinite);
    const totalSI = sums.reduce((a, b) => a + b, 0);
    const avgSI = sums.length ? totalSI / sums.length : 0;
    const blockCount = new Set(
      list.map((p) => clean(p.block_reference)).filter(Boolean)
    ).size;
    const enrichedCount = list.filter(
      (p) => p.uprn || p.enrichment_status === "enriched"
    ).length;

    return {
      n,
      propertyType,
      occupancy,
      wall,
      roof,
      osConstruction,
      osConstructionCaption: coverage(osConstruction),
      ageRows,
      storeyRows,
      flood,
      floodCaption: coverage(flood),
      height,
      heightCaption: [coverage(height), "High = 18m+ (Scotland 11m+), Medium = 11–18m, Low = <11m."]
        .filter(Boolean)
        .join(" · "),
      uprn,
      uprnCaption: coverage(uprn),
      stats: { totalSI, avgSI, blockCount, enrichedCount },
    };
  }, [properties]);

  const [collapsed, setCollapsed] = useState(false);

  if (!properties?.length) return null;

  const { stats } = model;

  return (
    <div className="card">
      <div
        className="card-header row-between"
        style={{ cursor: "pointer", userSelect: "none", paddingBottom: collapsed ? 16 : undefined }}
        onClick={() => setCollapsed((c) => !c)}
      >
        <div>
          <div className="card-title">Portfolio Insights</div>
          <div className="card-subtitle">
            Composition and risk profile across the ingested portfolio and enrichment data.
          </div>
        </div>
        <span className={`panel-chev${collapsed ? " is-collapsed" : ""}`} style={{ fontSize: 16, lineHeight: 1 }}>▾</span>
      </div>

      <div
        style={{
          overflow: "hidden",
          maxHeight: collapsed ? 0 : 1600,
          transition: "max-height 0.35s ease",
        }}
      >
      <div className="card-body">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 14,
            marginBottom: 16,
          }}
        >
          <StatTile label="Properties" value={model.n.toLocaleString()} />
          <StatTile
            label="Properties enriched"
            value={`${stats.enrichedCount.toLocaleString()} (${pct(stats.enrichedCount, model.n)} of the portfolio)`}
          />
          <StatTile label="Blocks" value={stats.blockCount.toLocaleString()} />
          <StatTile label="Total insured value" value={gbp(stats.totalSI)} />
          <StatTile label="Average sum insured" value={gbp(stats.avgSI)} />
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: 16,
          }}
        >
          <DonutCard title="Property type" data={model.propertyType} />
          <DonutCard title="Occupancy" data={model.occupancy} />
          <DonutCard title="Wall construction" data={model.wall} />
          <DonutCard title="Roof construction" data={model.roof} />
          <DonutCard
            title="OS construction material"
            data={model.osConstruction}
            caption={model.osConstructionCaption}
            enrichedOnly
          />

          <BarCard title="Age band" data={model.ageRows} />
          <BarCard
            title="Flats by building storeys"
            data={model.storeyRows}
            labelFormatter={(l) => (l === UNKNOWN ? l : `${l} storeys`)}
          />
          <DonutCard
            title="Flood risk"
            data={model.flood}
            caption={model.floodCaption}
            colors={FLOOD_COLORS}
            enrichedOnly
          />
          <DonutCard
            title="Building height"
            data={model.height}
            caption={model.heightCaption}
            colors={HEIGHT_COLORS}
            enrichedOnly
          />
          <DonutCard
            title="UPRN match confidence"
            data={model.uprn}
            caption={model.uprnCaption}
            colors={CONFIDENCE_COLORS}
            enrichedOnly
          />
        </div>
      </div>
      </div>
    </div>
  );
}

export default PortfolioInsightsPanel;
