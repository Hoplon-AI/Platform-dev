# """
# backend/workers/fra_processor.py

# Processes Fire Risk Assessment (FRA) documents.
# Works with ALL UK FRA formats: Eurosafe, council templates, BAFE reports, narrative prose.

# Flow:
#   1. Smart-truncate PDF text → fits Groq free tier limits
#   2. LLM extraction → structured JSON
#   3. Normalise + validate all fields
#   4. Write to silver.document_features + silver.fra_features
# """

# import json
# import logging
# import re
# import uuid
# from dataclasses import dataclass, field
# from datetime import date, datetime
# from typing import Any, Optional

# logger = logging.getLogger(__name__)


# # ──────────────────────────────────────────────────────────────────────
# # Data classes
# # ──────────────────────────────────────────────────────────────────────

# @dataclass
# class FRAActionItem:
#     issue_ref:   Optional[str]
#     description: str
#     hazard_type: Optional[str]
#     priority:    str            # advisory | low | medium | high
#     due_date:    Optional[date]
#     status:      str            # outstanding | completed | overdue
#     responsible: Optional[str]


# @dataclass
# class FRAExtractedFeatures:
#     risk_rating:                   Optional[str]
#     fra_assessment_type:           Optional[str]
#     assessment_date:               Optional[date]
#     assessment_valid_until:        Optional[date]
#     next_review_date:              Optional[date]
#     assessor_name:                 Optional[str]
#     assessor_company:              Optional[str]
#     assessor_qualification:        Optional[str]
#     responsible_person:            Optional[str]
#     evacuation_strategy:           Optional[str]
#     evacuation_strategy_changed:   bool = False
#     evacuation_strategy_notes:     Optional[str] = None
#     has_accessibility_needs_noted: bool = False
#     has_sprinkler_system:          Optional[bool] = None
#     has_smoke_detection:           Optional[bool] = None
#     has_fire_alarm_system:         Optional[bool] = None
#     has_fire_doors:                Optional[bool] = None
#     has_compartmentation:          Optional[bool] = None
#     has_emergency_lighting:        Optional[bool] = None
#     has_fire_extinguishers:        Optional[bool] = None
#     has_firefighting_shaft:        Optional[bool] = None
#     has_dry_riser:                 Optional[bool] = None
#     has_wet_riser:                 Optional[bool] = None
#     action_items:                  list = field(default_factory=list)
#     significant_findings:          list = field(default_factory=list)
#     bsa_2022_applicable:           bool = False
#     accountable_person_noted:      bool = False
#     mandatory_occurrence_noted:    bool = False
#     extraction_confidence:         float = 0.5


# # ──────────────────────────────────────────────────────────────────────
# # LLM Prompt (concise — saves tokens)
# # ──────────────────────────────────────────────────────────────────────

# FRA_EXTRACTION_PROMPT = """Extract structured data from this UK Fire Risk Assessment (FRA) document.
# Return ONLY valid JSON — no markdown, no explanation, no preamble.
# Use null for any field not found. Never use "N/A" or "unknown".
# Dates must be YYYY-MM-DD.

# RISK RATING: Extract the exact phrase (e.g. Tolerable, Moderate, Substantial, High, Intolerable, Grade A-E, Priority 1-3).
# For council composite ratings (Hazard/Consequences/Overall), use the "Overall Risk from Fire" value.

# EVACUATION STRATEGY — map to exactly one of these or null:
#   stay_put | simultaneous | phased | temporary_evacuation

# ACTION ITEMS — extract EVERY action/recommendation/deficiency. Formats vary:
#   - Private assessors (Eurosafe etc.): action cards with Issue Ref, Priority, Action Required
#   - Council tables: columns like No. | Action | Priority | By When | By Whom | Completed
#   - Narrative lists: numbered recommendations
#   Each table row = one separate action_item.

# FIRE SYSTEMS — infer from any mention: sprinklers, smoke/heat detectors, fire alarm,
# fire doors (FD30/FD60), compartmentation, emergency lighting, extinguishers,
# firefighting shaft, dry riser, wet riser.

# Return this JSON:
# {{
#   "risk_rating": "exact phrase or null",
#   "fra_assessment_type": "Type 1/2/3/4 or null",
#   "assessment_date": "YYYY-MM-DD or null",
#   "assessment_valid_until": "YYYY-MM-DD or null",
#   "next_review_date": "YYYY-MM-DD or null",
#   "assessor_name": "name or null",
#   "assessor_company": "company or null",
#   "assessor_qualification": "qualifications or null",
#   "responsible_person": "person or org or null",
#   "evacuation_strategy": "stay_put or simultaneous or phased or temporary_evacuation or null",
#   "evacuation_strategy_changed": true or false,
#   "evacuation_strategy_notes": "notes or null",
#   "has_accessibility_needs_noted": true or false,
#   "has_sprinkler_system": true or false or null,
#   "has_smoke_detection": true or false or null,
#   "has_fire_alarm_system": true or false or null,
#   "has_fire_doors": true or false or null,
#   "has_compartmentation": true or false or null,
#   "has_emergency_lighting": true or false or null,
#   "has_fire_extinguishers": true or false or null,
#   "has_firefighting_shaft": true or false or null,
#   "has_dry_riser": true or false or null,
#   "has_wet_riser": true or false or null,
#   "action_items": [
#     {{
#       "issue_ref": "ref or null",
#       "description": "what needs to be done",
#       "hazard_type": "Housekeeping|Means of Escape|Fire Spread|Detection|Signage|Emergency Plans|Fire Service Facilities|Structural|Other",
#       "priority": "advisory|low|medium|high",
#       "due_date": "YYYY-MM-DD or null",
#       "status": "outstanding|completed|overdue",
#       "responsible": "person or null"
#     }}
#   ],
#   "significant_findings": [
#     {{"finding": "description", "location": "location or null", "severity": "high|medium|low"}}
#   ],
#   "bsa_2022_applicable": true or false,
#   "accountable_person_noted": true or false,
#   "mandatory_occurrence_noted": true or false,
#   "extraction_confidence": 0.0 to 1.0
# }}

# DOCUMENT:
# {document_text}"""


# # ──────────────────────────────────────────────────────────────────────
# # Type coercion helpers
# # ──────────────────────────────────────────────────────────────────────

# def _to_date(value: Any) -> Optional[date]:
#     if value is None:
#         return None
#     if isinstance(value, date) and not isinstance(value, datetime):
#         return value
#     if isinstance(value, datetime):
#         return value.date()
#     if isinstance(value, str):
#         s = value.strip()
#         if not s or s.lower() in ("null", "n/a", "unknown", "tbc", "tbd", "none"):
#             return None
#         try:
#             return date.fromisoformat(s[:10])
#         except ValueError:
#             pass
#         s_stripped = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", s, flags=re.IGNORECASE)
#         for fmt in ("%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y",
#                     "%Y/%m/%d", "%Y.%m.%d", "%d.%m.%Y",
#                     "%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y"):
#             try:
#                 return datetime.strptime(s_stripped if s_stripped != s else s, fmt).date()
#             except ValueError:
#                 continue
#         logger.warning("Could not parse date: %r", value)
#     return None


# def _to_bool(value: Any) -> Optional[bool]:
#     if value is None:
#         return None
#     if isinstance(value, bool):
#         return value
#     if isinstance(value, int):
#         return bool(value)
#     if isinstance(value, str):
#         v = value.strip().lower()
#         if v in ("true", "yes", "1", "present", "installed", "provided", "fitted"):
#             return True
#         if v in ("false", "no", "0", "not present", "not installed", "none", "n/a"):
#             return False
#     return None


# def _to_float(value: Any, default: float = 0.5) -> float:
#     try:
#         return max(0.0, min(1.0, float(value)))
#     except (TypeError, ValueError):
#         return default


# def _to_str(value: Any) -> Optional[str]:
#     if value is None:
#         return None
#     s = str(value).strip()
#     if s.lower() in ("null", "none", "n/a", "unknown", "tbc", "tbd",
#                      "not stated", "not applicable", "not available",
#                      "not provided", "not assessed", ""):
#         return None
#     return s


# def _date_to_str(d: Optional[date]) -> Optional[str]:
#     return d.isoformat() if d else None


# def _normalise_priority(raw: Any) -> str:
#     s = (_to_str(raw) or "").lower()
#     if s in ("advisory", "low", "medium", "high"):
#         return s
#     if any(k in s for k in ("high", "urgent", "immediate", "critical", "priority 1", "serious breach")):
#         return "high"
#     if any(k in s for k in ("medium", "moderate", "priority 2", "3 month", "6 month")):
#         return "medium"
#     if any(k in s for k in ("advisory", "informational", "best practice", "no timescale")):
#         return "advisory"
#     return "low"


# def _normalise_status(raw: Any) -> str:
#     s = (_to_str(raw) or "").lower()
#     if any(k in s for k in ("complet", "done", "resolved", "closed", "actioned", "fixed")):
#         return "completed"
#     if any(k in s for k in ("overdue", "past due", "late", "missed")):
#         return "overdue"
#     return "outstanding"


# def _normalise_hazard_type(raw: Any) -> str:
#     VALID = ("Housekeeping", "Means of Escape", "Fire Spread", "Detection",
#              "Signage", "Emergency Plans", "Fire Service Facilities", "Structural", "Other")
#     s = _to_str(raw)
#     if not s:
#         return "Other"
#     if s in VALID:
#         return s
#     sl = s.lower()
#     if any(k in sl for k in ("housekeep", "storage", "waste", "rubbish", "clutter")):
#         return "Housekeeping"
#     if any(k in sl for k in ("escape", "exit", "egress", "corridor", "stair")):
#         return "Means of Escape"
#     if any(k in sl for k in ("spread", "compartment", "cladding", "stopping", "intumescent")):
#         return "Fire Spread"
#     if any(k in sl for k in ("detect", "alarm", "smoke", "heat", "aov")):
#         return "Detection"
#     if any(k in sl for k in ("sign", "notice", "label", "marking")):
#         return "Signage"
#     if any(k in sl for k in ("plan", "procedure", "drill", "assembly")):
#         return "Emergency Plans"
#     if any(k in sl for k in ("brigade", "riser", "hydrant", "hose", "extinguish", "firefight")):
#         return "Fire Service Facilities"
#     if any(k in sl for k in ("structural", "construction", "building fabric")):
#         return "Structural"
#     return "Other"


# # ──────────────────────────────────────────────────────────────────────
# # FRAProcessor
# # ──────────────────────────────────────────────────────────────────────

# class FRAProcessor:
#     """End-to-end FRA processor. Works with any UK FRA format."""

#     def __init__(self, db_conn, llm_client):
#         self.db  = db_conn
#         self.llm = llm_client
#         self.last_raw_response: Optional[str] = None

#     async def process(
#         self,
#         text: str,
#         upload_id: str,
#         block_id: Optional[str],
#         ha_id: str,
#         s3_path: str,
#         assessor_company: Optional[str] = None,
#     ) -> dict[str, Any]:
#         logger.info("FRAProcessor.process() upload_id=%s ha_id=%s", upload_id, ha_id)

#         raw_json = await self._call_llm(text)
#         features = self._parse_llm_response(raw_json)
#         logger.info(
#             "FRAProcessor parsed: risk=%s rag=%s actions=%d confidence=%.2f",
#             features.risk_rating,
#             self._normalise_rag_status(features.risk_rating),
#             len(features.action_items),
#             features.extraction_confidence,
#         )

