"""
Agentic feature extraction: PDF text -> Claude on Bedrock -> structured A/B/C features.
"""

from __future__ import annotations

import io
import json
import os
import re
from typing import Any, Dict, Optional

import pdfplumber

from backend.core.agentic.bedrock_client import invoke_claude, BedrockAgenticError
from backend.core.agentic.feature_definitions import get_feature_definitions

# Max chars to send to Claude (leave room for system + JSON output)
_MAX_TEXT_CHARS = 120_000
_MAX_PAGES = 30


def _extract_text_from_pdf(file_bytes: bytes, max_pages: int = _MAX_PAGES) -> str:
    """Extract text from PDF using pdfplumber."""
    parts: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for i, page in enumerate(pdf.pages[:max_pages], start=1):
                try:
                    t = page.extract_text() or ""
                    if t.strip():
                        parts.append(t)
                except Exception:
                    continue
    except Exception:
        pass
    return "\n\n".join(parts)


def _build_extraction_prompt(text: str, feature_definitions: Dict[str, Any]) -> str:
    """Build user prompt for extraction."""
    guidance = feature_definitions.get("extraction_guidance", {})
    conf = guidance.get("confidence_scoring", {})
    evidence = guidance.get("evidence_requirements", {})

    instruct = (
        "Extract building-safety features from the following document text. "
        "Return a single JSON object (no markdown, no code fences) with this structure:\n\n"
        "{\n"
        '  "agentic_features": {\n'
        '    "high_rise_indicators": { ... },\n'
        '    "evacuation_strategy": { ... },\n'
        '    "fire_safety_measures": { ... },\n'
        '    "structural_integrity": { ... },\n'
        '    "maintenance_requirements": { ... },\n'
        '    "building_safety_act_2022": { ... },\n'
        '    "mandatory_occurrence_reports": { ... },\n'
        '    "building_safety_regulator": { ... }\n'
        "  },\n"
        '  "docb_features": {\n'
        '    "claddingType": null | string,\n'
        '    "ewsStatus": null | string,\n'
        '    "fireRiskManagementSummary": null | string,\n'
        '    "docBRef": null | string\n'
        "  }\n"
        "}\n\n"
    )
    if conf:
        instruct += (
            "For each extracted field use: value, confidence (0-1), evidence (short quote) where applicable. "
            "Confidence: explicit_mention 0.9-1.0, strong_inference 0.7-0.9, weak_inference 0.5-0.7; not_found = null.\n\n"
        )
    if evidence:
        instruct += "Include brief evidence (quoted snippet or page ref) for important fields.\n\n"

    instruct += "---\nDocument text:\n\n"
    if len(text) > _MAX_TEXT_CHARS:
        text = text[:_MAX_TEXT_CHARS] + "\n\n[truncated]"
    instruct += text
    return instruct


def _parse_agentic_response(raw: str) -> Dict[str, Any]:
    """Parse JSON from model output; strip code fences if present."""
    s = raw.strip()
    # Strip markdown code block
    for marker in ("```json", "```"):
        if s.startswith(marker):
            s = s[len(marker):].strip()
        if s.endswith("```"):
            s = s[:-3].strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # Try to find first { ... } block
        m = re.search(r"\{[\s\S]*\}", s)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def _normalize_to_contract(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize parsed model output to the features JSON contract:
    - agentic_features: dict with A+B groups
    - docb_features: dict (from docb_features or category_c_docb_planb.docb_required_fields)
    """
    out: Dict[str, Any] = {}

    agentic = parsed.get("agentic_features") or {}
    if isinstance(agentic, dict):
        out["agentic_features"] = agentic

    docb = parsed.get("docb_features")
    if not docb and isinstance(parsed.get("category_c_docb_planb"), dict):
        req = parsed["category_c_docb_planb"].get("docb_required_fields") or {}
        if isinstance(req, dict):
            docb = req
    if isinstance(docb, dict):
        out["docb_features"] = docb

    return out


def extract_features_agentic(
    file_bytes: bytes,
    file_type: str,
    *,
    feature_definitions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extract agentic (A+B) and DocB (C) features from a PDF.

    When USE_AGENTIC_EXTRACTION is not set or false, or when Bedrock is unavailable,
    returns {}. The caller treats {} as "no agentic result" and keeps regex-only.

    Args:
        file_bytes: Raw PDF bytes.
        file_type: Document type (e.g. fra_document, fraew_document).
        feature_definitions: Optional pre-loaded schema; loaded if not provided.

    Returns:
        Dict with optional "agentic_features" and "docb_features" keys,
        conforming to the features JSON contract. Empty dict on disable/error.
    """
    if os.getenv("USE_AGENTIC_EXTRACTION", "").lower() not in ("1", "true", "yes"):
        print("[AGENTIC_AGENT] USE_AGENTIC_EXTRACTION not enabled")
        return {}

    try:
        defs = feature_definitions or get_feature_definitions()
        print(f"[AGENTIC_AGENT] Loaded feature definitions, {len(defs.get('feature_groups', {}))} groups")
    except (FileNotFoundError, ValueError) as e:
        print(f"[AGENTIC_AGENT] Failed to load feature definitions: {e}")
        return {}

    text = _extract_text_from_pdf(file_bytes)
    if not text.strip():
        print("[AGENTIC_AGENT] No text extracted from PDF")
        return {}
    print(f"[AGENTIC_AGENT] Extracted {len(text)} chars from PDF")

    prompt = _build_extraction_prompt(text, defs)
    system = (
        "You are a building safety document analyst. Extract structured data only. "
        "Output valid JSON only, no commentary."
    )

    try:
        print(f"[AGENTIC_AGENT] Invoking Bedrock (model: {os.getenv('BEDROCK_MODEL_ID', 'default')})")
        raw = invoke_claude(prompt, system=system, temperature=0.1)
        print(f"[AGENTIC_AGENT] Bedrock returned {len(raw)} chars")
    except BedrockAgenticError as e:
        print(f"[AGENTIC_AGENT] Bedrock error: {e}")
        return {}

    parsed = _parse_agentic_response(raw)
    print(f"[AGENTIC_AGENT] Parsed response keys: {list(parsed.keys())}")
    result = _normalize_to_contract(parsed)
    print(f"[AGENTIC_AGENT] Normalized result keys: {list(result.keys())}")
    return result
