# """
# backend/api/v1/pdf_test_router.py

# Test endpoint — upload a real FRA or FRAEW PDF, see the LLM response
# in Swagger, and store the result in the database.

# Swagger URL:  http://localhost:8000/docs
# Endpoint:     POST /api/v1/test/extract-pdf
# """

# import decimal
# import hashlib
# import io
# import json
# import logging
# import os
# import uuid
# from datetime import date, datetime, timezone
# from typing import Any, Literal

# import pdfplumber
# from fastapi import APIRouter, File, HTTPException, UploadFile
# from fastapi.responses import JSONResponse

# from backend.core.database.db_pool import DatabasePool

# logger = logging.getLogger(__name__)

# router = APIRouter(prefix="/api/v1/test", tags=["PDF Test"])

# HA_ID = os.getenv("DEV_HA_ID", "ha_demo")


# # ─────────────────────────────────────────────────────────────────────
# # JSON serialisation helper — handles all DB / Python types
# # ─────────────────────────────────────────────────────────────────────

# def _make_serializable(obj: Any) -> Any:
#     """
#     Recursively convert any non-JSON-serializable value into a
#     JSON-safe equivalent.  Handles:
#       - decimal.Decimal  → float
#       - date / datetime  → ISO string
#       - bytes            → hex string
#       - sets             → sorted list
#       - Anything else    → str() fallback
#     """
#     if obj is None:
#         return None
#     if isinstance(obj, bool):
#         return obj
#     if isinstance(obj, decimal.Decimal):
#         return float(obj)
#     if isinstance(obj, datetime):
#         return obj.isoformat()
#     if isinstance(obj, date):
#         return obj.isoformat()
#     if isinstance(obj, bytes):
#         return obj.hex()
#     if isinstance(obj, dict):
#         return {str(k): _make_serializable(v) for k, v in obj.items()}
#     if isinstance(obj, (list, tuple)):
#         return [_make_serializable(v) for v in obj]
#     if isinstance(obj, set):
#         return sorted(_make_serializable(v) for v in obj)
#     if isinstance(obj, (int, float, str)):
#         return obj
#     # Fallback for any other type (UUID, Enum, custom objects, etc.)
#     return str(obj)


# # ─────────────────────────────────────────────────────────────────────
# # PDF text extraction — multiple strategies for robustness
# # ─────────────────────────────────────────────────────────────────────

# def extract_text_from_pdf(pdf_bytes: bytes) -> str:
#     """
#     Extract all text from a PDF using pdfplumber.

#     Strategy:
#       1. extract_text() — standard text layer
#       2. extract_words() — fallback for complex layouts
#       3. extract_tables() — capture tabular data as text too
#     """
#     pages = []

#     with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
#         for page_num, page in enumerate(pdf.pages, start=1):
#             page_text_parts = []

#             # Strategy 1: standard text extraction
#             text = page.extract_text(x_tolerance=3, y_tolerance=3)
#             if text and text.strip():
#                 page_text_parts.append(text.strip())

#             # Strategy 2: word-level extraction (catches some complex layouts)
#             if not page_text_parts:
#                 words = page.extract_words(x_tolerance=3, y_tolerance=3)
#                 if words:
#                     word_text = " ".join(w["text"] for w in words)
#                     if word_text.strip():
#                         page_text_parts.append(word_text.strip())

#             # Strategy 3: also extract tables and append as structured text
#             try:
#                 tables = page.extract_tables()
#                 for table in tables:
#                     for row in table:
#                         if row:
#                             row_text = " | ".join(
#                                 cell.strip() if cell else ""
#                                 for cell in row
#                             )
#                             if row_text.strip(" |"):
#                                 page_text_parts.append(row_text)
#             except Exception:
#                 pass  # Tables are optional — don't fail if extraction breaks

#             if page_text_parts:
#                 pages.append(f"[Page {page_num}]\n" + "\n".join(page_text_parts))

#     return "\n\n".join(pages)


# # ─────────────────────────────────────────────────────────────────────
# # Helper: ensure ha_demo exists and register upload in upload_audit
# # ─────────────────────────────────────────────────────────────────────

