# Flood Risk

`backend/geo/uprn maps/flood_risk.py`

Looks up the published flood risk band for a British National Grid point, dispatching by country to the relevant national agency. Inputs come directly from the OS Places record already fetched by the address pipeline — no extra geocoding calls are needed.

---

## Output schema

Every lookup returns the same three-field dict:

| Field | Type | Description |
|---|---|---|
| `flood_risk_band` | `str \| None` | Band as published by the agency (see per-country sections below). `None` when the lookup is not supported or a required input is missing. |
| `flood_risk_source` | `str \| None` | Agency name (`"EA RoFRS"`, `"NRW FRAW"`, `"SEPA"`). |
| `flood_risk_note` | `str \| None` | Additional context — used when the band is `None`, `"Very Low"`, or `"Could not match"`. |

On a hard request error the function returns an error **string** instead of a dict.

---

## Country dispatch

The `COUNTRY_CODE` field from OS Places (`E`, `W`, `S`, `N`) determines which agency is queried.

```
E  →  EA RoFRS          postcode CSV
W  →  NRW FRAW          WFS spatial query
S  →  SEPA Flood Maps   ArcGIS MapServer spatial query
N  →  not supported
```

**Bands are not directly comparable across countries.** Each agency defines its own probability thresholds, and Scotland's bands are on an entirely different scale to England and Wales. A "High" in Scotland means a ≥10%/year chance; a "High" in England means ≥3.3%/year. Scotland also reports undefended (natural) risk, while England and Wales report post-defence risk. Do not rank or aggregate across the England/Wales/Scotland divide without accounting for these differences.

### Annual probability comparison

| Band | England (EA RoFRS) | Wales (NRW FRAW) | Scotland (SEPA) |
|---|---|---|---|
| High | ≥ 3.3%/yr (1-in-30) | ≥ 3.3%/yr (1-in-30) | ≥ 10%/yr (1-in-10) |
| Medium | 1.0 – 3.3%/yr (1-in-100 to 1-in-30) | Rivers/SW: 1.0 – 3.3%/yr · Coastal: 0.5 – 3.3%/yr | 0.5 – 10%/yr (1-in-200 to 1-in-10) |
| Low | 0.1 – 1.0%/yr (1-in-1000 to 1-in-100) | Rivers/SW: 0.1 – 1.0%/yr · Coastal: 0.1 – 0.5%/yr | 0.1 – 0.5%/yr (1-in-1000 to 1-in-200) |
| Very Low | < 0.1%/yr (worse than 1-in-1000) | *(not published — outside all extents)* | *(not published — outside all extents)* |
| Accounts for defences? | Yes | Yes | **No** (undefended/natural risk) |
| Terminology | "Risk" | "Risk" | "Likelihood" |

**Key implication:** because Scotland is undefended and uses a higher High threshold, a Scottish "Low" (0.1–0.5%/yr) is roughly equivalent to an English/Welsh "Low-Medium", and a Scottish "High" (≥10%/yr) describes events that would be "High" in England only at the most extreme end. When comparing properties across nations, use the annual probability ranges above rather than the band labels.

---

## England — EA RoFRS (postcode CSV)

**Bands:** High / Medium / Low / Very Low  
**Basis:** defended (post-flood-defence) risk

| Band | Annual probability | Return period |
|---|---|---|
| High | ≥ 3.3% | more frequent than 1-in-30 |
| Medium | 1.0 – 3.3% | 1-in-100 to 1-in-30 |
| Low | 0.1 – 1.0% | 1-in-1000 to 1-in-100 |
| Very Low | < 0.1% | less frequent than 1-in-1000 |

**Source:** `Postcodes_Risk_Assessment_All.csv`  
Dataset: <https://environment.data.gov.uk/dataset/53cba123-71f8-417a-8441-4c7ba111e8e1>  
Licence: OGL v3 — quarterly updates

### Why a CSV and not an API

