-- Expand SCR features table with Safety Case Report specific columns
-- Migration: 009_expand_scr_features.sql
--
-- Adds structured storage for Building Safety Case Report features:
-- - Building identification (name, address, BSR registration, UPRN)
-- - Building characteristics (height, storeys, construction year, type)
-- - Safety case metadata (version, date, author, PAP, BSM)
-- - Fire safety features (FRA, evacuation, fire systems)
-- - Structural information (construction type, cladding, certification)
-- - BSA 2022 compliance indicators

-- Add SCR-specific columns to scr_features table
ALTER TABLE scr_features
    -- Building identification
    ADD COLUMN IF NOT EXISTS building_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS building_address TEXT,
    ADD COLUMN IF NOT EXISTS bsr_registration_number VARCHAR(50),  -- e.g., HRB12881N5H4
    ADD COLUMN IF NOT EXISTS building_reference VARCHAR(100),      -- Internal reference like BLKCROCODILECOURTY
    ADD COLUMN IF NOT EXISTS uprn_labeled VARCHAR(100),            -- Whatever the document labels as "UPRN"
    ADD COLUMN IF NOT EXISTS uprns TEXT[],                         -- Array of standard 12-digit UPRNs found

    -- Building characteristics
    ADD COLUMN IF NOT EXISTS building_height_metres DECIMAL(6, 2),
    ADD COLUMN IF NOT EXISTS number_of_storeys INTEGER,
    ADD COLUMN IF NOT EXISTS construction_year INTEGER,
    ADD COLUMN IF NOT EXISTS building_type VARCHAR(50),            -- HRRB, etc.
    ADD COLUMN IF NOT EXISTS height_category VARCHAR(20),          -- HIGH_RISE (18m+), MEDIUM_RISE, LOW_RISE
    ADD COLUMN IF NOT EXISTS total_units INTEGER,

    -- Safety case metadata
    ADD COLUMN IF NOT EXISTS safety_case_version VARCHAR(20),
    ADD COLUMN IF NOT EXISTS safety_case_date DATE,
    ADD COLUMN IF NOT EXISTS report_author VARCHAR(255),
    ADD COLUMN IF NOT EXISTS principal_accountable_person VARCHAR(255),  -- PAP
    ADD COLUMN IF NOT EXISTS building_safety_manager VARCHAR(255),       -- BSM
    ADD COLUMN IF NOT EXISTS accountable_person_entity VARCHAR(255),     -- Organization

    -- FRA (Fire Risk Assessment) information
    ADD COLUMN IF NOT EXISTS fra_type VARCHAR(20),                 -- Type 1, Type 2, Type 3, Type 4
    ADD COLUMN IF NOT EXISTS fra_date DATE,
    ADD COLUMN IF NOT EXISTS fra_assessor VARCHAR(255),
    ADD COLUMN IF NOT EXISTS fra_assessor_credentials VARCHAR(255), -- e.g., MIFSM, AIFireE
    ADD COLUMN IF NOT EXISTS fra_peer_reviewer VARCHAR(255),
    ADD COLUMN IF NOT EXISTS fra_outcome VARCHAR(50),              -- e.g., 'suitable and sufficient'

    -- Evacuation strategy
    ADD COLUMN IF NOT EXISTS evacuation_strategy VARCHAR(50),      -- STAY_PUT, FULL_EVACUATION, PHASED, etc.
    ADD COLUMN IF NOT EXISTS evacuation_strategy_description TEXT,
    ADD COLUMN IF NOT EXISTS personal_evacuation_plans_required BOOLEAN DEFAULT FALSE,

    -- Fire safety systems
    ADD COLUMN IF NOT EXISTS fire_alarm_system_type VARCHAR(100),  -- e.g., BS 5839 pt1: L1
    ADD COLUMN IF NOT EXISTS fire_alarm_coverage VARCHAR(50),      -- communal, full building, etc.
    ADD COLUMN IF NOT EXISTS smoke_detection_type VARCHAR(100),    -- L5, etc.
    ADD COLUMN IF NOT EXISTS firefighters_lift_present BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS dry_riser_present BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS wet_riser_present BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS sprinklers_present BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS aov_present BOOLEAN DEFAULT FALSE,    -- Automatic Opening Vents
    ADD COLUMN IF NOT EXISTS emergency_lighting_present BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS fire_compartmentation_status VARCHAR(50),
    ADD COLUMN IF NOT EXISTS premises_information_box_present BOOLEAN DEFAULT FALSE,

    -- Structural information
    ADD COLUMN IF NOT EXISTS construction_type VARCHAR(100),       -- e.g., reinforced concrete
    ADD COLUMN IF NOT EXISTS cladding_type VARCHAR(100),           -- ACM, HPL, etc.
    ADD COLUMN IF NOT EXISTS cladding_status VARCHAR(50),          -- safe, unsafe, remediated, etc.
    ADD COLUMN IF NOT EXISTS building_control_certificate BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS structural_issues_identified BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS structural_issues_description TEXT,
    ADD COLUMN IF NOT EXISTS gas_detectors_present BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS lightning_protection_present BOOLEAN DEFAULT FALSE,

    -- BSA 2022 compliance
    ADD COLUMN IF NOT EXISTS bsa_2022_applicable BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS part_4_duties_compliance_status VARCHAR(50),
    ADD COLUMN IF NOT EXISTS mandatory_occurrence_reporting_in_place BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS resident_engagement_strategy_present BOOLEAN DEFAULT FALSE,

    -- Key contacts
    ADD COLUMN IF NOT EXISTS key_contacts_json JSONB,              -- Array of contact objects

    -- Extraction metadata
    ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(20) DEFAULT 'regex',  -- 'regex', 'agentic', 'merged'
    ADD COLUMN IF NOT EXISTS agentic_confidence_score DECIMAL(3, 2),
    ADD COLUMN IF NOT EXISTS extraction_comparison_json JSONB;     -- Comparison between regex and agentic

