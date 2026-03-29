""""
Detection of properties that belong in the same building block based on parent UPRN.

Edge cases handled:
- Null PARENT_UPRN: standalone houses or block-level records themselves
- Block-level records: if a property has no PARENT_UPRN but its own UPRN is
  another property's PARENT_UPRN, it is the block entry itself — group it with its children
- Nested hierarchies: large developments can have multi-level parent chains
  (flat → block → estate). We resolve the root parent via API lookups (up to MAX_DEPTH)
- Missing PARENT_UPRN on flats: data quality varies by Local Authority, so some
  flats may lack a PARENT_UPRN despite being in a block
- DPA/LPI UPRN mismatch: a building address (e.g. "99 Spean Street") may have a
  different UPRN than the one its flats reference as PARENT_UPRN. Post-grouping
  address matching catches these.
"""
import re
from backend.geo.uprn_maps.os_datahub_functions import (
    get_coordinates_from_uprn,
    get_coordinates_from_uprns,
)

MAX_DEPTH = 5  # max levels to traverse upward for nested hierarchies


def _resolve_root_parent(parent_uprn: str, api_key: str) -> str:
    """Walk up the PARENT_UPRN chain to find the root parent.

    Handles nested hierarchies like flat -> block -> estate by looking up each
    parent's own record until we find one with no PARENT_UPRN (the root).
    Returns the root PARENT_UPRN, or the deepest one found within MAX_DEPTH.
    """
    current = parent_uprn
    seen = {current}

    for _ in range(MAX_DEPTH):
        record = get_coordinates_from_uprn(current, api_key)
        if isinstance(record, str):
            # API error — stop traversing, use what we have
            break
        grandparent = record.get("PARENT_UPRN")
        if not grandparent or grandparent in seen:
            # reached the root or hit a cycle
            break
        seen.add(grandparent)
        current = grandparent

    return current


def _resolve_root_parents_batch(parent_uprns: list[str], api_key: str) -> dict[str, str]:
    """Resolve root parents for multiple UPRNs using batch lookups.

    Pre-fetches all parent UPRNs in one batch per hierarchy level (up to
    MAX_DEPTH levels), rather than making individual API calls per parent.

    Args:
        parent_uprns: List of PARENT_UPRNs to resolve.
        api_key: OS Data Hub API key (Places API).

    Returns:
        Dict mapping each input PARENT_UPRN to its resolved root PARENT_UPRN.
    """
    root_map: dict[str, str] = {}
    # current_level: UPRNs we need to look up at this level
    current_level = {u: u for u in parent_uprns}  # maps original -> current position
    seen_per_chain: dict[str, set] = {u: {u} for u in parent_uprns}

    for _ in range(MAX_DEPTH):
        # Collect unique UPRNs to look up at this level
        uprns_to_lookup = list(set(current_level.values()) - set(root_map.values()))
        if not uprns_to_lookup:
            break

        records = get_coordinates_from_uprns(uprns_to_lookup, api_key)

        next_level = {}
        for original, current in current_level.items():
            if original in root_map:
                continue

            record = records.get(str(current))
            if isinstance(record, str):
                # API error — stop traversing, use what we have
                root_map[original] = current
                continue

            grandparent = record.get("PARENT_UPRN")
            if not grandparent or str(grandparent) in seen_per_chain[original]:
                # Reached root or cycle
                root_map[original] = current
            else:
                seen_per_chain[original].add(str(grandparent))
                next_level[original] = str(grandparent)

        current_level = next_level
        if not current_level:
            break

    # Any remaining unresolved chains — use their current position
    for original, current in current_level.items():
        if original not in root_map:
            root_map[original] = current

    return root_map


