# Address Cross-Reference Scoring

## Overview

`backend/geo/uprn maps/cross_reference.py` re-scores OS Places address matches independently of the OS confidence score. It returns a traffic-light level (`GREEN` / `AMBER` / `RED`) plus a numeric confidence (0.0–1.0).

The OS Places MATCH score alone is not sufficient — a score of 0.9 can still represent the wrong flat in the same building, and a score of 0.7 can be a perfectly correct match with a formatting difference. The cross-reference scorer catches both of these cases.

---

## Inputs

| Parameter | Type | Description |
|---|---|---|
| `input_address` | `str` | Raw address as supplied by the user |
| `matched_address` | `str` | Canonical address returned by OS Places |
| `os_match` | `float` | OS Places MATCH score (0.0–1.0) |
| `matched_record` | `dict` | Full DPA/LPI record from OS Places; used for `PARENT_UPRN` and `COUNTRY_CODE` |
| `api_key` | `str` | OS Places API key; only used if a parent UPRN lookup is needed |

---

## Pre-computation

Before any branching the scorer derives these values used throughout:

| Value | How it is computed |
|---|---|
| `addr_similarity` | `SequenceMatcher` ratio on normalised (lowercase, punctuation-stripped) versions of both addresses |
| `input_has_flat` | True if the input contains a flat keyword (`flat`, `apt`, `unit`, `room`, `suite`), a Scottish `X/Y` notation, an Edinburgh floor-flat code (`1F2`), or `ground floor` / `basement` |
| `matched_subunit` | True if the OS record has a non-empty `PARENT_UPRN` |
| `structural_alignment` | True when `input_has_flat == _has_flat_token(matched_address)` — both sides agree on whether a flat/unit indicator is present |
| `input_bld_num` / `matched_bld_num` | Building number extracted after removing flat designators and postcodes |
| `input_flat_num` / `matched_flat_num` | Flat number extracted via `_extract_flat_and_building`, handling English (`Flat 3, 1 Grange Rd`), Edinburgh floor-flat (`1F2`), and Scottish canonical (`60/3`) notations |

---

## Decision Flow

### Step 1 — Immediate RED: number mismatch

Fires before any GREEN check. A number mismatch is unambiguous regardless of OS score.

| Condition | Reason code | Confidence |
|---|---|---|
| Both sides have a building number and they differ | `building_number_mismatch` | min(os_match, 0.30) |
| Both sides have a flat number and they differ | `flat_number_mismatch` | min(os_match, 0.30) |

---

### Step 2 — GREEN paths (evaluated in order)

**(a) Exact match**
`os_match == 1.0` → GREEN, confidence = max(os_match, 0.95).

**(b) Good match with structural alignment**
`os_match >= 0.8` AND `addr_similarity >= 0.8` AND `structural_alignment` AND the matched address does not introduce a building number the input is missing → GREEN, confidence = os_match.

The building-number guard prevents `"Beech Grove, Selby, YO8 4AS"` → `"1, BEECH GROVE, SELBY, YO8 4AS"` from being promoted to GREEN when the user omitted the house number entirely.

**(b2) Input has extra descriptors, matched is a clean subset**
`os_match >= 0.8` AND `addr_similarity >= 0.85` AND `structural_alignment` AND every token in the normalised matched address also appears in the normalised input → GREEN, confidence = os_match.

`structural_alignment` is required here to prevent cases where the input has a room/flat indicator but the matched address is just the parent building. Without this guard, `"Room 1, 1 Heron Rise"` and `"Room 2, 1 Heron Rise"` would both resolve GREEN to the same house UPRN.

**(c) Partial OS score but confirmed format mismatch**
`os_match >= 0.7` and `_is_format_mismatch()` returns True → GREEN, confidence = max(os_match, 0.80).

`_is_format_mismatch` confirms it is the same property by requiring all of:
- Both addresses have flat indicators
- Postcodes agree
- Flat numbers agree
- Building numbers agree (when both present)
- Street-token overlap ≥ 0.5

---

### Step 3 — Implicit flat number

Applies when the input has **no** flat indicator but the OS record **is** a sub-unit (`PARENT_UPRN` set), there is no "Block / Tower / Wing" prefix in the input, and `os_match >= 0.7`.

If `input_bld_num == matched_flat_num` and street-token overlap ≥ 0.6 → GREEN, confidence = os_match, reason = `implicit_flat_number_matches`.

Example: `"117 Parker Court"` matching `"FLAT 117, PARKER COURT"` — the user omitted "Flat".

---

### Step 3b — Named-property sub-unit: word-split variant

Applies when the input has no flat indicator, the matched record is a sub-unit, the matched address has no flat indicator, and the matched address does not introduce a building number the input is missing.

Splits both addresses by comma into segments, normalises each segment (lowercase, punctuation stripped), and for every input segment finds the best-matching matched segment via `SequenceMatcher`. If ≥ 90% of input segments find a match with score ≥ 0.85 → GREEN, confidence = max(os_match, 0.75), reason = `segment_match_same_property`.

This handles property names written as one word or two, e.g. `"5 Red Mayes, Aston, Bampton, OX18 2DF"` → `"5 REDMAYES, HAM LANE, ASTON, BAMPTON, OX18 2DF"` where `"Red Mayes"` and `"REDMAYES"` score ~0.95 within their respective comma segments.

