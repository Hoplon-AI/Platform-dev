# Agentic Feature Extraction – Implementation Thinking

This document captures the reasoning, plan, and decisions for implementing the missing phases of the Bedrock Agentic Feature Extraction plan.

---

## 1. What’s Already Done (No Work Here)

- **Feature definitions**: `schemas/agentic-feature-definitions.json` – Categories A (ML/UI), B (compliance/workflow), C (DocB/PlanB); types, enums, extraction hints, confidence rules.
- **Specs**: `docs/BUILDING_SAFETY_FEATURE_SPECIFICATIONS.md` – Field-level specs.
- **Storage**:  
  - Migration 006: `building_safety_features`, `docb_features`; `document_features` gains `agentic_features_json`, `extraction_method`, `extraction_comparison_metadata`.  
  - Migration 007: 10 gold views.  
- **Silver processor**: `_write_building_safety_features`, `_write_docb_features`, `_update_document_features_with_agentic`; wired into `process_features_to_silver` and reading from the features JSON contract below.

---

## 2. Features JSON Contract (What We Must Produce)

The silver layer and gold views expect:

- **Agentic (A+B)**:  
  - In `features_json.agentic_features` or `features_json["features"].get("agentic_features")`.  
  - Groups: `high_rise_indicators`, `evacuation_strategy`, `fire_safety_measures`, `structural_integrity`, `maintenance_requirements`, `building_safety_act_2022`, `mandatory_occurrence_reports`, `building_safety_regulator`.
- **DocB (C)**:  
  - In `features_json.docb_features` or `features.docb_features` or `features.agentic_features.category_c_docb_planb.docb_required_fields` (and optional context).
- **Metadata**:  
  - `extraction_method`: `"regex"` | `"agentic"` | `"merged"`.  
  - `extraction_comparison_metadata`: e.g. `agreement_score`, `discrepancies`.

The agentic extractor and merge step must emit this structure so the existing silver processor works unchanged.

---

## 3. Pending Phases and Decisions

### 3.1 Bedrock Infrastructure (CDK)

- **Where**: Add to **IngestionStack** only (no new stack). The ingestion Lambda already does PDF → extraction → features; we’ll optionally add agentic in the same process.
- **What**:  
  - IAM: `bedrock:InvokeModel` (and optionally `InvokeModelWithResponseStream`) on  
    `arn:aws:bedrock:${region}::foundation-model/anthropic.claude-*` (or a specific model ID, e.g. `anthropic.claude-3-5-sonnet-*`).  
  - No new Lambda: reuse **Ingestion Worker Lambda**.  
  - No new Lambda layer for Bedrock: `boto3` in the Lambda runtime already includes `bedrock-runtime`; we only need IAM.
- **Model**: Prefer `anthropic.claude-3-5-sonnet-*-v2` or `anthropic.claude-3-haiku-*` for cost/latency. Make it configurable via `BEDROCK_MODEL_ID` (or similar) env var.

---

### 3.2 Agentic Extractor (Backend)

**3.2.1 `backend/core/agentic/feature_definitions.py`**

- Load and validate `schemas/agentic-feature-definitions.json`.  
- Resolve path: try relative to `__file__` (e.g. `../../../../schemas/agentic-feature-definitions.json` from `backend/core/agentic/`), then fallback to `os.getcwd()/schemas/` or `$SCHEMAS_PATH` for Lambda/tests.  
- API:  
  - `get_feature_definitions() -> dict` (full JSON).  
  - `get_features_for_document_type(document_type: str) -> dict` – for now return the same schema for all PDF types; we can later filter by `document_type` if the schema adds type-specific sections.  
- Validation: require `feature_groups`, `extraction_guidance`; optional `extraction_metadata`.

**3.2.2 `backend/core/agentic/bedrock_client.py`**

