-- =============================================================
-- Migration: 012_underwriter_dashboard.sql
--
-- Adds everything needed for the Underwriter Portfolio Overview
-- dashboard. Run this AFTER migrations 001–011.
--
-- What this does (in order):
--   1. Underwriter users table
--   2. HA <-> Underwriter access control table
--   3. New columns on silver.properties  (sum_insured, property_type, responsible_party)
--   4. New columns on silver.blocks      (fra_status, fraew_status)
--   5. Gold view: portfolio_composition_v1  (Houses / Flats / Blocks widget)
--   6. Gold view: underwriter_summary_v1   (header KPI cards)
--   7. Gold view: fra_status_by_block_v1   (FRA RED / AMBER / GREEN counts)
--   8. Gold view: portfolio_map_v1         (map markers with colour)
-- =============================================================


-- =============================================================
-- 1. Underwriter users
--    Separate table from HA users. An underwriter belongs to
--    an insurance organisation (e.g. Aviva) and can be granted
--    access to one or more HA portfolios.
-- =============================================================

CREATE TABLE IF NOT EXISTS underwriter_users (
    underwriter_id  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    full_name       VARCHAR(255) NOT NULL,
    organisation    VARCHAR(255),           -- e.g. 'Aviva', 'RSA'
    role            VARCHAR(50)  NOT NULL DEFAULT 'underwriter',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMP,
    metadata        JSONB
);

CREATE INDEX IF NOT EXISTS idx_uw_users_email  ON underwriter_users(email);
CREATE INDEX IF NOT EXISTS idx_uw_users_org    ON underwriter_users(organisation);


-- =============================================================
-- 2. HA <-> Underwriter access control
--    An underwriter must be explicitly granted access to
--    a specific HA + renewal year before they can view data.
-- =============================================================

CREATE TABLE IF NOT EXISTS ha_underwriter_access (
    access_id       UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    ha_id           VARCHAR(50)  NOT NULL REFERENCES housing_associations(ha_id) ON DELETE CASCADE,
    underwriter_id  UUID         NOT NULL REFERENCES underwriter_users(underwriter_id) ON DELETE CASCADE,
    renewal_year    INTEGER,                -- NULL = access to all years
    access_level    VARCHAR(20)  NOT NULL DEFAULT 'read',   -- 'read' | 'export'
    granted_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    granted_by      VARCHAR(100),
    expires_at      TIMESTAMP,             -- NULL = never expires
    UNIQUE (ha_id, underwriter_id, renewal_year)
);

CREATE INDEX IF NOT EXISTS idx_ha_uw_access_ha          ON ha_underwriter_access(ha_id);
CREATE INDEX IF NOT EXISTS idx_ha_uw_access_underwriter ON ha_underwriter_access(underwriter_id);


-- =============================================================
-- 3. New columns on silver.properties
--
--    sum_insured      – declared insured value from SOV CSV (£)
--    property_type    – House / Flat / Block (from SOV CSV)
--    responsible_party– who manages fire safety for this unit
-- =============================================================

ALTER TABLE silver.properties
    ADD COLUMN IF NOT EXISTS sum_insured       DECIMAL(15, 2),
    ADD COLUMN IF NOT EXISTS property_type     VARCHAR(30),
    ADD COLUMN IF NOT EXISTS responsible_party VARCHAR(20) DEFAULT 'ha_controlled';

CREATE INDEX IF NOT EXISTS idx_properties_property_type
    ON silver.properties(property_type);

CREATE INDEX IF NOT EXISTS idx_properties_responsible_party
    ON silver.properties(responsible_party);

COMMENT ON COLUMN silver.properties.sum_insured
    IS 'Declared insured value in GBP — sourced from the SOV CSV upload';

COMMENT ON COLUMN silver.properties.property_type
    IS 'house | flat | block_common — normalised from the SOV CSV type column';

COMMENT ON COLUMN silver.properties.responsible_party
    IS 'ha_controlled | third_party — who holds fire safety responsibility';


-- =============================================================
-- 4. New columns on silver.blocks
--
--    fra_status   – latest FRA RAG status for this block
--    fraew_status – whether an FRAEW assessment exists for this block
--
--    These are DENORMALISED from the document feature tables so
--    the dashboard can count RED/AMBER/GREEN blocks with a single
--    query instead of joining 3 tables every time.
--    They are updated by the silver processor when a PDF is ingested.
-- =============================================================

ALTER TABLE silver.blocks
    ADD COLUMN IF NOT EXISTS fra_status   VARCHAR(10),
    ADD COLUMN IF NOT EXISTS fraew_status VARCHAR(20);

COMMENT ON COLUMN silver.blocks.fra_status
    IS 'Latest FRA RAG status for this block: RED | AMBER | GREEN — set by silver processor on PDF ingest';

COMMENT ON COLUMN silver.blocks.fraew_status
    IS 'FRAEW coverage status: assessed | pending | not_required — set by silver processor on PDF ingest';


