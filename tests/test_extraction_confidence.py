"""
Tests for validation-warning harvesting and composite extraction confidence
(chunk 1 of the FRA/FRAEW citations+confidence milestone).

Covers:
- extraction_common: coverage_score, composite_confidence, ctx_warn
- FRAProcessor._parse_llm_response: warnings harvested from validators,
  dropped action items, consistency checks, composite score, min-merge
- FRAEWProcessor._parse_llm_response: wall type / remedial validation,
  height category derivation, consistency checks

No DB or LLM required — processors are constructed with db_conn=None and
llm_client=None and only the pure parsing paths are exercised.
"""

import json
from datetime import date, timedelta

from backend.workers.extraction_common import (
    WARN_WEIGHT_DROPPED,
    Citation,
    composite_confidence,
    coverage_score,
    ctx_warn,
    make_warning,
    split_pages,
    verify_citations,
)
from backend.workers.fra_processor import FRAExtraction, FRAProcessor
from backend.workers.fraew_processor import FRAEWExtraction, FRAEWProcessor


def fra_processor() -> FRAProcessor:
    return FRAProcessor(db_conn=None, llm_client=None)


def fraew_processor() -> FRAEWProcessor:
    return FRAEWProcessor(db_conn=None, llm_client=None)


# ──────────────────────────────────────────────────────────────────────
# extraction_common
# ──────────────────────────────────────────────────────────────────────

class TestCoverageScore:
    def test_all_present(self):
        assert coverage_score(["Moderate", date.today(), ["item"]]) == 1.0

    def test_false_counts_as_present(self):
        # has_fire_alarm_system=False is a real answer, not a gap
        assert coverage_score([False, True]) == 1.0

    def test_none_and_empty_count_as_missing(self):
        assert coverage_score([None, "", [], "present"]) == 0.25

    def test_empty_list_of_criticals(self):
        assert coverage_score([]) == 1.0


class TestCompositeConfidence:
    def test_min_of_components(self):
        assert composite_confidence(0.9, 0.5, []) == 0.5
        assert composite_confidence(0.4, 1.0, []) == 0.4

    def test_penalty_applies(self):
        warnings = [make_warning("f", None, "r")] * 4  # 4 × 0.05 = 0.2
        assert composite_confidence(1.0, 1.0, warnings) == 0.8

    def test_penalty_capped(self):
        warnings = [make_warning("f", None, "r", weight=0.1)] * 20  # 2.0 → cap 0.5
        assert composite_confidence(1.0, 1.0, warnings) == 0.5

    def test_ctx_warn_none_context_is_noop(self):
        ctx_warn(None, "f", "raw", "reason")  # must not raise

    def test_make_warning_truncates_raw(self):
        w = make_warning("f", "x" * 500, "r")
        assert len(w["raw"]) == 120


# ──────────────────────────────────────────────────────────────────────
# FRA parsing
# ──────────────────────────────────────────────────────────────────────

def _fra_json(**overrides) -> str:
    """A clean, fully-populated FRA extraction response."""
    base = {
        "risk_rating": "Moderate",
        "fra_assessment_type": "Type 1",
        "assessment_date": "2025-06-01",
        "assessment_valid_until": "2026-06-01",
        "next_review_date": "2026-06-01",
        "assessor_name": "Jane Smith",
        "assessor_company": "FireSafe Ltd",
        "assessor_qualification": "MIFireE",
        "responsible_person": "Cathcart Demo HA",
        "evacuation_strategy": "stay_put",
        "evacuation_strategy_changed": False,
        "evacuation_strategy_notes": None,
        "has_accessibility_needs_noted": False,
        "has_sprinkler_system": False,
        "has_smoke_detection": True,
        "has_fire_alarm_system": True,
        "has_fire_doors": True,
        "has_compartmentation": True,
        "has_emergency_lighting": True,
        "has_fire_extinguishers": False,
        "has_firefighting_shaft": None,
        "has_dry_riser": None,
        "has_wet_riser": None,
        "bsa_2022_applicable": False,
        "accountable_person_noted": False,
        "mandatory_occurrence_noted": False,
        "action_items": [
            {
                "issue_ref": "A1",
                "description": "Replace damaged fire door on level 2",
                "hazard_type": "Means of Escape",
                "priority": "high",
                "due_date": "2025-09-01",
                "status": "outstanding",
                "responsible": "Maintenance",
            }
        ],
        "significant_findings": [
            {"finding": "Compartmentation breach in riser", "location": "Riser 3", "severity": "high"}
        ],
        "extraction_confidence": 0.9,
    }
    base.update(overrides)
    return json.dumps(base)


