-- Schema reorganization: Create proper medallion architecture
-- Migration: 011_schema_reorganization.sql
--
-- Moves silver layer tables from public to silver schema
-- Updates gold views to reference silver schema tables
--
-- Structure after migration:
-- - public: Reference/system tables (housing_associations, upload_audit, processing_audit, etc.)
-- - silver: Entity/feature tables (properties, document_features, fraew_features, etc.)
-- - gold: Analytics views (portfolio summaries, risk distributions, etc.)

-- Create silver schema if not exists
CREATE SCHEMA IF NOT EXISTS silver;

-- Grant usage on silver schema to current role
GRANT USAGE ON SCHEMA silver TO PUBLIC;

-- -----------------------------
-- Move Silver layer tables from public to silver schema
-- -----------------------------

-- Entity tables
ALTER TABLE IF EXISTS portfolios SET SCHEMA silver;
ALTER TABLE IF EXISTS blocks SET SCHEMA silver;
ALTER TABLE IF EXISTS properties SET SCHEMA silver;
ALTER TABLE IF EXISTS epc_data SET SCHEMA silver;
ALTER TABLE IF EXISTS uprn_mappings SET SCHEMA silver;

-- Document feature tables
ALTER TABLE IF EXISTS document_features SET SCHEMA silver;
ALTER TABLE IF EXISTS fraew_features SET SCHEMA silver;
ALTER TABLE IF EXISTS fra_features SET SCHEMA silver;
ALTER TABLE IF EXISTS scr_features SET SCHEMA silver;
ALTER TABLE IF EXISTS frsa_features SET SCHEMA silver;
ALTER TABLE IF EXISTS building_safety_features SET SCHEMA silver;
ALTER TABLE IF EXISTS docb_features SET SCHEMA silver;

-- -----------------------------
-- Update Foreign Key constraint on uprn_lineage_map
-- (points to silver.properties now)
-- -----------------------------
-- Drop and recreate the FK constraint
ALTER TABLE uprn_lineage_map DROP CONSTRAINT IF EXISTS fk_uprn_lineage_map_property;
ALTER TABLE uprn_lineage_map
    ADD CONSTRAINT fk_uprn_lineage_map_property
    FOREIGN KEY (property_id) REFERENCES silver.properties(property_id);

-- -----------------------------
-- Recreate Gold layer views with silver schema references
-- -----------------------------

-- 1) Portfolio summary (cards)
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
FROM silver.portfolios p
LEFT JOIN silver.blocks b
  ON b.portfolio_id = p.portfolio_id
LEFT JOIN silver.properties pr
  ON pr.portfolio_id = p.portfolio_id
GROUP BY p.portfolio_id, p.ha_id, p.name, p.renewal_year;

-- 2) Portfolio risk distribution (chart)
CREATE OR REPLACE VIEW gold.portfolio_risk_distribution_v1 AS
SELECT
  p.portfolio_id,
  p.ha_id,
  pr.risk_rating,
  COUNT(*) AS property_count
FROM silver.portfolios p
JOIN silver.properties pr
  ON pr.portfolio_id = p.portfolio_id
WHERE pr.risk_rating IS NOT NULL
GROUP BY p.portfolio_id, p.ha_id, pr.risk_rating;

-- 3) Portfolio readiness / data completeness
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
  FROM silver.properties pr
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

-- 4) Missing info gaps (action list)
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
FROM silver.properties pr
WHERE
  pr.uprn IS NULL
  OR pr.postcode IS NULL
  OR pr.latitude IS NULL OR pr.longitude IS NULL
  OR pr.height_m IS NULL
  OR pr.build_year IS NULL
  OR pr.construction_type IS NULL
  OR pr.risk_rating IS NULL;

-- 5) Recent activity (upload audit) - references public.upload_audit
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

-- 6) High-rise building indicators (Category A - ML+UI)
CREATE OR REPLACE VIEW gold.high_rise_indicators_v1 AS
SELECT
    bsf.feature_id,
    bsf.ha_id,
    bsf.upload_id,
    df.document_type,
    df.building_name,
    df.address,
    df.uprn,
    df.postcode,
    bsf.high_rise_building_mentioned,
    bsf.building_height_category,
    bsf.number_of_storeys,
    bsf.building_height_metres,
    bsf.number_of_high_rise_buildings,
    bsf.building_safety_act_applicable,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM silver.building_safety_features bsf
JOIN silver.document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.high_rise_building_mentioned = TRUE
   OR bsf.building_height_category IN ('HIGH_RISE', 'MEDIUM_RISE');

