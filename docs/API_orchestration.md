# API Orchestration — Property Data Enrichment

## Overview

The `backend/geo/uprn maps/` module resolves free-text addresses or raw UPRNs into fully enriched property records by orchestrating four external APIs in sequence. The entry point is `address_to_final.py`; all other modules are called by it.

The central concept is **resolve once, share everywhere**: OS Places is called first to get BNG coordinates, and those coordinates are passed directly to NGD and Listed Building lookups so no downstream call needs to re-resolve the UPRN.

---

## APIs Used

| API | Module | Auth | Coverage |
|---|---|---|---|
| OS Places (free-text search / UPRN lookup) | `os_datahub_functions.py` | API key | GB |
| OS NGD Buildings (`bld-fts-building-4`) | `uprn_to_height.py` | API key (separate NGD key) | GB |
| Open Data Communities EPC | `uprn_to_epc.py` | Basic auth (email + key) | England & Wales only |
| planning.data.gov.uk / Historic Environment Scotland WFS | `uprn_to_listed.py` | None (open) | England + Scotland |

---

## Enrichment Pipeline

### Single-property path (`get_final_info_from_address`)

```
Free-text address
      │
      ▼
 OS Places (find)
 → UPRN, BNG coordinates (X/Y), canonical address, MATCH score
      │
      ├──────────────────────────────────────────────┐
      │                                              │
      ▼                                              ▼
 EPC API (by UPRN)                          NGD Buildings (by BNG bbox)
 → energy rating, property type,            → height, floor count, footprint
   wall/roof/age, floor area, fuel,           area, wall/roof material, age band
   running costs, lodgement date              (30m × 30m bbox, nearest centroid)
      │                                              │
      └──────────────────────┬───────────────────────┘
                             │
                             ▼
                    Listed Building check (by BNG)
                    → England: planning.data.gov.uk
                    → Scotland: HES WFS
                    → grade, name, list reference
                             │
                             ▼
                    Merge (EPC preferred for construction fields)
                    → single result dict
```

### UPRN path (`get_final_info_from_uprn`)

Same pipeline but the first call is `get_coordinates_from_uprn` (OS Places UPRN endpoint) instead of the free-text search. No MATCH score is generated.

---

## Batch Optimisation

The batch orchestrators (`get_final_info_from_addresses` / `get_final_info_from_uprns`) cut redundant API calls significantly.

**Without batching:** each of 4 lookups would call OS Places independently → ~4N OS API calls for N properties.

**With batching:** OS Places is called once per property to resolve coordinates. Those coordinates are passed directly into the downstream batch calls. NGD, EPC, and Listed all use `requests.Session` to reuse the underlying TCP/SSL connection across calls.

```
N addresses → 1 batch OS Places call (N requests, 1 session)
           → 1 batch EPC call        (N requests, 1 session)
           → 1 batch NGD call        (N requests, 1 session)
           → 1 batch Listed call     (N lookups, pre-resolved coordinates)
```

---

## Module Responsibilities

### `os_datahub_functions.py` — Address ↔ UPRN resolution

| Function | Input | Output |
|---|---|---|
| `get_uprn_from_address` | free-text address | DPA/LPI record (UPRN, coordinates, MATCH score) |
| `get_uprns_from_addresses` | list of addresses | list of DPA/LPI records (batch, shared session) |
| `get_coordinates_from_uprn` | UPRN | DPA/LPI record (address, BNG coordinates) |
| `get_coordinates_from_uprns` | list of UPRNs | dict of UPRN → DPA/LPI records (batch, shared session) |

The DPA/LPI record contains: `UPRN`, `PARENT_UPRN`, `ADDRESS`, `POSTCODE`, `X_COORDINATE`, `Y_COORDINATE`, `COUNTRY_CODE`, `CLASSIFICATION_CODE`, `MATCH`, `MATCH_DESCRIPTION`.

`PARENT_UPRN` is used by `block_detection.py` to group flats into their parent building. `COUNTRY_CODE` drives the Scotland vs England branching in the listed building and cross-reference modules.

---

### `uprn_to_epc.py` — Energy Performance Certificates

Queries the Open Data Communities domestic EPC API by exact UPRN. Returns up to 100 certificates ordered most-recent-first. **England and Wales only** — no Scottish EPC data.

Key fields consumed by the merger:

| EPC field | Maps to output field |
|---|---|
| `current-energy-rating` | `epc_rating` |
| `potential-energy-rating` | `epc_potential_rating` |
| `property-type` | `property_type` (preferred over NGD) |
| `built-form` | `built_form` |
| `walls-description` | `wall_construction` (preferred over NGD) |
| `roof-description` | `roof_construction` (preferred over NGD) |
| `construction-age-band` | `age_band` (preferred over NGD) |
| `total-floor-area` | `total_floor_area_m2` |
| `main-fuel` | `main_fuel` |
| `lighting/heating/hot-water-cost-current` | running cost fields |
| `lodgement-datetime` | `epc_lodgement_date` |

EPC data is cross-validated against the OS Places address using `address_confidence.compare_addresses()` (sequence similarity + token overlap, threshold 0.6).

