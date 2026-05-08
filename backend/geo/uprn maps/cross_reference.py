"""Cross-reference scoring for OS Places address matches.

Takes an input address, the OS Places matched address, the OS MATCH score,
and the full matched DPA/LPI record — returns a traffic-light confidence:

  GREEN  — definitely correct (exact match, or format mismatch but same property)
  AMBER  — building found but flat unknown (parent UPRN resolves to the building)
  RED    — serious warning (mismatch, or can't verify the parent building)

Uses COUNTRY_CODE from the matched record to handle Scottish (1/3) vs
English (Flat 3, 1 Street) flat notation.
"""

import re
from difflib import SequenceMatcher

from address_confidence import _normalize, compare_addresses
from os_datahub_functions import get_coordinates_from_uprn


# ── Postcode extraction ───────────────────────────────────

_POSTCODE_RE = re.compile(
    r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}",
    re.IGNORECASE,
)


def _extract_postcode(address: str) -> str | None:
    """Extract a UK postcode from an address string."""
    m = _POSTCODE_RE.search(address)
    return m.group(0).upper().replace(" ", "") if m else None


# ── Flat / unit detection ─────────────────────────────────

_FLAT_KEYWORDS_RE = re.compile(
    r"\b(flat|apt|apartment|unit|room|suite)\b",
    re.IGNORECASE,
)

# Scottish X/Y notation (e.g. "1/2", "3/1") but NOT postcodes.
# Requires the pattern to be preceded by start-of-string, comma, or space
# and NOT followed by a letter (which would indicate a postcode like "G42 9LF").
_SCOTTISH_FLAT_RE = re.compile(
    r"(?:^|[\s,])(\d+)\s*/\s*(\d+)(?=[\s,]|$)",
)

_FLOOR_FLAT_RE = re.compile(
    r"\b(\d+)\s*f\s*(\d+)\b",
    re.IGNORECASE,
)

_GROUND_BASEMENT_RE = re.compile(
    r"\b(gfl|gfr|bfl|bfr|ground\s+floor|basement)\b",
    re.IGNORECASE,
)

# Descriptors before a number that mean something OTHER than a flat.
# "Block 1" ≠ "Flat 1", "Tower 2" ≠ "Flat 2", etc.
_NON_FLAT_PREFIX_RE = re.compile(
    r"\b(block|building|tower|wing|phase|stair|entrance)\s+\d+\b",
    re.IGNORECASE,
)


def _has_flat_token(address: str) -> bool:
    """Check whether an address contains a flat/unit indicator."""
    if _FLAT_KEYWORDS_RE.search(address):
        return True
    # Strip postcode before checking Scottish notation to avoid false positives
    addr_no_postcode = _POSTCODE_RE.sub("", address)
    if _SCOTTISH_FLAT_RE.search(addr_no_postcode):
        return True
    if _FLOOR_FLAT_RE.search(address):
        return True
    if _GROUND_BASEMENT_RE.search(address):
        return True
    return False


def _is_subunit(matched_record: dict) -> bool:
    """Check if the matched OS Places record is a flat within a larger building."""
    parent = matched_record.get("PARENT_UPRN")
    return parent is not None and str(parent).strip() != ""


# ── Number extraction for format mismatch detection ───────

