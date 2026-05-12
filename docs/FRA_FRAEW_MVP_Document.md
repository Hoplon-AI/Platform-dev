# EquiRisk — Fire Risk Intelligence
## FRA & FRAEW: What We Do, What We Extract, What's Next

**Audience:** Ewan McFarlane — Founder
**Date:** April 2026
**Purpose:** Plain-English summary of current MVP capability, live extraction example, and remaining build items

---

## 1. The Problem We Are Solving

When an insurance underwriter receives a portfolio submission from a Housing Association, they receive a folder of PDFs — Fire Risk Assessments (FRAs) and Fire Risk Appraisals of External Walls (FRAEWs). Reading and summarising these manually takes **days per portfolio**.

EquiRisk reads these documents automatically using AI (AWS Bedrock — Claude Sonnet) and extracts every piece of information that matters to an underwriter in **seconds**.

No other platform in UK social housing insurance does this.

---

## 2. Two Document Types — What They Cover

| | FRA | FRAEW |
|---|---|---|
| **Full name** | Fire Risk Assessment | Fire Risk Appraisal of External Walls |
| **Covers** | Internal fire safety of the building | External wall construction and cladding |
| **Regulation** | FSO 2005, Fire Safety Act 2021, BSA 2022 | PAS 9980:2022 |
| **Produced by** | Qualified fire risk assessors | Fire engineers |
| **Renewed** | Annually or every 2–5 years | Every 5 years |
| **Key output** | Risk rating + action plan | Cladding risk + wall type assessment |

---

## 3. The Traffic Light System (RAG)

Every FRA and FRAEW gets a single colour:

| Colour | Meaning | Example Phrases in Document |
|---|---|---|
| 🔴 **RED** | High risk — immediate action required | "High", "Intolerable", "Substantial", "Not Acceptable" |
| 🟡 **AMBER** | Medium risk — action needed | "Moderate", "Tolerable with conditions", "Further Action Required" |
| 🟢 **GREEN** | Low risk — acceptable | "Low", "Broadly Acceptable", "Tolerable", "No Further Action" |

**Combined Block Colour Rule:**
Each block on the portfolio map gets one colour — the **worst** of its FRA and FRAEW:
- FRA = RED or FRAEW = RED → block is **RED**
- FRA = AMBER or FRAEW = AMBER (no RED) → block is **AMBER**
- Both GREEN → block is **GREEN**
- Neither assessed → block is **grey**

---

## 4. FRA — What We Extract (43 Fields)

### 4.1 Identity and Dates

| Field | What It Means | Live Example |
|---|---|---|
| `risk_rating` | Exact phrase from the document | `"Moderate"` |
| `rag_status` | Our computed RED / AMBER / GREEN | `"AMBER"` |
| `fra_assessment_type` | Type 1 / 2 / 3 / 4 (invasiveness level) | `"Type 1"` |
| `assessment_date` | Date the assessment was carried out | `"2024-06-18"` |
| `assessment_valid_until` | Explicit expiry date if stated | `null` (not stated in this doc) |
| `next_review_date` | Recommended next review date | `"2025-06-18"` |
| `assessor_name` | Name of the fire assessor | `"K. Henderson"` |
| `assessor_qualification` | Professional qualifications | `"BSc (Hons), MIFireE, CFPA Dip"` |
| `assessor_company` | Assessor's company | `null` (not stated in this doc) |
| `responsible_person` | Who is legally responsible (FSO 2005) | `"Cathcart & District Housing Association"` |

### 4.2 Building Information

| Field | What It Means | Live Example |
|---|---|---|
| `building_name` | Building name or address | `"269 Holmlea Road"` |
| `building_address` | Full postal address | `"269 Holmlea Road, Cathcart, Glasgow G44 4BU"` |
| `num_storeys` | Number of floors | `4` |
| `num_units` | Number of flats | `10` |
| `build_year` | Year built | `1965` |
| `evacuation_strategy` | How residents should evacuate | `"stay_put"` |
| `evacuation_strategy_changed` | Has the strategy changed? | `false` |

