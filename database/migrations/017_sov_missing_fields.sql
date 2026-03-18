-- =============================================================
-- Migration: 017_sov_missing_fields.sql
--
-- Adds the remaining SoV fields to silver.properties that are
-- present in one or more real SoV files but were missing from
-- the DB after migration 016.
--
-- Fields added and their coverage across 9 real SoV files:
--   deductible           -- 4/9 files (core Doc A field)
--   basis_of_deductible  -- 5/9 files (majority of files)
--   policy_reference     -- 3/9 files
--   sum_insured_prior    -- 3/9 files (prior year sum insured)
--   jba_flood            -- 2/9 files (required for Doc B)
--   year_of_build        -- TYPE FIX: build_year is INTEGER but
--                           SoV files store strings like "1900's"
--                           Adding VARCHAR(20) column alongside
--                           existing build_year (left untouched
--                           so FRA views are not broken)
--
-- Fields deliberately NOT added (appear in <=1 file or come
-- from the policy system, not the SoV):
--   start_date, end_date      -- policy system, not SoV
--   product_type              -- only 2/9 files
--   flood_deductible          -- only 1/9 files (Example 11 only)
--   storm_deductible          -- only 1/9 files (Example 11 only)
--   sum_insured_type_prior    -- only 1/9 files (Example 11 only)
--
-- Notes:
--   - All ADD COLUMN statements use IF NOT EXISTS (safe to re-run)
--   - No existing columns, constraints, or views are modified
--   - lor_value / total_insured_value are DERIVED in the exporter
--     (sum_insured x 0.25 / x 1.25) -- do NOT populate from SoV
--   - tenure and construction_type columns are legacy -- the SoV
--     processor writes to occupancy_type and wall/roof/floor_construction
--
-- Run AFTER migrations 001-016.
-- =============================================================


-- =============================================================
-- 1. Add missing SoV fields to silver.properties
-- =============================================================
ALTER TABLE silver.properties

    -- Deductible fields (4-5/9 SoV files)
    ADD COLUMN IF NOT EXISTS deductible             DECIMAL(10, 2),
    ADD COLUMN IF NOT EXISTS basis_of_deductible    VARCHAR(20),

    -- Policy reference (3/9 SoV files)
    ADD COLUMN IF NOT EXISTS policy_reference       VARCHAR(50),

    -- Prior year sum insured (3/9 SoV files)
    -- Enables year-on-year comparison in Doc A
    ADD COLUMN IF NOT EXISTS sum_insured_prior      DECIMAL(15, 2),

    -- JBA flood risk (2/9 SoV files, required for Doc B)
    ADD COLUMN IF NOT EXISTS jba_flood              TEXT,

    -- Year of build as string (TYPE FIX)
    -- build_year INTEGER stays for FRA pipeline compatibility
    -- year_of_build VARCHAR stores SoV values like "1900's", "2005", "Pre-1919"
    -- SoV processor writes here; age_banding is derived from this
    ADD COLUMN IF NOT EXISTS year_of_build          VARCHAR(20);


-- =============================================================
-- 2. Indexes
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_properties_policy_reference
    ON silver.properties (ha_id, policy_reference);

CREATE INDEX IF NOT EXISTS idx_properties_jba_flood
    ON silver.properties (jba_flood)
    WHERE jba_flood IS NOT NULL;


-- =============================================================
-- 3. Comments
-- =============================================================
COMMENT ON COLUMN silver.properties.deductible
    IS 'Policy excess/deductible in GBP. Sourced from SoV where present.';

COMMENT ON COLUMN silver.properties.basis_of_deductible
    IS 'Basis on which deductible applies. Common values: EEL (Each and Every Loss), SEC (Subject to Excess Clause).';

COMMENT ON COLUMN silver.properties.policy_reference
    IS 'Insurer or broker policy reference number. Sourced from SoV where present.';

COMMENT ON COLUMN silver.properties.sum_insured_prior
    IS 'Prior year sum insured in GBP (e.g. 2025 SI when current year is 2026). Enables year-on-year uplift comparison in Doc A.';

COMMENT ON COLUMN silver.properties.jba_flood
    IS 'JBA flood risk indicator. Required for Doc B column Q33. Values vary by file — store as-is from SoV.';

COMMENT ON COLUMN silver.properties.year_of_build
    IS 'Year of build as extracted from SoV — stored as VARCHAR to handle strings like "1900s", "Pre-1919", "2005". age_banding is derived from this field by the SoV processor. build_year (INTEGER) is retained for FRA pipeline compatibility.';


-- =============================================================
-- 4. Self-check: confirm all 6 new columns now exist
-- =============================================================
DO $$
DECLARE
    v_missing TEXT := '';
    v_col     TEXT;
    v_cols    TEXT[] := ARRAY[
        'deductible',
        'basis_of_deductible',
        'policy_reference',
        'sum_insured_prior',
        'jba_flood',
        'year_of_build'
    ];
BEGIN
    FOREACH v_col IN ARRAY v_cols LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'silver'
              AND table_name   = 'properties'
              AND column_name  = v_col
        ) THEN
            v_missing := v_missing || v_col || ' ';
        END IF;
    END LOOP;

    IF v_missing <> '' THEN
        RAISE EXCEPTION 'Migration 017 failed — columns still missing: %', v_missing;
    END IF;

    RAISE NOTICE 'Migration 017: all 6 columns verified in silver.properties.';
END;
$$;