def _extract_flat_and_building(address: str, country_code: str | None = None) -> tuple[str | None, str | None]:
    """Extract (flat_number, building_number) from an address.

    Handles both English ("Flat 3, 1 Grange Road") and Scottish ("1/3 Grange Road")
    notations. Uses country_code hint when available but also tries both patterns.

    Returns:
        (flat_number, building_number) as strings, or None for either if not found.
    """
    flat_num = None
    building_num = None

    # Strip postcode to avoid false positives
    addr_clean = _POSTCODE_RE.sub("", address).strip()

    # Try English style first: "Flat X, Y Street" or "Flat X/Y, Z Street"
    # Captures optional /Y for Scottish notation after keyword (e.g. "Flat 0/1")
    eng_match = re.search(
        r"\b(?:flat|apt|apartment|unit|room|suite)\s+(\d+)(?:\s*/\s*(\d+))?\b",
        addr_clean,
        re.IGNORECASE,
    )
    if eng_match:
        if eng_match.group(2):
            # "Flat X/Y" — X is floor, Y is the actual flat number
            flat_num = eng_match.group(2)
        else:
            # "Flat X" — X is the flat number
            flat_num = eng_match.group(1)
        # Building number: first standalone number AFTER the flat designation
        remainder = addr_clean[eng_match.end():]
        bld_match = re.search(r"(?:^|[\s,]+)(\d+)\b", remainder)
        if bld_match:
            building_num = bld_match.group(1)

    # Try Edinburgh floor-flat codes: "1F1", "2F2", "0F2" etc.
    if flat_num is None:
        ff_match = _FLOOR_FLAT_RE.search(addr_clean)
        if ff_match:
            flat_num = ff_match.group(2)  # second digit is the flat
            remainder = addr_clean[ff_match.end():]
            bld_match = re.search(r"(?:^|[\s,]+)(\d+)\b", remainder)
            if bld_match:
                building_num = bld_match.group(1)

    # Try Scottish style: "X/Y" where X = building (or floor), Y = flat
    scot_match = _SCOTTISH_FLAT_RE.search(addr_clean)
    if scot_match:
        first, second = scot_match.group(1), scot_match.group(2)
        if country_code == "S":
            # Scottish convention: first = floor (or building), second = flat
            # In canonical AddressBase Scottish form "60/3", first = building, second = flat
            # In input "Flat 1/3, 60 Grange Road", the 1/3 = floor/flat
            if flat_num is None:
                # No English-style flat found, so this IS the flat designation
                flat_num = second
                # Look for building number after the X/Y pattern
                remainder = addr_clean[scot_match.end():]
                bld_match = re.search(r"(?:^|[\s,]+)(\d+)\b", remainder)
                if bld_match:
                    building_num = bld_match.group(1)
                else:
                    # The first number might be the building in canonical form (e.g. "60/3")
                    building_num = first
            elif building_num is None:
                # English match already got flat_num; X/Y may contain the building
                # e.g. "Flat 1/3, 60 Grange" — eng got flat=3, scot sees "1/3"
                # Look for building after the X/Y
                remainder = addr_clean[scot_match.end():]
                bld_match = re.search(r"(?:^|[\s,]+)(\d+)\b", remainder)
                if bld_match:
                    building_num = bld_match.group(1)
        else:
            # Non-Scottish or unknown: treat X/Y as floor/flat
            if flat_num is None:
                flat_num = second
                remainder = addr_clean[scot_match.end():]
                bld_match = re.search(r"(?:^|[\s,]+)(\d+)\b", remainder)
                if bld_match:
                    building_num = bld_match.group(1)
                else:
                    building_num = first

    # If we still don't have a building number, grab the first standalone number
    # after stripping all flat designators
    if building_num is None:
        stripped = addr_clean
        if eng_match:
            stripped = stripped[:eng_match.start()] + stripped[eng_match.end():]
        if scot_match:
            stripped = stripped[:scot_match.start()] + stripped[scot_match.end():]
        # Also strip floor-flat codes
        stripped = _FLOOR_FLAT_RE.sub("", stripped)
        bld_match = re.search(r"\b(\d+)\b", stripped)
        if bld_match:
            building_num = bld_match.group(1)

    return (flat_num, building_num)


def _extract_building_number(address: str) -> str | None:
    """Extract the primary building/house number from an address.

    Looks for the first standalone number that isn't part of a flat designator
    or postcode. Handles formats like "328 Holmlea Road", "348, HOLMLEA ROAD",
    "Flat 3, 1 Grange Road" (returns "1", not "3").
    """
    addr_clean = _POSTCODE_RE.sub("", address).strip()
    # Remove flat designators so we don't pick up the flat number
    # Handles "Flat 3", "Flat 0/1", "Flat 1/3", "Unit 5" etc.
    addr_clean = re.sub(
        r"\b(?:flat|apt|apartment|unit|room|suite)\s+\d+(?:\s*/\s*\d+)?\b", "", addr_clean, flags=re.IGNORECASE,
    )
    # Remove Scottish X/Y notation (e.g. "1/3" or "60/3")
    addr_clean = re.sub(r"(?:^|[\s,])(\d+)\s*/\s*(\d+)", " ", addr_clean)
    # Remove floor-flat codes
    addr_clean = re.sub(r"\b\d+\s*f\s*\d+\b", "", addr_clean, flags=re.IGNORECASE)
    # First remaining standalone number is the building number
    m = re.search(r"\b(\d+)\b", addr_clean)
    return m.group(1) if m else None


