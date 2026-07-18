"""EPC lookup by UPRN via the MHCLG "Get energy performance of buildings data" service.

Replaces the retired Open Data Communities API (uprn_to_epc.py; access ended
30 May 2026). Auth is now a Bearer token (the API key issued by the new
service); email is no longer used for auth. Responses are JSON, not CSV.

Register / get a key at: https://get-energy-performance-data.communities.gov.uk/

Two-tier API:
  1. GET /api/domestic/search?uprn=   -> summary rows (includes certificateNumber)
  2. GET /api/certificate?certificate_number=  -> full 83-field certificate

get_epc_from_uprn() does both: searches by UPRN, then fetches the full
certificate for each result (most recent first). Each returned dict contains
ALL raw fields from the detail endpoint (new snake_case names) PLUS a set of
old kebab-case aliases (current-energy-rating, walls-description, ...) so the
existing downstream mapping in address_to_final.py / enrichment_worker.py keeps
working unchanged. Curate/strip the aliases once you've picked the fields.

Drop-in for uprn_to_epc: same function names and signatures.
"""

import os
import requests
from backend.geo.uprn_maps.address_confidence import compare_addresses
from backend.geo.uprn_maps.os_datahub_functions import get_coordinates_from_uprn

# ponytail: env-overridable in case the paths/host change again
EPC_SEARCH_URL = os.getenv(
    "EPC_API_URL",
    "https://api.get-energy-performance-data.communities.gov.uk/api/domestic/search",
)
EPC_CERT_URL = os.getenv(
    "EPC_CERT_URL",
    "https://api.get-energy-performance-data.communities.gov.uk/api/certificate",
)

TIMEOUT = 20


def _desc(value):
    """Pull the free-text 'description' out of a nested EPC field.

    walls/roofs/floors/main_heating are lists of {description, ...};
    window/hot_water/lighting are single {description, ...} dicts.
    """
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, dict):
        desc = value.get("description")
        # Some certs localise it as {"value": ..., "language": ...}.
        if isinstance(desc, dict):
            return desc.get("value")
        return desc
    return None


def _money(value):
    """New API wraps costs as {'value': N, 'currency': ...}; old API gave a scalar."""
    if isinstance(value, dict):
        return value.get("value")
    return value


def _legacy_aliases(d: dict) -> dict:
    """Old kebab-case keys the current downstream mapping reads.

    ponytail: back-compat shim so address_to_final.py / enrichment_worker.py
    keep working without edits. Delete once downstream reads the new
    snake_case fields directly.

    Shape fixes vs the retired API:
      - property-type: new schema's `property_type` is a numeric code, so we
        alias the readable `dwelling_type` ("Mid-floor flat") instead.
      - built-form: new schema gives only a numeric code with no text form —
        nulled here rather than write "5" to the DB. Decode via the service's
        EPC-codes endpoint if the value is needed; raw `built_form` stays in
        the returned dict.
      - costs: unwrapped from {value, currency} back to a scalar via _money().
      - construction-age-band: no direct equivalent in the new schema.
    """
    address = " ".join(
        str(d[k]).strip()
        for k in ("address_line_1", "address_line_2", "address_line_3")
        if d.get(k)
    )
    return {
        "current-energy-rating": d.get("current_energy_efficiency_band"),
        "potential-energy-rating": d.get("potential_energy_efficiency_band"),
        "walls-description": _desc(d.get("walls")),
        "roof-description": _desc(d.get("roofs")),
        "floor-description": _desc(d.get("floors")),
        "glazing-description": _desc(d.get("window")),
        "property-type": d.get("dwelling_type"),
        "built-form": None,
        "construction-age-band": None,
        "total-floor-area": d.get("total_floor_area"),
        "main-fuel": _desc(d.get("main_heating")),
        "secondary-heating": _desc(d.get("secondary_heating")),
        "extension-count": d.get("extensions_count"),
        "lighting-cost-current": _money(d.get("lighting_cost_current")),
        "heating-cost-current": _money(d.get("heating_cost_current")),
        "hot-water-cost-current": _money(d.get("hot_water_cost_current")),
        "lodgement-datetime": d.get("registration_date"),
        "address": address,
        "postcode": d.get("postcode"),
    }


