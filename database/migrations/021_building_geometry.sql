-- 021: Store the OS NGD building footprint polygon (WGS84 GeoJSON) per property.
-- Captured during enrichment from the same NGD call that fills building_footprint_m2.
-- The risk map renders one polygon per block (colored by risk) at close zoom.
ALTER TABLE silver.properties
  ADD COLUMN IF NOT EXISTS building_geometry JSONB;
