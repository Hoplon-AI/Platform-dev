"""Full property lookup: address -> UPRN -> all available attributes.

Combines OS Places, NGD Buildings, EPC, and Listed Building lookups into a
single result dict. When EPC data is available, it takes priority over NGD
for construction-related fields (wall type, roof type, age band, property type).

Batch versions (get_final_info_from_addresses / get_final_info_from_uprns)
resolve coordinates once and share them across downstream lookups, cutting
OS Places API calls from ~4N to ~N for N properties.
"""

from os_datahub_functions import (
    get_uprn_from_address,
    get_coordinates_from_uprn,
    get_uprns_from_addresses,
    get_coordinates_from_uprns,
)
from uprn_to_epc import get_epc_from_uprn, get_epcs_from_uprns
from uprn_to_height import get_building_from_coords, get_buildings_from_coords_batch
from uprn_to_listed import get_listed_building_status, get_listed_building_statuses
from cross_reference import cross_reference, cross_reference_batch
from flood_risk import get_flood_risk_from_coords, get_flood_risks_from_coords_batch


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

    # Step 5: Cross-reference scoring — reuses the already-fetched place record,
    # so no extra OS Places call (parent UPRN lookup only fires in AMBER cases).
    cr = cross_reference(
        address, place.get("ADDRESS", ""), float(place.get("MATCH") or 0), place, places_key,
    )

    # Step 6: Flood risk lookup (reuses coordinates already fetched in Step 1)
    flood: dict = {}
    country_code = place.get("COUNTRY_CODE")
    postcode = place.get("POSTCODE")
    if x is not None and y is not None and country_code:
        flood_result = get_flood_risk_from_coords(float(x), float(y), country_code, postcode=postcode)
        if isinstance(flood_result, dict):
            flood = flood_result

    # Step 7: Merge — EPC preferred for construction fields
    result = {
        # Identity
        "uprn": str(uprn),
        "address": place.get("ADDRESS"),
        "postcode": place.get("POSTCODE"),
        "x_coordinate": x,
        "y_coordinate": y,
        "country_code": place.get("COUNTRY_CODE"),
        "match_score_OS": place.get("MATCH"),
        "match_description_OS": place.get("MATCH_DESCRIPTION"),

        # Cross-reference match quality
        "match_level_via_metric": cr["level"],
        "match_score_metric": cr["confidence"],
        "match_reasons": cr["reasons"],

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

        # Flood risk
        "flood_risk_band": flood.get("flood_risk_band"),
        "flood_risk_source": flood.get("flood_risk_source"),
        "flood_risk_note": flood.get("flood_risk_note"),

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

    # Flood risk
    flood: dict = {}
    country_code = place.get("COUNTRY_CODE")
    postcode = place.get("POSTCODE")
    if x is not None and y is not None and country_code:
        flood_result = get_flood_risk_from_coords(float(x), float(y), country_code, postcode=postcode)
        if isinstance(flood_result, dict):
            flood = flood_result

    result = {
        "uprn": str(uprn),
        "address": place.get("ADDRESS"),
        "postcode": place.get("POSTCODE"),
        "x_coordinate": x,
        "y_coordinate": y,
        "country_code": place.get("COUNTRY_CODE"),
        "match_score_OS": place.get("MATCH"),
        "match_description_OS": place.get("MATCH_DESCRIPTION"),

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

        "flood_risk_band": flood.get("flood_risk_band"),
        "flood_risk_source": flood.get("flood_risk_source"),
        "flood_risk_note": flood.get("flood_risk_note"),

        "osid": ngd.get("osid"),
    }

    return result


# ── Batch orchestrators ────────────────────────────────────


def _merge_property_result(
    uprn: str, place: dict, epc_data, ngd_building, listed_data: dict,
    include_match_score: bool = False,
    cross_ref: dict | None = None,
    flood_data: dict | None = None,
) -> dict:
    """Merge data from all sources into a single property dict.

    Shared by both single and batch orchestrators to avoid duplicating
    the merge logic.
    """
    has_epc = isinstance(epc_data, list) and len(epc_data) > 0
    epc = epc_data[0] if has_epc else {}

    ngd = {}
    if isinstance(ngd_building, dict):
        ngd = ngd_building.get("properties", {})

    result = {
        # Identity
        "uprn": str(uprn),
        "address": place.get("ADDRESS"),
        "postcode": place.get("POSTCODE"),
        "x_coordinate": place.get("X_COORDINATE"),
        "y_coordinate": place.get("Y_COORDINATE"),
        "country_code": place.get("COUNTRY_CODE"),
        "parent_uprn": place.get("PARENT_UPRN"),
        "classification_code": place.get("CLASSIFICATION_CODE"),
        "classification_description": place.get("CLASSIFICATION_CODE_DESCRIPTION"),
        "logical_status": place.get("LOGICAL_STATUS_CODE"),
        "match_score_OS": place.get("MATCH"),
        "match_description_OS": place.get("MATCH_DESCRIPTION"),

        # Cross-reference match quality (address-based lookups only; None for UPRN-based)
        "match_level_via_metric": cross_ref["level"] if cross_ref else None,
        "match_score_metric": cross_ref["confidence"] if cross_ref else None,
        "match_reasons": cross_ref["reasons"] if cross_ref else None,

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

        # Flood risk
        "flood_risk_band": flood_data.get("flood_risk_band") if flood_data else None,
        "flood_risk_source": flood_data.get("flood_risk_source") if flood_data else None,
        "flood_risk_note": flood_data.get("flood_risk_note") if flood_data else None,

        # NGD identifiers
        "osid": ngd.get("osid"),
    }

    if include_match_score:
        result["match_score_OS"] = place.get("MATCH")
        result["match_description_OS"] = place.get("MATCH_DESCRIPTION")

    return result


def get_final_info_from_addresses(
    addresses: list[str],
    email: str,
    places_key: str,
    ngd_key: str,
    epc_key: str,
) -> list[dict | str]:
    """Look up all available property data for multiple addresses.

    Batch version of get_final_info_from_address. Resolves addresses to
    UPRNs + coordinates once via OS Places, then shares those coordinates
    with NGD and Listed Building lookups (no redundant OS Places calls).

    Args:
        addresses: List of free-text address strings.
        email: Registered email for EPC API auth.
        places_key: OS Data Hub API key (Places API).
        ngd_key: OS Data Hub API key (NGD Features API).
        epc_key: EPC API key.

    Returns:
        List of result dicts (or error strings), one per input address.
    """
    # Step 1: Batch address -> UPRN + coordinates (one OS Places call per address)
    places = get_uprns_from_addresses(addresses, places_key)

    # Collect successful lookups for downstream batch calls
    valid_uprns = []
    valid_places = {}  # uprn -> place record
    ngd_coords = []    # (uprn, x, y) for NGD batch
    listed_inputs = [] # (uprn, place) for listed batch
    flood_coords = []  # (uprn, x, y, country_code, postcode) for flood batch
    cr_entries = []    # (input_address, matched_address, os_match, matched_record) for cross-reference batch
    cr_uprn_keys = []  # uprn_str for each cr_entry, to map results back

    for addr, place in zip(addresses, places):
        if isinstance(place, str):
            continue
        uprn = place.get("UPRN")
        if not uprn:
            continue
        uprn_str = str(uprn)
        valid_uprns.append(uprn_str)
        valid_places[uprn_str] = place

        x = place.get("X_COORDINATE")
        y = place.get("Y_COORDINATE")
        if x is not None and y is not None:
            ngd_coords.append((uprn_str, float(x), float(y)))
            listed_inputs.append((uprn_str, place))
            country_code = place.get("COUNTRY_CODE")
            if country_code:
                flood_coords.append((uprn_str, float(x), float(y), country_code, place.get("POSTCODE")))

        cr_entries.append((addr, place.get("ADDRESS", ""), float(place.get("MATCH") or 0), place))
        cr_uprn_keys.append(uprn_str)

    # Step 2: Batch EPC lookup
    epc_results = get_epcs_from_uprns(valid_uprns, email, epc_key) if valid_uprns else {}

    # Step 3: Batch NGD building lookup (using pre-resolved coordinates)
    ngd_results = get_buildings_from_coords_batch(ngd_coords, ngd_key) if ngd_coords else {}

    # Step 4: Batch listed building lookup (using pre-resolved place records)
    listed_results = get_listed_building_statuses(listed_inputs, places_key) if listed_inputs else {}

    # Step 5: Cross-reference scoring — reuses already-fetched place records,
    # so no extra OS Places calls (parent UPRN lookup only fires in AMBER cases).
    cr_list = cross_reference_batch(cr_entries, places_key) if cr_entries else []
    cr_results = dict(zip(cr_uprn_keys, cr_list))

    # Step 6: Batch flood risk lookup (reuses coordinates already resolved in Step 1)
    flood_results = get_flood_risks_from_coords_batch(flood_coords) if flood_coords else {}

    # Step 7: Merge results per address
    output: list[dict | str] = []
    for addr, place in zip(addresses, places):
        if isinstance(place, str):
            output.append(place)
            continue

        uprn = place.get("UPRN")
        if not uprn:
            output.append("No UPRN found for this address.")
            continue

        uprn_str = str(uprn)
        epc_data = epc_results.get(uprn_str, "No EPC certificates found.")
        ngd_building = ngd_results.get(uprn_str, {})
        listed_data = listed_results.get(uprn_str, {})

        output.append(_merge_property_result(
            uprn_str, place, epc_data, ngd_building, listed_data,
            include_match_score=True,
            cross_ref=cr_results.get(uprn_str),
            flood_data=flood_results.get(uprn_str),
        ))

    return output


def get_final_info_from_uprns(
    uprns: list[str | int],
    email: str,
    places_key: str,
    ngd_key: str,
    epc_key: str,
) -> list[dict | str]:
    """Look up all available property data for multiple UPRNs.

    Batch version of get_final_info_from_uprn. Resolves coordinates once
    via OS Places and shares them with downstream lookups.

    Args:
        uprns: List of UPRNs (str or int).
        email: Registered email for EPC API auth.
        places_key: OS Data Hub API key (Places API).
        ngd_key: OS Data Hub API key (NGD Features API).
        epc_key: EPC API key.

    Returns:
        List of result dicts (or error strings), one per input UPRN.
    """
    # Step 1: Batch UPRN -> coordinates
    places_map = get_coordinates_from_uprns(uprns, places_key)

    # Collect successful lookups
    valid_uprns = []
    ngd_coords = []
    listed_inputs = []
    flood_coords = []

    for uprn in uprns:
        uprn_str = str(uprn)
        place = places_map.get(uprn_str)
        if isinstance(place, str):
            continue
        valid_uprns.append(uprn_str)

        x = place.get("X_COORDINATE")
        y = place.get("Y_COORDINATE")
        if x is not None and y is not None:
            ngd_coords.append((uprn_str, float(x), float(y)))
            listed_inputs.append((uprn_str, place))
            country_code = place.get("COUNTRY_CODE")
            if country_code:
                flood_coords.append((uprn_str, float(x), float(y), country_code, place.get("POSTCODE")))

    # Step 2-5: Batch downstream lookups
    epc_results = get_epcs_from_uprns(valid_uprns, email, epc_key) if valid_uprns else {}
    ngd_results = get_buildings_from_coords_batch(ngd_coords, ngd_key) if ngd_coords else {}
    listed_results = get_listed_building_statuses(listed_inputs, places_key) if listed_inputs else {}
    flood_results = get_flood_risks_from_coords_batch(flood_coords) if flood_coords else {}

    # Step 6: Merge results per UPRN
    output: list[dict | str] = []
    for uprn in uprns:
        uprn_str = str(uprn)
        place = places_map.get(uprn_str)

        if isinstance(place, str):
            output.append(place)
            continue

        epc_data = epc_results.get(uprn_str, "No EPC certificates found.")
        ngd_building = ngd_results.get(uprn_str, {})
        listed_data = listed_results.get(uprn_str, {})

        output.append(_merge_property_result(
            uprn_str, place, epc_data, ngd_building, listed_data,
            flood_data=flood_results.get(uprn_str),
        ))

    return output


# ── Quick test ──────────────────────────────────────────────
if __name__ == "__main__":
    from block_detection import detect_block_properties

    PLACES_KEY = "7VakhnbibvboaY9eE0385zORrBJAc2sw"
    NGD_KEY = "7VakhnbibvboaY9eE0385zORrBJAc2sw"
    EPC_EMAIL = "igorshuvalov23@gmail.com"
    EPC_KEY = "9213b51f9af85ba4700865191700778f0cc7f3fc"

    test_addresses = ["Flat 1/1, 351 Holmlea Road, Cathcart, Glasgow, G44 4BP",
                      "Flat 2/1, 60 Grange Road, Battlefield, Glasgow, G42 9LF"]

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

    # Batch lookup — resolves addresses once, correct match scores preserved
    results = get_final_info_from_addresses(test_addresses, EPC_EMAIL, PLACES_KEY, NGD_KEY, EPC_KEY)

    # Block detection using the results (parent_uprn is now included)
    block_input = []
    for r in results:
        if isinstance(r, dict):
            block_input.append({
                "UPRN": r.get("uprn"),
                "PARENT_UPRN": r.get("parent_uprn"),
                "ADDRESS": r.get("address"),
                "X_COORDINATE": r.get("x_coordinate"),
                "Y_COORDINATE": r.get("y_coordinate"),
            })
    block_result = detect_block_properties(block_input, api_key=PLACES_KEY)

    print("\n" + "=" * 60)
    print("BLOCK SUMMARY")
    print("=" * 60)
    for bkey, bdata in block_result["blocks"].items():
        print(f"\n  {bkey}: {bdata['block_size']} properties (root UPRN: {bdata['root_parent_uprn']})")
        for uprn in bdata["properties"]:
            # Find input + matched address for this UPRN
            input_addr = "?"
            matched_addr = ""
            for addr, r in zip(test_addresses, results):
                if isinstance(r, dict) and r.get("uprn") == uprn:
                    input_addr = addr
                    matched_addr = r.get("address", "")
                    break
            print(f"      - {uprn}")
            print(f"          input:   {input_addr}")
            print(f"          matched: {matched_addr}")

    if block_result["standalone"]:
        print(f"\n  Standalone: {len(block_result['standalone'])} properties")
        for uprn in block_result["standalone"]:
            input_addr = "?"
            matched_addr = ""
            for addr, r in zip(test_addresses, results):
                if isinstance(r, dict) and r.get("uprn") == uprn:
                    input_addr = addr
                    matched_addr = r.get("address", "")
                    break
            print(f"      - {uprn}")
            print(f"          input:   {input_addr}")
            print(f"          matched: {matched_addr}")

    print("\n\n" + "=" * 60)
    print("PROPERTY DETAILS")
    print("=" * 60)
    for addr, result in zip(test_addresses, results):
        if isinstance(result, dict):
            print(f"\n  Input:   {addr}")
            print(f"  Matched: {result.get('address', 'unknown')}")
            for key, value in result.items():
                if key not in ("address",) and value is not None:
                    print(f"    {key:30s}: {value}")
        else:
            print(f"\n  Input: {addr}")
            print(f"  Error: {result}")
