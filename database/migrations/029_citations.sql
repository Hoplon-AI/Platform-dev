-- 029_citations.sql
--
-- Per-field citations for FRA/FRAEW LLM extraction (groundedness/audit).
-- JSONB object keyed by field name:
--   {"risk_rating": {"pg": 2, "q": "first words of source sentence",
--                    "c": "H|M|L", "verified": true, "found_page": 2,
--                    "snippet": "full source sentence"}, ...}
-- pg/q/c come from the LLM; verified/found_page/snippet are set by Python
-- verification against the [Page N]-marked source text. An unverified
-- citation also appears in validation_warnings and lowers the composite
-- extraction_confidence.

ALTER TABLE silver.fra_features
    ADD COLUMN IF NOT EXISTS citations JSONB;

ALTER TABLE silver.fraew_features
    ADD COLUMN IF NOT EXISTS citations JSONB;

COMMENT ON COLUMN silver.fra_features.citations IS
    'Per-field source citations (page + verbatim quote + verification result) for click-to-verify UI';
COMMENT ON COLUMN silver.fraew_features.citations IS
    'Per-field source citations (page + verbatim quote + verification result) for click-to-verify UI';
