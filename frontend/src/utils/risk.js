/**
 * Map qualitative risk bands to numeric scores
 */
export const RISK_BAND_SCORE = {
  Low: 0.35,
  Medium: 0.55,
  High: 0.75,
  "Very High": 0.9,
};

/**
 * Single property risk score
 */
export function getRiskScore(property) {
  return RISK_BAND_SCORE[property.riskBand] ?? 0.55;
}

/**
 * Portfolio-level dashboard metrics
 */
export function computeDashboardMetrics(properties) {
  if (!properties?.length)
    return {
      totalValue: 0,
      propertyCount: 0,
      avgRiskScore: 0,
      riskLabel: "Low",
      flatRoofPct: 0,
      basementPct: 0,
      balconyPct: 0,
      combustibilityHotspots: 0,
      fireHotspots: 0,
      floodHotspots: 0,
      maintenanceIssues: 0,
    };

  const count = properties.length;

  let totalValue = 0;
  let riskSum = 0;
  let flatRoofCount = 0;
  let basementCount = 0;
  let balconyCount = 0;

  properties.forEach((p) => {
    totalValue += p.sumInsured || 0;
    riskSum += getRiskScore(p);

    if ((p.roofConstruction || "").toLowerCase().includes("flat"))
      flatRoofCount++;

    if (p.basementLocation && p.basementLocation.toLowerCase() !== "none")
      basementCount++;

    if ((p.propertyType || "").toLowerCase().includes("flat")) balconyCount++;
  });

  const avgRiskScore = riskSum / count;

  const riskLabel =
    avgRiskScore < 0.4 ? "Low" : avgRiskScore < 0.65 ? "Moderate" : "High";

  const combustibilityHotspots = Math.round(
    (properties.filter((p) =>
      (p.claddingType || p.wallConstruction || "")
        .toLowerCase()
        .includes("cladding")
    ).length /
      count) *
      100
  );

  const fireHotspots = Math.round(
    (properties.filter((p) =>
      (p.fireProtection || "").toLowerCase().includes("battery")
    ).length /
      count) *
      100
  );

  const floodHotspots = Math.round(
    (properties.filter((p) => (p.floodScore || 0) > 0.5).length / count) * 100
  );

  const maintenanceIssues = Math.round(
    (properties.filter((p) => (p.maintenanceScore || 0) < 6).length / count) * 100
  );

  return {
    totalValue,
    propertyCount: count,
    avgRiskScore,
    riskLabel,
    flatRoofPct: Math.round((flatRoofCount / count) * 100),
    basementPct: Math.round((basementCount / count) * 100),
    balconyPct: Math.round((balconyCount / count) * 100),
    combustibilityHotspots,
    fireHotspots,
    floodHotspots,
    maintenanceIssues,
  };
}
