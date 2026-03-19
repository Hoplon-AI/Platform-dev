"""
Geo module - UPRN confidence scoring service.
"""
from backend.geo.confidence_mapping.models import (
    UPRNMatchRequest,
    UPRNMatchResponse,
    UPRNCandidate,
    ConfidenceBand,
    SignalBreakdown,
    AddressHint,
)
from backend.geo.confidence_mapping.confidence import ConfidenceScorer, ScoringConfig, RawCandidate
from backend.geo.confidence_mapping.confidence_v2 import ConfidenceScorerV2, ScoringConfigV2
from backend.geo.confidence_mapping.repository import UPRNRepository
from backend.geo.confidence_mapping.router import router

__all__ = [
    "router",
    "UPRNMatchRequest",
    "UPRNMatchResponse",
    "UPRNCandidate",
    "ConfidenceBand",
    "SignalBreakdown",
    "AddressHint",
    "ConfidenceScorer",
    "ScoringConfig",
    "ConfidenceScorerV2",
    "ScoringConfigV2",
    "UPRNRepository",
    "RawCandidate",
]