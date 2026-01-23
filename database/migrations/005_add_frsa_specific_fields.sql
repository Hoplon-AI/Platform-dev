-- Add FRSA-specific fields to frsa_features table
-- Migration: 005_add_frsa_specific_fields.sql
--
-- Adds structured fields for FRSA (Fire Risk Safety Assessment) documents
-- Similar to FRAEW features, but focused on fire safety compliance

-- Add FRSA-specific columns
ALTER TABLE frsa_features
    ADD COLUMN IF NOT EXISTS assessment_valid_until DATE,
    ADD COLUMN IF NOT EXISTS building_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS address TEXT,
    ADD COLUMN IF NOT EXISTS job_reference VARCHAR(100),
    ADD COLUMN IF NOT EXISTS client_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS assessor_company VARCHAR(255),
    ADD COLUMN IF NOT EXISTS has_fire_safety_measures BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS has_emergency_procedures BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS has_maintenance_requirements BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS fso_compliant BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS fire_safety_act_compliant BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS uprn VARCHAR(12),
    ADD COLUMN IF NOT EXISTS postcode VARCHAR(10);

-- Create indexes for query performance
CREATE INDEX IF NOT EXISTS idx_frsa_features_risk_rating ON frsa_features(risk_rating);
CREATE INDEX IF NOT EXISTS idx_frsa_features_assessment_valid_until ON frsa_features(assessment_valid_until);
CREATE INDEX IF NOT EXISTS idx_frsa_features_uprn ON frsa_features(uprn);
CREATE INDEX IF NOT EXISTS idx_frsa_features_postcode ON frsa_features(postcode);
CREATE INDEX IF NOT EXISTS idx_frsa_features_fso_compliant ON frsa_features(fso_compliant);

-- Add comments explaining the fields
COMMENT ON COLUMN frsa_features.risk_rating IS 'Overall fire risk rating (HIGH, MEDIUM, LOW)';
COMMENT ON COLUMN frsa_features.assessment_valid_until IS 'Date until which the assessment is valid';
COMMENT ON COLUMN frsa_features.fso_compliant IS 'Compliant with Regulatory Reform (Fire Safety) Order 2005';
COMMENT ON COLUMN frsa_features.fire_safety_act_compliant IS 'Compliant with Fire Safety Act 2021 and Fire Safety (England) Regulations 2022';
COMMENT ON COLUMN frsa_features.uprn IS 'Denormalized from document_features for query performance. Source of truth: document_features.uprn';
COMMENT ON COLUMN frsa_features.postcode IS 'Denormalized from document_features for query performance. Source of truth: document_features.postcode';
