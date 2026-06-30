-- Migration 025: Backfill portfolio_id on silver.properties and silver.blocks
--
-- Context:
--   portfolio_id columns exist on both tables (added in 001b) but have never
--   been populated — all rows carry NULL. This migration links every existing
--   property and block row to its correct portfolio by joining on ha_id,
--   taking the most recently created portfolio per HA as the canonical one.
--   It also adds composite (ha_id, portfolio_id) indexes to replace the
--   single-column portfolio_id indexes, which are insufficient for the
--   tenant-scoped queries used throughout the exporter and dashboard code.
--
-- Safe to re-run: UPDATE is idempotent (WHERE portfolio_id IS NULL guard).
-- Does NOT add NOT NULL constraint — new rows from SoV uploads will carry
-- NULL until sov_processor_v3.py is updated (migration 026 will enforce).

BEGIN;

-- ── 1. Backfill silver.properties ──────────────────────────────────────────

UPDATE silver.properties p
SET    portfolio_id = latest.portfolio_id
FROM (
    SELECT DISTINCT ON (ha_id)
        ha_id,
        portfolio_id
    FROM   silver.portfolios
    ORDER  BY ha_id, created_at DESC NULLS LAST
) latest
WHERE  p.ha_id          = latest.ha_id
AND    p.portfolio_id   IS NULL;

-- ── 2. Backfill silver.blocks ───────────────────────────────────────────────

UPDATE silver.blocks b
SET    portfolio_id = latest.portfolio_id
FROM (
    SELECT DISTINCT ON (ha_id)
        ha_id,
        portfolio_id
    FROM   silver.portfolios
    ORDER  BY ha_id, created_at DESC NULLS LAST
) latest
WHERE  b.ha_id          = latest.ha_id
AND    b.portfolio_id   IS NULL;

-- ── 3. Drop single-column portfolio_id indexes (too broad for tenant queries) ──

DROP INDEX IF EXISTS silver.idx_properties_portfolio_id;
DROP INDEX IF EXISTS silver.idx_blocks_portfolio_id;

-- ── 4. Add composite (ha_id, portfolio_id) indexes ─────────────────────────
-- These replace the single-column ones and match the WHERE p.ha_id=$1 AND
-- p.portfolio_id=$2 pattern used in exporters, underwriter router, and
-- enrichment worker.

CREATE INDEX IF NOT EXISTS idx_properties_ha_portfolio
    ON silver.properties (ha_id, portfolio_id);

CREATE INDEX IF NOT EXISTS idx_blocks_ha_portfolio
    ON silver.blocks (ha_id, portfolio_id);

-- ── 5. Verify backfill ──────────────────────────────────────────────────────

DO $$
DECLARE
    null_props  BIGINT;
    null_blocks BIGINT;
BEGIN
    SELECT COUNT(*) INTO null_props  FROM silver.properties WHERE portfolio_id IS NULL;
    SELECT COUNT(*) INTO null_blocks FROM silver.blocks     WHERE portfolio_id IS NULL;

    IF null_props > 0 THEN
        RAISE WARNING 'Migration 025: % properties still have NULL portfolio_id — no matching portfolio row for their ha_id', null_props;
    END IF;

    IF null_blocks > 0 THEN
        RAISE WARNING 'Migration 025: % blocks still have NULL portfolio_id — no matching portfolio row for their ha_id', null_blocks;
    END IF;

    RAISE NOTICE 'Migration 025 complete — properties nulls: %, blocks nulls: %', null_props, null_blocks;
END $$;

COMMIT;