#         rag_status    = self._normalise_rag_status(features.risk_rating)
#         is_in_date    = self._compute_is_in_date(features.assessment_valid_until)
#         action_counts = self._count_actions(features.action_items)

#         feature_id, fra_id = await self._write_to_db(
#             features=features, rag_status=rag_status, is_in_date=is_in_date,
#             action_counts=action_counts, upload_id=upload_id, block_id=block_id,
#             ha_id=ha_id, s3_path=s3_path, assessor_company=assessor_company,
#         )

#         logger.info("FRAProcessor complete: fra_id=%s rag=%s", fra_id, rag_status)
#         return {
#             "fra_id":                fra_id,
#             "feature_id":            feature_id,
#             "rag_status":            rag_status,
#             "extraction_confidence": features.extraction_confidence,
#         }

#     # ── LLM call ─────────────────────────────────────────────────────

#     async def _call_llm(self, text: str) -> str:
#         """
#         Smart-truncate to stay within Groq free tier, then call LLM.

#         Token budget:
#           llama-3.1-8b-instant:  500K tokens/day, 30K TPM
#           Prompt template:       ~400 tokens
#           Document budget:       ~5,000 tokens → 20,000 chars
#         """
#         truncated = self._smart_truncate(text, max_chars=20_000)
#         prompt    = FRA_EXTRACTION_PROMPT.format(document_text=truncated)
#         try:
#             response = await self.llm.extract(prompt)
#             self.last_raw_response = response
#             logger.info("LLM responded with %d chars", len(response or ""))
#             return response
#         except Exception as exc:
#             logger.error("LLM call failed: %s", exc)
#             raise RuntimeError(f"LLM extraction failed: {exc}") from exc

#     def _smart_truncate(self, text: str, max_chars: int) -> str:
#         """
#         Section-aware truncation. Budget:
#           20% → header (assessor, dates, risk rating)
#           65% → action plan / significant findings  ← most important
#           15% → fire protection systems
#         """
#         if len(text) <= max_chars:
#             return text

#         header_budget  = int(max_chars * 0.20)   # 4,000 chars
#         action_budget  = int(max_chars * 0.65)   # 13,000 chars
#         systems_budget = int(max_chars * 0.15)   # 3,000 chars

#         upper = text.upper()

#         def find_first(markers: list) -> int:
#             hits = [upper.find(m) for m in markers if upper.find(m) != -1]
#             return min(hits) if hits else -1

#         action_start = find_first([
#             "SIGNIFICANT FINDINGS", "ACTION PLAN", "RECOMMENDATIONS",
#             "REMEDIAL ACTIONS", "ACTIONS REQUIRED", "IMPROVEMENT ACTIONS",
#             "FIRE SAFETY ACTION PLAN", "FIRE SAFETY DEFICIENCIES",
#             "DEFICIENCIES AND RECOMMENDATIONS", "ITEMS FOR ACTION",
#             "OUTSTANDING ACTIONS", "RECOMMENDED ACTIONS",
#             "SECTION 3", "ACTION NO", "ACTION REF",
#         ])

#         systems_start = find_first([
#             "FIRE PROTECTION MEASURES", "MEANS OF ESCAPE",
#             "FIRE SAFETY SYSTEMS", "SECTION 5", "SECTION 6",
#         ])

#         # Header: everything before the action section
#         if action_start != -1:
#             header = text[:min(action_start, header_budget)]
#         else:
#             header = text[:header_budget]

#         # Action section: the bulk of the budget
#         if action_start != -1:
#             action = text[action_start : action_start + action_budget]
#             logger.info("Smart truncate: action section at char %d, %d chars", action_start, len(action))
#         else:
#             # Fallback: scan for table column headers
#             late_start = find_first([
#                 "PRIORITY", "BY WHEN", "BY WHOM", "DATE COMPLETED",
#                 "TIMESCALE", "ACTION REQUIRED", "RECOMMENDED ACTION",
#             ])
#             if late_start != -1:
#                 action = text[max(0, late_start - 200) : late_start - 200 + action_budget]
#             else:
#                 # Use second quarter of document
#                 q = len(text) // 4
#                 action = text[q : q + action_budget]
#                 logger.warning("Smart truncate: no action markers found, using mid-doc fallback")

#         # Fire systems section
#         if systems_start != -1:
#             systems = text[systems_start : systems_start + systems_budget]
#         else:
#             systems = ""

#         parts = ["=== HEADER ===", header.strip()]
#         if action.strip():
#             parts += ["\n\n=== ACTION PLAN / FINDINGS ===", action.strip()]
#         if systems.strip():
#             parts += ["\n\n=== FIRE SYSTEMS ===", systems.strip()]

#         result = "\n".join(parts)
#         if len(result) > max_chars:
#             result = result[:max_chars]

#         logger.info(
#             "Smart truncate: %d → %d chars (header=%d action=%d systems=%d)",
#             len(text), len(result), len(header), len(action), len(systems),
#         )
#         return result

#     # ── Parse response ────────────────────────────────────────────────

#     def _extract_json(self, raw: str) -> Optional[dict]:
#         if not raw:
#             return None

#         # Strategy 1: strip markdown fences
#         cleaned = raw.strip()
#         if cleaned.startswith("```"):
#             lines   = cleaned.split("\n")
#             cleaned = "\n".join(lines[1:-1]).strip()
#         try:
#             result = json.loads(cleaned)
#             if isinstance(result, dict):
#                 return result
#         except json.JSONDecodeError:
#             pass

#         # Strategy 2: find outermost { ... }
#         start = raw.find("{")
#         end   = raw.rfind("}")
#         if start != -1 and end > start:
#             try:
#                 result = json.loads(raw[start:end + 1])
#                 if isinstance(result, dict):
#                     return result
#             except json.JSONDecodeError:
#                 pass

#         # Strategy 3: fix common LLM formatting issues
#         fixed = re.sub(r",\s*([}\]])", r"\1", raw)
#         fixed = re.sub(r"\bNone\b", "null", fixed)
#         fixed = re.sub(r"\bTrue\b", "true", fixed)
#         fixed = re.sub(r"\bFalse\b", "false", fixed)
#         start = fixed.find("{")
#         end   = fixed.rfind("}")
#         if start != -1 and end > start:
#             try:
#                 result = json.loads(fixed[start:end + 1])
#                 if isinstance(result, dict):
#                     return result
#             except json.JSONDecodeError:
#                 pass

#         logger.error("JSON parse failed. Raw (500 chars):\n%s", raw[:500])
#         return None

#     def _parse_llm_response(self, raw_json: str) -> FRAExtractedFeatures:
#         data = self._extract_json(raw_json)
#         if data is None:
#             return self._empty_features(confidence=0.1)

#         action_items = []
#         for item in data.get("action_items") or []:
#             if not isinstance(item, dict):
#                 continue
#             desc = _to_str(item.get("description"))
#             if not desc:
#                 continue
#             action_items.append(FRAActionItem(
#                 issue_ref   = _to_str(item.get("issue_ref")),
#                 description = desc,
#                 hazard_type = _normalise_hazard_type(item.get("hazard_type")),
#                 priority    = _normalise_priority(item.get("priority")),
#                 due_date    = _to_date(item.get("due_date")),
#                 status      = _normalise_status(item.get("status")),
#                 responsible = _to_str(item.get("responsible")),
#             ))

#         significant_findings = []
#         for f in data.get("significant_findings") or []:
#             if not isinstance(f, dict):
#                 continue
#             finding = _to_str(f.get("finding"))
#             if not finding:
#                 continue
#             severity = _to_str(f.get("severity")) or "low"
#             if severity not in ("high", "medium", "low"):
#                 severity = "low"
#             significant_findings.append({
#                 "finding":  finding,
#                 "location": _to_str(f.get("location")),
#                 "severity": severity,
#             })

#         VALID_EVAC = ("stay_put", "simultaneous", "phased", "temporary_evacuation")
#         evac = _to_str(data.get("evacuation_strategy"))
#         if evac not in VALID_EVAC:
#             evac = None

#         fra_type = _to_str(data.get("fra_assessment_type"))
#         if fra_type and not re.match(r"^Type\s*[1-4]$", fra_type, re.IGNORECASE):
#             m = re.search(r"\b([1-4])\b", fra_type)
#             fra_type = f"Type {m.group(1)}" if m else None

#         bsa = bool(_to_bool(data.get("bsa_2022_applicable")) or False)

#         return FRAExtractedFeatures(
#             risk_rating                   = _to_str(data.get("risk_rating")),
#             fra_assessment_type           = fra_type,
#             assessment_date               = _to_date(data.get("assessment_date")),
#             assessment_valid_until        = _to_date(data.get("assessment_valid_until")),
#             next_review_date              = _to_date(data.get("next_review_date")),
#             assessor_name                 = _to_str(data.get("assessor_name")),
#             assessor_company              = _to_str(data.get("assessor_company")),
#             assessor_qualification        = _to_str(data.get("assessor_qualification")),
#             responsible_person            = _to_str(data.get("responsible_person")),
#             evacuation_strategy           = evac,
#             evacuation_strategy_changed   = bool(_to_bool(data.get("evacuation_strategy_changed")) or False),
#             evacuation_strategy_notes     = _to_str(data.get("evacuation_strategy_notes")),
#             has_accessibility_needs_noted = bool(_to_bool(data.get("has_accessibility_needs_noted")) or False),
#             has_sprinkler_system          = _to_bool(data.get("has_sprinkler_system")),
#             has_smoke_detection           = _to_bool(data.get("has_smoke_detection")),
#             has_fire_alarm_system         = _to_bool(data.get("has_fire_alarm_system")),
#             has_fire_doors                = _to_bool(data.get("has_fire_doors")),
#             has_compartmentation          = _to_bool(data.get("has_compartmentation")),
#             has_emergency_lighting        = _to_bool(data.get("has_emergency_lighting")),
#             has_fire_extinguishers        = _to_bool(data.get("has_fire_extinguishers")),
#             has_firefighting_shaft        = _to_bool(data.get("has_firefighting_shaft")),
#             has_dry_riser                 = _to_bool(data.get("has_dry_riser")),
#             has_wet_riser                 = _to_bool(data.get("has_wet_riser")),
#             action_items                  = action_items,
#             significant_findings          = significant_findings,
#             bsa_2022_applicable           = bsa,
#             accountable_person_noted      = bool(_to_bool(data.get("accountable_person_noted")) or False),
#             mandatory_occurrence_noted    = bool(_to_bool(data.get("mandatory_occurrence_noted")) or False),
#             extraction_confidence         = _to_float(data.get("extraction_confidence"), default=0.5),
#         )

#     def _empty_features(self, confidence: float = 0.1) -> FRAExtractedFeatures:
#         return FRAExtractedFeatures(
#             risk_rating=None, fra_assessment_type=None,
#             assessment_date=None, assessment_valid_until=None,
#             next_review_date=None, assessor_name=None,
#             assessor_company=None, assessor_qualification=None,
#             responsible_person=None, evacuation_strategy=None,
#             action_items=[], significant_findings=[],
#             extraction_confidence=confidence,
#         )

#     # ── Derived fields ────────────────────────────────────────────────

