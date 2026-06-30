// Shared portfolio breakdown helpers used by the Portfolio Overview KPIs and the
// standalone Portfolio Insights page. Pure functions over the SoV `properties` array.

export const inferPortfolioClass = (property) => {
  const propertyType = String(property?.property_type ?? property?.type ?? "").toLowerCase();
  const builtForm = String(property?.built_form ?? "").toLowerCase();
  const address = String(
    property?.address_line_1 ?? property?.address ?? property?.property_reference ?? ""
  ).toLowerCase();

  const combined = `${propertyType} ${builtForm} ${address}`;

  if (
    propertyType.includes("lock up") ||
    propertyType.includes("lockup") ||
    propertyType.includes("office") ||
    propertyType.includes("commercial") ||
    propertyType.includes("mixed use")
  ) {
    return "Other";
  }

  if (
    combined.includes("flat") ||
    combined.includes("apartment") ||
    combined.includes("maisonette") ||
    combined.includes("tenement")
  ) {
    return "Flats";
  }

  if (
    combined.includes("house") ||
    combined.includes("bungalow") ||
    combined.includes("terrace") ||
    combined.includes("semi") ||
    combined.includes("detached")
  ) {
    return "Houses";
  }

  return "Other";
};

export const buildBreakdown = (items, keyFn, valueFn) => {
  const grouped = new Map();

  (items || []).forEach((item) => {
    const key = keyFn(item) || "Not recorded";
    if (!grouped.has(key)) {
      grouped.set(key, {
        label: key,
        count: 0,
        totalValue: 0,
      });
    }

    const entry = grouped.get(key);
    entry.count += 1;
    entry.totalValue += Number(valueFn(item) || 0);
  });

  return Array.from(grouped.values()).sort((a, b) => {
    if (b.totalValue !== a.totalValue) return b.totalValue - a.totalValue;
    return b.count - a.count;
  });
};

// Lightweight block grouping for the "By block reference" table — groups by the
// same key precedence the dashboard uses, returning only label/count/totalValue.
export const buildBlockRows = (properties) => {
  const rows = buildBreakdown(
    properties,
    (property) =>
      property.block_reference ||
      property.parent_uprn ||
      property.uprn ||
      property.property_reference ||
      property.id ||
      "Unassigned block",
    (property) => property.sum_insured
  );
  return rows.map((row) => ({ ...row, label: row.label || "Unassigned block" }));
};

export const ageBandKey = (property) => {
  if (property.year_of_build) {
    const year = Number(property.year_of_build);
    if (Number.isFinite(year)) {
      if (year < 1919) return "Pre-1919";
      if (year < 1945) return "1920-1944";
      if (year < 1980) return "1945-1979";
      if (year < 2001) return "1980-2000";
      return "2001+";
    }
  }
  return "Unknown";
};