- Thin wrapper around `boto3.client("bedrock-runtime").invoke_model()`.  
- `invoke_claude(prompt: str, *, model_id: str | None, max_tokens: int, temperature: float) -> str` (response text).  
- Use Claude’s Messages API format: ` AnthropicModelID, body with `messages`, `max_tokens`, `temperature`.  
- `model_id` from env `BEDROCK_MODEL_ID` or default e.g. `anthropic.claude-3-5-sonnet-v2`.  
- Handle `ResourceNotFoundException`, `ValidationException`, `ThrottlingException` and raise a small `BedrockAgenticError` (or similar) for the caller.

**3.2.3 `backend/core/agentic/extraction_agent.py`**

- **Input**: `extract_features_agentic(file_bytes: bytes, file_type: str, feature_definitions: dict | None = None) -> dict`.  
- **Text**: Extract text from the PDF inside this module (e.g. `pdfplumber`), up to N pages (e.g. 25–30) to stay within context and time. Reuse the same pattern as `_extract_text_sample` in `pdf_pipeline` (or a shared helper) so we don’t duplicate heavy logic.  
- **Chunking**: For MVP, one request: truncate text to ~100–120k chars to leave room for system prompt + JSON output. If we later hit token limits, we can chunk and merge (e.g. by section or pages).  
- **Prompt**:  
  - System: “You extract building-safety features from PDF text. Return valid JSON only. Follow the schema provided.”  
  - User: (1) Short extraction guidance from `feature_definitions` (confidence rules, evidence requirements); (2) A simplified “target schema” for the A/B/C groups we care about (enough for the model to produce the right shape); (3) The text (or truncated text).  
- **Output**: Parse JSON from the response (strip markdown code fences if present). Validate that we have at least the top-level keys we need (`agentic_features` with the expected groups, and `docb_features` or `category_c_docb_planb`). Normalise into the **features JSON contract** (see §2): e.g. map `category_c_docb_planb.docb_required_fields` into `docb_features` at the top level.  
- **Value/confidence/evidence**: The schema says each field can have `value`, `confidence`, `evidence`. The agent’s raw output may use different keys; we normalise to that structure where possible. For storage, the silver processor already accepts the groups as dicts; nested `value`/`confidence`/`evidence` can live inside those dicts.  
- **Feature-flag / no-op**: If `feature_definitions` is missing or Bedrock is disabled (env `USE_AGENTIC_EXTRACTION=false` or not set), return `{}` or a structure that the merge step treats as “no agentic result,” so the pipeline stays regex-only.

---

### 3.3 Comparison / Merge (`backend/core/agentic/comparison_engine.py`)

- **Inputs**:  
  - `regex_features`: dict from the existing `build_pdf_artifacts` features (at least `features` and any top-level keys we need to preserve).  
  - `agentic_result`: dict from `extract_features_agentic` already normalised to the contract (including `agentic_features` and `docb_features`).
- **Functions**:  
  - `compare_extractions(regex: dict, agentic: dict) -> dict`:  
    - For each comparable field (we define a small mapping: e.g. `evacuation_strategy` ↔ `features.fra_specific.evacuation_strategy` or `features.agentic_features.evacuation_strategy`), compute agreement.  
    - Return `{ "agreement_score": float, "discrepancies": [ { "field", "regex_value", "agentic_value", "score" } ] }`.  
  - `calculate_agreement_score(field: str, regex_val, agentic_val) -> float`:  
    - 1.0 if both missing or both equal (normalising strings). Slightly lower for type coercion (e.g. `"STAY_PUT"` vs `"Stay Put"`). 0.0 for clearly conflicting.  
  - `identify_discrepancies(regex: dict, agentic: dict) -> list`:  
    - Use the same field mapping as `compare_extractions`; return list of `{ "field", "regex_value", "agentic_value" }` where `calculate_agreement_score` is below a threshold (e.g. 0.9).  
- **Merge**:  
  - `merge_extractions(regex: dict, agentic: dict, comparison: dict) -> dict`:  
    - Start from a copy of `regex` (preserve `schema_version`, `extracted_at`, `document`, `scanned`, `features`).  
    - Overlay `agentic_features` and `docb_features` from `agentic`.  
    - Where both exist and disagree, prefer by confidence: if agentic gives `confidence` and it’s higher than an implicit regex confidence (e.g. 0.7), use agentic; else keep regex. If no confidence, prefer agentic for agentic-specific groups, regex for document-specific (e.g. `fraew_specific`, `fra_specific`).  
    - Set `extraction_method = "merged"` and `extraction_comparison_metadata = comparison`.  
    - If `agentic` is empty, leave `extraction_method` as `"regex"` and do not add `extraction_comparison_metadata`.

---

### 3.4 Pipeline / Worker Integration

- **Where to run agentic and merge**: In the **Step Functions ingestion worker** (`stepfn_ingestion_worker`), **after** `build_pdf_artifacts` and **before** writing `features.json` to S3. This keeps `pdf_pipeline` free of Bedrock and boto3, and all PDF-related orchestration in one place.  
- **Flow**:  
  1. `build_pdf_artifacts(file_bytes, file_type=..., filename=...)` → `artifacts` (extraction, features, interpretation).  
  2. If `USE_AGENTIC_EXTRACTION` is not truthy: write `artifacts.features` as today; done.  
  3. If truthy:  
     - `agentic_result = extract_features_agentic(file_bytes, file_type)`  
     - If `agentic_result` is non-empty:  
       - `comparison = compare_extractions(artifacts.features, agentic_result)`  
       - `artifacts.features = merge_extractions(artifacts.features, agentic_result, comparison)`  
     - Else: keep `artifacts.features` as-is, `extraction_method` remains `"regex"`.  
  4. Write `artifacts.extraction`, `artifacts.features`, `artifacts.interpretation` to S3 (same keys as today).  
- **Env**: `USE_AGENTIC_EXTRACTION=true` in the ingestion Lambda when we want agentic; default `false` so existing and local flows stay regex-only.  
- **Error handling**: If `extract_features_agentic` or Bedrock fails, we should **not** fail the whole run: log, set `extraction_method="regex"`, and write the regex-only `artifacts.features`. Optionally put `extraction_comparison_metadata = { "agentic_error": "..." }` for observability.

---

### 3.5 Step Functions and Async Worker

- **State machine**: The CDK defines the machine in code; `pdf_ingestion.asl.json` appears to be a stale or reference definition. We will **not** change the high-level shape for now:  
  - `ProcessPdf` (ingestion Lambda) → `Choice(ExtractionSucceeded)` → `ProcessToSilver` or `Succeed(ExtractionFailed)`.  
- **No new states**: Agentic and merge run **inside** the existing `ProcessPdf` Lambda. A future “parallel branch” (separate Agentic Lambda + Merge Lambda) can be added later if we need to scale or isolate Bedrock.  
- **Silver processor**: Unchanged. It already reads `extraction_method`, `extraction_comparison_metadata`, `agentic_features`, and `docb_features` from the features JSON.

---

### 3.6 Ingestion Stack CDK (Concrete Changes)

- **Ingestion Worker Lambda**:  
  - Add IAM:  
    - `bedrock:InvokeModel` on  
      `arn:aws:bedrock:${AWS::Region}::foundation-model/anthropic.claude-*`.  
    - If we want to restrict to one model:  
      `arn:aws:bedrock:${AWS::Region}::foundation-model/anthropic.claude-3-5-sonnet-*`.  
  - Env:  
    - `USE_AGENTIC_EXTRACTION` = `"false"` by default; set to `"true"` in a deploy config when enabling.  
    - `BEDROCK_MODEL_ID` = `"anthropic.claude-3-5-sonnet-v2"` (or leave unset to use code default).  
- **Layers**: Still only the existing `worker_deps_layer` (asyncpg, pdfplumber). Add `boto3` only if the runtime doesn’t provide it; it does, so no change.

---

## 4. File and Dependency Summary

**New files**

- `backend/core/agentic/__init__.py`  
- `backend/core/agentic/feature_definitions.py`  
- `backend/core/agentic/bedrock_client.py`  
- `backend/core/agentic/extraction_agent.py`  
- `backend/core/agentic/comparison_engine.py`  

**Modified**

- `backend/workers/stepfn_ingestion_worker.py`: after `build_pdf_artifacts`, optional agentic + merge, then write.  
- `infrastructure/aws/cdk/cdk/ingestion_stack.py`: Bedrock IAM for ingestion Lambda; `USE_AGENTIC_EXTRACTION`, `BEDROCK_MODEL_ID`.

**Unchanged**

- `backend/core/pdf_extraction/pdf_pipeline.py`  
- `infrastructure/aws/stepfunctions/pdf_ingestion.asl.json` (reference only)  
- `backend/workers/silver_processor.py`  
- `infrastructure/aws/cdk/app.py`  
- `infrastructure/aws/cdk/lambda_layers/ingestion_worker/requirements.txt` (boto3 not added)

---

## 5. Testing and Local / No-Bedrock Behaviour

- **Unit tests**:  
  - `feature_definitions`: load from a fixture or the real schema path in repo.  
  - `bedrock_client`: mock `boto3.client("bedrock-runtime").invoke_model` and assert `invoke_claude` returns the parsed text.  
  - `extraction_agent`: mock `invoke_claude`; pass short text and a minimal `feature_definitions`; assert structure (e.g. `agentic_features`, `docb_features`) and that we don’t raise on empty/Bedrock-disabled.  
  - `comparison_engine`: `compare_extractions`, `merge_extractions` with fixed `regex` and `agentic` dicts; assert `extraction_method`, `extraction_comparison_metadata`, and that overwrites follow the stated rules.  
- **Integration**: With `USE_AGENTIC_EXTRACTION=false`, the worker behaves as today. With `true` and a Bedrock-enabled env, we’d need a small PDF and possibly mocked Bedrock or a dev account.  
- **Local / no Bedrock**: If `USE_AGENTIC_EXTRACTION` is false or Bedrock is unavailable, `extract_features_agentic` returns `{}` (or the no-op structure), and `merge_extractions` leaves regex-only; all existing tests and local runs keep working.

---

## 6. Order of Implementation

1. **Bedrock infra (CDK)**: IAM + env vars on the ingestion Lambda.  
2. **Agentic package**:  
   - `feature_definitions`  
   - `bedrock_client`  
   - `extraction_agent` (including in-agentic text extraction and normalisation to the contract).  
3. **Comparison engine**: `compare_extractions`, `identify_discrepancies`, `merge_extractions`.  
4. **Worker**: Wire `USE_AGENTIC_EXTRACTION`, call agentic + merge, and error handling.  
5. **Tests**: Unit for agentic and comparison; keep existing silver and ingestion tests green.

---

## 7. Open Points (For Later)

- **Parallel SFN branch**: If we need to run agentic in a separate Lambda (e.g. to isolate failures or to use a different memory/timeout), we’d add an extra state and a Merge state; the merge would read from two S3 objects. Not in scope for this pass.  
- **Chunking**: If documents exceed our current token budget, we need a chunking strategy and a merge of per-chunk agentic outputs.  
- **Model and region**: `BEDROCK_MODEL_ID` and region (inherited from Lambda env) should be validated (e.g. model exists in that region) in a health-check or startup, not in the hot path.  
- **Cost and quotas**: Bedrock per-request and per-model quotas; consider circuit-breaker or fallback to regex-only when throttled.

---

*Document generated to capture implementation thinking for the Bedrock Agentic Feature Extraction plan. Update as decisions change.*
