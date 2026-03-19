"""Listed building lookup by UPRN.

Checks whether a property is a listed building using:
- England: planning.data.gov.uk (Historic England data, no API key required)
- Scotland: Historic Environment Scotland WFS (no API key required)

Pipeline: UPRN -> BNG coordinates (OS Places) -> spatial query against listed building polygons.
"""

import requests
from pyproj import Transformer
from backend.geo.uprn_maps.os_datahub_functions import get_coordinates_from_uprn

# BNG (EPSG:27700) -> WGS84 (EPSG:4326) transformer
_bng_to_wgs84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


# ── England: planning.data.gov.uk ──────────────────────────
PLANNING_DATA_URL = "https://www.planning.data.gov.uk/entity.json"

# ── Scotland: Historic Environment Scotland WFS ─────────────
HES_WFS_URL = (
    "https://inspire.hes.scot/arcgis/services/HES/"
    "Listed_Buildings/MapServer/WFSServer"
)


def _check_england(x: float, y: float) -> dict:
    """Query planning.data.gov.uk for listed buildings near a BNG point.

    Converts BNG to WGS84, creates a small ~50m buffer polygon, and searches
    the listed-building (point) dataset for intersections.
    """
    lon, lat = _bng_to_lonlat(x, y)

    # ~50m buffer in degrees
    buf = 0.0005
    wkt = (
        f"POLYGON(({lon-buf} {lat-buf},{lon+buf} {lat-buf},"
        f"{lon+buf} {lat+buf},{lon-buf} {lat+buf},{lon-buf} {lat-buf}))"
    )

    params = {
        "dataset": "listed-building",
        "geometry": wkt,
        "geometry_relation": "intersects",
        "limit": 1,
    }

    try:
        response = requests.get(PLANNING_DATA_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return {"is_listed": None, "error": f"England API error: {e}"}

    entities = data.get("entities", [])
    if not entities:
        return {"is_listed": False, "grade": None, "name": None, "reference": None}

    entity = entities[0]
    return {
        "is_listed": True,
        "grade": entity.get("listed-building-grade"),
        "name": entity.get("name"),
        "reference": entity.get("reference"),
        "source": "Historic England via planning.data.gov.uk",
    }


def _check_scotland(x: float, y: float) -> dict:
    """Query HES WFS for listed building boundaries containing a BNG point.

    Uses a small BBOX around the point in EPSG:27700 and checks intersection.
    """
    buffer = 5  # meters
    bbox = f"{x - buffer},{y - buffer},{x + buffer},{y + buffer}"

    params = {
        "service": "WFS",
        "request": "GetFeature",
        "typeName": "HES_Listed_Buildings:Listed_Buildings_boundaries",
        "outputFormat": "GEOJSON",
        "srsName": "EPSG:27700",
        "bbox": f"{bbox},EPSG:27700",
        "count": 1,
    }

    try:
        response = requests.get(HES_WFS_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return {"is_listed": None, "error": f"Scotland API error: {e}"}

    features = data.get("features", [])
    if not features:
        return {"is_listed": False, "grade": None, "name": None, "reference": None}

    props = features[0].get("properties", {})
    return {
        "is_listed": True,
        "grade": props.get("CATEGORY"),  # A, B, or C
        "name": props.get("DES_TITLE"),
        "reference": props.get("DES_REF"),
        "source": "Historic Environment Scotland",
    }


def _bng_to_lonlat(x: float, y: float) -> tuple[float, float]:
    """Convert BNG (EPSG:27700) to WGS84 (lon, lat) using pyproj."""
    lon, lat = _bng_to_wgs84.transform(x, y)
    return round(lon, 6), round(lat, 6)


def _is_scotland(place: dict) -> bool:
    """Check if a property is in Scotland using the OS Places COUNTRY_CODE field."""
    return place.get("COUNTRY_CODE") == "S"


def get_listed_building_status(
    uprn: str | int,
    places_api_key: str,
) -> dict:
    """Check if a UPRN is a listed building (England or Scotland).

    Two-step lookup:
      1. UPRN -> BNG coordinates via OS Places API
      2. Coordinates -> spatial query against listed building polygons

    Args:
        uprn: The UPRN to look up.
        places_api_key: OS Data Hub API key (Places API).

    Returns:
        dict with keys:
            - is_listed: True/False/None (None = API error)
            - grade: e.g. "I", "II", "II*" (England) or "A", "B", "C" (Scotland)
            - name: Listed building name/title
            - reference: List entry reference number
            - source: Data source used
            - error: Error message if lookup failed
    """
    # Step 1: UPRN -> BNG coordinates
    place = get_coordinates_from_uprn(uprn, places_api_key)
    if isinstance(place, str):
        return {"is_listed": None, "error": place}

    x = place.get("X_COORDINATE")
    y = place.get("Y_COORDINATE")
    if x is None or y is None:
        return {"is_listed": None, "error": "No coordinates for this UPRN."}

    x, y = float(x), float(y)

    # Step 2: Check against the right dataset based on country
    if _is_scotland(place):
        return _check_scotland(x, y)
    else:
        return _check_england(x, y)


# ── Quick test ──────────────────────────────────────────────
if __name__ == "__main__":
    PLACES_KEY = "Ajrj5AiJphBOM2GdP7KqVx6Ax6CTemtY"

    test_uprns = [
        100121171192,  # 2 Royal Crescent, Bath (England) - Grade II listed
        10070095245, # Chatsworth House, Bakewell (England) - Grade I listed
        906359983, # 272 Canongate, Edinburgh (Scotland) - Category B listed
        100120943507, # 30 Sycamore Drive, Carterton (England) - not listed
        906369718,    # 3/2 Grange Loan, Edinburgh (Scotland)
        100021008224, # England test
        10023012454,  # England test
    ]

    for uprn in test_uprns:
        print(f"\n{'='*60}")
        print(f"UPRN: {uprn}")
        result = get_listed_building_status(uprn, PLACES_KEY)
        for k, v in result.items():
            print(f"  {k}: {v}")
