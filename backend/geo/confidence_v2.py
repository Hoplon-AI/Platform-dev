"""
Deterministic UPRN Confidence Scoring Engine v2.

Key insight: Confidence should reflect "how certain are we that best_match is correct?"
- Single UPRN in search radius = HIGH confidence (we know it's right)
- Many UPRNs = LOW confidence (we're guessing)

Principles:
1. Deterministic: same input → same score
2. Explainable: each point attributable to a rule
3. Honest: confidence reflects actual certainty, not a guess
"""
from dataclasses import dataclass
import re
from typing import Optional

from .models import SignalBreakdown, UPRNCandidate, ConfidenceBand, AddressHint


@dataclass
class ScoringConfigV2:
    """Confidence scoring parameters - tuned for meaningful confidence."""

    # Search radius for "isolated property" determination
    ISOLATION_RADIUS_M: float = 30.0  # Consider property isolated if alone within this

    # Confidence by candidate count (the core logic)
    SINGLE_UPRN_CONFIDENCE: float = 0.90  # Only 1 UPRN = very confident
    TWO_UPRN_CONFIDENCE: float = 0.60     # 2 UPRNs = decent odds
    THREE_UPRN_CONFIDENCE: float = 0.45   # 3 UPRNs = coin flip-ish
    SMALL_CLUSTER_CONFIDENCE: float = 0.25  # 4-10 UPRNs = low confidence
    DENSE_CLUSTER_CONFIDENCE: float = 0.10  # 10+ UPRNs = basically guessing

    # Postcode validity bonus
    POSTCODE_VALID_BONUS: float = 0.05

    # Distance penalty for candidates far from centroid
    DISTANCE_PENALTY_THRESHOLD_M: float = 20.0
    DISTANCE_PENALTY: float = -0.10

    # Search params
    DEFAULT_SEARCH_RADIUS_M: float = 60.0
    MAX_CANDIDATES: int = 20


@dataclass
class RawCandidate:
    """Raw candidate data from database."""
    uprn: str
    distance_m: float
    neighbor_count: int