-- Add indexes for commonly queried columns
CREATE INDEX IF NOT EXISTS idx_scr_features_uprn_labeled ON scr_features(uprn_labeled);
CREATE INDEX IF NOT EXISTS idx_scr_features_uprns ON scr_features USING GIN(uprns);
CREATE INDEX IF NOT EXISTS idx_scr_features_bsr_registration ON scr_features(bsr_registration_number);
CREATE INDEX IF NOT EXISTS idx_scr_features_height_category ON scr_features(height_category);
CREATE INDEX IF NOT EXISTS idx_scr_features_evacuation_strategy ON scr_features(evacuation_strategy);
CREATE INDEX IF NOT EXISTS idx_scr_features_fra_type ON scr_features(fra_type);
CREATE INDEX IF NOT EXISTS idx_scr_features_fra_date ON scr_features(fra_date);
CREATE INDEX IF NOT EXISTS idx_scr_features_construction_year ON scr_features(construction_year);
CREATE INDEX IF NOT EXISTS idx_scr_features_bsa_applicable ON scr_features(bsa_2022_applicable);
CREATE INDEX IF NOT EXISTS idx_scr_features_extraction_method ON scr_features(extraction_method);

-- Add comments
COMMENT ON TABLE scr_features IS 'Building Safety Case Report (SCR) specific features extracted from PDF documents';
COMMENT ON COLUMN scr_features.bsr_registration_number IS 'Building Safety Regulator registration number (e.g., HRB12881N5H4)';
COMMENT ON COLUMN scr_features.height_category IS 'Building height category: HIGH_RISE (18m+ or 7+ storeys), MEDIUM_RISE (11-18m), LOW_RISE (<11m)';
COMMENT ON COLUMN scr_features.fra_type IS 'Fire Risk Assessment type: Type 1 (non-destructive common areas), Type 2 (destructive common areas), Type 3 (Type 2 + flats), Type 4 (Type 3 + destructive)';
COMMENT ON COLUMN scr_features.extraction_method IS 'Feature extraction method: regex (pattern matching), agentic (LLM/Bedrock), merged (both combined)';
