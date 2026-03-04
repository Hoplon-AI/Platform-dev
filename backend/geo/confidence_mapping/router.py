"""
API Routes for UPRN Confidence Scoring.
"""
from uuid import uuid4
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

from backend.geo import UPRNMatchRequest, UPRNMatchResponse
from backend.geo import ConfidenceScorerV2, ScoringConfigV2
from backend.geo import UPRNRepository

router = APIRouter(prefix="/api/v1/geo", tags=["UPRN Matching"])

# Initialize scorer with default config (V2 - improved scoring)
scorer = ConfidenceScorerV2(ScoringConfigV2())


@router.post(
    "/uprn/match",
    response_model=UPRNMatchResponse,
    summary="Match address to UPRN candidates",
    description="""
Returns UPRN candidates with deterministic confidence scores.

**Scoring Principles:**
- Deterministic: same input → same score
- Explainable: each point attributable to a rule  
- Conservative: missing data penalizes, never inflates

**Score Bands:**
- High (≥0.75): Strong evidence, low ambiguity
- Medium (0.55-0.74): Likely, but not definitive
- Low (<0.45): Weak association
    """
)
async def match_uprn(request: UPRNMatchRequest) -> UPRNMatchResponse:
    """Match an address to UPRN candidates with confidence scoring."""

    request_id = str(uuid4())
    warnings: list[str] = []
    config = scorer.config

    # Validate postcode format
    postcode_valid = scorer.validate_postcode(request.postcode)
    if not postcode_valid:
        warnings.append(f"Postcode '{request.postcode}' does not match UK format")

    # Check if postcode exists in database
    if not await UPRNRepository.postcode_exists(request.postcode):
        warnings.append(f"Postcode '{request.postcode}' not found in ONS directory")
        return UPRNMatchResponse(
            request_id=request_id,
            input_address=request.address,
            input_postcode=request.postcode,
            postcode_valid=False,
            candidates=[],
            best_match=None,
            warnings=warnings
        )

    # Get candidates from database
    raw_candidates = await UPRNRepository.get_uprn_candidates(
        postcode=request.postcode,
        radius_m=config.DEFAULT_SEARCH_RADIUS_M,
        limit=config.MAX_CANDIDATES
    )

    if not raw_candidates:
        warnings.append(
            f"No UPRNs found within {config.DEFAULT_SEARCH_RADIUS_M}m of postcode centroid"
        )
        return UPRNMatchResponse(
            request_id=request_id,
            input_address=request.address,
            input_postcode=request.postcode,
            postcode_valid=postcode_valid,
            candidates=[],
            best_match=None,
            warnings=warnings
        )

    # Score all candidates
    scored_candidates = scorer.score_all_candidates(
        candidates=raw_candidates,
        address=request.address,
        postcode_valid=postcode_valid
    )

    best_match = scored_candidates[0] if scored_candidates else None

    if best_match and best_match.confidence_band.value == "Uncertain":
        warnings.append("Best match has low confidence - manual verification recommended")

    return UPRNMatchResponse(
        request_id=request_id,
        input_address=request.address,
        input_postcode=request.postcode,
        postcode_valid=postcode_valid,
        candidates=scored_candidates,
        best_match=best_match,
        warnings=warnings
    )


@router.get(
    "/uprn/health",
    summary="UPRN service health check"
)
async def uprn_health() -> Dict[str, Any]:
    """Check UPRN service health and data availability."""
    try:
        stats = await UPRNRepository.get_stats()
        return {
            "status": "healthy",
            "data": {
                "uprn_count": stats["uprn_count"],
                "postcode_count": stats["postcode_count"],
                "density_view_ready": stats["density_view_count"] > 0
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "error": str(e)}
        )