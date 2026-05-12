# Block Detection — Grouping Properties by Parent Building

## Overview

`backend/geo/uprn maps/block_detection.py` groups a list of OS Places property records into blocks (buildings) by walking their `PARENT_UPRN` chains to find the root parent of each hierarchy. The entry point is `detect_block_properties`.

The central problem it solves: when a batch of addresses is resolved via OS Places, flats return with a `PARENT_UPRN` pointing to their parent building. That parent may itself have a parent (e.g. a block within an estate). The module resolves these chains in bulk and returns a clean block → flat mapping without making N individual API calls.

---

## Input

`detect_block_properties(props, api_key)` takes:

| Parameter | Type | Description |
|---|---|---|
| `props` | `list[dict]` | OS Places DPA/LPI records. Each must have `UPRN`; `PARENT_UPRN` is optional. |
| `api_key` | `str` | OS Places API key. Required — raises `ValueError` (with a logged warning) if omitted when any `PARENT_UPRN` values are present. |

---

## Output

```python
{
    "blocks": {
        "block_1": {
            "block_size": 3,
            "root_parent_uprn": "906421443",
            "properties": ["906421451", "906421452", "906421443"],
            "is_block_record": True   # present only when the block's own record is in the list
        },
        "block_2": { ... }
    },
    "standalone": ["200010045678"]   # UPRNs not part of any block
}
```

- `block_size` — total number of UPRNs in this block (including the block-level record itself if present).
- `root_parent_uprn` — the UPRN at the top of the hierarchy; used as the grouping key.
- `properties` — list of UPRN strings belonging to this block.
- `is_block_record` — set to `True` when the block's own address record (e.g. "99 Spean Street" as opposed to "Flat 1/1, 99 Spean Street") is in the result set.
- `standalone` — list of UPRN strings that have no `PARENT_UPRN` and are not referenced as a parent by any other property in the batch.

---

## Algorithm

### Step 1 — Build the parent map

Iterate over all input records and collect a `child_parent_map` (`UPRN → PARENT_UPRN`) for every property that has a `PARENT_UPRN`. Also compute `referenced_parents` — the set of all `PARENT_UPRN` values referenced by children. This set is used in Step 3 to identify block-level records.

### Step 2 — Batch-resolve all parents to their root

All unique `PARENT_UPRN` values (plus any block-level UPRNs in the input — see Step 3) are passed to `_resolve_root_parents_batch`. This function walks the hierarchy level by level, fetching one batch of UPRN lookups per depth level, up to `MAX_DEPTH = 5`.

For each UPRN at the current level it fetches the record and checks for a grandparent:
- If no grandparent, or if the grandparent was already seen in this chain (cycle guard) → this UPRN is the root.
- If a new grandparent exists → advance to the next level.

The result is a `root_map` — a dict mapping every input PARENT_UPRN to its resolved root PARENT_UPRN. If `api_key` is absent and `PARENT_UPRN` values are present, a `ValueError` is raised before this step is reached.

**API efficiency:** N unique parent UPRNs at depth D require at most D batch calls, not N × D individual calls. For a typical flat development (depth 1–2), this is 1–2 batch calls regardless of how many flats are in the input.

### Step 3 — Group properties

For each property in the input, one of three paths applies:

| Condition | Action |
|---|---|
| Has `PARENT_UPRN` | Resolve to root via `root_map`. Assign to existing block for that root, or create a new one. |
| No `PARENT_UPRN` but its own UPRN is in `referenced_parents` | This is the parent building itself. Group it with its children under its own UPRN as root. Marks block with `is_block_record = True`. |
| No `PARENT_UPRN` and not referenced by any child | Standalone — appended to the `standalone` list. |

### Step 4 — Post-grouping address substring check

After grouping, any property in `standalone` is cross-checked against all block members by address substring. Both addresses are normalised using `_normalize` from `address_confidence` (punctuation stripped, lowercased, whitespace collapsed) and compared bidirectionally.

If the standalone address is a substring of a block member's address, or vice versa, the standalone property is folded into that block and marked with `is_block_record = True`.

**Why this is needed:** OS AddressBase sometimes stores a building record (e.g. "99 SPEAN STREET") under a different UPRN than the `PARENT_UPRN` that its flats reference. In these cases the building record arrives in `standalone` rather than being detected in Step 3. The substring check catches this without requiring any additional API calls.

---

## Hierarchy resolution in detail

`_resolve_root_parents_batch` operates across levels:

```
Level 0  input:   [parent_A, parent_B, parent_C]
              ↓  batch UPRN lookup
Level 1  result:  A has grandparent X, B has no grandparent (root), C has grandparent X
              ↓  root_map: B → B;  next_level: A → X, C → X
Level 2  input:   [X]  (deduplicated)
              ↓  batch UPRN lookup
Level 2  result:  X has no grandparent (root)
              ↓  root_map: A → X, C → X
```

Cycle guard: each chain maintains a `seen` set. If a grandparent has already appeared in this chain it is treated as the root to prevent infinite loops.

---

## Edge cases handled

| Case | How it is handled |
|---|---|
| No `PARENT_UPRN` on a flat | Treated as standalone (data quality limitation — some Local Authorities don't populate this field). |
| Block-level record in the input | Detected via `referenced_parents` and grouped with its children (Step 3, second branch). |
| Nested hierarchy (flat → block → estate) | Resolved by `_resolve_root_parents_batch` up to `MAX_DEPTH = 5` levels. |
| UPRN chain cycle in OS data | Cycle guard in `seen_per_chain` stops traversal and uses the current position as the root. |
| API error mid-traversal | Treated as root — traversal stops and the deepest successfully resolved UPRN is used. |
| DPA/LPI UPRN mismatch | Post-grouping substring check folds the building record into the correct block without extra API calls. |
| `api_key` is `None` but `PARENT_UPRN` values are present | Logs a warning with the count of unresolvable UPRNs and raises `ValueError`. |

---

## Constants

| Constant | Value | Meaning |
|---|---|---|
| `MAX_DEPTH` | `5` | Maximum hierarchy levels to traverse when resolving root parents. |
