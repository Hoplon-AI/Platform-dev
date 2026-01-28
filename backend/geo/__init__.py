"""
Geo module - UPRN confidence scoring service.

Provides deterministic, auditable UPRN matching using:
- OS Open UPRN (geometry)
- ONS Postcode Directory (centroids)
- PostGIS spatial queries
"""
from .router import router
from .models import (
    UPRNMatchRequest,
    UPRNMatchResponse,
    UPRNCandidate,
    ConfidenceBand,
    SignalBreakdown,
)
from .confidence import ConfidenceScorer, ScoringConfig
from .repository import UPRNRepository

__all__ = [
    "router",
    "UPRNMatchRequest",
    "UPRNMatchResponse",
    "UPRNCandidate",
    "ConfidenceBand",
    "SignalBreakdown",
    "ConfidenceScorer",
    "ScoringConfig",
    "UPRNRepository",
]