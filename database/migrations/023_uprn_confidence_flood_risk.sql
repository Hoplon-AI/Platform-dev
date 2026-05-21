-- Migration 023: UPRN confidence scoring + flood risk columns
-- Adds:
--   silver.properties.uprn_confidence        — GREEN / AMBER / LOW / RED
--   silver.properties.uprn_confidence_reason — human-readable mismatch explanation
--   silver.properties.flood_risk_band        — High / Medium / Low / Very Low / Could not match
--   silver.properties.flood_risk_source      — EA RoFRS / NRW FRAW / SEPA
--   silver.properties.flood_risk_note        — additional context (null when band is unambiguous)

ALTER TABLE silver.properties
    ADD COLUMN IF NOT EXISTS uprn_confidence        VARCHAR(10),
    ADD COLUMN IF NOT EXISTS uprn_confidence_reason TEXT,
    ADD COLUMN IF NOT EXISTS flood_risk_band        VARCHAR(30),
    ADD COLUMN IF NOT EXISTS flood_risk_source      VARCHAR(50),
    ADD COLUMN IF NOT EXISTS flood_risk_note        TEXT;