class TestFRAParsing:
    def test_clean_document_no_warnings(self):
        f = fra_processor()._parse_llm_response(_fra_json())
        assert f.validation_warnings == []
        assert f.llm_reported_confidence == 0.9
        # coverage 1.0, no penalty → composite = self-report
        assert f.extraction_confidence == 0.9
        assert f.action_items[0].priority == "high"

    def test_invalid_evac_enum_warned_and_nulled(self):
        f = fra_processor()._parse_llm_response(
            _fra_json(evacuation_strategy="defend in place"))
        assert f.evacuation_strategy is None
        assert any(w["field"] == "evacuation_strategy" for w in f.validation_warnings)
        # coverage drops (evac now missing) AND penalty applies
        assert f.extraction_confidence < 0.9

    def test_unparseable_date_warned(self):
        f = fra_processor()._parse_llm_response(
            _fra_json(assessment_date="sometime in spring"))
        assert f.assessment_date is None
        assert any(w["field"] == "assessment_date" for w in f.validation_warnings)

    def test_null_date_not_warned(self):
        f = fra_processor()._parse_llm_response(_fra_json(assessment_date=None))
        assert not any(w["field"] == "assessment_date" for w in f.validation_warnings)

    def test_dropped_action_item_warned_with_heavier_weight(self):
        items = [
            {"description": "Valid action", "priority": "low"},
            {"description": "", "priority": "high"},  # empty description → dropped
        ]
        f = fra_processor()._parse_llm_response(_fra_json(action_items=items))
        assert len(f.action_items) == 1
        dropped = [w for w in f.validation_warnings if w["field"].startswith("action_items[")]
        assert len(dropped) == 1
        assert dropped[0]["weight"] == WARN_WEIGHT_DROPPED

    def test_consistency_review_before_assessment(self):
        f = fra_processor()._parse_llm_response(_fra_json(
            assessment_date="2025-06-01", next_review_date="2024-01-01"))
        assert any(w["field"] == "next_review_date" for w in f.validation_warnings)

    def test_consistency_build_year_out_of_range(self):
        f = fra_processor()._parse_llm_response(_fra_json(build_year=1005))
        assert any(w["field"] == "build_year" for w in f.validation_warnings)

    def test_coverage_floors_confidence(self):
        # High self-report but critical fields missing → coverage is the ceiling
        f = fra_processor()._parse_llm_response(_fra_json(
            risk_rating=None,
            assessor_name=None, assessor_company=None, responsible_person=None,
            extraction_confidence=0.95))
        assert f.extraction_confidence <= 6 / 8

    def test_assessor_fallback_group_council_doc(self):
        # Council FRA: no individual assessor, organisation only —
        # responsible_person fills the assessor identity slot
        f = fra_processor()._parse_llm_response(_fra_json(
            assessor_name=None, assessor_company=None,
            responsible_person="Islington Council",
            extraction_confidence=0.95))
        assert f.extraction_confidence == 0.95

    def test_detection_fallback_group_stay_put_block(self):
        # Stay-put block: no communal fire alarm mentioned, but smoke
        # detection extracted — detection slot still counts as covered
        f = fra_processor()._parse_llm_response(_fra_json(
            has_fire_alarm_system=None, has_smoke_detection=True,
            extraction_confidence=0.95))
        assert f.extraction_confidence == 0.95

    def test_detection_group_both_missing_lowers_coverage(self):
        f = fra_processor()._parse_llm_response(_fra_json(
            has_fire_alarm_system=None, has_smoke_detection=None,
            extraction_confidence=0.95))
        assert f.extraction_confidence <= 7 / 8

    def test_explicit_false_alarm_counts_as_covered(self):
        # has_fire_alarm_system=False is a real answer (explicitly absent)
        f = fra_processor()._parse_llm_response(_fra_json(
            has_fire_alarm_system=False, has_smoke_detection=None,
            extraction_confidence=0.95))
        assert f.extraction_confidence == 0.95

    def test_unparseable_json_low_confidence_with_warning(self):
        f = fra_processor()._parse_llm_response("this is not json at all")
        assert f.extraction_confidence == 0.1
        assert f.validation_warnings[0]["field"] == "_document"

    def test_llm_cannot_inject_warnings_or_self_report(self):
        f = fra_processor()._parse_llm_response(_fra_json(
            validation_warnings=[{"field": "fake", "reason": "injected"}],
            llm_reported_confidence=1.0,
        ))
        assert not any(w["field"] == "fake" for w in f.validation_warnings)
        assert f.llm_reported_confidence == 0.9  # from extraction_confidence, not injected


