// Formatting and classification helpers for the ingestion landing page.

export const fmtInt = (value) => Number(value || 0).toLocaleString();

export const fmtMoney = (value) => {
  const n = Number(value || 0);
  if (n >= 1e9) return `£${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `£${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `£${Math.round(n / 1e3)}k`;
  return `£${n.toLocaleString()}`;
};

export const readinessBand = (score) => {
  if (score >= 80) return "green";
  if (score >= 50) return "amber";
  return "red";
};

export const typeLabel = (type) => {
  const t = (type || "").toUpperCase();
  if (t === "SOV") return "SoV";
  return t || "Doc";
};

export const fileFormat = (doc) => {
  const name = (doc.name || "").toLowerCase();
  if (name.endsWith(".csv")) return "csv";
  if (name.endsWith(".xlsx") || name.endsWith(".xls") || name.endsWith(".xlsm"))
    return "xls";
  if (name.endsWith(".pdf")) return "pdf";
  const t = (doc.type || "").toUpperCase();
  if (t === "SOV") return "xls";
  if (t === "FRA" || t === "FRAEW" || t === "FIRE") return "pdf";
  return "doc";
};

export const riskTone = (rating) => {
  const r = (rating || "").toLowerCase();
  if (/(high|substantial|intolerable|severe|\bred\b|p2|p3)/.test(r)) return "red";
  if (/(moderate|medium|tolerable|\bamber\b|p1)/.test(r)) return "amber";
  if (/(low|trivial|negligible|\bgreen\b|acceptable)/.test(r)) return "green";
  return "neutral";
};
