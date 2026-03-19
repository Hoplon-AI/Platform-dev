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
  Merged → single FRAEWExtractedFeatures object → written to DB
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _to_date(value) -> Optional[date]:
    """Convert YYYY-MM-DD string (or date/None) to date object for asyncpg."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() in ("null", "n/a", "unknown", "tbc", "tbd", "none"):
            return None
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            logger.warning("Could not parse date: %r", value)
    return None


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class WallTypeAssessment:
    """
    PAS 9980 risk assessment for one external wall type.
    Elizabeth Court example: Wall Type 1 (EPS), Wall Type 2 (mineral wool), Balconies.
    """
    type_ref:               str                 # "Wall Type 1", "Balconies", etc.
    description:            Optional[str]        # "Render to EPS insulation with masonry"
    coverage_percent:       Optional[float]      # 80.0 (% of total external wall)

    insulation_type:        Optional[str]        # eps | mineral_wool | pir | phenolic | unknown
    insulation_combustible: Optional[bool]
    render_type:            Optional[str]        # cement | acrylic | silicone | unknown
    render_combustible:     Optional[bool]

    # PAS 9980 Step 5 risk scores
    spread_risk:    Optional[str]                # low | medium | high
    entry_risk:     Optional[str]                # low | medium | high
    occupant_risk:  Optional[str]                # low | medium | high
    overall_risk:   Optional[str]                # low | medium | high

    remedial_required: bool = False
    remedial_detail:   Optional[str] = None


@dataclass
class FRAEWExtractedFeatures:
    # Report metadata
    report_reference:       Optional[str]
    assessment_date:        Optional[str]       # site investigation date
    report_date:            Optional[str]       # date report issued
    assessment_valid_until: Optional[str]

    # Assessor (report writer)
    assessor_name:          Optional[str]
    assessor_company:       Optional[str]
    assessor_qualification: Optional[str]

    # Fire engineer (Clause 14)
    fire_engineer_name:           Optional[str]
    fire_engineer_company:        Optional[str]
    fire_engineer_qualification:  Optional[str]
    clause_14_applied:            bool = False

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
    pas_9980_version:    str           = "2022"
    pas_9980_compliant:  Optional[bool] = None
    building_risk_rating: Optional[str] = None      # raw text from document

    # Interim and remedial
    interim_measures_required: bool = False
    interim_measures_detail:   Optional[str] = None
    has_remedial_actions:      bool = False
    remedial_actions:          list = field(default_factory=list)

    # Wall types — core FRAEW data
    wall_types: list = field(default_factory=list)  # list[WallTypeAssessment]

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
    adb_compliant:        Optional[str]  = None     # compliant | non_compliant | uncertain

    # Recommended actions
    height_survey_recommended:           bool = False
    fire_door_survey_recommended:        bool = False
    intrusive_investigation_recommended: bool = False
    asbestos_suspected:                  bool = False

    extraction_confidence: float = 0.5


# ──────────────────────────────────────────────────────────────────────
# Pass 1: Metadata prompt  (first 18K chars of document)
# ──────────────────────────────────────────────────────────────────────

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
      "action": "what needs to be done",
      "priority": "advisory or low or medium or high",
      "due_date": "YYYY-MM-DD or null",
      "responsible": "landlord or contractor or null",
      "status": "outstanding or completed"
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

    # ── Public entry point ────────────────────────────────────────────

    async def process(
        self,
        text: str,
        upload_id: str,
        block_id: str,
        ha_id: str,
        s3_path: str,
    ) -> dict[str, Any]:
        logger.info("FRAEWProcessor.process() block_id=%s ha_id=%s", block_id, ha_id)

        raw_json        = await self._call_llm(text)
        features        = self._parse_llm_response(raw_json)
        rag_status      = self._normalise_rag_status(features.building_risk_rating)
        is_in_date      = self._compute_is_in_date(features.assessment_valid_until)
        height_category = self._derive_height_category(features)
        material_flags  = self._derive_material_flags(features.wall_types)

        logger.info(
            "FRAEWProcessor parsed: risk=%s rag=%s wall_types=%d confidence=%.2f",
            features.building_risk_rating, rag_status,
            len(features.wall_types), features.extraction_confidence,
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

    # ── LLM call — two pass ───────────────────────────────────────────

    async def _call_llm(self, text: str) -> str:
        """
        Two-pass extraction to stay within Groq free tier TPM limits.

        Groq free tier hard limit: 6,000 tokens per request.
        At ~4 chars/token, max safe document chunk = ~18,000 chars.

        Pass 1 — first 18K chars + metadata prompt
          → Extracts: report metadata, building description, fire safety
            features, overall risk rating, compliance fields

        Pass 2 — last 18K chars + wall types prompt
          → Extracts: ALL wall type assessments + remedial actions
          → Uses the END of the document because FRAEW conclusions
            and full wall type tables typically appear in the latter half.

        Results are merged: metadata from pass 1, wall_types/remedial
        from pass 2 (with deduplication if both passes found wall types).
        """
        CHUNK = 18_000

        meta_chunk    = text[:CHUNK]
        actions_chunk = text[-CHUNK:] if len(text) > CHUNK else text

        logger.info(
            "FRAEWProcessor: two-pass LLM — "
            "meta_chunk=%d chars (0-%d), wall_chunk=%d chars (%d-%d)",
            len(meta_chunk), len(meta_chunk),
            len(actions_chunk), max(0, len(text) - CHUNK), len(text),
        )

        # Pass 1: metadata
        meta_prompt = FRAEW_METADATA_PROMPT.replace("{document_text}", meta_chunk)
        try:
            meta_raw = await self.llm.extract(meta_prompt)
            logger.info("Pass 1 (metadata) returned %d chars", len(meta_raw or ""))
        except Exception as exc:
            logger.error("Pass 1 (metadata) failed: %s", exc)
            raise RuntimeError(f"LLM extraction failed (metadata pass): {exc}") from exc

        # Pass 2: wall types + remedial
        wall_prompt = FRAEW_WALL_TYPES_PROMPT.replace("{document_text}", actions_chunk)
        try:
            wall_raw = await self.llm.extract(wall_prompt)
            logger.info("Pass 2 (wall types) returned %d chars", len(wall_raw or ""))
        except Exception as exc:
            logger.error("Pass 2 (wall types) failed: %s", exc)
            raise RuntimeError(f"LLM extraction failed (wall types pass): {exc}") from exc

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
          - extraction_confidence = average of both passes
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

        # Average confidence
        c1 = float(meta.get("extraction_confidence") or 0.5)
        c2 = float(wall.get("extraction_confidence") or 0.5)
        merged["extraction_confidence"] = round((c1 + c2) / 2, 3)

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

    def _parse_llm_response(self, raw_json: str) -> FRAEWExtractedFeatures:
        data = self._extract_json(raw_json)
        if data is None:
            logger.error("Could not parse FRAEW LLM response")
            return self._empty_features(confidence=0.1)

        # Parse wall types
        VALID_INSULATION = ("eps", "mineral_wool", "pir", "phenolic", "unknown")
        VALID_RISK       = ("low", "medium", "high")

        wall_types = []
        for wt in data.get("wall_types") or []:
            if not isinstance(wt, dict):
                continue
            insulation = wt.get("insulation_type")
            if insulation not in VALID_INSULATION:
                insulation = "unknown" if insulation else None

            wall_types.append(WallTypeAssessment(
                type_ref               = wt.get("type_ref", "Wall Type"),
                description            = wt.get("description"),
                coverage_percent       = wt.get("coverage_percent"),
                insulation_type        = insulation,
                insulation_combustible = wt.get("insulation_combustible"),
                render_type            = wt.get("render_type"),
                render_combustible     = wt.get("render_combustible"),
                spread_risk   = wt.get("spread_risk")   if wt.get("spread_risk")   in VALID_RISK else None,
                entry_risk    = wt.get("entry_risk")    if wt.get("entry_risk")    in VALID_RISK else None,
                occupant_risk = wt.get("occupant_risk") if wt.get("occupant_risk") in VALID_RISK else None,
                overall_risk  = wt.get("overall_risk")  if wt.get("overall_risk")  in VALID_RISK else None,
                remedial_required = bool(wt.get("remedial_required", False)),
                remedial_detail   = wt.get("remedial_detail"),
            ))

        # Validate enums
        evac = data.get("evacuation_strategy")
        if evac not in ("stay_put", "simultaneous", "phased", "temporary_evacuation"):
            evac = None

        adb = data.get("adb_compliant")
        if adb not in ("compliant", "non_compliant", "uncertain", "not_applicable"):
            adb = None

        height_cat = data.get("building_height_category")
        if height_cat not in ("under_11m", "11_to_18m", "18_to_30m", "over_30m", "unknown"):
            height_cat = None

        return FRAEWExtractedFeatures(
            report_reference        = data.get("report_reference"),
            assessment_date         = data.get("assessment_date"),
            report_date             = data.get("report_date"),
            assessment_valid_until  = data.get("assessment_valid_until"),
            assessor_name           = data.get("assessor_name"),
            assessor_company        = data.get("assessor_company"),
            assessor_qualification  = data.get("assessor_qualification"),
            fire_engineer_name      = data.get("fire_engineer_name"),
            fire_engineer_company   = data.get("fire_engineer_company"),
            fire_engineer_qualification = data.get("fire_engineer_qualification"),
            clause_14_applied       = bool(data.get("clause_14_applied", False)),
            building_height_m       = data.get("building_height_m"),
            building_height_category= height_cat,
            num_storeys             = data.get("num_storeys"),
            num_units               = data.get("num_units"),
            build_year              = data.get("build_year"),
            construction_frame_type = data.get("construction_frame_type"),
            external_wall_base_construction = data.get("external_wall_base_construction"),
            retrofit_year           = data.get("retrofit_year"),
            pas_9980_version        = data.get("pas_9980_version", "2022"),
            pas_9980_compliant      = data.get("pas_9980_compliant"),
            building_risk_rating    = data.get("building_risk_rating"),
            interim_measures_required = bool(data.get("interim_measures_required", False)),
            interim_measures_detail = data.get("interim_measures_detail"),
            has_remedial_actions    = bool(data.get("has_remedial_actions", False)),
            remedial_actions        = data.get("remedial_actions") or [],
            wall_types              = wall_types,
            cavity_barriers_present = data.get("cavity_barriers_present"),
            cavity_barriers_windows = data.get("cavity_barriers_windows"),
            cavity_barriers_floors  = data.get("cavity_barriers_floors"),
            fire_breaks_floor_level = data.get("fire_breaks_floor_level"),
            fire_breaks_party_walls = data.get("fire_breaks_party_walls"),
            dry_riser_present       = data.get("dry_riser_present"),
            wet_riser_present       = data.get("wet_riser_present"),
            evacuation_strategy     = evac,
            bs8414_test_evidence    = data.get("bs8414_test_evidence"),
            br135_criteria_met      = data.get("br135_criteria_met"),
            adb_compliant           = adb,
            height_survey_recommended           = bool(data.get("height_survey_recommended", False)),
            fire_door_survey_recommended        = bool(data.get("fire_door_survey_recommended", False)),
            intrusive_investigation_recommended = bool(data.get("intrusive_investigation_recommended", False)),
            asbestos_suspected      = bool(data.get("asbestos_suspected", False)),
            extraction_confidence   = float(data.get("extraction_confidence", 0.5)),
        )

    def _empty_features(self, confidence: float = 0.1) -> FRAEWExtractedFeatures:
        return FRAEWExtractedFeatures(
            report_reference=None, assessment_date=None, report_date=None,
            assessment_valid_until=None, assessor_name=None, assessor_company=None,
            assessor_qualification=None, fire_engineer_name=None,
            fire_engineer_company=None, fire_engineer_qualification=None,
            extraction_confidence=confidence,
        )

    # ── Derived fields ────────────────────────────────────────────────

    def _normalise_rag_status(self, building_risk_rating: Optional[str]) -> Optional[str]:
        """Map PAS 9980 risk rating text → GREEN / AMBER / RED / None."""
        if not building_risk_rating:
            return None
        lower = building_risk_rating.lower().strip()

        if lower in ("n/a", "not assessed", "unknown", "tbc", "tbd", "none"):
            return None

        # Multi-word phrases first (order matters)
        if "no further action" in lower or "broadly acceptable" in lower:
            return "GREEN"
        if "not acceptable" in lower:
            return "RED"
        if "tolerable but" in lower or "tolerable with" in lower:
            return "AMBER"
        if "further action" in lower or "further assessment" in lower:
            return "AMBER"

        # Single keywords
        for kw in ("high", "intolerable", "unacceptable", "extreme", "critical"):
            if kw in lower:
                return "RED"
        for kw in ("medium", "moderate", "significant"):
            if kw in lower:
                return "AMBER"
        for kw in ("low", "tolerable", "acceptable", "negligible"):
            if kw in lower:
                return "GREEN"

        logger.warning("Unknown FRAEW risk rating '%s' → defaulting to AMBER", building_risk_rating)
        return "AMBER"

    def _compute_is_in_date(self, valid_until_str: Optional[str]) -> Optional[bool]:
        if not valid_until_str:
            return None
        try:
            return date.fromisoformat(valid_until_str[:10]) >= date.today()
        except ValueError:
            return None

    def _derive_height_category(self, features: FRAEWExtractedFeatures) -> Optional[str]:
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
        features:        FRAEWExtractedFeatures,
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

        # Convert string dates → Python date objects for asyncpg
        assessment_date_obj    = _to_date(features.assessment_date)
        report_date_obj        = _to_date(features.report_date)
        valid_until_obj        = _to_date(features.assessment_valid_until)

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

        remedial_actions_json = json.dumps(features.remedial_actions)

        raw_json = json.dumps({
            "report_reference":     features.report_reference,
            "building_risk_rating": features.building_risk_rating,
            "clause_14_applied":    features.clause_14_applied,
            "bs8414_test_evidence": features.bs8414_test_evidence,
            "adb_compliant":        features.adb_compliant,
            "wall_type_count":      len(features.wall_types),
        })

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
                    extraction_confidence, fraew_features_json,
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
                    $60,$61::jsonb,
                    $62,$63
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
                raw_json,
                now, now,
            )

        return feature_id, fraew_id