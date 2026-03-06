"""
Geo module - UPRN confidence scoring service.

Provides deterministic, auditable UPRN matching using:
- OS Open UPRN (geometry)
- ONS Postcode Directory (centroids)
- PostGIS spatial queries
"""
from backend.geo.confidence_mapping.router import router
from backend.geo.confidence_mapping.models import (
    UPRNMatchRequest,
    UPRNMatchResponse,
    UPRNCandidate,
    ConfidenceBand,
    SignalBreakdown,
)
from backend.geo.confidence_mapping.confidence import ConfidenceScorer, ScoringConfig
from backend.geo.confidence_mapping.repository import UPRNRepository

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


class RawCandidate:
    pass