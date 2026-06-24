-- Migration 026: Change silver.properties unique constraint to include portfolio_id
--
-- Context:
--   The current constraint UNIQUE(ha_id, property_reference) was correct when
--   each HA had exactly one portfolio. Now that each SoV upload creates its own
--   portfolio, the same property_reference can legitimately appear in multiple
--   portfolios for the same HA (e.g. a property carried forward to a new renewal).
--
--   Without this change, uploading a second SoV for the same HA silently reassigns
--   portfolio_id on any matching property_reference rows, corrupting the first
--   portfolio's Doc A/B exports with no error raised.
--
--   The new constraint UNIQUE(ha_id, portfolio_id, property_reference) allows the
--   same reference in different portfolios while still preventing duplicates within
--   a single portfolio.
--
-- Impact on sov_processor_v2.py:
--   UPSERT_SQL ON CONFLICT clause must be updated to match this new constraint
--   (done in the same commit — see backend/workers/sov_processor_v2.py).
--
-- Safe to re-run: CREATE UNIQUE INDEX IF NOT EXISTS / DROP INDEX IF EXISTS.

BEGIN;

-- 1. Drop the old HA-scoped constraint
ALTER TABLE silver.properties
    DROP CONSTRAINT IF EXISTS uq_properties_ha_property_ref;

-- Also drop the underlying index if it exists separately
DROP INDEX IF EXISTS silver.uq_properties_ha_property_ref;

-- 2. Add the new portfolio-scoped constraint
--    NULL portfolio_id is excluded so legacy rows (pre-migration 025) without
--    a portfolio_id don't block the constraint — they will always INSERT rather
--    than conflict, which is safer than silently dropping them.
ALTER TABLE silver.properties
    ADD CONSTRAINT uq_properties_ha_portfolio_ref
    UNIQUE (ha_id, portfolio_id, property_reference);

-- 3. Verify
DO $$
DECLARE
    cnt INTEGER;
BEGIN
    SELECT COUNT(*) INTO cnt
    FROM information_schema.table_constraints
    WHERE table_schema = 'silver'
      AND table_name   = 'properties'
      AND constraint_name = 'uq_properties_ha_portfolio_ref';

    IF cnt = 0 THEN
        RAISE EXCEPTION 'Migration 026 failed: new constraint not created';
    END IF;

    RAISE NOTICE 'Migration 026 complete — uq_properties_ha_portfolio_ref created';
END $$;

COMMIT;