Guards:
- `not matched_addr_has_flat` — if the matched address has an explicit flat indicator, the AMBER logic in Step 4 is the right handler
- `not (matched_bld_num and not input_bld_num)` — if the matched address introduces a building number the input is missing, do not promote to GREEN

---

### Step 4 — AMBER / RED: input is a building, OS matched a flat

Applies when the input has no flat indicator but the matched record is a sub-unit (Steps 3 and 3b did not fire).

Looks up the `PARENT_UPRN` via the OS API and runs `compare_addresses` against the input:

| Parent lookup result | Level | Confidence | Reason |
|---|---|---|---|
| Parent resolves and address similarity ≥ 0.6 | AMBER | 0.50 | `parent_uprn_resolves_to_building` |
| No `PARENT_UPRN` on the record | RED | min(os_match, 0.30) | `missing_flat_no_parent_uprn` |
| Parent lookup fails or similarity < 0.6 | RED | min(os_match, 0.30) | `missing_flat_parent_mismatch` |

AMBER means: the building was found correctly, but the specific unit cannot be confirmed because no flat designator was in the input.

---

### Step 5 — RED: structural mismatches

Evaluated in order; first match exits.

| Condition | Reason | Confidence |
|---|---|---|
| Postcodes both present and differ | `postcode_mismatch` | min(os_match, 0.30) |
| `addr_similarity < 0.4` | `low_address_similarity` | min(os_match, 0.30) |
| `os_match >= 0.8` AND `addr_similarity < 0.5` | `high_os_score_low_similarity` | min(os_match, 0.30) |
| `os_match < 0.7` | `low_os_match` | min(os_match, 0.30) |

---

### Step 6 — Fallback GREEN

Requires `structural_alignment` AND `addr_similarity >= 0.5`.

Computes street-token overlap: tokens remaining after removing the postcode, flat designators, floor-flat codes, and pure numbers from each address. Overlap = shared tokens / max(token count of either side).

If overlap ≥ 0.6 AND the matched address does not introduce a building number the input is missing → GREEN, confidence = os_match, reason = `moderate_match_aligned`.

The building-number guard is needed here because `_extract_street_tokens` strips pure digit tokens, so a number added by OS (e.g. the `"1"` in `"1, BEECH GROVE"`) disappears from the token comparison and would otherwise allow a numberless input to score full overlap.

---

### Step 7 — Catch-all RED

If no earlier step returned a result:
**RED**, confidence = min(os_match, 0.30), reason = `uncertain_match`.

---

## Confidence values by outcome

| Level | Condition | Confidence |
|---|---|---|
| GREEN | Exact match | max(os_match, 0.95) |
| GREEN | Format mismatch confirmed | max(os_match, 0.80) |
| GREEN | Segment match (word-split property name) | max(os_match, 0.75) |
| GREEN | All other GREEN paths | os_match (0.70–1.0) |
| AMBER | Parent UPRN resolves to building | 0.50 fixed |
| RED | All RED paths | min(os_match, 0.30) |

---

## Reason codes

| Code | Step | Meaning |
|---|---|---|
| `building_number_mismatch` | 1 | House / building numbers differ |
| `flat_number_mismatch` | 1 | Flat numbers differ |
| `exact_match` | 2a | OS score is 1.0 |
| `good_match_aligned` | 2b | OS ≥ 0.8, high similarity, same flat structure, no introduced building number |
| `good_match_input_has_extra_descriptors` | 2b2 | OS ≥ 0.8, structural alignment, matched tokens are a subset of input tokens |
| `format_mismatch_same_property` | 2c | Different flat notation, all anchors agree |
| `implicit_flat_number_matches` | 3 | Input building number equals matched flat number |
| `segment_match_same_property` | 3b | ≥ 90% of comma-separated input segments align with matched segments; handles property names written as one word or two |
| `parent_uprn_resolves_to_building` | 4 | No flat in input; parent UPRN confirmed the building |
| `missing_flat_no_parent_uprn` | 4 | No flat in input; OS record has no parent UPRN |
| `missing_flat_parent_mismatch` | 4 | No flat in input; parent address does not match input |
| `postcode_mismatch` | 5 | Postcodes differ |
| `low_address_similarity` | 5 | Normalised address similarity below 0.4 |
| `high_os_score_low_similarity` | 5 | OS ≥ 0.8 but our similarity < 0.5 |
| `low_os_match` | 5 | OS score below 0.7 |
| `moderate_match_aligned` | 6 | OS 0.7–0.8, aligned structure, street tokens overlap, no introduced building number |
| `uncertain_match` | 7 | No earlier rule fired; cautious fallback |

---

## Known limitation

A plain street address with a **typo in the street name** (e.g. `"6 Albert Streetm"` → `"6, ALBERT STREET"`) or an **extra locality token** (e.g. `"Riverside"` present in input but absent from the OS canonical form) can cause the Step 6 street-token overlap to fall below the 0.6 threshold and reach `uncertain_match` RED, even when the postcode and building number agree. The Step 3b segment check handles this for records stored as OS sub-units, but not for standalone house records where `matched_subunit` is False.
