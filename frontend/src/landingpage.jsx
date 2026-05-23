import React, { useEffect, useState, useRef, useCallback } from "react";

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  navy:       "#0b1120",
  navyMid:    "#0f172a",
  navyLight:  "#1e293b",
  blue:       "#2563eb",
  blueMid:    "#3b82f6",
  bluePale:   "#dbeafe",
  blueXPale:  "#eff6ff",
  slate:      "#64748b",
  slateLight: "#94a3b8",
  text:       "#1e293b",
  textMid:    "#334155",
  surface:    "#f8fafc",
  white:      "#ffffff",
  border:     "#e2e8f0",
  green:      "#10b981",
  amber:      "#f59e0b",
};

// ─── CSS animations injected once ─────────────────────────────────────────────
const GLOBAL_CSS = `
  @keyframes equi-float {
    0%, 100% { transform: translateY(0px); }
    50%       { transform: translateY(-10px); }
  }
  @keyframes equi-pulse-dot {
    0%, 100% { box-shadow: 0 0 0 0 rgba(37,99,235,0.7); }
    50%       { box-shadow: 0 0 0 6px rgba(37,99,235,0); }
  }
  @keyframes equi-marquee {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
  }
  @keyframes equi-fade-up {
    from { opacity: 0; transform: translateY(28px); }
    to   { opacity: 1; transform: translateY(0);    }
  }
  @keyframes equi-fade-in {
    from { opacity: 0; }
    to   { opacity: 1; }
  }
  @keyframes equi-shimmer {
    0%   { background-position: -400px 0; }
    100% { background-position:  400px 0; }
  }
  .equi-reveal {
    opacity: 0;
    transform: translateY(28px);
    transition: opacity 0.7s cubic-bezier(0.22,1,0.36,1), transform 0.7s cubic-bezier(0.22,1,0.36,1);
  }
  .equi-reveal.visible {
    opacity: 1;
    transform: translateY(0);
  }
  .equi-reveal-delay-1 { transition-delay: 0.1s; }
  .equi-reveal-delay-2 { transition-delay: 0.2s; }
  .equi-reveal-delay-3 { transition-delay: 0.3s; }
  .equi-reveal-delay-4 { transition-delay: 0.4s; }
  .equi-reveal-delay-5 { transition-delay: 0.5s; }
  .equi-reveal-delay-6 { transition-delay: 0.6s; }
`;

// ─── Marquee capabilities (replaces raw number stats bar) ─────────────────────
const MARQUEE_ITEMS = [
  { icon: "📋", text: "Schedule of Values ingestion" },
  { icon: "🔥", text: "FRA risk extraction" },
  { icon: "🏗️", text: "FRAEW cladding analysis" },
  { icon: "📍", text: "OS UPRN geocoding" },
  { icon: "⚡", text: "< 60s portfolio build" },
  { icon: "📊", text: "Doc A & Doc B export" },
  { icon: "🛡️", text: "EPC rating enrichment" },
  { icon: "🏘️", text: "Block detection & grouping" },
  { icon: "📄", text: "Listed building flags" },
  { icon: "🤖", text: "AI-powered document reading" },
  { icon: "🗺️", text: "Building geometry from NGD" },
  { icon: "✅", text: "Underwriter-ready reports" },
];

// ─── Data ─────────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: <SvgSchedule />,
    title: "Schedule of Values",
    desc: "Ingest SoV Excel files in seconds. Quinn maps 35+ property attributes, detects blocks, and builds your full portfolio structure automatically.",
    tag: "Core",
  },
  {
    icon: <SvgFire />,
    title: "FRA Intelligence",
    desc: "AI extracts fire risk ratings, evacuation strategies, sprinkler systems, and outstanding action items directly from PDF assessments.",
    tag: "AI-powered",
  },
  {
    icon: <SvgBuilding />,
    title: "FRAEW Analysis",
    desc: "External wall risk scoring — cladding detection, EPS insulation flags, cavity barrier assessment, and remedial action tracking.",
    tag: "AI-powered",
  },
  {
    icon: <SvgExport />,
    title: "Doc A & Doc B Export",
    desc: "Generate submission-ready Excel reports per unit (Doc A) and per block (Doc B) enriched with OS data, EPC ratings, and cladding risk scores.",
    tag: "Underwriting",
  },
  {
    icon: <SvgMap />,
    title: "OS & EPC Enrichment",
    desc: "Automatically geocode every property via Ordnance Survey, fetch EPC ratings, and flag listed buildings — no manual data entry.",
    tag: "Data",
  },
  {
    icon: <SvgShield />,
    title: "Underwriter Dashboard",
    desc: "Real-time portfolio views for housing associations and underwriters, with RAG status, risk ratings, and cross-portfolio analytics.",
    tag: "Analytics",
  },
];