-- 7) Evacuation strategies (Category A - ML+UI)
CREATE OR REPLACE VIEW gold.evacuation_strategies_v1 AS
SELECT
    bsf.feature_id,
    bsf.ha_id,
    bsf.upload_id,
    df.document_type,
    df.building_name,
    df.address,
    df.uprn,
    bsf.evacuation_strategy_mentioned,
    bsf.evacuation_strategy_type,
    bsf.evacuation_strategy_description,
    bsf.evacuation_strategy_changed,
    bsf.personal_evacuation_plans_mentioned,
    bsf.evacuation_support_required,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM silver.building_safety_features bsf
JOIN silver.document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.evacuation_strategy_mentioned = TRUE;

-- 8) Fire safety measures summary (Category A - ML+UI)
CREATE OR REPLACE VIEW gold.fire_safety_measures_summary_v1 AS
SELECT
    bsf.feature_id,
    bsf.ha_id,
    bsf.upload_id,
    df.document_type,
    df.building_name,
    df.address,
    df.uprn,
    bsf.fire_safety_measures_mentioned,
    bsf.fire_doors_mentioned,
    bsf.fire_safety_officers_mentioned,
    (bsf.agentic_features_json->'fire_safety_measures'->'fire_safety_systems')::jsonb AS fire_safety_systems,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM silver.building_safety_features bsf
JOIN silver.document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.fire_safety_measures_mentioned = TRUE;

-- 9) Structural integrity summary (Category A - ML+UI)
CREATE OR REPLACE VIEW gold.structural_integrity_summary_v1 AS
SELECT
    bsf.feature_id,
    bsf.ha_id,
    bsf.upload_id,
    df.document_type,
    df.building_name,
    df.address,
    df.uprn,
    bsf.structural_integrity_mentioned,
    bsf.structural_assessments_mentioned,
    bsf.structural_risks_mentioned,
    bsf.structural_work_mentioned,
    bsf.structural_maintenance_required,
    (bsf.agentic_features_json->'structural_integrity'->'structural_assessments')::jsonb AS structural_assessments,
    (bsf.agentic_features_json->'structural_integrity'->'structural_risks')::jsonb AS structural_risks,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM silver.building_safety_features bsf
JOIN silver.document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.structural_integrity_mentioned = TRUE
   OR bsf.structural_assessments_mentioned = TRUE
   OR bsf.structural_risks_mentioned = TRUE;

-- 10) Maintenance requirements summary (Category A - ML+UI)
CREATE OR REPLACE VIEW gold.maintenance_requirements_summary_v1 AS
SELECT
    bsf.feature_id,
    bsf.ha_id,
    bsf.upload_id,
    df.document_type,
    df.building_name,
    df.address,
    df.uprn,
    bsf.maintenance_mentioned,
    bsf.maintenance_schedules_mentioned,
    bsf.maintenance_checks_mentioned,
    bsf.tenancy_audits_mentioned,
    (bsf.agentic_features_json->'maintenance_requirements'->'maintenance_schedules')::jsonb AS maintenance_schedules,
    (bsf.agentic_features_json->'maintenance_requirements'->'maintenance_checks')::jsonb AS maintenance_checks,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM silver.building_safety_features bsf
JOIN silver.document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.maintenance_mentioned = TRUE
   OR bsf.maintenance_schedules_mentioned = TRUE
   OR bsf.tenancy_audits_mentioned = TRUE;

-- 11) Building Safety Act 2022 compliance (Category B - Compliance/workflow)
CREATE OR REPLACE VIEW gold.bsa_compliance_v1 AS
SELECT
    bsf.feature_id,
    bsf.ha_id,
    bsf.upload_id,
    df.document_type,
    df.building_name,
    df.address,
    df.uprn,
    bsf.building_safety_act_2022_mentioned,
    bsf.building_safety_act_compliance_status,
    bsf.part_4_duties_mentioned,
    bsf.building_safety_decisions_mentioned,
    bsf.building_safety_regulator_mentioned,
    bsf.building_safety_case_report_mentioned,
    (bsf.agentic_features_json->'building_safety_act_2022'->'part_4_duties_list')::jsonb AS part_4_duties_list,
    (bsf.agentic_features_json->'building_safety_act_2022'->'building_safety_decisions_list')::jsonb AS building_safety_decisions_list,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM silver.building_safety_features bsf
JOIN silver.document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.building_safety_act_2022_mentioned = TRUE;

