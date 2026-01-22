-- Add UPRN and postcode to fraew_features for query performance
-- Migration: 004_add_uprn_postcode_to_fraew.sql
--
-- Rationale:
-- - FRAEW features are frequently queried by UPRN/postcode
-- - Denormalization avoids JOINs for common queries
-- - document_features remains the source of truth
-- - These fields are indexed for fast lookups

-- Add UPRN and postcode columns to fraew_features
ALTER TABLE fraew_features
    ADD COLUMN IF NOT EXISTS uprn VARCHAR(12),
    ADD COLUMN IF NOT EXISTS postcode VARCHAR(10);

-- Create indexes for query performance
CREATE INDEX IF NOT EXISTS idx_fraew_features_uprn ON fraew_features(uprn);
CREATE INDEX IF NOT EXISTS idx_fraew_features_postcode ON fraew_features(postcode);

-- Backfill existing data from document_features
UPDATE fraew_features f
SET 
    uprn = df.uprn,
    postcode = df.postcode
FROM document_features df
WHERE f.feature_id = df.feature_id
AND (f.uprn IS NULL OR f.postcode IS NULL);

-- Add comment explaining the denormalization
COMMENT ON COLUMN fraew_features.uprn IS 'Denormalized from document_features for query performance. Source of truth: document_features.uprn';
COMMENT ON COLUMN fraew_features.postcode IS 'Denormalized from document_features for query performance. Source of truth: document_features.postcode';