def _extract_street_tokens(address: str) -> set[str]:
    """Extract street-level tokens from an address (removing flat designators and postcode)."""
    text = address.lower()
    # Remove postcode
    text = _POSTCODE_RE.sub("", text)
    # Remove flat keywords and their numbers
    text = re.sub(r"\b(flat|apt|apartment|unit|room|suite)\s*\d*\b", "", text, flags=re.IGNORECASE)
    # Remove Scottish X/Y notation
    text = re.sub(r"(?:^|[\s,])(\d+)\s*/\s*(\d+)", " ", text)
    # Remove floor-flat codes
    text = re.sub(r"\b\d+\s*f\s*\d+\b", "", text, flags=re.IGNORECASE)
    # Normalize
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = set(text.split())
    # Remove pure numbers (building numbers already handled separately)
    tokens = {t for t in tokens if not t.isdigit()}
    return tokens


def _is_format_mismatch(
    input_address: str,
    matched_address: str,
    country_code: str | None = None,
) -> bool:
    """Detect when input and matched address are the same property with different flat notation.

    Returns True when:
      - Both have flat indicators
      - Postcodes match
      - Extracted flat number and building number match
      - Street tokens overlap significantly

    This is the guard for promoting a 0.7 (PARTIAL) OS score to GREEN.
    """
    # Both must have flat indicators
    if not _has_flat_token(input_address) or not _has_flat_token(matched_address):
        return False

    # Postcodes must match
    pc_input = _extract_postcode(input_address)
    pc_matched = _extract_postcode(matched_address)
    if pc_input and pc_matched and pc_input != pc_matched:
        return False

    # Extract flat + building numbers from both
    input_flat, input_bld = _extract_flat_and_building(input_address, country_code)
    matched_flat, matched_bld = _extract_flat_and_building(matched_address, country_code)

    # At least the flat numbers must match
    if input_flat is None or matched_flat is None:
        return False
    if input_flat != matched_flat:
        return False

    # Building numbers must match if both are present
    if input_bld and matched_bld and input_bld != matched_bld:
        return False

    # Street tokens should overlap (strip flat designators and postcodes, compare remainder)
    input_street = _extract_street_tokens(input_address)
    matched_street = _extract_street_tokens(matched_address)
    if input_street and matched_street:
        overlap = len(input_street & matched_street) / max(len(input_street), len(matched_street))
        if overlap < 0.5:
            return False

    return True


# ── Parent UPRN verification ──────────────────────────────

def _verify_parent_uprn(
    input_address: str,
    matched_record: dict,
    api_key: str,
) -> tuple[str, dict | None]:
    """Look up the parent UPRN and check if its address matches the input.

    Returns:
        ("AMBER", parent_record) if parent resolves and address matches input.
        ("RED", None) if no parent, lookup fails, or parent address doesn't match.
    """
    parent_uprn = matched_record.get("PARENT_UPRN")
    if not parent_uprn or str(parent_uprn).strip() == "":
        return ("RED", None)

    parent_record = get_coordinates_from_uprn(parent_uprn, api_key)
    if isinstance(parent_record, str):
        # Lookup failed
        return ("RED", None)

    parent_address = parent_record.get("ADDRESS", "")
    if not parent_address:
        return ("RED", None)

    comparison = compare_addresses(input_address, parent_address)
    if comparison["score"] >= 0.6:
        return ("AMBER", parent_record)
    else:
        return ("RED", None)


# ── Main cross-reference function ─────────────────────────

