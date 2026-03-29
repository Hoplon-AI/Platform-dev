"""
backend/api/v1/pdf_test_router.py

Test endpoint for FRA / FRAEW PDF extraction.

- Accepts a PDF upload
- Extracts text with pdfplumber
- Sends to LLM (uses LLM_PROVIDER env var — set to 'gemini' to test Gemini)
- Returns the raw LLM JSON response in Swagger
- NO database writes — purely for testing extraction quality
"""

import io
import logging
from typing import Literal

import pdfplumber
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/test", tags=["PDF Test (no DB write)"])


def _extract_text(pdf_bytes: bytes) -> str:
    """Extract all text from PDF using pdfplumber."""
    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            parts = []
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text and text.strip():
                parts.append(text.strip())
            else:
                words = page.extract_words(x_tolerance=3, y_tolerance=3)
                if words:
                    parts.append(" ".join(w["text"] for w in words))
            try:
                for table in page.extract_tables():
                    for row in table:
                        if row:
                            row_text = " | ".join(c.strip() if c else "" for c in row)
                            if row_text.strip(" |"):
                                parts.append(row_text)
            except Exception:
                pass
            if parts:
                pages.append(f"[Page {page_num}]\n" + "\n".join(parts))
    return "\n\n".join(pages)


@router.post(
    "/extract-pdf",
    summary="Test FRA/FRAEW extraction — raw LLM response, no DB write",
    response_class=JSONResponse,
)
async def test_extract_pdf(
    file: UploadFile = File(..., description="FRA or FRAEW PDF file"),
    document_type: Literal["fra", "fraew"] = Query(
        ...,
        description="'fra' = Fire Risk Assessment | 'fraew' = Fire Risk Appraisal of External Walls",
    ),
):
    """
    Upload an FRA or FRAEW PDF and see the raw LLM extraction result.

    - Extracts text from the PDF using pdfplumber
    - Sends to LLM configured via **LLM_PROVIDER** env var
    - Returns the full parsed JSON — **nothing is written to the database**

    Use this to test and compare extraction quality across providers
    (set `LLM_PROVIDER=gemini` to test Gemini, `LLM_PROVIDER=bedrock` for Claude Haiku).
    """
    # Validate file type
    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Extract text
    try:
        text = _extract_text(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {e}")

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted. File may be a scanned/image-only PDF.",
        )

    # Initialise LLM client
    try:
        from backend.workers.llm_client import LLMClient, GEMINI_MODEL, BEDROCK_MODEL_ID, GROQ_MODEL
        import os
        llm = LLMClient.from_env()
        provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
        model_used = {
            "gemini": GEMINI_MODEL,
            "bedrock": BEDROCK_MODEL_ID,
            "groq": GROQ_MODEL,
        }.get(provider, provider)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM client init failed: {e}")

    # Run extraction (two-pass, no DB)
    try:
        if document_type == "fra":
            from backend.workers.fra_processor import FRAProcessor
            processor = FRAProcessor(db_conn=None, llm_client=llm)
            raw_json = await processor._call_llm(text)
            parsed = processor._parse_llm_response(raw_json)
            rag_status = processor._normalise_rag_status(parsed.risk_rating)
            result = {
                "document_type": "fra",
                "provider": provider,
                "model": model_used,
                "filename": filename,
                "text_chars_extracted": len(text),
                "pages_extracted": text.count("[Page "),
                "rag_status": rag_status,
                "extraction_confidence": parsed.extraction_confidence,
                "extracted_fields": {
                    "fra_assessment_type": parsed.fra_assessment_type,
                    "assessment_date": str(parsed.assessment_date) if parsed.assessment_date else None,
                    "assessment_valid_until": str(parsed.assessment_valid_until) if parsed.assessment_valid_until else None,
                    "next_review_date": str(parsed.next_review_date) if parsed.next_review_date else None,
                    "assessor_name": parsed.assessor_name,
                    "assessor_company": parsed.assessor_company,
                    "assessor_qualification": parsed.assessor_qualification,
                    "responsible_person": parsed.responsible_person,
                    "risk_rating": parsed.risk_rating,
                    "evacuation_strategy": parsed.evacuation_strategy,
                    "evacuation_strategy_changed": parsed.evacuation_strategy_changed,
                    "has_sprinkler_system": parsed.has_sprinkler_system,
                    "has_smoke_detection": parsed.has_smoke_detection,
                    "has_fire_alarm_system": parsed.has_fire_alarm_system,
                    "has_fire_doors": parsed.has_fire_doors,
                    "has_compartmentation": parsed.has_compartmentation,
                    "has_emergency_lighting": parsed.has_emergency_lighting,
                    "has_fire_extinguishers": parsed.has_fire_extinguishers,
                    "has_firefighting_shaft": parsed.has_firefighting_shaft,
                    "has_dry_riser": parsed.has_dry_riser,
                    "has_wet_riser": parsed.has_wet_riser,
                    "has_remedial_actions": bool(parsed.action_items),
                    "action_items": [
                        {
                            "issue_ref": a.issue_ref,
                            "description": a.description,
                            "hazard_type": a.hazard_type,
                            "priority": a.priority,
                            "due_date": str(a.due_date) if a.due_date else None,
                            "status": a.status,
                            "responsible": a.responsible,
                        }
                        for a in parsed.action_items
                    ],
                    "significant_findings": parsed.significant_findings,
                    "bsa_2022_applicable": parsed.bsa_2022_applicable,
                    "accountable_person_noted": parsed.accountable_person_noted,
                },
                "raw_llm_response": raw_json,
            }

        else:  # fraew
            from backend.workers.fraew_processor import FRAEWProcessor
            processor = FRAEWProcessor(db_conn=None, llm_client=llm)
            raw_json = await processor._call_llm(text)
            parsed = processor._parse_llm_response(raw_json)
            llm_rag = (processor._extract_json(raw_json) or {}).get("rag_status")
            result_debug = {
                "pass1_raw": processor.last_pass1_response,
                "pass2_raw": processor.last_pass2_response,
            }
            rag_status = processor._normalise_rag_status(parsed.building_risk_rating, llm_rag=llm_rag)
            material_flags = processor._derive_material_flags(parsed.wall_types)
            result = {
                "document_type": "fraew",
                "provider": provider,
                "model": model_used,
                "filename": filename,
                "text_chars_extracted": len(text),
                "pages_extracted": text.count("[Page "),
                "rag_status": rag_status,
                "extraction_confidence": parsed.extraction_confidence,
                "extracted_fields": {
                    "report_reference": parsed.report_reference,
                    "assessment_date": parsed.assessment_date,
                    "assessor_name": parsed.assessor_name,
                    "assessor_company": parsed.assessor_company,
                    "building_risk_rating": parsed.building_risk_rating,
                    "pas_9980_compliant": parsed.pas_9980_compliant,
                    "clause_14_applied": parsed.clause_14_applied,
                    "building_height_m": parsed.building_height_m,
                    "building_height_category": parsed.building_height_category,
                    "num_storeys": parsed.num_storeys,
                    "num_units": parsed.num_units,
                    "wall_types_count": len(parsed.wall_types),
                    "wall_types": [
                        {
                            "type_ref": wt.type_ref,
                            "description": wt.description,
                            "coverage_percent": wt.coverage_percent,
                            "insulation_type": wt.insulation_type,
                            "insulation_combustible": wt.insulation_combustible,
                            "render_type": wt.render_type,
                            "render_combustible": wt.render_combustible,
                            "overall_risk": wt.overall_risk,
                            "remedial_required": wt.remedial_required,
                        }
                        for wt in parsed.wall_types
                    ],
                    "has_combustible_cladding": material_flags.get("has_combustible_cladding"),
                    "eps_insulation_present": material_flags.get("eps_insulation_present"),
                    "has_remedial_actions": parsed.has_remedial_actions,
                    "remedial_actions": parsed.remedial_actions,
                    "interim_measures_required": parsed.interim_measures_required,
                    "cavity_barriers_present": parsed.cavity_barriers_present,
                    "bs8414_test_evidence": parsed.bs8414_test_evidence,
                    "br135_criteria_met": parsed.br135_criteria_met,
                },
                "raw_llm_response": raw_json,
                "debug": result_debug,
            }

    except Exception as e:
        logger.exception("Test extraction failed for %s", filename)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

    return JSONResponse(content=result)
