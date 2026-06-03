# OS Data Strategy — Address & Building Data Knowledge Base

> **Purpose.** This is the shared reference for how the platform sources, links, and enriches
> Ordnance Survey (OS) address and building data. It records *what we do today*, the
> *short-term workarounds* we have in place, the *intended future pathway*, and the *open
> questions* we are putting to OS. It is written so the whole team can stay appraised of this critical
> part of our offering.
>
> For the *implementation* detail of the live enrichment pipeline, see
> [API_orchestration.md](./API_orchestration.md) and [Flood_Risk.md](./Flood_Risk.md).
>
> **Status:** Living document. Last reviewed 2026-06-03.

---

## 1. TL;DR for the team

- OS is **retiring the AddressBase family (AddressBase, AddressBase Plus, Plus Islands) in Spring 2027** and replacing it with the **OS NGD (National Geographic Database)** data model. This is a *when*, not an *if* — our address/building sourcing has to move to NGD.
- The **single most important thing to understand**: in OS NGD the building layer is keyed on **`osid`** (a GUID), **not TOID**. The rich `Building` feature even carries a **direct UPRN cross-reference**. TOID still exists but is a *secondary, optional* identifier and only appears on the `Building Part` feature.
- **What we built today does not yet use either join.** Our live pipeline resolves a UPRN to coordinates and then does a **spatial (bounding-box, nearest-centroid) match** to the nearest NGD building. That is a reasonable interim approach but it is neither the TOID join nor the NGD-native UPRN→Building join.
- All the building attributes we want (height, floor count, roof material/shape, building use, connectivity) **do exist in NGD and are co-located on the single `Building` feature** — but they are reached via `osid`/UPRN, *not* via TOID.

---

## 2. The OS product landscape

### 2.1 Where things are heading

| Product | Status | Notes |
|---|---|---|
| AddressBase / AddressBase Plus / Plus Islands | **End of Life ~Spring 2027** | Access removed from OS Data Hub at EOL. |
| AddressBase Premium | Legacy premium address product | The lifecycle + cross-reference content we care about; the NGD Address Theme is its successor. |
| **OS NGD Address Theme** | Current / strategic | "Builds on AddressBase Premium" with up-to-daily currency; interoperable with other NGD themes via cross-reference + UPRN. |
| **OS NGD Buildings Theme** | Current / strategic | Building footprints + height, floors, roof, use, connectivity. |
| "OS GB Address" / NGD **GB Address Collection** | Current / strategic | The NGD collection that carries address data; has tiers — the exact tier that matches AddressBase Premium content needs confirming with OS. |

> **Terminology note.** "OS GB Address" is not a single SKU — it refers to the **GB Address
> Collection** within the NGD Address Theme, which comes in tiers. When talking to OS, always
> pin down *which tier* carries the full lifecycle + cross-reference content.

### 2.2 How NGD data is delivered

| Channel | Format | Use |
|---|---|---|
| **OS Select+Build** (download) | GeoPackage, CSV | Full dataset; **Change-Only Updates (COU)** available in CSV for full-GB coverage. |
| **OS NGD API – Features** | GeoJSON | Live, query-by-area / by-feature access. |
| **OS NGD API – Tiles** | Vector tiles | Map rendering. |

> **Open question (see §6):** whether the *premium* GB Address Collection is reachable via the
> **NGD API – Features**, or is **download-only via Select+Build**. The public docs are
> ambiguous and this materially changes our integration (live API calls vs. ingest-the-whole-
> dataset + apply COUs).

---

## 3. The address ↔ building linkage (the backbone)

This is the heart of the platform: we resolve an address/UPRN, then attach the building's
physical attributes. There are **three different ways to make that join**, and it is important
not to confuse them.

### 3.1 The legacy mental model (AddressBase Premium + OS MasterMap Topography)

- Address layer keyed on **UPRN**.
- Building (topography) layer keyed on **TOID**.
- A dedicated **cross-reference table** (100M+ entries in AddressBase Premium) links UPRN → TOID.
- In this world, "join UPRN-keyed addresses to TOID-keyed buildings" is the natural backbone.

### 3.2 What OS NGD actually does

In NGD the keying is different:

| Feature | Primary key | Carries TOID? | Carries the attributes we want? |
|---|---|---|---|
| **`Building`** (`bld-fts-building`) | **`osid`** (GUID) + **UPRN reference** | **No `toid` attribute** | **Yes** — floors, height, roof material/shape, building use, connectivity |
| **`Building Part`** (`bld-fts-buildingpart`) | `osid` + **`toid`** | **Yes** | **No** — height only; no floors / roof / use / connectivity |

