# Silver Layer Processor

## Overview

The Silver layer processor is a separate Lambda function that reads extracted features from S3 (`features.json`) and writes them to normalized PostgreSQL tables. This follows the Bronze → Silver → Gold data architecture pattern.

## Architecture

```
S3 Source File Upload
  ↓
EventBridge Rule (filters */file=*)
  ↓
Step Functions State Machine
  ├─ Step 1: Extract PDF (ingestion_worker)
  │   ├─ Extract text/layout
  │   ├─ Extract features
  │   └─ Write artifacts to S3 (extraction.json, features.json, interpretation.json)
  │
  └─ Step 2: Process to Silver (silver_processor) [conditional]
      ├─ Read features.json from S3
      ├─ Parse and normalize features
      └─ Write to PostgreSQL Silver tables
```

## Database Schema

### Base Table: `document_features`
Stores common fields across all document types:
- `feature_id` (UUID, PK)
- `ha_id`, `upload_id`, `document_type`
- `building_name`, `address`, `uprn`, `postcode`
- `assessment_date`, `job_reference`, `client_name`, `assessor_company`
- `features_json` (full JSON for reference)
- Links to `properties` and `blocks` tables

### Document-Specific Tables

1. **`fraew_features`** - FRAEW (PAS 9980:2022) specific:
   - `pas_9980_compliant`, `pas_9980_version`
   - `building_risk_rating` (HIGH/MEDIUM/LOW)
   - `wall_types` (JSONB array)
   - `has_interim_measures`, `has_remedial_actions`

2. **`fra_features`** - Fire Risk Assessment specific
3. **`scr_features`** - Safety Case Report specific
4. **`frsa_features`** - Fire Risk Safety Assessment specific

## Implementation

### Files Created

1. **Database Migration**: `database/migrations/003_silver_document_features.sql`
   - Creates normalized tables for document features
   - Indexes for common queries

2. **Silver Processor**: `backend/workers/silver_processor.py`
   - Lambda function handler
   - Reads `features.json` from S3
   - Normalizes and writes to PostgreSQL
   - Updates `processing_audit` table

3. **Infrastructure**: Updated `infrastructure/aws/cdk/cdk/ingestion_stack.py`
   - Added `SilverProcessorLambda` function
   - Updated Step Functions to chain extraction → silver processing
   - Added conditional logic (only process if extraction succeeded)

### Step Functions Flow

```python
invoke_worker (Extract PDF)
  ↓
Choice: Extraction Succeeded?
  ├─ Yes → invoke_silver (Process to Silver)
  └─ No → Succeed (Skip Silver processing)
```

## Error Handling

- **Retry Logic**: Silver processor has 3 retry attempts with exponential backoff
- **Conditional Execution**: Only runs if extraction succeeded (status: "completed" or "needs_review")
- **Audit Trail**: Updates `processing_audit` with Silver layer status
- **Error Recovery**: If Silver processing fails, extraction artifacts remain in S3 for manual recovery

## Benefits of Separate Step

1. **Separation of Concerns**: Extraction vs. storage logic
2. **Retryability**: Can retry storage without re-extraction
3. **Performance**: Extraction and storage can scale independently
4. **Flexibility**: Easy to add validation/transformation between steps
5. **Architecture Alignment**: Follows Bronze → Silver → Gold pattern

## Usage

The Silver processor is automatically triggered by Step Functions after successful PDF extraction. No manual intervention required.

### Manual Testing

To test the Silver processor manually:

```python
from backend.workers.silver_processor import process_features_to_silver

event = {
    "bucket": "platform-dev-bronze",
    "key": "ha_id=test/bronze/dataset=fraew_document/ingest_date=2024-01-01/submission_id=<uuid>/features.json",
    "execution_arn": "arn:aws:states:..."
}

result = await process_features_to_silver(event)
```

## Future Enhancements
# TODO
- Property/Block linking: Automatically link documents to properties/blocks via UPRN
- Data validation: Add validation rules before writing to Silver
- Multiple storage targets: Write to data warehouse in addition to PostgreSQL
- Feature enrichment: Add external data lookups (e.g., UPRN → property details)