-- 12) Mandatory Occurrence Reports (Category B - Compliance/workflow)
CREATE OR REPLACE VIEW gold.mandatory_occurrence_reports_v1 AS
SELECT
    bsf.feature_id,
    bsf.ha_id,
    bsf.upload_id,
    df.document_type,
    df.building_name,
    df.address,
    df.uprn,
    bsf.mandatory_occurrence_report_mentioned,
    bsf.mandatory_occurrence_reporting_process_mentioned,
    (bsf.agentic_features_json->'mandatory_occurrence_reports'->'mandatory_occurrence_reports')::jsonb AS mor_reports,
    (bsf.agentic_features_json->'mandatory_occurrence_reports'->'mandatory_occurrence_reporting_channels')::jsonb AS reporting_channels,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM silver.building_safety_features bsf
JOIN silver.document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.mandatory_occurrence_report_mentioned = TRUE;

-- 13) Building Safety Regulator interactions (Category B - Compliance/workflow)
CREATE OR REPLACE VIEW gold.bsr_interactions_v1 AS
SELECT
    bsf.feature_id,
    bsf.ha_id,
    bsf.upload_id,
    df.document_type,
    df.building_name,
    df.address,
    df.uprn,
    bsf.building_safety_regulator_mentioned,
    (bsf.agentic_features_json->'building_safety_regulator'->'bsr_interactions')::jsonb AS bsr_interactions,
    (bsf.agentic_features_json->'building_safety_regulator'->'bsr_submissions')::jsonb AS bsr_submissions,
    (bsf.agentic_features_json->'building_safety_regulator'->'bsr_complaint_appeals')::jsonb AS bsr_complaint_appeals,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM silver.building_safety_features bsf
JOIN silver.document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.building_safety_regulator_mentioned = TRUE;

-- 14) DocB/PlanB features summary (Category C)
CREATE OR REPLACE VIEW gold.docb_features_summary_v1 AS
SELECT
    dbf.docb_id,
    dbf.feature_id,
    dbf.ha_id,
    dbf.upload_id,
    df.document_type,
    df.building_name,
    df.address,
    df.uprn,
    df.postcode,
    dbf.cladding_type,
    dbf.ews_status,
    dbf.fire_risk_management_summary,
    dbf.docb_ref,
    dbf.fire_protection,
    dbf.alarms,
    dbf.evacuation_strategy,
    dbf.floors_above_ground,
    dbf.floors_below_ground,
    dbf.extraction_method,
    dbf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM silver.docb_features dbf
JOIN silver.document_features df ON df.feature_id = dbf.feature_id;

-- 15) Agentic extraction comparison summary (for monitoring)
CREATE OR REPLACE VIEW gold.agentic_extraction_comparison_v1 AS
SELECT
    df.feature_id,
    df.ha_id,
    df.upload_id,
    df.document_type,
    df.extraction_method,
    df.extraction_comparison_metadata,
    (df.extraction_comparison_metadata->>'agreement_score')::numeric AS agreement_score,
    (df.extraction_comparison_metadata->>'discrepancies_count')::integer AS discrepancies_count,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM silver.document_features df
LEFT JOIN silver.building_safety_features bsf ON bsf.feature_id = df.feature_id
WHERE df.extraction_method IN ('agentic', 'merged')
   OR df.extraction_comparison_metadata IS NOT NULL;

-- 16) Document features overview (new convenience view)
CREATE OR REPLACE VIEW gold.document_features_overview_v1 AS
SELECT
    df.feature_id,
    df.ha_id,
    df.upload_id,
    df.document_type,
    df.building_name,
    df.address,
    df.uprn,
    df.postcode,
    df.assessment_date,
    df.job_reference,
    df.client_name,
    df.assessor_company,
    df.extraction_method,
    df.extracted_at,
    df.processed_at,
    df.created_at,
    -- FRAEW specific
    ff.building_risk_rating AS fraew_risk_rating,
    ff.pas_9980_compliant,
    -- FRA specific
    fra.risk_rating AS fra_risk_rating,
    -- SCR specific
    scr.safety_case_status
FROM silver.document_features df
LEFT JOIN silver.fraew_features ff ON ff.feature_id = df.feature_id
LEFT JOIN silver.fra_features fra ON fra.feature_id = df.feature_id
LEFT JOIN silver.scr_features scr ON scr.feature_id = df.feature_id;

-- Add comments
COMMENT ON SCHEMA silver IS 'Silver layer: Cleaned, normalized entity and feature tables';
COMMENT ON VIEW gold.document_features_overview_v1 IS 'Overview of all document features with key fields from each document type';