**Evacuation Strategy — what each value means:**
- `stay_put` — residents stay in their flat unless directly affected (most common for older blocks)
- `simultaneous` — everyone evacuates immediately on alarm
- `phased` — floor by floor evacuation
- `temporary_evacuation` — waking watch / interim measure while remediation is underway

### 4.3 Fire Safety Systems

For each system we record whether it **exists** (true), **does not exist** (false), or **was not mentioned** (null):

| System | Live Example |
|---|---|
| Sprinkler system | `false` — not installed |
| Smoke detection | `true` — present |
| Fire alarm system | `true` — present |
| Fire doors | `true` — present (though some deficient) |
| Compartmentation | `true` — present |
| Emergency lighting | `true` — present (though 3 units faulty) |
| Fire extinguishers | `true` — present |
| Firefighting shaft | `false` — not installed |
| Dry riser | `false` — not installed |
| Wet riser | `false` — not installed |

### 4.4 Compliance Flags

| Field | What It Means | Live Example |
|---|---|---|
| `bsa_2022_applicable` | Does Building Safety Act 2022 apply? | `false` (block under 18m) |
| `accountable_person_noted` | Is the Accountable Person identified? | `false` |
| `mandatory_occurrence_noted` | Has a fire incident been formally recorded? | `false` |

---

## 5. Remediation Actions — The Core of What Ewan Asked For

This is the most commercially important part. Every FRA contains an **action plan** — a list of things that must be fixed.

We extract **every single action** from the document, regardless of format (numbered cards, tables, narrative paragraphs).

### 5.1 What We Capture Per Action

| Field | What It Means |
|---|---|
| `issue_ref` | The reference number given in the document |
| `description` | The full action text, word for word |
| `hazard_type` | Category of risk |
| `priority` | How urgent it is |
| `due_date` | The date by which it must be done |
| `status` | outstanding / completed / overdue |
| `responsible` | Who must carry out the work |

**Hazard Types:**
Housekeeping · Means of Escape · Fire Spread · Detection · Signage · Emergency Plans · Fire Service Facilities · Structural · Other

**Priority:**
- `high` — immediate / within 1 month
- `medium` — 3–6 months
- `low` — within 12 months
- `advisory` — no timescale given

### 5.2 Live Example — 5 Actions from 02BR Holmlea Road

---

**Action 1 — CDHA-HR-2024-001**
Category: Housekeeping | Priority: Medium | Due: 18 Sep 2024 | Status: **Overdue**
*"Clear storage items from ground floor common area adjacent to bin store. Advise residents of waste disposal policy and enforce no-storage policy in common areas."*
Responsible: Estate Management Team — Tenancy Services

---

**Action 2 — CDHA-HR-2024-002**
Category: Means of Escape | Priority: Medium | Due: 18 Sep 2024 | Status: **Overdue**
*"Test all emergency lighting units on stairway and replace faulty units. Ensure all emergency lighting provides minimum 1 hour duration along escape routes."*
Responsible: Property Services — Electrical Team

---

**Action 3 — CDHA-HR-2024-003**
Category: Means of Escape | Priority: Medium | Due: 18 Dec 2024 | Status: **Overdue**
*"Install self-closing devices (overhead door closers) on all 10 flat front entrance doors. Ensure doors close fully into frames with intumescent strips and cold smoke seals."*
Responsible: Property Services — Joinery Team

---

**Action 4 — CDHA-HR-2024-004**
Category: Fire Spread | Priority: Medium | Due: 18 Sep 2024 | Status: **Overdue**
*"Repair/adjust communal fire door at 2nd floor landing — door not closing fully into frame. Check and replace damaged intumescent strips where required."*
Responsible: Property Services — Joinery Team

---

**Action 5 — CDHA-HR-2024-005**
Category: Emergency Plans | Priority: Medium | Due: 18 Sep 2024 | Status: **Overdue**
*"Issue updated fire safety leaflet to all residents. Ensure fire action notices are displayed at each floor level and at main entrance."*
Responsible: Housing Services — Tenant Liaison

---

### 5.3 Action Count Summary (stored for fast querying)