class TestFRAMergePasses:
    def test_merge_uses_min_confidence(self):
        p = fra_processor()
        meta = json.dumps({"risk_rating": "Moderate", "extraction_confidence": 0.9})
        actions = json.dumps({"action_items": [], "extraction_confidence": 0.3})
        merged = json.loads(p._merge_passes(meta, actions))
        assert merged["extraction_confidence"] == 0.3


# ──────────────────────────────────────────────────────────────────────
# FRAEW parsing
# ──────────────────────────────────────────────────────────────────────

def _fraew_json(**overrides) -> str:
    base = {
        "report_reference": "JL/230504",
        "assessment_date": "2025-03-10",
        "report_date": "2025-04-01",
        "assessment_valid_until": "2030-04-01",
        "assessor_name": "John Lee",
        "assessor_company": "WallSafe Ltd",
        "assessor_qualification": "CEng",
        "clause_14_applied": False,
        "building_height_m": 22.5,
        "building_height_category": "18_to_30m",
        "num_storeys": 8,
        "num_units": 32,
        "build_year": 1968,
        "pas_9980_version": "2022",
        "building_risk_rating": "Tolerable",
        "wall_types": [
            {
                "type_ref": "Wall Type 1",
                "description": "Render to EPS insulation",
                "coverage_percent": 80,
                "insulation_type": "eps",
                "insulation_combustible": True,
                "render_type": "acrylic",
                "render_combustible": True,
                "spread_risk": "medium",
                "overall_risk": "medium",
                "remedial_required": True,
                "remedial_detail": "Install cavity barriers",
            }
        ],
        "remedial_actions": [
            {"action": "Install cavity barriers at floor level", "priority": "high",
             "due_date": "2026-01-01", "responsible": "landlord", "status": "outstanding"}
        ],
        "has_remedial_actions": True,
        "evacuation_strategy": "stay_put",
        "extraction_confidence": 0.85,
    }
    base.update(overrides)
    return json.dumps(base)


