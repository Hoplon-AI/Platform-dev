"""
Deterministic UPRN Confidence Scoring Engine.

Principles (non-negotiable):
1. Deterministic: same input → same score
2. Explainable: each point attributable to a rule
3. Conservative: missing data penalizes, never inflates
4. Composable: multiple weak signals > one strong guess

No ML. No string similarity black boxes.
"""
from dataclasses import dataclass
import re
from typing import Optional

from backend.geo import SignalBreakdown, UPRNCandidate, ConfidenceBand, AddressHint


@dataclass
class ScoringConfig:
    """Confidence scoring parameters - explicit and auditable."""
    # Postcode validity
    POSTCODE_VALID_SCORE: float = 0.20
    # Spatial proximity thresholds (meters)
    SPATIAL_TIER_1_DIST: float = 15.0
    SPATIAL_TIER_1_SCORE: float = 0.30
    SPATIAL_TIER_2_DIST: float = 30.0
    SPATIAL_TIER_2_SCORE: float = 0.20
    SPATIAL_TIER_3_DIST: float = 60.0
    SPATIAL_TIER_3_SCORE: float = 0.10
    # Density thresholds
    DENSITY_SINGLE_SCORE: float = 0.20
    DENSITY_SMALL_CLUSTER_MAX: int = 5
    DENSITY_SMALL_CLUSTER_SCORE: float = 0.10
    # Address hints
    HINT_FLAT_SCORE: float = 0.05
    HINT_HOUSE_SCORE: float = 0.05
    # Penalties
    AMBIGUITY_PENALTY: float = -0.15
    INCONSISTENCY_PENALTY: float = -0.20
    # Hard cap without AddressBase
    MAX_CONFIDENCE: float = 0.95
    # Search params
    DEFAULT_SEARCH_RADIUS_M: float = 60.0
    MAX_CANDIDATES: int = 20


@dataclass
class RawCandidate:
    """Raw candidate data from database."""
    uprn: str
    distance_m: float
    neighbor_count: int


