import requests
from backend.geo.premium_uprn import get_uprn_from_address

LOCAL_API_URL = "http://127.0.0.1:8000/api/v1/geo/uprn/match"

addresses = [
    "10 Downing Street, London, SW1A 2AA",
    "Buckingham Palace, London, SW1A 1AA",
    "221B Baker Street, London, NW1 6XE",
    "1 Canada Square, Canary Wharf, London, E14 5AB",
    "30 St Mary Axe, London, EC3A 8BF",
    "Tower of London, London, EC3N 4AB",
    "1 Churchill Place, London, E14 5HP",
    "1 Cabot Square, London, E14 4QJ",
    "Broadcasting House, Portland Place, London, W1A 1AA",
    "1 Kensington Palace Gardens, London, W8 4QP",
    "Royal Albert Hall, Kensington Gore, London, SW7 2AP",
    "Natural History Museum, Cromwell Road, London, SW7 5BD",
    "British Museum, Great Russell Street, London, WC1B 3DG",
    "St Paul's Cathedral, St Paul's Churchyard, London, EC4M 8AD",
    "The Shard, 32 London Bridge Street, London, SE1 9SG",
    "1 Liverpool Street, London, EC2M 7QD",
    "100 Liverpool Street, London, EC2M 2RH",
    "22 Bishopsgate, London, EC2N 4BQ",
    "1 Bank Street, London, E14 4SG",
    "20 Fenchurch Street, London, EC3M 3BY",
    "1 Poultry, London, EC2R 8EJ",
    "1 Fleet Place, London, EC4M 7WS",
    "Harrods, 87-135 Brompton Road, London, SW1X 7XL",
    "Selfridges, 400 Oxford Street, London, W1A 1AB",
    "King's Cross Station, Euston Road, London, N1C 4QP",
    "Paddington Station, Praed Street, London, W2 1HQ",
    "Victoria Station, Terminus Place, London, SW1V 1JU",
    "Waterloo Station, York Road, London, SE1 7ND",
    "Liverpool Street Station, Liverpool Street, London, EC2M 7PY",
    "Euston Station, Euston Road, London, NW1 2RT",
    "1 Piccadilly, Manchester, M1 1RG",
    "Deansgate Square, Manchester, M15 4QH",
    "1 Spinningfields, Manchester, M3 3AP",
    "MediaCityUK, Salford Quays, Manchester, M50 2LH",
    "Town Hall, Albert Square, Manchester, M2 5DB",
    "1 Colmore Square, Birmingham, B4 6AA",
    "One Snowhill, Birmingham, B4 6GH",
    "Bullring Shopping Centre, Birmingham, B5 4BU",
    "Brindleyplace, Birmingham, B1 2JB",
    "The Mailbox, Birmingham, B1 1XL",
    "One Canada Square, Liverpool, L3 1HG",
    "Royal Liver Building, Pier Head, Liverpool, L3 1HU",
    "Liverpool ONE, Paradise Street, Liverpool, L1 8JF",
    "St George's Hall, Lime Street, Liverpool, L1 1JJ",
    "Albert Dock, Liverpool, L3 4BB",
    "Bridgewater Place, Water Lane, Leeds, LS11 5BZ",
    "1 City Square, Leeds, LS1 2ES",
    "Trinity Leeds, Albion Street, Leeds, LS1 5AT",
    "Leeds Town Hall, The Headrow, Leeds, LS1 3AD",
    "First Direct Arena, Arena Way, Leeds, LS2 8BY",
    "St Paul's Tower, Sheffield, S1 2LJ",
    "Heart of the City, Sheffield, S1 2GD",
    "Sheffield Town Hall, Pinstone Street, Sheffield, S1 2HH",
    "Meadowhall Centre, Sheffield, S9 1EP",
    "The Moor, Sheffield, S1 4PA",
    "Grey Street, Newcastle upon Tyne, NE1 6EE",
    "Quayside, Newcastle upon Tyne, NE1 3JE",
    "St James' Park, Newcastle upon Tyne, NE1 4ST",
    "Eldon Square, Newcastle upon Tyne, NE1 7JB",
    "The Sage Gateshead, Gateshead, NE8 2JR",
    "1 Bristol, Bristol, BS1 5TR",
    "Cabot Circus, Bristol, BS1 3BF",
    "Harbourside, Bristol, BS1 5TX",
    "Clifton Suspension Bridge, Bristol, BS8 3PA",
    "Temple Meads Station, Bristol, BS1 6QF",
    "Old Market Square, Nottingham, NG1 2BY",
    "Victoria Centre, Nottingham, NG1 3QN",
    "Lace Market, Nottingham, NG1 1PF",
    "Nottingham Castle, Nottingham, NG1 6EL",
    "Trent Bridge, Nottingham, NG2 6AG",
    "Highcross, Leicester, LE1 4AN",
    "Leicester Market, Leicester, LE1 5HQ",
    "King Power Stadium, Leicester, LE2 7FL",
    "New Walk, Leicester, LE1 7EA",
    "Leicester Cathedral, Leicester, LE1 5PZ",
    "West Quay, Southampton, SO15 1QE",
    "Ocean Village, Southampton, SO14 3TJ",
    "Southampton Docks, Southampton, SO14 2AQ",
    "Civic Centre, Southampton, SO14 7LP",
    "Guildhall Square, Southampton, SO14 7DU",
    "Gunwharf Quays, Portsmouth, PO1 3TU",
    "Historic Dockyard, Portsmouth, PO1 3LJ",
    "Commercial Road, Portsmouth, PO1 1EJ",
    "Southsea Seafront, Portsmouth, PO5 3AB",
    "The Hard, Portsmouth, PO1 3DT",
    "Churchill Square, Brighton, BN1 2RG",
    "The Lanes, Brighton, BN1 1HB",
    "Brighton Pier, Brighton, BN2 1TW",
    "North Laine, Brighton, BN1 4GH",
    "Brighton Station, Queens Road, Brighton, BN1 3XP",
    "Radcliffe Camera, Oxford, OX1 3BG",
    "Bodleian Library, Broad Street, Oxford, OX1 3BG",
    "Westgate Oxford, Castle Street, Oxford, OX1 1NX",
    "Carfax Tower, Oxford, OX1 1DB",
    "Christ Church, St Aldate's, Oxford, OX1 1DP",
    "King's College, King's Parade, Cambridge, CB2 1ST",
    "Grand Arcade, St Andrew's Street, Cambridge, CB2 3BJ",
    "Market Square, Cambridge, CB2 3QJ",
    "Fitzwilliam Museum, Trumpington Street, Cambridge, CB2 1RB",
    "Cambridge Station, Station Road, Cambridge, CB1 2JW",
]

