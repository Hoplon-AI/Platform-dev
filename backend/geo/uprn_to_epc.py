import requests
import base64
import csv
import io


def get_epc_from_uprn(uprn, email, api_key):

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

test_U = [200004166668,
10002925710, 100021008224,
200003423587, 10023012454]

FIELDS_OF_INTEREST = {
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

    else:
        print(result)

print()
