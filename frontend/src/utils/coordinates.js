// Coordinate helpers: BNG↔WGS84 conversion, UK/OSGB bounds, and readiness banding.
import proj4 from "proj4";

// EPSG:27700 (British National Grid) -> EPSG:4326 (WGS84)
proj4.defs(
  "EPSG:27700",
  "+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 " +
    "+x_0=400000 +y_0=-100000 +ellps=airy " +
    "+towgs84=446.448,-125.157,542.06,0.15,0.247,0.842,-20.489 " +
    "+units=m +no_defs"
);

export const UK_LAT_BOUNDS = {
  min: 49.0,
  max: 61.5,
};

export const UK_LON_BOUNDS = {
  min: -8.8,
  max: 2.8,
};

export const OSGB_EASTING_BOUNDS = {
  min: 1,     // exclude 0: Number(null)=0, proj4(0,0) → lat≈49.7 lon≈-7.5 (Atlantic)
  max: 700000,
};

export const OSGB_NORTHING_BOUNDS = {
  min: 1,     // same fix — reject null/missing coordinates
  max: 1300000,
};

export const toNumberOrNull = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

export const looksLikeLatitude = (value) => {
  const n = Number(value);
  return (
    Number.isFinite(n) &&
    n >= UK_LAT_BOUNDS.min &&
    n <= UK_LAT_BOUNDS.max &&
    n !== 0
  );
};

export const looksLikeLongitude = (value) => {
  const n = Number(value);
  return (
    Number.isFinite(n) &&
    n >= UK_LON_BOUNDS.min &&
    n <= UK_LON_BOUNDS.max &&
    n !== 0
  );
};

export const looksLikeBritishNationalGrid = (easting, northing) => {
  const e = Number(easting);
  const n = Number(northing);

  return (
    Number.isFinite(e) &&
    Number.isFinite(n) &&
    e > 0 &&
    e <= OSGB_EASTING_BOUNDS.max &&
    n > 0 &&
    n <= OSGB_NORTHING_BOUNDS.max
  );
};

export const convertBritishNationalGridToLatLon = (easting, northing) => {
  try {
    if (!looksLikeBritishNationalGrid(easting, northing)) {
      return null;
    }

    const [lon, lat] = proj4("EPSG:27700", "EPSG:4326", [
      Number(easting),
      Number(northing),
    ]);

    if (!looksLikeLatitude(lat) || !looksLikeLongitude(lon)) {
      return null;
    }

    return { latitude: lat, longitude: lon };
  } catch (error) {
    console.warn("Failed to convert BNG to lat/lon:", error);
    return null;
  }
};

export const resolveCoordinates = (row) => {
  const directLatitude =
    toNumberOrNull(row.latitude) ??
    toNumberOrNull(row.lat) ??
    toNumberOrNull(row.location?.latitude) ??
    toNumberOrNull(row.__lat);

  const directLongitude =
    toNumberOrNull(row.longitude) ??
    toNumberOrNull(row.lon) ??
    toNumberOrNull(row.lng) ??
    toNumberOrNull(row.location?.longitude) ??
    toNumberOrNull(row.__lon);

  if (looksLikeLatitude(directLatitude) && looksLikeLongitude(directLongitude)) {
    return {
      latitude: directLatitude,
      longitude: directLongitude,
      coordinate_source: "direct_lat_lon",
    };
  }

  if (looksLikeLatitude(directLongitude) && looksLikeLongitude(directLatitude)) {
    return {
      latitude: directLongitude,
      longitude: directLatitude,
      coordinate_source: "swapped_lat_lon",
    };
  }

  const fallbackNorthing = toNumberOrNull(row.y_coordinate) ?? toNumberOrNull(row.y);
  const fallbackEasting = toNumberOrNull(row.x_coordinate) ?? toNumberOrNull(row.x);

  if (looksLikeLatitude(fallbackNorthing) && looksLikeLongitude(fallbackEasting)) {
    return {
      latitude: fallbackNorthing,
      longitude: fallbackEasting,
      coordinate_source: "fallback_lat_lon",
    };
  }

  if (looksLikeLatitude(fallbackEasting) && looksLikeLongitude(fallbackNorthing)) {
    return {
      latitude: fallbackEasting,
      longitude: fallbackNorthing,
      coordinate_source: "swapped_fallback_lat_lon",
    };
  }

  const converted = convertBritishNationalGridToLatLon(fallbackEasting, fallbackNorthing);

  if (converted) {
    return {
      ...converted,
      coordinate_source: "osgb36_converted",
    };
  }

  return {
    latitude: null,
    longitude: null,
    coordinate_source: null,
  };
};

export const readinessBandFromScore = (score) => {
  const s = Number(score) || 0;
  if (s >= 80) return "Green";
  if (s >= 50) return "Amber";
  return "Red";
};