def cross_reference(
    input_address: str,
    matched_address: str,
    os_match: float,
    matched_record: dict,
    api_key: str,
) -> dict:
    """Score an OS Places address match with traffic-light confidence.

    Args:
        input_address: The original address as provided by the user.
        matched_address: The canonical address returned by OS Places.
        os_match: The OS Places MATCH score (0.0-1.0).
        matched_record: The full DPA/LPI dict from OS Places.
        api_key: OS Places API key (for parent UPRN lookup if needed).

    Returns:
        dict with keys:
            level: "GREEN" | "AMBER" | "RED"
            confidence: float 0.0-1.0
            reasons: list[str]
            input_has_flat: bool
            matched_is_subunit: bool
            parent_uprn: str | None
            parent_record: dict | None
            format_mismatch: bool
    """
    reasons = []
    country_code = matched_record.get("COUNTRY_CODE")
    parent_uprn = matched_record.get("PARENT_UPRN")
    parent_uprn_str = str(parent_uprn).strip() if parent_uprn else None

    input_has_flat = _has_flat_token(input_address)
    matched_subunit = _is_subunit(matched_record)
    format_mismatch = False
    parent_record = None

    # Address similarity (our own check, independent of OS score)
    norm_input = _normalize(input_address)
    norm_matched = _normalize(matched_address)
    addr_similarity = SequenceMatcher(None, norm_input, norm_matched).ratio()

    # ── Number extraction for early mismatch checks ─────────
    # Uses _extract_flat_and_building (handles Scottish canonical "60/3" correctly)
    # rather than _extract_building_number (which loses the building in X/Y form).

    input_flat_num, input_bld_num = _extract_flat_and_building(input_address, country_code)
    matched_flat_num, matched_bld_num = _extract_flat_and_building(matched_address, country_code)

    # Building number mismatch → immediate RED
    # Catches "328 Holmlea Road" matching "348 Holmlea Road" and also
    # "60 Holmlea Road" matching "62/1, HOLMLEA ROAD" (building 60 vs 62).
    if input_bld_num and matched_bld_num and input_bld_num != matched_bld_num:
        reasons.append("building_number_mismatch")
        return _build_result(
            "RED", min(os_match, 0.30), reasons,
            input_has_flat, matched_subunit, parent_uprn_str, None, False,
        )

    # Flat number mismatch → immediate RED
    # Catches "Flat 1, 60 Grange Road" matching "FLAT 3, 60, GRANGE ROAD"
    # where OS score is high (~0.9) because most tokens match, but it's
    # the wrong flat.
    if input_flat_num and matched_flat_num and input_flat_num != matched_flat_num:
        reasons.append("flat_number_mismatch")
        return _build_result(
            "RED", min(os_match, 0.30), reasons,
            input_has_flat, matched_subunit, parent_uprn_str, None, False,
        )

    # ── GREEN checks ──────────────────────────────────────

    # (a) Exact match
    if os_match == 1.0:
        reasons.append("exact_match")
        return _build_result(
            "GREEN", max(os_match, 0.95), reasons,
            input_has_flat, matched_subunit, parent_uprn_str, None, False,
        )

    # (b) GOOD match (>= 0.8) with structural alignment and high address similarity
    # Compare input address vs matched ADDRESS (not matched record's PARENT_UPRN).
    # "22 Rowntree Lodge" and "22 ROWNTREE LODGE" are structurally identical even
    # though the record is a sub-unit in the database.
    matched_addr_has_flat = _has_flat_token(matched_address)
    structural_alignment = (input_has_flat == matched_addr_has_flat)
    if os_match >= 0.8 and addr_similarity >= 0.8 and structural_alignment:
        reasons.append("good_match_aligned")
        return _build_result(
            "GREEN", os_match, reasons,
            input_has_flat, matched_subunit, parent_uprn_str, None, False,
        )

    # (b2) Input has extra descriptors that OS stripped — matched is a clean subset.
    # e.g. "Guest Room 28 Rowntree Lodge" → "28 ROWNTREE LODGE" (OS dropped "Guest Room")
    # Safe because matched didn't ADD anything (unlike "60 Grange Rd" → "60/1, GRANGE RD"
    # where OS added a flat number "1").
    if os_match >= 0.8 and addr_similarity >= 0.85:
        matched_tokens = set(norm_matched.split())
        input_tokens = set(norm_input.split())
        if matched_tokens.issubset(input_tokens):
            reasons.append("good_match_input_has_extra_descriptors")
            return _build_result(
                "GREEN", os_match, reasons,
                input_has_flat, matched_subunit, parent_uprn_str, None, False,
            )

    # (c) PARTIAL match (~0.7) but format mismatch confirms same property
    if os_match >= 0.7:
        format_mismatch = _is_format_mismatch(input_address, matched_address, country_code)
        if format_mismatch:
            reasons.append("format_mismatch_same_property")
            return _build_result(
                "GREEN", max(os_match, 0.80), reasons,
                input_has_flat, matched_subunit, parent_uprn_str, None, True,
            )

    # ── Implicit flat number: "117 Parker Court" = "FLAT 117, PARKER COURT" ──
    # When the input has no flat keyword but its "building number" equals the
    # matched record's flat number, and the rest of the address aligns, the
    # user just omitted "Flat". Common with purpose-built apartment blocks.
    # Guard: "Block 1", "Tower 2" etc. are NOT implicit flat numbers.

    if not input_has_flat and matched_subunit:
        has_non_flat_prefix = bool(_NON_FLAT_PREFIX_RE.search(input_address))
        if (not has_non_flat_prefix
                and input_bld_num and matched_flat_num
                and input_bld_num == matched_flat_num
                and os_match >= 0.7):
            input_street = _extract_street_tokens(input_address)
            matched_street = _extract_street_tokens(matched_address)
            if input_street and matched_street:
                overlap = len(input_street & matched_street) / max(len(input_street), len(matched_street))
                if overlap >= 0.6:
                    reasons.append("implicit_flat_number_matches")
                    return _build_result(
                        "GREEN", os_match, reasons,
                        input_has_flat, matched_subunit, parent_uprn_str, None, False,
                    )

    # ── AMBER / RED: missing flat number, matched a sub-unit ──

    if not input_has_flat and matched_subunit:
        level, parent_record = _verify_parent_uprn(input_address, matched_record, api_key)
        if level == "AMBER":
            reasons.append("parent_uprn_resolves_to_building")
            return _build_result(
                "AMBER", 0.50, reasons,
                input_has_flat, matched_subunit, parent_uprn_str, parent_record, False,
            )
        else:
            if not parent_uprn_str:
                reasons.append("missing_flat_no_parent_uprn")
            else:
                reasons.append("missing_flat_parent_mismatch")
            return _build_result(
                "RED", min(os_match, 0.30), reasons,
                input_has_flat, matched_subunit, parent_uprn_str, None, False,
            )

    # ── RED: other mismatches ─────────────────────────────

    # Postcode mismatch → RED
    # Even a one-letter postcode difference (OX29 6SP vs OX29 6SG) means a
    # different address. OS Places sometimes returns a near-postcode match
    # for an unrelated property when no good match exists.
    pc_input = _extract_postcode(input_address)
    pc_matched = _extract_postcode(matched_address)
    if pc_input and pc_matched and pc_input != pc_matched:
        reasons.append("postcode_mismatch")
        return _build_result(
            "RED", min(os_match, 0.30), reasons,
            input_has_flat, matched_subunit, parent_uprn_str, None, format_mismatch,
        )

    # Address similarity very low
    if addr_similarity < 0.4:
        reasons.append("low_address_similarity")
        return _build_result(
            "RED", min(os_match, 0.30), reasons,
            input_has_flat, matched_subunit, parent_uprn_str, None, format_mismatch,
        )

    # OS score high but our similarity disagrees
    if os_match >= 0.8 and addr_similarity < 0.5:
        reasons.append("high_os_score_low_similarity")
        return _build_result(
            "RED", min(os_match, 0.30), reasons,
            input_has_flat, matched_subunit, parent_uprn_str, None, format_mismatch,
        )

    # OS score low
    if os_match < 0.7:
        reasons.append("low_os_match")
        return _build_result(
            "RED", min(os_match, 0.30), reasons,
            input_has_flat, matched_subunit, parent_uprn_str, None, format_mismatch,
        )

    # ── Fallback: moderate score, no red flags ────────────

    # OS 0.7-0.8 range, structural alignment, reasonable similarity
    # Also require street tokens to overlap — postcode match alone isn't enough
    # because OS sometimes returns a near-postcode result on a different street.
    if structural_alignment and addr_similarity >= 0.5:
        input_street = _extract_street_tokens(input_address)
        matched_street = _extract_street_tokens(matched_address)
        street_overlap = 0.0
        if input_street and matched_street:
            street_overlap = len(input_street & matched_street) / max(len(input_street), len(matched_street))
        if street_overlap >= 0.6:
            reasons.append("moderate_match_aligned")
            return _build_result(
                "GREEN", os_match, reasons,
                input_has_flat, matched_subunit, parent_uprn_str, None, format_mismatch,
            )

    # Anything else: cautious RED
    reasons.append("uncertain_match")
    return _build_result(
        "RED", min(os_match, 0.30), reasons,
        input_has_flat, matched_subunit, parent_uprn_str, None, format_mismatch,
    )