const HOW_STEPS = [
  {
    n: "01",
    title: "Upload your portfolio",
    desc: "Drop in your Schedule of Values Excel. Quinn validates, parses, and creates your full property and block structure — typically under 60 seconds.",
  },
  {
    n: "02",
    title: "Attach risk evidence",
    desc: "Upload FRA and FRAEW PDFs. Our AI reads every page, extracting risk indicators, ratings, cladding types, and remediation actions automatically.",
  },
  {
    n: "03",
    title: "Export ready reports",
    desc: "Download Doc A (per-unit schedule) and Doc B (per-block risk summary) — enriched, structured, and ready for underwriting submission.",
  },
];

const AUDIENCES = [
  {
    for: "Housing Associations",
    icon: <SvgHA />,
    points: [
      "Upload SoV, FRA, and FRAEW documents in one place",
      "Track fire risk and cladding status across your entire portfolio",
      "Prepare submission-ready documentation for insurers",
      "Monitor remediation action progress and compliance",
    ],
  },
  {
    for: "Underwriters",
    icon: <SvgUnderwriter />,
    points: [
      "Receive structured, enriched data with every submission",
      "View block-level cladding, EPC, and fire risk ratings instantly",
      "Compare risk profiles across multiple housing associations",
      "Reduce manual data gathering and speed up pricing decisions",
    ],
  },
];

// ─── SVG icons ────────────────────────────────────────────────────────────────
function SvgSchedule() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14,2 14,8 20,8"/>
      <line x1="8" y1="13" x2="16" y2="13"/>
      <line x1="8" y1="17" x2="12" y2="17"/>
    </svg>
  );
}
function SvgFire() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2c0 6-6 6-6 12a6 6 0 0 0 12 0c0-3-2-5-2-8"/>
      <path d="M12 2c0 4 3 5 3 9a3 3 0 0 1-6 0c0-3 3-5 3-9z"/>
    </svg>
  );
}
function SvgBuilding() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="8" height="18"/><rect x="13" y="8" width="8" height="13"/>
      <line x1="3" y1="21" x2="21" y2="21"/>
      <line x1="7" y1="7" x2="7" y2="7"/><line x1="7" y1="11" x2="7" y2="11"/><line x1="7" y1="15" x2="7" y2="15"/>
      <line x1="17" y1="12" x2="17" y2="12"/><line x1="17" y1="16" x2="17" y2="16"/>
    </svg>
  );
}
function SvgExport() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6,9 12,15 18,9"/>
      <path d="M12 3v12M3 17v2a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-2"/>
    </svg>
  );
}
function SvgMap() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="3,6 9,3 15,6 21,3 21,18 15,21 9,18 3,21"/>
      <line x1="9" y1="3" x2="9" y2="18"/><line x1="15" y1="6" x2="15" y2="21"/>
    </svg>
  );
}
function SvgShield() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      <polyline points="9,12 11,14 15,10"/>
    </svg>
  );
}
function SvgHA() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
      <polyline points="9,22 9,12 15,12 15,22"/>
    </svg>
  );
}
function SvgUnderwriter() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
      <line x1="8" y1="21" x2="16" y2="21"/>
      <line x1="12" y1="17" x2="12" y2="21"/>
    </svg>
  );
}
function SvgCheck() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke={C.blue} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="2,8 6,12 14,4"/>
    </svg>
  );
}
function SvgArrow() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="3" y1="9" x2="15" y2="9"/>
      <polyline points="10,4 15,9 10,14"/>
    </svg>
  );
}

// ─── Scroll-reveal hook ───────────────────────────────────────────────────────
function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".equi-reveal");
    const io = new IntersectionObserver(
      entries => entries.forEach(e => {
        if (e.isIntersecting) { e.target.classList.add("visible"); io.unobserve(e.target); }
      }),
      { threshold: 0.12 }
    );
    els.forEach(el => io.observe(el));
    return () => io.disconnect();
  }, []);
}

