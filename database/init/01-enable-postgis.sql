-- Enable PostGIS extension
-- This script runs automatically when the database is first initialized

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable PostGIS Topology extension (optional, for topology support)
-- CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Verify PostGIS installation
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis') THEN
        RAISE NOTICE 'PostGIS extension enabled successfully';
    ELSE
        RAISE EXCEPTION 'Failed to enable PostGIS extension';
    END IF;
END $$;
