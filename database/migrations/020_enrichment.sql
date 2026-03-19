-- ═══════════════════════════════════════════════════════════════════
-- Migration 020: Enrichment columns for API data
--
-- SAFE TO RUN MULTIPLE TIMES — every statement uses IF NOT EXISTS
--
-- What already exists in silver.properties (from 001b + 012 + 016):
--   id, ha_id, address, postcode, latitude, longitude, uprn,
--   property_reference, block_reference, occupancy_type,
--   address_2, address_3, sum_insured, sum_insured_type,
--   wall_construction, roof_construction, floor_construction,
--   age_banding, num_bedrooms, storeys, basement, is_listed,
--   security_features, fire_protection, alarms, flood_insured,
--   storm_insured, submission_id, enrichment_status, metadata
--
-- What this migration ADDS (API-only fields that don't exist yet):
--   UPRN identity: parent_uprn, x_coordinate, y_coordinate,
--                  country_code, uprn_match_score, uprn_match_description
--   NGD height:    height_max_m, height_roofbase_m, height_confidence,
--                  building_footprint_m2
--   EPC data:      epc_rating, epc_potential_rating, total_floor_area_m2,
--                  main_fuel, built_form, epc_lodgement_date
--   Listed detail: listed_grade, listed_name, listed_reference
--   Tracking:      enrichment_source, enriched_at
--
-- What already exists in silver.blocks (from 001b + 012):
--   block_id, ha_id, name, address, postcode, latitude, longitude,
--   fra_status, fraew_status
--
-- What this migration ADDS to silver.blocks:
--   parent_uprn, unit_count, total_sum_insured, max_storeys,
--   predominant_wall, predominant_roof, height_max_m,
--   listed_grade
-- ═══════════════════════════════════════════════════════════════════

BEGIN;

-- ──────────────────────────────────────────────────────────────────
-- 1. silver.properties — add enrichment columns
-- ──────────────────────────────────────────────────────────────────

-- UPRN & geo identity (uprn column likely exists from 001b — ADD IF NOT EXISTS is safe)
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS uprn varchar(20);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS parent_uprn varchar(20);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS x_coordinate numeric(12,2);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS y_coordinate numeric(12,2);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS country_code varchar(5);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS uprn_match_score numeric(5,2);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS uprn_match_description varchar(20);

-- NGD building height data
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS height_max_m numeric(8,2);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS height_roofbase_m numeric(8,2);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS height_confidence varchar(20);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS building_footprint_m2 numeric(12,2);

-- EPC data
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS epc_rating varchar(5);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS epc_potential_rating varchar(5);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS total_floor_area_m2 numeric(10,2);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS main_fuel varchar(100);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS built_form varchar(50);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS epc_lodgement_date varchar(30);

-- Listed building details (is_listed already exists from 016)
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS listed_grade varchar(10);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS listed_name text;
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS listed_reference varchar(50);

-- Enrichment tracking
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS enrichment_source varchar(50);
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS enriched_at timestamptz;

-- year_of_build — may or may not exist depending on which migration ran
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS year_of_build varchar(20);

-- deductible — may not exist yet
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS deductible numeric(12,2);

-- units — may not exist yet
ALTER TABLE silver.properties ADD COLUMN IF NOT EXISTS units integer;

-- Widen any varchar columns that are too narrow (safe — ALTER TYPE is idempotent)
-- These were varchar(30) or varchar(50) in earlier migrations but need 100+
DO $$
BEGIN
    -- Only widen if current max_length is less than target
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='silver' AND table_name='properties'
        AND column_name='property_reference'
        AND character_maximum_length < 100
    ) THEN
        ALTER TABLE silver.properties ALTER COLUMN property_reference TYPE varchar(100);
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='silver' AND table_name='properties'
        AND column_name='block_reference'
        AND character_maximum_length < 100
    ) THEN
        ALTER TABLE silver.properties ALTER COLUMN block_reference TYPE varchar(100);
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='silver' AND table_name='properties'
        AND column_name='occupancy_type'
        AND character_maximum_length < 100
    ) THEN
        ALTER TABLE silver.properties ALTER COLUMN occupancy_type TYPE varchar(100);
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='silver' AND table_name='properties'
        AND column_name='property_type'
        AND character_maximum_length < 100
    ) THEN
        ALTER TABLE silver.properties ALTER COLUMN property_type TYPE varchar(100);
    END IF;
END $$;


-- ──────────────────────────────────────────────────────────────────
-- 2. silver.blocks — add enrichment columns to EXISTING table
--    (NOT creating a new table — silver.blocks already exists)
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE silver.blocks ADD COLUMN IF NOT EXISTS parent_uprn varchar(20);
ALTER TABLE silver.blocks ADD COLUMN IF NOT EXISTS unit_count integer DEFAULT 0;
ALTER TABLE silver.blocks ADD COLUMN IF NOT EXISTS total_sum_insured numeric(15,2) DEFAULT 0;
ALTER TABLE silver.blocks ADD COLUMN IF NOT EXISTS max_storeys integer;
ALTER TABLE silver.blocks ADD COLUMN IF NOT EXISTS predominant_wall varchar(100);
ALTER TABLE silver.blocks ADD COLUMN IF NOT EXISTS predominant_roof varchar(100);
ALTER TABLE silver.blocks ADD COLUMN IF NOT EXISTS height_max_m numeric(8,2);
ALTER TABLE silver.blocks ADD COLUMN IF NOT EXISTS is_listed boolean;
ALTER TABLE silver.blocks ADD COLUMN IF NOT EXISTS listed_grade varchar(10);


