-- Silver layer: Document features tables
-- Migration: 003_silver_document_features.sql
--
-- Normalized tables for extracted features from PDF documents (FRAEW, FRA, SCR, FRSA)
-- These tables store structured data extracted from features.json artifacts

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------
-- Document Features (base table for all document types)
-- -----------------------------
CREATE TABLE IF NOT EXISTS document_features (
    feature_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    upload_id UUID NOT NULL REFERENCES upload_audit(upload_id),
    document_type VARCHAR(50) NOT NULL, -- 'fraew_document', 'fra_document', 'scr_document', 'frsa_document'
    
    -- Common fields across all document types
    building_name VARCHAR(255),
    address TEXT,
    uprn VARCHAR(12),
    postcode VARCHAR(10),
    assessment_date DATE,
    job_reference VARCHAR(100),
    client_name VARCHAR(255),
    assessor_company VARCHAR(255),
    
    -- Full features JSON for reference and future extraction
    features_json JSONB NOT NULL,
    
    -- Processing metadata
    extracted_at TIMESTAMP,
    processed_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Link to properties/blocks if identified
    property_id UUID REFERENCES properties(property_id),
    block_id UUID REFERENCES blocks(block_id)
);

CREATE INDEX IF NOT EXISTS idx_document_features_ha_id ON document_features(ha_id);
CREATE INDEX IF NOT EXISTS idx_document_features_upload_id ON document_features(upload_id);
CREATE INDEX IF NOT EXISTS idx_document_features_document_type ON document_features(document_type);
CREATE INDEX IF NOT EXISTS idx_document_features_uprn ON document_features(uprn);
CREATE INDEX IF NOT EXISTS idx_document_features_property_id ON document_features(property_id);
CREATE INDEX IF NOT EXISTS idx_document_features_block_id ON document_features(block_id);
CREATE INDEX IF NOT EXISTS idx_document_features_assessment_date ON document_features(assessment_date);

-- -----------------------------
-- FRAEW Features (PAS 9980:2022 specific)
-- -----------------------------
CREATE TABLE IF NOT EXISTS fraew_features (
    fraew_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id UUID NOT NULL REFERENCES document_features(feature_id) ON DELETE CASCADE,
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    upload_id UUID NOT NULL REFERENCES upload_audit(upload_id),
    
    -- PAS 9980 compliance
    pas_9980_compliant BOOLEAN DEFAULT FALSE,
    pas_9980_version VARCHAR(10), -- '2022' or other version
    
    -- Building risk assessment
    building_risk_rating VARCHAR(10), -- 'HIGH', 'MEDIUM', 'LOW'
    
    -- External wall details (stored as JSONB for flexibility)
    wall_types JSONB, -- Array of wall type objects with risk ratings
    
    -- Remediation indicators
    has_interim_measures BOOLEAN DEFAULT FALSE,
    has_remedial_actions BOOLEAN DEFAULT FALSE,
    
    -- Full FRAEW-specific features JSON
    fraew_features_json JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fraew_features_feature_id ON fraew_features(feature_id);
CREATE INDEX IF NOT EXISTS idx_fraew_features_ha_id ON fraew_features(ha_id);
CREATE INDEX IF NOT EXISTS idx_fraew_features_upload_id ON fraew_features(upload_id);
CREATE INDEX IF NOT EXISTS idx_fraew_features_risk_rating ON fraew_features(building_risk_rating);
CREATE INDEX IF NOT EXISTS idx_fraew_features_pas_compliant ON fraew_features(pas_9980_compliant);

-- -----------------------------
-- FRA Features (Fire Risk Assessment)
-- -----------------------------
CREATE TABLE IF NOT EXISTS fra_features (
    fra_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id UUID NOT NULL REFERENCES document_features(feature_id) ON DELETE CASCADE,
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    upload_id UUID NOT NULL REFERENCES upload_audit(upload_id),
    
    -- FRA-specific fields (to be expanded as needed)
    risk_rating VARCHAR(10),
    assessment_valid_until DATE,
    
    -- Full FRA-specific features JSON
    fra_features_json JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fra_features_feature_id ON fra_features(feature_id);
CREATE INDEX IF NOT EXISTS idx_fra_features_ha_id ON fra_features(ha_id);
CREATE INDEX IF NOT EXISTS idx_fra_features_upload_id ON fra_features(upload_id);

-- -----------------------------
-- SCR Features (Safety Case Report)
-- -----------------------------
CREATE TABLE IF NOT EXISTS scr_features (
    scr_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id UUID NOT NULL REFERENCES document_features(feature_id) ON DELETE CASCADE,
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    upload_id UUID NOT NULL REFERENCES upload_audit(upload_id),
    
    -- SCR-specific fields (to be expanded as needed)
    safety_case_status VARCHAR(50),
    
    -- Full SCR-specific features JSON
    scr_features_json JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scr_features_feature_id ON scr_features(feature_id);
CREATE INDEX IF NOT EXISTS idx_scr_features_ha_id ON scr_features(ha_id);
CREATE INDEX IF NOT EXISTS idx_scr_features_upload_id ON scr_features(upload_id);

-- -----------------------------
-- FRSA Features (Fire Risk Safety Assessment)
-- -----------------------------
CREATE TABLE IF NOT EXISTS frsa_features (
    frsa_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id UUID NOT NULL REFERENCES document_features(feature_id) ON DELETE CASCADE,
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    upload_id UUID NOT NULL REFERENCES upload_audit(upload_id),
    
    -- FRSA-specific fields (to be expanded as needed)
    risk_rating VARCHAR(10),
    
    -- Full FRSA-specific features JSON
    frsa_features_json JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_frsa_features_feature_id ON frsa_features(feature_id);
CREATE INDEX IF NOT EXISTS idx_frsa_features_ha_id ON frsa_features(ha_id);
CREATE INDEX IF NOT EXISTS idx_frsa_features_upload_id ON frsa_features(upload_id);
