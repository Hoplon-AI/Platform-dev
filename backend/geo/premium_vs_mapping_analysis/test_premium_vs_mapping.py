import requests
from backend.geo.premium_vs_mapping_analysis.premium_uprn import get_uprn_from_address
from backend.geo.premium_vs_mapping_analysis.addresses import addresses

LOCAL_API_URL = "http://127.0.0.1:8000/api/v1/geo/uprn/match"



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
        print(f"{band:6} (conf): {matches}/{total} = {accuracy:.1f}% accuracy")
    else:
        print(f"{band:6}: No samples")

print(f"\nPostcodes not in DB: {no_db}")
total_tested = sum(s['total'] for s in stats.values())
total_matches = sum(s['matches'] for s in stats.values())
print(f"Overall (excluding no_db): {total_matches}/{total_tested} = {total_matches/total_tested*100:.1f}%")





