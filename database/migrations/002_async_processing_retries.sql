-- Async processing retry state for uploads + processing
-- Migration: 002_async_processing_retries.sql

-- Upload audit: track async processing attempts/state
ALTER TABLE upload_audit
    ADD COLUMN IF NOT EXISTS processing_attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS processing_max_attempts INTEGER NOT NULL DEFAULT 5,
    ADD COLUMN IF NOT EXISTS processing_last_error TEXT,
    ADD COLUMN IF NOT EXISTS processing_last_attempt_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS processing_next_attempt_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS processing_completed_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS stepfn_execution_arn TEXT;

CREATE INDEX IF NOT EXISTS idx_upload_audit_next_attempt
    ON upload_audit(processing_next_attempt_at);

-- Processing audit: track retries/attempts per transformation
ALTER TABLE processing_audit
    ADD COLUMN IF NOT EXISTS attempt INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 5,
    ADD COLUMN IF NOT EXISTS last_error TEXT,
    ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS retryable BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS stepfn_execution_arn TEXT;

CREATE INDEX IF NOT EXISTS idx_processing_audit_next_attempt
    ON processing_audit(next_attempt_at);

