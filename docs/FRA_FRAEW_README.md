# FRA & FRAEW — Fire Risk Processing

## What We Are Doing

EquiRisk ingests Fire Risk Assessment (FRA) and Fire Risk Appraisal of External Walls (FRAEW) PDF documents for UK social housing blocks. Using AWS Bedrock (Claude AI), we automatically extract structured risk data from these documents and surface it to insurance underwriters — replacing a manual process that currently takes days per portfolio.

No other platform in the UK social housing insurance market does this automatically.

---

## What We Are Trying to Achieve

### For Underwriters
- Instantly know which blocks are **RED** (high risk) across an entire portfolio
- See exactly how many remediation actions are outstanding, overdue, or have no due date
- Identify unchecked liabilities — actions with **no stipulated completion date**
- Get a combined FRA + FRAEW risk signal per block (worst-case wins)

### For Housing Associations
- Demonstrate compliance with Building Safety Act 2022
- Track remediation progress across their estate
- Know which blocks are approaching FRA review expiry

### Business Goal
Fire risk intelligence is our **USP**. We will eventually assign financial liability values to outstanding actions and integrate with HA asset management systems (Ask Quinn) to verify whether remediation has actually been carried out.

---

## Document Types

### FRA — Fire Risk Assessment
- Covers **internal** fire safety
- Regulatory basis: FSO 2005, Fire Safety Act 2021, Building Safety Act 2022
- Produced by qualified fire risk assessors
- Renewed annually or every 2–5 years

### FRAEW — Fire Risk Appraisal of External Walls
- Covers **external** wall construction and cladding
- Methodology: PAS 9980:2022
- Produced by fire engineers
- Triggered by EWS1 form requirements and BSA 2022

---

## What We Extract

### FRA Fields (43 total)

#### Identity & Dates
| Field | Description |
|-------|-------------|
| `risk_rating` | Exact phrase from document (e.g. "Substantial", "Moderate") |
| `rag_status` | Normalised RED / AMBER / GREEN |
| `fra_assessment_type` | Type 1 / 2 / 3 / 4 (if stated) |
| `assessment_date` | Date assessment was carried out |
| `assessment_valid_until` | Explicit expiry date (null if not stated) |
| `next_review_date` | Recommended review date |
| `assessor_name` | Full name of assessor |
| `assessor_company` | Assessor organisation |
| `assessor_qualification` | Qualifications (IFE, IFSM, etc.) |
| `responsible_person` | RP under FSO 2005 |

#### Building Info
| Field | Description |
|-------|-------------|
| `building_name` | Building name or address |
| `num_storeys` | Number of floors |
| `num_units` | Number of residential units |
| `build_year` | Year of construction |
| `evacuation_strategy` | stay_put / simultaneous / phased / temporary_evacuation |
| `evacuation_strategy_changed` | Whether strategy has changed since last assessment |

#### Fire Systems (true / false / null)
| Field |
|-------|
| `has_sprinkler_system` |
| `has_smoke_detection` |
| `has_fire_alarm_system` |
| `has_fire_doors` |
| `has_compartmentation` |
| `has_emergency_lighting` |
| `has_fire_extinguishers` |
| `has_firefighting_shaft` |
| `has_dry_riser` |
| `has_wet_riser` |

#### Compliance Flags
| Field | Description |
|-------|-------------|
| `bsa_2022_applicable` | Building Safety Act 2022 applies |
| `accountable_person_noted` | Accountable person identified |
| `mandatory_occurrence_noted` | Fire incident formally recorded |
| `has_accessibility_needs_noted` | Vulnerable residents identified |

#### Action Items (JSONB array — every remediation action)
Each item contains:
```
issue_ref     → reference number from document
description   → full action text verbatim
hazard_type   → Housekeeping / Means of Escape / Fire Spread / Detection /
                Signage / Emergency Plans / Fire Service Facilities / Structural / Other
priority      → high / medium / low / advisory
due_date      → YYYY-MM-DD or null (null = unchecked liability)
status        → outstanding / completed / overdue
responsible   → named team, role, or person
```

#### Action Counts (stored separately for fast querying)
| Field | Description |
|-------|-------------|
| `total_action_count` | All actions found |
| `high_priority_action_count` | High priority only |
| `outstanding_action_count` | Not yet completed |
| `overdue_action_count` | Past due date and not done ⚠️ *bug: currently returns 0* |
| `no_date_action_count` | Actions with **no due date** — unchecked liability |

