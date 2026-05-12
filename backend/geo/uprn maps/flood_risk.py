"""Flood risk API wrappers.

Looks up the flood risk band published by the relevant agency for a British
National Grid (EPSG:27700) point, dispatching by country code from OS Places:

  E → EA RoFRS         (High / Medium / Low / Very Low)
  W → NRW FRAW         (High / Medium / Low)
  S → SEPA flood maps  (High / Medium / Low — derived from 1-in-10 /
                        1-in-200 / 1-in-1000 likelihood extents)
  N → not supported    (no equivalent free public API for Northern Ireland)

Returns the raw band as published by each agency. Bands are NOT directly
comparable across countries — see the accompanying manual for the annual
probability ranges behind each band.

Single-item functions return either a result dict on success or an error
string on failure. Batch functions take ``(uprn, x, y, country_code)``
tuples and return a dict mapping UPRN to result, mirroring the pattern
used by ``get_buildings_from_coords_batch`` and ``get_listed_building_statuses``.

IMPORTANT: WFS typeNames and ArcGIS layer IDs change over time. The values
in the CONFIG block below are best-effort and must be verified against each
agency's current GetCapabilities / service directory before relying on this
in production:

  EA RoFRS:  postcode CSV — Postcodes_Risk_Assessment_All.csv
             https://environment.data.gov.uk/dataset/53cba123-71f8-417a-8441-4c7ba111e8e1
             Place CSV alongside flood_risk.py before use.
  NRW FRAW:  https://datamap.gov.wales/capabilities/layergroup/889/?ows_service=wfs  (layer-group caps)
             https://datamap.gov.wales/geoserver/inspire-nrw/wfs?service=WFS&request=GetCapabilities  (workspace caps, FRAW layers NOT listed here)
  SEPA:      https://map.sepa.org.uk/server/rest/services/Open/Flood_Maps/MapServer  (layer list)
"""

import csv
import os
import requests


# ── CONFIG (verify against current agency documentation) ──────────────────

# EA RoFRS — postcode-level CSV lookup (England only).
#
# No publicly accessible per-cell WFS/REST endpoint exists for England:
#   - Old WFS retired Jan 2025 (NaFRA2 replaced the dataset)
#   - NaFRA2 is raster WMS only (GetFeatureInfo returns nothing usable)
#   - gisrest.defra.gov.uk is an internal Defra server, not public
#
# The official "Check Long Term Flood Risk" service uses postcode-level
# aggregates, not per-property cells ("the risk is for the area around
# an address, not the address itself"). The underlying data is:
#   Postcodes_Risk_Assessment_All.csv
#   https://environment.data.gov.uk/dataset/53cba123-71f8-417a-8441-4c7ba111e8e1
#   OGL v3 — quarterly updates
#
# CSV schema (verified May 2026):
#   Postcode, HIGH_CNT, MED_CNT, LOW_CNT, GWTR_RISK
#   *_CNT = count of properties at that band within the postcode.
#   Band is the highest non-zero count (HIGH_CNT > 0 → High, etc.).
#
# Download the CSV and place it alongside this file, or set EA_ROFRS_CSV_PATH.
EA_ROFRS_CSV_PATH = os.path.join(os.path.dirname(__file__), "Postcodes_Risk_Assessment_All.csv")

# Populated on first call to get_flood_risk_england() — maps normalised
# postcode (no spaces, uppercase) to "High" | "Medium" | "Low" | "Very Low".
_EA_ROFRS_BY_POSTCODE: dict[str, str] = {}


