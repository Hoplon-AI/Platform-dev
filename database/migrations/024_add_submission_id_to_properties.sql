-- Migration 024: Add submission_id to silver.properties
-- This column tracks which upload (upload_audit.upload_id) each property row came from.

ALTER TABLE silver.properties
    ADD COLUMN IF NOT EXISTS submission_id UUID REFERENCES upload_audit(upload_id);

CREATE INDEX IF NOT EXISTS idx_properties_submission_id
    ON silver.properties(submission_id);

CREATE INDEX IF NOT EXISTS idx_properties_ha_submission
    ON silver.properties(ha_id, submission_id);