-- =============================================================
-- 5. Gold view: portfolio_composition_v1
--    Powers the "Portfolio Composition" widget.
--    Returns unit counts split by property_type and
--    responsible_party for a given portfolio.
-- =============================================================

CREATE OR REPLACE VIEW gold.portfolio_composition_v1 AS
SELECT
    pr.portfolio_id,
    pr.ha_id,
    p.name                                          AS portfolio_name,
    p.renewal_year,

    -- ---- totals ----
    COUNT(*)                                        AS total_properties,
    COALESCE(SUM(pr.units), 0)                      AS total_units,

    -- ---- houses ----
    COUNT(*)    FILTER (WHERE pr.property_type = 'house')          AS house_count,
    COALESCE(SUM(pr.units) FILTER (WHERE pr.property_type = 'house'), 0)
                                                    AS house_units,

    -- ---- flats ----
    COUNT(*)    FILTER (WHERE pr.property_type = 'flat')           AS flat_count,
    COALESCE(SUM(pr.units) FILTER (WHERE pr.property_type = 'flat'), 0)
                                                    AS flat_units,

    -- flat sub-split by responsible party
    COALESCE(SUM(pr.units) FILTER (
        WHERE pr.property_type = 'flat'
          AND (pr.responsible_party = 'ha_controlled' OR pr.responsible_party IS NULL)
    ), 0)                                           AS flat_units_ha_controlled,

    COALESCE(SUM(pr.units) FILTER (
        WHERE pr.property_type = 'flat'
          AND pr.responsible_party = 'third_party'
    ), 0)                                           AS flat_units_third_party,

    -- ---- blocks (common areas) ----
    COUNT(*)    FILTER (WHERE pr.property_type = 'block_common')   AS block_count,
    COALESCE(SUM(pr.units) FILTER (WHERE pr.property_type = 'block_common'), 0)
                                                    AS block_units,

    COUNT(*)    FILTER (
        WHERE pr.property_type = 'block_common'
          AND pr.responsible_party = 'third_party'
    )                                               AS blocks_third_party_count,

    -- ---- warning flags (drive amber callout boxes in UI) ----
    (SUM(pr.units) FILTER (
        WHERE pr.property_type = 'flat'
          AND pr.responsible_party = 'third_party'
    ) > 0)                                          AS has_third_party_flats,

    (COUNT(*) FILTER (
        WHERE pr.property_type = 'block_common'
          AND pr.responsible_party = 'third_party'
    ) > 0)                                          AS has_third_party_blocks,

    NOW()                                           AS computed_at

FROM silver.properties pr
JOIN silver.portfolios p ON p.portfolio_id = pr.portfolio_id
GROUP BY pr.portfolio_id, pr.ha_id, p.name, p.renewal_year;

COMMENT ON VIEW gold.portfolio_composition_v1
    IS 'Portfolio Composition widget — unit counts split by property type (house/flat/block) and responsible party';


-- =============================================================
-- 6. Gold view: underwriter_summary_v1
--    Powers the 4 header KPI cards:
--      • Total Insured Value
--      • FRA Red Rating  (count of RED blocks)
--      • FRAEW Status    (assessed / total blocks ≥ 11m)
-- =============================================================

CREATE OR REPLACE VIEW gold.underwriter_summary_v1 AS
SELECT
    p.portfolio_id,
    p.ha_id,
    p.name        AS portfolio_name,
    p.renewal_year,

    -- Total Insured Value (sum of all property sum_insured)
    COALESCE(SUM(pr.sum_insured), 0)                AS total_insured_value,

    -- How many properties have sum_insured populated
    COUNT(pr.property_id) FILTER (WHERE pr.sum_insured IS NOT NULL)
                                                    AS properties_with_tiv,
    COUNT(pr.property_id)                           AS total_properties,

    -- FRA status — count blocks by RAG
    COUNT(b.block_id) FILTER (WHERE b.fra_status = 'RED')
                                                    AS fra_red_count,
    COUNT(b.block_id) FILTER (WHERE b.fra_status = 'AMBER')
                                                    AS fra_amber_count,
    COUNT(b.block_id) FILTER (WHERE b.fra_status = 'GREEN')
                                                    AS fra_green_count,
    COUNT(b.block_id) FILTER (WHERE b.fra_status IS NOT NULL)
                                                    AS fra_assessed_blocks,
    COUNT(b.block_id)                               AS total_blocks,

    -- FRAEW status — blocks ≥ 11m
    COUNT(b.block_id) FILTER (
        WHERE b.height_category IN ('11-16m', '16m+')
    )                                               AS blocks_requiring_fraew,

    COUNT(b.block_id) FILTER (
        WHERE b.height_category IN ('11-16m', '16m+')
          AND b.fraew_status = 'assessed'
    )                                               AS fraew_assessed_count,

    COUNT(b.block_id) FILTER (
        WHERE b.height_category IN ('11-16m', '16m+')
          AND (b.fraew_status IS NULL OR b.fraew_status = 'pending')
    )                                               AS fraew_pending_count,

    NOW()                                           AS computed_at

