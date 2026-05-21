from uprn_to_epc import get_epc_from_uprn

MY_EMAIL = "igorshuvalov23@gmail.com"
MY_API_KEY = "9213b51f9af85ba4700865191700778f0cc7f3fc"

TEST_UPRNS = [
    90074379,
    906421451,
    10023350964,
    100023336956,
    10002924680,
    200004166668,
    100021058498,
    10091054491,
    100020453013,
    10091856737,
    10008907302,
    100022811498,
    10070135288,
    200001227954,
    100023581984,
    10009033845,
    100022446870,
    10094702498,
    200003417498,
    100023699498,
    10009195498,
    100021851289,
    10033617773,
    200001036226,
    100023430756,
    10070210584,
    100022198570,
    10093974112,
    200002728095,
    100023127370,
    # --- Scotland: Edinburgh (906xxxxx) ---
    906421443,
    906000011,
    906000038,
    906000052,
    906000066,
    906000073,
    906000080,
    906000097,
    906000107,
    906000114,
    906000121,
    906000138,
    906000145,
    906000152,
    906000169,
    # --- Scotland: Glasgow (900xxxxx / 901xxxxx) ---
    900000012,
    900000029,
    900000036,
    900000043,
    900000050,
    901000017,
    901000024,
    901000031,
    901000048,
    901000055,
    # --- Scotland: Aberdeen (120xxxxxxx) ---
    120000001,
    120000018,
    120000025,
    120000032,
    120000049,
    # --- Scotland: Dundee (380xxxxx) ---
    380000013,
    380000020,
    380000037,
    380000044,
    380000051,
    # --- Scotland: Highland / Stirling / misc ---
    130052230,
    130052247,
    130052254,
    130052261,
    130052278,
    # --- England: additional mixed regions ---
    100010710498,
    100011634870,
    100012027498,
    100012345678,
    10024288961,
    10024288978,
    10024288985,
    10024288992,
    200003500001,
    200003500018,
]

for uprn in TEST_UPRNS:
    result = get_epc_from_uprn(uprn, MY_EMAIL, MY_API_KEY)
    if isinstance(result, list):
        latest = result[0]
        print(
            f"UPRN {uprn:<15} | "
            f"Current: {latest.get('current-energy-rating', 'N/A'):>2} | "
            f"Potential: {latest.get('potential-energy-rating', 'N/A'):>2} | "
            f"Age Band: {latest.get('construction-age-band', 'N/A')}"
        )
    else:
        print(f"UPRN {uprn:<15} | {result}")