-- Gold layer views (dashboard-ready aggregations)
-- Migration: 001_gold_layer.sql
--
-- Notes:
-- - Gold should be stable and API-friendly: one query per widget.
-- - Prefer views initially; promote hot paths to MATERIALIZED VIEW later.
-- - Joins are keyed by property_id, but UPRN is used for many initial document joins.

CREATE SCHEMA IF NOT EXISTS gold;

-- ---------------------------------------
-- 1) Portfolio summary (cards)
-- ---------------------------------------
CREATE OR REPLACE VIEW gold.portfolio_summary_v1 AS
SELECT
  p.portfolio_id,
  p.ha_id,
  p.name AS portfolio_name,
  p.renewal_year,

  COUNT(DISTINCT b.block_id)      AS total_blocks,
  COALESCE(SUM(b.total_units), 0) AS total_units,
  COUNT(DISTINCT pr.property_id)  AS total_properties,

  NOW() AS computed_at
FROM portfolios p
LEFT JOIN blocks b
  ON b.portfolio_id = p.portfolio_id
LEFT JOIN properties pr
  ON pr.portfolio_id = p.portfolio_id
GROUP BY p.portfolio_id, p.ha_id, p.name, p.renewal_year;

-- ---------------------------------------
-- 2) Portfolio risk distribution (chart)
-- ---------------------------------------
CREATE OR REPLACE VIEW gold.portfolio_risk_distribution_v1 AS
SELECT
  p.portfolio_id,
  p.ha_id,
  pr.risk_rating,
  COUNT(*) AS property_count
FROM portfolios p
JOIN properties pr
  ON pr.portfolio_id = p.portfolio_id
WHERE pr.risk_rating IS NOT NULL
GROUP BY p.portfolio_id, p.ha_id, pr.risk_rating;

-- ---------------------------------------
-- 3) Portfolio readiness / data completeness
-- ---------------------------------------
-- These are simple completeness percentages; map them to "statutory vs insurance"
-- readiness scores in the API layer (or expand this view later with business rules).
CREATE OR REPLACE VIEW gold.portfolio_readiness_v1 AS
WITH base AS (
  SELECT
    pr.portfolio_id,
    pr.ha_id,
    pr.property_id,
    pr.uprn,
    pr.postcode,
    pr.latitude,
    pr.longitude,
    pr.height_m,
    pr.build_year,
    pr.construction_type,
    pr.risk_rating
  FROM properties pr
),
flags AS (
  SELECT
    portfolio_id,
    ha_id,
    property_id,
    (uprn IS NOT NULL) AS has_uprn,
    (postcode IS NOT NULL) AS has_postcode,
    (latitude IS NOT NULL AND longitude IS NOT NULL) AS has_geo,
    (height_m IS NOT NULL) AS has_height,
    (build_year IS NOT NULL) AS has_build_year,
    (construction_type IS NOT NULL) AS has_construction,
    (risk_rating IS NOT NULL) AS has_risk_rating
  FROM base
)
SELECT
  portfolio_id,
  ha_id,
  COUNT(*) AS total_properties,

  AVG(has_uprn::int)::numeric(5,2)         AS pct_has_uprn,
  AVG(has_postcode::int)::numeric(5,2)     AS pct_has_postcode,
  AVG(has_geo::int)::numeric(5,2)          AS pct_has_geo,
  AVG(has_height::int)::numeric(5,2)       AS pct_has_height,
  AVG(has_build_year::int)::numeric(5,2)   AS pct_has_build_year,
  AVG(has_construction::int)::numeric(5,2) AS pct_has_construction,
  AVG(has_risk_rating::int)::numeric(5,2)  AS pct_has_risk_rating,

  NOW() AS computed_at
FROM flags
GROUP BY portfolio_id, ha_id;

-- ---------------------------------------
-- 4) Missing info gaps (action list)
-- ---------------------------------------
CREATE OR REPLACE VIEW gold.portfolio_missing_info_gaps_v1 AS
SELECT
  pr.portfolio_id,
  pr.ha_id,
  pr.property_id,
  pr.block_id,
  pr.uprn,
  CASE
    WHEN pr.uprn IS NULL THEN 'missing_uprn'
    WHEN pr.postcode IS NULL THEN 'missing_postcode'
    WHEN pr.latitude IS NULL OR pr.longitude IS NULL THEN 'missing_geocode'
    WHEN pr.height_m IS NULL THEN 'missing_height'
    WHEN pr.build_year IS NULL THEN 'missing_build_year'
    WHEN pr.construction_type IS NULL THEN 'missing_construction'
    WHEN pr.risk_rating IS NULL THEN 'missing_risk_rating'
    ELSE NULL
  END AS gap_type,
  pr.updated_at AS last_seen_at
FROM properties pr
WHERE
  pr.uprn IS NULL
  OR pr.postcode IS NULL
  OR pr.latitude IS NULL OR pr.longitude IS NULL
  OR pr.height_m IS NULL
  OR pr.build_year IS NULL
  OR pr.construction_type IS NULL
  OR pr.risk_rating IS NULL;

-- ---------------------------------------
-- 5) Recent activity (upload audit)
-- ---------------------------------------
-- This is HA-scoped because uploads are HA-scoped. If/when uploads are mapped to
-- portfolio_id, you can create a portfolio-scoped view too.
CREATE OR REPLACE VIEW gold.ha_recent_activity_v1 AS
SELECT
  ua.ha_id,
  ua.upload_id AS event_id,
  'upload'::text AS event_type,
  ua.file_type,
  ua.filename,
  ua.user_id AS actor_id,
  ua.uploaded_at AS created_at,
  ua.status,
  ua.metadata
FROM upload_audit ua
WHERE ua.uploaded_at >= NOW() - INTERVAL '30 days'
ORDER BY ua.uploaded_at DESC;

