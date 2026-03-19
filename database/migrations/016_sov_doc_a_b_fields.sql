-- Migration: 016_sov_doc_a_b_fields.sql
-- Adds all Doc A and Doc B fields to silver.properties
-- These are populated by the new sov_processor.py from Example 11 format SOV files

ALTER TABLE silver.properties
    -- Doc A: Property identity
    ADD COLUMN IF NOT EXISTS property_reference   VARCHAR(50),
    ADD COLUMN IF NOT EXISTS block_reference      VARCHAR(50),
    ADD COLUMN IF NOT EXISTS occupancy_type       VARCHAR(50),

    -- Doc A: Address (address already exists as full address, add parts)
    ADD COLUMN IF NOT EXISTS address_2            VARCHAR(255),
    ADD COLUMN IF NOT EXISTS address_3            VARCHAR(255),

    -- Doc A: Financial
    ADD COLUMN IF NOT EXISTS sum_insured_type     VARCHAR(100),
    ADD COLUMN IF NOT EXISTS lor_value            DECIMAL(15, 2),
    ADD COLUMN IF NOT EXISTS total_insured_value  DECIMAL(15, 2),

    -- Doc A: Property classification
    ADD COLUMN IF NOT EXISTS avid_property_type   VARCHAR(50),

    -- Doc A: Construction
    ADD COLUMN IF NOT EXISTS wall_construction    VARCHAR(100),
    ADD COLUMN IF NOT EXISTS roof_construction    VARCHAR(100),
    ADD COLUMN IF NOT EXISTS floor_construction   VARCHAR(100),

    -- Doc A: Building characteristics
    ADD COLUMN IF NOT EXISTS age_banding          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS num_bedrooms         INTEGER,
    ADD COLUMN IF NOT EXISTS storeys              INTEGER,
    ADD COLUMN IF NOT EXISTS basement             BOOLEAN,
    ADD COLUMN IF NOT EXISTS is_listed            BOOLEAN,

    -- Doc A: Risk / security
    ADD COLUMN IF NOT EXISTS security_features    TEXT,
    ADD COLUMN IF NOT EXISTS fire_protection      TEXT,
    ADD COLUMN IF NOT EXISTS alarms               TEXT,
    ADD COLUMN IF NOT EXISTS flood_insured        BOOLEAN,
    ADD COLUMN IF NOT EXISTS storm_insured        BOOLEAN;

-- Index on block_reference for fast Doc B block-level queries
CREATE INDEX IF NOT EXISTS idx_properties_block_reference
    ON silver.properties (ha_id, block_reference);

-- Index on property_reference for lookups
CREATE INDEX IF NOT EXISTS idx_properties_property_reference
    ON silver.properties (ha_id, property_reference);

COMMENT ON COLUMN silver.properties.property_reference  IS 'Client internal property reference (e.g. 01BR01)';
COMMENT ON COLUMN silver.properties.block_reference     IS 'Block grouping reference (e.g. 01BR) - links units to a block';
COMMENT ON COLUMN silver.properties.occupancy_type      IS 'Rented / Factored / Leasehold / Shared Ownership';
COMMENT ON COLUMN silver.properties.sum_insured_type    IS 'How sum insured was determined (e.g. Declared by Client, RICS)';
COMMENT ON COLUMN silver.properties.lor_value           IS 'Loss of Rent / Alternative Accommodation / ICOW value';
COMMENT ON COLUMN silver.properties.total_insured_value IS 'Sum Insured + LOR/AA/ICOW';
COMMENT ON COLUMN silver.properties.avid_property_type  IS 'Avid/insurer normalised property type (Flat/House/Commercial)';
COMMENT ON COLUMN silver.properties.age_banding         IS 'Derived age band e.g. Pre 1919, 1919-1944, 1945-1964, 1965-1980, 1981-2000, Post 2000';
COMMENT ON COLUMN silver.properties.storeys             IS 'Number of storeys above ground';
COMMENT ON COLUMN silver.properties.basement            IS 'Whether basement flats are present';
COMMENT ON COLUMN silver.properties.is_listed           IS 'Whether property is a listed building';