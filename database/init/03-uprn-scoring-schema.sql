-- ============================================
-- UPRN Confidence Scoring - Additional Schema
-- ============================================
-- Run after spatial_seed.dump is restored
-- Creates materialized view for density lookups

-- Verify required tables exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'uprn_points') THEN
        RAISE EXCEPTION 'uprn_points table not found - ensure spatial_seed.dump is restored first';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'postcode_centroids') THEN
        RAISE EXCEPTION 'postcode_centroids table not found - ensure spatial_seed.dump is restored first';
    END IF;
END $$;

-- Ensure spatial indexes exist (idempotent)
CREATE INDEX IF NOT EXISTS idx_uprn_geom
    ON uprn_points USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_postcode_geom
    ON postcode_centroids USING GIST (geom);

-- Materialized view for UPRN density (30m radius neighbor count)
-- This significantly speeds up density lookups
DROP MATERIALIZED VIEW IF EXISTS uprn_density_30m;

CREATE MATERIALIZED VIEW uprn_density_30m AS
SELECT
    u1.uprn,
    COUNT(*) as neighbor_count
FROM uprn_points u1
JOIN uprn_points u2
    ON ST_DWithin(u1.geom, u2.geom, 30)
GROUP BY u1.uprn;

CREATE UNIQUE INDEX idx_uprn_density_uprn
    ON uprn_density_30m(uprn);

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'UPRN scoring schema initialized successfully';
    RAISE NOTICE 'Density view created with % records', (SELECT COUNT(*) FROM uprn_density_30m);
END $$;