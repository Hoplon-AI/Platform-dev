"""
Pydantic models for UPRN confidence scoring.
Audit-grade schemas for insurer-defensible output.
"""
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


class RawCandidate:
    pass


class ConfidenceBand(str, Enum):
    """Score interpretation bands. Never call anything "verified" without licensed data."""
    HIGH = "Green"          # ≥ 0.75: Strong evidence, low ambiguity
    MEDIUM = "Yellow"      # 0.45-0.74: Likely, but not definitive
    LOW = "Red"            # <0.45: Weak association


class AddressHint(str, Enum):
    """Detected address type hints."""
    FLAT = "flat"
    HOUSE = "house"
    NONE = "none"


class SignalBreakdown(BaseModel):
    """Individual scoring signals - fully auditable."""
    postcode: float = Field(description="Postcode validity signal (0.00 or 0.20)")
    spatial: float = Field(description="Spatial proximity to centroid (0.00-0.30)")
    density: float = Field(description="Local UPRN density signal (0.00-0.20)")
    hints: float = Field(description="Address hint signal (0.00-0.05)")
    penalties: float = Field(description="Consistency/ambiguity penalties (negative)")


class UPRNCandidate(BaseModel):
    """A single UPRN candidate with confidence scoring."""
    uprn: str
    confidence_score: float = Field(ge=0, le=1)
    confidence_band: ConfidenceBand
    distance_m: float
    neighbor_count: int
    signals: SignalBreakdown
    method: str = "postcode_spatial_inference_v1"
    notes: Optional[str] = None


class UPRNMatchRequest(BaseModel):
    """Input request for UPRN matching."""
    address: str = Field(min_length=1, max_length=500)
    postcode: str = Field(min_length=5, max_length=10)

    @field_validator('postcode')
    @classmethod
    def normalize_postcode(cls, v: str) -> str:
        """Normalize postcode: uppercase, single space."""
        v = re.sub(r'\s+', '', v.upper())
        if len(v) >= 5:
            return f"{v[:-3]} {v[-3:]}"
        return v


class UPRNMatchResponse(BaseModel):
    """Response containing UPRN candidates with confidence scores."""
    request_id: str
    input_address: str
    input_postcode: str
    postcode_valid: bool
    candidates: list[UPRNCandidate]
    best_match: Optional[UPRNCandidate] = None
    warnings: list[str] = Field(default_factory=list)