class ConfidenceScorerV2:
    """Honest confidence scoring - reflects actual certainty."""

    def __init__(self, config: Optional[ScoringConfigV2] = None):
        self.config = config or ScoringConfigV2()

    def validate_postcode(self, postcode: str) -> bool:
        """Validate UK postcode format."""
        pattern = r'^[A-Z]{1,2}[0-9][0-9A-Z]?\s[0-9][A-Z]{2}$'
        return bool(re.match(pattern, postcode.upper()))

    def detect_address_hint(self, address: str) -> AddressHint:
        """Detect address type hints."""
        addr_lower = address.lower()
        flat_indicators = ['flat', 'unit', 'apt', 'apartment', 'floor']
        house_indicators = ['house', 'cottage', 'lodge', 'villa', 'bungalow']

        for ind in flat_indicators:
            if ind in addr_lower:
                return AddressHint.FLAT
        for ind in house_indicators:
            if ind in addr_lower:
                return AddressHint.HOUSE
        return AddressHint.NONE

    def calculate_base_confidence(self, total_candidates: int, best_distance_m: float = 0.0) -> float:
        """
        Core logic: confidence based on how many candidates we have.

        1 candidate close (<30m) = 90% confident (it's the only option, and it's close)
        1 candidate far (>30m) = 55% confident (suspicious - might be missing data)
        2 candidates = 60% (50/50 but we pick closest)
        3 candidates = 45%
        4-10 candidates = 25%
        10+ candidates = 10% (basically random)
        """
        if total_candidates == 1:
            # Single UPRN but far from centroid = suspicious (missing data?)
            if best_distance_m > 30.0:
                return 0.55  # Drop to Yellow - might be incomplete data
            return self.config.SINGLE_UPRN_CONFIDENCE
        elif total_candidates == 2:
            return self.config.TWO_UPRN_CONFIDENCE
        elif total_candidates == 3:
            return self.config.THREE_UPRN_CONFIDENCE
        elif total_candidates <= 10:
            return self.config.SMALL_CLUSTER_CONFIDENCE
        else:
            return self.config.DENSE_CLUSTER_CONFIDENCE

    def calculate_distance_adjustment(self, distance_m: float, is_best: bool) -> float:
        """
        Small bonus for being closest, penalty for being far.
        Only significant for tie-breaking.
        """
        if is_best and distance_m <= 5.0:
            return 0.05  # Small bonus for being very close
        elif distance_m > self.config.DISTANCE_PENALTY_THRESHOLD_M:
            return self.config.DISTANCE_PENALTY
        return 0.0

    def determine_confidence_band(self, score: float) -> ConfidenceBand:
        """Map score to confidence band."""
        if score >= 0.65:
            return ConfidenceBand.HIGH  # Green - trustworthy
        elif score >= 0.35:
            return ConfidenceBand.MEDIUM  # Yellow - needs verification
        return ConfidenceBand.LOW  # Red - don't trust without manual check

    def generate_notes(
            self, distance_m: float, total_candidates: int,
            hint: AddressHint, band: ConfidenceBand
    ) -> str:
        """Generate human-readable notes."""
        parts = []

        # Candidate count context
        if total_candidates == 1:
            if distance_m > 30:
                parts.append("Only UPRN but far from centroid (possible missing data)")
            else:
                parts.append("Only UPRN within search radius")
        elif total_candidates == 2:
            parts.append("One of 2 nearby UPRNs")
        elif total_candidates <= 5:
            parts.append(f"One of {total_candidates} nearby UPRNs")
        elif total_candidates <= 10:
            parts.append(f"Cluster of {total_candidates} UPRNs")
        else:
            parts.append(f"Dense area with {total_candidates}+ UPRNs")

        # Distance context
        if distance_m <= 5:
            parts.append(f"at postcode centroid")
        elif distance_m <= 15:
            parts.append(f"{distance_m:.0f}m from centroid")
        else:
            parts.append(f"{distance_m:.0f}m from centroid (peripheral)")

        if hint != AddressHint.NONE:
            parts.append(f"{hint.value} indicator")

        return "; ".join(parts)

    def score_candidate(
            self, candidate: RawCandidate, all_candidates: list[RawCandidate],
            address: str, postcode_valid: bool, is_best: bool = False
    ) -> UPRNCandidate:
        """Calculate confidence score for a candidate."""
        hint = self.detect_address_hint(address)
        total_candidates = len(all_candidates)

        # Find closest candidate distance (for single-UPRN suspicious check)
        best_distance = min(c.distance_m for c in all_candidates) if all_candidates else 0.0

        # Base confidence from candidate count (and distance if single UPRN)
        base_confidence = self.calculate_base_confidence(total_candidates, best_distance)

        # Small adjustments
        postcode_bonus = self.config.POSTCODE_VALID_BONUS if postcode_valid else 0.0
        distance_adj = self.calculate_distance_adjustment(candidate.distance_m, is_best)

        # Final score
        raw_score = base_confidence + postcode_bonus + distance_adj
        final_score = max(0.05, min(raw_score, 0.95))
        final_score = round(final_score, 2)

        band = self.determine_confidence_band(final_score)

        # Build signal breakdown for transparency
        signals = SignalBreakdown(
            postcode=postcode_bonus,
            spatial=distance_adj,
            density=base_confidence,  # Using density field for base confidence
            hints=0.0,
            penalties=0.0
        )

        return UPRNCandidate(
            uprn=candidate.uprn,
            confidence_score=final_score,
            confidence_band=band,
            distance_m=round(candidate.distance_m, 2),
            neighbor_count=candidate.neighbor_count,
            signals=signals,
            notes=self.generate_notes(candidate.distance_m, total_candidates, hint, band)
        )

    def score_all_candidates(
            self, candidates: list[RawCandidate], address: str, postcode_valid: bool
    ) -> list[UPRNCandidate]:
        """Score all candidates and return sorted by distance (closest first)."""
        # Sort by distance first to determine "best"
        sorted_candidates = sorted(candidates, key=lambda x: x.distance_m)

        scored = []
        for i, c in enumerate(sorted_candidates):
            is_best = (i == 0)  # First one (closest) is best
            scored.append(
                self.score_candidate(c, candidates, address, postcode_valid, is_best)
            )

        return scored