def _search(session: requests.Session, uprn) -> list:
    """Return summary rows for a UPRN, most recent first (may be empty)."""
    resp = session.get(EPC_SEARCH_URL, params={"uprn": str(uprn), "size": 100}, timeout=TIMEOUT)
    resp.raise_for_status()
    rows = resp.json().get("data", [])
    rows.sort(key=lambda r: r.get("registrationDate") or "", reverse=True)
    return rows


def _fetch_certificate(session: requests.Session, certificate_number: str) -> dict:
    """Full certificate detail (all fields) + old-key aliases merged on top."""
    resp = session.get(
        EPC_CERT_URL, params={"certificate_number": certificate_number}, timeout=TIMEOUT
    )
    resp.raise_for_status()
    detail = resp.json().get("data", {})
    return {**detail, **_legacy_aliases(detail)}


def _full_certs_for_uprn(session: requests.Session, uprn) -> list | str:
    """search(uprn) -> fetch detail for each cert. List (newest first) or error string."""
    rows = _search(session, uprn)
    if not rows:
        return "No EPC certificates found."
    certs = []
    for row in rows:
        cert_no = row.get("certificateNumber")
        if cert_no:
            certs.append(_fetch_certificate(session, cert_no))
    return certs or "No EPC certificates found."


def get_epc_from_uprn(uprn, email, api_key):
    """Fetch all domestic EPC certificates (full detail) for a UPRN, most recent first.

    Args:
        uprn: The UPRN to look up (str or int).
        email: Unused (kept for signature compatibility; Bearer auth needs only the key).
        api_key: EPC API key, used directly as the Bearer token.

    Returns:
        list[dict]: Full certificate dicts (all raw fields + legacy aliases),
        most recent first, or
        str: Error message if none found / request fails.
    """
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    try:
        with requests.Session() as session:
            session.headers.update(headers)
            return _full_certs_for_uprn(session, uprn)
    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"


def get_epcs_from_uprns(uprns: list, email: str, api_key: str) -> dict[str, list | str]:
    """Fetch full EPC certificates for multiple UPRNs, reusing one HTTP session.

    Returns a dict mapping each UPRN (as str) to a list of full cert dicts,
    or to an error string if that lookup failed / found nothing.

    NOTE: this is now 2+ API calls per UPRN (1 search + 1 per certificate).
    """
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    results: dict[str, list | str] = {}
    with requests.Session() as session:
        session.headers.update(headers)
        for uprn in uprns:
            try:
                results[str(uprn)] = _full_certs_for_uprn(session, uprn)
            except requests.exceptions.RequestException as e:
                results[str(uprn)] = f"An error occurred: {e}"
    return results


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)  # standalone run: app normally loads this via main.py

    MY_EMAIL = os.getenv("EPC_EMAIL", "")
    MY_API_KEY = os.getenv("EPC_API_KEY", "")
    PLACES_API_KEY = os.getenv("OS_PLACES_API_KEY", "")
    print(f"Search:  {EPC_SEARCH_URL}")
    print(f"Cert:    {EPC_CERT_URL}")

    # ponytail: one runnable check — full lookup must return construction detail.
    result = get_epc_from_uprn(200004166668, MY_EMAIL, MY_API_KEY)
    assert isinstance(result, list) and result, f"expected certs, got: {result}"
    cert = result[0]
    assert cert["current-energy-rating"], "missing epc rating"
    assert cert.get("walls"), "missing raw construction detail (walls)"
    assert cert["walls-description"], "missing walls alias"
    print(f"Fields returned: {len(cert)}")
    print(f"  rating:  {cert['current-energy-rating']}")
    print(f"  walls:   {cert['walls-description']}")
    print(f"  roof:    {cert['roof-description']}")
    print(f"  floor:   {cert['floor-description']}")
    print(f"  area m2: {cert['total-floor-area']}")

    place = get_coordinates_from_uprn(200004166668, PLACES_API_KEY)
    if isinstance(place, dict):
        match = compare_addresses(place.get("ADDRESS", ""), cert["address"])
        print(f"OS Places: {place.get('ADDRESS','')}")
        print(f"EPC:       {cert['address']}")
        print(f"Score: {match['score']}  Confidence: {match['confidence']}")

    import json
    print("\n--- ALL FIELDS (most recent cert) ---")
    print(json.dumps(cert, indent=2, default=str, ensure_ascii=False))