#     def _normalise_rag_status(self, risk_rating: Optional[str]) -> Optional[str]:
#         if not risk_rating:
#             return None
#         lower = risk_rating.lower().strip()
#         if lower in ("n/a", "not assessed", "unknown", "tbc", "tbd", "none"):
#             return None
#         for kw in ("intolerable", "substantial", "high", "critical", "priority 1",
#                    "very high", "grade e", "grade d", "4/5", "5/5", "serious"):
#             if kw in lower:
#                 return "RED"
#         for kw in ("moderate", "medium", "significant", "tolerable but",
#                    "priority 2", "grade c", "3/5"):
#             if kw in lower:
#                 return "AMBER"
#         for kw in ("trivial", "low", "tolerable", "acceptable", "negligible",
#                    "priority 3", "grade a", "grade b", "1/5", "2/5"):
#             if kw in lower:
#                 return "GREEN"
#         logger.warning("Unknown risk rating '%s' → defaulting to AMBER", risk_rating)
#         return "AMBER"

#     def _compute_is_in_date(self, valid_until: Optional[date]) -> Optional[bool]:
#         if valid_until is None:
#             return None
#         return valid_until >= date.today()

#     def _count_actions(self, action_items: list) -> dict:
#         total         = len(action_items)
#         high_priority = sum(1 for a in action_items if a.priority == "high")
#         overdue       = sum(1 for a in action_items if a.status == "overdue")
#         outstanding   = sum(1 for a in action_items if a.status in ("outstanding", "overdue"))
#         no_date       = sum(1 for a in action_items if not a.due_date)
#         return {
#             "total_action_count":         total,
#             "high_priority_action_count": high_priority,
#             "overdue_action_count":       overdue,
#             "outstanding_action_count":   outstanding,
#             "no_date_action_count":       no_date,
#         }

#     # ── Write to DB ───────────────────────────────────────────────────

#     async def _write_to_db(
#         self,
#         features:         FRAExtractedFeatures,
#         rag_status:       Optional[str],
#         is_in_date:       Optional[bool],
#         action_counts:    dict,
#         upload_id:        str,
#         block_id:         Optional[str],
#         ha_id:            str,
#         s3_path:          str,
#         assessor_company: Optional[str],
#     ) -> tuple:
#         feature_id = str(uuid.uuid4())
#         fra_id     = str(uuid.uuid4())
#         now        = datetime.utcnow()

#         action_items_json = json.dumps([
#             {
#                 "issue_ref":   a.issue_ref,
#                 "description": a.description,
#                 "hazard_type": a.hazard_type,
#                 "priority":    a.priority,
#                 "due_date":    _date_to_str(a.due_date),
#                 "status":      a.status,
#                 "responsible": a.responsible,
#             }
#             for a in features.action_items
#         ])

#         significant_findings_json = json.dumps(features.significant_findings)

#         raw_features_json = json.dumps({
#             "risk_rating":            features.risk_rating,
#             "fra_assessment_type":    features.fra_assessment_type,
#             "assessment_date":        _date_to_str(features.assessment_date),
#             "assessment_valid_until": _date_to_str(features.assessment_valid_until),
#             "evacuation_strategy":    features.evacuation_strategy,
#             "bsa_2022_applicable":    features.bsa_2022_applicable,
#         })

#         async with self.db.transaction():

#             await self.db.execute("""
#                 INSERT INTO silver.document_features (
#                     feature_id, ha_id, upload_id, block_id, document_type,
#                     assessment_date, assessor_company, features_json,
#                     processed_at, created_at, updated_at
#                 )
#                 VALUES ($1, $2, $3::uuid, $4::uuid, 'fra_document', $5, $6,
#                         $7::jsonb, $8, $9, $10)
#                 ON CONFLICT (feature_id) DO NOTHING
#             """,
#                 feature_id, ha_id, upload_id, block_id,
#                 features.assessment_date,
#                 features.assessor_company or assessor_company,
#                 raw_features_json, now, now, now,
#             )

#             await self.db.execute("""
#                 INSERT INTO silver.fra_features (
#                     fra_id, feature_id, ha_id, block_id,
#                     risk_rating, rag_status, fra_assessment_type,
#                     assessment_date, assessment_valid_until, next_review_date, is_in_date,
#                     assessor_name, assessor_company, assessor_qualification, responsible_person,
#                     evacuation_strategy, evacuation_strategy_changed,
#                     evacuation_strategy_notes, has_accessibility_needs_noted,
#                     has_sprinkler_system, has_smoke_detection, has_fire_alarm_system,
#                     has_fire_doors, has_compartmentation, has_emergency_lighting,
#                     has_fire_extinguishers, has_firefighting_shaft, has_dry_riser, has_wet_riser,
#                     action_items, significant_findings,
#                     total_action_count, high_priority_action_count,
#                     overdue_action_count, outstanding_action_count, no_date_action_count,
#                     bsa_2022_applicable, accountable_person_noted, mandatory_occurrence_noted,
#                     extraction_confidence, raw_features, created_at, updated_at
#                 )
#                 VALUES (
#                     $1,$2,$3,$4, $5,$6,$7, $8,$9,$10,$11,
#                     $12,$13,$14,$15, $16,$17,$18,$19,
#                     $20,$21,$22,$23,$24,$25,$26,$27,$28,$29,
#                     $30::jsonb,$31::jsonb,
#                     $32,$33,$34,$35,$36,
#                     $37,$38,$39,$40,$41::jsonb,$42,$43
#                 )
#             """,
#                 fra_id, feature_id, ha_id, block_id,
#                 features.risk_rating, rag_status, features.fra_assessment_type,
#                 features.assessment_date, features.assessment_valid_until,
#                 features.next_review_date, is_in_date,
#                 features.assessor_name, features.assessor_company or assessor_company,
#                 features.assessor_qualification, features.responsible_person,
#                 features.evacuation_strategy, features.evacuation_strategy_changed,
#                 features.evacuation_strategy_notes, features.has_accessibility_needs_noted,
#                 features.has_sprinkler_system, features.has_smoke_detection,
#                 features.has_fire_alarm_system, features.has_fire_doors,
#                 features.has_compartmentation, features.has_emergency_lighting,
#                 features.has_fire_extinguishers, features.has_firefighting_shaft,
#                 features.has_dry_riser, features.has_wet_riser,
#                 action_items_json, significant_findings_json,
#                 action_counts["total_action_count"],
#                 action_counts["high_priority_action_count"],
#                 action_counts["overdue_action_count"],
#                 action_counts["outstanding_action_count"],
#                 action_counts["no_date_action_count"],
#                 features.bsa_2022_applicable, features.accountable_person_noted,
#                 features.mandatory_occurrence_noted, features.extraction_confidence,
#                 raw_features_json, now, now,
#             )

#         return feature_id, fra_id


# """
# backend/workers/fra_processor.py

# Processes Fire Risk Assessment (FRA) documents.
# Works with ALL UK FRA formats: Eurosafe, council templates, BAFE reports, narrative prose.

# Flow:
#   1. Smart-truncate PDF text → fits Groq free tier limits
#   2. LLM extraction → structured JSON
#   3. Normalise + validate all fields
#   4. Write to silver.document_features + silver.fra_features
# """

# import json
# import logging
# import re
# import uuid
# from dataclasses import dataclass, field
# from datetime import date, datetime
# from typing import Any, Optional

# logger = logging.getLogger(__name__)


# # ──────────────────────────────────────────────────────────────────────
# # Data classes
# # ──────────────────────────────────────────────────────────────────────

# @dataclass
# class FRAActionItem:
#     issue_ref:   Optional[str]
#     description: str
#     hazard_type: Optional[str]
#     priority:    str            # advisory | low | medium | high
#     due_date:    Optional[date]
#     status:      str            # outstanding | completed | overdue
#     responsible: Optional[str]


# @dataclass
# class FRAExtractedFeatures:
#     risk_rating:                   Optional[str]
#     fra_assessment_type:           Optional[str]
#     assessment_date:               Optional[date]
#     assessment_valid_until:        Optional[date]
#     next_review_date:              Optional[date]
#     assessor_name:                 Optional[str]
#     assessor_company:              Optional[str]
#     assessor_qualification:        Optional[str]
#     responsible_person:            Optional[str]
#     evacuation_strategy:           Optional[str]
#     evacuation_strategy_changed:   bool = False
#     evacuation_strategy_notes:     Optional[str] = None
#     has_accessibility_needs_noted: bool = False
#     has_sprinkler_system:          Optional[bool] = None
#     has_smoke_detection:           Optional[bool] = None
#     has_fire_alarm_system:         Optional[bool] = None
#     has_fire_doors:                Optional[bool] = None
#     has_compartmentation:          Optional[bool] = None
#     has_emergency_lighting:        Optional[bool] = None
#     has_fire_extinguishers:        Optional[bool] = None
#     has_firefighting_shaft:        Optional[bool] = None
#     has_dry_riser:                 Optional[bool] = None
#     has_wet_riser:                 Optional[bool] = None
#     action_items:                  list = field(default_factory=list)
#     significant_findings:          list = field(default_factory=list)
#     bsa_2022_applicable:           bool = False
#     accountable_person_noted:      bool = False
#     mandatory_occurrence_noted:    bool = False
#     extraction_confidence:         float = 0.5


# # ──────────────────────────────────────────────────────────────────────
# # LLM Prompt (concise — saves tokens)
# # ──────────────────────────────────────────────────────────────────────

# FRA_EXTRACTION_PROMPT = """Extract structured data from this UK Fire Risk Assessment (FRA) document.
# Return ONLY valid JSON — no markdown, no explanation, no preamble.
# Use null for any field not found. Never use "N/A" or "unknown".
# Dates must be YYYY-MM-DD.

# RISK RATING: Extract the exact phrase (e.g. Tolerable, Moderate, Substantial, High, Intolerable, Grade A-E, Priority 1-3).
# For council composite ratings (Hazard/Consequences/Overall), use the "Overall Risk from Fire" value.

# EVACUATION STRATEGY — map to exactly one of these or null:
#   stay_put | simultaneous | phased | temporary_evacuation

# ACTION ITEMS — extract EVERY action/recommendation/deficiency. Formats vary:

#   FORMAT A — Islington/Council "Action Ref" cards (pages at END of document):
#     Action Ref: [number e.g. 0039992]
#     Action Required: [what to do]
#     Due Date: [date]
#     Responsible: [team]
#     Status: OPEN or CLOSED
#     → Each "Action Ref" block = one separate action_item. Extract ALL of them.

#   FORMAT B — Private assessors (Eurosafe etc.) inline action cards:
#     Issue Ref: [ref]  Priority: [level]  Action Required: [description]

#   FORMAT C — Council audit tables with columns:
#     No. | Action | Priority | By When | By Whom | Date Completed

#   FORMAT D — Narrative recommendations numbered list

#   CRITICAL: In Islington-style FRAs, the structured Action Ref cards appear at the
#   END of the document in an "Audit Details" section. Extract ALL of them even if
#   the same action was also mentioned inline earlier in the document — use the
#   Action Ref card version as it has the definitive due date, responsible party, and status.

#   Priority: If not stated on the card, infer from due date:
#     < 1 month past/future = high, 1-6 months = medium, 12 months = low

