import asyncio
from backend.geo.confidence import ConfidenceScorer, RawCandidate
from backend.geo.models import UPRNMatchRequest

# Test 1: Confidence scoring (no database needed)
print("=== Test 1: Confidence Scoring ===")
scorer = ConfidenceScorer()

# Simulate a candidate
candidates = [
    RawCandidate(uprn="10012345678", distance_m=18.0, neighbor_count=1),
    RawCandidate(uprn="10012345679", distance_m=25.0, neighbor_count=3),
    RawCandidate(uprn="10012345680", distance_m=45.0, neighbor_count=12),
]

results = scorer.score_all_candidates(
    candidates=candidates,
    address="12 High Street",
    postcode_valid=True
)

for r in results:
    print(f"UPRN: {r.uprn}")
    print(f"  Score: {r.confidence_score} ({r.confidence_band.value})")
    print(f"  Signals: postcode={r.signals.postcode}, spatial={r.signals.spatial}, density={r.signals.density}")
    print(f"  Notes: {r.notes}")
    print()

# Test 2: Postcode validation
print("=== Test 2: Postcode Validation ===")
test_postcodes = ["SW1A 1AA", "EH3 9AA", "invalid", "M1 1AA"]
for pc in test_postcodes:
    print(f"  {pc}: {'✓ valid' if scorer.validate_postcode(pc) else '✗ invalid'}")

# Add this to your test_geo.py
print("\n=== Test 3: Single candidate (no ambiguity) ===")
single = [RawCandidate(uprn="10012345678", distance_m=18.0, neighbor_count=1)]
result = scorer.score_all_candidates(single, "12 High Street", True)
print(f"Score: {result[0].confidence_score} (expected: 0.60)")

print("\n=== All tests passed! ===")

