"""Full property lookup: address -> UPRN -> all available attributes.

Combines OS Places, NGD Buildings, EPC, and Listed Building lookups into a
single result dict. When EPC data is available, it takes priority over NGD
for construction-related fields (wall type, roof type, age band, property type).
"""

from backend.geo.uprn_maps.os_datahub_functions import get_uprn_from_address, get_coordinates_from_uprn
from backend.geo.uprn_maps.uprn_to_epc import get_epc_from_uprn
from backend.geo.uprn_maps.uprn_to_height import get_building_from_coords
from backend.geo.uprn_maps.uprn_to_listed import get_listed_building_status

def get_final_info_from_address(address: str, email: str, places_key: str, ngd_key: str, epc_key: str) -> dict | str:
    """Look up all available property data from a free-text address.

    Pipeline:
      1. Address -> UPRN + coordinates (OS Places)
      2. UPRN -> EPC certificates (England/Wales only)
      3. Coordinates -> NGD building data (height, floors, construction)
      4. Coordinates -> Listed building status (England/Scotland)
      5. Merge results; EPC takes priority for construction fields.

    Args:
        address: Free-text address string.
        email: Registered email for EPC API auth.
        places_key: OS Data Hub API key (Places API).
        ngd_key: OS Data Hub API key (NGD Features API).
        epc_key: EPC API key.

    Returns:
        dict: Combined property data.
        str: Error message if address lookup fails.
    """
    # Step 1: Address -> UPRN + coordinates
    place = get_uprn_from_address(address, places_key)
    if isinstance(place, str):
        return place

    uprn = place.get("UPRN")
    x = place.get("X_COORDINATE")
    y = place.get("Y_COORDINATE")

    if not uprn:
        return "No UPRN found for this address."

    # Step 2: EPC lookup
    epc_data = get_epc_from_uprn(uprn, email, epc_key)
    has_epc = isinstance(epc_data, list) and len(epc_data) > 0
    epc = epc_data[0] if has_epc else {}

    # Step 3: NGD building lookup (needs coordinates)
    ngd = {}
    if x is not None and y is not None:
        building = get_building_from_coords(float(x), float(y), ngd_key)
        if isinstance(building, dict):
            ngd = building.get("properties", {})

    # Step 4: Listed building lookup
    listed_data = get_listed_building_status(uprn, places_key)

    # Step 5: Merge — EPC preferred for construction fields
    result = {
        # Identity
        "uprn": str(uprn),
        "address": place.get("ADDRESS"),
        "postcode": place.get("POSTCODE"),
        "x_coordinate": x,
        "y_coordinate": y,
        "country_code": place.get("COUNTRY_CODE"),
        "match_score": place.get("MATCH"),
        "match_description": place.get("MATCH_DESCRIPTION"),

        # Height data (NGD only)
        "height_relativemax_m": ngd.get("height_relativemax_m"),
        "height_relativeroofbase_m": ngd.get("height_relativeroofbase_m"),
        "height_absolutemax_m": ngd.get("height_absolutemax_m"),
        "height_absolutemin_m": ngd.get("height_absolutemin_m"),
        "height_absoluteroofbase_m": ngd.get("height_absoluteroofbase_m"),
        "height_confidencelevel": ngd.get("height_confidencelevel"),
        "numberoffloors": ngd.get("numberoffloors"),
        "geometry_area_m2": ngd.get("geometry_area_m2"),

        # Construction data — EPC preferred, NGD fallback
        "property_type": epc.get("property-type") or ngd.get("description"),
        "built_form": epc.get("built-form"),
        "wall_construction": epc.get("walls-description") or ngd.get("constructionmaterial"),
        "roof_construction": epc.get("roof-description") or ngd.get("roofmaterial_primarymaterial"),
        "age_band": epc.get("construction-age-band") or ngd.get("buildingage_period"),
        "year_of_build": ngd.get("buildingage_year"),
        "basement": ngd.get("basementpresence"),
        "construction_data_source": "EPC" if has_epc else "NGD",

        # EPC energy data
        "epc_rating": epc.get("current-energy-rating"),
        "epc_potential_rating": epc.get("potential-energy-rating"),
        "total_floor_area_m2": epc.get("total-floor-area"),
        "main_fuel": epc.get("main-fuel"),
        "extension_count": epc.get("extension-count"),
        "lighting_cost_current": epc.get("lighting-cost-current"),
        "heating_cost_current": epc.get("heating-cost-current"),
        "hot_water_cost_current": epc.get("hot-water-cost-current"),
        "epc_lodgement_date": epc.get("lodgement-datetime"),

        # Listed building data
        "is_listed": listed_data.get("is_listed"),
        "listed_grade": listed_data.get("grade"),
        "listed_name": listed_data.get("name"),
        "listed_reference": listed_data.get("reference"),

        # NGD identifiers
        "osid": ngd.get("osid"),
    }

    return result