-- ──────────────────────────────────────────────────────────────────
-- 3. Indexes for enrichment queries
-- ──────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_properties_enrichment_pending
    ON silver.properties (ha_id, enrichment_status)
    WHERE enrichment_status = 'pending';

CREATE INDEX IF NOT EXISTS idx_properties_uprn
    ON silver.properties (uprn)
    WHERE uprn IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_properties_parent_uprn
    ON silver.properties (parent_uprn)
    WHERE parent_uprn IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_blocks_parent_uprn
    ON silver.blocks (parent_uprn)
    WHERE parent_uprn IS NOT NULL;


-- ──────────────────────────────────────────────────────────────────
-- 4. Gold views for Doc A and Doc B — CREATE OR REPLACE
--    (replaces any old versions safely)
-- ──────────────────────────────────────────────────────────────────

-- Doc A: per-unit schedule with enrichment data merged in
CREATE OR REPLACE VIEW gold.doc_a_enriched AS
SELECT
    p.ha_id,
    p.property_reference,
    p.block_reference,
    p.uprn,
    p.occupancy_type,
    p.deductible,
    p.address          AS address_1,
    p.address_2,
    p.address_3,
    p.postcode,
    p.sum_insured,
    p.sum_insured_type,
    p.units            AS number_of_units,
    COALESCE(p.property_type, p.built_form)  AS property_type,
    p.avid_property_type,
    p.wall_construction,
    p.roof_construction,
    p.floor_construction,
    p.year_of_build,
    p.age_banding,
    p.num_bedrooms     AS number_of_bedrooms,
    p.storeys          AS number_of_storeys,
    p.basement         AS basement_location,
    p.is_listed        AS listed_building,
    p.listed_grade,
    p.security_features,
    p.fire_protection,
    p.alarms,
    p.flood_insured,
    p.storm_insured,
    -- Enrichment-only fields
    p.enrichment_status,
    p.enrichment_source,
    p.uprn_match_score,
    p.height_max_m,
    p.epc_rating,
    p.total_floor_area_m2,
    p.parent_uprn
FROM silver.properties p
ORDER BY p.block_reference, p.property_reference;


-- Doc B: per-block schedule aggregated from units
CREATE OR REPLACE VIEW gold.doc_b_enriched AS
SELECT
    p.ha_id,
    COALESCE(p.block_reference, p.address) AS block_reference,
    MIN(p.address)                          AS address_line_1,
    MIN(p.address_2)                        AS address_line_2,
    MIN(p.postcode)                         AS postcode,
    SUM(p.sum_insured)                      AS sum_insured,
    ROUND(SUM(p.sum_insured) * 0.25, 2)    AS lor_aa,
    ROUND(SUM(p.sum_insured) * 1.25, 2)    AS total_insured_value,
    MAX(p.storeys)                          AS storeys_above_ground,
    MAX(p.height_max_m)                     AS height_metres,
    BOOL_OR(p.basement)                     AS basement_flats_present,
    MODE() WITHIN GROUP (ORDER BY p.property_type)    AS property_type,
    MODE() WITHIN GROUP (ORDER BY p.occupancy_type)   AS occupancy_type,
    COUNT(*)::integer                       AS number_of_units,
    MIN(p.year_of_build)                    AS date_of_build,
    BOOL_OR(p.is_listed)                    AS listed_building,
    MAX(p.listed_grade)                     AS listed_grade,
    MODE() WITHIN GROUP (ORDER BY p.wall_construction)  AS wall_construction,
    MODE() WITHIN GROUP (ORDER BY p.floor_construction) AS floor_construction,
    MODE() WITHIN GROUP (ORDER BY p.roof_construction)  AS roof_construction,
    CASE
        WHEN MODE() WITHIN GROUP (ORDER BY p.wall_construction) ILIKE '%timber%'
        THEN true ELSE false
    END                                     AS timber_framed,
    MAX(p.parent_uprn)                      AS parent_uprn
FROM silver.properties p
GROUP BY p.ha_id, COALESCE(p.block_reference, p.address)
ORDER BY COALESCE(p.block_reference, p.address);


-- Underwriter dashboard: enrichment coverage summary
CREATE OR REPLACE VIEW gold.enrichment_summary AS
SELECT
    p.ha_id,
    COUNT(*)                                    AS total_properties,
    COUNT(CASE WHEN enrichment_status = 'enriched' THEN 1 END) AS enriched_count,
    COUNT(CASE WHEN enrichment_status = 'pending' THEN 1 END)  AS pending_count,
    COUNT(CASE WHEN enrichment_status = 'failed' THEN 1 END)   AS failed_count,
    COUNT(p.uprn)                                AS has_uprn,
    COUNT(p.wall_construction)                   AS has_wall,
    COUNT(p.roof_construction)                   AS has_roof,
    COUNT(p.year_of_build)                       AS has_year,
    COUNT(p.height_max_m)                        AS has_height,
    COUNT(p.epc_rating)                          AS has_epc,
    COUNT(CASE WHEN p.is_listed IS NOT NULL THEN 1 END) AS has_listed_check,
    SUM(COALESCE(p.sum_insured, 0))             AS total_sum_insured
FROM silver.properties p
GROUP BY p.ha_id;


COMMIT;