# FIRE SYSTEMS — infer true/false from ANY mention anywhere in the document:
#   Sprinklers/suppression                    → has_sprinkler_system
#   Smoke detectors, heat detectors, AOV      → has_smoke_detection
#   Fire alarm (L1/L2/M system, call points)  → has_fire_alarm_system
#   Fire doors, FD30, FD60, flat entrance doors mentioned as fire-rated → has_fire_doors
#   Compartmentation, fire stopping, fire separation → has_compartmentation
#   Emergency/escape lighting                 → has_emergency_lighting
#   Fire extinguishers, hose reels            → has_fire_extinguishers
#   Firefighting shaft, fire lift             → has_firefighting_shaft
#   DRM, Dry Riser, Dry Rising Main           → has_dry_riser (DRM = Dry Rising Main)
#   WRM, Wet Riser, Wet Rising Main           → has_wet_riser (WRM = Wet Rising Main)

# IMPORTANT: "DRM and WRM are inspected" means BOTH dry and wet risers are present → set both true.
# IMPORTANT: If fire doors are mentioned anywhere (even if not fully compliant), set has_fire_doors: true.

# Return this JSON:
# {{
#   "risk_rating": "exact phrase or null",
#   "fra_assessment_type": "ONLY set if explicitly stated in the document e.g. Type 1/2/3/4 — otherwise null",
#   "assessment_date": "YYYY-MM-DD or null",
#   "assessment_valid_until": "YYYY-MM-DD or null",
#   "next_review_date": "YYYY-MM-DD or null",
#   "assessor_name": "name or null",
#   "assessor_company": "company or null",
#   "assessor_qualification": "qualifications or null",
#   "responsible_person": "person or org or null",
#   "evacuation_strategy": "stay_put or simultaneous or phased or temporary_evacuation or null",
#   "evacuation_strategy_changed": true or false,
#   "evacuation_strategy_notes": "notes or null",
#   "has_accessibility_needs_noted": true or false,
#   "has_sprinkler_system": true or false or null,
#   "has_smoke_detection": true or false or null,
#   "has_fire_alarm_system": true or false or null,
#   "has_fire_doors": true or false or null,
#   "has_compartmentation": true or false or null,
#   "has_emergency_lighting": true or false or null,
#   "has_fire_extinguishers": true or false or null,
#   "has_firefighting_shaft": true or false or null,
#   "has_dry_riser": true or false or null,
#   "has_wet_riser": true or false or null,
#   "action_items": [
#     {{
#       "issue_ref": "ref or null",
#       "description": "what needs to be done",
#       "hazard_type": "Housekeeping|Means of Escape|Fire Spread|Detection|Signage|Emergency Plans|Fire Service Facilities|Structural|Other",
#       "priority": "advisory|low|medium|high",
#       "due_date": "YYYY-MM-DD or null",
#       "status": "outstanding|completed|overdue",
#       "responsible": "person or null"
#     }}
#   ],
#   "significant_findings": [
#     {{"finding": "description", "location": "location or null", "severity": "high|medium|low"}}
#   ],
#   "bsa_2022_applicable": true or false,
#   "accountable_person_noted": true or false,
#   "mandatory_occurrence_noted": true or false,
#   "extraction_confidence": 0.0 to 1.0
# }}

# DOCUMENT:
# {document_text}"""


# # ──────────────────────────────────────────────────────────────────────
# # Type coercion helpers
# # ──────────────────────────────────────────────────────────────────────

# def _to_date(value: Any) -> Optional[date]:
#     if value is None:
#         return None
#     if isinstance(value, date) and not isinstance(value, datetime):
#         return value
#     if isinstance(value, datetime):
#         return value.date()
#     if isinstance(value, str):
#         s = value.strip()
#         if not s or s.lower() in ("null", "n/a", "unknown", "tbc", "tbd", "none"):
#             return None
#         try:
#             return date.fromisoformat(s[:10])
#         except ValueError:
#             pass
#         s_stripped = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", s, flags=re.IGNORECASE)
#         for fmt in ("%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y",
#                     "%Y/%m/%d", "%Y.%m.%d", "%d.%m.%Y",
#                     "%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y"):
#             try:
#                 return datetime.strptime(s_stripped if s_stripped != s else s, fmt).date()
#             except ValueError:
#                 continue
#         logger.warning("Could not parse date: %r", value)
#     return None


# def _to_bool(value: Any) -> Optional[bool]:
#     if value is None:
#         return None
#     if isinstance(value, bool):
#         return value
#     if isinstance(value, int):
#         return bool(value)
#     if isinstance(value, str):
#         v = value.strip().lower()
#         if v in ("true", "yes", "1", "present", "installed", "provided", "fitted"):
#             return True
#         if v in ("false", "no", "0", "not present", "not installed", "none", "n/a"):
#             return False
#     return None


# def _to_float(value: Any, default: float = 0.5) -> float:
#     try:
#         return max(0.0, min(1.0, float(value)))
#     except (TypeError, ValueError):
#         return default


# def _to_str(value: Any) -> Optional[str]:
#     if value is None:
#         return None
#     s = str(value).strip()
#     if s.lower() in ("null", "none", "n/a", "unknown", "tbc", "tbd",
#                      "not stated", "not applicable", "not available",
#                      "not provided", "not assessed", ""):
#         return None
#     return s


# def _date_to_str(d: Optional[date]) -> Optional[str]:
#     return d.isoformat() if d else None


# def _normalise_priority(raw: Any) -> str:
#     s = (_to_str(raw) or "").lower()
#     if s in ("advisory", "low", "medium", "high"):
#         return s
#     if any(k in s for k in ("high", "urgent", "immediate", "critical", "priority 1", "serious breach")):
#         return "high"
#     if any(k in s for k in ("medium", "moderate", "priority 2", "3 month", "6 month")):
#         return "medium"
#     if any(k in s for k in ("advisory", "informational", "best practice", "no timescale")):
#         return "advisory"
#     return "low"


# def _normalise_status(raw: Any) -> str:
#     s = (_to_str(raw) or "").lower()
#     if any(k in s for k in ("complet", "done", "resolved", "closed", "actioned", "fixed")):
#         return "completed"
#     if any(k in s for k in ("overdue", "past due", "late", "missed")):
#         return "overdue"
#     return "outstanding"


# def _normalise_hazard_type(raw: Any) -> str:
#     VALID = ("Housekeeping", "Means of Escape", "Fire Spread", "Detection",
#              "Signage", "Emergency Plans", "Fire Service Facilities", "Structural", "Other")
#     s = _to_str(raw)
#     if not s:
#         return "Other"
#     if s in VALID:
#         return s
#     sl = s.lower()
#     if any(k in sl for k in ("housekeep", "storage", "waste", "rubbish", "clutter")):
#         return "Housekeeping"
#     if any(k in sl for k in ("escape", "exit", "egress", "corridor", "stair")):
#         return "Means of Escape"
#     if any(k in sl for k in ("spread", "compartment", "cladding", "stopping", "intumescent")):
#         return "Fire Spread"
#     if any(k in sl for k in ("detect", "alarm", "smoke", "heat", "aov")):
#         return "Detection"
#     if any(k in sl for k in ("sign", "notice", "label", "marking")):
#         return "Signage"
#     if any(k in sl for k in ("plan", "procedure", "drill", "assembly")):
#         return "Emergency Plans"
#     if any(k in sl for k in ("brigade", "riser", "hydrant", "hose", "extinguish", "firefight")):
#         return "Fire Service Facilities"
#     if any(k in sl for k in ("structural", "construction", "building fabric")):
#         return "Structural"
#     return "Other"


# # ──────────────────────────────────────────────────────────────────────
# # FRAProcessor
# # ──────────────────────────────────────────────────────────────────────

# class FRAProcessor:
#     """End-to-end FRA processor. Works with any UK FRA format."""

#     def __init__(self, db_conn, llm_client):
#         self.db  = db_conn
#         self.llm = llm_client
#         self.last_raw_response: Optional[str] = None

#     async def process(
#         self,
#         text: str,
#         upload_id: str,
#         block_id: Optional[str],
#         ha_id: str,
#         s3_path: str,
#         assessor_company: Optional[str] = None,
#     ) -> dict[str, Any]:
#         logger.info("FRAProcessor.process() upload_id=%s ha_id=%s", upload_id, ha_id)

#         raw_json = await self._call_llm(text)
#         features = self._parse_llm_response(raw_json)
#         logger.info(
#             "FRAProcessor parsed: risk=%s rag=%s actions=%d confidence=%.2f",
#             features.risk_rating,
#             self._normalise_rag_status(features.risk_rating),
#             len(features.action_items),
#             features.extraction_confidence,
#         )

#         rag_status    = self._normalise_rag_status(features.risk_rating)
#         is_in_date    = self._compute_is_in_date(features.assessment_valid_until)
#         action_counts = self._count_actions(features.action_items)

#         feature_id, fra_id = await self._write_to_db(
#             features=features, rag_status=rag_status, is_in_date=is_in_date,
#             action_counts=action_counts, upload_id=upload_id, block_id=block_id,
#             ha_id=ha_id, s3_path=s3_path, assessor_company=assessor_company,
#         )

#         logger.info("FRAProcessor complete: fra_id=%s rag=%s", fra_id, rag_status)
#         return {
#             "fra_id":                fra_id,
#             "feature_id":            feature_id,
#             "rag_status":            rag_status,
#             "extraction_confidence": features.extraction_confidence,
#         }

#     # ── LLM call ─────────────────────────────────────────────────────

#     async def _call_llm(self, text: str) -> str:
#         """
#         Smart-truncate only when necessary, then call LLM.

#         llama-3.1-8b-instant context window: 128K tokens (~512K chars)
#         Groq free tier TPM limit: 30K tokens/min

#         Strategy:
#           - Docs <= 100K chars: send in FULL — no truncation at all
#             (most FRAs are 20K-80K chars; truncating loses end-of-doc
#              action cards that Islington-style FRAs put on the last pages)
#           - Docs > 100K chars: smart-truncate to 100K chars
#         """
#         truncated = self._smart_truncate(text, max_chars=100_000)
#         prompt    = FRA_EXTRACTION_PROMPT.format(document_text=truncated)
#         try:
#             response = await self.llm.extract(prompt)
#             self.last_raw_response = response
#             logger.info("LLM responded with %d chars", len(response or ""))
#             return response
#         except Exception as exc:
#             logger.error("LLM call failed: %s", exc)
#             raise RuntimeError(f"LLM extraction failed: {exc}") from exc

#     def _smart_truncate(self, text: str, max_chars: int) -> str:
#         """
#         Section-aware truncation. Budget:
#           20% → header (assessor, dates, risk rating)
#           65% → action plan / significant findings  ← most important
#           15% → fire protection systems
#         """
#         if len(text) <= max_chars:
#             logger.info("smart_truncate: doc fits (%d chars) — sending in full", len(text))
#             return text

#         logger.warning(
#             "smart_truncate: doc too large (%d chars > %d limit) — truncating",
#             len(text), max_chars,
#         )
#         header_budget  = int(max_chars * 0.15)
#         action_budget  = int(max_chars * 0.65)
#         systems_budget = int(max_chars * 0.10)

#         upper = text.upper()

#         def find_first(markers: list) -> int:
#             hits = [upper.find(m) for m in markers if upper.find(m) != -1]
#             return min(hits) if hits else -1

