-- Migration 027: Change silver.blocks unique constraint to include portfolio_id
--
-- Context:
--   The current constraint UNIQUE(ha_id, name) was correct when each HA had one
--   portfolio. Now each SoV upload creates its own portfolio, and the same block
--   name (e.g. "CATHCART_BLOCK_01") can legitimately appear in two different
--   portfolios for the same HA (different renewal years).
--
--   Without this change, run_block_detection ON CONFLICT (ha_id, name) silently
--   overwrites portfolio_id on existing blocks, so the earlier portfolio's
--   fra_blocks / map / summary queries return zero results.
--
-- Safe to re-run: IF NOT EXISTS / IF EXISTS guards throughout.

BEGIN;

ALTER TABLE silver.blocks
    DROP CONSTRAINT IF EXISTS uq_blocks_ha_name;

ALTER TABLE silver.blocks
    ADD CONSTRAINT uq_blocks_ha_portfolio_name
    UNIQUE (ha_id, portfolio_id, name);

DO $$
BEGIN
    RAISE NOTICE 'Migration 027 complete — uq_blocks_ha_portfolio_name created';
END $$;

COMMIT;
