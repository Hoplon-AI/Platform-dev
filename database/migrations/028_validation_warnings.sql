-- 028_validation_warnings.sql
--
-- Validation-warning harvesting for FRA/FRAEW LLM extraction.
-- Each row records the repair/null/skip events the Pydantic validators
-- detected while parsing the LLM response, as a JSONB array of
--   {"field": str, "raw": str|null, "reason": str, "weight": float}
-- The extraction_confidence column now holds a composite score
-- (min of LLM self-report, critical-field coverage, 1 - repair penalty);
-- the raw LLM self-report is kept in raw_features/fraew_features_json
-- as "llm_reported_confidence".

ALTER TABLE silver.fra_features
    ADD COLUMN IF NOT EXISTS validation_warnings JSONB;

ALTER TABLE silver.fraew_features
    ADD COLUMN IF NOT EXISTS validation_warnings JSONB;

COMMENT ON COLUMN silver.fra_features.validation_warnings IS
    'Repair/skip events harvested during Pydantic validation of the LLM extraction; feeds composite extraction_confidence';
COMMENT ON COLUMN silver.fraew_features.validation_warnings IS
    'Repair/skip events harvested during Pydantic validation of the LLM extraction; feeds composite extraction_confidence';
