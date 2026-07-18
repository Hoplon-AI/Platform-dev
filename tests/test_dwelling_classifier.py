"""Unit tests for backend/core/classification/dwelling_classifier.py."""

import pytest

from backend.core.classification.dwelling_classifier import (
    classify_dwelling_form,
    derive_is_standalone,
    derive_fra_requirement,
)


class TestClassifyDwellingForm:
    @pytest.mark.parametrize("property_type,expected", [
        # Cottsway (Test Example 8) vocabulary
        ("House", "house"),
        ("Bungalow", "bungalow"),
        ("Flat", "flat"),
        ("Maisonette", "maisonette"),
        ("Studio", "flat"),
        ("Shared House", "house"),
        ("Garage", "garage"),
        ("Garage Block", "garage"),
        ("Private Drainage/Services", "infrastructure"),
        ("Office", "commercial"),
        ("Community Facilities", "commercial"),
        ("Organisation", "infrastructure"),
        # ha_demo (Scottish) vocabulary
        ("Tenement", "flat"),
        ("Deck access", "flat"),
        ("Multiple Residential Accommodation", "flat"),
        ("Sheltered", "sheltered"),
        ("Mixed Use Building", "mixed_use"),
        ("Main door flat", "flat"),
        # Precedence: specific before general
        ("Semi Detached Bungalow", "bungalow"),
        ("Terraced House", "house"),
        # Unmatched text is classified as other, not None
        ("Windmill", "other"),
    ])
    def test_property_type_mapping(self, property_type, expected):
        assert classify_dwelling_form(property_type) == expected

    def test_no_signal_returns_none(self):
        assert classify_dwelling_form(None) is None
        assert classify_dwelling_form("") is None
        assert classify_dwelling_form("  ", None) is None

    def test_built_form_is_null_only_fallback(self):
        # SoV property_type wins even when built_form disagrees
        assert classify_dwelling_form("Flat", "Semi-Detached") == "flat"
        # built_form only consulted when property_type is empty
        assert classify_dwelling_form(None, "Semi-Detached") == "house"
        assert classify_dwelling_form("", "Mid-Terrace") == "house"


class TestDeriveIsStandalone:
    def test_block_reference_wins(self):
        # even a house grouped by the SoV stays in its block
        assert derive_is_standalone("house", "Anson Avenue 12-26") is False
        assert derive_is_standalone("flat", "02BR") is False

    def test_house_bungalow_without_block_are_standalone(self):
        assert derive_is_standalone("house", None) is True
        assert derive_is_standalone("bungalow", "") is True
        assert derive_is_standalone("house", "   ") is True

    def test_flat_without_block_is_unknown_until_detection(self):
        assert derive_is_standalone("flat", None) is None
        assert derive_is_standalone("maisonette", None) is None
        assert derive_is_standalone(None, None) is None


class TestDeriveFraRequirement:
    def test_standalone_single_household_not_required(self):
        assert derive_fra_requirement("house", True) == "not_required"
        assert derive_fra_requirement("bungalow", True) == "not_required"

    def test_block_dwellings_required(self):
        assert derive_fra_requirement("flat", False) == "required"
        assert derive_fra_requirement("house", False) == "required"
        assert derive_fra_requirement("maisonette", False) == "required"

    def test_sheltered_always_required(self):
        # sheltered housing has common parts even when detached
        assert derive_fra_requirement("sheltered", True) == "required"
        assert derive_fra_requirement("sheltered", False) == "required"

    def test_non_dwellings_not_required(self):
        assert derive_fra_requirement("garage", None) == "not_required"
        assert derive_fra_requirement("commercial", False) == "not_required"

    def test_unknowns(self):
        assert derive_fra_requirement(None, None) == "unknown"
        assert derive_fra_requirement("flat", None) == "unknown"