FROM silver.portfolios p
LEFT JOIN silver.properties pr ON pr.portfolio_id = p.portfolio_id
LEFT JOIN silver.blocks      b  ON b.portfolio_id  = p.portfolio_id
GROUP BY p.portfolio_id, p.ha_id, p.name, p.renewal_year;

COMMENT ON VIEW gold.underwriter_summary_v1
    IS 'Header KPI cards — Total Insured Value, FRA Red count, FRAEW assessed/pending counts';


-- =============================================================
-- 7. Gold view: fra_status_by_block_v1
--    Powers the "FRA Status & Remediation" section.
--    Returns one row per block with its FRA RAG status,
--    assessment date, and whether it is HA or third-party managed.
-- =============================================================

CREATE OR REPLACE VIEW gold.fra_status_by_block_v1 AS
SELECT
    b.block_id,
    b.ha_id,
    b.portfolio_id,
    b.name                  AS block_name,
    b.height_category,
    b.total_units,
    b.fra_status,           -- RED | AMBER | GREEN (denormalised from silver processor)
    b.fraew_status,

    -- Latest FRA document details for this block
    df.assessment_date      AS fra_assessment_date,
    df.assessor_company     AS fra_assessor_company,
    fra.assessment_valid_until,
    fra.risk_rating         AS fra_raw_risk_rating,

    -- Latest FRAEW document details
    fraew.building_risk_rating AS fraew_risk_rating,
    fraew.pas_9980_compliant,
    fraew.has_remedial_actions,

    -- Responsible party comes from the properties in this block
    BOOL_OR(pr.responsible_party = 'third_party') AS is_third_party_managed,

    b.updated_at            AS block_updated_at

FROM silver.blocks b
-- join most recent FRA document for this block
LEFT JOIN LATERAL (
    SELECT df2.feature_id, df2.assessment_date, df2.assessor_company
    FROM silver.document_features df2
    WHERE df2.block_id = b.block_id
      AND df2.document_type = 'fra_document'
    ORDER BY df2.assessment_date DESC NULLS LAST
    LIMIT 1
) df ON TRUE
LEFT JOIN silver.fra_features fra
    ON fra.feature_id = df.feature_id
-- join most recent FRAEW document for this block
LEFT JOIN LATERAL (
    SELECT fraew2.fraew_id, fraew2.building_risk_rating,
           fraew2.pas_9980_compliant, fraew2.has_remedial_actions
    FROM silver.fraew_features fraew2
    JOIN silver.document_features df3
        ON df3.feature_id = fraew2.feature_id
       AND df3.block_id = b.block_id
    ORDER BY df3.assessment_date DESC NULLS LAST
    LIMIT 1
) fraew ON TRUE
-- get responsible_party from properties linked to this block
LEFT JOIN silver.properties pr ON pr.block_id = b.block_id
GROUP BY
    b.block_id, b.ha_id, b.portfolio_id, b.name, b.height_category,
    b.total_units, b.fra_status, b.fraew_status, b.updated_at,
    df.assessment_date, df.assessor_company,
    fra.assessment_valid_until, fra.risk_rating,
    fraew.building_risk_rating, fraew.pas_9980_compliant, fraew.has_remedial_actions;

COMMENT ON VIEW gold.fra_status_by_block_v1
    IS 'FRA Status & Remediation section — one row per block with RAG status, assessment dates, and FRAEW details';


-- =============================================================
-- 8. Gold view: portfolio_map_v1
--    Powers the Portfolio Map.
--    Returns one row per property/block with coordinates
--    and a colour code based on FRA status.
-- =============================================================

CREATE OR REPLACE VIEW gold.portfolio_map_v1 AS
SELECT
    pr.property_id,
    pr.portfolio_id,
    pr.ha_id,
    pr.address,
    pr.postcode,
    pr.latitude,
    pr.longitude,
    pr.units,
    pr.property_type,
    pr.block_id,
    b.name          AS block_name,
    b.fra_status    AS block_fra_status,

    -- Colour code for map marker
    -- Rule: if property is in a block, use the block's FRA status
    --       otherwise use the property's own risk_rating
    CASE
        WHEN b.fra_status = 'RED'   THEN 'red'
        WHEN b.fra_status = 'AMBER' THEN 'amber'
        WHEN b.fra_status = 'GREEN' THEN 'green'
        WHEN pr.risk_rating IN ('A', 'B') THEN 'green'
        WHEN pr.risk_rating IN ('C', 'D') THEN 'amber'
        WHEN pr.risk_rating = 'E'         THEN 'red'
        ELSE 'grey'
    END             AS map_colour

FROM silver.properties pr
LEFT JOIN silver.blocks b ON b.block_id = pr.block_id
WHERE pr.latitude  IS NOT NULL
  AND pr.longitude IS NOT NULL;

COMMENT ON VIEW gold.portfolio_map_v1
    IS 'Map markers — one row per property with coordinates and FRA-based colour code (red/amber/green/grey)';