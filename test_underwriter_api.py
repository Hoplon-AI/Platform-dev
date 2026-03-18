"""
Quick integration test for the Underwriter Dashboard API endpoints.
Run with:  python test_underwriter_api.py

Requires backend running on port 8000 with DEV_MODE=true.
"""

import json
import sys
import requests

BASE = "http://127.0.0.1:8000/api/v1/underwriter"
DEMO_PORTFOLIO_ID = "11111111-1111-1111-1111-111111111111"
ALBYN_PORTFOLIO_ID = "aaaaaaaa-0000-0000-0000-000000000001"

PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"
INFO = "\033[94m INFO\033[0m"

errors = []


def check(label: str, resp: requests.Response, assertions: list = None):
    ok = resp.status_code == 200
    status = PASS if ok else FAIL
    print(f"{status}  [{resp.status_code}]  {label}")

    if not ok:
        errors.append(f"{label}: HTTP {resp.status_code} — {resp.text[:200]}")
        return None

    data = resp.json()
    if assertions:
        for key, expected in assertions:
            val = data
            for part in key.split("."):
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    val = None
                    break
            if expected == "NOT_NULL":
                passed = val is not None
            elif expected == "LIST":
                passed = isinstance(val, list)
            elif expected == "GT_ZERO":
                passed = isinstance(val, (int, float)) and val > 0
            elif expected == "GTE_ZERO":
                passed = isinstance(val, (int, float)) and val >= 0
            else:
                passed = val == expected

            symbol = "  ✓" if passed else "  ✗"
            if not passed:
                errors.append(f"  {label} — {key}: expected {expected!r}, got {val!r}")
            print(f"  {'✓' if passed else '✗'}  {key} = {val!r}")

    return data