API = "Ajrj5AiJphBOM2GdP7KqVx6Ax6CTemtY"

# Track by confidence band
stats = {
    'Green': {'total': 0, 'matches': 0},   # HIGH
    'Yellow': {'total': 0, 'matches': 0},  # MEDIUM
    'Red': {'total': 0, 'matches': 0},     # LOW
}
no_db = 0

for address in addresses:
    # Premium API
    response_premium = get_uprn_from_address(address, API)
    matched = response_premium['matched_address']
    postcode = matched.split(',')[-1].strip()
    uprn_premium = response_premium['uprn']

    # Local API
    response_local = requests.post(LOCAL_API_URL, json={"address": address, "postcode": postcode})
    data = response_local.json()
    best_match = data.get('best_match')
    uprn_local = best_match['uprn'] if best_match else None
    confidence_score = best_match['confidence_score'] if best_match else None
    confidence_band = best_match['confidence_band'] if best_match else None
    warnings = data.get('warnings', [])

    # Check for postcode not found warning
    postcode_missing = any("not found in ONS directory" in w for w in warnings)

    is_match = str(uprn_premium) == str(uprn_local)
    match_str = "MATCH" if is_match else "MISMATCH"
    flag = " [POSTCODE NOT IN DB]" if postcode_missing else ""

    if postcode_missing:
        no_db += 1
    elif confidence_band:
        stats[confidence_band]['total'] += 1
        if is_match:
            stats[confidence_band]['matches'] += 1

    print(f"{confidence_band:6} | {confidence_score} | {match_str:8} | {postcode}{flag}")

# Summary
print("\n" + "=" * 60)
print("ACCURACY BY CONFIDENCE BAND")
print("=" * 60)
for band in ['Green', 'Yellow', 'Red']:
    total = stats[band]['total']
    matches = stats[band]['matches']
    if total > 0:
        accuracy = matches / total * 100
        print(f"{band:6} (HIGH conf): {matches}/{total} = {accuracy:.1f}% accuracy")
    else:
        print(f"{band:6}: No samples")

print(f"\nPostcodes not in DB: {no_db}")
total_tested = sum(s['total'] for s in stats.values())
total_matches = sum(s['matches'] for s in stats.values())
print(f"Overall (excluding no_db): {total_matches}/{total_tested} = {total_matches/total_tested*100:.1f}%")





