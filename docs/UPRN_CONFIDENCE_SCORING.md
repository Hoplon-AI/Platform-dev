# UPRN Confidence Scoring Model

## Overview

The UPRN Confidence Scoring Engine provides a **deterministic, explainable** confidence score for address-to-UPRN matching. Unlike black-box ML approaches, every point in the score is attributable to a specific rule.

### Core Principle

**Confidence reflects certainty, not accuracy.**

The score answers: *"How certain are we that `best_match` is the correct UPRN?"*

- If there's only 1 UPRN near a postcode → we're confident (it's the only option)
- If there are 50 UPRNs → we're honestly uncertain (we're picking among many)

This approach ensures that **high confidence matches are trustworthy**, while low confidence honestly signals "manual verification recommended."

---

## Confidence Bands

| Band | Score Range | Meaning | Recommended Action |
|------|-------------|---------|-------------------|
| **Green** (HIGH) | ≥ 0.65 | Strong certainty | Auto-accept |
| **Yellow** (MEDIUM) | 0.35 - 0.64 | Moderate certainty | Review recommended |
| **Red** (LOW) | < 0.35 | Low certainty | Manual verification required |

---

## Scoring Logic

### Base Confidence (Primary Factor)

The number of UPRN candidates within the search radius (60m from postcode centroid) is the dominant factor:

| Candidates | Base Confidence | Rationale |
|------------|-----------------|-----------|
| 1 UPRN (within 30m) | 0.90 | Only option, close to centroid |
| 1 UPRN (>30m away) | 0.55 | Suspicious - possible missing data |
| 2 UPRNs | 0.60 | 50/50 odds, we pick closest |
| 3 UPRNs | 0.45 | ~33% chance |
| 4-10 UPRNs | 0.25 | Low confidence |
| 10+ UPRNs | 0.10 | Dense area, essentially guessing |

### Adjustments

| Factor | Adjustment | Condition |
|--------|------------|-----------|
| Valid postcode format | +0.05 | Postcode matches UK format regex |
| Best candidate very close | +0.05 | Best match ≤5m from centroid |
| Candidate far from centroid | -0.10 | Candidate >20m from centroid |

### Final Score Calculation

```
final_score = base_confidence + postcode_bonus + distance_adjustment
final_score = clamp(final_score, 0.05, 0.95)
```

---

## Example Scenarios

### Scenario 1: Rural Isolated Property
- **Input**: Address in rural postcode with 1 UPRN within 60m
- **Candidates**: 1
- **Distance**: 5m from centroid
- **Score**: 0.90 + 0.05 (postcode) + 0.05 (close) = **0.95 (Green)**
- **Interpretation**: High confidence - only one property, definitely correct

### Scenario 2: Residential Street
- **Input**: Address on typical residential street
- **Candidates**: 8
- **Distance**: 12m from centroid
- **Score**: 0.25 + 0.05 (postcode) = **0.30 (Red)**
- **Interpretation**: Low confidence - one of 8 similar properties, need address matching

### Scenario 3: City Centre Dense Area
- **Input**: Address in central London
- **Candidates**: 20 (capped)
- **Distance**: 0m from centroid
- **Score**: 0.10 + 0.05 (postcode) + 0.05 (close) = **0.20 (Red)**
- **Interpretation**: Very low confidence - dense area, many UPRNs at same location

### Scenario 4: Suspicious Single UPRN
- **Input**: Address where only 1 UPRN found but it's 45m away
- **Candidates**: 1
- **Distance**: 45m from centroid
- **Score**: 0.55 + 0.05 (postcode) - 0.10 (far) = **0.50 (Yellow)**
- **Interpretation**: Medium confidence - only UPRN is far, might be missing data

---

## Limitations

### What This Model Cannot Do

1. **Address String Matching**: Without AddressBase Premium data, we cannot match "221B Baker Street" to a specific UPRN among many at the same location.

2. **Distinguish Flats in Same Building**: Multiple flats at identical coordinates require address-level matching.

3. **Guarantee Accuracy in Dense Areas**: In areas with 10+ UPRNs, the model honestly reports low confidence rather than falsely claiming high confidence.

### Data Quality Signals

The model provides implicit data quality signals:

| Scenario | Signal |
|----------|--------|
| Green + MATCH | Data is good, matching works |
| Green + MISMATCH | **UPRN data incomplete** - correct UPRN missing from database |
| Yellow + MISMATCH | Expected - moderate ambiguity |
| Red + MISMATCH | Expected - high ambiguity, need address matching |

---

## Validation Results

Tested against premium UPRN API (100 UK addresses):

| Confidence Band | Accuracy | Interpretation |
|-----------------|----------|----------------|
| Green (HIGH) | ~100%* | Trustworthy when data is complete |
| Yellow (MEDIUM) | ~58% | Needs verification |
| Red (LOW) | ~20% | Manual check required |

*Need some more testing, green is very rare + UPRN data was incomplete in the testing scenario.

---

## Configuration Parameters

All parameters are configurable via `ScoringConfigV2`:

```python
@dataclass
class ScoringConfigV2:
    # Confidence by candidate count
    SINGLE_UPRN_CONFIDENCE: float = 0.90
    TWO_UPRN_CONFIDENCE: float = 0.60
    THREE_UPRN_CONFIDENCE: float = 0.45
    SMALL_CLUSTER_CONFIDENCE: float = 0.25  # 4-10 UPRNs
    DENSE_CLUSTER_CONFIDENCE: float = 0.10  # 10+ UPRNs

    # Adjustments
    POSTCODE_VALID_BONUS: float = 0.05
    DISTANCE_PENALTY_THRESHOLD_M: float = 20.0
    DISTANCE_PENALTY: float = -0.10

    # Search parameters
    DEFAULT_SEARCH_RADIUS_M: float = 60.0
    MAX_CANDIDATES: int = 20
```

---

## API Response Structure

```json
{
  "request_id": "uuid",
  "input_address": "221B Baker Street, London",
  "input_postcode": "NW1 6XE",
  "postcode_valid": true,
  "candidates": [...],
  "best_match": {
    "uprn": "100022723861",
    "confidence_score": 0.15,
    "confidence_band": "Red",
    "distance_m": 0.0,
    "neighbor_count": 76,
    "signals": {
      "postcode": 0.05,
      "spatial": 0.05,
      "density": 0.10,
      "hints": 0.0,
      "penalties": 0.0
    },
    "notes": "Dense area with 20+ UPRNs; at postcode centroid"
  },
  "warnings": []
}
```

---

## Future Improvements

To improve accuracy beyond the current model:

1. **AddressBase Integration**: Licensed address-to-UPRN mapping would enable string matching
2. **Building Name Matching**: Fuzzy matching on building/street names
3. **Property Classification**: Residential vs commercial filtering
4. **Historical Match Learning**: Track which candidates are confirmed correct over time