class TestFRAEWParsing:
    def test_clean_document_no_warnings(self):
        f = fraew_processor()._parse_llm_response(_fraew_json())
        assert f.validation_warnings == []
        assert f.llm_reported_confidence == 0.85
        assert f.extraction_confidence == 0.85
        assert f.assessment_date == date(2025, 3, 10)  # date object now
        assert f.wall_types[0].insulation_type == "eps"
        assert f.remedial_actions[0].priority == "high"

    def test_invalid_insulation_becomes_unknown_with_warning(self):
        f = fraew_processor()._parse_llm_response(_fraew_json(wall_types=[
            {"type_ref": "Wall Type 1", "insulation_type": "polyurethane foam"}
        ]))
        assert f.wall_types[0].insulation_type == "unknown"
        assert any(w["field"] == "wall_types.insulation_type" for w in f.validation_warnings)

    def test_invalid_risk_level_nulled_with_warning(self):
        f = fraew_processor()._parse_llm_response(_fraew_json(wall_types=[
            {"type_ref": "Wall Type 1", "overall_risk": "severe"}
        ]))
        assert f.wall_types[0].overall_risk is None
        assert any(w["field"] == "wall_types.overall_risk" for w in f.validation_warnings)

    def test_remedial_action_without_text_dropped(self):
        f = fraew_processor()._parse_llm_response(_fraew_json(remedial_actions=[
            {"action": "Real action", "priority": "low"},
            {"action": None, "priority": "high"},
        ]))
        assert len(f.remedial_actions) == 1
        dropped = [w for w in f.validation_warnings if w["field"].startswith("remedial_actions[")]
        assert dropped and dropped[0]["weight"] == WARN_WEIGHT_DROPPED

    def test_height_category_derived_from_height(self):
        f = fraew_processor()._parse_llm_response(_fraew_json(
            building_height_category="over_18m",  # invalid enum → warned, then re-derived
            building_height_m=25.0))
        assert f.building_height_category == "18_to_30m"
        assert any(w["field"] == "building_height_category" for w in f.validation_warnings)

    def test_consistency_investigation_after_report(self):
        f = fraew_processor()._parse_llm_response(_fraew_json(
            assessment_date="2025-06-01", report_date="2025-04-01"))
        assert any(w["field"] == "assessment_date" for w in f.validation_warnings)

    def test_consistency_coverage_sum(self):
        f = fraew_processor()._parse_llm_response(_fraew_json(wall_types=[
            {"type_ref": "WT1", "coverage_percent": 80},
            {"type_ref": "WT2", "coverage_percent": 70},
        ]))
        assert any(w["field"] == "wall_types.coverage_percent" for w in f.validation_warnings)

    def test_unparseable_json_low_confidence(self):
        f = fraew_processor()._parse_llm_response("garbage")
        assert f.extraction_confidence == 0.1
        assert f.validation_warnings[0]["field"] == "_document"

    def test_merge_uses_min_confidence(self):
        p = fraew_processor()
        meta = json.dumps({"building_risk_rating": "Tolerable", "extraction_confidence": 0.9})
        wall = json.dumps({"wall_types": [], "extraction_confidence": 0.2})
        merged = json.loads(p._merge_passes(meta, wall))
        assert merged["extraction_confidence"] == 0.2

    def test_is_in_date_accepts_date_object(self):
        p = fraew_processor()
        assert p._compute_is_in_date(date.today() + timedelta(days=1)) is True
        assert p._compute_is_in_date(date.today() - timedelta(days=1)) is False
        assert p._compute_is_in_date(None) is None


# ──────────────────────────────────────────────────────────────────────
# Citations
# ──────────────────────────────────────────────────────────────────────

SOURCE = """[Page 1]
Fire Risk Assessment for Holmlea Court.
The assessment was carried out on 18 June 2024 by Jane Smith.

[Page 2]
Overall Risk Rating
The overall risk rating for this premises is considered to be Moderate.
A stay put evacuation policy is in place for all residents.

[Page 3]
Action Plan
1 | Replace damaged fire door on level 2 | High | 01/09/2024
"""


class TestSplitPages:
    def test_splits_on_markers(self):
        pages = split_pages(SOURCE)
        assert set(pages) == {1, 2, 3}
        assert "Holmlea Court" in pages[1]
        assert "Moderate" in pages[2]

    def test_empty_text(self):
        assert split_pages("") == {}
        assert split_pages("no markers here") == {}