def _build_result(
    level: str,
    confidence: float,
    reasons: list[str],
    input_has_flat: bool,
    matched_is_subunit: bool,
    parent_uprn: str | None,
    parent_record: dict | None,
    format_mismatch: bool,
) -> dict:
    return {
        "level": level,
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "reasons": reasons,
        "input_has_flat": input_has_flat,
        "matched_is_subunit": matched_is_subunit,
        "parent_uprn": parent_uprn,
        "parent_record": parent_record,
        "format_mismatch": format_mismatch,
    }


# ── Batch variant ─────────────────────────────────────────

def cross_reference_batch(
    entries: list[tuple[str, str, float, dict]],
    api_key: str,
) -> list[dict]:
    """Score multiple OS Places matches.

    Args:
        entries: List of (input_address, matched_address, os_match, matched_record) tuples.
        api_key: OS Places API key.

    Returns:
        List of result dicts, one per entry.
    """
    return [
        cross_reference(input_addr, matched_addr, os_match, record, api_key)
        for input_addr, matched_addr, os_match, record in entries
    ]


# ── Quick test ────────────────────────────────────────────

if __name__ == "__main__":
    PLACES_KEY = "7VakhnbibvboaY9eE0385zORrBJAc2sw"


    # ── Live comparison: OS Places vs our cross-reference ──
    # Feed addresses through address_to_final pipeline, then compare
    # OS confidence against our traffic-light scoring.

    from os_datahub_functions import get_uprns_from_addresses

    test_addresses = [
'91 Albert Street, Riverside, Cardiff, CF11 6JQ',
'110 Albert Street, Riverside, Cardiff, CF11 6JP',
'16 Alexandra Court, Ethel Street, Canton, Cardiff, CF5 1EN',
]

    os_results = get_uprns_from_addresses(test_addresses, PLACES_KEY)

    rows = []
    for input_addr, os_record in zip(test_addresses, os_results):
        if isinstance(os_record, str):
            rows.append((input_addr, f"ERROR: {os_record}", "-", "-", os_record))
            continue

        matched_addr = os_record.get("ADDRESS", "")
        os_match = os_record.get("MATCH", 0.0)
        cr = cross_reference(input_addr, matched_addr, os_match, os_record, PLACES_KEY)

        our_conf = f"{cr['level']} {cr['confidence']:.2f}"
        reasoning = ", ".join(cr["reasons"])
        rows.append((input_addr, matched_addr, f"{os_match:.2f}", our_conf, reasoning))

    col_w = [max(len(r[i]) for r in rows + [("Input", "Matched", "OS conf", "Our conf", "Reasoning")]) for i in range(5)]
    header = ("Input", "Matched", "OS conf", "Our conf", "Reasoning")
    sep = "  ".join("-" * w for w in col_w)
    fmt = "  ".join(f"{{:<{w}}}" for w in col_w)

    print("\n\n" + fmt.format(*header))
    print(sep)
    for row in rows:
        print(fmt.format(*row))