The EA retired its WFS endpoint in January 2025 when NaFRA2 replaced the underlying dataset. NaFRA2 is only available as a raster WMS (GetFeatureInfo returns nothing useful for band lookups). The `gisrest.defra.gov.uk` server is internal to Defra and not publicly accessible. The official "Check Long Term Flood Risk" service itself uses postcode-level aggregates, not per-property cells, and the CSV is the same underlying data. There is no public per-cell vector flood risk API for England as of May 2026.

### How it works

The CSV is loaded once into memory on the first call and cached for the process lifetime. Each row maps a postcode to counts of properties at each risk level (`HIGH_CNT`, `MED_CNT`, `LOW_CNT`). The band assigned is the highest non-zero count:

```
HIGH_CNT > 0  →  High
MED_CNT  > 0  →  Medium
LOW_CNT  > 0  →  Low
all zero       →  Very Low
```

Postcodes not present in the CSV return `flood_risk_band: "Could not match"`. This is an honest gap — the CSV covers the residential receptor dataset, which does not include all postcodes that the live EA service covers.

### Known limitation

Some postcodes that appear at risk on the official EA checker (<https://check-long-term-flood-risk.service.gov.uk/risk>) are missing from the CSV (e.g. SY3 8JY, YO1 9SN). This is an upstream data completeness issue, not a bug. Returning `"Could not match"` rather than defaulting to `"Very Low"` is intentional — a silent false Very Low would be worse than an honest gap. A WMS fallback for missed postcodes is a potential future improvement.

### Setup

Download `Postcodes_Risk_Assessment_All.csv` and place it alongside `flood_risk.py`:

```
backend/geo/uprn maps/
    flood_risk.py
    Postcodes_Risk_Assessment_All.csv   ← required
```

---

## Wales — NRW FRAW (WFS)

**Bands:** High / Medium / Low (+ Very Low when outside all extents)  
**Basis:** defended (post-flood-defence) risk

Wales has slightly different thresholds for coastal vs rivers/surface water at the Medium band:

| Band | Rivers & surface water | Coastal | Return period (rivers) |
|---|---|---|---|
| High | > 3.3%/yr | > 3.3%/yr | more frequent than 1-in-30 |
| Medium | 1.0 – 3.3%/yr | 0.5 – 3.3%/yr | 1-in-100 to 1-in-30 |
| Low | 0.1 – 1.0%/yr | 0.1 – 0.5%/yr | 1-in-1000 to 1-in-100 |
| Very Low | *(not published)* | *(not published)* | — |

NRW does not publish a Very Low band. Points outside all FRAW extents are reported as Very Low by this code with a note to that effect.

**Source:** Natural Resources Wales Flood Risk Assessment Wales  
WFS endpoint: `https://datamap.gov.wales/geoserver/inspire-nrw/wfs`

### How it works

Queries three separate WFS layers using a `CQL_FILTER INTERSECTS(geom_col, POINT(x y))` against the BNG coordinates. The highest band found across any layer is returned.

| Layer typename | Geometry column |
|---|---|
| `inspire-nrw:NRW_FLOOD_RISK_FROM_RIVERS` | `geom` |
| `inspire-nrw:NRW_FLOOD_RISK_FROM_SEA` | `geom` |
| `inspire-nrw:NRW_FLOOD_RISK_FROM_SURFACE_WATER_SMALL_WATERCOURSES` | `fme_geometry` |

The geometry column difference on the surface water layer is an upstream FME export artifact — not a naming inconsistency in our code. Querying with the wrong column name returns HTTP 400.

If the point falls outside all three layer extents, the result is `Very Low` with a note that FRAW itself does not publish a Very Low band — the point is simply outside all flood extents.

### History note

The old monolithic layer `inspire-nrw:NRW_FLOOD_RISK_ASSESSMENT_WALES` and field `RISK_BAND` no longer exist as of 2026. The current risk field is `risk` (lowercase). Always verify against the layer-group capabilities document if queries start returning 400 errors: <https://datamap.gov.wales/capabilities/layergroup/889/?ows_service=wfs>

---

## Scotland — SEPA (ArcGIS MapServer)

**Bands:** High / Medium / Low (+ Very Low when outside all extents)  
**Basis:** undefended (natural) risk — flood defences are NOT factored in

SEPA uses the term "likelihood" rather than "probability", but the values are annual probability percentages. The thresholds are significantly different from England and Wales:

| Band (SEPA: "likelihood") | Annual probability | Return period |
|---|---|---|
| High | ≥ 10%/yr | more frequent than 1-in-10 |
| Medium | 0.5 – 10%/yr | 1-in-200 to 1-in-10 |
| Low | 0.1 – 0.5%/yr | 1-in-1000 to 1-in-200 |
| Very Low | *(not published)* | — |

Because Scotland reports undefended risk, the same physical flooding event will appear at a higher band in Scotland than it would in England or Wales (where defences reduce the apparent risk). A Scottish "Low" (0.1–0.5%/yr) covers roughly the same probability range as the upper end of an English "Low" and part of English "Medium".

**Source:** SEPA Flood Maps  
Service: `https://map.sepa.org.uk/server/rest/services/Open/Flood_Maps/MapServer`

### How it works

Queries SEPA's ArcGIS REST MapServer using a point-in-polygon spatial query (`esriSpatialRelIntersects`) against six layers — river and coastal sources at three likelihood thresholds:

| Band | River layer | Coastal layer | Annual probability |
|---|---|---|---|
| High | 0 | 6 | ≥ 10% (1-in-10) |
| Medium | 1 | 7 | 0.5 – 10% (1-in-200 to 1-in-10) |
| Low | 2 | 8 | 0.1 – 0.5% (1-in-1000 to 1-in-200) |

Layers are queried in priority order (High first). The first hit is returned without querying lower-priority bands. Surface water layers (3–5) are excluded to match the rivers-and-sea scope of EA RoFRS and NRW FRAW.

If the point falls outside all six layer extents, the result is `Very Low` with a note.

### History note

SEPA previously published flood maps via ArcGIS Online (org ID `6MAR0WJ80jL5oZBp`). That organisation is defunct. All lookups must go to `map.sepa.org.uk` directly. If queries start failing, verify the layer list at the service directory URL above.

---

## Northern Ireland

Not supported. No equivalent free public flood risk API exists for Northern Ireland. The result is `flood_risk_band: None` with a note.

---

## Integration with address_to_final.py

Flood risk is integrated as a final step in all four pipeline functions. The inputs (`x`, `y`, `country_code`, `postcode`) are all available from the OS Places record resolved in Step 1, so no extra API call is made.

**Single address / UPRN** — calls `get_flood_risk_from_coords` directly.

**Batch address / UPRN** — collects `(uprn, x, y, country_code, postcode)` tuples in the same loop that collects NGD and listed building coordinates, then calls `get_flood_risks_from_coords_batch` once. The batch function opens a single `requests.Session` and reuses it across all properties, cutting TCP overhead.

The three flood fields appear in every result dict:

```python
{
    ...
    "flood_risk_band":   "High" | "Medium" | "Low" | "Very Low" | "Could not match" | None,
    "flood_risk_source": "EA RoFRS" | "NRW FRAW" | "SEPA" | None,
    "flood_risk_note":   str | None,
    ...
}
```

---

## Maintenance

The three data sources are operated by separate agencies and change independently.

| Agency | What to check | Where |
|---|---|---|
| EA (England) | New CSV quarterly. Download and replace `Postcodes_Risk_Assessment_All.csv`. | Dataset page linked above |
| NRW (Wales) | Layer typenames and geometry column names if 400 errors appear. | Layer-group capabilities URL above |
| SEPA (Scotland) | Layer IDs if queries return no features unexpectedly. | MapServer service directory URL above |

The config block at the top of `flood_risk.py` has the current values with verification dates noted in comments. Update there first.
