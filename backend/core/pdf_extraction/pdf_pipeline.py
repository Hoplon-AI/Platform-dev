"""
PDF extraction pipeline:

Document Upload (into S3 correspondent location)
→ Detect if PDF Type (handled upstream in ingestion)
→ IF scanned: Textract (Tables + Forms) (placeholder)
→ Structured JSON (cells, boxes, confidence)
→ Deterministic validation
→ (Optional, placeholder) Agent-assisted interpretation → Human approval
→ Canonical storage of extracted features
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber


PDF_TYPES = {
    "fra_document",
    "frsa_document",
    "fraew_document",
    "scr_document",
}


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
    Best-effort: extract a small text sample for scanned detection + feature mining.
    """
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text_parts: list[str] = []
            for i in range(min(len(pdf.pages), max_pages)):
                t = pdf.pages[i].extract_text() or ""
                if t.strip():
                    text_parts.append(t)
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
) -> PdfArtifacts:
    scanned = detect_scanned_pdf(file_bytes)
    now = _utc_now_iso()

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
    text_sample = _extract_text_sample(file_bytes, max_pages=min(5, max_pages_layout))
    features_core = extract_features_from_text(text_sample)

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

