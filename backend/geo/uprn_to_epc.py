"""EPC (Energy Performance Certificate) lookup by UPRN - works only for England and Wales.

Queries the Open Data Communities domestic EPC API to retrieve certificate
history for a given UPRN. Auth is via Basic auth (email + API key).
Register at: https://epc.opendatacommunities.org/

Returns a list of certificate dicts (most recent first) on success,
or an error string on failure. Each cert contains ~90 fields; see
FIELDS_OF_INTEREST below for the most useful ones.
"""

import requests
import base64
import csv
import io
from address_confidence import compare_addresses
from os_datahub_functions import get_coordinates_from_uprn


def get_epc_from_uprn(uprn, email, api_key):
    """Fetch all domestic EPC certificates for a UPRN.

    This is an exact UPRN lookup — no fuzzy matching. The API returns
    certificates ordered by lodgement date (most recent first). A property
    can have multiple certificates if it has been re-assessed.

    The response includes address fields (address, address1, address2,
    address3, postcode) which can be cross-validated against the original
    input address using address_confidence.compare_addresses().

    Args:
        uprn: The UPRN to look up (str or int).
        email: Registered email for EPC API auth.
        api_key: EPC API key.

    Returns:
        list[dict]: List of certificate dicts (up to 100), most recent first.
            Key fields: current-energy-rating, property-type, built-form,
            total-floor-area, construction-age-band, walls-description,
            roof-description, address, postcode.
        str: Error message if no certificates found or request fails.
    """

    url = "https://epc.opendatacommunities.org/api/v1/domestic/search"

    token = base64.b64encode(f"{email}:{api_key}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Accept": "text/csv",
    }

    params = {"uprn": str(uprn), "size": 100}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)

        if len(rows) > 0:
            return rows
        else:
            return "No EPC certificates found."

    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"

MY_EMAIL = "igorshuvalov23@gmail.com"
MY_API_KEY = "9213b51f9af85ba4700865191700778f0cc7f3fc"
PLACES_API_KEY = "Ajrj5AiJphBOM2GdP7KqVx6Ax6CTemtY"

test_U = [200004166668,
10002925710, 100021008224,
200003423587, 10023012454]

FIELDS_OF_INTEREST = {
    "address": "Address",
    "lodgement-datetime": "Lodgement Date",
    "property-type": "Property Type",
    "built-form": "Built Form",
    "walls-description": "Wall Type / Insulation",
    "roof-description": "Roof Type",
    "main-fuel": "Main Fuel",
    "total-floor-area": "Total Floor Area (m²)",
    "construction-age-band": "Year of Build (Band)",
    "extension-count": "Extension Count",
    "number-open-fireplaces": "Open Fireplaces",
    "current-energy-rating": "EPC Rating",
    "potential-energy-rating": "Potential EPC Rating",
    "transaction-type": "Transaction Type",
    "lighting-cost-current": "Lighting Cost (£)",
    "heating-cost-current": "Heating Cost (£)",
    "hot-water-cost-current": "Hot Water Cost (£)",
}

for test_uprns in test_U:

    result = get_epc_from_uprn(test_uprns, MY_EMAIL, MY_API_KEY)

    if isinstance(result, list):
        print(f"Found {len(result)} certificate(s) — showing most recent:\n")
        cert = result[0]
        for api_key, label in FIELDS_OF_INTEREST.items():
            print(f"  {label:30s}: {cert.get(api_key, 'N/A')}")

        # Cross-validate: compare OS Places address with EPC address
        place = get_coordinates_from_uprn(test_uprns, PLACES_API_KEY)
        if isinstance(place, dict):
            os_address = place.get("ADDRESS", "")
            epc_address = cert.get("address", "")
            match = compare_addresses(os_address, epc_address)
            print(f"\n  --- Address Cross-Validation ---")
            print(f"  OS Places:  {os_address}")
            print(f"  EPC:        {epc_address}")
            print(f"  Score: {match['score']}  Confidence: {match['confidence']}")

    else:
        print(result)

    print()