| Count | Value | What It Means |
|---|---|---|
| `total_action_count` | 5 | 5 remediation actions found in this document |
| `high_priority_action_count` | 0 | No immediate/urgent actions |
| `outstanding_action_count` | 5 | 5 actions not yet completed |
| `overdue_action_count` | **5** | All 5 have passed their due date (fixed — was always 0 before) |
| `no_date_action_count` | 0 | All actions have a due date — no unchecked liabilities |

> **The Unchecked Liability:** `no_date_action_count` is the most important insurance metric. An action with no due date means the Housing Association has no contractual obligation to complete it by any specific date — the hazard can persist indefinitely. This is an unchecked liability on the underwriter's book.

---

## 6. FRAEW — What We Extract (50 Fields)

### 6.1 Identity and Dates

| Field | What It Means |
|---|---|
| `building_risk_rating` | Exact phrase from document conclusion |
| `rag_status` | RED / AMBER / GREEN |
| `assessment_date` | Date of site investigation |
| `report_date` | Date the report was issued |
| `assessment_valid_until` | Typically 5 years from report date |
| `assessor_name / company / qualification` | Report writer details |
| `fire_engineer_name / company` | Fire engineer (Clause 14 of PAS 9980) |
| `clause_14_applied` | Whether an independent fire engineer reviewed the report |

### 6.2 Building Height and Construction

| Field | What It Means |
|---|---|
| `building_height_m` | Height in metres |
| `building_height_category` | under_11m / 11_to_18m / 18_to_30m / over_30m |
| `num_storeys` | Number of storeys |
| `construction_frame_type` | e.g. structural concrete, steel frame |
| `external_wall_base_construction` | e.g. double masonry cavity wall |
| `retrofit_year` | Year cladding or insulation was added |

> **Why height matters:** The Building Safety Act 2022 applies to buildings over 18m. This triggers much higher regulatory obligations on the Housing Association and significantly higher risk for the underwriter.

### 6.3 Cladding and Insulation Flags

These are the post-Grenfell flags that underwriters care most about:

| Flag | What It Means |
|---|---|
| `has_combustible_cladding` | Any combustible material on external walls |
| `eps_insulation_present` | Expanded Polystyrene (EPS) — highly combustible |
| `pir_insulation_present` | Polyisocyanurate (PIR) — combustible |
| `phenolic_insulation_present` | Phenolic foam — combustible |
| `mineral_wool_insulation_present` | Mineral wool — non-combustible (safe) |
| `aluminium_composite_cladding` | ACM panels — Grenfell Tower material |
| `hpl_cladding_present` | High Pressure Laminate — combustible |
| `timber_cladding_present` | Timber — combustible |
| `acrylic_render_present` | Acrylic render — combustible |
| `cement_render_present` | Cement render — non-combustible (safe) |

### 6.4 Wall Types (per zone assessed)

A single building can have multiple different wall types — for example the main facade may be mineral wool render while the balconies are EPS. We extract each zone separately.

Per wall type we capture:
- Material description
- Insulation type and whether it is combustible
- Render type and whether it is combustible
- PAS 9980 Step 5 risk scores: spread risk / entry risk / occupant risk / overall risk
- Whether remedial works are required

### 6.5 Structural Safety

| Flag | What It Means |
|---|---|
| `cavity_barriers_present` | Fire barriers within wall cavities — critical for stopping fire spread |
| `cavity_barriers_windows` | Barriers around window openings |
| `cavity_barriers_floors` | Barriers at each floor level |
| `fire_breaks_floor_level` | Fire breaks at floor levels |
| `fire_breaks_party_walls` | Fire breaks at party walls |

### 6.6 Compliance

| Field | What It Means |
|---|---|
| `bs8414_test_evidence` | Evidence of large-scale fire test on wall system |
| `br135_criteria_met` | BRE 135 criteria satisfied |
| `adb_compliant` | compliant / non_compliant / uncertain / not_applicable |
| `pas_9980_compliant` | Compliant with PAS 9980:2022 methodology |

### 6.7 FRAEW Remedial Actions

| Field | What It Means |
|---|---|
| `has_remedial_actions` | Quick boolean flag — remediation required yes/no |
| `remedial_actions` | Full list of required works (action, priority, due date, responsible, status) |
| `interim_measures_required` | Is a waking watch or interim safety measure currently active? |
| `interim_measures_detail` | Description of the interim measure |

