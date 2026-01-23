# AWS-first async ingestion (S3 PUT → Step Functions)

## Goal

Make ingestion **asynchronous, robust, and retryable**:

- Upload API is **fast**: store raw files + metadata only.
- Heavy work (PDF extraction/validation/features) runs in a **Step Functions worker** with retries.

## Flow

1. **Client uploads** (batch upload endpoint)
2. API writes:
   - raw file to S3 under the submission prefix
   - `metadata.json` + `manifest.json`
   - `upload_audit` row with `status='queued'`
3. **S3 PUT event** triggers Step Functions execution (EventBridge recommended)
4. Step Functions invokes worker (Lambda/ECS task):
   - fetch source file
   - extract/validate/features
   - write `extraction.json`, `features.json`, `interpretation.json`
   - append manifest
   - update `upload_audit` status + retry fields

## Keying / loop prevention

Only trigger executions for **source file objects**:

- Process keys containing `/file=`
- Ignore sidecars/artifacts:
  - `manifest.json`, `metadata.json`
  - `extraction.json`, `features.json`, `interpretation.json`

## Step Functions definition

See `infrastructure/aws/stepfunctions/pdf_ingestion.asl.json`.

## Worker implementation

Worker entrypoint:
- `backend/workers/stepfn_ingestion_worker.py`

It accepts:
- Step Functions input: `{ "bucket": "...", "key": "...", "execution_arn": "..." }`
- Or an S3 event record (for Lambda testing)

## Database retry state

Migration:
- `database/migrations/002_async_processing_retries.sql`

Adds retry/attempt fields to:
- `upload_audit`
- `processing_audit`

## Recommended AWS wiring

### Option A (recommended): S3 → EventBridge → Step Functions

1. Enable S3 → EventBridge notifications on the bucket.
2. EventBridge rule filters for object created events with key prefix pattern matching `/file=`.
3. Rule target starts the Step Functions state machine, passing:
   - `bucket`
   - `key`

Example EventBridge event pattern (filters **only** source objects by substring match):

```json
{
  "source": ["aws.s3"],
  "detail-type": ["Object Created"],
  "detail": {
    "bucket": {
      "name": ["platform-bronze"]
    },
    "object": {
      "key": [
        { "wildcard": "*\/file=*" }
      ]
    }
  }
}
```

Notes:
- EventBridge supports `wildcard` matching, so `*\/file=*` correctly matches “contains `/file=`”.
- This avoids triggering on `manifest.json` / `metadata.json` / artifacts because those keys do not include `/file=`.

### Option B: S3 → Lambda → Step Functions

Use a small Lambda to start the Step Functions execution, if you prefer S3 notification configuration.

