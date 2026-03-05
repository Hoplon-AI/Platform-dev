import requests


def get_uprn_from_address(address, api_key):

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
            return {
                'uprn': result.get('UPRN'),
                'matched_address': result.get('ADDRESS'),
                #'latitude': result.get('LAT'),
                #'longitude': result.get('LNG')
            }
        else:
            return "No match found."

    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"


# Usage example
#MY_API_KEY = "Ajrj5AiJphBOM2GdP7KqVx6Ax6CTemtY"
#search_address = "10 Downing Street, London"

#result = get_uprn_from_address(search_address, MY_API_KEY)

#if isinstance(result, dict):
    #print(f"Address Provided: {search_address}")
    #print(f"Matched Address:  {result['matched_address']}")
    #print(f"UPRN:             {result['uprn']}")
    #print(f"Latitude:         {result['latitude']}")
    #print(f"Longitude:        {result['longitude']}")
#else:
   #print(result)