def print_section(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ─────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────
print_section("0. Health Check")
try:
    r = requests.get("http://127.0.0.1:8000/health", timeout=3)
    print(f"{PASS if r.status_code == 200 else FAIL}  Backend reachable — {r.json()}")
except Exception as e:
    print(f"{FAIL}  Cannot connect: {e}")
    print("      Start the server: uvicorn backend.main:app --reload --port 8000")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────
# 1. Portfolio dropdown
# ─────────────────────────────────────────────────────────────
print_section("1. GET /portfolios  (dropdown)")
r = requests.get(f"{BASE}/portfolios")
data = check("List portfolios", r, [
    ("", "LIST"),  # top-level is a list
])
if data:
    print(f"{INFO}  Returned {len(data)} portfolios")
    for p in data:
        print(f"       • {p.get('ha_id')} / {p.get('portfolio_name')} "
              f"— {p.get('block_count')} blocks, £{p.get('total_insured_value'):,.0f} TIV "
              f"| FRA RED:{p.get('fra_red_count')} AMBER:{p.get('fra_amber_count')} GREEN:{p.get('fra_green_count')}")


# ─────────────────────────────────────────────────────────────
# 2. Summary — ha_demo
# ─────────────────────────────────────────────────────────────
print_section("2. GET /portfolios/{id}/summary  (ha_demo)")
r = requests.get(f"{BASE}/portfolios/{DEMO_PORTFOLIO_ID}/summary")
data = check("ha_demo summary", r, [
    ("total_blocks",      "GT_ZERO"),
    ("total_insured_value", "GT_ZERO"),
    ("fra_amber_count",   "GTE_ZERO"),
    ("fra_green_count",   "GTE_ZERO"),
    ("fra_unassessed_count", "GTE_ZERO"),
    ("fraew_assessed_count", "GTE_ZERO"),
])
if data:
    print(f"\n  KPI cards preview:")
    print(f"    Total Insured Value : £{data.get('total_insured_value', 0):>14,.2f}")
    print(f"    Total Blocks        : {data.get('total_blocks', 0)}")
    print(f"    Total Units         : {data.get('total_units', 0)}")
    print(f"    FRA RED             : {data.get('fra_red_count', 0)}")
    print(f"    FRA AMBER           : {data.get('fra_amber_count', 0)}")
    print(f"    FRA GREEN           : {data.get('fra_green_count', 0)}")
    print(f"    FRA Unassessed      : {data.get('fra_unassessed_count', 0)}")
    print(f"    FRAEW Assessed      : {data.get('fraew_assessed_count', 0)}")
    print(f"    Combustible cladding: {data.get('combustible_cladding_blocks', 0)} blocks")
    print(f"    Height 11–18m       : {data.get('blocks_11_to_18m', 0)}")
    print(f"    Height 18–30m       : {data.get('blocks_18_to_30m', 0)}")


# ─────────────────────────────────────────────────────────────
# 2b. Summary — ha_albyn
# ─────────────────────────────────────────────────────────────
print_section("2b. GET /portfolios/{id}/summary  (ha_albyn)")
r = requests.get(f"{BASE}/portfolios/{ALBYN_PORTFOLIO_ID}/summary")
check("ha_albyn summary", r, [
    ("total_blocks", "GTE_ZERO"),
    ("ha_name",      "NOT_NULL"),
])


# ─────────────────────────────────────────────────────────────
# 3. Composition
# ─────────────────────────────────────────────────────────────
print_section("3. GET /portfolios/{id}/composition")
r = requests.get(f"{BASE}/portfolios/{DEMO_PORTFOLIO_ID}/composition")
data = check("ha_demo composition", r, [
    ("property_types",    "LIST"),
    ("wall_construction", "LIST"),
    ("age_banding",       "LIST"),
])
if data:
    print(f"\n  Property types:")
    for t in data.get("property_types", [])[:5]:
        print(f"    • {t.get('property_type'):20s} {t.get('property_count'):5d} properties  {t.get('unit_count'):5d} units")
    print(f"\n  Wall construction (top 5):")
    for w in data.get("wall_construction", [])[:5]:
        print(f"    • {w.get('wall_type'):40s} {w.get('count'):5d}")
    print(f"\n  Age banding:")
    for a in data.get("age_banding", [])[:6]:
        print(f"    • {a.get('age_band'):20s} {a.get('count'):5d}")


# ─────────────────────────────────────────────────────────────
# 4. Map markers
# ─────────────────────────────────────────────────────────────
print_section("4. GET /portfolios/{id}/map")
r = requests.get(f"{BASE}/portfolios/{DEMO_PORTFOLIO_ID}/map")
data = check("ha_demo map markers", r, [
    ("total_markers",  "GT_ZERO"),
    ("colour_counts",  "NOT_NULL"),
    ("markers",        "LIST"),
])
if data:
    print(f"\n  Colour counts: {data.get('colour_counts')}")
    print(f"  Total markers: {data.get('total_markers')}")
    print(f"\n  First 5 markers:")
    for m in data.get("markers", [])[:5]:
        lat = m.get("latitude")
        lon = m.get("longitude")
        colour = m.get("map_colour", "grey")
        colour_display = {"red": "🔴", "amber": "🟡", "green": "🟢", "grey": "⚪"}.get(colour, "?")
        print(f"    {colour_display} {m.get('block_name'):8s}  lat={lat}  lon={lon}  "
              f"FRA={m.get('fra_rag','—'):5s}  FRAEW={m.get('fraew_rag','—'):5s}  "
              f"units={m.get('unit_count')}  TIV=£{(m.get('total_sum_insured') or 0):,.0f}")
    # Validate coordinates are in Great Britain
    for m in data.get("markers", []):
        lat = m.get("latitude")
        lon = m.get("longitude")
        if lat and lon:
            if not (49.0 < float(lat) < 61.0 and -8.0 < float(lon) < 2.0):
                errors.append(f"Map: {m['block_name']} has out-of-GB coordinates: {lat}, {lon}")
                print(f"  ✗  {m['block_name']} out-of-GB coords: {lat}, {lon}")


# ─────────────────────────────────────────────────────────────
# 5. FRA blocks
# ─────────────────────────────────────────────────────────────
print_section("5. GET /portfolios/{id}/fra-blocks")
r = requests.get(f"{BASE}/portfolios/{DEMO_PORTFOLIO_ID}/fra-blocks")
data = check("ha_demo FRA blocks", r, [
    ("total_blocks", "GT_ZERO"),
    ("rag_summary",  "NOT_NULL"),
    ("blocks",       "LIST"),
])
if data:
    print(f"\n  RAG summary: {data.get('rag_summary')}")
    for b in data.get("blocks", [])[:8]:
        rag = b.get("fra_rag") or "—"
        colour = {"RED": "🔴", "AMBER": "🟡", "GREEN": "🟢"}.get(rag, "⚪")
        print(f"    {colour} {b.get('block_name'):8s}  RAG={rag:5s}  "
              f"date={b.get('fra_date') or '—':12s}  "
              f"in_date={b.get('is_in_date')}  "
              f"actions={b.get('total_actions') or 0}  overdue={b.get('overdue_actions') or 0}")

print_section("5a. GET /fra-blocks?rag_filter=AMBER")
r = requests.get(f"{BASE}/portfolios/{DEMO_PORTFOLIO_ID}/fra-blocks?rag_filter=AMBER")
data = check("FRA blocks — AMBER filter", r)
if data:
    print(f"  Returned {data.get('total_blocks')} blocks")

print_section("5b. GET /fra-blocks?rag_filter=unassessed")
r = requests.get(f"{BASE}/portfolios/{DEMO_PORTFOLIO_ID}/fra-blocks?rag_filter=unassessed")
data = check("FRA blocks — unassessed filter", r)
if data:
    print(f"  Returned {data.get('total_blocks')} unassessed blocks")


# ─────────────────────────────────────────────────────────────
# 6. FRAEW blocks
# ─────────────────────────────────────────────────────────────
print_section("6. GET /portfolios/{id}/fraew-blocks")
r = requests.get(f"{BASE}/portfolios/{DEMO_PORTFOLIO_ID}/fraew-blocks")
data = check("ha_demo FRAEW blocks", r, [
    ("total_blocks",  "GT_ZERO"),
    ("fraew_summary", "NOT_NULL"),
    ("blocks",        "LIST"),
])
if data:
    print(f"\n  FRAEW summary: {data.get('fraew_summary')}")
    for b in data.get("blocks", [])[:8]:
        rag = b.get("fraew_rag") or "—"
        colour = {"RED": "🔴", "AMBER": "🟡", "GREEN": "🟢"}.get(rag, "⚪")
        comb = "🔥" if b.get("has_combustible_cladding") else "  "
        acm  = "⚠ ACM" if b.get("aluminium_composite_cladding") else ""
        print(f"    {colour} {b.get('block_name'):8s}  RAG={rag:5s}  {comb} combustible  "
              f"EPS={b.get('eps_insulation_present')}  BS8414={b.get('bs8414_test_evidence')}  {acm}")

print_section("6a. GET /fraew-blocks?combustible_only=true")
r = requests.get(f"{BASE}/portfolios/{DEMO_PORTFOLIO_ID}/fraew-blocks?combustible_only=true")
data = check("FRAEW — combustible only", r)
if data:
    print(f"  Returned {data.get('total_blocks')} blocks with combustible cladding")


# ─────────────────────────────────────────────────────────────
# 7. Risk summary
# ─────────────────────────────────────────────────────────────
print_section("7. GET /portfolios/{id}/risk-summary")
r = requests.get(f"{BASE}/portfolios/{DEMO_PORTFOLIO_ID}/risk-summary")
data = check("ha_demo risk summary", r, [
    ("compliance_score", "NOT_NULL"),
    ("fra",              "NOT_NULL"),
    ("fraew",            "NOT_NULL"),
    ("urgent_blocks",    "LIST"),
])
if data:
    print(f"\n  Compliance score    : {data.get('compliance_score')}/100")
    fra = data.get("fra", {})
    fraew = data.get("fraew", {})
    print(f"  Total blocks        : {fra.get('total_blocks')}")
    print(f"  Blocks with FRA     : {fra.get('blocks_with_fra')}")
    print(f"  FRA in-date         : {fra.get('fra_in_date')}")
    print(f"  FRA out-of-date     : {fra.get('fra_out_of_date')}")
    print(f"  Total actions       : {fra.get('total_actions')}")
    print(f"  Overdue actions     : {fra.get('overdue_actions')}")
    print(f"  Blocks with FRAEW   : {fraew.get('blocks_with_fraew')}")
    print(f"  Combustible blocks  : {fraew.get('combustible_blocks')}")
    print(f"  No BS8414 + combust : {fraew.get('no_bs8414_combustible')}")
    urgent = data.get("urgent_blocks", [])
    if urgent:
        print(f"\n  Urgent blocks ({len(urgent)}):")
        for u in urgent:
            print(f"    ⚠  {u.get('block_name'):8s}  FRA={u.get('fra_rag') or '—'}  "
                  f"FRAEW={u.get('fraew_rag') or '—'}  "
                  f"overdue={u.get('overdue_action_count') or 0}")


# ─────────────────────────────────────────────────────────────
# 8. Error cases
# ─────────────────────────────────────────────────────────────
print_section("8. Error handling")
r = requests.get(f"{BASE}/portfolios/00000000-0000-0000-0000-000000000000/summary")
ok = r.status_code == 404
print(f"{'✓' if ok else '✗'}  Unknown portfolio returns 404 (got {r.status_code})")
if not ok:
    errors.append(f"Unknown portfolio should return 404, got {r.status_code}")


# ─────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────
print(f"\n{'═'*60}")
if errors:
    print(f"\033[91m  {len(errors)} FAILURE(S):\033[0m")
    for e in errors:
        print(f"    ✗  {e}")
else:
    print(f"\033[92m  All checks passed.\033[0m")
print(f"{'═'*60}\n")
