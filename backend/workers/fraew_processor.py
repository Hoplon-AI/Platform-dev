"""
backend/workers/fraew_processor.py

Processes Fire Risk Appraisal of External Walls (FRAEW) documents.

Key difference from FRA processor:
  - FRAEW covers EXTERNAL walls using PAS 9980:2022 methodology
  - A single building can have multiple wall types (e.g. EPS render 80%,
    mineral wool render 20%, balconies) — each assessed separately
  - Two professional roles: report writer + fire engineer (Clause 14)
  - Outputs combustible cladding flags critical for insurance underwriting

Two-pass LLM extraction (mirrors fra_processor.py):
  Groq free tier hard limit: 6,000 tokens per request (~18,000 chars)
  Pass 1 → first 18K chars: metadata, building info, fire safety features
  Pass 2 → last 18K chars:  wall types, remedial actions, conclusions
  Merged → single FRAEWExtraction (Pydantic) object → written to DB
"""

import json
import logging
import re
import uuid
from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator, model_validator

from backend.workers.extraction_common import (
    WARN_WEIGHT_DROPPED,
    Citation,
    _date_to_str,
    _to_bool,
    _to_date,
    _to_float,
    _to_str,
    citations_to_json,
    composite_confidence,
    coverage_score,
    ctx_warn,
    make_warning,
    parse_citations,
    verify_citations,
    verify_item_sources,
)

logger = logging.getLogger(__name__)

# Address tokens too generic to use alone in block matching (Strategy 3)
_ADDR_STOP_WORDS = frozenset({
    "road", "street", "avenue", "lane", "way", "close", "drive", "court",
    "house", "block", "flat", "floor", "place", "gardens", "grove", "park",
    "rise", "walk", "terrace", "crescent", "square", "mews", "row",
    "the", "and", "for", "with", "ltd", "limited",
})


# ──────────────────────────────────────────────────────────────────────
# Pydantic models — all coercion happens in validators
# ──────────────────────────────────────────────────────────────────────

RiskLevel = Literal["low", "medium", "high"]

_VALID_INSULATION = ("eps", "mineral_wool", "pir", "phenolic", "unknown")
_VALID_RENDER     = ("cement", "acrylic", "silicone", "unknown")