#         action_start = find_first([
#             "SIGNIFICANT FINDINGS", "ACTION PLAN", "RECOMMENDATIONS",
#             "REMEDIAL ACTIONS", "ACTIONS REQUIRED", "IMPROVEMENT ACTIONS",
#             "FIRE SAFETY ACTION PLAN", "FIRE SAFETY DEFICIENCIES",
#             "DEFICIENCIES AND RECOMMENDATIONS", "ITEMS FOR ACTION",
#             "OUTSTANDING ACTIONS", "RECOMMENDED ACTIONS",
#             "SECTION 3", "ACTION NO", "ACTION REF",
#         ])

#         systems_start = find_first([
#             "FIRE PROTECTION MEASURES", "MEANS OF ESCAPE",
#             "FIRE SAFETY SYSTEMS", "SECTION 5", "SECTION 6",
#         ])

#         # Header: everything before the action section
#         if action_start != -1:
#             header = text[:min(action_start, header_budget)]
#         else:
#             header = text[:header_budget]

#         # Action section: the bulk of the budget
#         if action_start != -1:
#             action = text[action_start : action_start + action_budget]
#             logger.info("Smart truncate: action section at char %d, %d chars", action_start, len(action))
#         else:
#             # Fallback: scan for table column headers
#             late_start = find_first([
#                 "PRIORITY", "BY WHEN", "BY WHOM", "DATE COMPLETED",
#                 "TIMESCALE", "ACTION REQUIRED", "RECOMMENDED ACTION",
#             ])
#             if late_start != -1:
#                 action = text[max(0, late_start - 200) : late_start - 200 + action_budget]
#             else:
#                 # Use second quarter of document
#                 q = len(text) // 4
#                 action = text[q : q + action_budget]
#                 logger.warning("Smart truncate: no action markers found, using mid-doc fallback")

#         # Fire systems section
#         if systems_start != -1:
#             systems = text[systems_start : systems_start + systems_budget]
#         else:
#             systems = ""

#         parts = ["=== HEADER ===", header.strip()]
#         if action.strip():
#             parts += ["\n\n=== ACTION PLAN / FINDINGS ===", action.strip()]
#         if systems.strip():
#             parts += ["\n\n=== FIRE SYSTEMS ===", systems.strip()]

#         result = "\n".join(parts)
#         if len(result) > max_chars:
#             result = result[:max_chars]

#         logger.info(
#             "Smart truncate: %d → %d chars (header=%d action=%d systems=%d)",
#             len(text), len(result), len(header), len(action), len(systems),
#         )
#         return result

#     # ── Parse response ────────────────────────────────────────────────

#     def _extract_json(self, raw: str) -> Optional[dict]:
#         if not raw:
#             return None

#         # Strategy 1: strip markdown fences
#         cleaned = raw.strip()
#         if cleaned.startswith("```"):
#             lines   = cleaned.split("\n")
#             cleaned = "\n".join(lines[1:-1]).strip()
#         try:
#             result = json.loads(cleaned)
#             if isinstance(result, dict):
#                 return result
#         except json.JSONDecodeError:
#             pass

#         # Strategy 2: find outermost { ... }
#         start = raw.find("{")
#         end   = raw.rfind("}")
#         if start != -1 and end > start:
#             try:
#                 result = json.loads(raw[start:end + 1])
#                 if isinstance(result, dict):
#                     return result
#             except json.JSONDecodeError:
#                 pass

#         # Strategy 3: fix common LLM formatting issues
#         fixed = re.sub(r",\s*([}\]])", r"\1", raw)
#         fixed = re.sub(r"\bNone\b", "null", fixed)
#         fixed = re.sub(r"\bTrue\b", "true", fixed)
#         fixed = re.sub(r"\bFalse\b", "false", fixed)
#         start = fixed.find("{")
#         end   = fixed.rfind("}")
#         if start != -1 and end > start:
#             try:
#                 result = json.loads(fixed[start:end + 1])
#                 if isinstance(result, dict):
#                     return result
#             except json.JSONDecodeError:
#                 pass

#         logger.error("JSON parse failed. Raw (500 chars):\n%s", raw[:500])
#         return None

#     def _parse_llm_response(self, raw_json: str) -> FRAExtractedFeatures:
#         data = self._extract_json(raw_json)
#         if data is None:
#             return self._empty_features(confidence=0.1)

#         action_items = []
#         for item in data.get("action_items") or []:
#             if not isinstance(item, dict):
#                 continue
#             desc = _to_str(item.get("description"))
#             if not desc:
#                 continue
#             action_items.append(FRAActionItem(
#                 issue_ref   = _to_str(item.get("issue_ref")),
#                 description = desc,
#                 hazard_type = _normalise_hazard_type(item.get("hazard_type")),
#                 priority    = _normalise_priority(item.get("priority")),
#                 due_date    = _to_date(item.get("due_date")),
#                 status      = _normalise_status(item.get("status")),
#                 responsible = _to_str(item.get("responsible")),
#             ))

#         significant_findings = []
#         for f in data.get("significant_findings") or []:
#             if not isinstance(f, dict):
#                 continue
#             finding = _to_str(f.get("finding"))
#             if not finding:
#                 continue
#             severity = _to_str(f.get("severity")) or "low"
#             if severity not in ("high", "medium", "low"):
#                 severity = "low"
#             significant_findings.append({
#                 "finding":  finding,
#                 "location": _to_str(f.get("location")),
#                 "severity": severity,
#             })

#         VALID_EVAC = ("stay_put", "simultaneous", "phased", "temporary_evacuation")
#         evac = _to_str(data.get("evacuation_strategy"))
#         if evac not in VALID_EVAC:
#             evac = None

#         fra_type = _to_str(data.get("fra_assessment_type"))
#         if fra_type and not re.match(r"^Type\s*[1-4]$", fra_type, re.IGNORECASE):
#             m = re.search(r"\b([1-4])\b", fra_type)
#             fra_type = f"Type {m.group(1)}" if m else None

#         bsa = bool(_to_bool(data.get("bsa_2022_applicable")) or False)

#         return FRAExtractedFeatures(
#             risk_rating                   = _to_str(data.get("risk_rating")),
#             fra_assessment_type           = fra_type,
#             assessment_date               = _to_date(data.get("assessment_date")),
#             assessment_valid_until        = _to_date(data.get("assessment_valid_until")),
#             next_review_date              = _to_date(data.get("next_review_date")),
#             assessor_name                 = _to_str(data.get("assessor_name")),
#             assessor_company              = _to_str(data.get("assessor_company")),
#             assessor_qualification        = _to_str(data.get("assessor_qualification")),
#             responsible_person            = _to_str(data.get("responsible_person")),
#             evacuation_strategy           = evac,
#             evacuation_strategy_changed   = bool(_to_bool(data.get("evacuation_strategy_changed")) or False),
#             evacuation_strategy_notes     = _to_str(data.get("evacuation_strategy_notes")),
#             has_accessibility_needs_noted = bool(_to_bool(data.get("has_accessibility_needs_noted")) or False),
#             has_sprinkler_system          = _to_bool(data.get("has_sprinkler_system")),
#             has_smoke_detection           = _to_bool(data.get("has_smoke_detection")),
#             has_fire_alarm_system         = _to_bool(data.get("has_fire_alarm_system")),
#             has_fire_doors                = _to_bool(data.get("has_fire_doors")),
#             has_compartmentation          = _to_bool(data.get("has_compartmentation")),
#             has_emergency_lighting        = _to_bool(data.get("has_emergency_lighting")),
#             has_fire_extinguishers        = _to_bool(data.get("has_fire_extinguishers")),
#             has_firefighting_shaft        = _to_bool(data.get("has_firefighting_shaft")),
#             has_dry_riser                 = _to_bool(data.get("has_dry_riser")),
#             has_wet_riser                 = _to_bool(data.get("has_wet_riser")),
#             action_items                  = action_items,
#             significant_findings          = significant_findings,
#             bsa_2022_applicable           = bsa,
#             accountable_person_noted      = bool(_to_bool(data.get("accountable_person_noted")) or False),
#             mandatory_occurrence_noted    = bool(_to_bool(data.get("mandatory_occurrence_noted")) or False),
#             extraction_confidence         = _to_float(data.get("extraction_confidence"), default=0.5),
#         )

#     def _empty_features(self, confidence: float = 0.1) -> FRAExtractedFeatures:
#         return FRAExtractedFeatures(
#             risk_rating=None, fra_assessment_type=None,
#             assessment_date=None, assessment_valid_until=None,
#             next_review_date=None, assessor_name=None,
#             assessor_company=None, assessor_qualification=None,
#             responsible_person=None, evacuation_strategy=None,
#             action_items=[], significant_findings=[],
#             extraction_confidence=confidence,
#         )

#     # ── Derived fields ────────────────────────────────────────────────

#     def _normalise_rag_status(self, risk_rating: Optional[str]) -> Optional[str]:
#         if not risk_rating:
#             return None
#         lower = risk_rating.lower().strip()
#         if lower in ("n/a", "not assessed", "unknown", "tbc", "tbd", "none"):
#             return None
#         for kw in ("intolerable", "substantial", "high", "critical", "priority 1",
#                    "very high", "grade e", "grade d", "4/5", "5/5", "serious"):
#             if kw in lower:
#                 return "RED"
#         for kw in ("moderate", "medium", "significant", "tolerable but",
#                    "priority 2", "grade c", "3/5"):
#             if kw in lower:
#                 return "AMBER"
#         for kw in ("trivial", "low", "tolerable", "acceptable", "negligible",
#                    "priority 3", "grade a", "grade b", "1/5", "2/5"):
#             if kw in lower:
#                 return "GREEN"
#         logger.warning("Unknown risk rating '%s' → defaulting to AMBER", risk_rating)
#         return "AMBER"

#     def _compute_is_in_date(self, valid_until: Optional[date]) -> Optional[bool]:
#         if valid_until is None:
#             return None
#         return valid_until >= date.today()

#     def _count_actions(self, action_items: list) -> dict:
#         total         = len(action_items)
#         high_priority = sum(1 for a in action_items if a.priority == "high")
#         overdue       = sum(1 for a in action_items if a.status == "overdue")
#         outstanding   = sum(1 for a in action_items if a.status in ("outstanding", "overdue"))
#         no_date       = sum(1 for a in action_items if not a.due_date)
#         return {
#             "total_action_count":         total,
#             "high_priority_action_count": high_priority,
#             "overdue_action_count":       overdue,
#             "outstanding_action_count":   outstanding,
#             "no_date_action_count":       no_date,
#         }

#     # ── Write to DB ───────────────────────────────────────────────────

#     async def _write_to_db(
#         self,
#         features:         FRAExtractedFeatures,
#         rag_status:       Optional[str],
#         is_in_date:       Optional[bool],
#         action_counts:    dict,
#         upload_id:        str,
#         block_id:         Optional[str],
#         ha_id:            str,
#         s3_path:          str,
#         assessor_company: Optional[str],
#     ) -> tuple:
#         feature_id = str(uuid.uuid4())
#         fra_id     = str(uuid.uuid4())
#         now        = datetime.utcnow()

#         action_items_json = json.dumps([
#             {
#                 "issue_ref":   a.issue_ref,
#                 "description": a.description,
#                 "hazard_type": a.hazard_type,
#                 "priority":    a.priority,
#                 "due_date":    _date_to_str(a.due_date),
#                 "status":      a.status,
#                 "responsible": a.responsible,
#             }
#             for a in features.action_items
#         ])

