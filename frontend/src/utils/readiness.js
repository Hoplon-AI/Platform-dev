export function computeReadiness(row) {
    // Core fields we want for underwriting + mapping
    const required = [
      "address_line_1",
      "postcode",
      "city",
      "latitude",
      "longitude",
      "sum_insured",
    ];
  
    // A row might use different headers — map them:
    const get = (k) => {
      switch (k) {
        case "address_line_1":
          return row.address_line_1 ?? row.address1 ?? row.address ?? row["address line 1"];
        case "postcode":
          return row.post_code ?? row.postcode ?? row.Postcode ?? row["post code"];
        case "city":
          return row.city ?? row.town ?? row.City;
        case "latitude":
          return row.latitude ?? row.lat ?? row.Latitude ?? row.LATITUDE;
        case "longitude":
          return row.longitude ?? row.lon ?? row.lng ?? row.Longitude ?? row.LONGITUDE;
        case "sum_insured":
          return (
            row.sum_insured ??
            row.sumInsured ??
            row.SumInsured ??
            row["sum insured"] ??
            row["Sum Insured"]
          );
        default:
          return row[k];
      }
    };
  
    const missing = [];
    required.forEach((k) => {
      const v = get(k);
      const empty = v == null || String(v).trim() === "";
      if (empty) missing.push(k);
    });
  
    // Readiness scoring:
    // start 100, penalize missing core fields (weighted)
    // lat/lon are important → heavier penalty
    let score = 100;
  
    const weights = {
      address_line_1: 10,
      postcode: 10,
      city: 10,
      latitude: 25,
      longitude: 25,
      sum_insured: 20,
    };
  
    missing.forEach((k) => {
      score -= weights[k] ?? 10;
    });
  
    score = Math.max(0, Math.min(100, Math.round(score)));
  
    return { score, missing };
  }
  
  export function readinessBand(score) {
    if (score >= 80) return "Green";
    if (score >= 50) return "Yellow";
    return "Red";
  }
  
  export function readinessColor(score) {
    // Use the same colours you described
    if (score >= 80) return "#10b981"; // green
    if (score >= 50) return "#f59e0b"; // yellow
    return "#ef4444"; // red
  }
