-- Add UPRN fields to scr_features table
-- Migration: 010_add_scr_uprn_fields.sql

-- Add UPRN columns
ALTER TABLE scr_features
    ADD COLUMN IF NOT EXISTS uprn_labeled VARCHAR(100),
    ADD COLUMN IF NOT EXISTS uprns TEXT[];

-- Add indexes for UPRN queries
CREATE INDEX IF NOT EXISTS idx_scr_features_uprn_labeled ON scr_features(uprn_labeled);
CREATE INDEX IF NOT EXISTS idx_scr_features_uprns ON scr_features USING GIN(uprns);

-- Add comments
COMMENT ON COLUMN scr_features.uprn_labeled IS 'Whatever the document labels as "UPRN" - may be building reference or standard UPRN';
COMMENT ON COLUMN scr_features.uprns IS 'Array of standard 12-digit UPRNs found in the document';
