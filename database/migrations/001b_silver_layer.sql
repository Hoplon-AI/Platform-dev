-- Silver layer tables (normalized, queryable entities)
-- Migration: 001_silver_layer.sql
--
-- Notes:
-- - Properties are keyed by property_id (UUID PK)
-- - Many documents will join to properties via UPRN initially, so UPRN is indexed
-- - All tables are tenant-scoped by ha_id

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------
-- Portfolios
-- -----------------------------
CREATE TABLE IF NOT EXISTS portfolios (
    portfolio_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    name VARCHAR(255) NOT NULL,
    renewal_year INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_portfolios_ha_id ON portfolios(ha_id);
CREATE INDEX IF NOT EXISTS idx_portfolios_renewal_year ON portfolios(renewal_year);

-- -----------------------------
-- Blocks
-- -----------------------------
CREATE TABLE IF NOT EXISTS blocks (
    block_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    portfolio_id UUID REFERENCES portfolios(portfolio_id),
    name VARCHAR(255) NOT NULL,
    jurisdiction VARCHAR(10), -- 'ENG' or 'SCO'
    total_units INTEGER,
    height_m DECIMAL(6, 2),
    height_category VARCHAR(10), -- '<11m', '11-16m', '16m+'
    build_year INTEGER,
    construction_type VARCHAR(50),
    ews_cladding_status VARCHAR(50),
    risk_rating VARCHAR(2), -- allow A/B/C/D/E or variants like I-rating
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_blocks_ha_id ON blocks(ha_id);
CREATE INDEX IF NOT EXISTS idx_blocks_portfolio_id ON blocks(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_blocks_jurisdiction ON blocks(jurisdiction);

-- -----------------------------
-- Properties
-- -----------------------------
CREATE TABLE IF NOT EXISTS properties (
    property_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    portfolio_id UUID REFERENCES portfolios(portfolio_id),
    block_id UUID REFERENCES blocks(block_id),

    uprn VARCHAR(12),
    address TEXT NOT NULL,
    postcode VARCHAR(10),

    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),

    units INTEGER,
    height_m DECIMAL(6, 2),
    build_year INTEGER,
    construction_type VARCHAR(50),
    tenure VARCHAR(50),
    risk_rating VARCHAR(2),

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- UPRN joins are common; keep it indexed (and optionally unique per ha_id)
CREATE INDEX IF NOT EXISTS idx_properties_ha_id ON properties(ha_id);
CREATE INDEX IF NOT EXISTS idx_properties_portfolio_id ON properties(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_properties_block_id ON properties(block_id);
CREATE INDEX IF NOT EXISTS idx_properties_uprn ON properties(uprn);
CREATE INDEX IF NOT EXISTS idx_properties_postcode ON properties(postcode);

-- Ensure the same UPRN is not duplicated within a tenant (optional, but usually desired)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_properties_ha_uprn'
    ) THEN
        ALTER TABLE properties
            ADD CONSTRAINT uq_properties_ha_uprn UNIQUE (ha_id, uprn);
    END IF;
EXCEPTION
    WHEN duplicate_object THEN
        NULL;
END $$;

-- -----------------------------
-- EPC data (tabular, joined by uprn)
-- -----------------------------
CREATE TABLE IF NOT EXISTS epc_data (
    epc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),
    property_id UUID REFERENCES properties(property_id),
    uprn VARCHAR(12),

    epc_rating VARCHAR(2),
    epc_date DATE,
    energy_efficiency INTEGER,
    environmental_impact INTEGER,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_epc_data_ha_id ON epc_data(ha_id);
CREATE INDEX IF NOT EXISTS idx_epc_data_property_id ON epc_data(property_id);
CREATE INDEX IF NOT EXISTS idx_epc_data_uprn ON epc_data(uprn);

-- -----------------------------
-- UPRN mappings (OS DataHub dataset import cache / lookup table)
-- -----------------------------
CREATE TABLE IF NOT EXISTS uprn_mappings (
    mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ha_id VARCHAR(50) NOT NULL REFERENCES housing_associations(ha_id),

    uprn VARCHAR(12) NOT NULL,
    address TEXT NOT NULL,
    postcode VARCHAR(10),
    normalized_address TEXT,

    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    confidence DECIMAL(3, 2), -- 0.00 to 1.00
    source VARCHAR(50) DEFAULT 'os_datahub',

    mapped_at TIMESTAMP DEFAULT NOW(),
    last_verified_at TIMESTAMP,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_uprn_mappings_ha_id ON uprn_mappings(ha_id);
CREATE INDEX IF NOT EXISTS idx_uprn_mappings_uprn ON uprn_mappings(uprn);
CREATE INDEX IF NOT EXISTS idx_uprn_mappings_normalized_address ON uprn_mappings(normalized_address);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_uprn_mappings_ha_uprn_address'
    ) THEN
        ALTER TABLE uprn_mappings
            ADD CONSTRAINT uq_uprn_mappings_ha_uprn_address UNIQUE (ha_id, uprn, address);
    END IF;
EXCEPTION
    WHEN duplicate_object THEN
        NULL;
END $$;

-- -----------------------------
-- Backfill / linkage constraints (Bronze → Silver)
-- -----------------------------
-- Bronze table uprn_lineage_map has property_id reserved for Silver linkage.
-- Add FK once the Silver properties table exists.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_uprn_lineage_map_property'
    ) THEN
        ALTER TABLE uprn_lineage_map
            ADD CONSTRAINT fk_uprn_lineage_map_property
            FOREIGN KEY (property_id) REFERENCES properties(property_id);
    END IF;
EXCEPTION
    WHEN duplicate_object THEN
        NULL;
END $$;