# async def ensure_ha_and_register_upload(
#     conn,
#     upload_id: uuid.UUID,
#     file_type: str,
#     filename: str,
#     pdf_bytes: bytes,
# ) -> None:
#     # Ensure the HA row exists
#     await conn.execute(
#         "INSERT INTO housing_associations (ha_id, name) "
#         "VALUES ($1, 'Demo Housing Association') ON CONFLICT (ha_id) DO NOTHING",
#         HA_ID,
#     )

#     # Register upload so silver_processor / processors can look it up
#     checksum = hashlib.sha256(pdf_bytes).hexdigest()
#     s3_key   = f"ha_id={HA_ID}/test/upload_id={upload_id}/file={filename}"

#     await conn.execute(
#         """
#         INSERT INTO upload_audit
#             (upload_id, ha_id, file_type, filename, s3_key,
#              checksum, file_size, user_id, status)
#         VALUES ($1, $2, $3, $4, $5, $6, $7, 'swagger_test', 'processing')
#         ON CONFLICT (upload_id) DO NOTHING
#         """,
#         upload_id, HA_ID, file_type, filename,
#         s3_key, checksum, len(pdf_bytes),
#     )


# # ─────────────────────────────────────────────────────────────────────
# # Main endpoint
# # ─────────────────────────────────────────────────────────────────────

# @router.post(
#     "/extract-pdf",
#     summary="Upload FRA or FRAEW PDF → Groq LLM → Store in DB",
#     description="""
# Upload your own FRA or FRAEW PDF.

# The API will:
# 1. Extract all text from the PDF (handles complex layouts, tables, multi-column)
# 2. Send it to Groq LLM with the extraction prompt
# 3. Store the result in the database (silver.fra_features or silver.fraew_features)
# 4. Return the full LLM response so you can see exactly what was extracted

# **document_type**: `fra` or `fraew`

# No auth needed in DEV_MODE.
#     """,
# )
# async def extract_pdf(
#     document_type: Literal["fra", "fraew"],
#     file: UploadFile = File(..., description="Upload your FRA or FRAEW PDF"),
# ):
#     # ── Validate file type ────────────────────────────────────
#     if not file.filename or not file.filename.lower().endswith(".pdf"):
#         raise HTTPException(status_code=400, detail="Only PDF files are accepted")

#     # ── Read PDF bytes ────────────────────────────────────────
#     pdf_bytes = await file.read()
#     if len(pdf_bytes) == 0:
#         raise HTTPException(status_code=400, detail="Uploaded file is empty")

#     logger.info("PDF test: %s type=%s size=%d bytes", file.filename, document_type, len(pdf_bytes))

#     # ── Extract text ──────────────────────────────────────────
#     try:
#         text = extract_text_from_pdf(pdf_bytes)
#     except Exception as e:
#         raise HTTPException(status_code=422, detail=f"Could not read PDF: {e}")

#     if not text.strip():
#         raise HTTPException(
#             status_code=422,
#             detail=(
#                 "No text could be extracted from this PDF. "
#                 "It may be a scanned/image-only document. "
#                 "Please provide a text-based PDF."
#             )
#         )

#     logger.info("Extracted %d chars from %s", len(text), file.filename)

#     # ── Create LLM client ─────────────────────────────────────
#     try:
#         from backend.workers.llm_client import LLMClient
#         llm = LLMClient.from_env()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"LLM client error: {e}")

#     # ── Call LLM + store in DB ────────────────────────────────
#     upload_id = uuid.uuid4()
#     file_type = f"{document_type}_document"

#     pool = DatabasePool.get_pool()
#     async with pool.acquire() as conn:

#         # Ensure HA and upload_audit rows exist
#         await ensure_ha_and_register_upload(
#             conn, upload_id, file_type, file.filename, pdf_bytes
#         )

#         raw_llm_response = None
#         processor        = None