def _load_rofrs_csv() -> None:
    """Load EA_ROFRS_CSV_PATH into _EA_ROFRS_BY_POSTCODE (called once, lazily)."""
    if not os.path.exists(EA_ROFRS_CSV_PATH):
        raise FileNotFoundError(
            f"EA RoFRS postcode CSV not found at {EA_ROFRS_CSV_PATH!r}. "
            "Download Postcodes_Risk_Assessment_All.csv from "
            "https://environment.data.gov.uk/dataset/53cba123-71f8-417a-8441-4c7ba111e8e1 "
            "and place it in the same directory as flood_risk.py."
        )
    with open(EA_ROFRS_CSV_PATH, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pc = row.get("Postcode", "").replace(" ", "").upper()
            if not pc:
                continue
            high = int(row.get("HIGH_CNT") or 0)
            med  = int(row.get("MED_CNT")  or 0)
            low  = int(row.get("LOW_CNT")  or 0)
            if high > 0:
                _EA_ROFRS_BY_POSTCODE[pc] = "High"
            elif med > 0:
                _EA_ROFRS_BY_POSTCODE[pc] = "Medium"
            elif low > 0:
                _EA_ROFRS_BY_POSTCODE[pc] = "Low"
            else:
                _EA_ROFRS_BY_POSTCODE[pc] = "Very Low"

# NRW FRAW was split into three separate layers (verified 2026-05).
# Old monolithic typename "inspire-nrw:NRW_FLOOD_RISK_ASSESSMENT_WALES" no
# longer exists.  The layer-group capabilities document is at:
#   https://datamap.gov.wales/capabilities/layergroup/889/?ows_service=wfs
# All three layers use DefaultCRS urn:ogc:def:crs:EPSG::27700 and return
# risk bands as the string field "risk" with values "High" / "Medium" / "Low".
#
# IMPORTANT — geometry column names differ between layers (FME export artifact):
#   NRW_FLOOD_RISK_FROM_RIVERS  →  geom
#   NRW_FLOOD_RISK_FROM_SEA     →  geom
#   NRW_FLOOD_RISK_FROM_SURFACE_WATER_SMALL_WATERCOURSES  →  fme_geometry
NRW_FRAW_WFS = "https://datamap.gov.wales/geoserver/inspire-nrw/wfs"
NRW_FRAW_TYPENAMES = [
    ("inspire-nrw:NRW_FLOOD_RISK_FROM_RIVERS", "geom"),
    ("inspire-nrw:NRW_FLOOD_RISK_FROM_SEA", "geom"),
    ("inspire-nrw:NRW_FLOOD_RISK_FROM_SURFACE_WATER_SMALL_WATERCOURSES", "fme_geometry"),
]
NRW_FRAW_BAND_FIELD = "risk"  # lowercase; was "RISK_BAND" on old monolithic layer

# SEPA publishes flood maps via a single MapServer on their own ArcGIS
# Server (map.sepa.org.uk). Each likelihood band has dedicated layer IDs:
#
#   Layer 0 — River Flooding High Likelihood   (1-in-10,  ≥10%/yr)
#   Layer 1 — River Flooding Medium Likelihood (1-in-200, ≥0.5%/yr)
#   Layer 2 — River Flooding Low Likelihood    (1-in-1000,≥0.1%/yr)
#   Layer 6 — Coastal Flooding High Likelihood
#   Layer 7 — Coastal Flooding Medium Likelihood
#   Layer 8 — Coastal Flooding Low Likelihood
#
# Surface water layers (3–5) are excluded to match the rivers-and-sea
# scope of EA RoFRS and NRW FRAW. All layers use EPSG:27700 (BNG).
#
# Service verified: map.sepa.org.uk/server/rest/services/Open/Flood_Maps/MapServer
# (©SEPA 2025, Open Government Licence v3.0)
SEPA_MAPSERVER = "https://map.sepa.org.uk/server/rest/services/Open/Flood_Maps/MapServer"
SEPA_LAYERS = {
    "High": [0, 6],    # River High (layer 0), Coastal High (layer 6)
    "Medium": [1, 7],  # River Medium (layer 1), Coastal Medium (layer 7)
    "Low": [2, 8],     # River Low (layer 2), Coastal Low (layer 8)
}

REQUEST_TIMEOUT = 30  # seconds


# ── Helpers ───────────────────────────────────────────────────────────────

def _result(band, source, note=None) -> dict:
    """Wrap a band lookup into the standard output schema."""
    return {
        "flood_risk_band": band,
        "flood_risk_source": source,
        "flood_risk_note": note,
    }


# ── England: EA RoFRS ─────────────────────────────────────────────────────

def get_flood_risk_england(postcode: str, session=None) -> dict | str:
    """Look up the EA RoFRS flood risk band for an English postcode.

    Uses the EA postcode-level risk assessment CSV, which is the same data
    source as the 'Check Long Term Flood Risk' service. The band reflects
    the highest risk among all properties within the postcode — it is not
    per-property. Bands: High / Medium / Low / Very Low.

    Args:
        postcode: Full UK postcode (spaces and case ignored).
        session: unused; kept for interface consistency with Wales/Scotland.

    Returns:
        dict: {flood_risk_band, flood_risk_source, flood_risk_note}.
        str: Error message if the CSV cannot be loaded.
    """
    if not _EA_ROFRS_BY_POSTCODE:
        try:
            _load_rofrs_csv()
        except FileNotFoundError as e:
            return str(e)

    pc = postcode.replace(" ", "").upper()
    band = _EA_ROFRS_BY_POSTCODE.get(pc)
    if band is None:
        return _result("Could not match", "EA RoFRS")
    return _result(band, "EA RoFRS")


# ── Wales: NRW FRAW ───────────────────────────────────────────────────────

def get_flood_risk_wales(x: float, y: float, session=None) -> dict | str:
    """Look up the NRW FRAW flood risk band for a BNG point in Wales.

    Queries all three NRW FRAW layers (rivers, sea, surface water) and returns
    the highest band found across any source.
    FRAW publishes three bands (High / Medium / Low) accounting for defences.
    Points outside all extents are reported as 'Very Low' for output
    consistency, with a note that FRAW itself does not publish a Very Low band.

    Args:
        x: BNG easting (EPSG:27700).
        y: BNG northing (EPSG:27700).
        session: optional ``requests.Session``.

    Returns:
        dict: {flood_risk_band, flood_risk_source, flood_risk_note}.
        str: Error message on request failure.
    """
    _band_priority = {"High": 3, "Medium": 2, "Low": 1}
    sess = session or requests
    best_band: str | None = None
    best_priority = 0

    try:
        for typename, geom_col in NRW_FRAW_TYPENAMES:
            params = {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": typename,
                "CQL_FILTER": f"INTERSECTS({geom_col},POINT({x} {y}))",
                "srsName": "urn:ogc:def:crs:EPSG::27700",
                "outputFormat": "application/json",
                "count": 1,
            }
            response = sess.get(NRW_FRAW_WFS, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            features = data.get("features", [])
            if not features:
                continue
            props = features[0].get("properties", {})
            band = props.get(NRW_FRAW_BAND_FIELD)
            if band and _band_priority.get(band, 0) > best_priority:
                best_band = band
                best_priority = _band_priority[band]
            if best_priority == 3:
                break  # already at highest possible band — no need to query further

        if best_band is None:
            return _result("Very Low", "NRW FRAW",
                           note="No feature at point across rivers, sea, or surface "
                                "water layers; FRAW does not publish a Very Low band "
                                "— point is outside all extents.")
        return _result(best_band, "NRW FRAW")

    except requests.exceptions.RequestException as e:
        return f"NRW FRAW request failed: {e}"


# ── Scotland: SEPA ────────────────────────────────────────────────────────

def _sepa_layer_hits(layer_id: int, x: float, y: float, session) -> bool:
    """True if the BNG point intersects any polygon in a SEPA MapServer layer.

    Args:
        layer_id: Integer layer ID within the SEPA Flood Maps MapServer.
        x: BNG easting (EPSG:27700).
        y: BNG northing (EPSG:27700).
        session: requests.Session or the requests module itself.
    """
    sess = session or requests
    params = {
        "geometry": f'{{"x":{x},"y":{y},"spatialReference":{{"wkid":27700}}}}',
        "geometryType": "esriGeometryPoint",
        "inSR": 27700,
        "spatialRel": "esriSpatialRelIntersects",
        "returnGeometry": "false",
        "outFields": "OBJECTID",
        "resultRecordCount": 1,
        "f": "json",
    }
    url = f"{SEPA_MAPSERVER}/{layer_id}/query"
    response = sess.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    return len(data.get("features", [])) > 0


def get_flood_risk_scotland(x: float, y: float, session=None) -> dict | str:
    """Look up the SEPA flood risk band for a BNG point in Scotland.

    Queries the three SEPA likelihood extents (1-in-10, 1-in-200, 1-in-1000)
    for river and coastal sources in priority order, returning the most
    extreme band the point intersects. Surface water is excluded to match
    the rivers-and-sea scope of EA RoFRS and NRW FRAW.

    Args:
        x: BNG easting (EPSG:27700).
        y: BNG northing (EPSG:27700).
        session: optional ``requests.Session``.

    Returns:
        dict: {flood_risk_band, flood_risk_source, flood_risk_note}.
        str: Error message on request failure.
    """
    try:
        for band in ("High", "Medium", "Low"):
            for layer_id in SEPA_LAYERS[band]:
                if _sepa_layer_hits(layer_id, x, y, session):
                    return _result(band, "SEPA")
        return _result("Very Low", "SEPA",
                       note="Point is outside all SEPA river/coastal extents.")
    except requests.exceptions.RequestException as e:
        return f"SEPA request failed: {e}"


# ── Router ────────────────────────────────────────────────────────────────

def get_flood_risk_from_coords(
    x: float, y: float, country_code: str,
    postcode: str | None = None,
    session=None,
) -> dict | str:
    """Dispatch a flood risk lookup by country.

    Args:
        x: BNG easting (EPSG:27700).
        y: BNG northing (EPSG:27700).
        country_code: 'E', 'W', 'S', or 'N' from OS Places COUNTRY_CODE.
        postcode: Required for England (CSV lookup). Ignored for W/S.
        session: optional ``requests.Session`` for connection reuse.

    Returns:
        dict: {flood_risk_band, flood_risk_source, flood_risk_note}. Bands
            are NOT directly comparable across countries — EA uses postcode
            aggregates; NRW and SEPA return per-cell spatial results.
        str: Error message on request failure.
    """
    if country_code == "E":
        if not postcode:
            return _result(None, "EA RoFRS",
                           note="Postcode required for England flood risk lookup.")
        return get_flood_risk_england(postcode, session)
    elif country_code == "W":
        return get_flood_risk_wales(x, y, session)
    elif country_code == "S":
        return get_flood_risk_scotland(x, y, session)
    elif country_code == "N":
        return _result(None, None,
                       note="Northern Ireland not supported (no equivalent "
                            "free public flood risk API).")
    else:
        return _result(None, None,
                       note=f"Unknown country code: {country_code!r}")


# ── Batch ─────────────────────────────────────────────────────────────────

def get_flood_risks_from_coords_batch(
    coords: list[tuple[str, float, float, str, str | None]],
) -> dict[str, dict | str]:
    """Look up flood risk for multiple properties, reusing a single Session.

    Args:
        coords: List of ``(uprn, x, y, country_code, postcode)`` tuples.
            postcode is required for England (country_code='E'); pass None
            for Wales/Scotland where spatial lookup is used instead.

    Returns:
        Dict mapping each UPRN (as str) to its result dict, or to an error
        string if the lookup failed.
    """
    results: dict[str, dict | str] = {}

    with requests.Session() as session:
        for uprn, x, y, country_code, postcode in coords:
            results[str(uprn)] = get_flood_risk_from_coords(
                x, y, country_code, postcode=postcode, session=session,
            )

    return results


# ── Usage example ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    from os_datahub_functions import get_uprns_from_addresses

    PLACES_KEY = "7VakhnbibvboaY9eE0385zORrBJAc2sw"

    test_addresses = [
        "Flat 1/1, 351 Holmlea Road, Cathcart, Glasgow, G44 4BP",  # Scotland,
        # "61, WHITESANDS, DUMFRIES, DG1 2RS",
        "76A, TAY STREET, PERTH, PH2 8NP P",
        # "12, NORTH BRIDGE STREET, HAWICK, TD9 9QW",
        # "40, SHORE ROAD, COVE, HELENSBURGH, G84 0LR",
        # "47 Greens Road, Eynsham, Witney, OX29 4NQ",  # England
        # "9 Flexneys Paddock, Stanton Harcourt, Witney, OX29 5RS",
        # "32 Sycamore Drive, Carterton, OX18 3AT",
        # "21 Heyford Close, Standlake, Witney, OX29 7SZ",
        # "1 Mill Street, Tewkesbury, GL20 5RZ",
        # "13, KINGS STAITH, YORK, YO1 9SN",
        "11, FRANKWELL, SHREWSBURY, SY3 8JY",
        "3, BRIDGE GATE, HEBDEN BRIDGE, HX7 8EX",
         "1, OLD CARDIFF ROAD, NEWPORT, NP20 3AT",  # Wales
         # "10, DOWNING STREET, LLANELLI, SA15 2UA",
         # "4 Albert Street, Riverside, Cardiff, CF11 6BG",
         # "110 Albert Street, Riverside, Cardiff, CF11 6JP",
         # "4 Alexandra Court, Ethel Street, Canton, Cardiff, CF5 1EN",
         # "107 Bartley Wilson Way, Canton, Cardiff, CF11 8EN"
    ]

    # Resolve addresses to UPRN + BNG coords + country code in one batch call.
    # No need for the full address_to_final pipeline — flood risk only needs x, y, country_code.
    places = get_uprns_from_addresses(test_addresses, PLACES_KEY)

    coords = []
    for addr, place in zip(test_addresses, places):
        if isinstance(place, str):
            print(f"Address lookup failed for: {addr}\n  {place}")
            continue
        uprn = str(place.get("UPRN", "unknown"))
        x = place.get("X_COORDINATE")
        y = place.get("Y_COORDINATE")
        country = place.get("COUNTRY_CODE")
        postcode = place.get("POSTCODE")
        if x is None or y is None or not country:
            print(f"Missing coords/country for: {addr}")
            continue
        coords.append((uprn, float(x), float(y), country, postcode))
        print(f"Resolved: {addr}")
        print(f"  UPRN={uprn}  BNG=({x}, {y})  country={country}  postcode={postcode}")

    print()
    print("=" * 60)
    print("FLOOD RISK RESULTS")
    print("=" * 60)
    results = get_flood_risks_from_coords_batch(coords)
    for (uprn, x, y, country, postcode), addr in zip(coords, [a for a, p in zip(test_addresses, places) if not isinstance(p, str) and p.get("X_COORDINATE")]):
        result = results.get(str(uprn))
        print(f"\n  {addr}")
        print(f"  UPRN: {uprn}  country: {country}")
        if isinstance(result, dict):
            print(f"  flood_risk_band:   {result.get('flood_risk_band')}")
            print(f"  flood_risk_source: {result.get('flood_risk_source')}")
            if result.get("flood_risk_note"):
                print(f"  note:              {result.get('flood_risk_note')}")
        else:
            print(f"  ERROR: {result}")