-- Bronze layer audit tables and GDPR compliance
-- Migration: 001_bronze_layer.sql

-- Housing Associations table
CREATE TABLE IF NOT EXISTS housing_associations (
    ha_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Upload audit table
CREATE TABLE IF NOT EXISTS upload_audit (
    upload_id UUID PRIMARY KEY,
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    file_type VARCHAR(20) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    s3_key VARCHAR(500) NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    file_size BIGINT NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'pending',
    metadata JSONB
);

CREATE INDEX idx_upload_audit_ha_id ON upload_audit(ha_id);
CREATE INDEX idx_upload_audit_status ON upload_audit(status);
CREATE INDEX idx_upload_audit_uploaded_at ON upload_audit(uploaded_at);

-- Enhanced lineage tracking
CREATE TABLE IF NOT EXISTS data_lineage (
    lineage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL, -- 'upload', 'processing', 'output'
    source_id UUID NOT NULL, -- upload_id, processing_id, output_id
    target_type VARCHAR(50) NOT NULL,
    target_id UUID NOT NULL,
    transformation_type VARCHAR(100), -- 'validation', 'normalization', 'aggregation'
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_data_lineage_source ON data_lineage(source_type, source_id);
CREATE INDEX idx_data_lineage_target ON data_lineage(target_type, target_id);

-- UPRN lineage mapping
CREATE TABLE IF NOT EXISTS uprn_lineage_map (
    uprn VARCHAR(12) NOT NULL,
    ha_id VARCHAR(50) NOT NULL,
    submission_id UUID NOT NULL REFERENCES upload_audit(upload_id),
    property_id UUID, -- Will reference properties_silver(property_id) after Silver layer migration
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (uprn, ha_id, submission_id)
);

CREATE INDEX idx_uprn_lineage_uprn ON uprn_lineage_map(uprn);
CREATE INDEX idx_uprn_lineage_submission ON uprn_lineage_map(submission_id);
CREATE INDEX idx_uprn_lineage_ha ON uprn_lineage_map(ha_id);

-- Processing audit table
CREATE TABLE IF NOT EXISTS processing_audit (
    processing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ha_id VARCHAR(50) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    source_id UUID NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id UUID NOT NULL,
    transformation_type VARCHAR(100) NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    metadata JSONB
);

CREATE INDEX idx_processing_audit_ha_id ON processing_audit(ha_id);
CREATE INDEX idx_processing_audit_source ON processing_audit(source_type, source_id);
CREATE INDEX idx_processing_audit_target ON processing_audit(target_type, target_id);

-- Output audit table
CREATE TABLE IF NOT EXISTS output_audit (
    output_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ha_id VARCHAR(50) NOT NULL,
    output_type VARCHAR(50) NOT NULL, -- 'pdf', 'report', etc.
    source_ids JSONB NOT NULL, -- Array of source entity IDs
    generated_at TIMESTAMP DEFAULT NOW(),
    version VARCHAR(20),
    metadata JSONB
);

CREATE INDEX idx_output_audit_ha_id ON output_audit(ha_id);
CREATE INDEX idx_output_audit_type ON output_audit(output_type);
CREATE INDEX idx_output_audit_generated_at ON output_audit(generated_at);

-- GDPR compliance tables
CREATE TABLE IF NOT EXISTS gdpr_consents (
    consent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ha_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    consent_type VARCHAR(50) NOT NULL, -- 'data_processing', 'data_sharing', 'marketing'
    granted BOOLEAN NOT NULL,
    granted_at TIMESTAMP,
    revoked_at TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent TEXT,
    metadata JSONB
);

CREATE INDEX idx_gdpr_consents_ha_user ON gdpr_consents(ha_id, user_id);
CREATE INDEX idx_gdpr_consents_type ON gdpr_consents(consent_type);

-- Data retention policies
CREATE TABLE IF NOT EXISTS data_retention_policies (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_type VARCHAR(50) NOT NULL UNIQUE, -- 'property_data', 'upload_files', 'audit_logs'
    retention_days INTEGER NOT NULL,
    auto_delete BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default retention policies
INSERT INTO data_retention_policies (data_type, retention_days, auto_delete)
VALUES
    ('property_data', 2555, true),  -- 7 years
    ('upload_files', 2555, true),  -- 7 years
    ('audit_logs', 2555, true),    -- 7 years
    ('pii_mappings', 2555, true)   -- 7 years
ON CONFLICT (data_type) DO NOTHING;

-- Deletion audit table
CREATE TABLE IF NOT EXISTS deletion_audit (
    deletion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ha_id VARCHAR(50) NOT NULL,
    deletion_type VARCHAR(50) NOT NULL, -- 'gdpr_request', 'retention_policy', 'manual'
    entity_type VARCHAR(50) NOT NULL, -- 'property', 'upload', 'user_data'
    entity_id UUID NOT NULL,
    deleted_by VARCHAR(100),
    deletion_reason TEXT,
    deleted_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB -- Store what was deleted for audit purposes
);

CREATE INDEX idx_deletion_audit_ha_id ON deletion_audit(ha_id);
CREATE INDEX idx_deletion_audit_type ON deletion_audit(deletion_type);
CREATE INDEX idx_deletion_audit_entity ON deletion_audit(entity_type, entity_id);

-- Row-level security (PostgreSQL RLS) - Enable for tenant isolation
-- Note: This requires PostgreSQL 9.5+
ALTER TABLE upload_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE output_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE gdpr_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE deletion_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE uprn_lineage_map ENABLE ROW LEVEL SECURITY;

-- RLS Policies (example - will be customized per table)
-- Policy: Users can only access data for their ha_id
CREATE POLICY ha_isolation_upload_audit ON upload_audit
    FOR ALL
    USING (ha_id = current_setting('app.current_ha_id', true));

CREATE POLICY ha_isolation_processing_audit ON processing_audit
    FOR ALL
    USING (ha_id = current_setting('app.current_ha_id', true));

CREATE POLICY ha_isolation_output_audit ON output_audit
    FOR ALL
    USING (ha_id = current_setting('app.current_ha_id', true));

CREATE POLICY ha_isolation_gdpr_consents ON gdpr_consents
    FOR ALL
    USING (ha_id = current_setting('app.current_ha_id', true));

CREATE POLICY ha_isolation_deletion_audit ON deletion_audit
    FOR ALL
    USING (ha_id = current_setting('app.current_ha_id', true));

CREATE POLICY ha_isolation_uprn_lineage ON uprn_lineage_map
    FOR ALL
    USING (ha_id = current_setting('app.current_ha_id', true));