#         significant_findings_json = json.dumps(features.significant_findings)

#         raw_features_json = json.dumps({
#             "risk_rating":            features.risk_rating,
#             "fra_assessment_type":    features.fra_assessment_type,
#             "assessment_date":        _date_to_str(features.assessment_date),
#             "assessment_valid_until": _date_to_str(features.assessment_valid_until),
#             "evacuation_strategy":    features.evacuation_strategy,
#             "bsa_2022_applicable":    features.bsa_2022_applicable,
#         })

#         async with self.db.transaction():

#             await self.db.execute("""
#                 INSERT INTO silver.document_features (
#                     feature_id, ha_id, upload_id, block_id, document_type,
#                     assessment_date, assessor_company, features_json,
#                     processed_at, created_at, updated_at
#                 )
#                 VALUES ($1, $2, $3::uuid, $4::uuid, 'fra_document', $5, $6,
#                         $7::jsonb, $8, $9, $10)
#                 ON CONFLICT (feature_id) DO NOTHING
#             """,
#                 feature_id, ha_id, upload_id, block_id,
#                 features.assessment_date,
#                 features.assessor_company or assessor_company,
#                 raw_features_json, now, now, now,
#             )

#             await self.db.execute("""
#                 INSERT INTO silver.fra_features (
#                     fra_id, feature_id, ha_id, block_id,
#                     risk_rating, rag_status, fra_assessment_type,
#                     assessment_date, assessment_valid_until, next_review_date, is_in_date,
#                     assessor_name, assessor_company, assessor_qualification, responsible_person,
#                     evacuation_strategy, evacuation_strategy_changed,
#                     evacuation_strategy_notes, has_accessibility_needs_noted,
#                     has_sprinkler_system, has_smoke_detection, has_fire_alarm_system,
#                     has_fire_doors, has_compartmentation, has_emergency_lighting,
#                     has_fire_extinguishers, has_firefighting_shaft, has_dry_riser, has_wet_riser,
#                     action_items, significant_findings,
#                     total_action_count, high_priority_action_count,
#                     overdue_action_count, outstanding_action_count, no_date_action_count,
#                     bsa_2022_applicable, accountable_person_noted, mandatory_occurrence_noted,
#                     extraction_confidence, raw_features, created_at, updated_at
#                 )
#                 VALUES (
#                     $1,$2,$3,$4, $5,$6,$7, $8,$9,$10,$11,
#                     $12,$13,$14,$15, $16,$17,$18,$19,
#                     $20,$21,$22,$23,$24,$25,$26,$27,$28,$29,
#                     $30::jsonb,$31::jsonb,
#                     $32,$33,$34,$35,$36,
#                     $37,$38,$39,$40,$41::jsonb,$42,$43
#                 )
#             """,
#                 fra_id, feature_id, ha_id, block_id,
#                 features.risk_rating, rag_status, features.fra_assessment_type,
#                 features.assessment_date, features.assessment_valid_until,
#                 features.next_review_date, is_in_date,
#                 features.assessor_name, features.assessor_company or assessor_company,
#                 features.assessor_qualification, features.responsible_person,
#                 features.evacuation_strategy, features.evacuation_strategy_changed,
#                 features.evacuation_strategy_notes, features.has_accessibility_needs_noted,
#                 features.has_sprinkler_system, features.has_smoke_detection,
#                 features.has_fire_alarm_system, features.has_fire_doors,
#                 features.has_compartmentation, features.has_emergency_lighting,
#                 features.has_fire_extinguishers, features.has_firefighting_shaft,
#                 features.has_dry_riser, features.has_wet_riser,
#                 action_items_json, significant_findings_json,
#                 action_counts["total_action_count"],
#                 action_counts["high_priority_action_count"],
#                 action_counts["overdue_action_count"],
#                 action_counts["outstanding_action_count"],
#                 action_counts["no_date_action_count"],
#                 features.bsa_2022_applicable, features.accountable_person_noted,
#                 features.mandatory_occurrence_noted, features.extraction_confidence,
#                 raw_features_json, now, now,
#             )

#         return feature_id, fra_id




  ## Best Till Now 

"""
backend/workers/fra_processor.py

Processes Fire Risk Assessment (FRA) documents.
Works with ALL UK FRA formats: Eurosafe, council templates, BAFE reports, narrative prose.

Flow:
  1. Smart-truncate PDF text → fits Groq free tier limits
  2. LLM extraction → structured JSON
  3. Normalise + validate all fields
  4. Write to silver.document_features + silver.fra_features
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class FRAActionItem:
    issue_ref:   Optional[str]
    description: str
    hazard_type: Optional[str]
    priority:    str            # advisory | low | medium | high
    due_date:    Optional[date]
    status:      str            # outstanding | completed | overdue
    responsible: Optional[str]


@dataclass
class FRAExtractedFeatures:
    risk_rating:                   Optional[str]
    fra_assessment_type:           Optional[str]
    assessment_date:               Optional[date]
    assessment_valid_until:        Optional[date]
    next_review_date:              Optional[date]
    assessor_name:                 Optional[str]
    assessor_company:              Optional[str]
    assessor_qualification:        Optional[str]
    responsible_person:            Optional[str]
    evacuation_strategy:           Optional[str]
    evacuation_strategy_changed:   bool = False
    evacuation_strategy_notes:     Optional[str] = None
    has_accessibility_needs_noted: bool = False
    has_sprinkler_system:          Optional[bool] = None
    has_smoke_detection:           Optional[bool] = None
    has_fire_alarm_system:         Optional[bool] = None
    has_fire_doors:                Optional[bool] = None
    has_compartmentation:          Optional[bool] = None
    has_emergency_lighting:        Optional[bool] = None
    has_fire_extinguishers:        Optional[bool] = None
    has_firefighting_shaft:        Optional[bool] = None
    has_dry_riser:                 Optional[bool] = None
    has_wet_riser:                 Optional[bool] = None
    action_items:                  list = field(default_factory=list)
    significant_findings:          list = field(default_factory=list)
    bsa_2022_applicable:           bool = False
    accountable_person_noted:      bool = False
    mandatory_occurrence_noted:    bool = False
    extraction_confidence:         float = 0.5


# ──────────────────────────────────────────────────────────────────────
# LLM Prompt (concise — saves tokens)
# ──────────────────────────────────────────────────────────────────────

# ── Pass 1: metadata prompt (header/systems only — NO actions) ───────────────

FRA_METADATA_PROMPT = """Extract metadata from this UK Fire Risk Assessment excerpt.
Return ONLY valid JSON. Use null for missing fields. Dates: YYYY-MM-DD.

RISK RATING: exact phrase used (e.g. Tolerable, Moderate, Substantial, High, Intolerable).
For council composite ratings use the "Overall Risk from Fire" value.

EVACUATION STRATEGY → one of: stay_put | simultaneous | phased | temporary_evacuation | null

FIRE SYSTEMS — infer true/false from ANY mention:
  Sprinklers/suppression → has_sprinkler_system
  Smoke/heat detectors, AOV → has_smoke_detection
  Fire alarm, call points → has_fire_alarm_system
  Fire doors, FD30/FD60, flat entrance doors (even non-compliant) → has_fire_doors
  Compartmentation, fire stopping → has_compartmentation
  Emergency/escape lighting → has_emergency_lighting
  Fire extinguishers, hose reels → has_fire_extinguishers
  Firefighting shaft, fire lift → has_firefighting_shaft
  DRM / Dry Riser / Dry Rising Main → has_dry_riser
  WRM / Wet Riser / Wet Rising Main → has_wet_riser
NOTE: "DRM and WRM are inspected" → set BOTH dry and wet riser true.

Return ONLY this JSON:
{{
  "risk_rating": "exact phrase or null",
  "fra_assessment_type": "Type 1/2/3/4 ONLY if explicitly stated in doc — else null",
  "assessment_date": "YYYY-MM-DD or null",
  "assessment_valid_until": "YYYY-MM-DD or null",
  "next_review_date": "YYYY-MM-DD or null",
  "assessor_name": "name or null",
  "assessor_company": "company or null",
  "assessor_qualification": "qualifications or null",
  "responsible_person": "person or org or null",
  "evacuation_strategy": "stay_put or simultaneous or phased or temporary_evacuation or null",
  "evacuation_strategy_changed": true or false,
  "evacuation_strategy_notes": "notes or null",
  "has_accessibility_needs_noted": true or false,
  "has_sprinkler_system": true or false or null,
  "has_smoke_detection": true or false or null,
  "has_fire_alarm_system": true or false or null,
  "has_fire_doors": true or false or null,
  "has_compartmentation": true or false or null,
  "has_emergency_lighting": true or false or null,
  "has_fire_extinguishers": true or false or null,
  "has_firefighting_shaft": true or false or null,
  "has_dry_riser": true or false or null,
  "has_wet_riser": true or false or null,
  "bsa_2022_applicable": true or false,
  "accountable_person_noted": true or false,
  "mandatory_occurrence_noted": true or false,
  "extraction_confidence": 0.0 to 1.0
}}

DOCUMENT EXCERPT:
{document_text}"""


# ── Pass 2: actions prompt (action cards / findings only) ────────────────────

FRA_ACTIONS_PROMPT = """Extract action items from this UK Fire Risk Assessment excerpt.
Return ONLY valid JSON. Dates: YYYY-MM-DD or null.

Extract EVERY action/deficiency/recommendation. Common formats:

FORMAT A — Council "Action Ref" cards (Islington, Southwark etc.):
  Action Ref: 0039992
  Action Required: [description]
  Due Date: DD/MM/YYYY
  Responsible: [team]
  Status: OPEN / CLOSED
  → Each Action Ref block = one action_item. "OPEN" = outstanding, "CLOSED" = completed.

FORMAT B — Private assessor cards (Eurosafe etc.):
  Issue Ref: ES/xxxxx/001  Priority: High
  Action Required: [description]

FORMAT C — Table rows: No. | Action | Priority | By When | By Whom | Completed

Priority inference (if not stated):
  high = urgent/immediate/1 month | medium = 3-6 months | low = 12 months | advisory = no date

Hazard types: Housekeeping | Means of Escape | Fire Spread | Detection |
              Signage | Emergency Plans | Fire Service Facilities | Structural | Other

Return ONLY this JSON:
{{
  "action_items": [
    {{
      "issue_ref": "Action Ref number or Issue Ref or null",
      "description": "exact Action Required text",
      "hazard_type": "one of the 9 categories above",
      "priority": "advisory|low|medium|high",
      "due_date": "YYYY-MM-DD or null",
      "status": "outstanding|completed|overdue",
      "responsible": "Responsible team/person or null"
    }}
  ],
  "significant_findings": [
    {{"finding": "description", "location": "location or null", "severity": "high|medium|low"}}
  ],
  "extraction_confidence": 0.0 to 1.0
}}

