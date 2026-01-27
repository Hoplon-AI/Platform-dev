import Papa from "papaparse";

/**
 * Parse CSV file and standardise rows
 */
export function parseCSVFile(file, onComplete, onError) {
  Papa.parse(file, {
    header: true,
    skipEmptyLines: true,

    complete: (results) => {
      if (!results.data || !results.data.length) {
        onError?.("No rows detected in CSV.");
        return;
      }

      const rawColumns = Object.keys(results.data[0] || {});
      const columns = rawColumns.map((c) => c.trim());

      const data = results.data.map((row) => {
        const cleanRow = {};
        columns.forEach((col) => {
          cleanRow[col] = (row[col] ?? "").toString().trim();
        });
        return cleanRow;
      });

      onComplete({
        columns,
        data,
        row_count: data.length,
      });
    },

    error: (err) => onError?.(err.message),
  });
}

/**
 * Produce ingestion quality summary
 */
export function getIngestionSummary(uploadedData) {
  if (!uploadedData?.data?.length) return null;

  const colsLower = uploadedData.columns.map((c) => c.toLowerCase());

  const postcodeIndex = colsLower.findIndex((c) => c.includes("postcode"));
  const addressIndex = colsLower.findIndex((c) => c.includes("address"));
  const sumIndex = colsLower.findIndex(
    (c) => c.includes("sum") && c.includes("insured")
  );

  let missingAddress = 0;
  let missingPostcode = 0;

  uploadedData.data.forEach((row) => {
    if (addressIndex !== -1) {
      const key = uploadedData.columns[addressIndex];
      if (!row[key]) missingAddress += 1;
    }

    if (postcodeIndex !== -1) {
      const key = uploadedData.columns[postcodeIndex];
      if (!row[key]) missingPostcode += 1;
    }
  });

  return {
    rowCount: uploadedData.row_count,
    columnCount: uploadedData.columns.length,
    hasAddress: addressIndex !== -1,
    hasPostcode: postcodeIndex !== -1,
    hasSumInsured: sumIndex !== -1,
    missingAddress,
    missingPostcode,
  };
}

/**
 * Snapshot portfolio metrics from uploaded CSV
 */
export function getPortfolioSnapshot(uploadedData) {
  if (!uploadedData?.data?.length) return null;

  const rows = uploadedData.data;
  const colsLower = uploadedData.columns.map((c) => c.toLowerCase());

  const sumColIndex = colsLower.findIndex(
    (c) => c.includes("sum") && c.includes("insured")
  );
  const postcodeIndex = colsLower.findIndex((c) => c.includes("postcode"));
  const addressIndex = colsLower.findIndex((c) => c.includes("address"));

  let totalValue = 0;
  let missingCore = 0;

  rows.forEach((row) => {
    if (sumColIndex !== -1) {
      const key = uploadedData.columns[sumColIndex];
      const raw = row[key];
      const numeric = parseFloat(String(raw).replace(/[^0-9.]/g, ""));
      if (!Number.isNaN(numeric)) totalValue += numeric;
    }

    const missingPostcode =
      postcodeIndex === -1 || !row[uploadedData.columns[postcodeIndex]];

    const missingAddress =
      addressIndex === -1 || !row[uploadedData.columns[addressIndex]];

    if (missingPostcode || missingAddress) missingCore += 1;
  });

  return {
    source: "Uploaded SOV",
    propertyCount: rows.length,
    totalValue: totalValue || null,
    missingCore,
  };
}