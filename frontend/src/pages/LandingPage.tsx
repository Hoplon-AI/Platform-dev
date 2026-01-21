import { useEffect, useMemo, useState } from "react";

import type {
  Portfolio,
  PortfolioReadiness,
  PortfolioRiskDistributionRow,
  PortfolioSummary,
  RecentActivityRow,
} from "../types/portfolio";
import {
  getPortfolioReadiness,
  getPortfolioRecentActivity,
  getPortfolioRiskDistribution,
  getPortfolioSummary,
  listPortfolios,
} from "../services/portfolios";
import { API_BASE_URL } from "../services/apiClient";

function formatPct(value: string | number) {
  const n = typeof value === "string" ? Number.parseFloat(value) : value;
  if (!Number.isFinite(n)) return "—";
  return `${Math.round(n * 100)}%`;
}

function formatDateTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function RiskBars({ rows }: { rows: PortfolioRiskDistributionRow[] }) {
  const total = rows.reduce((acc, r) => acc + r.property_count, 0) || 1;
  const ordered = useMemo(() => {
    const order = ["A", "B", "C", "D", "E"];
    return [...rows].sort(
      (a, b) => order.indexOf(a.risk_rating) - order.indexOf(b.risk_rating),
    );
  }, [rows]);

  return (
    <div style={{ display: "grid", gap: 10 }}>
      {ordered.map((r) => {
        const pct = (r.property_count / total) * 100;
        return (
          <div key={r.risk_rating} style={{ display: "grid", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span className="subtle">Rating {r.risk_rating}</span>
              <span className="subtle">{r.property_count}</span>
            </div>
            <div
              style={{
                height: 10,
                borderRadius: 999,
                border: "1px solid var(--border)",
                background: "rgba(2, 6, 23, 0.45)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: "100%",
                  background: "rgba(96, 165, 250, 0.75)",
                }}
              />
            </div>
          </div>
        );
      })}
      {rows.length === 0 ? <div className="subtle">No ratings yet.</div> : null}
    </div>
  );
}

export function PortfolioOverviewPage() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");

  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [readiness, setReadiness] = useState<PortfolioReadiness | null>(null);
  const [risk, setRisk] = useState<PortfolioRiskDistributionRow[]>([]);
  const [activity, setActivity] = useState<RecentActivityRow[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load portfolios
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listPortfolios()
      .then((data) => {
        if (cancelled) return;
        setPortfolios(data);
        setSelectedPortfolioId((prev) => prev || data[0]?.portfolio_id || "");
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Load dashboard widgets for selected portfolio
  useEffect(() => {
    if (!selectedPortfolioId) return;
    let cancelled = false;
    setError(null);

    Promise.all([
      getPortfolioSummary(selectedPortfolioId),
      getPortfolioReadiness(selectedPortfolioId),
      getPortfolioRiskDistribution(selectedPortfolioId),
      getPortfolioRecentActivity(selectedPortfolioId, 10),
    ])
      .then(([s, r, d, a]) => {
        if (cancelled) return;
        setSummary(s);
        setReadiness(r);
        setRisk(d);
        setActivity(a);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      });

    return () => {
      cancelled = true;
    };
  }, [selectedPortfolioId]);

  return (
    <div className="container">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28 }}>PortfolioOverview</h1>
          <div className="subtle" style={{ marginTop: 6 }}>
            Wired to API: <code>{API_BASE_URL}</code>
          </div>
        </div>

        <div className="row" style={{ alignItems: "center" }}>
          <select
            className="select"
            value={selectedPortfolioId}
            onChange={(e) => setSelectedPortfolioId(e.target.value)}
            aria-label="Select portfolio"
            disabled={loading || portfolios.length === 0}
          >
            {portfolios.length === 0 ? (
              <option value="">No portfolios</option>
            ) : (
              portfolios.map((p) => (
                <option key={p.portfolio_id} value={p.portfolio_id}>
                  {p.name} ({p.ha_id})
                </option>
              ))
            )}
          </select>
          <button
            className="btn"
            type="button"
            onClick={() => {
              // quick refresh of widgets
              setSummary(null);
              setReadiness(null);
              setRisk([]);
              setActivity([]);
              // re-trigger effect by setting same id in microtask
              queueMicrotask(() => setSelectedPortfolioId((v) => v));
            }}
          >
            Refresh
          </button>
        </div>
      </div>

      {error ? (
        <div className="card" style={{ marginTop: 16, borderColor: "#ef4444" }}>
          <h3>Error</h3>
          <div style={{ whiteSpace: "pre-wrap" }}>{error}</div>
          <div className="subtle" style={{ marginTop: 10 }}>
            Tip: confirm the API is running (`/health`) and `DEV_MODE=true`.
          </div>
        </div>
      ) : null}

      <div className="grid3" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>Total blocks</h3>
          <div className="metric">{summary?.total_blocks ?? "—"}</div>
        </div>
        <div className="card">
          <h3>Total units</h3>
          <div className="metric">{summary?.total_units ?? "—"}</div>
        </div>
        <div className="card">
          <h3>Total properties</h3>
          <div className="metric">{summary?.total_properties ?? "—"}</div>
        </div>
      </div>

      <div className="grid2" style={{ marginTop: 12 }}>
        <div className="card">
          <h3>Readiness (data completeness)</h3>
          {readiness ? (
            <div style={{ display: "grid", gap: 8 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="subtle">Has UPRN</span>
                <span>{formatPct(readiness.pct_has_uprn)}</span>
              </div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="subtle">Has postcode</span>
                <span>{formatPct(readiness.pct_has_postcode)}</span>
              </div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="subtle">Has geocode</span>
                <span>{formatPct(readiness.pct_has_geo)}</span>
              </div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="subtle">Has height</span>
                <span>{formatPct(readiness.pct_has_height)}</span>
              </div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="subtle">Has build year</span>
                <span>{formatPct(readiness.pct_has_build_year)}</span>
              </div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="subtle">Has construction</span>
                <span>{formatPct(readiness.pct_has_construction)}</span>
              </div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="subtle">Has risk rating</span>
                <span>{formatPct(readiness.pct_has_risk_rating)}</span>
              </div>
              <div className="subtle" style={{ marginTop: 6 }}>
                Computed at: {formatDateTime(readiness.computed_at)}
              </div>
            </div>
          ) : (
            <div className="subtle">Loading readiness…</div>
          )}
        </div>

        <div className="card">
          <h3>Risk distribution</h3>
          {summary ? <RiskBars rows={risk} /> : <div className="subtle">Loading risk…</div>}
        </div>
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <h3>Recent activity</h3>
        {activity.length === 0 ? (
          <div className="subtle">No activity yet.</div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {activity.map((e) => (
              <div
                key={e.event_id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto",
                  gap: 8,
                  padding: "10px 12px",
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  background: "rgba(2, 6, 23, 0.35)",
                }}
              >
                <div style={{ display: "grid", gap: 2 }}>
                  <div style={{ fontWeight: 600 }}>
                    {e.file_type} — {e.filename}
                  </div>
                  <div className="subtle">
                    {e.status} · {e.actor_id} · {e.ha_id}
                  </div>
                </div>
                <div className="subtle" style={{ whiteSpace: "nowrap" }}>
                  {formatDateTime(e.created_at)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {loading && portfolios.length === 0 ? (
        <div className="subtle" style={{ marginTop: 12 }}>
          Loading portfolios…
        </div>
      ) : null}
    </div>
  );
}

