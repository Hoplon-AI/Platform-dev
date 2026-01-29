-- Add agentic building safety features (Category A + B)
-- Migration: 006_add_agentic_building_safety_features.sql
--
-- Adds structured storage for agentic-extracted building safety features:
-- Category A: ML+UI features (high-rise indicators, evacuation strategies, fire safety measures, structural integrity, maintenance)
-- Category B: Compliance/workflow features (BSA 2022 compliance, MOR references, BSR interactions)
--
-- These features are shared across all document types (FRAEW, FRA, SCR, FRSA, etc.)

-- -----------------------------
-- Building Safety Features (Category A + B)
-- -----------------------------
CREATE TABLE IF NOT EXISTS building_safety_features (
    safety_feature_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id UUID NOT NULL REFERENCES document_features(feature_id) ON DELETE CASCADE,
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    upload_id UUID NOT NULL REFERENCES upload_audit(upload_id),
    
    -- Category A: High-rise indicators
    high_rise_building_mentioned BOOLEAN DEFAULT FALSE,
    building_height_category VARCHAR(20), -- 'HIGH_RISE', 'MEDIUM_RISE', 'LOW_RISE', 'NOT_SPECIFIED'
    number_of_storeys INTEGER,
    building_height_metres DECIMAL(6, 2),
    number_of_high_rise_buildings INTEGER,
    building_safety_act_applicable BOOLEAN DEFAULT FALSE,
    
    -- Category A: Evacuation strategies
    evacuation_strategy_mentioned BOOLEAN DEFAULT FALSE,
    evacuation_strategy_type VARCHAR(20), -- 'STAY_PUT', 'STAY_SAFE', 'SIMULTANEOUS', 'PHASED', 'DEFEND_IN_PLACE', 'FULL_EVACUATION', 'NOT_SPECIFIED'
    evacuation_strategy_description TEXT,
    evacuation_strategy_changed BOOLEAN,
    personal_evacuation_plans_mentioned BOOLEAN DEFAULT FALSE,
    evacuation_support_required BOOLEAN,
    
    -- Category A: Fire safety measures (summary flags)
    fire_safety_measures_mentioned BOOLEAN DEFAULT FALSE,
    fire_doors_mentioned BOOLEAN DEFAULT FALSE,
    fire_safety_officers_mentioned BOOLEAN DEFAULT FALSE,
    
    -- Category A: Structural integrity (summary flags)
    structural_integrity_mentioned BOOLEAN DEFAULT FALSE,
    structural_assessments_mentioned BOOLEAN DEFAULT FALSE,
    structural_risks_mentioned BOOLEAN DEFAULT FALSE,
    structural_work_mentioned BOOLEAN DEFAULT FALSE,
    structural_maintenance_required BOOLEAN,
    
    -- Category A: Maintenance requirements (summary flags)
    maintenance_mentioned BOOLEAN DEFAULT FALSE,
    maintenance_schedules_mentioned BOOLEAN DEFAULT FALSE,
    maintenance_checks_mentioned BOOLEAN DEFAULT FALSE,
    tenancy_audits_mentioned BOOLEAN DEFAULT FALSE,
    
    -- Category B: Building Safety Act 2022 compliance
    building_safety_act_2022_mentioned BOOLEAN DEFAULT FALSE,
    building_safety_act_compliance_status VARCHAR(30), -- 'COMPLIANT', 'NON_COMPLIANT', 'PARTIALLY_COMPLIANT', 'UNDER_REVIEW', 'NOT_SPECIFIED'
    part_4_duties_mentioned BOOLEAN DEFAULT FALSE,
    building_safety_decisions_mentioned BOOLEAN DEFAULT FALSE,
    building_safety_regulator_mentioned BOOLEAN DEFAULT FALSE,
    building_safety_case_report_mentioned BOOLEAN DEFAULT FALSE,
    
    -- Category B: Mandatory Occurrence Reports
    mandatory_occurrence_report_mentioned BOOLEAN DEFAULT FALSE,
    mandatory_occurrence_reporting_process_mentioned BOOLEAN DEFAULT FALSE,
    
    -- Full agentic features JSON (Category A + B detailed data)
    agentic_features_json JSONB,
    
    -- Extraction metadata
    extraction_method VARCHAR(20) DEFAULT 'regex', -- 'regex', 'agentic', 'merged'
    agentic_confidence_score DECIMAL(3, 2), -- 0.00 to 1.00
    extraction_comparison_metadata JSONB, -- Comparison between regex and agentic results
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_building_safety_features_feature_id ON building_safety_features(feature_id);
CREATE INDEX IF NOT EXISTS idx_building_safety_features_ha_id ON building_safety_features(ha_id);
CREATE INDEX IF NOT EXISTS idx_building_safety_features_upload_id ON building_safety_features(upload_id);
CREATE INDEX IF NOT EXISTS idx_building_safety_features_height_category ON building_safety_features(building_height_category);
CREATE INDEX IF NOT EXISTS idx_building_safety_features_evacuation_strategy ON building_safety_features(evacuation_strategy_type);
CREATE INDEX IF NOT EXISTS idx_building_safety_features_bsa_compliance ON building_safety_features(building_safety_act_compliance_status);
CREATE INDEX IF NOT EXISTS idx_building_safety_features_extraction_method ON building_safety_features(extraction_method);

-- Add comments
COMMENT ON TABLE building_safety_features IS 'Stores agentic-extracted building safety features (Category A: ML+UI, Category B: Compliance/workflow) shared across all document types';
COMMENT ON COLUMN building_safety_features.agentic_features_json IS 'Full JSON structure with detailed Category A+B features (high-rise details, evacuation instructions, fire safety systems inventory, structural assessments, maintenance schedules, BSA compliance details, MOR references, BSR interactions)';
COMMENT ON COLUMN building_safety_features.extraction_method IS 'Method used: regex (existing), agentic (Bedrock/Claude), or merged (both)';
COMMENT ON COLUMN building_safety_features.agentic_confidence_score IS 'Overall confidence score for agentic extraction (0.00 to 1.00)';
COMMENT ON COLUMN building_safety_features.extraction_comparison_metadata IS 'Comparison metadata between regex and agentic extraction results (agreement scores, discrepancies)';

-- -----------------------------
-- DocB/PlanB Features (Category C)
-- -----------------------------
CREATE TABLE IF NOT EXISTS docb_features (
    docb_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id UUID NOT NULL REFERENCES document_features(feature_id) ON DELETE CASCADE,
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    upload_id UUID NOT NULL REFERENCES upload_audit(upload_id),
    
    -- Required DocB fields
    cladding_type VARCHAR(255),
    ews_status VARCHAR(100), -- External Wall System status
    fire_risk_management_summary TEXT,
    docb_ref VARCHAR(255), -- Document B reference
    
    -- Optional context fields
    fire_protection TEXT,
    alarms VARCHAR(255),
    evacuation_strategy VARCHAR(50), -- May overlap with building_safety_features.evacuation_strategy_type
    floors_above_ground INTEGER,
    floors_below_ground INTEGER,
    
    -- Full DocB features JSON
    docb_features_json JSONB,
    
    -- Extraction metadata
    extraction_method VARCHAR(20) DEFAULT 'regex',
    agentic_confidence_score DECIMAL(3, 2),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_docb_features_feature_id ON docb_features(feature_id);
CREATE INDEX IF NOT EXISTS idx_docb_features_ha_id ON docb_features(ha_id);
CREATE INDEX IF NOT EXISTS idx_docb_features_upload_id ON docb_features(upload_id);
CREATE INDEX IF NOT EXISTS idx_docb_features_cladding_type ON docb_features(cladding_type);
CREATE INDEX IF NOT EXISTS idx_docb_features_ews_status ON docb_features(ews_status);
CREATE INDEX IF NOT EXISTS idx_docb_features_docb_ref ON docb_features(docb_ref);

-- Add comments
COMMENT ON TABLE docb_features IS 'Stores DocB/PlanB portfolio columns (high-value property fields) extracted from documents';
COMMENT ON COLUMN docb_features.cladding_type IS 'Type of cladding material (from property-schema.json)';
COMMENT ON COLUMN docb_features.ews_status IS 'External Wall System (EWS) status (from property-schema.json)';
COMMENT ON COLUMN docb_features.fire_risk_management_summary IS 'Summary of fire risk management measures (from property-schema.json)';
COMMENT ON COLUMN docb_features.docb_ref IS 'Document B reference for high value properties (from property-schema.json)';

-- -----------------------------
-- Update document_features to store agentic extraction metadata
-- -----------------------------
ALTER TABLE document_features
    ADD COLUMN IF NOT EXISTS agentic_features_json JSONB,
    ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(20) DEFAULT 'regex',
    ADD COLUMN IF NOT EXISTS extraction_comparison_metadata JSONB;

CREATE INDEX IF NOT EXISTS idx_document_features_extraction_method ON document_features(extraction_method);
CREATE INDEX IF NOT EXISTS idx_document_features_agentic_features ON document_features USING GIN (agentic_features_json);

COMMENT ON COLUMN document_features.agentic_features_json IS 'Full agentic extraction results (all categories A+B+C) from Bedrock/Claude';
COMMENT ON COLUMN document_features.extraction_method IS 'Method used: regex (existing), agentic (Bedrock/Claude), or merged (both)';
COMMENT ON COLUMN document_features.extraction_comparison_metadata IS 'Comparison metadata between regex and agentic extraction (agreement scores, discrepancies, confidence scores)';