class TestVerifyCitations:
    def _verify(self, cite_kwargs) -> tuple[Citation, list]:
        cite = Citation(**cite_kwargs)
        warnings: list = []
        verify_citations({"risk_rating": cite}, SOURCE, warnings)
        return cite, warnings

    def test_exact_match_verified_with_snippet(self):
        cite, warnings = self._verify(
            {"pg": 2, "q": "The overall risk rating for this", "c": "H"})
        assert cite.verified is True
        assert cite.found_page == 2
        assert "moderate" in cite.snippet.lower()
        assert warnings == []

    def test_fuzzy_match_tolerates_small_typo(self):
        cite, warnings = self._verify(
            {"pg": 2, "q": "The overal risk rating for this", "c": "H"})  # typo
        assert cite.verified is True
        assert warnings == []

    def test_off_by_one_page_still_found(self):
        cite, warnings = self._verify(
            {"pg": 3, "q": "The overall risk rating for this", "c": "H"})
        assert cite.verified is True
        assert cite.found_page == 2
        assert warnings == []

    def test_wrong_page_far_away_found_by_full_scan(self):
        cite = Citation(pg=1, q="Replace damaged fire door", c="H")
        warnings: list = []
        verify_citations({"f": cite}, SOURCE, warnings)
        assert cite.verified is True
        assert cite.found_page == 3

    def test_fabricated_quote_flagged_as_hallucination(self):
        cite, warnings = self._verify(
            {"pg": 2, "q": "the building is fully sprinklered throughout", "c": "H"})
        assert cite.verified is False
        assert any("hallucination" in w["reason"] for w in warnings)

    def test_low_confidence_c_produces_warning(self):
        cite, warnings = self._verify(
            {"pg": 2, "q": "The overall risk rating for this", "c": "L"})
        assert cite.verified is True  # verifiable, but model unsure
        assert any("LOW confidence" in w["reason"] for w in warnings)

    def test_no_source_text_skips_verification(self):
        cite = Citation(pg=2, q="The overall risk rating for this", c="H")
        warnings: list = []
        verify_citations({"risk_rating": cite}, None, warnings)
        assert cite.verified is None
        assert warnings == []


class TestFieldScore:
    def _score(self, cite_kwargs, warnings=None):
        cite = Citation(**cite_kwargs)
        verify_citations({"risk_rating": cite}, SOURCE, warnings if warnings is not None else [])
        return cite.score

    def test_verified_high_scores_full(self):
        assert self._score({"pg": 2, "q": "The overall risk rating for this", "c": "H"}) == 1.0

    def test_verified_medium_above_threshold(self):
        s = self._score({"pg": 2, "q": "The overall risk rating for this", "c": "M"})
        assert s == 0.75  # above the 0.7 review threshold

    def test_low_self_report_is_low_even_when_verified(self):
        s = self._score({"pg": 2, "q": "The overall risk rating for this", "c": "L"})
        assert s == 0.45
        assert s < 0.7

    def test_hallucinated_citation_capped(self):
        s = self._score({"pg": 2, "q": "totally invented quote about sprinkler coverage", "c": "H"})
        assert s <= 0.3

    def test_validator_warning_on_field_lowers_score(self):
        pre = [make_warning("risk_rating", "raw", "some repair")]
        s = self._score({"pg": 2, "q": "The overall risk rating for this", "c": "H"}, warnings=pre)
        assert s == 0.8  # 1.0 - 0.2

    def test_score_persisted_through_parse(self):
        raw = _fra_json(citations={
            "risk_rating": {"pg": 2, "q": "The overall risk rating for this", "c": "H"},
            "assessment_date": {"pg": 1, "q": "The assessment was carried out on", "c": "L"},
        })
        f = fra_processor()._parse_llm_response(raw, source_text=SOURCE)
        assert f.citations["risk_rating"].score == 1.0
        assert f.citations["assessment_date"].score is not None
        assert f.citations["assessment_date"].score < 0.7