#         try:
#             if document_type == "fra":
#                 from backend.workers.fra_processor import FRAProcessor
#                 processor = FRAProcessor(conn, llm)
#                 result = await processor.process(
#                     text      = text,
#                     upload_id = str(upload_id),
#                     block_id  = None,
#                     ha_id     = HA_ID,
#                     s3_path   = f"test/{file.filename}",
#                 )
#             else:  # fraew
#                 from backend.workers.fraew_processor import FRAEWProcessor
#                 processor = FRAEWProcessor(conn, llm)
#                 result = await processor.process(
#                     text      = text,
#                     upload_id = str(upload_id),
#                     block_id  = None,
#                     ha_id     = HA_ID,
#                     s3_path   = f"test/{file.filename}",
#                 )

#             raw_llm_response = getattr(processor, "last_raw_response", None)

#         except Exception as e:
#             if processor is not None:
#                 raw_llm_response = getattr(processor, "last_raw_response", None)

#             logger.exception("Processor failed")
#             return JSONResponse(
#                 status_code=500,
#                 content=_make_serializable({
#                     "status":           "failed",
#                     "error":            str(e),
#                     "error_type":       type(e).__name__,
#                     "raw_llm_response": raw_llm_response,
#                     "text_preview":     text[:500] if text else None,
#                     "hint": (
#                         "If raw_llm_response is null, the LLM call itself failed. "
#                         "Otherwise the DB write failed. "
#                         "Check text_preview to see what was extracted from the PDF."
#                     ),
#                 }),
#             )

#         # ── Read back what was stored in the DB ───────────────
#         feature_id = uuid.UUID(result["feature_id"])

#         if document_type == "fra":
#             db_row = await conn.fetchrow(
#                 """
#                 SELECT
#                     risk_rating, rag_status, fra_assessment_type,
#                     assessment_date, assessment_valid_until, is_in_date,
#                     assessor_name, assessor_company, assessor_qualification,
#                     responsible_person, evacuation_strategy,
#                     has_sprinkler_system, has_smoke_detection, has_fire_alarm_system,
#                     has_fire_doors, has_compartmentation, has_emergency_lighting,
#                     has_fire_extinguishers, has_firefighting_shaft,
#                     has_dry_riser, has_wet_riser,
#                     total_action_count, high_priority_action_count,
#                     outstanding_action_count, overdue_action_count,
#                     bsa_2022_applicable, accountable_person_noted,
#                     extraction_confidence,
#                     action_items, significant_findings
#                 FROM silver.fra_features
#                 WHERE feature_id = $1
#                 """,
#                 feature_id,
#             )
#         else:
#             db_row = await conn.fetchrow(
#                 """
#                 SELECT
#                     risk_rating, rag_status,
#                     assessment_date, assessment_valid_until, is_in_date,
#                     assessor_name, assessor_company,
#                     building_height_m, height_category,
#                     has_combustible_cladding, eps_insulation_present,
#                     pir_insulation_present, mineral_wool_insulation_present,
#                     timber_cladding_present, acrylic_render_present,
#                     aluminium_composite_cladding, hpl_cladding_present,
#                     adb_compliant, evacuation_strategy_recommendation,
#                     extraction_confidence,
#                     wall_types
#                 FROM silver.fraew_features
#                 WHERE feature_id = $1
#                 """,
#                 feature_id,
#             )

#     if db_row is None:
#         raise HTTPException(
#             status_code=500,
#             detail="DB write succeeded but row not found on read-back"
#         )

#     # ── Deserialise JSONB columns ─────────────────────────────
#     stored = dict(db_row)
#     for jsonb_col in ("action_items", "significant_findings", "wall_types"):
#         if jsonb_col in stored and isinstance(stored[jsonb_col], str):
#             try:
#                 stored[jsonb_col] = json.loads(stored[jsonb_col])
#             except Exception:
#                 pass

#     # ── Build and return response — fully serializable ────────
#     return JSONResponse(content=_make_serializable({
#         "status":               "success",
#         "document_type":        document_type,
#         "upload_id":            str(upload_id),
#         "feature_id":           str(feature_id),
#         "filename":             file.filename,
#         "text_chars_extracted": len(text),
#         "text_preview":         text[:300],   # first 300 chars so you can verify extraction
#         "raw_llm_response":     raw_llm_response,
#         "stored_in_db":         stored,
#     }))