---

### `uprn_to_height.py` — Building physical data (NGD)

Two-step lookup: UPRN → BNG coordinates → NGD Buildings API (`bld-fts-building-4` collection). Creates a 30m × 30m bounding box around the UPRN point and returns the building whose polygon centroid is closest to that point. Handles both `Polygon` and `MultiPolygon` geometries.

Key fields consumed by the merger:

| NGD field | Maps to output field |
|---|---|
| `height_relativemax_m` | `height_relativemax_m` |
| `height_relativeroofbase_m` | `height_relativeroofbase_m` (eaves height) |
| `height_absolutemax/min_m` | absolute heights above sea level |
| `height_confidencelevel` | `height_confidencelevel` (Moderate/Good/Suspect) |
| `numberoffloors` | `numberoffloors` |
| `geometry_area_m2` | `geometry_area_m2` (footprint) |
| `constructionmaterial` | `wall_construction` (fallback if no EPC) |
| `roofmaterial_primarymaterial` | `roof_construction` (fallback if no EPC) |
| `buildingage_period` | `age_band` (fallback if no EPC) |
| `buildingage_year` | `year_of_build` |
| `basementpresence` | `basement` |

---

### `uprn_to_listed.py` — Listed building status

Spatial lookup using pre-resolved BNG coordinates. Country is determined from `COUNTRY_CODE` in the OS Places record.

| Country | API | Method |
|---|---|---|
| England | planning.data.gov.uk | WGS84 polygon intersect (~50m buffer) |
| Scotland | Historic Environment Scotland WFS | BNG bbox (5m buffer) |

Returns `is_listed` (True/False/None), `grade`, `name`, `reference`, and `source`. The batch variant accepts pre-resolved `(uprn, place_record)` tuples directly, avoiding a second OS Places call.

Grade conventions differ by country:
- England: I, II*, II
- Scotland: A, B, C

---

### `address_confidence.py` — Address cross-validation

Standalone utility used internally to validate that downstream API responses (EPC, parent UPRN) refer to the same property as the OS Places result. Scores two addresses using `SequenceMatcher` ratio and token overlap, returning the higher of the two.

| Score | Confidence |
|---|---|
| ≥ 0.8 | HIGH |
| ≥ 0.5 | MEDIUM |
| < 0.5 | LOW |

Used by `cross_reference.py` when verifying parent UPRNs (threshold 0.6) and by `uprn_to_epc.py` for EPC address cross-validation.

---

### `block_detection.py` — Block grouping

Post-lookup step that groups a list of OS Places records into blocks by their `PARENT_UPRN`. Resolves nested hierarchies (flat → block → estate) up to 5 levels deep using batch UPRN lookups. Standalone records (no `PARENT_UPRN`, not referenced by others) are returned separately.

A post-grouping address-substring check catches the DPA/LPI mismatch case where a building's own UPRN differs from the `PARENT_UPRN` its flats reference.

---

## Field Merge Priority

When both EPC and NGD return the same conceptual field, EPC is used if available. NGD is the fallback for properties without an EPC (Scotland, new-build, commercial).

| Field | EPC | NGD | Winner |
|---|---|---|---|
| Property type | `property-type` | `description` | EPC if present |
| Wall construction | `walls-description` | `constructionmaterial` | EPC if present |
| Roof construction | `roof-description` | `roofmaterial_primarymaterial` | EPC if present |
| Age band | `construction-age-band` | `buildingage_period` | EPC if present |
| Height / floors | — | direct | NGD only |
| EPC ratings | direct | — | EPC only |
| Listed status | — | — | Listed API only |

`construction_data_source` in the output is set to `"EPC"` or `"NGD"` to indicate which source was used.

---

## Output Fields (full property result)

| Field | Source |
|---|---|
| `uprn`, `address`, `postcode` | OS Places |
| `x_coordinate`, `y_coordinate` | OS Places (BNG EPSG:27700) |
| `country_code`, `parent_uprn` | OS Places |
| `classification_code`, `classification_description` | OS Places |
| `match_score`, `match_description` | OS Places (address search only) |
| `height_relativemax_m`, `height_relativeroofbase_m` | NGD |
| `height_absolutemax_m`, `height_absolutemin_m`, `height_absoluteroofbase_m` | NGD |
| `height_confidencelevel`, `numberoffloors`, `geometry_area_m2` | NGD |
| `property_type`, `built_form` | EPC → NGD |
| `wall_construction`, `roof_construction`, `age_band` | EPC → NGD |
| `year_of_build`, `basement` | NGD |
| `construction_data_source` | derived (`"EPC"` or `"NGD"`) |
| `epc_rating`, `epc_potential_rating` | EPC |
| `total_floor_area_m2`, `main_fuel`, `extension_count` | EPC |
| `lighting_cost_current`, `heating_cost_current`, `hot_water_cost_current` | EPC |
| `epc_lodgement_date` | EPC |
| `is_listed`, `listed_grade`, `listed_name`, `listed_reference` | Listed API |
| `osid` | NGD |