class TestFRACitationsIntegration:
    def test_verified_citation_no_penalty(self):
        raw = _fra_json(citations={
            "risk_rating": {"pg": 2, "q": "The overall risk rating for this", "c": "H"},
        })
        f = fra_processor()._parse_llm_response(raw, source_text=SOURCE)
        assert f.citations["risk_rating"].verified is True
        assert f.citations["risk_rating"].snippet
        assert f.extraction_confidence == 0.9  # unchanged

    def test_hallucinated_citation_lowers_confidence(self):
        raw = _fra_json(citations={
            "risk_rating": {"pg": 2, "q": "completely invented quote about nothing real", "c": "H"},
        })
        f = fra_processor()._parse_llm_response(raw, source_text=SOURCE)
        assert f.citations["risk_rating"].verified is False
        assert any(w["field"] == "risk_rating.citation" for w in f.validation_warnings)
        assert f.extraction_confidence < 0.9

    def test_llm_cannot_preverify_its_own_citation(self):
        raw = _fra_json(citations={
            "risk_rating": {"pg": 2, "q": "invented quote xyz", "c": "H",
                            "verified": True, "snippet": "fake snippet"},
        })
        f = fra_processor()._parse_llm_response(raw, source_text=SOURCE)
        assert f.citations["risk_rating"].verified is False  # re-verified by Python

    def test_malformed_citations_block_ignored(self):
        raw = _fra_json(citations="not a dict")
        f = fra_processor()._parse_llm_response(raw, source_text=SOURCE)
        assert f.citations == {}

    def test_no_citations_block_no_penalty(self):
        # two-pass (Groq) prompts don't request citations — absence is not an error
        f = fra_processor()._parse_llm_response(_fra_json(), source_text=SOURCE)
        assert f.citations == {}
        assert f.extraction_confidence == 0.9


class TestItemSourceVerification:
    def test_action_item_verified_on_cited_page(self):
        items = [{"description": "Replace damaged fire door on level two",
                  "priority": "high", "pg": 3}]
        # SOURCE page 3 contains "Replace damaged fire door"
        raw = _fra_json(action_items=items)
        f = fra_processor()._parse_llm_response(raw, source_text=SOURCE.replace(
            "Replace damaged fire door", "Replace damaged fire door on level two"))
        a = f.action_items[0]
        assert a.source_verified is True
        assert a.source_page == 3

    def test_fabricated_action_item_flagged(self):
        items = [{"description": "Install a brand new sprinkler system in the basement car park",
                  "priority": "high", "pg": 2}]
        f = fra_processor()._parse_llm_response(_fra_json(action_items=items),
                                                source_text=SOURCE)
        a = f.action_items[0]
        assert a.source_verified is False
        assert any(w["field"] == "action_items[0]" and "hallucination" in w["reason"]
                   for w in f.validation_warnings)
        assert f.extraction_confidence < 0.9

    def test_llm_cannot_preverify_action_item(self):
        items = [{"description": "Totally invented action nobody ever wrote down here",
                  "priority": "low", "pg": 1, "source_verified": True, "source_page": 1}]
        f = fra_processor()._parse_llm_response(_fra_json(action_items=items),
                                                source_text=SOURCE)
        assert f.action_items[0].source_verified is False

    def test_no_source_text_leaves_verification_unset(self):
        items = [{"description": "Replace damaged fire door immediately", "pg": 3}]
        f = fra_processor()._parse_llm_response(_fra_json(action_items=items))
        assert f.action_items[0].source_verified is None

    def test_fraew_remedial_action_verified(self):
        source = "[Page 1]\nConclusion.\n\n[Page 2]\nInstall cavity barriers at floor level within 12 months."
        f = fraew_processor()._parse_llm_response(_fraew_json(remedial_actions=[
            {"action": "Install cavity barriers at floor level within", "priority": "high", "pg": 2},
        ]), source_text=source)
        ra = f.remedial_actions[0]
        assert ra.source_verified is True
        assert ra.source_page == 2

    def test_fraew_fabricated_remedial_flagged(self):
        source = "[Page 1]\nConclusion: no remedial works are required for this building."
        f = fraew_processor()._parse_llm_response(_fraew_json(remedial_actions=[
            {"action": "Remove and replace all ACM cladding panels immediately", "priority": "high", "pg": 1},
        ]), source_text=source)
        assert f.remedial_actions[0].source_verified is False
        assert any("hallucination" in w["reason"] for w in f.validation_warnings)