class ConfidenceScorer:
    """Transparent, repeatable confidence scoring."""

    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()

    def validate_postcode(self, postcode: str) -> bool:
        """Validate UK postcode format."""
        pattern = r'^[A-Z]{1,2}[0-9][0-9A-Z]?\s[0-9][A-Z]{2}$'
        return bool(re.match(pattern, postcode.upper()))

    def calculate_postcode_signal(self, postcode_valid: bool) -> float:
        """Postcode validity baseline gate."""
        return self.config.POSTCODE_VALID_SCORE if postcode_valid else 0.0

    def calculate_spatial_signal(self, distance_m: float) -> float:
        """
        Spatial proximity to postcode centroid.
        ≤15m: +0.30 | 15-30m: +0.20 | 30-60m: +0.10 | >60m: +0.00
        """
        if distance_m <= self.config.SPATIAL_TIER_1_DIST:
            return self.config.SPATIAL_TIER_1_SCORE
        elif distance_m <= self.config.SPATIAL_TIER_2_DIST:
            return self.config.SPATIAL_TIER_2_SCORE
        elif distance_m <= self.config.SPATIAL_TIER_3_DIST:
            return self.config.SPATIAL_TIER_3_SCORE
        return 0.0

    def calculate_density_signal(self, neighbor_count: int) -> float:
        """
        Local UPRN density consistency.
        Single: +0.20 | 2-5: +0.10 | 6+: +0.00
        """
        if neighbor_count == 1:
            return self.config.DENSITY_SINGLE_SCORE
        elif neighbor_count <= self.config.DENSITY_SMALL_CLUSTER_MAX:
            return self.config.DENSITY_SMALL_CLUSTER_SCORE
        return 0.0

    def detect_address_hint(self, address: str) -> AddressHint:
        """Detect non-controversial address type hints."""
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

    def calculate_hint_signal(self, hint: AddressHint) -> float:
        """Address hint signal (very light touch)."""
        if hint == AddressHint.FLAT:
            return self.config.HINT_FLAT_SCORE
        elif hint == AddressHint.HOUSE:
            return self.config.HINT_HOUSE_SCORE
        return 0.0

    def calculate_ambiguity_penalty(
            self, candidates: list[RawCandidate], current: RawCandidate
    ) -> float:
        """Penalty when multiple candidates have same best spatial score."""
        if len(candidates) < 2:
            return 0.0
        current_spatial = self.calculate_spatial_signal(current.distance_m)
        same_score_count = sum(
            1 for c in candidates
            if self.calculate_spatial_signal(c.distance_m) == current_spatial
        )
        return self.config.AMBIGUITY_PENALTY if same_score_count > 1 else 0.0

    def calculate_consistency_penalty(
            self, hint: AddressHint, neighbor_count: int
    ) -> float:
        """Penalty for inconsistent signals (e.g., house hint + dense cluster)."""
        if hint == AddressHint.HOUSE and neighbor_count > 5:
            return self.config.INCONSISTENCY_PENALTY
        return 0.0

    def determine_confidence_band(self, score: float) -> ConfidenceBand:
        """Map score to confidence band."""
        if score >= 0.75:
            return ConfidenceBand.HIGH
        elif score >= 0.45:
            return ConfidenceBand.MEDIUM
        return ConfidenceBand.LOW


    def generate_notes(
            self, distance_m: float, neighbor_count: int,
            hint: AddressHint, band: ConfidenceBand
    ) -> str:
        """Generate human-readable notes for the match."""
        parts = []
        if distance_m <= 15:
            parts.append(f"Within {distance_m:.0f}m of postcode centroid")
        elif distance_m <= 30:
            parts.append(f"Matched via centroid proximity ({distance_m:.0f}m)")
        else:
            parts.append(f"Peripheral match ({distance_m:.0f}m from centroid)")

        if neighbor_count == 1:
            parts.append("isolated property")
        elif neighbor_count <= 5:
            parts.append(f"small cluster ({neighbor_count} UPRNs)")
        else:
            parts.append(f"dense cluster ({neighbor_count} UPRNs)")

        if hint != AddressHint.NONE:
            parts.append(f"{hint.value} indicator detected")
        return "; ".join(parts)

    def score_candidate(
            self, candidate: RawCandidate, all_candidates: list[RawCandidate],
            address: str, postcode_valid: bool
    ) -> UPRNCandidate:
        """Calculate full confidence score for a candidate."""
        hint = self.detect_address_hint(address)

        # Calculate signals
        postcode_signal = self.calculate_postcode_signal(postcode_valid)
        spatial_signal = self.calculate_spatial_signal(candidate.distance_m)
        density_signal = self.calculate_density_signal(candidate.neighbor_count)
        hint_signal = self.calculate_hint_signal(hint)

        # Calculate penalties
        ambiguity = self.calculate_ambiguity_penalty(all_candidates, candidate)
        consistency = self.calculate_consistency_penalty(hint, candidate.neighbor_count)
        total_penalties = ambiguity + consistency

        # Sum and cap
        raw_score = (postcode_signal + spatial_signal + density_signal
                     + hint_signal + total_penalties)
        final_score = max(0.0, min(raw_score, self.config.MAX_CONFIDENCE))
        final_score = round(final_score, 2)

        band = self.determine_confidence_band(final_score)

        return UPRNCandidate(
            uprn=candidate.uprn,
            confidence_score=final_score,
            confidence_band=band,
            distance_m=round(candidate.distance_m, 2),
            neighbor_count=candidate.neighbor_count,
            signals=SignalBreakdown(
                postcode=postcode_signal,
                spatial=spatial_signal,
                density=density_signal,
                hints=hint_signal,
                penalties=total_penalties
            ),
            notes=self.generate_notes(candidate.distance_m, candidate.neighbor_count, hint, band)
        )

    def score_all_candidates(
            self, candidates: list[RawCandidate], address: str, postcode_valid: bool
    ) -> list[UPRNCandidate]:
        """Score all candidates and return sorted by confidence."""
        scored = [
            self.score_candidate(c, candidates, address, postcode_valid)
            for c in candidates
        ]
        return sorted(scored, key=lambda x: x.confidence_score, reverse=True)