"""
Tests for the UPRN Confidence Scoring Engine.
Ensures deterministic, auditable behavior.
"""
import pytest
from backend.geo.confidence import ConfidenceScorer, RawCandidate, ScoringConfig
from backend.geo.models import ConfidenceBand, AddressHint


@pytest.fixture
def scorer():
    return ConfidenceScorer()


class TestPostcodeValidation:
    @pytest.mark.parametrize("postcode,expected", [
        ("SW1A 1AA", True),
        ("EH3 9AA", True),
        ("M1 1AA", True),
        ("EC1A 1BB", True),
        ("invalid", False),
        ("12345", False),
        ("SW1A1AA", False),  # No space
    ])
    def test_postcode_validation(self, scorer, postcode, expected):
        assert scorer.validate_postcode(postcode) == expected


class TestSpatialScoring:
    @pytest.mark.parametrize("distance,expected", [
        (5.0, 0.30),
        (15.0, 0.30),
        (15.1, 0.20),
        (30.0, 0.20),
        (30.1, 0.10),
        (60.0, 0.10),
        (60.1, 0.00),
    ])
    def test_spatial_scoring(self, scorer, distance, expected):
        assert scorer.calculate_spatial_signal(distance) == expected


class TestDensityScoring:
    @pytest.mark.parametrize("count,expected", [
        (1, 0.20),
        (2, 0.10),
        (5, 0.10),
        (6, 0.00),
    ])
    def test_density_scoring(self, scorer, count, expected):
        assert scorer.calculate_density_signal(count) == expected


class TestAddressHints:
    @pytest.mark.parametrize("address,expected_hint", [
        ("Flat 2, 123 High Street", AddressHint.FLAT),
        ("Unit 5, Industrial Estate", AddressHint.FLAT),
        ("Rose Cottage", AddressHint.HOUSE),
        ("123 High Street", AddressHint.NONE),
    ])
    def test_hint_detection(self, scorer, address, expected_hint):
        assert scorer.detect_address_hint(address) == expected_hint


class TestConfidenceBands:
    @pytest.mark.parametrize("score,expected_band", [
        (0.90, ConfidenceBand.HIGH),
        (0.75, ConfidenceBand.HIGH),
        (0.74, ConfidenceBand.MEDIUM),
        (0.55, ConfidenceBand.MEDIUM),
        (0.54, ConfidenceBand.LOW),
        (0.35, ConfidenceBand.LOW),
        (0.34, ConfidenceBand.UNCERTAIN),
    ])
    def test_confidence_bands(self, scorer, score, expected_band):
        assert scorer.determine_confidence_band(score) == expected_band


class TestSpecExample:
    def test_spec_example(self, scorer):
        """
        From spec: Address "12 High Street, EH3 9AA"
        Postcode valid, 18m distance, 1 neighbor = 0.60
        """
        candidates = [RawCandidate(uprn="1234", distance_m=18.0, neighbor_count=1)]
        result = scorer.score_all_candidates(candidates, "12 High Street", True)

        assert result[0].confidence_score == 0.60
        assert result[0].signals.postcode == 0.20
        assert result[0].signals.spatial == 0.20
        assert result[0].signals.density == 0.20
        assert result[0].confidence_band == ConfidenceBand.MEDIUM


class TestDeterminism:
    def test_same_input_same_output(self, scorer):
        """Same input must always produce same output."""
        candidates = [RawCandidate(uprn="1234", distance_m=25.0, neighbor_count=3)]

        result1 = scorer.score_all_candidates(candidates, "123 Main St", True)
        result2 = scorer.score_all_candidates(candidates, "123 Main St", True)

        assert result1[0].confidence_score == result2[0].confidence_score