> **Interim measures** are the most urgent signal for an underwriter. If a waking watch is in place, the Housing Association is paying someone to patrol the building 24/7 because it is not safe to leave residents unattended. This is a significant ongoing liability.

---

## 7. Block Auto-Detection

When a PDF is uploaded, the system automatically identifies which block it belongs to — without the user having to manually select one.

It uses four strategies in order:

1. **Block reference code** — if the document contains an explicit code like "02BR", match directly to the block register
2. **Exact building name** — match "Elizabeth Court" directly to the block name
3. **Substring match** — match partial names (minimum 4 characters to avoid false matches)
4. **Address lookup** — match the street address in the PDF to a property in the portfolio, then find its block

---

## 8. What Is Working Right Now

| Feature | Status |
|---|---|
| Upload FRA PDF → AI extraction → store in database | ✅ Working |
| Upload FRAEW PDF → AI extraction → store in database | ✅ Working |
| RAG status (RED/AMBER/GREEN) per block | ✅ Working |
| Combined block colour (worst of FRA + FRAEW) | ✅ Working |
| All 43 FRA fields extracted and stored | ✅ Working |
| All 50 FRAEW fields extracted and stored | ✅ Working |
| Action items extracted verbatim with due dates | ✅ Working |
| Unchecked liability count (no_date_action_count) | ✅ Working |
| Overdue action count (past due date, not completed) | ✅ **Just fixed** |
| Block auto-detection from PDF content | ✅ Working |
| Doc B Excel export includes FRA/FRAEW data | ✅ Working |

---

## 9. What Is Still to Build for MVP

### Must Have Before Wildcard Final

| Item | What It Is | Why It Matters |
|---|---|---|
| FRA/FRAEW upload UI | A simple frontend: select document type, pick block, upload PDF | Currently requires a raw API call — cannot demo to investors |
| Per-block action drill-down endpoint | `GET /fra-blocks/{block_id}/actions` returns the full action list for one block | Ewan's requirement: "note what the red issues are" |
| RED block summary endpoint | One call returning all RED-rated blocks with their action counts | The core underwriter view — "show me everything I need to worry about" |
| `assessment_valid_until` fallback | When not stated in document, populate from `next_review_date` | 02BR example shows `assessment_valid_until = null` — should be `2025-06-18` |

### Post-Funding

| Item | What It Is |
|---|---|
| Ask Quinn / AMS integration | Verify whether remediation was actually carried out by the stipulated date |
| Liability quantification | Assign a financial value to each outstanding action based on hazard type, priority, block TIV, and remediation cost benchmarks |
| Assessor quality scoring | Track which assessors consistently find more/fewer issues |
| Cross-portfolio RED benchmarking | Anonymised comparison across all Housing Associations on the platform |

---

## 10. How It Looks in Practice — 02BR Holmlea Road Summary

If an underwriter queries block 02BR today, the system would return:

```
Block:          02BR — 269 Holmlea Road, Cathcart, Glasgow
FRA Status:     AMBER (Moderate)
Assessment:     18 June 2024 — K. Henderson (MIFireE)
Next Review:    18 June 2025 — OVERDUE FOR REVIEW

Actions:        5 total
                0 high priority
                5 outstanding
                5 overdue (all past due date — oldest overdue since Sep 2024)
                0 unchecked liabilities (all have due dates)

Key Issues:
  - No self-closing devices on any of 10 flat entrance doors
  - 3 of 8 emergency lighting units faulty on stairway
  - 2nd floor communal fire door not closing — warped frame
  - Waste and buggy stored in ground floor lobby (fire hazard)

Evacuation:     Stay Put
BSA 2022:       Not applicable (under 18m)
FRAEW:          Not yet assessed
```

This is the intelligence that currently takes an underwriter a full day to produce manually for one block. EquiRisk produces it in seconds, across an entire portfolio of 156 blocks simultaneously.

---

*Document prepared by Govind — EquiRisk Platform Team*
*Branch: fra-fraew-fixes | Last updated: April 2026*
