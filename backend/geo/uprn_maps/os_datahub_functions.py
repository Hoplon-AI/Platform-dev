"""OS Data Hub API wrappers.

Thin wrappers around the OS Places API for UPRN lookups and address searches.
API docs: https://osdatahub.os.uk/docs/places/overview

Both functions return either a DPA/LPI result dict on success, or an error
string on failure. Callers should check ``isinstance(result, dict)``.
"""

import requests


def get_coordinates_from_uprn(uprn, api_key):
    """Look up a UPRN and return its full address record (DPA or LPI).

    Uses the OS Places UPRN endpoint. This is an exact lookup — no fuzzy
    matching. The returned dict includes X_COORDINATE / Y_COORDINATE
    (British National Grid), ADDRESS, UPRN, PARENT_UPRN, POSTCODE, etc.

    Args:
        uprn: The UPRN to look up (str or int).
        api_key: OS Data Hub API key (Places API).

    Returns:
        dict: DPA/LPI record with address fields and BNG coordinates.
        str: Error message if no match or request fails.
    """

    url = "https://api.os.uk/search/places/v1/uprn"

    params = {
        'uprn': uprn,
        'key': api_key
    }

    try:
        response = requests.get(url, params=params)

        response.raise_for_status()

        data = response.json()

        if 'results' in data and len(data['results']) > 0:
            result = data['results'][0].get('DPA') or data['results'][0].get('LPI')
            return result
        else:
            return "No match found."

    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"


def get_uprn_from_address(address, api_key):
    """Search for an address and return the best-matching record.

    Uses the OS Places free-text search endpoint. Returns the top result
    only (maxresults=1). The returned dict includes a MATCH score (0.0-1.0)
    and MATCH_DESCRIPTION (EXACT / GOOD / FAIR / POOR) indicating how
    closely the query matched the canonical address.

    Args:
        address: Free-text address string (e.g. "30 Sycamore Drive, Carterton").
        api_key: OS Data Hub API key (Places API).

    Returns:
        dict: DPA/LPI record with UPRN, ADDRESS, MATCH, coordinates, etc.
        str: Error message if no match or request fails.
    """

    url = "https://api.os.uk/search/places/v1/find"

    params = {
        'query': address,
        'key': api_key,
        'maxresults': 1
    }

    try:
        response = requests.get(url, params=params)

        response.raise_for_status()

        data = response.json()

        if 'results' in data and len(data['results']) > 0:
            result = data['results'][0].get('DPA') or data['results'][0].get('LPI')
            return result
        else:
            return "No match found."

    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"


# Usage example
if __name__ == "__main__":
    MY_API_KEY = "Ajrj5AiJphBOM2GdP7KqVx6Ax6CTemtY"
    search_address = "10 Downing Street, London"
    search_address = "3/2 Grange Loan, Edinburgh, EH9 2NP"
    search_address = "Flat 9 Whittingham Court, Tower Hill"
    search_address = "Flat 2/1, 22 Brunton Street, Cathcart, Glasgow, G443DX"
    search_address = "Flat 2/1, 269 Holmlea Road, Cathcart, Glasgow, G44 4BU"
    #search_address = "1/8 Cables Wynd, Leith, Edinburgh EH6 6DU"
    #search_address = "30 Sycamore Drive, Carterton, OX18 3AT"

    #parent_uprn: 906421443

    #uprn = 90074379

    result = get_uprn_from_address(search_address, MY_API_KEY)

    if isinstance(result, dict):
        print(f"Address Provided:        {search_address}")
        print(f"ADDRESS:                 {result.get('ADDRESS')}")
        print(f"UPRN:                    {result.get('UPRN')}")
        print(f"UDPRN:                   {result.get('UDPRN')}")
        print(f"PARENT_UPRN:             {result.get('PARENT_UPRN')}")
        print(f"BUILDING_NAME:           {result.get('BUILDING_NAME')}")
        print(f"THOROUGHFARE_NAME:       {result.get('THOROUGHFARE_NAME')}")
        print(f"POST_TOWN:               {result.get('POST_TOWN')}")
        print(f"POSTCODE:                {result.get('POSTCODE')}")
        print(f"RPC:                     {result.get('RPC')}")
        print(f"X_COORDINATE:            {result.get('X_COORDINATE')}")
        print(f"Y_COORDINATE:            {result.get('Y_COORDINATE')}")
        print(f"STATUS:                  {result.get('STATUS')}")
        print(f"LOGICAL_STATUS_CODE:     {result.get('LOGICAL_STATUS_CODE')}")
        print(f"CLASSIFICATION_CODE:     {result.get('CLASSIFICATION_CODE')}")
        print(f"CLASSIFICATION_CODE_DESCRIPTION: {result.get('CLASSIFICATION_CODE_DESCRIPTION')}")
        print(f"LOCAL_CUSTODIAN_CODE:    {result.get('LOCAL_CUSTODIAN_CODE')}")
        print(f"LOCAL_CUSTODIAN_CODE_DESCRIPTION: {result.get('LOCAL_CUSTODIAN_CODE_DESCRIPTION')}")
        print(f"COUNTRY_CODE:            {result.get('COUNTRY_CODE')}")
        print(f"COUNTRY_CODE_DESCRIPTION: {result.get('COUNTRY_CODE_DESCRIPTION')}")
        print(f"POSTAL_ADDRESS_CODE:     {result.get('POSTAL_ADDRESS_CODE')}")
        print(f"POSTAL_ADDRESS_CODE_DESCRIPTION: {result.get('POSTAL_ADDRESS_CODE_DESCRIPTION')}")
        print(f"BLPU_STATE_CODE:         {result.get('BLPU_STATE_CODE')}")
        print(f"BLPU_STATE_CODE_DESCRIPTION: {result.get('BLPU_STATE_CODE_DESCRIPTION')}")
        print(f"TOPOGRAPHY_LAYER_TOID:   {result.get('TOPOGRAPHY_LAYER_TOID')}")
        print(f"WARD_CODE:               {result.get('WARD_CODE')}")
        print(f"LAST_UPDATE_DATE:        {result.get('LAST_UPDATE_DATE')}")
        print(f"ENTRY_DATE:              {result.get('ENTRY_DATE')}")
        print(f"BLPU_STATE_DATE:         {result.get('BLPU_STATE_DATE')}")
        print(f"LANGUAGE:                {result.get('LANGUAGE')}")
        print(f"MATCH:                   {result.get('MATCH')}")
        print(f"MATCH_DESCRIPTION:       {result.get('MATCH_DESCRIPTION')}")
        print(f"DELIVERY_POINT_SUFFIX:   {result.get('DELIVERY_POINT_SUFFIX')}")
    else:
        print(result)

    result = get_coordinates_from_uprn(906421451, MY_API_KEY)
    if isinstance(result, dict):
        print(f"X: {result.get('X_COORDINATE')}")
        print(f"Y: {result.get('Y_COORDINATE')}")
