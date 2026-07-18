-- Migration 030: Mixed-dwelling support — dwelling_form + is_standalone
--
-- Standalone dwellings (houses, bungalows, single flats) are first-class
-- assets, NOT single-unit pseudo-blocks. silver.blocks stays multi-unit only.
--
--   dwelling_form  — normalised physical form, derived deterministically from
--                    SoV property_type (EPC built_form as NULL-only fallback).
--                    Values: house | bungalow | flat | maisonette | sheltered |
--                            commercial | mixed_use | garage | infrastructure | other
--   is_standalone  — TRUE when the dwelling is not part of any multi-unit block.
--                    Provisional at SoV ingest (no block_reference + house/bungalow
--                    form), finalised by enrichment block detection.
--
-- Both columns are nullable; enrichment follows the SoV-priority rule.

-- ── 1. Columns ──────────────────────────────────────────────────────────────
ALTER TABLE silver.properties
    ADD COLUMN IF NOT EXISTS dwelling_form VARCHAR(30),
    ADD COLUMN IF NOT EXISTS is_standalone BOOLEAN;

CREATE INDEX IF NOT EXISTS idx_properties_standalone
    ON silver.properties (ha_id, portfolio_id)
    WHERE is_standalone;

-- ── 2. Backfill dwelling_form from existing property_type ───────────────────
-- Keyword mapping mirrors backend/core/classification/dwelling_classifier.py.
-- Order matters: bungalow before house, maisonette/tenement before flat.
UPDATE silver.properties
SET dwelling_form = CASE
    WHEN property_type ILIKE '%bungalow%'                                   THEN 'bungalow'
    WHEN property_type ILIKE '%maisonette%'                                 THEN 'maisonette'
    WHEN property_type ILIKE '%shared house%'                               THEN 'house'
    WHEN property_type ILIKE '%house%'
      OR property_type ILIKE '%detached%'
      OR property_type ILIKE '%terrace%'
      OR property_type ILIKE '%semi%'                                       THEN 'house'
    WHEN property_type ILIKE '%sheltered%'                                  THEN 'sheltered'
    WHEN property_type ILIKE '%garage%'                                     THEN 'garage'
    WHEN property_type ILIKE '%mixed%'                                      THEN 'mixed_use'
    WHEN property_type ILIKE '%retail%'
      OR property_type ILIKE '%shop%'
      OR property_type ILIKE '%office%'
      OR property_type ILIKE '%commercial%'
      OR property_type ILIKE '%industrial%'
      OR property_type ILIKE '%community%'                                  THEN 'commercial'
    WHEN property_type ILIKE '%drainage%'
      OR property_type ILIKE '%services%'                                   THEN 'infrastructure'
    WHEN property_type ILIKE '%flat%'
      OR property_type ILIKE '%apartment%'
      OR property_type ILIKE '%studio%'
      OR property_type ILIKE '%tenement%'
      OR property_type ILIKE '%deck access%'
      OR property_type ILIKE '%main door%'
      OR property_type ILIKE '%multiple residential%'                       THEN 'flat'
    WHEN property_type IS NOT NULL AND btrim(property_type) <> ''           THEN 'other'
    ELSE NULL
END
WHERE dwelling_form IS NULL;

-- ── 3. Backfill is_standalone ────────────────────────────────────────────────
-- No block linkage at all → standalone; anything block-linked → not standalone.
UPDATE silver.properties
SET is_standalone = (
    (block_reference IS NULL OR btrim(block_reference) = '')
    AND block_id IS NULL
)
WHERE is_standalone IS NULL;

-- ── 4. Gold view: standalone dwellings ──────────────────────────────────────
CREATE OR REPLACE VIEW gold.standalone_dwellings_v1 AS
SELECT
    p.ha_id,
    p.portfolio_id,
    p.property_id,
    p.property_reference,
    p.address,
    p.postcode,
    p.dwelling_form,
    p.property_type,
    p.occupancy_type,
    p.sum_insured,
    p.year_of_build,
    p.age_banding,
    p.wall_construction,
    p.roof_construction,
    p.storeys,
    p.uprn,
    p.uprn_confidence,
    p.epc_rating,
    p.flood_risk_band,
    p.is_listed,
    p.listed_grade,
    p.enrichment_status
FROM silver.properties p
WHERE p.is_standalone
  AND COALESCE(p.dwelling_form, '') NOT IN ('garage', 'infrastructure');

COMMENT ON COLUMN silver.properties.dwelling_form IS
    'Normalised dwelling form (house/bungalow/flat/...), derived deterministically — see dwelling_classifier.py';
COMMENT ON COLUMN silver.properties.is_standalone IS
    'TRUE = not part of any multi-unit block. Provisional at SoV ingest, finalised by block detection.';
