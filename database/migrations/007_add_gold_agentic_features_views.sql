-- Gold layer views for agentic building safety features
-- Migration: 007_add_gold_agentic_features_views.sql
--
-- Creates dashboard-ready views for ML/UI consumption of agentic features:
-- - High-rise building indicators
-- - Evacuation strategies
-- - Fire safety measures
-- - Structural integrity
-- - Maintenance requirements
-- - BSA compliance indicators
-- - MOR references
-- - BSR interactions

-- ---------------------------------------
-- 1) High-rise building indicators (Category A - ML+UI)
-- ---------------------------------------
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
FROM building_safety_features bsf
JOIN document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.high_rise_building_mentioned = TRUE
   OR bsf.building_height_category IN ('HIGH_RISE', 'MEDIUM_RISE');

-- ---------------------------------------
-- 2) Evacuation strategies (Category A - ML+UI)
-- ---------------------------------------
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
FROM building_safety_features bsf
JOIN document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.evacuation_strategy_mentioned = TRUE;

-- ---------------------------------------
-- 3) Fire safety measures summary (Category A - ML+UI)
-- ---------------------------------------
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
    -- Extract system counts from JSON if available
    (bsf.agentic_features_json->'fire_safety_measures'->'fire_safety_systems')::jsonb AS fire_safety_systems,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM building_safety_features bsf
JOIN document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.fire_safety_measures_mentioned = TRUE;

-- ---------------------------------------
-- 4) Structural integrity summary (Category A - ML+UI)
-- ---------------------------------------
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
    -- Extract detailed assessments/risks from JSON if available
    (bsf.agentic_features_json->'structural_integrity'->'structural_assessments')::jsonb AS structural_assessments,
    (bsf.agentic_features_json->'structural_integrity'->'structural_risks')::jsonb AS structural_risks,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM building_safety_features bsf
JOIN document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.structural_integrity_mentioned = TRUE
   OR bsf.structural_assessments_mentioned = TRUE
   OR bsf.structural_risks_mentioned = TRUE;

-- ---------------------------------------
-- 5) Maintenance requirements summary (Category A - ML+UI)
-- ---------------------------------------
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
    -- Extract detailed schedules/checks from JSON if available
    (bsf.agentic_features_json->'maintenance_requirements'->'maintenance_schedules')::jsonb AS maintenance_schedules,
    (bsf.agentic_features_json->'maintenance_requirements'->'maintenance_checks')::jsonb AS maintenance_checks,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM building_safety_features bsf
JOIN document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.maintenance_mentioned = TRUE
   OR bsf.maintenance_schedules_mentioned = TRUE
   OR bsf.tenancy_audits_mentioned = TRUE;

-- ---------------------------------------
-- 6) Building Safety Act 2022 compliance (Category B - Compliance/workflow)
-- ---------------------------------------
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
    -- Extract detailed Part 4 duties and decisions from JSON if available
    (bsf.agentic_features_json->'building_safety_act_2022'->'part_4_duties_list')::jsonb AS part_4_duties_list,
    (bsf.agentic_features_json->'building_safety_act_2022'->'building_safety_decisions_list')::jsonb AS building_safety_decisions_list,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM building_safety_features bsf
JOIN document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.building_safety_act_2022_mentioned = TRUE;

-- ---------------------------------------
-- 7) Mandatory Occurrence Reports (Category B - Compliance/workflow)
-- ---------------------------------------
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
    -- Extract detailed MORs from JSON if available
    (bsf.agentic_features_json->'mandatory_occurrence_reports'->'mandatory_occurrence_reports')::jsonb AS mor_reports,
    (bsf.agentic_features_json->'mandatory_occurrence_reports'->'mandatory_occurrence_reporting_channels')::jsonb AS reporting_channels,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM building_safety_features bsf
JOIN document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.mandatory_occurrence_report_mentioned = TRUE;

-- ---------------------------------------
-- 8) Building Safety Regulator interactions (Category B - Compliance/workflow)
-- ---------------------------------------
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
    -- Extract detailed BSR interactions from JSON if available
    (bsf.agentic_features_json->'building_safety_regulator'->'bsr_interactions')::jsonb AS bsr_interactions,
    (bsf.agentic_features_json->'building_safety_regulator'->'bsr_submissions')::jsonb AS bsr_submissions,
    (bsf.agentic_features_json->'building_safety_regulator'->'bsr_complaint_appeals')::jsonb AS bsr_complaint_appeals,
    bsf.extraction_method,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM building_safety_features bsf
JOIN document_features df ON df.feature_id = bsf.feature_id
WHERE bsf.building_safety_regulator_mentioned = TRUE;

-- ---------------------------------------
-- 9) DocB/PlanB features summary (Category C)
-- ---------------------------------------
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
FROM docb_features dbf
JOIN document_features df ON df.feature_id = dbf.feature_id;

-- ---------------------------------------
-- 10) Agentic extraction comparison summary (for monitoring)
-- ---------------------------------------
CREATE OR REPLACE VIEW gold.agentic_extraction_comparison_v1 AS
SELECT
    df.feature_id,
    df.ha_id,
    df.upload_id,
    df.document_type,
    df.extraction_method,
    df.extraction_comparison_metadata,
    -- Extract comparison metrics from metadata
    (df.extraction_comparison_metadata->>'agreement_score')::numeric AS agreement_score,
    (df.extraction_comparison_metadata->>'discrepancies_count')::integer AS discrepancies_count,
    bsf.agentic_confidence_score,
    df.assessment_date,
    df.processed_at
FROM document_features df
LEFT JOIN building_safety_features bsf ON bsf.feature_id = df.feature_id
WHERE df.extraction_method IN ('agentic', 'merged')
   OR df.extraction_comparison_metadata IS NOT NULL;