**Implication:** the NGD-native join is **UPRN → `Building` (via the UPRN cross-reference),
keyed on `osid`**. A *TOID-keyed* join would land on `Building Part`, which carries TOID and
height but **not** the floor/roof/use/connectivity attributes our use cases depend on. So
making TOID "the backbone" would actively route us away from the data we need.

### 3.3 What our code does *today* (the short-term workaround)

The live pipeline (`backend/geo/uprn maps/`, see [API_orchestration.md](./API_orchestration.md)):

1. Resolve address/UPRN → BNG coordinates via **OS Places API**.
2. **Spatially match** to the nearest NGD building: a 30 m × 30 m bounding box around the point,
   then the building whose polygon centroid is closest (`uprn_to_height.py`).
3. Keep the building's **`osid`** in the output; **TOID is not used at all**.

This works and ships, but it is a *proximity heuristic*, not an authoritative link. In dense
terraces or blocks of flats it can select the wrong adjacent building, and it carries no
guarantee of being the building the UPRN actually belongs to.

### 3.4 Comparison

| Approach | Join key | Reaches floors/roof/use/connectivity? | Robustness | Status |
|---|---|---|---|---|
| Legacy TOID join | UPRN→TOID→topography | n/a (legacy topo, not NGD attrs) | High (authoritative xref) | Being retired with AddressBase |
| **NGD-native (target)** | **UPRN→`Building` (`osid`)** | **Yes** | High (authoritative xref) | **Intended future pathway** |
| TOID join *into NGD* | UPRN→TOID→`Building Part` | **No** (Building Part lacks them) | Misleading for our use case | ❌ Not recommended |
| **Spatial match (current)** | coordinates→nearest centroid | Yes (lands on `Building`) | Medium (proximity heuristic) | **Current workaround** |

---

## 4. Building attribute availability (NGD Buildings)

All attributes required for per-building 3D rendering and analytics exist in NGD, and (this is
the good news) they are **co-located on the single `Building` feature type** — they are *not*
scattered across separate themes.

| Attribute | NGD feature type | Notes |
|---|---|---|
| `numberoffloors` | **Building** | Occupiable floors at/above ground; excludes basements/plant rooms; integer 1–99. |
| Height — `height_relativemax_m` (+ absolute heights) | **Building** *and* **Building Part** | `relativeheightmaximum` was renamed `height_relativemax_m` from v2.0+. |
| `roofmaterial` (`roofmaterial_primarymaterial` + confidence) | **Building** | ~10 material values + confidence indicator. |
| `roofshape` (`roofshapeaspect_shape`) | **Building** | Flat / Pitched / Mixed / Unknown. |
| `buildinguse` | **Building** | Primary functional use (up to two values); residential vs commercial. |
| `connectivity` | **Building** | Standalone / Semi-Connected / End-Connected / Multi-connected, + count of connected buildings. |
| `osid` | Building & Building Part | Primary GUID identifier. |
| `toid` | **Building Part only** | Secondary, optional identifier (OSMM ancestry). |
| UPRN reference | **Building** (cross-table) | Links the building to the UPRN(s) located within it. |