def detect_block_properties(props: list[dict], api_key: str = None) -> dict:
    """Group properties by their root PARENT_UPRN to identify blocks.

    When api_key is provided, resolves nested hierarchies using batch API
    lookups (one call per hierarchy level) instead of individual calls per parent.

    Args:
        props: List of property dicts from OS Places API (must contain UPRN,
               may contain PARENT_UPRN).
        api_key: OS Data Hub API key. Required for nested hierarchy resolution.
                 If None, only single-level grouping is performed.

    Returns:
        Dict with keys "blocks" and "standalone":
        - blocks: dict of block_1, block_2, ... each with block_size, root_parent_uprn, properties
        - standalone: list of UPRNs that are not part of any block
    """
    # Build a set of all UPRNs in the input for block-level record detection
    all_uprns = {str(p.get("UPRN")) for p in props if p.get("UPRN")}

    # Collect parent_uprns used by properties in this batch
    child_parent_map = {}
    for prop in props:
        uprn = str(prop.get("UPRN", ""))
        parent = prop.get("PARENT_UPRN")
        if parent:
            child_parent_map[uprn] = str(parent)

    # Set of parent_uprns referenced by children — used to detect block-level records
    referenced_parents = set(child_parent_map.values())

    # Batch-resolve all unique parent UPRNs to their roots
    unique_parents = set(child_parent_map.values())
    # Also include block-level records (UPRNs that are referenced as parents)
    block_level_uprns = {str(p.get("UPRN", "")) for p in props
                        if not p.get("PARENT_UPRN") and str(p.get("UPRN", "")) in referenced_parents}
    all_to_resolve = unique_parents | block_level_uprns

    if api_key and all_to_resolve:
        root_cache = _resolve_root_parents_batch(list(all_to_resolve), api_key)
    else:
        root_cache = {u: u for u in all_to_resolve}

    def get_root(parent_uprn: str) -> str:
        return root_cache.get(parent_uprn, parent_uprn)

    # Group into blocks
    root_to_block = {}
    blocks = {}
    standalone = []
    block_count = 0

    for prop in props:
        uprn = str(prop.get("UPRN", ""))
        parent_uprn = prop.get("PARENT_UPRN")

        if parent_uprn:
            # Normal case: property has a parent, resolve to root
            root = get_root(str(parent_uprn))

            if root not in root_to_block:
                block_count += 1
                key = f"block_{block_count}"
                root_to_block[root] = key
                blocks[key] = {"block_size": 0, "root_parent_uprn": root, "properties": []}
            key = root_to_block[root]
            blocks[key]["block_size"] += 1
            blocks[key]["properties"].append(uprn)

        elif uprn in referenced_parents:
            # Block-level record: this property IS the parent building
            # Group it with its children under its own UPRN as root
            root = get_root(uprn)

            if root not in root_to_block:
                block_count += 1
                key = f"block_{block_count}"
                root_to_block[root] = key
                blocks[key] = {"block_size": 0, "root_parent_uprn": root, "properties": []}
            key = root_to_block[root]
            blocks[key]["block_size"] += 1
            blocks[key]["properties"].append(uprn)
            blocks[key]["is_block_record"] = True

        else:
            # Standalone property — no parent and not referenced as a parent
            standalone.append(uprn)

    # Post-grouping: check if any standalone property's address is a substring
    # of a block member's address (or vice versa). Catches the DPA/LPI mismatch
    # where e.g. "99 Spean Street" has a different UPRN than the PARENT_UPRN
    # that "Flat 1/1, 99 Spean Street" points to. No extra API calls needed.
    if standalone and blocks:
        prop_by_uprn = {str(p.get("UPRN", "")): p for p in props}

        def _norm_addr(addr: str) -> str:
            """Strip punctuation and collapse whitespace for substring matching."""
            text = re.sub(r"[^\w\s]", " ", addr.upper())
            return " ".join(text.split())

        # Collect normalised addresses for each block's members
        block_addresses: dict[str, list[str]] = {}
        for bkey, bdata in blocks.items():
            addrs = []
            for member_uprn in bdata["properties"]:
                addr = prop_by_uprn.get(member_uprn, {}).get("ADDRESS", "")
                if addr:
                    addrs.append(_norm_addr(addr))
            block_addresses[bkey] = addrs

        remaining_standalone = []
        for s_uprn in standalone:
            s_addr = _norm_addr(prop_by_uprn.get(s_uprn, {}).get("ADDRESS", ""))
            matched = False

            if s_addr:
                for bkey, addrs in block_addresses.items():
                    for block_addr in addrs:
                        if s_addr in block_addr or block_addr in s_addr:
                            blocks[bkey]["block_size"] += 1
                            blocks[bkey]["properties"].append(s_uprn)
                            blocks[bkey]["is_block_record"] = True
                            matched = True
                            break
                    if matched:
                        break

            if not matched:
                remaining_standalone.append(s_uprn)

        standalone = remaining_standalone

    return {"blocks": blocks, "standalone": standalone}


if __name__ == "__main__":
    API_KEY = "1cNGEE0jL0R5pXlDpPd55wyEXnIBCF2J"

    test_addresses = ["Flat 1/1, 351 Holmlea Road, Cathcart, Glasgow, G44 4BP",
                      "Flat 1/1, 351 Holmlea Road, Cathcart, Glasgow, G44 4BP",
                      "Flat 1/2, 351 Holmlea Road, Cathcart, Glasgow, G44 4BP",
                      "Flat 1/3, 351 Holmlea Road, Cathcart, Glasgow, G44 4BP",
                      "Flat 2/1, 351 Holmlea Road, Cathcart, Glasgow, G44 4BP",
                      "Flat 2/2, 351 Holmlea Road, Cathcart, Glasgow, G44 4BP",
                      "Flat 0/1, 60 Grange Road, Battlefield, Glasgow, G42 9LF",
                      "Flat 0/2, 60 Grange Road, Battlefield, Glasgow, G42 9LF",
                      "Flat 1/1, 60 Grange Road, Battlefield, Glasgow, G42 9LF",
                      "Flat 1/2, 60 Grange Road, Battlefield, Glasgow, G42 9LF",
                      "Flat 2/1, 60 Grange Road, Battlefield, Glasgow, G42 9LF",
                      "Flat 2/2, 60 Grange Road, Battlefield, Glasgow, G42 9LF",]

    test = ["flat 1/1 99 Spean Street, Cathcart, Glasgow, G44 4FA",
                "99 Spean Street, Cathcart, Glasgow, G44 4FA",
                "flat 1/2 99 Spean Street, Cathcart, Glasgow, G44 4FA",
                "flat 2/1 99 Spean Street, Cathcart, Glasgow, G44 4FA",
                "flat 2/2 99 Spean Street, Cathcart, Glasgow, G44 4FA",]

    props = get_uprns_from_addresses(test, API_KEY)

    result = detect_block_properties(props, api_key=API_KEY)
    print("Blocks:", result["blocks"])
    print("Standalone:", result["standalone"])