"""
backend/api/v1/pdf_test_router.py

Test endpoint — upload a real FRA or FRAEW PDF, see the LLM response
in Swagger, and store the result in the database.

Swagger URL:  http://localhost:8000/docs
Endpoint:     POST /api/v1/test/extract-pdf
"""

import decimal
import hashlib
import io
import json
import logging
import os
import uuid
from datetime import date, datetime, timezone
from typing import Any, Literal

import pdfplumber
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from backend.core.database.db_pool import DatabasePool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/test", tags=["PDF Test"])

HA_ID = os.getenv("DEV_HA_ID", "ha_demo")


# ─────────────────────────────────────────────────────────────────────
# JSON serialisation helper — handles all DB / Python types
# ─────────────────────────────────────────────────────────────────────

def _make_serializable(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, set):
        return sorted(_make_serializable(v) for v in obj)
    if isinstance(obj, (int, float, str)):
        return obj
    return str(obj)


# ─────────────────────────────────────────────────────────────────────
# PDF text extraction
# ─────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    pages = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text_parts = []

            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text and text.strip():
                page_text_parts.append(text.strip())

            if not page_text_parts:
                words = page.extract_words(x_tolerance=3, y_tolerance=3)
                if words:
                    word_text = " ".join(w["text"] for w in words)
                    if word_text.strip():
                        page_text_parts.append(word_text.strip())

            try:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            row_text = " | ".join(
                                cell.strip() if cell else ""
                                for cell in row
                            )
                            if row_text.strip(" |"):
                                page_text_parts.append(row_text)
            except Exception:
                pass

            if page_text_parts:
                pages.append(f"[Page {page_num}]\n" + "\n".join(page_text_parts))

    return "\n\n".join(pages)


# ─────────────────────────────────────────────────────────────────────
# Helper: ensure ha_demo exists and register upload
# ─────────────────────────────────────────────────────────────────────

async def ensure_ha_and_register_upload(
    conn,
    upload_id: uuid.UUID,
    file_type: str,
    filename: str,
    pdf_bytes: bytes,
) -> None:
    await conn.execute(
        "INSERT INTO housing_associations (ha_id, name) "
        "VALUES ($1, 'Demo Housing Association') ON CONFLICT (ha_id) DO NOTHING",
        HA_ID,
    )

    checksum = hashlib.sha256(pdf_bytes).hexdigest()
    s3_key   = f"ha_id={HA_ID}/test/upload_id={upload_id}/file={filename}"

    await conn.execute(
        """
        INSERT INTO upload_audit
            (upload_id, ha_id, file_type, filename, s3_key,
             checksum, file_size, user_id, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'swagger_test', 'processing')
        ON CONFLICT (upload_id) DO NOTHING
        """,
        upload_id, HA_ID, file_type, filename,
        s3_key, checksum, len(pdf_bytes),
    )


# ─────────────────────────────────────────────────────────────────────
# Main endpoint
# ─────────────────────────────────────────────────────────────────────