Sources: OS NGD docs — [Building feature](https://docs.os.uk/osngd/data-structure/buildings/building-features/building),
[Building Part feature](https://docs.os.uk/osngd/data-structure/buildings/building-features/building-part),
[number of floors release](https://www.ordnancesurvey.co.uk/blog/number-of-floors-data-release),
[roof data release](https://www.ordnancesurvey.co.uk/news/new-roof-data-for-over-40-million-buildings).

---

## 5. Address lifecycle & cross-reference content (NGD Address)

The lifecycle and cross-reference content we rely on from AddressBase Premium appears to be
**retained in NGD Address**, though the specific tier should be confirmed with OS (see §6).

| AddressBase Premium feature | NGD Address equivalent | Confidence |
|---|---|---|
| UPRN as persistent key | UPRN persists across feature types | High |
| Provisional UPRNs (planning stage) | Addressing stage includes "Provisional" | High |
| Historic UPRNs (retired/demolished) | Dedicated "Historic Address" feature type; `buildstatus` / `addressstatus` | High |
| Property classification | Up to quaternary-level classifications | High |
| Change-only updates | COU in CSV, full-GB | High |
| UPRN ↔ TOID cross-reference | Reorganised — via `Building` UPRN reference + TOID on `Building Part` | **Needs OS confirmation** |

Source: [Comparison of End-of-Life Address Products](https://docs.os.uk/more-than-maps/os-ngd-migration/comparison-of-end-of-life-address-products),
[OS NGD Address](https://docs.os.uk/osngd/data-structure/address).

---

## 6. Open questions to OS

These are the items we need OS (or the OS Consultancy Team) to confirm before committing.

**Address product (Q1):**
1. Which **tier** of the NGD GB Address Collection carries the full AddressBase-Premium-equivalent lifecycle + cross-reference content?
2. In NGD, **how is the UPRN ↔ building-feature ↔ TOID linkage delivered**, given that `Building` is `osid`-keyed (with a UPRN reference) and only `Building Part` carries TOID? What is the *recommended* join path for "address → building attributes"?
3. Are **provisional** and **historic** UPRNs, **property classification**, and **change-only updates** all included in that tier?
4. Is the premium GB Address Collection available via the **NGD API – Features**, or **download-only via Select+Build**? What is the COU cadence?

**Buildings attribution (Q2):**
5. Confirm `Building` (`bld-fts-building`) carries `numberoffloors`, `height_relativemax_m`, `roofmaterial`, `roofshape`, `buildinguse`, and `connectivity` at building-footprint level — and confirm coverage/completeness for our target geographies.
6. Confirm the `Building` ↔ UPRN cross-reference is the intended way to attach address-level data to a footprint (vs. relying on TOID / `Building Part`).

**Commercial/timeline:**
7. Confirm the **Spring 2027 AddressBase EOL** date and any migration support available to partners.

---

## 7. Short-term workarounds (in place today)

| Area | Workaround | Why | Risk / follow-up |
|---|---|---|---|
| Address→building link | **Spatial bbox + nearest-centroid** match in `uprn_to_height.py` | No NGD UPRN-reference integration yet | Can mis-pick in dense terraces/blocks; superseded by §3.2 target |
| Building identifier | Keep **`osid`** only; TOID not captured | NGD is `osid`-keyed | Fine long-term; TOID optional |
| Construction fields | **EPC preferred, NGD fallback** | EPC richer where available (England & Wales) | No EPC in Scotland / new-build / commercial → NGD fallback |
| England flood risk | **Cached EA RoFRS postcode CSV** (no live API) | EA retired its WFS endpoint Jan 2025 | Postcode gaps return "Could not match" — see [Flood_Risk.md](./Flood_Risk.md) |

---

## 8. Future pathway (intended)

1. **Confirm the product** with OS (§6) — tier, delivery channel, cross-reference mechanics.
2. **Adopt the NGD-native join**: resolve UPRN, then attach building attributes via the
   `Building` feature's **UPRN cross-reference** (`osid`-keyed), replacing the current spatial
   heuristic. Retain spatial match only as a fallback where the cross-reference is absent.
3. **Stand up the address ingest**: full GB Address Collection load + **COU** processing, on the
   delivery channel OS confirms (API vs Select+Build download).
4. **Migrate off AddressBase** ahead of the Spring 2027 EOL.
5. **Enrich the building model** with the now-available NGD attributes (`roofshape`,
   `buildinguse`, `connectivity`) for the 3D-rendering and analytics use cases.

---

## 9. References

**Internal**
- [API_orchestration.md](./API_orchestration.md) — live enrichment pipeline (implementation).
- [Flood_Risk.md](./Flood_Risk.md) — per-country flood risk sourcing.
- `backend/geo/uprn maps/` — the code that implements the current pipeline.

**OS documentation**
- [OS NGD Building feature](https://docs.os.uk/osngd/data-structure/buildings/building-features/building)
- [OS NGD Building Part feature](https://docs.os.uk/osngd/data-structure/buildings/building-features/building-part)
- [OS NGD Address](https://docs.os.uk/osngd/data-structure/address)
- [Comparison of End-of-Life Address Products](https://docs.os.uk/more-than-maps/os-ngd-migration/comparison-of-end-of-life-address-products)
- [OS NGD number-of-floors release](https://www.ordnancesurvey.co.uk/blog/number-of-floors-data-release)
- [OS NGD roof data release](https://www.ordnancesurvey.co.uk/news/new-roof-data-for-over-40-million-buildings)
- [OS Select+Build](https://www.ordnancesurvey.co.uk/products/os-select-build)

---

## 10. Glossary

| Term | Meaning |
|---|---|
| **UPRN** | Unique Property Reference Number — persistent identifier for an addressable location. |
| **TOID** | Topographic Identifier — OS MasterMap feature ID; in NGD it is a *secondary, optional* identifier. |
| **`osid`** | OS NGD primary identifier (GUID); the actual key for NGD features. |
| **NGD** | OS National Geographic Database — the current OS data model replacing AddressBase/MasterMap. |
| **COU** | Change-Only Update — delta feed of only the records that changed. |
| **Select+Build** | OS Data Hub download mechanism for NGD data (GeoPackage/CSV). |
| **EPC** | Energy Performance Certificate (Open Data Communities; England & Wales). |
| **BNG** | British National Grid (EPSG:27700) coordinate system. |
