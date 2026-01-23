"""
PDF extraction pipeline:

Document Upload (into S3 correspondent location)
→ Detect if PDF Type (handled upstream in ingestion)
→ IF scanned: Textract (Tables + Forms) (placeholder)
→ Structured JSON (cells, boxes, confidence)
→ Deterministic validation
→ Document-specific feature extraction (FRAEW, FRA, etc.)
→ (Optional, placeholder) Agent-assisted interpretation → Human approval
→ Canonical storage of extracted features
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber


PDF_TYPES = {
    "fra_document",
    "fraew_document",
    "scr_document",
}


class PDFExtractionError(Exception):
    """Base exception for PDF extraction errors."""
    pass


class PasswordProtectedPDFError(PDFExtractionError):
    """Raised when a PDF is password protected."""
    pass


class CorruptedPDFError(PDFExtractionError):
    """Raised when a PDF file is corrupted or unreadable."""
    pass


class EmptyPDFError(PDFExtractionError):
    """Raised when a PDF has no pages."""
    pass


@dataclass
class FRAEWFeatures:
    """FRAEW-specific extracted features (PAS 9980:2022 documents)."""
    pas_9980_compliant: bool = False
    pas_9980_version: Optional[str] = None
    building_name: Optional[str] = None
    address: Optional[str] = None
    building_risk_rating: Optional[str] = None  # HIGH, MEDIUM, LOW
    assessment_date: Optional[str] = None
    job_reference: Optional[str] = None
    client_name: Optional[str] = None
    assessor_company: Optional[str] = None
    wall_types: List[Dict[str, Any]] = field(default_factory=list)
    has_interim_measures: bool = False
    has_remedial_actions: bool = False


@dataclass(frozen=True)
class PdfArtifacts:
    extraction: Dict[str, Any]
    features: Dict[str, Any]
    interpretation: Dict[str, Any]


def is_pdf_type(file_type: str, filename: str) -> bool:
    return (file_type in PDF_TYPES) or (filename.lower().endswith(".pdf"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_text_sample(file_bytes: bytes, max_pages: int = 3) -> str:
    """
    Best-effort: extract text from PDF pages for scanned detection + feature mining.

    Args:
        file_bytes: Raw PDF bytes
        max_pages: Maximum number of pages to extract text from

    Returns:
        Concatenated text from pages, or empty string on error
    """
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text_parts: list[str] = []
            pages_to_extract = min(len(pdf.pages), max_pages)
            for i in range(pages_to_extract):
                try:
                    t = pdf.pages[i].extract_text() or ""
                    if t.strip():
                        text_parts.append(t)
                except Exception:
                    # Skip pages that fail to extract
                    continue
            return "\n".join(text_parts)
    except Exception:
        return ""


def detect_scanned_pdf(file_bytes: bytes, max_pages: int = 3, min_text_chars: int = 30) -> bool:
    """
    Heuristic: treat as scanned if we cannot extract meaningful text.
    """
    sample = _extract_text_sample(file_bytes, max_pages=max_pages)
    return len(sample.strip()) < min_text_chars


def extract_layout_pdfplumber(
    file_bytes: bytes,
    max_pages: int = 10,
) -> Dict[str, Any]:
    """
    Extract words + their bounding boxes (and a lightweight table view) for digital PDFs.

    Note: pdfplumber does not provide OCR confidence. For digital text we set confidence=1.0.
    """
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages_out: list[dict] = []
        for i, page in enumerate(pdf.pages[:max_pages], start=1):
            # Words include x0/x1/top/bottom and text
            words_raw = page.extract_words(
                use_text_flow=True,
                keep_blank_chars=False,
            ) or []

            words: list[dict] = []
            for w in words_raw:
                # w keys: text, x0, x1, top, bottom, ... (depending on pdfplumber)
                words.append(
                    {
                        "text": w.get("text", ""),
                        "bbox": {
                            "x0": float(w.get("x0", 0.0)),
                            "x1": float(w.get("x1", 0.0)),
                            "top": float(w.get("top", 0.0)),
                            "bottom": float(w.get("bottom", 0.0)),
                        },
                        "confidence": 1.0,
                    }
                )

            # Tables: pdfplumber returns a 2D array of cell strings. Bounding boxes are not stable
            # across PDFs without custom extraction settings. We store cells with row/col only.
            tables = []
            try:
                extracted_tables = page.extract_tables() or []
                for t_idx, table in enumerate(extracted_tables):
                    cells = []
                    for r_idx, row in enumerate(table or []):
                        for c_idx, cell_text in enumerate(row or []):
                            if cell_text is None:
                                continue
                            cells.append(
                                {
                                    "table_index": int(t_idx),
                                    "row": int(r_idx),
                                    "col": int(c_idx),
                                    "text": str(cell_text),
                                    "bbox": None,
                                    "confidence": 1.0,
                                }
                            )
                    tables.append({"table_index": int(t_idx), "cells": cells})
            except Exception:
                # Tables are best-effort; still return words.
                tables = []

            pages_out.append(
                {
                    "page_number": int(i),
                    "width": float(page.width or 0.0),
                    "height": float(page.height or 0.0),
                    "words": words,
                    "tables": tables,
                }
            )

    return {"pages": pages_out}


def textract_placeholder() -> Dict[str, Any]:
    """
    Placeholder for AWS Textract Tables + Forms for scanned PDFs.
    """
    return {
        "provider": "aws_textract",
        "mode": "tables_and_forms",
        "status": "not_implemented",
        "message": "Scanned PDF detected. Textract integration is a placeholder in MVP.",
        "requested_at": _utc_now_iso(),
    }


def extract_features_from_text(text: str) -> Dict[str, Any]:
    """
    Canonical feature extraction (deterministic, lightweight).

    For now we keep it conservative:
    - UPRNs (12 digits)
    - Candidate postcodes (UK-ish heuristic)
    - Candidate dates (ISO-like + common UK formats)
    """
    uprns = sorted(set(re.findall(r"\b\d{12}\b", text)))

    # Very lightweight UK postcode heuristic (not fully exhaustive)
    postcodes = sorted(
        set(
            m.group(0).upper().replace("  ", " ").strip()
            for m in re.finditer(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b", text, flags=re.I)
        )
    )

    # Dates: YYYY-MM-DD or DD/MM/YYYY or DD-MM-YYYY
    dates = sorted(set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{2}[/-]\d{2}[/-]\d{4}\b", text)))

    return {
        "uprns": uprns,
        "postcodes": postcodes,
        "dates": dates,
    }


def extract_fraew_features(text: str) -> Dict[str, Any]:
    """
    Extract FRAEW-specific features from PDF text content.

    FRAEW documents (Fire Risk Appraisal of External Walls) follow PAS 9980:2022
    and contain specific structured information about building fire risk assessments.
    """
    text_lower = text.lower()

    # PAS 9980 compliance detection
    pas_9980_compliant = "pas 9980" in text_lower or "pas9980" in text_lower
    pas_9980_version = None
    pas_match = re.search(r"pas\s*9980[:\s]*(\d{4})", text_lower)
    if pas_match:
        pas_9980_version = pas_match.group(1)
    elif pas_9980_compliant:
        # Default to 2022 if PAS 9980 mentioned but year not specified
        pas_9980_version = "2022"

    # Building risk rating extraction (HIGH, MEDIUM, LOW)
    # Look for patterns like "risk rating is HIGH" or "Building Risk Rating: HIGH"
    building_risk_rating = None
    risk_patterns = [
        r"risk\s+rating[^.]*?(?:is\s+)?(?:therefore\s+)?(?:considered\s+)?(?:as\s+)?(high|medium|low)",
        r"(?:building\s+)?risk\s+rating[:\s]+(high|medium|low)",
        r"rated\s+as[:\s]*(high|medium|low)\s+risk",
        r"[\"'](high|medium|low)[\"']\s+risk\s+(?:rating|outcome|band)",
    ]
    for pattern in risk_patterns:
        match = re.search(pattern, text_lower)
        if match:
            building_risk_rating = match.group(1).upper()
            break

    # Extract wall types and their risk ratings - deduplicate by wall number
    wall_types_dict: Dict[int, Dict[str, Any]] = {}
    # Pattern: "Wall Type N - Name" or similar
    wall_pattern = r"wall\s+type\s+(\d+)[:\s\-]+([A-Za-z\s]+?)(?:\s*[-–]\s*summary|\n)"
    wall_matches = re.finditer(wall_pattern, text_lower)
    for match in wall_matches:
        wall_num = int(match.group(1))
        wall_name = match.group(2).strip().title()
        if wall_num not in wall_types_dict:
            # Try to find risk rating for this wall type
            wall_risk = None
            # Look for risk outcomes like "high" risk outcome or "low" risk
            wall_risk_patterns = [
                rf"wall\s+type\s+{wall_num}[^.]*?[\"'](high|medium|low)[\"']\s+risk",
                rf"wall\s+type\s+{wall_num}[^.]*?based\s+on\s+the\s+[\"']?(high|medium|low)[\"']?\s+risk",
            ]
            for wrp in wall_risk_patterns:
                wall_risk_match = re.search(wrp, text_lower)
                if wall_risk_match:
                    wall_risk = wall_risk_match.group(1).upper()
                    break
            wall_types_dict[wall_num] = {
                "type_number": wall_num,
                "name": wall_name,
                "risk_rating": wall_risk,
            }

    wall_types = list(wall_types_dict.values())

    # Building name extraction - look for "Property" line
    building_name = None
    # Try to find after "Property" label - handle concatenated text
    property_patterns = [
        r"property\n([A-Za-z0-9\s,]+?)(?:\n|client)",
        r"property[:\s]+([A-Za-z]+(?:Court|House|Tower|Building|Place|Square))",
    ]
    for pattern in property_patterns:
        property_match = re.search(pattern, text, re.I)
        if property_match:
            building_name = property_match.group(1).strip()
            # Clean up: take first part before comma if it's a name
            if "," in building_name:
                building_name = building_name.split(",")[0].strip()
            # Handle concatenated text (AuraCourt -> Aura Court)
            building_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", building_name)
            break

    # Job/Reference number extraction
    job_reference = None
    job_match = re.search(r"(?:job\s*(?:nr|no|number|ref)|reference)[:\s\n]+(\d+[-A-Za-z0-9]*)", text, re.I)
    if job_match:
        job_reference = job_match.group(1).strip()

    # Client name extraction - more restrictive to avoid catching extra content
    client_name = None
    client_patterns = [
        r"client\n([A-Za-z0-9\s]+(?:Limited|Ltd|LLP|PLC))",
        r"client[:\s]+([A-Za-z0-9\s]+(?:Limited|Ltd|LLP|PLC))",
    ]
    for pattern in client_patterns:
        client_match = re.search(pattern, text, re.I)
        if client_match:
            client_name = client_match.group(1).strip()
            # Clean up concatenated text
            client_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", client_name)
            break

    # Assessor company extraction
    assessor_company = None
    company_patterns = [
        r"([A-Za-z0-9\s]+(?:Partnership|Consultants)[^.]*?(?:LLP|Ltd))",
        r"(?:undertaken|prepared|produced)\s+by[:\s]+([A-Za-z0-9\s]+(?:Limited|Ltd|LLP|PLC|Consultants))",
    ]
    for pattern in company_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            assessor_company = match.group(1).strip()
            break

    # Assessment date - look for Issue Date or specific date references
    assessment_date = None
    date_patterns = [
        r"(?:issue\s*date|assessment\s*date|dated)\n(\d{2}[/-]\d{2}[/-]\d{4})",
        r"(?:issue\s*date|assessment\s*date|dated)[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})",
    ]
    for pattern in date_patterns:
        date_match = re.search(pattern, text, re.I)
        if date_match:
            date_str = date_match.group(1)
            # Convert to ISO format if DD/MM/YYYY
            if "/" in date_str or "-" in date_str:
                parts = re.split(r"[/-]", date_str)
                if len(parts) == 3 and len(parts[2]) == 4:
                    assessment_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
            break

    # Check for interim measures and remedial actions sections
    has_interim_measures = "interim measures" in text_lower
    has_remedial_actions = "remedial actions" in text_lower or "remedial works" in text_lower

    return {
        "pas_9980_compliant": pas_9980_compliant,
        "pas_9980_version": pas_9980_version,
        "building_name": building_name,
        "building_risk_rating": building_risk_rating,
        "assessment_date": assessment_date,
        "job_reference": job_reference,
        "client_name": client_name,
        "assessor_company": assessor_company,
        "wall_types": wall_types,
        "has_interim_measures": has_interim_measures,
        "has_remedial_actions": has_remedial_actions,
    }


def extract_fra_features(text: str) -> Dict[str, Any]:
    """
    Extract FRA-specific features from PDF text content.

    FRA documents (Fire Risk Assessment) contain structured information about fire safety
    assessments for buildings, following the Regulatory Reform (Fire Safety) Order 2005.
    They use a 5-level risk rating: Trivial, Tolerable, Moderate, Substantial, Intolerable.
    """
    text_lower = text.lower()

    # Risk rating extraction - FRA uses 5-level scale
    # Trivial < Tolerable < Moderate < Substantial < Intolerable
    overall_risk_rating = None
    risk_patterns = [
        r"overall[:\s]+(trivial|tolerable|moderate|substantial|intolerable)",
        r"(?:overall\s+)?risk[:\s]+(?:is\s+)?(trivial|tolerable|moderate|substantial|intolerable)",
        r"risk\s+(?:rating|level|assessment)[:\s]*(trivial|tolerable|moderate|substantial|intolerable)",
        # Handle "risk rating is considered to be X" patterns
        r"risk\s+rating\s+(?:is\s+)?(?:considered\s+(?:to\s+be\s+)?|deemed\s+)?(trivial|tolerable|moderate|substantial|intolerable)",
        # Handle "Risk Assessment Level: X" patterns
        r"risk\s+assessment\s+level[:\s]*(trivial|tolerable|moderate|substantial|intolerable)",
    ]
    for pattern in risk_patterns:
        match = re.search(pattern, text_lower)
        if match:
            overall_risk_rating = match.group(1).upper()
            break

    # Also check for simplified HIGH/MEDIUM/LOW ratings (some FRAs use this)
    if not overall_risk_rating:
        simple_risk_patterns = [
            r"(?:overall\s+)?risk\s+(?:rating|level)[:\s]*(high|medium|low)",
            r"fire\s+risk[:\s]+(high|medium|low)",
        ]
        for pattern in simple_risk_patterns:
            match = re.search(pattern, text_lower)
            if match:
                overall_risk_rating = match.group(1).upper()
                break

    # Extract individual risk area ratings
    risk_areas: Dict[str, Optional[str]] = {}
    risk_area_names = [
        "identifying people at risk",
        "people at risk",
        "fire hazards",
        "fire protection measures",
        "fire protection",
        "management of fire safety",
        "management",
    ]
    for area in risk_area_names:
        # Look for patterns like "Fire Hazards: Moderate" or "Fire Hazards √ Moderate"
        area_pattern = rf"{area}[:\s√✓]*\s*(trivial|tolerable|moderate|substantial|intolerable)"
        match = re.search(area_pattern, text_lower)
        if match:
            # Normalize area name
            normalized_area = area.replace(" ", "_")
            if normalized_area not in risk_areas:
                risk_areas[normalized_area] = match.group(1).upper()

    # Building/premises name extraction
    building_name = None
    building_patterns = [
        r"(?:premises|site|property)[:\s]+([A-Za-z0-9\s,\-]+?)(?:\n|assessed|client|telephone)",
        r"fire\s+risk\s+assessment[^:]*?:\s*([A-Za-z0-9\s,\-]+?)(?:\n|contents|page)",
        r"for\n([A-Za-z0-9\s,\-]+?)(?:\n|colchester|assessed|client)",
    ]
    for pattern in building_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            building_name = match.group(1).strip()
            # Clean up: take meaningful part
            if len(building_name) > 100:
                building_name = building_name[:100]
            # Handle concatenated text
            building_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", building_name)
            break

    # Address extraction
    address = None
    address_patterns = [
        r"(?:site|premises|address)[:\s]+([A-Za-z0-9\s,\-]+?(?:Road|Street|Lane|Avenue|Close|Drive|Way)[^.]*?)(?:\n|telephone|client)",
        r"for\n([A-Za-z0-9\s,\-]+?)(?:\n\n|postcode|assessed)",
    ]
    for pattern in address_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            address = match.group(1).strip()
            break

    # Assessment type extraction (Type 1, 2, 3, 4)
    assessment_type = None
    type_match = re.search(r"(?:risk\s+assessment\s+)?type[:\s]+(\d+)[^.]*?(?:common|flats|intrusive|full)", text, re.I)
    if type_match:
        type_num = type_match.group(1)
        type_desc_match = re.search(rf"type\s+{type_num}\s*[-–:]\s*([^.]+)", text, re.I)
        if type_desc_match:
            assessment_type = f"Type {type_num} - {type_desc_match.group(1).strip()}"
        else:
            assessment_type = f"Type {type_num}"

    # Assessor extraction
    assessor_name = None
    assessor_patterns = [
        r"(?:assessed|assessor|consultant)[:\s]+(?:by\s+)?([A-Z][a-z]+\s+[A-Z][a-z]+)",
        r"risk\s+assessment\s+consultant[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)",
    ]
    for pattern in assessor_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            assessor_name = match.group(1).strip()
            break

    # Assessor company extraction
    assessor_company = None
    company_patterns = [
        r"(?:eurosafe|tersus|fire\s+safety)[^.]*?(?:ltd|limited|uk|consultancy)",
        r"(?:undertaken|prepared|produced|carried\s+out)\s+by[:\s]+([A-Za-z0-9\s]+(?:Limited|Ltd|LLP|PLC|UK))",
    ]
    for pattern in company_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            assessor_company = match.group(0).strip() if match.lastindex is None else match.group(1).strip()
            break

    # Client name extraction
    client_name = None
    client_patterns = [
        r"(?:on\s+behalf\s+of|client)[:\s]+([A-Za-z0-9\s]+(?:Homes|Council|Housing|Limited|Ltd|Association))",
        r"client[:\s]+([A-Za-z0-9\s]+?)(?:\n|client\s+contact|telephone)",
    ]
    for pattern in client_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            client_name = match.group(1).strip()
            # Clean up concatenated text
            client_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", client_name)
            break

    # Assessment date extraction
    assessment_date = None
    date_patterns = [
        r"date\s+assessed[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})",
        r"date\s+assessed[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})",
        r"assessment\s+date[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})",
        r"assessed\s+on[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            date_str = match.group(1)
            # Convert text date to ISO format
            assessment_date = _convert_text_date_to_iso(date_str)
            if not assessment_date:
                assessment_date = date_str  # Keep original if conversion fails
            break

    # Review date extraction
    review_date = None
    review_patterns = [
        r"review\s+date[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})",
        r"review\s+date[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})",
        r"next\s+review[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})",
    ]
    for pattern in review_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            date_str = match.group(1)
            review_date = _convert_text_date_to_iso(date_str)
            if not review_date:
                review_date = date_str
            break

    # Evacuation strategy detection
    evacuation_strategy = None
    if "stay put" in text_lower or "stay-put" in text_lower:
        evacuation_strategy = "STAY_PUT"
    elif "simultaneous evacuation" in text_lower or "full evacuation" in text_lower:
        evacuation_strategy = "SIMULTANEOUS"
    elif "phased evacuation" in text_lower:
        evacuation_strategy = "PHASED"
    elif "defend in place" in text_lower:
        evacuation_strategy = "DEFEND_IN_PLACE"

    # Compliance indicators
    fso_compliant = (
        "regulatory reform (fire safety) order" in text_lower
        or "fire safety order 2005" in text_lower
        or "rr(fs)o" in text_lower
    )
    housing_act_compliant = (
        "housing act 2004" in text_lower
        or "lacors" in text_lower
    )

    # Key sections detection
    has_significant_findings = "significant findings" in text_lower
    has_action_plan = "action plan" in text_lower
    has_fire_hazards_section = "fire hazards" in text_lower
    has_management_section = "management of fire safety" in text_lower

    return {
        "overall_risk_rating": overall_risk_rating,
        "risk_areas": risk_areas if risk_areas else None,
        "building_name": building_name,
        "address": address,
        "assessment_type": assessment_type,
        "assessment_date": assessment_date,
        "review_date": review_date,
        "assessor_name": assessor_name,
        "assessor_company": assessor_company,
        "client_name": client_name,
        "evacuation_strategy": evacuation_strategy,
        "fso_compliant": fso_compliant,
        "housing_act_compliant": housing_act_compliant,
        "has_significant_findings": has_significant_findings,
        "has_action_plan": has_action_plan,
        "has_fire_hazards_section": has_fire_hazards_section,
        "has_management_section": has_management_section,
    }


def _convert_text_date_to_iso(date_str: str) -> Optional[str]:
    """
    Convert text date format (e.g., '8th February 2023') to ISO format.
    """
    import calendar

    # Month name mapping
    months = {name.lower(): num for num, name in enumerate(calendar.month_name) if name}
    months.update({name.lower(): num for num, name in enumerate(calendar.month_abbr) if name})

    # Try parsing "8th February 2023" format
    match = re.match(r"(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\s+(\d{4})", date_str, re.I)
    if match:
        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = int(match.group(3))
        month = months.get(month_name)
        if month:
            return f"{year:04d}-{month:02d}-{day:02d}"

    # Try parsing DD/MM/YYYY or DD-MM-YYYY
    match = re.match(r"(\d{2})[/-](\d{2})[/-](\d{4})", date_str)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"

    return None


def _check_pdf_accessible(file_bytes: bytes) -> None:
    """
    Check if PDF is accessible (not password-protected, not corrupted).

    Raises:
        PasswordProtectedPDFError: If PDF is password protected
        CorruptedPDFError: If PDF is corrupted or unreadable
        EmptyPDFError: If PDF has no pages
    """
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if len(pdf.pages) == 0:
                raise EmptyPDFError("PDF has no pages")
            # Try to access first page to verify it's readable
            _ = pdf.pages[0].extract_text()
    except EmptyPDFError:
        raise
    except Exception as e:
        error_str = str(e).lower()
        if "password" in error_str or "encrypted" in error_str:
            raise PasswordProtectedPDFError(f"PDF is password protected: {e}")
        elif "syntax" in error_str or "invalid" in error_str or "corrupt" in error_str:
            raise CorruptedPDFError(f"PDF is corrupted or invalid: {e}")
        else:
            raise CorruptedPDFError(f"Unable to read PDF: {e}")


def validate_extraction(extraction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic validation of the structured JSON output.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(extraction, dict):
        return {"is_valid": False, "errors": ["extraction is not an object"], "warnings": []}

    pages = extraction.get("pages")
    if not isinstance(pages, list) or not pages:
        errors.append("pages is missing or empty")
        return {"is_valid": False, "errors": errors, "warnings": warnings}

    for p in pages:
        if not isinstance(p, dict):
            errors.append("page entry is not an object")
            continue
        width = float(p.get("width") or 0.0)
        height = float(p.get("height") or 0.0)
        words = p.get("words") or []
        if not isinstance(words, list):
            errors.append("words is not a list")
            continue
        if width <= 0 or height <= 0:
            warnings.append("page dimensions missing (width/height)")
        for w in words[:5000]:  # bound validation cost
            bbox = (w or {}).get("bbox") if isinstance(w, dict) else None
            if not isinstance(bbox, dict):
                errors.append("word bbox missing/invalid")
                break
            try:
                x0 = float(bbox.get("x0"))
                x1 = float(bbox.get("x1"))
                top = float(bbox.get("top"))
                bottom = float(bbox.get("bottom"))
            except Exception:
                errors.append("word bbox values not numeric")
                break
            if x1 < x0 or bottom < top:
                errors.append("word bbox has inverted coordinates")
                break
            if width > 0 and (x0 < -1 or x1 > width + 1):
                warnings.append("word bbox out of page width bounds")
            if height > 0 and (top < -1 or bottom > height + 1):
                warnings.append("word bbox out of page height bounds")

    return {"is_valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def agent_assisted_interpretation_placeholder(
    file_type: str,
    extraction_s3_key: str,
    features_s3_key: str,
) -> Dict[str, Any]:
    """
    Placeholder for an agent-assisted step that must be human-approved before use.
    """
    return {
        "status": "placeholder",
        "requires_human_approval": True,
        "approved": False,
        "proposed_at": _utc_now_iso(),
        "inputs": {
            "file_type": file_type,
            "extraction_s3_key": extraction_s3_key,
            "features_s3_key": features_s3_key,
        },
        "proposal": None,
        "approval": None,
    }


def build_pdf_artifacts(
    file_bytes: bytes,
    *,
    file_type: str,
    filename: str,
    max_pages_layout: int = 10,
    max_pages_features: int = 15,
) -> PdfArtifacts:
    """
    Build extraction, features, and interpretation artifacts from a PDF.

    Args:
        file_bytes: Raw PDF file bytes
        file_type: Document type (fra_document, fraew_document, etc.)
        filename: Original filename
        max_pages_layout: Max pages to extract layout from
        max_pages_features: Max pages to extract features from (FRAEW needs more pages)

    Returns:
        PdfArtifacts with extraction, features, and interpretation dicts

    Raises:
        PasswordProtectedPDFError: If PDF is password protected
        CorruptedPDFError: If PDF is corrupted
        EmptyPDFError: If PDF has no pages
    """
    now = _utc_now_iso()

    # Pre-check for accessibility issues
    _check_pdf_accessible(file_bytes)

    scanned = detect_scanned_pdf(file_bytes)

    if scanned:
        extraction = {
            "schema_version": "pdf-extraction/v1",
            "extracted_at": now,
            "document": {"filename": filename, "file_type": file_type},
            "scanned": True,
            "method": "textract_placeholder",
            "textract": textract_placeholder(),
            "pages": [],
        }
        validation = {"is_valid": True, "errors": [], "warnings": ["scanned PDF: no layout extracted in MVP"]}
        extraction["validation"] = validation

        features = {
            "schema_version": "pdf-features/v1",
            "extracted_at": now,
            "document": {"filename": filename, "file_type": file_type},
            "scanned": True,
            "features": {},
        }

        # interpretation placeholder filled later once we know S3 keys
        interpretation = {
            "status": "placeholder",
            "requires_human_approval": True,
            "approved": False,
            "proposed_at": now,
            "inputs": None,
            "proposal": None,
            "approval": None,
        }
        return PdfArtifacts(extraction=extraction, features=features, interpretation=interpretation)

    layout = extract_layout_pdfplumber(file_bytes, max_pages=max_pages_layout)
    validation = validate_extraction(layout)

    # Build a text sample for canonical features
    # Use more pages for feature extraction since key info may be spread out
    text_sample = _extract_text_sample(file_bytes, max_pages=max_pages_features)
    features_core = extract_features_from_text(text_sample)

    # Add document-specific features based on file_type
    if file_type == "fraew_document":
        fraew_specific = extract_fraew_features(text_sample)
        features_core["fraew_specific"] = fraew_specific
    elif file_type == "fra_document":
        fra_specific = extract_fra_features(text_sample)
        features_core["fra_specific"] = fra_specific

    extraction = {
        "schema_version": "pdf-extraction/v1",
        "extracted_at": now,
        "document": {"filename": filename, "file_type": file_type},
        "scanned": False,
        "method": "pdfplumber",
        **layout,
        "validation": validation,
    }

    features = {
        "schema_version": "pdf-features/v1",
        "extracted_at": now,
        "document": {"filename": filename, "file_type": file_type},
        "scanned": False,
        "features": features_core,
    }

    interpretation = {
        "status": "placeholder",
        "requires_human_approval": True,
        "approved": False,
        "proposed_at": now,
        "inputs": None,
        "proposal": None,
        "approval": None,
    }

    return PdfArtifacts(extraction=extraction, features=features, interpretation=interpretation)


def json_dumps(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=False).encode("utf-8")