#### Significant Findings (JSONB array)
Major safety concerns noted by the assessor not already captured as action items (e.g. structural deficiencies, lack of compartmentation).

---

### FRAEW Fields (50 total)

#### Identity & Dates
| Field | Description |
|-------|-------------|
| `building_risk_rating` | Exact phrase (e.g. "Not Acceptable", "Broadly Acceptable") |
| `rag_status` | Normalised RED / AMBER / GREEN |
| `assessment_date` | Site investigation date |
| `report_date` | Date report was issued |
| `assessment_valid_until` | Typically 5 years from report date |
| `assessor_name / company / qualification` | Report writer details |
| `fire_engineer_name / company` | Fire engineer (Clause 14) |
| `clause_14_applied` | Whether independent fire engineer reviewed |

#### Building Info
| Field | Description |
|-------|-------------|
| `building_height_m` | Height in metres |
| `building_height_category` | under_11m / 11_to_18m / 18_to_30m / over_30m |
| `num_storeys` | Number of storeys |
| `construction_frame_type` | e.g. structural concrete, steel frame |
| `external_wall_base_construction` | e.g. double masonry cavity wall |
| `retrofit_year` | Year cladding/insulation was added |

#### Cladding & Insulation Flags
| Field |
|-------|
| `has_combustible_cladding` |
| `aluminium_composite_cladding` |
| `hpl_cladding_present` |
| `timber_cladding_present` |
| `eps_insulation_present` |
| `mineral_wool_insulation_present` |
| `pir_insulation_present` |
| `phenolic_insulation_present` |

#### Structural Safety
| Field |
|-------|
| `cavity_barriers_present` |
| `cavity_barriers_windows` |
| `cavity_barriers_floors` |
| `fire_breaks_floor_level` |
| `fire_breaks_party_walls` |

#### Compliance
| Field | Description |
|-------|-------------|
| `bs8414_test_evidence` | BS 8414 large-scale fire test evidence |
| `br135_criteria_met` | BRE 135 criteria satisfied |
| `adb_compliant` | compliant / non_compliant / uncertain / not_applicable |
| `pas_9980_compliant` | PAS 9980:2022 compliance |

#### Remediation
| Field | Description |
|-------|-------------|
| `has_remedial_actions` | Boolean flag — quick filter |
| `remedial_actions` | JSONB array (action, priority, due_date, responsible, status) |
| `interim_measures_required` | Waking watch or interim safety measures active |
| `interim_measures_detail` | Description of interim measures |

#### Wall Types (JSONB array — one per zone assessed)
Each wall type contains material type, combustibility flags, PAS 9980 Step 5 risk scores (spread / entry / occupant / overall), and remedial requirements.

---

## RAG Colour Coding

### FRA RAG Mapping
| RAG | Trigger Phrases |
|-----|----------------|
| **RED** | High, Very High, Intolerable, Substantial, Extreme, Critical, Serious, Unacceptable, Priority 1, Grade D, Grade E |
| **AMBER** | Medium, Moderate, Significant, Tolerable with conditions, Further Action Required, Priority 2, Grade C |
| **GREEN** | Low, Trivial, Negligible, Acceptable, Broadly Acceptable, Tolerable, No Further Action, Priority 3, Grade A, Grade B |

Numeric matrix: ≥15 → RED | 8–14 → AMBER | ≤7 → GREEN

### FRAEW RAG Mapping
| RAG | Trigger Phrases |
|-----|----------------|
| **RED** | High, Intolerable, Not Acceptable, Category B2, Category C, Extreme, Unacceptable |
| **AMBER** | Medium, Tolerable (with conditions), Further Action Required, Further Assessment Required, Category B1 |
| **GREEN** | Low, Broadly Acceptable, Tolerable, No Further Action, Category A |

### Combined Block Colour (Map + Dashboard)
Takes the **worst of FRA and FRAEW** for each block:
```
FRA=RED  OR  FRAEW=RED              →  block colour = RED
FRA=AMBER OR FRAEW=AMBER (no RED)   →  block colour = AMBER
FRA=GREEN AND FRAEW=GREEN           →  block colour = GREEN
Neither assessed                    →  block colour = grey
```