@router.post(
    "/extract-pdf",
    summary="Upload FRA or FRAEW PDF → Groq LLM → Store in DB",
    description="""
Upload your own FRA or FRAEW PDF.

The API will:
1. Extract all text from the PDF (handles complex layouts, tables, multi-column)
2. Send it to Groq LLM with the extraction prompt
3. Store the result in the database (silver.fra_features or silver.fraew_features)
4. Return the full LLM response so you can see exactly what was extracted

**document_type**: `fra` or `fraew`

No auth needed in DEV_MODE.
    """,
)
async def extract_pdf(
    document_type: Literal["fra", "fraew"],
    file: UploadFile = File(..., description="Upload your FRA or FRAEW PDF"),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    logger.info("PDF test: %s type=%s size=%d bytes", file.filename, document_type, len(pdf_bytes))

    try:
        text = extract_text_from_pdf(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {e}")

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "No text could be extracted from this PDF. "
                "It may be a scanned/image-only document. "
                "Please provide a text-based PDF."
            )
        )

    logger.info("Extracted %d chars from %s", len(text), file.filename)

    try:
        from backend.workers.llm_client import LLMClient
        llm = LLMClient.from_env()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM client error: {e}")

    upload_id = uuid.uuid4()
    file_type = f"{document_type}_document"

    pool = DatabasePool.get_pool()
    async with pool.acquire() as conn:

        await ensure_ha_and_register_upload(
            conn, upload_id, file_type, file.filename, pdf_bytes
        )

        raw_llm_response = None
        processor        = None

        try:
            if document_type == "fra":
                from backend.workers.fra_processor import FRAProcessor
                processor = FRAProcessor(conn, llm)
                result = await processor.process(
                    text      = text,
                    upload_id = str(upload_id),
                    block_id  = None,
                    ha_id     = HA_ID,
                    s3_path   = f"test/{file.filename}",
                )
            else:  # fraew
                from backend.workers.fraew_processor import FRAEWProcessor
                processor = FRAEWProcessor(conn, llm)
                result = await processor.process(
                    text      = text,
                    upload_id = str(upload_id),
                    block_id  = None,
                    ha_id     = HA_ID,
                    s3_path   = f"test/{file.filename}",
                )

            raw_llm_response = getattr(processor, "last_raw_response", None)

        except Exception as e:
            if processor is not None:
                raw_llm_response = getattr(processor, "last_raw_response", None)

            logger.exception("Processor failed")
            return JSONResponse(
                status_code=500,
                content=_make_serializable({
                    "status":           "failed",
                    "error":            str(e),
                    "error_type":       type(e).__name__,
                    "raw_llm_response": raw_llm_response,
                    "text_preview":     text[:500] if text else None,
                    "hint": (
                        "If raw_llm_response is null, the LLM call itself failed. "
                        "Otherwise the DB write failed. "
                        "Check text_preview to see what was extracted from the PDF."
                    ),
                }),
            )

        # ── Read back what was stored in the DB ───────────────
        feature_id = uuid.UUID(result["feature_id"])

        if document_type == "fra":
            db_row = await conn.fetchrow(
                """
                SELECT
                    risk_rating, rag_status, fra_assessment_type,
                    assessment_date, assessment_valid_until, is_in_date,
                    assessor_name, assessor_company, assessor_qualification,
                    responsible_person, evacuation_strategy,
                    has_sprinkler_system, has_smoke_detection, has_fire_alarm_system,
                    has_fire_doors, has_compartmentation, has_emergency_lighting,
                    has_fire_extinguishers, has_firefighting_shaft,
                    has_dry_riser, has_wet_riser,
                    total_action_count, high_priority_action_count,
                    outstanding_action_count, overdue_action_count,
                    bsa_2022_applicable, accountable_person_noted,
                    extraction_confidence,
                    action_items, significant_findings
                FROM silver.fra_features
                WHERE feature_id = $1
                """,
                feature_id,
            )
        else:  # fraew — column names match silver.fraew_features schema
            db_row = await conn.fetchrow(
                """
                SELECT
                    building_risk_rating, rag_status,
                    assessment_date, assessment_valid_until, is_in_date,
                    assessor_name, assessor_company,
                    building_height_m, building_height_category,
                    has_combustible_cladding, eps_insulation_present,
                    pir_insulation_present, mineral_wool_insulation_present,
                    timber_cladding_present, acrylic_render_present,
                    aluminium_composite_cladding, hpl_cladding_present,
                    adb_compliant, evacuation_strategy,
                    extraction_confidence,
                    wall_types
                FROM silver.fraew_features
                WHERE feature_id = $1
                """,
                feature_id,
            )

    if db_row is None:
        raise HTTPException(
            status_code=500,
            detail="DB write succeeded but row not found on read-back"
        )

    stored = dict(db_row)
    for jsonb_col in ("action_items", "significant_findings", "wall_types"):
        if jsonb_col in stored and isinstance(stored[jsonb_col], str):
            try:
                stored[jsonb_col] = json.loads(stored[jsonb_col])
            except Exception:
                pass

    return JSONResponse(content=_make_serializable({
        "status":               "success",
        "document_type":        document_type,
        "upload_id":            str(upload_id),
        "feature_id":           str(feature_id),
        "filename":             file.filename,
        "text_chars_extracted": len(text),
        "text_preview":         text[:300],
        "raw_llm_response":     raw_llm_response,
        "stored_in_db":         stored,
    }))