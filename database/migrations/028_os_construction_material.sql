-- OS NGD constructionmaterial stored separately from SoV-merged wall_construction,
-- so the Portfolio Insights panel can chart OS-derived construction on its own.
ALTER TABLE silver.properties
  ADD COLUMN IF NOT EXISTS os_construction_material TEXT;
