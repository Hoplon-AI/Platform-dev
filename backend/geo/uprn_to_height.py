import requests
from os_datahub_functions import get_coordinates_from_uprn


NGD_BUILDINGS_URL = "https://api.os.uk/features/ngd/ofa/v1/collections/bld-fts-building-4/items"
BNG_CRS = "http://www.opengis.net/def/crs/EPSG/0/27700"
BBOX_BUFFER_M = 15  # meters around the UPRN point


def get_building_from_coords(x: float, y: float, api_key: str) -> dict | str:
    """Query NGD Buildings API with a tight bbox around BNG coordinates.

    Returns the nearest building feature dict, or an error string.
    """
    bbox = f"{x - BBOX_BUFFER_M},{y - BBOX_BUFFER_M},{x + BBOX_BUFFER_M},{y + BBOX_BUFFER_M}"

    params = {
        "key": api_key,
        "bbox": bbox,
        "bbox-crs": BNG_CRS,
        "crs": BNG_CRS,
        "limit": 10,
    }

    try:
        response = requests.get(NGD_BUILDINGS_URL, params=params)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"NGD API error: {e}"

    features = data.get("features", [])
    if not features:
        return "No building found at these coordinates."

    # Pick the building whose centroid is closest to the UPRN point
    best = None
    best_dist = float("inf")

    for feat in features:
        coords = feat.get("geometry", {}).get("coordinates", [])
        if not coords:
            continue

        # Compute centroid from the outer ring of the polygon
        ring = coords[0] if feat["geometry"]["type"] == "Polygon" else coords[0][0]
        cx = sum(p[0] for p in ring) / len(ring)
        cy = sum(p[1] for p in ring) / len(ring)
        dist = ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5

        if dist < best_dist:
            best_dist = dist
            best = feat

    if best is None:
        return "No building geometry found."

    return best


def get_building_height_from_uprn(
    uprn: str | int,
    places_api_key: str,
    ngd_api_key: str,
) -> dict | str:
    """Get building height for a UPRN.

    Returns a dict with height fields and metadata, or an error string.
    Uses OS Places API (coordinates) -> NGD Buildings API (height).
    """
    # Step 1: UPRN -> BNG coordinates
    place = get_coordinates_from_uprn(uprn, places_api_key)
    if isinstance(place, str):
        return place

    x = place.get("X_COORDINATE")
    y = place.get("Y_COORDINATE")
    if x is None or y is None:
        return "No coordinates returned for this UPRN."

    # Step 2: Coordinates -> nearest building from NGD
    building = get_building_from_coords(float(x), float(y), ngd_api_key)
    if isinstance(building, str):
        return building

    props = building.get("properties", {})

    return {
        "uprn": str(uprn),
        "address": place.get("ADDRESS"),
        "x_coordinate": x,
        "y_coordinate": y,
        # Height fields (all nullable in the API)
        "height_relativemax_m": props.get("height_relativemax_m"),
        "height_relativeroofbase_m": props.get("height_relativeroofbase_m"),
        "height_absolutemax_m": props.get("height_absolutemax_m"),
        "height_absolutemin_m": props.get("height_absolutemin_m"),
        "height_absoluteroofbase_m": props.get("height_absoluteroofbase_m"),
        "height_confidencelevel": props.get("height_confidencelevel"),
        # Bonus fields available on the building feature
        "geometry_area_m2": props.get("geometry_area_m2"),
        "osid": props.get("osid"),
        "description": props.get("description"),
    }


# ── Quick test ──────────────────────────────────────────────
if __name__ == "__main__":
    PLACES_KEY = "Ajrj5AiJphBOM2GdP7KqVx6Ax6CTemtY"
    NGD_KEY = "6O5pS5fOPakmnsCbdaykC8nszFcaGSkz"
    TEST_UPRN = 906369718  # 3/2 Grange Loan, Edinburgh
    test_U = [200004166668,
              10002925710, 100021008224,
              200003423587, 10023012454, 100120943507]

    for uprn_t in test_U:

        result = get_building_height_from_uprn(uprn_t, PLACES_KEY, NGD_KEY)

        if isinstance(result, dict):
            print(f"UPRN:                {result['uprn']}")
            print(f"Address:             {result['address']}")
            print(f"Coordinates (BNG):   ({result['x_coordinate']}, {result['y_coordinate']})")
            print(f"Height (max):        {result['height_relativemax_m']} m")
            print(f"Height (roof base):  {result['height_relativeroofbase_m']} m")
            print(f"Height confidence:   {result['height_confidencelevel']}")
            print(f"Building area:       {result['geometry_area_m2']} m²")
            print(f"OS ID:               {result['osid']}")
        else:
            print(f"Error: {result}")