def get_final_info_from_uprn(uprn: str | int, email: str, places_key: str, ngd_key: str, epc_key: str) -> dict | str:
    """Same as get_final_info_from_address but starting from a known UPRN."""
    place = get_coordinates_from_uprn(uprn, places_key)
    if isinstance(place, str):
        return place

    x = place.get("X_COORDINATE")
    y = place.get("Y_COORDINATE")

    # EPC
    epc_data = get_epc_from_uprn(uprn, email, epc_key)
    has_epc = isinstance(epc_data, list) and len(epc_data) > 0
    epc = epc_data[0] if has_epc else {}

    # NGD building
    ngd = {}
    if x is not None and y is not None:
        building = get_building_from_coords(float(x), float(y), ngd_key)
        if isinstance(building, dict):
            ngd = building.get("properties", {})

    # Listed
    listed_data = get_listed_building_status(uprn, places_key)

    result = {
        "uprn": str(uprn),
        "address": place.get("ADDRESS"),
        "postcode": place.get("POSTCODE"),
        "x_coordinate": x,
        "y_coordinate": y,
        "country_code": place.get("COUNTRY_CODE"),

        "height_relative_max_m": ngd.get("height_relativemax_m"),
        "height_relative_roofbase_m": ngd.get("height_relativeroofbase_m"),
        "height_absolute_max_m": ngd.get("height_absolutemax_m"),
        "height_absolute_min_m": ngd.get("height_absolutemin_m"),
        "height_absolute_roofbase_m": ngd.get("height_absoluteroofbase_m"),
        "height_confidence_level": ngd.get("height_confidencelevel"),
        "number_of_floors": ngd.get("numberoffloors"),
        "geometry_area_m2": ngd.get("geometry_area_m2"),

        "property_type": epc.get("property-type") or ngd.get("description"),
        "built_form": epc.get("built-form"),
        "wall_construction": epc.get("walls-description") or ngd.get("constructionmaterial"),
        "roof_construction": epc.get("roof-description") or ngd.get("roofmaterial_primarymaterial"),
        "age_band": epc.get("construction-age-band") or ngd.get("buildingage_period"),
        "year_of_build": ngd.get("buildingage_year"),
        "basement": ngd.get("basementpresence"),
        "construction_data_source": "EPC" if has_epc else "NGD",

        "epc_rating": epc.get("current-energy-rating"),
        "epc_potential_rating": epc.get("potential-energy-rating"),
        "total_floor_area_m2": epc.get("total-floor-area"),
        "main_fuel": epc.get("main-fuel"),
        "extension_count": epc.get("extension-count"),
        "lighting_cost_current": epc.get("lighting-cost-current"),
        "heating_cost_current": epc.get("heating-cost-current"),
        "hot_water_cost_current": epc.get("hot-water-cost-current"),
        "epc_lodgement_date": epc.get("lodgement-datetime"),

        "is_listed": listed_data.get("is_listed"),
        "listed_grade": listed_data.get("grade"),
        "listed_name": listed_data.get("name"),
        "listed_reference": listed_data.get("reference"),

        "osid": ngd.get("osid"),
    }

    return result


# ── Quick test ──────────────────────────────────────────────
if __name__ == "__main__":
    PLACES_KEY = "Ajrj5AiJphBOM2GdP7KqVx6Ax6CTemtY"
    NGD_KEY = "6O5pS5fOPakmnsCbdaykC8nszFcaGSkz"
    EPC_EMAIL = "igorshuvalov23@gmail.com"
    EPC_KEY = "9213b51f9af85ba4700865191700778f0cc7f3fc"

    test_addresses = ["13 ABBOTTS BARN CLOSE",
        #"30 Sycamore Drive, Carterton, OX18 3AT",
        #"3/2 Grange Loan, Edinburgh, EH9 2NP",
        #"209 Clarkston Road, Cathcart, Glasgow, G44 3DS",
        #"Flat 1/1, 4 Craig Road, Cathcart, Glasgow, G44 3DR",
        "Flat 1/1, 217 Clarkston Road, Cathcart, Glasgow, G44 3DS",
        "2 BATH STREET, DERBY, DE1 3BU"
    ]

    for addr in test_addresses:
        print(f"\n{'='*60}")
        print(f"Query: {addr}")
        print(f"{'='*60}")

        result = get_final_info_from_address(addr, EPC_EMAIL, PLACES_KEY, NGD_KEY, EPC_KEY)

        if isinstance(result, dict):
            for key, value in result.items():
                print(f"  {key:30s}: {value}")
        else:
            print(f"  Error: {result}")