### Where RAG Is Used
- **Portfolio map** — coloured markers per block
- **FRA blocks table** — ordered RED → AMBER → GREEN → unassessed, then by height
- **FRAEW blocks table** — same ordering
- **Doc B Excel export** — risk columns per block
- **Dashboard KPI cards** — RED/AMBER/GREEN counts across portfolio

---

## Remediation — What We Capture

### Priority Inference (when not explicit in document)
```
Immediate / within 1 month  →  high
3–6 months                  →  medium
12 months                   →  low
No date given               →  advisory
```

### Status Assignment
```
Completed / closed / done   →  completed
Past due date, not done     →  overdue
Otherwise                   →  outstanding
```

### The Unchecked Liability Problem
`no_date_action_count` counts actions where the document gives **no due date**. These are the highest risk from an insurance liability perspective — there is no contractual obligation for the HA to complete them by any specific date, meaning the hazard can persist indefinitely.

---

## What Is Needed for MVP

### Must Fix
- [ ] **`overdue_action_count` always returns 0** — the count is not computing from the JSONB `action_items` array correctly. Fix: recalculate at write time by iterating action_items and counting where `due_date < today AND status != 'completed'`
- [ ] **FRA/FRAEW upload UI** — currently no frontend; PDFs must be uploaded via raw API call. Need: document type selector (FRA / FRAEW), block picker dropdown, PDF file input

### Must Build
- [ ] **Per-block action item drill-down** — endpoint to return all action items for a specific block (`GET /fra-blocks/{block_id}/actions`) so an underwriter can see the full list of what needs fixing
- [ ] **RED block summary report** — one endpoint that returns all RED-rated blocks across the portfolio with their action counts, overdue counts, and no-date counts in a single response
- [ ] **`assessment_valid_until` fallback** — some FRA templates use "Next FRA Due" / "Suggested Review Date" which maps to `next_review_date` not `assessment_valid_until`. When `assessment_valid_until` is null, populate it from `next_review_date`

### Nice to Have for MVP
- [ ] Filter FRA blocks by `has_no_date_actions=true` (unchecked liability view)
- [ ] Filter FRAEW blocks by `interim_measures_required=true` (waking watch active)
- [ ] `is_in_date` flag surfaced prominently (FRA expired = unacceptable liability)

---

## Future Roadmap

### Ask Quinn / AMS Integration (Post-Funding)
Connect to Housing Association Asset Management Systems. When an FRA/FRAEW stipulates a remediation due date, Ask Quinn checks the AMS to verify whether the work was actually completed within the stipulated timeframe. Unverified actions get flagged as confirmed unchecked liabilities.

### Liability Quantification
Assign a financial liability value to each outstanding action item based on:
- Hazard type (Structural/Cladding > Means of Escape > Detection > Housekeeping)
- Priority and overdue duration
- Block TIV (Total Insured Value)
- Benchmarked remediation cost estimates (BCIS / Rider Levett Bucknall data)

### Sector Intelligence
- Cross-portfolio RED rating benchmarking (anonymised)
- Assessor quality scoring
- Risk trend analysis across assessment cycles

---

## Database Tables

| Table | Description |
|-------|-------------|
| `silver.fra_features` | 43 columns, one row per uploaded FRA |
| `silver.fraew_features` | 50 columns, one row per uploaded FRAEW |
| `silver.blocks` | One row per block, linked to FRA/FRAEW via `block_id` |
| `silver.document_features` | Upload audit record for every processed document |

FRA/FRAEW are linked to blocks via `block_id` (UUID). The LATERAL JOIN pattern picks the **most recent** assessment per block when multiple FRAs exist for the same block.

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/upload/ingest?document_type=fra` | Upload and process FRA PDF |
| `POST /api/v1/upload/ingest?document_type=fraew` | Upload and process FRAEW PDF |
| `GET /api/v1/underwriter/portfolios/{id}/fra-blocks` | FRA status per block (filterable by RAG) |
| `GET /api/v1/underwriter/portfolios/{id}/fraew-blocks` | FRAEW status per block |
| `GET /api/v1/underwriter/portfolios/{id}/map` | Block map markers with combined RAG colour |
| `GET /api/v1/portfolios/{id}/export/doc-b` | Download Doc B Excel (64 cols inc FRA/FRAEW) |
