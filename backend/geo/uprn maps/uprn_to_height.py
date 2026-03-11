"""Building height and floor count lookup via OS NGD Buildings API.

Pipeline: UPRN -> BNG coordinates (OS Places) -> nearest building (NGD Buildings).
Uses the bld-fts-building-4 collection which includes height data, number of
floors, building area, and roof/construction attributes.

API docs: https://osdatahub.os.uk/docs/ofa/overview
Requires an NGD API key (separate from the Places API key).

Returns a dict on success or an error string on failure.
"""

import requests
from os_datahub_functions import get_coordinates_from_uprn


NGD_BUILDINGS_URL = "https://api.os.uk/features/ngd/ofa/v1/collections/bld-fts-building-4/items"
BNG_CRS = "http://www.opengis.net/def/crs/EPSG/0/27700"
BBOX_BUFFER_M = 15  # meters around the UPRN point


def get_building_from_coords(x: float, y: float, api_key: str) -> dict | str:
    """Query NGD Buildings API with a tight bbox around BNG coordinates.

    Creates a 30m x 30m bounding box centred on the point, fetches up to 10
    building features, and returns the one whose centroid is closest to the
    input coordinates. Handles both Polygon and MultiPolygon geometries.

    Args:
        x: Easting in British National Grid (EPSG:27700).
        y: Northing in British National Grid (EPSG:27700).
        api_key: OS Data Hub API key (NGD Features API).

    Returns:
        dict: GeoJSON feature of the nearest building.
        str: Error message if no building found or request fails.
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
    """Get building height, floor count, and area for a UPRN.

    Two-step lookup:
      1. UPRN -> BNG coordinates via OS Places API
      2. Coordinates -> nearest building via NGD Buildings API

    Args:
        uprn: The UPRN to look up (str or int).
        places_api_key: OS Data Hub API key (Places API).
        ngd_api_key: OS Data Hub API key (NGD Features API).

    Returns:
        dict: Building data with keys:
            - uprn, address, x_coordinate, y_coordinate
            - height_relativemax_m: Height from ground to the highest point
            - height_relativeroofbase_m: Height from ground to roof base (eaves)
            - height_absolutemax_m/min_m: Heights above sea level
            - height_confidencelevel: Moderate / Good / Suspect
            - numberoffloors: Estimated floor count (1-99, ~95% accurate for 1-2 storeys)
            - geometry_area_m2: Building footprint area
            - osid, description
        str: Error message if lookup fails at any step.
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
        # Number of floors (from NGD Building Part)
        "numberoffloors": props.get("numberoffloors"),
        # Bonus fields available on the building feature
        "geometry_area_m2": props.get("geometry_area_m2"),
        "osid": props.get("osid"),
        "description": props.get("description"),
        # Extra COPE data
        "property_type": props.get("description"),
        "wall_construction": props.get("constructionmaterial"),
        "roof_construction": props.get("roofmaterial_primarymaterial"),
        "age_band": props.get("buildingage_period"),
        "year_of_build": props.get("buildingage_year"),
        "basement": props.get("basementpresence"),
    }


# ── Quick test ──────────────────────────────────────────────
if __name__ == "__main__":
    PLACES_KEY = "Ajrj5AiJphBOM2GdP7KqVx6Ax6CTemtY"
    NGD_KEY = "6O5pS5fOPakmnsCbdaykC8nszFcaGSkz"
    TEST_UPRN = 906369718  # 3/2 Grange Loan, Edinburgh
    test_U = [906369718, 906700278607, 906700350103, 200004166668,
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
            print(f"Number of floors:   {result['numberoffloors']}")
            print(f"Building area:       {result['geometry_area_m2']} m²")
            print(f"Property type:      {result['property_type']}")
            print(f"Wall Construction       {result['wall_construction']}")
            print(f"Roof Construction       {result['roof_construction']}")
            print(f"Age Band:              {result['age_band']}")
            print(f"Year of Build:         {result['year_of_build']}")
            print(f"Basement:              {result['basement']}")
            print(f"OS ID:               {result['osid']}")
        else:
            print(f"Error: {result}")
