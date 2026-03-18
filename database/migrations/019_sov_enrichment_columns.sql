-- Migration 019: Add metadata and enrichment tracking columns to silver.properties
-- Required for sov_processor_v2.py enhanced pipeline
-- Adds: metadata JSONB (confidence scores per field), enrichment_status

BEGIN;

-- Confidence metadata per field (JSONB)
ALTER TABLE silver.properties
    ADD COLUMN IF NOT EXISTS metadata          JSONB         DEFAULT '{}';

-- Enrichment pipeline status
ALTER TABLE silver.properties
    ADD COLUMN IF NOT EXISTS enrichment_status VARCHAR(20)   DEFAULT 'pending';
-- Values: pending / enriched / failed / partial

-- Index for enrichment worker (find all pending rows)
CREATE INDEX IF NOT EXISTS idx_properties_enrichment_status
    ON silver.properties (enrichment_status)
    WHERE enrichment_status = 'pending';

-- Index for metadata queries (GIN for JSONB field lookups)
CREATE INDEX IF NOT EXISTS idx_properties_metadata
    ON silver.properties USING GIN (metadata);

COMMIT;