DOCUMENT EXCERPT:
{document_text}"""


# ──────────────────────────────────────────────────────────────────────
# Type coercion helpers
# ──────────────────────────────────────────────────────────────────────

def _to_date(value: Any) -> Optional[date]:
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
            pass
        s_stripped = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", s, flags=re.IGNORECASE)
        for fmt in ("%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y",
                    "%Y/%m/%d", "%Y.%m.%d", "%d.%m.%Y",
                    "%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y"):
            try:
                return datetime.strptime(s_stripped if s_stripped != s else s, fmt).date()
            except ValueError:
                continue
        logger.warning("Could not parse date: %r", value)
    return None


def _to_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes", "1", "present", "installed", "provided", "fitted"):
            return True
        if v in ("false", "no", "0", "not present", "not installed", "none", "n/a"):
            return False
    return None


def _to_float(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if s.lower() in ("null", "none", "n/a", "unknown", "tbc", "tbd",
                     "not stated", "not applicable", "not available",
                     "not provided", "not assessed", ""):
        return None
    return s


def _date_to_str(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def _normalise_priority(raw: Any) -> str:
    s = (_to_str(raw) or "").lower()
    if s in ("advisory", "low", "medium", "high"):
        return s
    if any(k in s for k in ("high", "urgent", "immediate", "critical", "priority 1", "serious breach")):
        return "high"
    if any(k in s for k in ("medium", "moderate", "priority 2", "3 month", "6 month")):
        return "medium"
    if any(k in s for k in ("advisory", "informational", "best practice", "no timescale")):
        return "advisory"
    return "low"


def _normalise_status(raw: Any) -> str:
    s = (_to_str(raw) or "").lower()
    if any(k in s for k in ("complet", "done", "resolved", "closed", "actioned", "fixed")):
        return "completed"
    if any(k in s for k in ("overdue", "past due", "late", "missed")):
        return "overdue"
    return "outstanding"


def _normalise_hazard_type(raw: Any) -> str:
    VALID = ("Housekeeping", "Means of Escape", "Fire Spread", "Detection",
             "Signage", "Emergency Plans", "Fire Service Facilities", "Structural", "Other")
    s = _to_str(raw)
    if not s:
        return "Other"
    if s in VALID:
        return s
    sl = s.lower()
    if any(k in sl for k in ("housekeep", "storage", "waste", "rubbish", "clutter")):
        return "Housekeeping"
    if any(k in sl for k in ("escape", "exit", "egress", "corridor", "stair")):
        return "Means of Escape"
    if any(k in sl for k in ("spread", "compartment", "cladding", "stopping", "intumescent")):
        return "Fire Spread"
    if any(k in sl for k in ("detect", "alarm", "smoke", "heat", "aov")):
        return "Detection"
    if any(k in sl for k in ("sign", "notice", "label", "marking")):
        return "Signage"
    if any(k in sl for k in ("plan", "procedure", "drill", "assembly")):
        return "Emergency Plans"
    if any(k in sl for k in ("brigade", "riser", "hydrant", "hose", "extinguish", "firefight")):
        return "Fire Service Facilities"
    if any(k in sl for k in ("structural", "construction", "building fabric")):
        return "Structural"
    return "Other"


# ──────────────────────────────────────────────────────────────────────
# FRAProcessor
# ──────────────────────────────────────────────────────────────────────

class FRAProcessor:
    """End-to-end FRA processor. Works with any UK FRA format."""

    def __init__(self, db_conn, llm_client):
        self.db  = db_conn
        self.llm = llm_client
        self.last_raw_response: Optional[str] = None

    async def process(
        self,
        text: str,
        upload_id: str,
        block_id: Optional[str],
        ha_id: str,
        s3_path: str,
        assessor_company: Optional[str] = None,
    ) -> dict[str, Any]:
        logger.info("FRAProcessor.process() upload_id=%s ha_id=%s", upload_id, ha_id)

        raw_json = await self._call_llm(text)
        features = self._parse_llm_response(raw_json)
        logger.info(
            "FRAProcessor parsed: risk=%s rag=%s actions=%d confidence=%.2f",
            features.risk_rating,
            self._normalise_rag_status(features.risk_rating),
            len(features.action_items),
            features.extraction_confidence,
        )

        rag_status    = self._normalise_rag_status(features.risk_rating)
        is_in_date    = self._compute_is_in_date(features.assessment_valid_until)
        action_counts = self._count_actions(features.action_items)

        feature_id, fra_id = await self._write_to_db(
            features=features, rag_status=rag_status, is_in_date=is_in_date,
            action_counts=action_counts, upload_id=upload_id, block_id=block_id,
            ha_id=ha_id, s3_path=s3_path, assessor_company=assessor_company,
        )

        logger.info("FRAProcessor complete: fra_id=%s rag=%s", fra_id, rag_status)
        return {
            "fra_id":                fra_id,
            "feature_id":            feature_id,
            "rag_status":            rag_status,
            "extraction_confidence": features.extraction_confidence,
        }

    # ── LLM call ─────────────────────────────────────────────────────

    async def _call_llm(self, text: str) -> str:
        """
        Two-pass extraction to stay within Groq free tier TPM limits.

        Groq free tier hard limit: 6,000 tokens/minute per request.
        At ~4 chars/token, max safe document chunk = ~18,000 chars.

        Pass 1 — Metadata prompt + first 18K chars of doc
          → Extracts: risk rating, dates, assessor, fire systems, evacuation strategy

        Pass 2 — Actions prompt + last 18K chars of doc
          → Extracts: all action items + significant findings
          → Uses the END of the document because Islington-style FRAs put
            their structured Action Ref cards on the final pages.

        Results are merged into a single JSON response.
        """
        # ~18,000 chars ≈ 4,500 tokens + ~400 token prompt = ~4,900 tokens (under 6K limit)
        CHUNK = 18_000

        # Pass 1: header section for metadata
        meta_chunk = text[:CHUNK]

        # Pass 2: end of document for action cards
        # Islington FRAs: Action Ref cards always at the end
        # Eurosafe FRAs: action cards in the middle — take last CHUNK which
        # typically includes action plan section + end-of-doc summary
        if len(text) > CHUNK:
            actions_chunk = text[-CHUNK:]
        else:
            actions_chunk = text  # short doc — use all of it for both passes

        logger.info(
            "FRAProcessor: two-pass LLM extraction — "
            "meta_chunk=%d chars (chars 0-%d), actions_chunk=%d chars (chars %d-%d)",
            len(meta_chunk), len(meta_chunk),
            len(actions_chunk), max(0, len(text) - CHUNK), len(text),
        )

        # ── Pass 1: metadata ─────────────────────────────────────────
        meta_prompt = FRA_METADATA_PROMPT.format(document_text=meta_chunk)
        try:
            meta_raw = await self.llm.extract(meta_prompt)
            logger.info("Pass 1 (metadata) returned %d chars", len(meta_raw or ""))
        except Exception as exc:
            logger.error("Pass 1 (metadata) failed: %s", exc)
            raise RuntimeError(f"LLM extraction failed (metadata pass): {exc}") from exc

        # ── Pass 2: actions ──────────────────────────────────────────
        actions_prompt = FRA_ACTIONS_PROMPT.format(document_text=actions_chunk)
        try:
            actions_raw = await self.llm.extract(actions_prompt)
            logger.info("Pass 2 (actions) returned %d chars", len(actions_raw or ""))
        except Exception as exc:
            logger.error("Pass 2 (actions) failed: %s", exc)
            raise RuntimeError(f"LLM extraction failed (actions pass): {exc}") from exc

        # ── Merge both responses ─────────────────────────────────────
        merged = self._merge_passes(meta_raw, actions_raw)
        self.last_raw_response = merged
        return merged

    def _merge_passes(self, meta_raw: str, actions_raw: str) -> str:
        """Merge metadata pass + actions pass into one combined JSON string."""
        meta    = self._extract_json(meta_raw)    or {}
        actions = self._extract_json(actions_raw) or {}

        merged = dict(meta)  # all metadata fields from pass 1

        # Actions come from pass 2 (dedicated prompt → more accurate)
        merged["action_items"]         = actions.get("action_items") or meta.get("action_items") or []
        merged["significant_findings"] = actions.get("significant_findings") or meta.get("significant_findings") or []

        # Average confidence
        c1 = float(meta.get("extraction_confidence") or 0.5)
        c2 = float(actions.get("extraction_confidence") or 0.5)
        merged["extraction_confidence"] = round((c1 + c2) / 2, 3)

        logger.info(
            "Merged: risk=%s actions=%d findings=%d confidence=%.3f",
            merged.get("risk_rating"),
            len(merged["action_items"]),
            len(merged["significant_findings"]),
            merged["extraction_confidence"],
        )
        return json.dumps(merged)

    def _smart_truncate(self, text: str, max_chars: int) -> str:
        """
        Section-aware truncation. Budget:
          20% → header (assessor, dates, risk rating)
          65% → action plan / significant findings  ← most important
          15% → fire protection systems
        """
        if len(text) <= max_chars:
            logger.info("smart_truncate: doc fits (%d chars) — sending in full", len(text))
            return text

        logger.warning(
            "smart_truncate: doc too large (%d chars > %d limit) — truncating",
            len(text), max_chars,
        )
        header_budget  = int(max_chars * 0.15)
        action_budget  = int(max_chars * 0.65)
        systems_budget = int(max_chars * 0.10)

        upper = text.upper()

        def find_first(markers: list) -> int:
            hits = [upper.find(m) for m in markers if upper.find(m) != -1]
            return min(hits) if hits else -1

        action_start = find_first([
            "SIGNIFICANT FINDINGS", "ACTION PLAN", "RECOMMENDATIONS",
            "REMEDIAL ACTIONS", "ACTIONS REQUIRED", "IMPROVEMENT ACTIONS",
            "FIRE SAFETY ACTION PLAN", "FIRE SAFETY DEFICIENCIES",
            "DEFICIENCIES AND RECOMMENDATIONS", "ITEMS FOR ACTION",
            "OUTSTANDING ACTIONS", "RECOMMENDED ACTIONS",
            "SECTION 3", "ACTION NO", "ACTION REF",
        ])

        systems_start = find_first([
            "FIRE PROTECTION MEASURES", "MEANS OF ESCAPE",
            "FIRE SAFETY SYSTEMS", "SECTION 5", "SECTION 6",
        ])

        # Header: everything before the action section
        if action_start != -1:
            header = text[:min(action_start, header_budget)]
        else:
            header = text[:header_budget]

        # Action section: the bulk of the budget
        if action_start != -1:
            action = text[action_start : action_start + action_budget]
            logger.info("Smart truncate: action section at char %d, %d chars", action_start, len(action))
        else:
            # Fallback: scan for table column headers
            late_start = find_first([
                "PRIORITY", "BY WHEN", "BY WHOM", "DATE COMPLETED",
                "TIMESCALE", "ACTION REQUIRED", "RECOMMENDED ACTION",
            ])
            if late_start != -1:
                action = text[max(0, late_start - 200) : late_start - 200 + action_budget]
            else:
                # Use second quarter of document
                q = len(text) // 4
                action = text[q : q + action_budget]
                logger.warning("Smart truncate: no action markers found, using mid-doc fallback")

        # Fire systems section
        if systems_start != -1:
            systems = text[systems_start : systems_start + systems_budget]
        else:
            systems = ""

        parts = ["=== HEADER ===", header.strip()]
        if action.strip():
            parts += ["\n\n=== ACTION PLAN / FINDINGS ===", action.strip()]
        if systems.strip():
            parts += ["\n\n=== FIRE SYSTEMS ===", systems.strip()]

        result = "\n".join(parts)
        if len(result) > max_chars:
            result = result[:max_chars]

        logger.info(
            "Smart truncate: %d → %d chars (header=%d action=%d systems=%d)",
            len(text), len(result), len(header), len(action), len(systems),
        )
        return result

    # ── Parse response ────────────────────────────────────────────────

    def _extract_json(self, raw: str) -> Optional[dict]:
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

        # Strategy 2: find outermost { ... }
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(raw[start:end + 1])
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        # Strategy 3: fix common LLM formatting issues
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

        logger.error("JSON parse failed. Raw (500 chars):\n%s", raw[:500])
        return None

    def _parse_llm_response(self, raw_json: str) -> FRAExtractedFeatures:
        data = self._extract_json(raw_json)
        if data is None:
            return self._empty_features(confidence=0.1)

        action_items = []
        for item in data.get("action_items") or []:
            if not isinstance(item, dict):
                continue
            desc = _to_str(item.get("description"))
            if not desc:
                continue
            action_items.append(FRAActionItem(
                issue_ref   = _to_str(item.get("issue_ref")),
                description = desc,
                hazard_type = _normalise_hazard_type(item.get("hazard_type")),
                priority    = _normalise_priority(item.get("priority")),
                due_date    = _to_date(item.get("due_date")),
                status      = _normalise_status(item.get("status")),
                responsible = _to_str(item.get("responsible")),
            ))

        significant_findings = []
        for f in data.get("significant_findings") or []:
            if not isinstance(f, dict):
                continue
            finding = _to_str(f.get("finding"))
            if not finding:
                continue
            severity = _to_str(f.get("severity")) or "low"
            if severity not in ("high", "medium", "low"):
                severity = "low"
            significant_findings.append({
                "finding":  finding,
                "location": _to_str(f.get("location")),
                "severity": severity,
            })

        VALID_EVAC = ("stay_put", "simultaneous", "phased", "temporary_evacuation")
        evac = _to_str(data.get("evacuation_strategy"))
        if evac not in VALID_EVAC:
            evac = None

        fra_type = _to_str(data.get("fra_assessment_type"))
        if fra_type and not re.match(r"^Type\s*[1-4]$", fra_type, re.IGNORECASE):
            m = re.search(r"\b([1-4])\b", fra_type)
            fra_type = f"Type {m.group(1)}" if m else None

        bsa = bool(_to_bool(data.get("bsa_2022_applicable")) or False)

        return FRAExtractedFeatures(
            risk_rating                   = _to_str(data.get("risk_rating")),
            fra_assessment_type           = fra_type,
            assessment_date               = _to_date(data.get("assessment_date")),
            assessment_valid_until        = _to_date(data.get("assessment_valid_until")),
            next_review_date              = _to_date(data.get("next_review_date")),
            assessor_name                 = _to_str(data.get("assessor_name")),
            assessor_company              = _to_str(data.get("assessor_company")),
            assessor_qualification        = _to_str(data.get("assessor_qualification")),
            responsible_person            = _to_str(data.get("responsible_person")),
            evacuation_strategy           = evac,
            evacuation_strategy_changed   = bool(_to_bool(data.get("evacuation_strategy_changed")) or False),
            evacuation_strategy_notes     = _to_str(data.get("evacuation_strategy_notes")),
            has_accessibility_needs_noted = bool(_to_bool(data.get("has_accessibility_needs_noted")) or False),
            has_sprinkler_system          = _to_bool(data.get("has_sprinkler_system")),
            has_smoke_detection           = _to_bool(data.get("has_smoke_detection")),
            has_fire_alarm_system         = _to_bool(data.get("has_fire_alarm_system")),
            has_fire_doors                = _to_bool(data.get("has_fire_doors")),
            has_compartmentation          = _to_bool(data.get("has_compartmentation")),
            has_emergency_lighting        = _to_bool(data.get("has_emergency_lighting")),
            has_fire_extinguishers        = _to_bool(data.get("has_fire_extinguishers")),
            has_firefighting_shaft        = _to_bool(data.get("has_firefighting_shaft")),
            has_dry_riser                 = _to_bool(data.get("has_dry_riser")),
            has_wet_riser                 = _to_bool(data.get("has_wet_riser")),
            action_items                  = action_items,
            significant_findings          = significant_findings,
            bsa_2022_applicable           = bsa,
            accountable_person_noted      = bool(_to_bool(data.get("accountable_person_noted")) or False),
            mandatory_occurrence_noted    = bool(_to_bool(data.get("mandatory_occurrence_noted")) or False),
            extraction_confidence         = _to_float(data.get("extraction_confidence"), default=0.5),
        )

    def _empty_features(self, confidence: float = 0.1) -> FRAExtractedFeatures:
        return FRAExtractedFeatures(
            risk_rating=None, fra_assessment_type=None,
            assessment_date=None, assessment_valid_until=None,
            next_review_date=None, assessor_name=None,
            assessor_company=None, assessor_qualification=None,
            responsible_person=None, evacuation_strategy=None,
            action_items=[], significant_findings=[],
            extraction_confidence=confidence,
        )

    # ── Derived fields ────────────────────────────────────────────────

    def _normalise_rag_status(self, risk_rating: Optional[str]) -> Optional[str]:
        if not risk_rating:
            return None
        lower = risk_rating.lower().strip()
        if lower in ("n/a", "not assessed", "unknown", "tbc", "tbd", "none"):
            return None
        for kw in ("intolerable", "substantial", "high", "critical", "priority 1",
                   "very high", "grade e", "grade d", "4/5", "5/5", "serious"):
            if kw in lower:
                return "RED"
        for kw in ("moderate", "medium", "significant", "tolerable but",
                   "priority 2", "grade c", "3/5"):
            if kw in lower:
                return "AMBER"
        for kw in ("trivial", "low", "tolerable", "acceptable", "negligible",
                   "priority 3", "grade a", "grade b", "1/5", "2/5"):
            if kw in lower:
                return "GREEN"
        logger.warning("Unknown risk rating '%s' → defaulting to AMBER", risk_rating)
        return "AMBER"

    def _compute_is_in_date(self, valid_until: Optional[date]) -> Optional[bool]:
        if valid_until is None:
            return None
        return valid_until >= date.today()

    def _count_actions(self, action_items: list) -> dict:
        total         = len(action_items)
        high_priority = sum(1 for a in action_items if a.priority == "high")
        overdue       = sum(1 for a in action_items if a.status == "overdue")
        outstanding   = sum(1 for a in action_items if a.status in ("outstanding", "overdue"))
        no_date       = sum(1 for a in action_items if not a.due_date)
        return {
            "total_action_count":         total,
            "high_priority_action_count": high_priority,
            "overdue_action_count":       overdue,
            "outstanding_action_count":   outstanding,
            "no_date_action_count":       no_date,
        }

    # ── Write to DB ───────────────────────────────────────────────────

    async def _write_to_db(
        self,
        features:         FRAExtractedFeatures,
        rag_status:       Optional[str],
        is_in_date:       Optional[bool],
        action_counts:    dict,
        upload_id:        str,
        block_id:         Optional[str],
        ha_id:            str,
        s3_path:          str,
        assessor_company: Optional[str],
    ) -> tuple:
        feature_id = str(uuid.uuid4())
        fra_id     = str(uuid.uuid4())
        now        = datetime.utcnow()

        action_items_json = json.dumps([
            {
                "issue_ref":   a.issue_ref,
                "description": a.description,
                "hazard_type": a.hazard_type,
                "priority":    a.priority,
                "due_date":    _date_to_str(a.due_date),
                "status":      a.status,
                "responsible": a.responsible,
            }
            for a in features.action_items
        ])

        significant_findings_json = json.dumps(features.significant_findings)

        raw_features_json = json.dumps({
            "risk_rating":            features.risk_rating,
            "fra_assessment_type":    features.fra_assessment_type,
            "assessment_date":        _date_to_str(features.assessment_date),
            "assessment_valid_until": _date_to_str(features.assessment_valid_until),
            "evacuation_strategy":    features.evacuation_strategy,
            "bsa_2022_applicable":    features.bsa_2022_applicable,
        })

        async with self.db.transaction():

            await self.db.execute("""
                INSERT INTO silver.document_features (
                    feature_id, ha_id, upload_id, block_id, document_type,
                    assessment_date, assessor_company, features_json,
                    processed_at, created_at, updated_at
                )
                VALUES ($1, $2, $3::uuid, $4::uuid, 'fra_document', $5, $6,
                        $7::jsonb, $8, $9, $10)
                ON CONFLICT (feature_id) DO NOTHING
            """,
                feature_id, ha_id, upload_id, block_id,
                features.assessment_date,
                features.assessor_company or assessor_company,
                raw_features_json, now, now, now,
            )

            await self.db.execute("""
                INSERT INTO silver.fra_features (
                    fra_id, feature_id, ha_id, block_id,
                    risk_rating, rag_status, fra_assessment_type,
                    assessment_date, assessment_valid_until, next_review_date, is_in_date,
                    assessor_name, assessor_company, assessor_qualification, responsible_person,
                    evacuation_strategy, evacuation_strategy_changed,
                    evacuation_strategy_notes, has_accessibility_needs_noted,
                    has_sprinkler_system, has_smoke_detection, has_fire_alarm_system,
                    has_fire_doors, has_compartmentation, has_emergency_lighting,
                    has_fire_extinguishers, has_firefighting_shaft, has_dry_riser, has_wet_riser,
                    action_items, significant_findings,
                    total_action_count, high_priority_action_count,
                    overdue_action_count, outstanding_action_count, no_date_action_count,
                    bsa_2022_applicable, accountable_person_noted, mandatory_occurrence_noted,
                    extraction_confidence, raw_features, created_at, updated_at
                )
                VALUES (
                    $1,$2,$3,$4, $5,$6,$7, $8,$9,$10,$11,
                    $12,$13,$14,$15, $16,$17,$18,$19,
                    $20,$21,$22,$23,$24,$25,$26,$27,$28,$29,
                    $30::jsonb,$31::jsonb,
                    $32,$33,$34,$35,$36,
                    $37,$38,$39,$40,$41::jsonb,$42,$43
                )
            """,
                fra_id, feature_id, ha_id, block_id,
                features.risk_rating, rag_status, features.fra_assessment_type,
                features.assessment_date, features.assessment_valid_until,
                features.next_review_date, is_in_date,
                features.assessor_name, features.assessor_company or assessor_company,
                features.assessor_qualification, features.responsible_person,
                features.evacuation_strategy, features.evacuation_strategy_changed,
                features.evacuation_strategy_notes, features.has_accessibility_needs_noted,
                features.has_sprinkler_system, features.has_smoke_detection,
                features.has_fire_alarm_system, features.has_fire_doors,
                features.has_compartmentation, features.has_emergency_lighting,
                features.has_fire_extinguishers, features.has_firefighting_shaft,
                features.has_dry_riser, features.has_wet_riser,
                action_items_json, significant_findings_json,
                action_counts["total_action_count"],
                action_counts["high_priority_action_count"],
                action_counts["overdue_action_count"],
                action_counts["outstanding_action_count"],
                action_counts["no_date_action_count"],
                features.bsa_2022_applicable, features.accountable_person_noted,
                features.mandatory_occurrence_noted, features.extraction_confidence,
                raw_features_json, now, now,
            )

        return feature_id, fra_id