class WallTypeAssessment(BaseModel):
    """
    PAS 9980 risk assessment for one external wall type.
    Elizabeth Court example: Wall Type 1 (EPS), Wall Type 2 (mineral wool), Balconies.
    """
    type_ref:               str = "Wall Type"
    description:            Optional[str] = None    # "Render to EPS insulation with masonry"
    coverage_percent:       Optional[float] = None  # 80.0 (% of total external wall)

    insulation_type:        Optional[str] = None    # eps | mineral_wool | pir | phenolic | unknown
    insulation_combustible: Optional[bool] = None
    render_type:            Optional[str] = None    # cement | acrylic | silicone | unknown
    render_combustible:     Optional[bool] = None

    # PAS 9980 Step 5 risk scores
    spread_risk:    Optional[RiskLevel] = None
    entry_risk:     Optional[RiskLevel] = None
    occupant_risk:  Optional[RiskLevel] = None
    overall_risk:   Optional[RiskLevel] = None

    remedial_required: bool = False
    remedial_detail:   Optional[str] = None

    @field_validator("type_ref", mode="before")
    @classmethod
    def _norm_type_ref(cls, v: Any) -> str:
        return _to_str(v) or "Wall Type"

    @field_validator("description", "remedial_detail", mode="before")
    @classmethod
    def _clean_str(cls, v: Any) -> Optional[str]:
        return _to_str(v)

    @field_validator("coverage_percent", mode="before")
    @classmethod
    def _norm_coverage(cls, v: Any, info: ValidationInfo) -> Optional[float]:
        if v is None:
            return None
        try:
            pct = float(v)
        except (TypeError, ValueError):
            ctx_warn(info.context, "wall_types.coverage_percent", v, "not a number, nulled")
            return None
        if not 0 <= pct <= 100:
            ctx_warn(info.context, "wall_types.coverage_percent", v, "outside 0-100, nulled")
            return None
        return pct

    @field_validator("insulation_type", mode="before")
    @classmethod
    def _norm_insulation(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        s = _to_str(v)
        if s is None:
            return None
        s = s.lower()
        if s not in _VALID_INSULATION:
            ctx_warn(info.context, "wall_types.insulation_type", v,
                     "not a valid insulation enum, set to unknown")
            return "unknown"
        return s

    @field_validator("render_type", mode="before")
    @classmethod
    def _norm_render(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        s = _to_str(v)
        if s is None:
            return None
        s = s.lower()
        if s not in _VALID_RENDER:
            ctx_warn(info.context, "wall_types.render_type", v,
                     "not a valid render enum, set to unknown")
            return "unknown"
        return s

    @field_validator("spread_risk", "entry_risk", "occupant_risk", "overall_risk", mode="before")
    @classmethod
    def _norm_risk(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        s = _to_str(v)
        if s is None:
            return None
        s = s.lower()
        if s not in ("low", "medium", "high"):
            ctx_warn(info.context, f"wall_types.{info.field_name}", v,
                     "not a valid risk level, nulled")
            return None
        return s

    @field_validator("insulation_combustible", "render_combustible", mode="before")
    @classmethod
    def _norm_bool(cls, v: Any) -> Optional[bool]:
        return _to_bool(v)

    @field_validator("remedial_required", mode="before")
    @classmethod
    def _norm_flag(cls, v: Any) -> bool:
        return bool(_to_bool(v) or False)


class FRAEWRemedialAction(BaseModel):
    """One remedial action on the external wall system."""
    action:      str
    priority:    Literal["advisory", "low", "medium", "high"] = "low"
    due_date:    Optional[date] = None
    responsible: Optional[str] = None
    status:      Literal["outstanding", "completed"] = "outstanding"
    # citation: page the LLM found this action on; verification set by Python
    pg:              Optional[int] = None
    source_verified: Optional[bool] = None
    source_page:     Optional[int] = None

    @field_validator("action", mode="before")
    @classmethod
    def _require_action(cls, v: Any) -> str:
        s = _to_str(v)
        if not s:
            raise ValueError("remedial action text is empty")
        return s

    @field_validator("pg", mode="before")
    @classmethod
    def _pg_to_int(cls, v: Any) -> Optional[int]:
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @field_validator("responsible", mode="before")
    @classmethod
    def _clean_str(cls, v: Any) -> Optional[str]:
        return _to_str(v)

    @field_validator("due_date", mode="before")
    @classmethod
    def _parse_date(cls, v: Any, info: ValidationInfo) -> Optional[date]:
        d = _to_date(v)
        if d is None and _to_str(v) is not None:
            ctx_warn(info.context, "remedial_actions.due_date", v, "unparseable date, nulled")
        return d

    @field_validator("priority", mode="before")
    @classmethod
    def _norm_priority(cls, v: Any) -> str:
        s = (_to_str(v) or "").lower()
        return s if s in ("advisory", "low", "medium", "high") else "low"

    @field_validator("status", mode="before")
    @classmethod
    def _norm_status(cls, v: Any) -> str:
        s = (_to_str(v) or "").lower()
        return "completed" if any(k in s for k in ("complet", "done", "closed", "resolved")) \
            else "outstanding"


class FRAEWExtraction(BaseModel):
    """Validated, normalised output of one FRAEW LLM extraction call."""

    # Report metadata
    report_reference:       Optional[str] = None
    assessment_date:        Optional[date] = None   # site investigation date
    report_date:            Optional[date] = None   # date report issued
    assessment_valid_until: Optional[date] = None

    # Assessor (report writer)
    assessor_name:          Optional[str] = None
    assessor_company:       Optional[str] = None
    assessor_qualification: Optional[str] = None

    # Fire engineer (Clause 14)
    fire_engineer_name:          Optional[str] = None
    fire_engineer_company:       Optional[str] = None
    fire_engineer_qualification: Optional[str] = None
    clause_14_applied:           bool = False

    # Building identity (single-pass prompt only)
    block_reference:  Optional[str] = None
    building_name:    Optional[str] = None
    building_address: Optional[str] = None

    # Building description
    building_height_m:               Optional[float] = None
    building_height_category:        Optional[str]   = None
    num_storeys:                     Optional[int]   = None
    num_units:                       Optional[int]   = None
    build_year:                      Optional[int]   = None
    construction_frame_type:         Optional[str]   = None
    external_wall_base_construction: Optional[str]   = None
    retrofit_year:                   Optional[int]   = None

    # PAS 9980
    pas_9980_version:     str            = "2022"
    pas_9980_compliant:   Optional[bool] = None
    building_risk_rating: Optional[str]  = None     # raw text from document

    # Interim and remedial
    interim_measures_required: bool = False
    interim_measures_detail:   Optional[str] = None
    has_remedial_actions:      bool = False
    remedial_actions:          list[FRAEWRemedialAction] = Field(default_factory=list)

    # Wall types — core FRAEW data
    wall_types: list[WallTypeAssessment] = Field(default_factory=list)

    # Fire safety features
    cavity_barriers_present: Optional[bool] = None
    cavity_barriers_windows: Optional[bool] = None
    cavity_barriers_floors:  Optional[bool] = None
    fire_breaks_floor_level: Optional[bool] = None
    fire_breaks_party_walls: Optional[bool] = None
    dry_riser_present:       Optional[bool] = None
    wet_riser_present:       Optional[bool] = None
    evacuation_strategy:     Optional[str]  = None

    # Compliance
    bs8414_test_evidence: Optional[bool] = None
    br135_criteria_met:   Optional[bool] = None
    adb_compliant:        Optional[str]  = None     # compliant | non_compliant | uncertain | not_applicable

    # Recommended actions
    height_survey_recommended:           bool = False
    fire_door_survey_recommended:        bool = False
    intrusive_investigation_recommended: bool = False
    asbestos_suspected:                  bool = False

    # per-field citations — enriched with verification results in
    # _parse_llm_response (verified/found_page/snippet never trusted from LLM)
    citations:               dict[str, Citation] = Field(default_factory=dict)
    # confidence — extraction_confidence holds the composite after
    # _parse_llm_response; the raw LLM self-report is kept alongside
    extraction_confidence:   float = 0.5
    llm_reported_confidence: Optional[float] = None
    # repair/skip events harvested during validation (never LLM-supplied)
    validation_warnings:     list[dict] = Field(default_factory=list)

    # ── string fields ──────────────────────────────────────────────────
    @field_validator(
        "report_reference", "assessor_name", "assessor_company", "assessor_qualification",
        "fire_engineer_name", "fire_engineer_company", "fire_engineer_qualification",
        "block_reference", "building_name", "building_address",
        "construction_frame_type", "external_wall_base_construction",
        "building_risk_rating", "interim_measures_detail",
        mode="before",
    )
    @classmethod
    def _clean_str(cls, v: Any) -> Optional[str]:
        return _to_str(v)

    # ── date fields ────────────────────────────────────────────────────
    @field_validator("assessment_date", "report_date", "assessment_valid_until", mode="before")
    @classmethod
    def _parse_date(cls, v: Any, info: ValidationInfo) -> Optional[date]:
        d = _to_date(v)
        if d is None and _to_str(v) is not None:
            ctx_warn(info.context, info.field_name, v, "unparseable date, nulled")
        return d

    # ── enums ──────────────────────────────────────────────────────────
    @field_validator("evacuation_strategy", mode="before")
    @classmethod
    def _norm_evac(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        VALID = ("stay_put", "simultaneous", "phased", "temporary_evacuation")
        s = _to_str(v)
        if s is not None and s not in VALID:
            ctx_warn(info.context, "evacuation_strategy", v, "not a valid strategy enum, nulled")
            return None
        return s

    @field_validator("adb_compliant", mode="before")
    @classmethod
    def _norm_adb(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        VALID = ("compliant", "non_compliant", "uncertain", "not_applicable")
        s = _to_str(v)
        if s is None:
            return None
        s = s.lower()
        if s not in VALID:
            ctx_warn(info.context, "adb_compliant", v, "not a valid ADB enum, nulled")
            return None
        return s

    @field_validator("building_height_category", mode="before")
    @classmethod
    def _norm_height_cat(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        VALID = ("under_11m", "11_to_18m", "18_to_30m", "over_30m")
        s = _to_str(v)
        if s is not None and s not in VALID:
            ctx_warn(info.context, "building_height_category", v,
                     "not a valid height category, nulled (re-derived from height if possible)")
            return None
        return s

    @field_validator("pas_9980_version", mode="before")
    @classmethod
    def _norm_pas_version(cls, v: Any) -> str:
        return _to_str(v) or "2022"

    # ── numeric fields ─────────────────────────────────────────────────
    @field_validator("building_height_m", mode="before")
    @classmethod
    def _norm_height(cls, v: Any, info: ValidationInfo) -> Optional[float]:
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            ctx_warn(info.context, "building_height_m", v, "not a number, nulled")
            return None

    @field_validator("num_storeys", "num_units", "build_year", "retrofit_year", mode="before")
    @classmethod
    def _to_int(cls, v: Any, info: ValidationInfo) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            ctx_warn(info.context, info.field_name, v, "not an integer, nulled")
            return None

    # ── Optional[bool] fields ──────────────────────────────────────────
    @field_validator(
        "pas_9980_compliant",
        "cavity_barriers_present", "cavity_barriers_windows", "cavity_barriers_floors",
        "fire_breaks_floor_level", "fire_breaks_party_walls",
        "dry_riser_present", "wet_riser_present",
        "bs8414_test_evidence", "br135_criteria_met",
        mode="before",
    )
    @classmethod
    def _to_optional_bool(cls, v: Any, info: ValidationInfo) -> Optional[bool]:
        b = _to_bool(v)
        if b is None and v is not None:
            ctx_warn(info.context, info.field_name, v, "unrecognised boolean, nulled")
        return b

    # ── required-bool flags ────────────────────────────────────────────
    @field_validator(
        "clause_14_applied", "interim_measures_required", "has_remedial_actions",
        "height_survey_recommended", "fire_door_survey_recommended",
        "intrusive_investigation_recommended", "asbestos_suspected",
        mode="before",
    )
    @classmethod
    def _to_bool_flag(cls, v: Any) -> bool:
        return bool(_to_bool(v) or False)

    # ── confidence clamp ───────────────────────────────────────────────
    @field_validator("extraction_confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v: Any, info: ValidationInfo) -> float:
        try:
            float(v)
        except (TypeError, ValueError):
            ctx_warn(info.context, "extraction_confidence", v,
                     "self-reported confidence unparseable, defaulted to 0.5")
        return _to_float(v, default=0.5)

    # ── citations block ────────────────────────────────────────────────
    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v: Any, info: ValidationInfo) -> dict:
        return parse_citations(v, info.context)

    # ── wall types — validate each; skipped items become warnings ─────
    @field_validator("wall_types", mode="before")
    @classmethod
    def _parse_wall_types(cls, v: Any, info: ValidationInfo) -> list:
        if v is None:
            return []
        if not isinstance(v, list):
            ctx_warn(info.context, "wall_types", type(v).__name__,
                     "not a list, dropped", weight=WARN_WEIGHT_DROPPED)
            return []
        result = []
        for i, wt in enumerate(v):
            if not isinstance(wt, dict):
                ctx_warn(info.context, f"wall_types[{i}]", wt,
                         "not an object, dropped", weight=WARN_WEIGHT_DROPPED)
                continue
            try:
                result.append(WallTypeAssessment.model_validate(wt, context=info.context))
            except ValidationError as exc:
                ctx_warn(info.context, f"wall_types[{i}]", wt.get("type_ref"),
                         f"invalid wall type dropped: {exc.errors()[0].get('msg', 'validation error')}",
                         weight=WARN_WEIGHT_DROPPED)
                logger.warning("Dropped invalid wall type %d: %s", i, exc)
        return result

    # ── remedial actions ───────────────────────────────────────────────
    @field_validator("remedial_actions", mode="before")
    @classmethod
    def _parse_remedials(cls, v: Any, info: ValidationInfo) -> list:
        if v is None:
            return []
        if not isinstance(v, list):
            ctx_warn(info.context, "remedial_actions", type(v).__name__,
                     "not a list, dropped", weight=WARN_WEIGHT_DROPPED)
            return []
        result = []
        for i, item in enumerate(v):
            if not isinstance(item, dict):
                ctx_warn(info.context, f"remedial_actions[{i}]", item,
                         "not an object, dropped", weight=WARN_WEIGHT_DROPPED)
                continue
            try:
                parsed = FRAEWRemedialAction.model_validate(item, context=info.context)
                # never trust verification fields from the LLM
                parsed.source_verified = None
                parsed.source_page = None
                result.append(parsed)
            except ValidationError as exc:
                ctx_warn(info.context, f"remedial_actions[{i}]", item.get("action"),
                         f"invalid remedial action dropped: {exc.errors()[0].get('msg', 'validation error')}",
                         weight=WARN_WEIGHT_DROPPED)
                logger.warning("Dropped invalid remedial action %d: %s", i, exc)
        return result

    # ── derive height category from numeric height when enum missing ──
    @model_validator(mode="after")
    def _derive_height_category_from_height(self):
        if self.building_height_category is None and self.building_height_m is not None:
            h = self.building_height_m
            if h < 11:    self.building_height_category = "under_11m"
            elif h <= 18: self.building_height_category = "11_to_18m"
            elif h <= 30: self.building_height_category = "18_to_30m"
            else:         self.building_height_category = "over_30m"
        return self


# ──────────────────────────────────────────────────────────────────────
# Pass 1: Metadata prompt  (first 18K chars of document)
# ──────────────────────────────────────────────────────────────────────

FRAEW_SINGLE_PASS_PROMPT = """You are an expert UK fire safety engineer specialising in PAS 9980:2022 external wall assessments.
Extract ALL structured data from this Fire Risk Appraisal of External Walls (FRAEW) document.
Return ONLY valid JSON. Use null for missing fields. Dates: YYYY-MM-DD.

This document follows PAS 9980:2022 methodology and may use various risk rating conventions:

━━━ BUILDING RISK RATING ━━━
Extract the EXACT phrase from the Conclusion or Summary section.
Common phrases: "Broadly Acceptable", "Tolerable", "Tolerable but not Acceptable",
"Not Acceptable", "No Further Action Required", "Further Assessment Required",
"High", "Medium", "Low", "Category A", "Category B1", "Category B2", "Category C"

━━━ WALL TYPES ━━━
Extract EVERY distinct wall type or zone assessed. Each may include:
- A type reference (e.g. "Wall Type 1", "Zone A", "Category A", "Balconies")
- Material description (insulation type, render type, cladding)
- PAS 9980 Step 5 risk scores (spread risk, entry risk, occupant risk, overall risk)
- Remedial requirements

Insulation types: eps | mineral_wool | pir | phenolic | unknown
Render types: cement | acrylic | silicone | unknown
  acrylic render → render_combustible = true
  cement render  → render_combustible = false
  EPS/polystyrene → insulation_combustible = true
  Mineral wool   → insulation_combustible = false
Risk levels: low | medium | high

━━━ COMPLIANCE ━━━
  BS 8414 test → bs8414_test_evidence
  BRE 135 criteria → br135_criteria_met
  ADB (Approved Document B) → adb_compliant: compliant | non_compliant | uncertain | not_applicable

━━━ CITATIONS ━━━
The document text contains [Page N] markers. For each field in the "citations" object, cite the evidence:
  pg = the [Page N] number where you found the value
  q  = the FIRST 6-8 WORDS of the source sentence or table row, copied VERBATIM (exact characters)
  c  = your confidence: "H" (stated explicitly) | "M" (inferred from context) | "L" (uncertain)
Omit a field from "citations" when its value is null. Do NOT paraphrase q — it is matched
character-for-character against the document.

Return ONLY this JSON:
{{
  "block_reference": "short block/property code ONLY if explicitly labelled in the document (e.g. 'Property Name: 02BR', 'Block Reference: BLK-A') — null otherwise. Do NOT extract organisation names here.",
  "building_name": "building name or street address — do NOT put a short block code here (use block_reference for codes)",
  "building_address": "full postal address of the building or null",
  "report_reference": "e.g. JL/230504 or null",
  "assessment_date": "YYYY-MM-DD (site investigation date) or null",
  "report_date": "YYYY-MM-DD (date report issued) or null",
  "assessment_valid_until": "YYYY-MM-DD (typically 5 years from report_date) or null",

  "assessor_name": "report writer full name or null",
  "assessor_company": "report writer company or null",
  "assessor_qualification": "e.g. IFE, MRICS, CEng or null",
  "fire_engineer_name": "fire engineer name if Clause 14 used, else null",
  "fire_engineer_company": "fire engineer company or null",
  "fire_engineer_qualification": "fire engineer qualifications or null",
  "clause_14_applied": true or false,

  "building_height_m": height in metres as number or null,
  "building_height_category": "under_11m or 11_to_18m or 18_to_30m or over_30m or null",
  "num_storeys": number or null,
  "num_units": number of residential units or null,
  "build_year": year as number or null,
  "construction_frame_type": "e.g. structural concrete, steel frame, timber frame or null",
  "external_wall_base_construction": "e.g. double masonry cavity wall or null",
  "retrofit_year": year cladding/insulation was added as number or null,

  "pas_9980_version": "2022",
  "pas_9980_compliant": true or false or null,
  "building_risk_rating": "overall conclusion — exact phrase from Conclusion section or null",

  "cavity_barriers_present": true or false or null,
  "cavity_barriers_windows": true or false or null,
  "cavity_barriers_floors": true or false or null,
  "fire_breaks_floor_level": true or false or null,
  "fire_breaks_party_walls": true or false or null,
  "dry_riser_present": true or false or null,
  "wet_riser_present": true or false or null,
  "evacuation_strategy": "stay_put or simultaneous or phased or null",

  "bs8414_test_evidence": true or false or null,
  "br135_criteria_met": true or false or null,
  "adb_compliant": "compliant or non_compliant or uncertain or not_applicable or null",

  "height_survey_recommended": true or false,
  "fire_door_survey_recommended": true or false,
  "intrusive_investigation_recommended": true or false,
  "asbestos_suspected": true or false,

  "interim_measures_required": true or false,
  "interim_measures_detail": "description or null",
  "has_remedial_actions": true or false,
  "remedial_actions": [
    {{
      "action": "what needs to be done — copy the document wording verbatim",
      "priority": "advisory or low or medium or high",
      "due_date": "YYYY-MM-DD or null",
      "responsible": "landlord or contractor or null",
      "status": "outstanding or completed",
      "pg": page number where this action appears
    }}
  ],

  "wall_types": [
    {{
      "type_ref": "e.g. Wall Type 1 or Balconies or Category A",
      "description": "material description or null",
      "coverage_percent": percentage as number or null,
      "insulation_type": "eps or mineral_wool or pir or phenolic or unknown or null",
      "insulation_combustible": true or false or null,
      "render_type": "cement or acrylic or silicone or unknown or null",
      "render_combustible": true or false or null,
      "spread_risk": "low or medium or high or null",
      "entry_risk": "low or medium or high or null",
      "occupant_risk": "low or medium or high or null",
      "overall_risk": "low or medium or high or null",
      "remedial_required": true or false,
      "remedial_detail": "description or null"
    }}
  ],

  "citations": {{
    "building_risk_rating": {{"pg": page number, "q": "first 6-8 words verbatim", "c": "H or M or L"}},
    "assessment_date":      {{"pg": ..., "q": "...", "c": "..."}},
    "report_date":          {{"pg": ..., "q": "...", "c": "..."}},
    "building_height_m":    {{"pg": ..., "q": "...", "c": "..."}},
    "num_storeys":          {{"pg": ..., "q": "...", "c": "..."}},
    "evacuation_strategy":  {{"pg": ..., "q": "...", "c": "..."}},
    "pas_9980_compliant":   {{"pg": ..., "q": "...", "c": "..."}},
    "adb_compliant":        {{"pg": ..., "q": "...", "c": "..."}}
  }},

  "extraction_confidence": 0.0 to 1.0
}}

FULL DOCUMENT:
{{document_text}}"""


FRAEW_METADATA_PROMPT = """Extract metadata from this UK FRAEW (Fire Risk Appraisal of External Walls) document.
Return ONLY valid JSON. Use null for missing fields. Dates: YYYY-MM-DD.

FRAEW documents follow PAS 9980:2022 methodology. The overall risk rating appears
in the Conclusion section (e.g. "Tolerable", "Low", "Medium", "High", "Broadly Acceptable").

Return ONLY this JSON:
{{
  "report_reference": "e.g. JL/230504 or null",
  "assessment_date": "YYYY-MM-DD (site investigation date) or null",
  "report_date": "YYYY-MM-DD (date report issued) or null",
  "assessment_valid_until": "YYYY-MM-DD (typically 5 years from report_date) or null",

  "assessor_name": "report writer full name or null",
  "assessor_company": "report writer company or null",
  "assessor_qualification": "e.g. IFE, MRICS, CEng or null",

  "fire_engineer_name": "fire engineer name if Clause 14 used, else null",
  "fire_engineer_company": "fire engineer company or null",
  "fire_engineer_qualification": "fire engineer qualifications or null",
  "clause_14_applied": true or false,

  "building_height_m": height in metres as number or null,
  "building_height_category": "under_11m or 11_to_18m or 18_to_30m or over_30m or null",
  "num_storeys": number or null,
  "num_units": number of residential units or null,
  "build_year": year as number or null,
  "construction_frame_type": "e.g. structural concrete, steel frame, timber frame or null",
  "external_wall_base_construction": "e.g. double masonry cavity wall or null",
  "retrofit_year": year cladding/insulation was added as number or null,

  "pas_9980_version": "2022",
  "pas_9980_compliant": true or false or null,
  "building_risk_rating": "overall conclusion — exact phrase from Conclusion section or null",

  "cavity_barriers_present": true or false or null,
  "cavity_barriers_windows": true or false or null,
  "cavity_barriers_floors": true or false or null,
  "fire_breaks_floor_level": true or false or null,
  "fire_breaks_party_walls": true or false or null,
  "dry_riser_present": true or false or null,
  "wet_riser_present": true or false or null,
  "evacuation_strategy": "stay_put or simultaneous or phased or null",

  "bs8414_test_evidence": true or false or null,
  "br135_criteria_met": true or false or null,
  "adb_compliant": "compliant or non_compliant or uncertain or not_applicable or null",

  "height_survey_recommended": true or false,
  "fire_door_survey_recommended": true or false,
  "intrusive_investigation_recommended": true or false,
  "asbestos_suspected": true or false,

  "extraction_confidence": 0.0 to 1.0
}}

DOCUMENT EXCERPT:
{{document_text}}"""


# ──────────────────────────────────────────────────────────────────────
# Pass 2: Wall types + remedial prompt  (last 18K chars of document)
# ──────────────────────────────────────────────────────────────────────

FRAEW_WALL_TYPES_PROMPT = """Extract wall type assessments and remedial actions from this UK FRAEW excerpt.
Return ONLY valid JSON. Dates: YYYY-MM-DD or null.

WALL TYPES — extract EVERY distinct wall type described.
Each wall type typically has: a name/ref, description of materials, risk scores, and remedial notes.

Insulation types: eps (expanded polystyrene/EPS) | mineral_wool | pir | phenolic | unknown
Render types: cement | acrylic | silicone | unknown
  - acrylic render → render_combustible = true
  - cement render  → render_combustible = false
  - EPS / polystyrene insulation → insulation_combustible = true
  - Mineral wool insulation → insulation_combustible = false

Risk levels: low | medium | high

OVERALL RISK RATING — look in the Conclusion/Summary section:
  Common phrases: "Tolerable", "Broadly Acceptable", "Low", "Medium", "High",
  "No Further Action Required", "Further Assessment Required"

INTERIM MEASURES — required when building is high risk pending remediation.
  Look for phrases: "interim measures", "waking watch", "enhanced detection", "evacuation strategy change"

REMEDIAL ACTIONS — specific works required on the external wall system.

Return ONLY this JSON:
{{
  "building_risk_rating": "overall conclusion — exact phrase from Conclusion section or null",

  "interim_measures_required": true or false,
  "interim_measures_detail": "description of interim measures or null",
  "has_remedial_actions": true or false,
  "remedial_actions": [
    {{
      "action": "what needs to be done — copy the document wording verbatim",
      "priority": "advisory or low or medium or high",
      "due_date": "YYYY-MM-DD or null",
      "responsible": "landlord or contractor or null",
      "status": "outstanding or completed",
      "pg": page number where this action appears
    }}
  ],

  "wall_types": [
    {{
      "type_ref": "e.g. Wall Type 1 or Balconies",
      "description": "e.g. Render to EPS insulation with masonry or null",
      "coverage_percent": percentage as number or null,
      "insulation_type": "eps or mineral_wool or pir or phenolic or unknown or null",
      "insulation_combustible": true or false or null,
      "render_type": "cement or acrylic or silicone or unknown or null",
      "render_combustible": true or false or null,
      "spread_risk": "low or medium or high or null",
      "entry_risk": "low or medium or high or null",
      "occupant_risk": "low or medium or high or null",
      "overall_risk": "low or medium or high or null",
      "remedial_required": true or false,
      "remedial_detail": "description or null"
    }}
  ],

  "extraction_confidence": 0.0 to 1.0
}}

NOTE: wall_types is the most critical field — extract ALL distinct wall types.
If the same wall type appears in multiple sections, merge into one entry.

DOCUMENT EXCERPT:
{{document_text}}"""


# ──────────────────────────────────────────────────────────────────────
# FRAEWProcessor
# ──────────────────────────────────────────────────────────────────────

class FRAEWProcessor:
    """End-to-end FRAEW processor. Works with any UK FRAEW format."""

    def __init__(self, db_conn, llm_client):
        self.db  = db_conn
        self.llm = llm_client
        self.last_raw_response: Optional[str] = None
        self.last_pass1_response: Optional[str] = None
        self.last_pass2_response: Optional[str] = None

    # ── Public entry point ────────────────────────────────────────────

    async def process(
        self,
        text: str,
        upload_id: str,
        block_id: Optional[str],
        ha_id: str,
        s3_path: str,
    ) -> dict[str, Any]:
        logger.info("FRAEWProcessor.process() block_id=%s ha_id=%s", block_id, ha_id)

        raw_json   = await self._call_llm(text)
        features   = self._parse_llm_response(raw_json, source_text=text)
        rag_status = self._normalise_rag_status(features.building_risk_rating)
        is_in_date      = self._compute_is_in_date(features.assessment_valid_until)
        height_category = self._derive_height_category(features)
        material_flags  = self._derive_material_flags(features.wall_types)

        # Auto-resolve block_id from Pydantic-validated building fields
        if not block_id:
            block_id = await self._resolve_block_id(
                ha_id,
                features.building_name,
                features.building_address,
                features.block_reference,
            )

        logger.info(
            "FRAEWProcessor parsed: risk=%s rag=%s wall_types=%d confidence=%.2f block_id=%s",
            features.building_risk_rating, rag_status,
            len(features.wall_types), features.extraction_confidence, block_id,
        )

        feature_id, fraew_id = await self._write_to_db(
            features=features, rag_status=rag_status, is_in_date=is_in_date,
            height_category=height_category, material_flags=material_flags,
            upload_id=upload_id, block_id=block_id, ha_id=ha_id, s3_path=s3_path,
        )

        logger.info("FRAEWProcessor complete: fraew_id=%s rag=%s", fraew_id, rag_status)
        return {
            "fraew_id":              fraew_id,
            "feature_id":            feature_id,
            "rag_status":            rag_status,
            "extraction_confidence": features.extraction_confidence,
            "wall_types_count":      len(features.wall_types),
        }

    # ── Block auto-detection ─────────────────────────────────────────

    async def _resolve_block_id(
        self,
        ha_id: str,
        building_name: Optional[str],
        building_address: Optional[str],
        block_reference: Optional[str] = None,
    ) -> Optional[str]:
        """
        Four-strategy block resolution:
          0. Exact/substring match on block_reference (LLM-extracted short code,
             e.g. '02BR' from 'Property Name: 02BR' on CDHA FRAEW template)
          1. Exact match on block name using building_name/address candidates
          2. Substring match — block name appears inside candidate (min 4 chars
             required to avoid generic single-word false matches)
          3. Address lookup via silver.properties → block_reference → block_id
             (handles '269 Holmlea Road' → property block_ref '02BR')
             Stop-words filtered; ORDER BY b.name for determinism.
        """
        all_blocks: list | None = None  # lazy-loaded once

        # ── Strategy 0: explicit block_reference from LLM ────────────
        if block_reference and block_reference.strip():
            br = block_reference.strip()
            row = await self.db.fetchrow(
                "SELECT block_id::text FROM silver.blocks WHERE ha_id=$1 AND UPPER(name)=UPPER($2) LIMIT 1",
                ha_id, br,
            )
            if row:
                logger.info(
                    "FRAEWProcessor: resolved block_id=%s (block_reference exact) from %r",
                    row["block_id"], br,
                )
                return row["block_id"]
            # Substring fallback — block name may contain the reference
            all_blocks = await self.db.fetch(
                "SELECT block_id::text, name FROM silver.blocks WHERE ha_id=$1", ha_id
            )
            br_upper = br.upper()
            for b in all_blocks:
                bn = (b["name"] or "").upper()
                if bn and (br_upper in bn or bn in br_upper):
                    logger.info(
                        "FRAEWProcessor: resolved block_id=%s (block_reference substring) block=%r from %r",
                        b["block_id"], b["name"], br,
                    )
                    return b["block_id"]

        candidates = [c.strip() for c in [building_name, building_address] if c and c.strip()]
        if not candidates:
            logger.info("FRAEWProcessor: no building_name/address extracted — block_id stays None")
            return None

        # ── Strategy 1: exact block name match ───────────────────────
        for candidate in candidates:
            row = await self.db.fetchrow(
                "SELECT block_id::text FROM silver.blocks WHERE ha_id=$1 AND UPPER(name)=UPPER($2) LIMIT 1",
                ha_id, candidate,
            )
            if row:
                logger.info(
                    "FRAEWProcessor: resolved block_id=%s (exact name) from %r",
                    row["block_id"], candidate,
                )
                return row["block_id"]

        # ── Strategy 2: substring — block name inside candidate ───────
        if all_blocks is None:
            all_blocks = await self.db.fetch(
                "SELECT block_id::text, name FROM silver.blocks WHERE ha_id=$1", ha_id
            )
        for candidate in candidates:
            cu = candidate.upper()
            for b in all_blocks:
                bn = (b["name"] or "").upper()
                # Require block name ≥ 4 chars — prevents single generic words
                # like "Cathcart" matching across all blocks in the same estate
                if bn and len(bn) >= 4 and (bn in cu or cu in bn):
                    logger.info(
                        "FRAEWProcessor: resolved block_id=%s (substring) block=%r from %r",
                        b["block_id"], b["name"], candidate,
                    )
                    return b["block_id"]

        # ── Strategy 3: address → silver.properties → block_reference ─
        for candidate in candidates:
            tokens = [
                t.strip() for t in re.split(r"[,\s]+", candidate)
                if len(t.strip()) >= 3 and t.strip().lower() not in _ADDR_STOP_WORDS
            ]
            if len(tokens) < 2:
                continue
            for i in range(len(tokens)):
                for j in range(i + 1, len(tokens)):
                    row = await self.db.fetchrow(
                        """
                        SELECT b.block_id::text
                        FROM silver.properties p
                        JOIN silver.blocks b ON b.ha_id = p.ha_id AND UPPER(b.name) = UPPER(p.block_reference)
                        WHERE p.ha_id = $1
                          AND p.block_reference IS NOT NULL
                          AND (
                            (UPPER(p.address) LIKE '%' || UPPER($2) || '%'
                             AND UPPER(p.address) LIKE '%' || UPPER($3) || '%')
                            OR (UPPER(p.postcode) LIKE '%' || UPPER($2) || '%')
                          )
                        ORDER BY b.name
                        LIMIT 1
                        """,
                        ha_id, tokens[i], tokens[j],
                    )
                    if row:
                        logger.info(
                            "FRAEWProcessor: resolved block_id=%s (address lookup) tokens=%r",
                            row["block_id"], [tokens[i], tokens[j]],
                        )
                        return row["block_id"]

        logger.warning("FRAEWProcessor: could not resolve block from candidates %s", candidates)
        return None

    # ── LLM call — two pass ───────────────────────────────────────────

    async def _call_llm(self, text: str) -> str:
        """Single-pass for Gemini/Bedrock. Two-pass fallback for Groq."""
        if self.llm.supports_large_context:
            return await self._call_llm_single_pass(text)
        return await self._call_llm_two_pass(text)

    async def _call_llm_single_pass(self, text: str) -> str:
        """Single LLM call with full document — for Gemini and Bedrock."""
        logger.info("FRAEWProcessor: single-pass extraction (%d chars)", len(text))
        prompt = FRAEW_SINGLE_PASS_PROMPT.replace("{{document_text}}", text)
        try:
            raw = await self.llm.extract(prompt, max_tokens=16384)
            logger.info("Single-pass returned %d chars", len(raw or ""))
        except Exception as exc:
            logger.error("Single-pass failed: %s", exc)
            raise RuntimeError(f"LLM extraction failed (single pass): {exc}") from exc
        self.last_pass1_response = raw
        self.last_pass2_response = None
        self.last_raw_response = raw
        return raw

    async def _call_llm_two_pass(self, text: str) -> str:
        """Two-pass extraction for Groq free tier (6K TPM hard limit)."""
        CHUNK = 18_000
        meta_chunk    = text[:CHUNK]
        actions_chunk = text[-CHUNK:] if len(text) > CHUNK else text

        logger.info(
            "FRAEWProcessor: two-pass LLM — meta=%d chars, wall=%d chars",
            len(meta_chunk), len(actions_chunk),
        )

        meta_prompt = FRAEW_METADATA_PROMPT.replace("{{document_text}}", meta_chunk)
        try:
            meta_raw = await self.llm.extract(meta_prompt)
            logger.info("Pass 1 (metadata) returned %d chars", len(meta_raw or ""))
        except Exception as exc:
            logger.error("Pass 1 (metadata) failed: %s", exc)
            raise RuntimeError(f"LLM extraction failed (metadata pass): {exc}") from exc

        wall_prompt = FRAEW_WALL_TYPES_PROMPT.replace("{{document_text}}", actions_chunk)
        try:
            wall_raw = await self.llm.extract(wall_prompt)
            logger.info("Pass 2 (wall types) returned %d chars", len(wall_raw or ""))
        except Exception as exc:
            logger.error("Pass 2 (wall types) failed: %s", exc)
            raise RuntimeError(f"LLM extraction failed (wall types pass): {exc}") from exc

        self.last_pass1_response = meta_raw
        self.last_pass2_response = wall_raw
        merged = self._merge_passes(meta_raw, wall_raw)
        self.last_raw_response = merged
        return merged

    def _merge_passes(self, meta_raw: str, wall_raw: str) -> str:
        """
        Merge metadata pass + wall types pass into one combined JSON string.

        Strategy:
          - All metadata fields come from pass 1
          - wall_types come from pass 2 (dedicated prompt → more accurate)
          - If pass 2 has no wall_types but pass 1 found some, use pass 1's
          - Deduplicate wall_types by type_ref (pass 2 wins on conflict)
          - building_risk_rating: prefer whichever pass found a non-null value;
            if both found one, prefer pass 2 (from Conclusion section)
          - remedial_actions from pass 2
          - extraction_confidence = min of both passes
        """
        meta = self._extract_json(meta_raw) or {}
        wall = self._extract_json(wall_raw) or {}

        merged = dict(meta)

        # Wall types: deduplicate by type_ref, pass 2 wins on conflict
        meta_walls = meta.get("wall_types") or []
        wall_walls = wall.get("wall_types") or []

        if wall_walls:
            # Build a dict keyed by type_ref from pass 1, then overwrite with pass 2
            wt_map: dict = {}
            for wt in meta_walls:
                ref = (wt.get("type_ref") or "").strip().lower()
                if ref:
                    wt_map[ref] = wt
            for wt in wall_walls:
                ref = (wt.get("type_ref") or "").strip().lower()
                if ref:
                    wt_map[ref] = wt   # pass 2 overwrites
            merged["wall_types"] = list(wt_map.values()) if wt_map else wall_walls
        else:
            merged["wall_types"] = meta_walls

        # Remedial actions from pass 2 (more complete — from conclusion section)
        merged["remedial_actions"]    = wall.get("remedial_actions") or meta.get("remedial_actions") or []
        merged["has_remedial_actions"] = bool(merged["remedial_actions"]) or \
                                         wall.get("has_remedial_actions") or \
                                         meta.get("has_remedial_actions") or False

        # Interim measures from pass 2
        merged["interim_measures_required"] = wall.get("interim_measures_required") or \
                                               meta.get("interim_measures_required") or False
        merged["interim_measures_detail"]   = wall.get("interim_measures_detail") or \
                                               meta.get("interim_measures_detail")

        # building_risk_rating: pass 2 wins (closer to Conclusion section)
        if wall.get("building_risk_rating"):
            merged["building_risk_rating"] = wall["building_risk_rating"]

        # Min confidence — a failed pass must not be masked by a good one
        c1 = float(meta.get("extraction_confidence") or 0.5)
        c2 = float(wall.get("extraction_confidence") or 0.5)
        merged["extraction_confidence"] = round(min(c1, c2), 3)

        logger.info(
            "Merged FRAEW: risk=%s wall_types=%d remedial=%d confidence=%.3f",
            merged.get("building_risk_rating"),
            len(merged["wall_types"]),
            len(merged["remedial_actions"]),
            merged["extraction_confidence"],
        )
        return json.dumps(merged)

    # ── JSON extraction ───────────────────────────────────────────────

    def _extract_json(self, raw: str) -> Optional[dict]:
        """Robust JSON extraction — handles markdown fences and LLM formatting quirks."""
        if not raw:
            return None

        # Strategy 1: strip markdown fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines   = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]).strip()
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        # Strategy 2: outermost { ... } block
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(raw[start:end + 1])
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        # Strategy 3: fix common LLM quirks
        fixed = re.sub(r",\s*([}\]])", r"\1", raw)
        fixed = re.sub(r"\bNone\b", "null", fixed)
        fixed = re.sub(r"\bTrue\b", "true", fixed)
        fixed = re.sub(r"\bFalse\b", "false", fixed)
        start = fixed.find("{")
        end   = fixed.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(fixed[start:end + 1])
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        logger.error("FRAEW JSON parse failed. Raw (500 chars):\n%s", raw[:500])
        return None

    # ── Parse LLM response ────────────────────────────────────────────

    # Fields whose absence almost always means the extraction failed, not
    # that the document is silent — used for the coverage component.
    # (Height/storeys count as one slot: PAS 9980 is height-driven, but
    # documents state one or the other.)
    def _critical_values(self, features: "FRAEWExtraction") -> list:
        return [
            features.building_risk_rating,
            features.assessment_date or features.report_date,
            features.assessor_name,
            features.wall_types,
            features.building_height_m if features.building_height_m is not None
            else features.num_storeys,
        ]

    def _parse_llm_response(self, raw_json: str, source_text: Optional[str] = None) -> FRAEWExtraction:
        data = self._extract_json(raw_json)
        if data is None:
            logger.error("Could not parse FRAEW LLM response")
            empty = FRAEWExtraction(extraction_confidence=0.1)
            empty.validation_warnings = [make_warning(
                "_document", None, "LLM response was not parseable JSON", weight=0.5)]
            return empty

        # These are computed here, never accepted from the LLM
        data.pop("validation_warnings", None)
        data.pop("llm_reported_confidence", None)

        warnings: list[dict] = []
        try:
            features = FRAEWExtraction.model_validate(data, context={"warnings": warnings})
        except ValidationError as exc:
            logger.error("FRAEWExtraction model_validate failed: %s", exc)
            empty = FRAEWExtraction(extraction_confidence=0.1)
            empty.validation_warnings = [make_warning(
                "_document", None, f"model validation failed: {exc.errors()[0].get('msg', '')}",
                weight=0.5)]
            return empty

        # Consistency checks first — their warnings feed per-field citation scores
        warnings.extend(self._consistency_warnings(features))

        # Ground each cited value in the source text; unverifiable quotes
        # and self-reported "L" fields append to warnings
        verify_citations(features.citations, source_text, warnings)
        verify_item_sources(features.remedial_actions, source_text, warnings,
                            "remedial_actions", text_attr="action")

        features.llm_reported_confidence = features.extraction_confidence
        features.validation_warnings = warnings
        coverage = coverage_score(self._critical_values(features))
        features.extraction_confidence = composite_confidence(
            features.llm_reported_confidence, coverage, warnings)

        if warnings:
            logger.warning(
                "FRAEWProcessor: %d validation warning(s): %s",
                len(warnings),
                "; ".join(f"{w['field']}: {w['reason']}" for w in warnings[:10]),
            )
        if features.extraction_confidence < 0.3:
            logger.warning(
                "FRAEWProcessor: low extraction confidence %.2f (self=%.2f coverage=%.2f "
                "warnings=%d risk=%s wall_types=%d)",
                features.extraction_confidence, features.llm_reported_confidence,
                coverage, len(warnings),
                features.building_risk_rating, len(features.wall_types),
            )
        return features

    def _consistency_warnings(self, features: FRAEWExtraction) -> list[dict]:
        """Cross-field sanity checks — each failure is a confidence penalty."""
        out: list[dict] = []
        today = date.today()

        if (features.assessment_date and features.report_date
                and features.assessment_date > features.report_date):
            out.append(make_warning(
                "assessment_date", _date_to_str(features.assessment_date),
                "site investigation after report_date"))
        if (features.report_date and features.assessment_valid_until
                and features.assessment_valid_until < features.report_date):
            out.append(make_warning(
                "assessment_valid_until", _date_to_str(features.assessment_valid_until),
                "before report_date"))
        if features.build_year is not None and not (1600 <= features.build_year <= today.year):
            out.append(make_warning(
                "build_year", features.build_year, "outside plausible range"))
        if (features.retrofit_year is not None and features.build_year is not None
                and features.retrofit_year < features.build_year):
            out.append(make_warning(
                "retrofit_year", features.retrofit_year, "before build_year"))
        if features.building_height_m is not None and not (2 <= features.building_height_m <= 150):
            out.append(make_warning(
                "building_height_m", features.building_height_m, "outside plausible range"))
        if features.num_storeys is not None and not (1 <= features.num_storeys <= 70):
            out.append(make_warning(
                "num_storeys", features.num_storeys, "outside plausible range"))
        coverage_total = sum(
            wt.coverage_percent for wt in features.wall_types
            if wt.coverage_percent is not None
        )
        if coverage_total > 120:
            out.append(make_warning(
                "wall_types.coverage_percent", coverage_total,
                "wall type coverage percentages sum to >120%"))
        return out

    # ── Derived fields ────────────────────────────────────────────────

    def _normalise_rag_status(self, building_risk_rating: Optional[str]) -> Optional[str]:
        """Map PAS 9980 risk rating → GREEN / AMBER / RED."""
        if not building_risk_rating:
            return None
        lower = building_risk_rating.lower().strip()

        if lower in ("n/a", "not assessed", "unknown", "tbc", "tbd", "none", ""):
            return None

        # RED — unacceptable risk
        if "not acceptable" in lower or "unacceptable" in lower:
            return "RED"
        for kw in ("high", "intolerable", "extreme", "critical",
                   "category b2", "category c"):
            if kw in lower:
                return "RED"

        # GREEN — acceptable / no action needed
        if "no further action" in lower or "broadly acceptable" in lower:
            return "GREEN"
        for kw in ("low", "negligible", "category a"):
            if kw in lower:
                return "GREEN"
        if lower == "tolerable":
            return "GREEN"

        # AMBER — tolerable with conditions / further work needed
        if "tolerable but" in lower or "tolerable with" in lower:
            return "AMBER"
        if "further action" in lower or "further assessment" in lower:
            return "AMBER"
        for kw in ("medium", "moderate", "significant", "category b1"):
            if kw in lower:
                return "AMBER"

        logger.warning("FRAEW: unknown risk rating '%s' → defaulting to AMBER", building_risk_rating)
        return "AMBER"

    def _compute_is_in_date(self, valid_until: Optional[date]) -> Optional[bool]:
        if valid_until is None:
            return None
        return valid_until >= date.today()

    def _derive_height_category(self, features: FRAEWExtraction) -> Optional[str]:
        if features.building_height_category:
            valid = ("under_11m", "11_to_18m", "18_to_30m", "over_30m", "unknown")
            if features.building_height_category in valid:
                return features.building_height_category
        if features.building_height_m:
            h = features.building_height_m
            if h < 11:   return "under_11m"
            elif h < 18: return "11_to_18m"
            elif h <= 30:return "18_to_30m"
            else:        return "over_30m"
        return None

    def _derive_material_flags(self, wall_types: list) -> dict[str, Optional[bool]]:
        """
        Derive boolean cladding material flags from wall_types for fast dashboard queries.
        Returns None for each flag when wall_types is empty (unknown, not false).
        """
        if not wall_types:
            return {k: None for k in (
                "has_combustible_cladding", "eps_insulation_present",
                "mineral_wool_insulation_present", "pir_insulation_present",
                "phenolic_insulation_present", "acrylic_render_present",
                "cement_render_present", "aluminium_composite_cladding",
                "hpl_cladding_present", "timber_cladding_present",
            )}

        insulation_types = {wt.insulation_type for wt in wall_types if wt.insulation_type}
        render_types     = {wt.render_type     for wt in wall_types if wt.render_type}

        any_combustible = any(
            (wt.insulation_combustible or wt.render_combustible)
            for wt in wall_types
            if wt.insulation_combustible is not None or wt.render_combustible is not None
        )

        return {
            "has_combustible_cladding":       any_combustible,
            "eps_insulation_present":          "eps"          in insulation_types,
            "mineral_wool_insulation_present": "mineral_wool" in insulation_types,
            "pir_insulation_present":          "pir"          in insulation_types,
            "phenolic_insulation_present":     "phenolic"     in insulation_types,
            "acrylic_render_present":          "acrylic"      in render_types,
            "cement_render_present":           "cement"       in render_types,
            # Not extractable from insulation/render — explicit LLM flags needed
            "aluminium_composite_cladding":    None,
            "hpl_cladding_present":            None,
            "timber_cladding_present":         None,
        }

    # ── Write to DB ───────────────────────────────────────────────────

    async def _write_to_db(
        self,
        features:        FRAEWExtraction,
        rag_status:      Optional[str],
        is_in_date:      Optional[bool],
        height_category: Optional[str],
        material_flags:  dict,
        upload_id:       str,
        block_id:        str,
        ha_id:           str,
        s3_path:         str,
    ) -> tuple:
        feature_id = str(uuid.uuid4())
        fraew_id   = str(uuid.uuid4())
        now        = datetime.utcnow()

        # Pydantic model holds date objects already
        assessment_date_obj = features.assessment_date
        report_date_obj     = features.report_date
        valid_until_obj     = features.assessment_valid_until

        wall_types_json = json.dumps([
            {
                "type_ref":               wt.type_ref,
                "description":            wt.description,
                "coverage_percent":       wt.coverage_percent,
                "insulation_type":        wt.insulation_type,
                "insulation_combustible": wt.insulation_combustible,
                "render_type":            wt.render_type,
                "render_combustible":     wt.render_combustible,
                "spread_risk":            wt.spread_risk,
                "entry_risk":             wt.entry_risk,
                "occupant_risk":          wt.occupant_risk,
                "overall_risk":           wt.overall_risk,
                "remedial_required":      wt.remedial_required,
                "remedial_detail":        wt.remedial_detail,
            }
            for wt in features.wall_types
        ])

        remedial_actions_json = json.dumps([
            {
                "action":          ra.action,
                "priority":        ra.priority,
                "due_date":        _date_to_str(ra.due_date),
                "responsible":     ra.responsible,
                "status":          ra.status,
                "pg":              ra.pg,
                "source_verified": ra.source_verified,
                "source_page":     ra.source_page,
            }
            for ra in features.remedial_actions
        ])

        raw_json = json.dumps({
            "report_reference":     features.report_reference,
            "building_risk_rating": features.building_risk_rating,
            "clause_14_applied":    features.clause_14_applied,
            "bs8414_test_evidence": features.bs8414_test_evidence,
            "adb_compliant":        features.adb_compliant,
            "wall_type_count":      len(features.wall_types),
            # raw LLM self-report — extraction_confidence column holds the composite
            "llm_reported_confidence":  features.llm_reported_confidence,
            "validation_warning_count": len(features.validation_warnings),
        })

        validation_warnings_json = json.dumps(features.validation_warnings)
        citations_json = json.dumps(citations_to_json(features.citations))

        async with self.db.transaction():

            # 1. document_features (matches silver schema from migrations 003 + 011)
            await self.db.execute("""
                INSERT INTO silver.document_features (
                    feature_id, ha_id, upload_id, block_id, document_type,
                    assessment_date, assessor_company, features_json,
                    processed_at, created_at, updated_at
                )
                VALUES ($1, $2, $3::uuid, $4::uuid, 'fraew_document', $5, $6,
                        $7::jsonb, $8, $9, $10)
                ON CONFLICT (feature_id) DO NOTHING
            """,
                feature_id, ha_id, upload_id, block_id,
                assessment_date_obj or report_date_obj,
                features.assessor_company,
                raw_json, now, now, now,
            )

            # 2. fraew_features
            await self.db.execute("""
                INSERT INTO silver.fraew_features (
                    fraew_id, feature_id, block_id, ha_id, upload_id,
                    report_reference, assessment_date, report_date,
                    assessment_valid_until, is_in_date,
                    assessor_name, assessor_company, assessor_qualification,
                    fire_engineer_name, fire_engineer_company, fire_engineer_qualification,
                    clause_14_applied,
                    building_height_m, building_height_category,
                    num_storeys, num_units, build_year,
                    construction_frame_type, external_wall_base_construction, retrofit_year,
                    pas_9980_version, pas_9980_compliant,
                    building_risk_rating, rag_status,
                    interim_measures_required, interim_measures_detail,
                    has_remedial_actions, remedial_actions,
                    wall_types,
                    has_combustible_cladding, eps_insulation_present,
                    mineral_wool_insulation_present, pir_insulation_present,
                    phenolic_insulation_present, acrylic_render_present,
                    cement_render_present, aluminium_composite_cladding,
                    hpl_cladding_present, timber_cladding_present,
                    cavity_barriers_present, cavity_barriers_windows,
                    cavity_barriers_floors, fire_breaks_floor_level,
                    fire_breaks_party_walls, dry_riser_present, wet_riser_present,
                    evacuation_strategy,
                    bs8414_test_evidence, br135_criteria_met, adb_compliant,
                    height_survey_recommended, fire_door_survey_recommended,
                    intrusive_investigation_recommended, asbestos_suspected,
                    extraction_confidence, fraew_features_json, validation_warnings, citations,
                    created_at, updated_at
                )
                VALUES (
                    $1,$2,$3,$4,$5,
                    $6,$7,$8,
                    $9,$10,
                    $11,$12,$13,
                    $14,$15,$16,
                    $17,
                    $18,$19,
                    $20,$21,$22,
                    $23,$24,$25,
                    $26,$27,
                    $28,$29,
                    $30,$31,
                    $32,$33::jsonb,
                    $34::jsonb,
                    $35,$36,
                    $37,$38,
                    $39,$40,
                    $41,$42,
                    $43,$44,
                    $45,$46,
                    $47,$48,
                    $49,$50,$51,
                    $52,
                    $53,$54,$55,
                    $56,$57,
                    $58,$59,
                    $60,$61::jsonb,$62::jsonb,$63::jsonb,
                    $64,$65
                )
            """,
                fraew_id, feature_id, block_id, ha_id, upload_id,
                features.report_reference, assessment_date_obj, report_date_obj,
                valid_until_obj, is_in_date,
                features.assessor_name, features.assessor_company, features.assessor_qualification,
                features.fire_engineer_name, features.fire_engineer_company, features.fire_engineer_qualification,
                features.clause_14_applied,
                features.building_height_m, height_category,
                features.num_storeys, features.num_units, features.build_year,
                features.construction_frame_type, features.external_wall_base_construction, features.retrofit_year,
                features.pas_9980_version, features.pas_9980_compliant,
                features.building_risk_rating, rag_status,
                features.interim_measures_required, features.interim_measures_detail,
                features.has_remedial_actions, remedial_actions_json,
                wall_types_json,
                material_flags["has_combustible_cladding"],
                material_flags["eps_insulation_present"],
                material_flags["mineral_wool_insulation_present"],
                material_flags["pir_insulation_present"],
                material_flags["phenolic_insulation_present"],
                material_flags["acrylic_render_present"],
                material_flags["cement_render_present"],
                material_flags["aluminium_composite_cladding"],
                material_flags["hpl_cladding_present"],
                material_flags["timber_cladding_present"],
                features.cavity_barriers_present,
                features.cavity_barriers_windows,
                features.cavity_barriers_floors,
                features.fire_breaks_floor_level,
                features.fire_breaks_party_walls,
                features.dry_riser_present,
                features.wet_riser_present,
                features.evacuation_strategy,
                features.bs8414_test_evidence,
                features.br135_criteria_met,
                features.adb_compliant,
                features.height_survey_recommended,
                features.fire_door_survey_recommended,
                features.intrusive_investigation_recommended,
                features.asbestos_suspected,
                features.extraction_confidence,
                raw_json, validation_warnings_json, citations_json,
                now, now,
            )

        return feature_id, fraew_id