// ─── Marquee bar ──────────────────────────────────────────────────────────────
function MarqueeBar() {
  // Duplicate items so the seam is invisible
  const doubled = [...MARQUEE_ITEMS, ...MARQUEE_ITEMS];
  return (
    <section style={{
      background: C.navyLight,
      borderTop: "1px solid rgba(148,163,184,0.08)",
      borderBottom: "1px solid rgba(148,163,184,0.08)",
      overflow: "hidden",
      padding: "22px 0",
    }}>
      {/* Fade edges */}
      <div style={{ position: "relative" }}>
        <div style={{
          position: "absolute", left: 0, top: 0, bottom: 0, width: 120,
          background: `linear-gradient(90deg, ${C.navyLight}, transparent)`,
          zIndex: 1, pointerEvents: "none",
        }} />
        <div style={{
          position: "absolute", right: 0, top: 0, bottom: 0, width: 120,
          background: `linear-gradient(270deg, ${C.navyLight}, transparent)`,
          zIndex: 1, pointerEvents: "none",
        }} />

        <div style={{
          display: "flex",
          width: "max-content",
          animation: "equi-marquee 36s linear infinite",
        }}>
          {doubled.map(({ icon, text }, i) => (
            <div key={i} style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 9,
              padding: "7px 22px",
              margin: "0 6px",
              borderRadius: 99,
              background: "rgba(37,99,235,0.07)",
              border: "1px solid rgba(37,99,235,0.14)",
              whiteSpace: "nowrap",
            }}>
              <span style={{ fontSize: 15 }}>{icon}</span>
              <span style={{
                fontSize: 13,
                fontWeight: 500,
                color: "#93c5fd",
                fontFamily: "Inter, sans-serif",
                letterSpacing: "0.01em",
              }}>{text}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Reusable components ──────────────────────────────────────────────────────
function Tag({ label, blue }) {
  return (
    <span style={{
      display: "inline-block",
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: "0.07em",
      textTransform: "uppercase",
      padding: "3px 10px",
      borderRadius: 99,
      background: blue ? C.bluePale : "#f1f5f9",
      color: blue ? C.blue : C.slate,
    }}>
      {label}
    </span>
  );
}

// ─── Dashboard mockup card (hero visual) ─────────────────────────────────────
function DashboardCard() {
  const rows = [
    { ref: "BLK-001", address: "Cathcart Road, Glasgow",   units: 24, rag: "green",  risk: "Low"    },
    { ref: "BLK-014", address: "Mosspark Blvd, Glasgow",   units: 18, rag: "amber",  risk: "Medium" },
    { ref: "BLK-027", address: "Govanhill St, Glasgow",    units: 31, rag: "red",    risk: "High"   },
    { ref: "BLK-042", address: "Pollokshields East, GL",   units: 12, rag: "green",  risk: "Low"    },
    { ref: "BLK-058", address: "Crosshill Ave, Glasgow",   units: 9,  rag: "amber",  risk: "Medium" },
  ];
  const ragColor = { green: "#10b981", amber: "#f59e0b", red: "#ef4444" };
  const ragBg    = { green: "#d1fae5", amber: "#fef3c7", red: "#fee2e2" };

  return (
    <div style={{
      background: "rgba(15,23,42,0.85)",
      backdropFilter: "blur(12px)",
      border: "1px solid rgba(148,163,184,0.12)",
      borderRadius: 16,
      overflow: "hidden",
      boxShadow: "0 32px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(37,99,235,0.15)",
      width: "100%",
      maxWidth: 560,
    }}>
      {/* Title bar */}
      <div style={{
        padding: "14px 20px",
        borderBottom: "1px solid rgba(148,163,184,0.1)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#ef4444" }} />
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#f59e0b" }} />
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#10b981" }} />
          <span style={{ marginLeft: 8, fontSize: 12, color: "#64748b", fontFamily: "Inter, sans-serif" }}>
            Portfolio Dashboard — Cathcart Demo
          </span>
        </div>
        <Tag label="Live" blue />
      </div>

      {/* Summary stats */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 1,
        background: "rgba(148,163,184,0.08)",
        borderBottom: "1px solid rgba(148,163,184,0.1)",
      }}>
        {[
          { v: "971", l: "Units" },
          { v: "156", l: "Blocks" },
          { v: "83%", l: "Enriched" },
        ].map(({ v, l }) => (
          <div key={l} style={{
            padding: "14px 16px",
            background: "rgba(15,23,42,0.6)",
            textAlign: "center",
          }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: C.white, fontFamily: "Inter, sans-serif", letterSpacing: "-0.03em" }}>{v}</div>
            <div style={{ fontSize: 11, color: "#64748b", fontFamily: "Inter, sans-serif", marginTop: 2 }}>{l}</div>
          </div>
        ))}
      </div>

      {/* Table */}
      <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "Inter, sans-serif" }}>
        <thead>
          <tr style={{ background: "rgba(148,163,184,0.06)" }}>
            {["Block Ref", "Address", "Units", "Risk"].map(h => (
              <th key={h} style={{
                padding: "8px 14px",
                fontSize: 11,
                fontWeight: 600,
                color: "#64748b",
                textAlign: "left",
                letterSpacing: "0.05em",
                textTransform: "uppercase",
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.ref} style={{
              borderTop: "1px solid rgba(148,163,184,0.07)",
              background: i % 2 === 0 ? "transparent" : "rgba(148,163,184,0.03)",
            }}>
              <td style={{ padding: "9px 14px", fontSize: 12, color: C.blueMid, fontWeight: 600 }}>{r.ref}</td>
              <td style={{ padding: "9px 14px", fontSize: 12, color: "#94a3b8", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.address}</td>
              <td style={{ padding: "9px 14px", fontSize: 12, color: "#cbd5e1", textAlign: "center" }}>{r.units}</td>
              <td style={{ padding: "9px 14px" }}>
                <span style={{
                  display: "inline-block",
                  fontSize: 11,
                  fontWeight: 700,
                  padding: "2px 9px",
                  borderRadius: 99,
                  background: ragBg[r.rag],
                  color: ragColor[r.rag],
                }}>{r.risk}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Main landing page ────────────────────────────────────────────────────────
export default function Landingpage({ onGetStarted }) {
  const [scrolled, setScrolled] = useState(false);
  const [activeAudience, setActiveAudience] = useState(0);

  useReveal();

  useEffect(() => {
    // Inject global keyframe CSS once
    const id = "equi-global-css";
    if (!document.getElementById(id)) {
      const s = document.createElement("style");
      s.id = id;
      s.textContent = GLOBAL_CSS;
      document.head.appendChild(s);
    }
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div style={{
      fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
      color: C.text,
      background: C.white,
      overflowX: "hidden",
    }}>

      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <header style={{
        position: "sticky",
        top: 0,
        zIndex: 100,
        background: scrolled ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.0)",
        backdropFilter: scrolled ? "blur(12px)" : "none",
        borderBottom: scrolled ? `1px solid ${C.border}` : "1px solid transparent",
        transition: "all 0.3s ease",
      }}>
        <div style={{
          maxWidth: 1200,
          margin: "0 auto",
          padding: "0 32px",
          height: 68,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <img src="/logo.png" alt="EquiRisk" style={{ height: 30, width: "auto" }} />
          </div>

          <nav style={{ display: "flex", alignItems: "center", gap: 32 }}>
            {["Features", "How it Works", "About"].map(item => (
              <a key={item} href={`#${item.toLowerCase().replace(/ /g, "-")}`} style={{
                fontSize: 14,
                fontWeight: 500,
                color: scrolled ? C.textMid : C.white,
                textDecoration: "none",
                transition: "color 0.2s",
                opacity: 0.85,
              }}
              onMouseEnter={e => e.currentTarget.style.opacity = "1"}
              onMouseLeave={e => e.currentTarget.style.opacity = "0.85"}
              >{item}</a>
            ))}
            <button
              onClick={onGetStarted}
              style={{
                background: C.blue,
                color: C.white,
                border: "none",
                borderRadius: 8,
                padding: "9px 22px",
                fontSize: 14,
                fontWeight: 600,
                cursor: "pointer",
                letterSpacing: "-0.01em",
                transition: "background 0.2s, transform 0.15s",
                boxShadow: "0 1px 6px rgba(37,99,235,0.35)",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = "#1d4ed8"; e.currentTarget.style.transform = "translateY(-1px)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = C.blue;    e.currentTarget.style.transform = "translateY(0)"; }}
            >
              Get Started
            </button>
          </nav>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <section style={{
        background: C.navyMid,
        position: "relative",
        overflow: "hidden",
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        marginTop: -68,
        paddingTop: 68,
      }}>
        {/* Grid pattern */}
        <div style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(rgba(37,99,235,0.06) 1px, transparent 1px),
            linear-gradient(90deg, rgba(37,99,235,0.06) 1px, transparent 1px)
          `,
          backgroundSize: "52px 52px",
          maskImage: "radial-gradient(ellipse 80% 80% at 50% 50%, black 40%, transparent 100%)",
        }} />
        {/* Blue glow */}
        <div style={{
          position: "absolute",
          width: 700,
          height: 700,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(37,99,235,0.18) 0%, transparent 70%)",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -60%)",
          pointerEvents: "none",
        }} />

        <div style={{
          maxWidth: 1200,
          margin: "0 auto",
          padding: "80px 32px",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 64,
          alignItems: "center",
          position: "relative",
          zIndex: 1,
          width: "100%",
        }}>
          {/* Left */}
          <div>
            <div style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              background: "rgba(37,99,235,0.15)",
              border: "1px solid rgba(37,99,235,0.3)",
              borderRadius: 99,
              padding: "5px 14px",
              marginBottom: 28,
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: "50%", background: C.blue,
                animation: "equi-pulse-dot 2s ease-in-out infinite",
              }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: "#93c5fd", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                UK Social Housing InsurTech
              </span>
            </div>

            <h1 style={{
              fontSize: "clamp(36px, 4vw, 56px)",
              fontWeight: 800,
              color: C.white,
              lineHeight: 1.1,
              letterSpacing: "-0.04em",
              margin: "0 0 24px",
            }}>
              AI-Powered Risk
              <br />
              <span style={{ color: C.blueMid }}>Intelligence</span> for
              <br />
              Social Housing
            </h1>

            <p style={{
              fontSize: 18,
              color: "#94a3b8",
              lineHeight: 1.7,
              margin: "0 0 40px",
              maxWidth: 440,
            }}>
              EquiRisk ingests Schedule of Values, FRA, and FRAEW documents to deliver
              enriched, submission-ready risk reports for housing associations and underwriters.
            </p>

            <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              <button
                onClick={onGetStarted}
                style={{
                  background: C.blue,
                  color: C.white,
                  border: "none",
                  borderRadius: 10,
                  padding: "14px 30px",
                  fontSize: 15,
                  fontWeight: 600,
                  cursor: "pointer",
                  letterSpacing: "-0.01em",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  boxShadow: "0 4px 20px rgba(37,99,235,0.4)",
                  transition: "all 0.2s",
                }}
                onMouseEnter={e => { e.currentTarget.style.background = "#1d4ed8"; e.currentTarget.style.transform = "translateY(-2px)"; }}
                onMouseLeave={e => { e.currentTarget.style.background = C.blue;    e.currentTarget.style.transform = "translateY(0)"; }}
              >
                Launch Platform <SvgArrow />
              </button>
              <button
                style={{
                  background: "rgba(255,255,255,0.06)",
                  color: C.white,
                  border: "1px solid rgba(255,255,255,0.14)",
                  borderRadius: 10,
                  padding: "14px 30px",
                  fontSize: 15,
                  fontWeight: 500,
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
                onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.1)"}
                onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,0.06)"}
              >
                Learn More
              </button>
            </div>

            {/* Trust line */}
            <div style={{ display: "flex", alignItems: "center", gap: 20, marginTop: 40 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <SvgCheck />
                <span style={{ fontSize: 13, color: "#64748b" }}>FCA-compliant data flows</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <SvgCheck />
                <span style={{ fontSize: 13, color: "#64748b" }}>OS data enrichment</span>
              </div>
            </div>
          </div>

          {/* Right — Dashboard mockup */}
          <div style={{
            display: "flex",
            justifyContent: "center",
            animation: "equi-float 6s ease-in-out infinite",
          }}>
            <DashboardCard />
          </div>
        </div>

        {/* Bottom fade */}
        <div style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 80,
          background: "linear-gradient(to bottom, transparent, rgba(255,255,255,0.03))",
        }} />
      </section>

      {/* ── Capability marquee ──────────────────────────────────────────── */}
      <MarqueeBar />

      {/* ── Features ────────────────────────────────────────────────────── */}
      <section id="features" style={{
        background: C.surface,
        padding: "100px 32px",
      }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div className="equi-reveal" style={{ textAlign: "center", marginBottom: 64 }}>
            <Tag label="Platform Capabilities" />
            <h2 style={{
              fontSize: "clamp(28px, 3vw, 42px)",
              fontWeight: 800,
              color: C.text,
              letterSpacing: "-0.04em",
              margin: "16px 0 16px",
            }}>
              Everything you need for housing risk
            </h2>
            <p style={{
              fontSize: 17,
              color: C.slate,
              maxWidth: 520,
              margin: "0 auto",
              lineHeight: 1.7,
            }}>
              From raw Excel schedules to structured underwriting submissions — Quinn handles the entire data pipeline.
            </p>
          </div>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 24,
          }}>
            {FEATURES.map(({ icon, title, desc, tag }, fi) => (
              <div
                key={title}
                className={`equi-reveal equi-reveal-delay-${fi + 1}`}
                style={{
                  background: C.white,
                  border: `1px solid ${C.border}`,
                  borderRadius: 16,
                  padding: "28px 28px 32px",
                  transition: "box-shadow 0.25s, transform 0.25s, border-color 0.25s",
                  cursor: "default",
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.boxShadow = "0 12px 40px rgba(37,99,235,0.1)";
                  e.currentTarget.style.transform = "translateY(-3px)";
                  e.currentTarget.style.borderColor = "#bfdbfe";
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.boxShadow = "none";
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.borderColor = C.border;
                }}
              >
                <div style={{
                  width: 46,
                  height: 46,
                  borderRadius: 12,
                  background: C.blueXPale,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: C.blue,
                  marginBottom: 18,
                }}>{icon}</div>
                <div style={{ marginBottom: 8 }}>
                  <Tag label={tag} blue={tag === "AI-powered"} />
                </div>
                <h3 style={{
                  fontSize: 17,
                  fontWeight: 700,
                  color: C.text,
                  letterSpacing: "-0.02em",
                  margin: "10px 0 10px",
                }}>{title}</h3>
                <p style={{ fontSize: 14, color: C.slate, lineHeight: 1.65 }}>{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ────────────────────────────────────────────────── */}
      <section id="how-it-works" style={{
        background: C.white,
        padding: "100px 32px",
        borderTop: `1px solid ${C.border}`,
      }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div className="equi-reveal" style={{ textAlign: "center", marginBottom: 72 }}>
            <Tag label="How it Works" />
            <h2 style={{
              fontSize: "clamp(28px, 3vw, 42px)",
              fontWeight: 800,
              color: C.text,
              letterSpacing: "-0.04em",
              margin: "16px 0 16px",
            }}>
              Three steps to underwriting-ready data
            </h2>
            <p style={{ fontSize: 17, color: C.slate, maxWidth: 480, margin: "0 auto", lineHeight: 1.7 }}>
              Quinn eliminates manual data work — from raw documents to structured risk intelligence.
            </p>
          </div>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 0,
            position: "relative",
          }}>
            {/* Connecting line */}
            <div style={{
              position: "absolute",
              top: 36,
              left: "16.5%",
              right: "16.5%",
              height: 1,
              background: `linear-gradient(90deg, ${C.blue}, ${C.bluePale}, ${C.blue})`,
              opacity: 0.3,
            }} />

            {HOW_STEPS.map(({ n, title, desc }, i) => (
              <div key={n} className={`equi-reveal equi-reveal-delay-${i + 1}`} style={{ padding: "0 32px", textAlign: "center", position: "relative" }}>
                <div style={{
                  width: 72,
                  height: 72,
                  borderRadius: "50%",
                  background: i === 1 ? C.blue : C.blueXPale,
                  border: `2px solid ${i === 1 ? C.blue : C.bluePale}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 28px",
                  position: "relative",
                  zIndex: 1,
                  boxShadow: i === 1 ? "0 0 0 8px rgba(37,99,235,0.1)" : "none",
                }}>
                  <span style={{
                    fontSize: 20,
                    fontWeight: 800,
                    color: i === 1 ? C.white : C.blue,
                    letterSpacing: "-0.02em",
                    fontFamily: "Inter, sans-serif",
                  }}>{n}</span>
                </div>
                <h3 style={{
                  fontSize: 19,
                  fontWeight: 700,
                  color: C.text,
                  letterSpacing: "-0.025em",
                  marginBottom: 12,
                }}>{title}</h3>
                <p style={{ fontSize: 14, color: C.slate, lineHeight: 1.7 }}>{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── About ───────────────────────────────────────────────────────── */}
      <section id="about" style={{
        background: C.navyMid,
        padding: "100px 32px",
        position: "relative",
        overflow: "hidden",
      }}>
        <div style={{
          position: "absolute",
          width: 500,
          height: 500,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(37,99,235,0.12) 0%, transparent 70%)",
          right: -100,
          bottom: -100,
          pointerEvents: "none",
        }} />

        <div style={{
          maxWidth: 1100,
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 80,
          alignItems: "center",
          position: "relative",
          zIndex: 1,
        }}>
          <div>
            <div className="equi-reveal">
            <Tag label="About EquiRisk" />
            <h2 style={{
              fontSize: "clamp(28px, 3vw, 42px)",
              fontWeight: 800,
              color: C.white,
              letterSpacing: "-0.04em",
              margin: "16px 0 20px",
              lineHeight: 1.15,
            }}>
              Making social housing insurance smarter
            </h2>
            <p style={{
              fontSize: 16,
              color: "#94a3b8",
              lineHeight: 1.75,
              marginBottom: 20,
            }}>
              EquiRisk was built to solve a real problem: housing associations hold thousands of
              properties but struggle to produce accurate, structured risk data for insurers.
              Manual processes are slow, error-prone, and miss critical fire safety signals.
            </p>
            <p style={{
              fontSize: 16,
              color: "#94a3b8",
              lineHeight: 1.75,
              marginBottom: 36,
            }}>
              Our platform — powered by Quinn, our AI engine — ingests SoV spreadsheets and
              PDF risk assessments to produce enriched portfolio data that underwriters can
              actually use. We integrate Ordnance Survey UPRN data, EPC ratings, and building
              geometry to give every block a complete risk profile.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[
                "Built for UK social housing — NROSH-aligned property data",
                "Powered by AWS Bedrock and Claude AI for document intelligence",
                "Integrates OS Places, EPC, and FRAEW cladding registers",
                "Used by housing associations managing hundreds of blocks",
              ].map(point => (
                <div key={point} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                  <div style={{ marginTop: 1, flexShrink: 0 }}><SvgCheck /></div>
                  <span style={{ fontSize: 14, color: "#cbd5e1", lineHeight: 1.6 }}>{point}</span>
                </div>
              ))}
            </div>
          </div>{/* end equi-reveal */}
          </div>{/* end left column */}

          {/* Metrics panel */}
          <div className="equi-reveal equi-reveal-delay-2" style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 16,
          }}>
            {[
              { v: "< 60s",  l: "SoV ingestion time",      sub: "From upload to structured portfolio" },
              { v: "64",     l: "Columns in Doc B",         sub: "Per-block enriched report" },
              { v: "35+",    l: "SoV property attributes",  sub: "Extracted and validated" },
              { v: "OS API", l: "UPRN-linked geocoding",    sub: "Every unit, every address" },
            ].map(({ v, l, sub }) => (
              <div key={l} style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(148,163,184,0.1)",
                borderRadius: 14,
                padding: "24px 22px",
              }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: C.blueMid, letterSpacing: "-0.04em", marginBottom: 4 }}>{v}</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: C.white, marginBottom: 4 }}>{l}</div>
                <div style={{ fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>{sub}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── For HA / Underwriters ────────────────────────────────────────── */}
      <section style={{
        background: C.surface,
        padding: "100px 32px",
        borderTop: `1px solid ${C.border}`,
      }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <Tag label="Who it's for" />
            <h2 style={{
              fontSize: "clamp(28px, 3vw, 42px)",
              fontWeight: 800,
              color: C.text,
              letterSpacing: "-0.04em",
              margin: "16px 0",
            }}>Built for both sides of the market</h2>
          </div>

          {/* Toggle */}
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 48 }}>
            <div style={{
              display: "flex",
              background: C.white,
              border: `1px solid ${C.border}`,
              borderRadius: 10,
              padding: 4,
              gap: 4,
            }}>
              {AUDIENCES.map(({ for: label }, i) => (
                <button
                  key={label}
                  onClick={() => setActiveAudience(i)}
                  style={{
                    padding: "10px 24px",
                    borderRadius: 8,
                    border: "none",
                    fontSize: 14,
                    fontWeight: 600,
                    cursor: "pointer",
                    background: activeAudience === i ? C.blue : "transparent",
                    color: activeAudience === i ? C.white : C.slate,
                    transition: "all 0.2s",
                  }}
                >{label}</button>
              ))}
            </div>
          </div>

          <div style={{
            background: C.white,
            border: `1px solid ${C.border}`,
            borderRadius: 20,
            padding: "48px 52px",
            display: "grid",
            gridTemplateColumns: "auto 1fr",
            gap: 52,
            alignItems: "start",
          }}>
            <div style={{
              width: 72,
              height: 72,
              borderRadius: 18,
              background: C.blueXPale,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: C.blue,
              flexShrink: 0,
            }}>
              {AUDIENCES[activeAudience].icon}
            </div>
            <div>
              <h3 style={{
                fontSize: 24,
                fontWeight: 800,
                color: C.text,
                letterSpacing: "-0.03em",
                marginBottom: 24,
              }}>
                For {AUDIENCES[activeAudience].for}
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px 32px" }}>
                {AUDIENCES[activeAudience].points.map(pt => (
                  <div key={pt} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <div style={{ marginTop: 2, flexShrink: 0 }}><SvgCheck /></div>
                    <span style={{ fontSize: 15, color: C.textMid, lineHeight: 1.6 }}>{pt}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA banner ──────────────────────────────────────────────────── */}
      <section style={{
        background: `linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #1e3a8a 100%)`,
        padding: "100px 32px",
        textAlign: "center",
        position: "relative",
        overflow: "hidden",
      }}>
        <div style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(rgba(37,99,235,0.07) 1px, transparent 1px),
            linear-gradient(90deg, rgba(37,99,235,0.07) 1px, transparent 1px)
          `,
          backgroundSize: "40px 40px",
        }} />
        <div style={{ position: "relative", zIndex: 1 }}>
          <h2 style={{
            fontSize: "clamp(32px, 4vw, 52px)",
            fontWeight: 800,
            color: C.white,
            letterSpacing: "-0.04em",
            marginBottom: 20,
          }}>
            Ready to insure smarter?
          </h2>
          <p style={{
            fontSize: 18,
            color: "#93c5fd",
            marginBottom: 44,
            maxWidth: 480,
            margin: "0 auto 44px",
            lineHeight: 1.7,
          }}>
            Join housing associations and underwriters already using EquiRisk to transform
            portfolio risk data into clear, actionable intelligence.
          </p>
          <button
            onClick={onGetStarted}
            style={{
              background: C.white,
              color: C.blue,
              border: "none",
              borderRadius: 10,
              padding: "16px 40px",
              fontSize: 16,
              fontWeight: 700,
              cursor: "pointer",
              letterSpacing: "-0.01em",
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              transition: "all 0.2s",
              boxShadow: "0 8px 30px rgba(0,0,0,0.3)",
            }}
            onMouseEnter={e => { e.currentTarget.style.transform = "translateY(-3px)"; e.currentTarget.style.boxShadow = "0 14px 40px rgba(0,0,0,0.4)"; }}
            onMouseLeave={e => { e.currentTarget.style.transform = "translateY(0)";    e.currentTarget.style.boxShadow = "0 8px 30px rgba(0,0,0,0.3)"; }}
          >
            Launch EquiRisk <SvgArrow />
          </button>
        </div>
      </section>

      {/* ── Contact ─────────────────────────────────────────────────────── */}
      <section style={{
        background: C.white,
        padding: "100px 32px",
        borderTop: `1px solid ${C.border}`,
      }}>
        <div style={{
          maxWidth: 680,
          margin: "0 auto",
          textAlign: "center",
        }}>
          <Tag label="Contact" />
          <h2 style={{
            fontSize: "clamp(28px, 3vw, 40px)",
            fontWeight: 800,
            color: C.text,
            letterSpacing: "-0.04em",
            margin: "16px 0 12px",
          }}>Get in touch</h2>
          <p style={{ fontSize: 16, color: C.slate, marginBottom: 44 }}>
            Reach us at{" "}
            <a href="mailto:Ewan@equirisk.ai" style={{ color: C.blue, textDecoration: "none", fontWeight: 600 }}>
              Ewan@equirisk.ai
            </a>
            {" "}or fill in the form below.
          </p>

          <form onSubmit={e => e.preventDefault()} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {[
              { placeholder: "Your name", type: "text" },
              { placeholder: "Email address", type: "email" },
              { placeholder: "Organisation", type: "text" },
            ].map(({ placeholder, type }) => (
              <input
                key={placeholder}
                type={type}
                placeholder={placeholder}
                style={{
                  width: "100%",
                  padding: "14px 18px",
                  border: `1px solid ${C.border}`,
                  borderRadius: 10,
                  fontSize: 15,
                  color: C.text,
                  background: C.surface,
                  outline: "none",
                  fontFamily: "Inter, sans-serif",
                  transition: "border-color 0.2s",
                  boxSizing: "border-box",
                }}
                onFocus={e => e.target.style.borderColor = C.blue}
                onBlur={e => e.target.style.borderColor = C.border}
              />
            ))}
            <textarea
              placeholder="How can we help?"
              rows={5}
              style={{
                width: "100%",
                padding: "14px 18px",
                border: `1px solid ${C.border}`,
                borderRadius: 10,
                fontSize: 15,
                color: C.text,
                background: C.surface,
                outline: "none",
                fontFamily: "Inter, sans-serif",
                resize: "vertical",
                transition: "border-color 0.2s",
                boxSizing: "border-box",
              }}
              onFocus={e => e.target.style.borderColor = C.blue}
              onBlur={e => e.target.style.borderColor = C.border}
            />
            <button
              type="submit"
              style={{
                background: C.blue,
                color: C.white,
                border: "none",
                borderRadius: 10,
                padding: "14px",
                fontSize: 15,
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.2s",
                boxShadow: "0 2px 12px rgba(37,99,235,0.3)",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = "#1d4ed8"; e.currentTarget.style.transform = "translateY(-1px)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = C.blue;    e.currentTarget.style.transform = "translateY(0)"; }}
            >
              Send Message
            </button>
          </form>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────── */}
      <footer style={{
        background: C.navyMid,
        borderTop: "1px solid rgba(148,163,184,0.1)",
        padding: "48px 32px 36px",
      }}>
        <div style={{
          maxWidth: 1200,
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 40,
          marginBottom: 40,
        }}>
          <div>
            <img src="/logo.png" alt="EquiRisk" style={{ height: 28, width: "auto", marginBottom: 14, filter: "brightness(0) invert(1)" }} />
            <p style={{ fontSize: 13, color: "#64748b", lineHeight: 1.7, maxWidth: 240 }}>
              AI-powered risk intelligence for UK social housing insurance. Built for housing associations and underwriters.
            </p>
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 14 }}>Platform</div>
            {["Portfolio Ingestion", "FRA Analysis", "FRAEW Analysis", "Doc A & B Export", "OS Enrichment"].map(link => (
              <div key={link} style={{ marginBottom: 8 }}>
                <a href="#" style={{ fontSize: 13, color: "#94a3b8", textDecoration: "none" }}
                  onMouseEnter={e => e.target.style.color = C.white}
                  onMouseLeave={e => e.target.style.color = "#94a3b8"}
                >{link}</a>
              </div>
            ))}
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 14 }}>Company</div>
            {["About EquiRisk", "Contact", "Privacy Policy"].map(link => (
              <div key={link} style={{ marginBottom: 8 }}>
                <a href="#" style={{ fontSize: 13, color: "#94a3b8", textDecoration: "none" }}
                  onMouseEnter={e => e.target.style.color = C.white}
                  onMouseLeave={e => e.target.style.color = "#94a3b8"}
                >{link}</a>
              </div>
            ))}
            <div style={{ marginTop: 20, fontSize: 13, color: "#64748b" }}>
              <a href="mailto:Ewan@equirisk.ai" style={{ color: C.blueMid, textDecoration: "none" }}>Ewan@equirisk.ai</a>
            </div>
          </div>
        </div>

        <div style={{
          borderTop: "1px solid rgba(148,163,184,0.1)",
          paddingTop: 24,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}>
          <span style={{ fontSize: 12, color: "#475569" }}>© 2026 EquiRisk. All rights reserved.</span>
          <span style={{ fontSize: 12, color: "#334155" }}>UK Social Housing InsurTech</span>
        </div>
      </footer>
    </div>
  );
}
