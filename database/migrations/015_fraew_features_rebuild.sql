-- =============================================================
-- Migration: 015_fraew_features_rebuild.sql
--
-- Rebuilds silver.fraew_features from scratch with a complete
-- schema derived from real FRAEW documents (PAS 9980:2022).
--
-- Reference document: Elizabeth Court, Herne Bay (Buildtech, 2023)
-- Reference document: Scarfe Way, Colchester (Eurosafe UK, 2023)
--
-- Why DROP and recreate:
--   The existing table (15 cols) is missing block_id (cannot link
--   to blocks at all), rag_status, all assessor details, all
--   cladding material flags, and extraction_confidence.
--   It cannot be salvaged with ALTER TABLE — it needs a full rebuild.
--
-- What this migration creates:
--   1. silver.fraew_features          – full 50+ column schema
--   2. normalize_fraew_risk_rating()  – maps raw text → GREEN/AMBER/RED
--   3. trg_sync_block_fraew_status    – keeps blocks.fraew_status live
--   4. gold.fraew_block_detail_v1     – per-block FRAEW drill-down
--   5. gold.fraew_compliance_summary_v1 – portfolio compliance view
--   6. Updates gold.fra_block_detail_v1 – adds FRAEW score columns
--
-- Run AFTER migrations 001–014.
-- Safe to re-run (DROP IF EXISTS CASCADE on table).
-- =============================================================


-- =============================================================
-- 1.  DROP old incomplete table (CASCADE removes dependent views)
-- =============================================================
DROP TABLE IF EXISTS silver.fraew_features CASCADE;


-- =============================================================
-- 2.  silver.fraew_features
--
-- One row per FRAEW document processed.
-- Key difference from FRA: a single building can have multiple
-- external WALL TYPES each with its own risk assessment.
-- These are stored in wall_types JSONB array.
--
-- Schema derived from PAS 9980:2022 methodology:
--   Step 1: Does building require FRAEW?
--   Step 2: Gather information
--   Step 3: Identify risk factors
--   Step 4: Assess factor contributions
--   Step 5: Overall risk against benchmark
--   Step 6 (Clause 14): Fire engineering analysis if inconclusive
-- =============================================================
CREATE TABLE silver.fraew_features (

    fraew_id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ----------------------------------------------------------
    -- Links to parent tables
    -- ----------------------------------------------------------
    feature_id          UUID        REFERENCES silver.document_features(feature_id)
                                    ON DELETE SET NULL,
    block_id            UUID        REFERENCES silver.blocks(block_id)
                                    ON DELETE SET NULL,
    ha_id               VARCHAR(50) NOT NULL,
    upload_id           UUID,       -- links to upload_audit if available

    -- ----------------------------------------------------------
    -- Report metadata
    -- ----------------------------------------------------------
    report_reference    VARCHAR(100),   -- e.g. "JL/230504"
    assessment_date     DATE,           -- date of site investigation
    report_date         DATE,           -- date report was issued
    assessment_valid_until DATE,        -- typically 5 years from report_date
    is_in_date          BOOLEAN,        -- set by processor: report_date + 5yr >= today

    -- ----------------------------------------------------------
    -- Assessor details
    -- Two separate roles in PAS 9980: report writer + fire engineer
    -- Clause 14 invokes fire engineering analysis when inconclusive
    -- ----------------------------------------------------------
    assessor_name           VARCHAR(255),
    assessor_company        VARCHAR(255),
    assessor_qualification  VARCHAR(255),   -- e.g. "full member, Fire Protection Association"
    fire_engineer_name      VARCHAR(255),   -- populated when clause_14_applied = TRUE
    fire_engineer_company   VARCHAR(255),
    fire_engineer_qualification VARCHAR(255), -- e.g. "MSc, MIFireE, CFPA Eur Dip"
    clause_14_applied       BOOLEAN DEFAULT FALSE,
                                            -- TRUE = fire engineering analysis was invoked
                                            -- Elizabeth Court used this due to EPS complexity

    -- ----------------------------------------------------------
    -- Building physical description
    -- ----------------------------------------------------------
    building_height_m           DECIMAL(6, 2),  -- approximate height of top occupied floor
    building_height_category    VARCHAR(20)
                                CHECK (building_height_category IN (
                                    'under_11m',    -- below lower threshold
                                    '11_to_18m',    -- Fire Safety (England) Regs 2022 threshold
                                    '18_to_30m',    -- BSA 2022 higher-risk building band
                                    'over_30m',     -- highest risk band
                                    'unknown'
                                )),
    num_storeys                 INTEGER,
    num_units                   INTEGER,
    build_year                  INTEGER,
    construction_frame_type     VARCHAR(100),   -- e.g. "structural concrete", "steel frame"
    external_wall_base_construction VARCHAR(255), -- e.g. "double masonry cavity wall"
    retrofit_year               INTEGER,        -- year cladding/insulation was added

    -- ----------------------------------------------------------
    -- PAS 9980:2022 compliance
    -- ----------------------------------------------------------
    pas_9980_version        VARCHAR(20) DEFAULT '2022',
    pas_9980_compliant      BOOLEAN,    -- assessor's formal PAS 9980 compliance conclusion

    -- ----------------------------------------------------------
    -- Overall risk outcome
    --
    -- building_risk_rating: raw text from document
    --   PAS 9980 uses:     Low / Medium / High (3-band)
    --   Some assessors:    Tolerable / Moderate / Intolerable
    --   Elizabeth Court:   "Tolerable" (overall), "Low" (per wall type)
    --
    -- rag_status: normalised by normalize_fraew_risk_rating()
    --   GREEN  = Low / Tolerable
    --   AMBER  = Medium / Tolerable with concerns
    --   RED    = High / Intolerable
    -- ----------------------------------------------------------
    building_risk_rating    VARCHAR(100),   -- raw text: "Low", "Tolerable", "High", etc.
    rag_status              VARCHAR(10)
                            CHECK (rag_status IN ('RED', 'AMBER', 'GREEN')),

    -- ----------------------------------------------------------
    -- Interim and remedial measures
    -- ----------------------------------------------------------
    interim_measures_required   BOOLEAN DEFAULT FALSE,
    interim_measures_detail     TEXT,           -- description if required
    has_remedial_actions        BOOLEAN DEFAULT FALSE,
    remedial_actions            JSONB,
    -- Shape: [
    --   {
    --     "action": "Monitor render for damage",
    --     "priority": "advisory|low|medium|high",
    --     "due_date": "YYYY-MM-DD or null",
    --     "responsible": "landlord|contractor",
    --     "status": "outstanding|completed"
    --   }
    -- ]

    -- ----------------------------------------------------------
    -- Wall types — CORE FRAEW DATA
    --
    -- PAS 9980 assesses each distinct external wall construction
    -- separately. A building can have 2-5 different wall types.
    -- Elizabeth Court had: Wall Type 1 (EPS render, 80%),
    --                       Wall Type 2 (mineral wool render, 20%),
    --                       Balconies (separate assessment)
    --
    -- Shape: [
    --   {
    --     "type_ref": "Wall Type 1",
    --     "description": "Render to EPS insulation with masonry",
    --     "coverage_percent": 80,
    --     "insulation_type": "eps|mineral_wool|pir|phenolic|unknown",
    --     "insulation_combustible": true,
    --     "render_type": "cement|acrylic|silicone|unknown",
    --     "render_combustible": false,
    --     "spread_risk": "low|medium|high",
    --     "entry_risk": "low|medium|high",
    --     "occupant_risk": "low|medium|high",
    --     "overall_risk": "low|medium|high",
    --     "remedial_required": false,
    --     "remedial_detail": null
    --   }
    -- ]
    -- ----------------------------------------------------------
    wall_types              JSONB DEFAULT '[]'::JSONB,

    -- ----------------------------------------------------------
    -- Cladding and insulation material flags
    -- (denormalised from wall_types for fast dashboard queries)
    --
    -- These drive the "Combustible Cladding" risk flags that
    -- insurers care most about post-Grenfell.
    -- ----------------------------------------------------------
    has_combustible_cladding        BOOLEAN,    -- TRUE if ANY wall type has combustible material
    eps_insulation_present          BOOLEAN,    -- expanded polystyrene — combustible
    mineral_wool_insulation_present BOOLEAN,    -- non-combustible
    pir_insulation_present          BOOLEAN,    -- polyisocyanurate — combustible
    phenolic_insulation_present     BOOLEAN,    -- combustible
    acrylic_render_present          BOOLEAN,    -- combustible topcoat
    cement_render_present           BOOLEAN,    -- non-combustible
    aluminium_composite_cladding    BOOLEAN,    -- ACM — highest risk (Grenfell type)
    hpl_cladding_present            BOOLEAN,    -- high pressure laminate — combustible
    timber_cladding_present         BOOLEAN,    -- combustible

    -- ----------------------------------------------------------
    -- Fire safety features of the external wall system
    -- ----------------------------------------------------------
    cavity_barriers_present         BOOLEAN,    -- any cavity barriers present
    cavity_barriers_windows         BOOLEAN,    -- barriers at window/vent perimeters
                                                -- Elizabeth Court: FALSE — noted concern
    cavity_barriers_floors          BOOLEAN,    -- barriers at floor levels
    fire_breaks_floor_level         BOOLEAN,    -- fire breaks at compartment floors
    fire_breaks_party_walls         BOOLEAN,    -- fire breaks at party wall junctions
    dry_riser_present               BOOLEAN,
    wet_riser_present               BOOLEAN,
    evacuation_strategy             VARCHAR(50)
                                    CHECK (evacuation_strategy IN (
                                        'stay_put',
                                        'simultaneous',
                                        'phased',
                                        'temporary_evacuation',
                                        'unknown'
                                    )),

    -- ----------------------------------------------------------
    -- Compliance and testing flags
    -- These are the critical insurance underwriting signals
    -- ----------------------------------------------------------
    bs8414_test_evidence            BOOLEAN,
    -- Whether BS 8414-1 large-scale fire test evidence exists.
    -- Elizabeth Court: FALSE — fire engineer noted this as gap.
    -- A FALSE here on a building >18m with combustible insulation
    -- is a serious underwriting concern.

    br135_criteria_met              BOOLEAN,
    -- Whether BR 135 fire spread criteria have been demonstrated.
    -- Related to BS 8414 — usually FALSE if bs8414_test_evidence is FALSE.

    adb_compliant                   VARCHAR(20)
                                    CHECK (adb_compliant IN (
                                        'compliant',
                                        'non_compliant',
                                        'uncertain',
                                        'not_applicable'
                                    )),
    -- Approved Document B compliance.
    -- Elizabeth Court: 'uncertain' — ADB 2006 para 12.6 not satisfied
    -- but overall risk still deemed tolerable.

    -- ----------------------------------------------------------
    -- Recommended further actions (flags from remedial section)
    -- ----------------------------------------------------------
    height_survey_recommended           BOOLEAN DEFAULT FALSE,
    -- Elizabeth Court: TRUE — height ~18m, accurate survey needed
    -- to confirm Fire Safety (England) Regulations 2022 duties

    fire_door_survey_recommended        BOOLEAN DEFAULT FALSE,
    -- Elizabeth Court: TRUE — full fire door survey required

    intrusive_investigation_recommended BOOLEAN DEFAULT FALSE,
    -- Some buildings need destructive investigation to confirm
    -- what's behind the cladding

    asbestos_suspected                  BOOLEAN DEFAULT FALSE,
    -- Elizabeth Court: TRUE — board behind render possibly asbestos
    -- Assessor could not confirm wall build-up at floor junction

    -- ----------------------------------------------------------
    -- Extraction quality
    -- ----------------------------------------------------------
    extraction_confidence   DECIMAL(4, 3)
                            CHECK (extraction_confidence BETWEEN 0.0 AND 1.0),

    fraew_features_json     JSONB,  -- complete raw LLM output (audit trail)

    -- ----------------------------------------------------------
    -- Timestamps
    -- ----------------------------------------------------------
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_fraew_features_feature_id  ON silver.fraew_features(feature_id);
CREATE INDEX idx_fraew_features_block_id    ON silver.fraew_features(block_id);
CREATE INDEX idx_fraew_features_ha_id       ON silver.fraew_features(ha_id);
CREATE INDEX idx_fraew_features_rag_status  ON silver.fraew_features(rag_status);
CREATE INDEX idx_fraew_features_combustible ON silver.fraew_features(has_combustible_cladding)
    WHERE has_combustible_cladding = TRUE;
CREATE INDEX idx_fraew_features_bs8414      ON silver.fraew_features(bs8414_test_evidence)
    WHERE bs8414_test_evidence = FALSE;

COMMENT ON TABLE silver.fraew_features IS
    'Extracted features from Fire Risk Appraisal of External Walls (FRAEW) documents. '
    'One row per FRAEW document. Based on PAS 9980:2022 methodology. '
    'wall_types JSONB contains per-wall-type risk assessments. '
    'Combustible cladding flags are critical for insurance underwriting.';

COMMENT ON COLUMN silver.fraew_features.clause_14_applied IS
    'TRUE when fire engineering analysis (Clause 14 of PAS 9980) was invoked. '
    'This happens when Step 5 is inconclusive and a fire engineer reviews the assessment. '
    'Elizabeth Court used Clause 14 due to EPS insulation complexity.';

COMMENT ON COLUMN silver.fraew_features.bs8414_test_evidence IS
    'Whether large-scale BS 8414-1 fire test evidence exists for the wall system. '
    'FALSE on a building >18m with combustible insulation is a serious concern. '
    'ADB 2006 para 12.6 requires this for buildings over 18m.';

COMMENT ON COLUMN silver.fraew_features.wall_types IS
    'Array of wall type assessments per PAS 9980. Each element covers one distinct '
    'external wall construction with its insulation type, render type, and risk scores. '
    'Fields: type_ref, description, coverage_percent, insulation_type, '
    'insulation_combustible, render_type, render_combustible, spread_risk, '
    'entry_risk, occupant_risk, overall_risk, remedial_required, remedial_detail.';

COMMENT ON COLUMN silver.fraew_features.rag_status IS
    'Normalised risk band from building_risk_rating. '
    'GREEN: Low/Tolerable. AMBER: Medium/Tolerable with concerns. RED: High/Intolerable. '
    'Set by normalize_fraew_risk_rating() in silver processor.';


-- =============================================================
-- 3.  normalize_fraew_risk_rating(text) → VARCHAR(10)
--
-- FRAEW documents use a 3-band system (Low/Medium/High) per
-- PAS 9980:2022. This is different from FRA which uses
-- 5-band (Trivial/Tolerable/Moderate/Substantial/Intolerable).
--
-- FRAEW overall conclusions often use "Tolerable" rather than
-- "Low" — this maps to GREEN. The key distinction is:
--   - "Tolerable with no further action" → GREEN
--   - "Tolerable with concerns / recommendations" → AMBER
--     (the processor decides based on presence of recommendations)
--
-- NULL handling: same as FRA — "N/A"/"Unknown" → NULL
--
-- Mapping table:
--   RED    high, intolerable, unacceptable, extreme, critical
--   AMBER  medium, moderate, tolerable but, significant,
--          tolerable with recommendations, further action required
--   GREEN  low, tolerable (standalone), acceptable, no further action
--   NULL   n/a, not assessed, unknown, tbc, —
-- =============================================================
CREATE OR REPLACE FUNCTION silver.normalize_fraew_risk_rating(p_risk_rating TEXT)
RETURNS VARCHAR(10)
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_lower TEXT;
BEGIN
    -- Step 1: null / empty guard
    IF p_risk_rating IS NULL OR TRIM(p_risk_rating) = '' THEN
        RETURN NULL;
    END IF;

    v_lower := LOWER(TRIM(p_risk_rating));

    -- Step 2: explicit no-data patterns → NULL
    -- These mean the LLM could not extract a rating
    IF v_lower ~ '^(n/?a|not\s+assessed|not\s+applicable|not\s+available|unknown|not\s+stated|tbc|tbd|none|[-–—]+)$'
    THEN
        RETURN NULL;
    END IF;

    -- Step 3: multi-word phrases first (most specific)

    -- "no further action" / "no remedial action required" → GREEN
    IF v_lower ~ '\mno\s+(further|remedial)\s+action\M'
    THEN
        RETURN 'GREEN';
    END IF;

    -- "tolerable but" / "tolerable with" → AMBER
    -- (acceptable overall but with concerns noted)
    IF v_lower ~ '\mtolerable\M.{0,40}\m(but|with\s+recommendations|with\s+concerns|further\s+action)\M'
    THEN
        RETURN 'AMBER';
    END IF;

    -- "further action required" / "further assessment required" → AMBER
    IF v_lower ~ '\mfurther\s+(action|assessment|investigation)\M'
    THEN
        RETURN 'AMBER';
    END IF;

    -- "broadly acceptable" → GREEN
    IF v_lower ~ '\mbroadly\s+acceptable\M'
    THEN
        RETURN 'GREEN';
    END IF;

    -- "not acceptable" → RED
    IF v_lower ~ '\mnot\s+acceptable\M'
    THEN
        RETURN 'RED';
    END IF;

    -- Step 4: single-word patterns (PAS 9980 3-band)

    -- RED
    IF v_lower ~ '\m(high|intolerable|unacceptable|extreme|critical|severe)\M'
    THEN
        RETURN 'RED';
    END IF;

    -- AMBER
    IF v_lower ~ '\m(medium|moderate|significant)\M'
    THEN
        RETURN 'AMBER';
    END IF;

    -- GREEN
    -- "Low" and standalone "Tolerable" (without "but") both map to GREEN
    -- PAS 9980 Elizabeth Court conclusion was "Tolerable" → GREEN
    IF v_lower ~ '\m(low|tolerable|acceptable|negligible)\M'
    THEN
        RETURN 'GREEN';
    END IF;

    -- Step 5: conservative fallback
    -- Unknown text → AMBER (better to flag than to miss)
    RETURN 'AMBER';
END;
$$;

COMMENT ON FUNCTION silver.normalize_fraew_risk_rating(TEXT) IS
    'Maps FRAEW risk rating text to GREEN/AMBER/RED (or NULL if no data). '
    'PAS 9980:2022 uses 3-band: Low/Medium/High. '
    'Also handles: Tolerable (GREEN), Tolerable but (AMBER), Intolerable (RED). '
    'Returns NULL for N/A/Unknown inputs. Returns AMBER as conservative fallback.';


-- =============================================================
-- 4.  Trigger: keep silver.blocks.fraew_status in sync
--
-- After every INSERT or UPDATE on silver.fraew_features,
-- update the corresponding block row's fraew_status column
-- so gold views can read it without an extra join.
--
-- Same pattern as trg_sync_block_fra_status (migration 013).
-- =============================================================
CREATE OR REPLACE FUNCTION silver.fn_sync_block_fraew_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_latest_rag VARCHAR(10);
BEGIN
    -- Find the most recent FRAEW for this block
    SELECT ff.rag_status INTO v_latest_rag
    FROM silver.fraew_features ff
    JOIN silver.document_features df ON df.feature_id = ff.feature_id
    WHERE ff.block_id = NEW.block_id
    ORDER BY df.assessment_date DESC NULLS LAST,
             ff.created_at DESC
    LIMIT 1;

    -- Update the block row
    IF NEW.block_id IS NOT NULL THEN
        UPDATE silver.blocks
        SET fraew_status = v_latest_rag,
            updated_at   = NOW()
        WHERE block_id = NEW.block_id;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_block_fraew_status ON silver.fraew_features;

CREATE TRIGGER trg_sync_block_fraew_status
    AFTER INSERT OR UPDATE
    ON silver.fraew_features
    FOR EACH ROW
    EXECUTE FUNCTION silver.fn_sync_block_fraew_status();

COMMENT ON TRIGGER trg_sync_block_fraew_status ON silver.fraew_features IS
    'After every INSERT or UPDATE on fraew_features, writes the most recent '
    'rag_status to silver.blocks.fraew_status for fast gold view queries.';


-- =============================================================
-- 5.  gold.fraew_block_detail_v1
--
-- Per-block FRAEW view. One row per block showing the most
-- recent FRAEW document with all cladding, compliance, and
-- risk fields exposed for the dashboard.
-- =============================================================
CREATE OR REPLACE VIEW gold.fraew_block_detail_v1 AS
SELECT
    b.block_id,
    b.ha_id,
    b.portfolio_id,
    b.name                              AS block_name,
    b.height_category,
    b.total_units,

    -- FRAEW status (denormalised from latest FRAEW trigger)
    b.fraew_status,

    -- Latest FRAEW document fields
    fraew.fraew_id,
    fraew.report_reference,
    fraew.assessment_date,
    fraew.report_date,
    fraew.assessment_valid_until,
    fraew.is_in_date,
    fraew.assessor_name,
    fraew.assessor_company,
    fraew.fire_engineer_name,
    fraew.fire_engineer_company,
    fraew.clause_14_applied,

    -- Building description
    fraew.building_height_m,
    fraew.building_height_category,
    fraew.num_storeys,
    fraew.num_units                     AS fraew_units,
    fraew.build_year,
    fraew.construction_frame_type,
    fraew.retrofit_year,

    -- Risk outcome
    fraew.building_risk_rating          AS fraew_raw_risk_rating,
    fraew.rag_status                    AS fraew_rag_status,
    fraew.pas_9980_compliant,
    fraew.pas_9980_version,

    -- Interim and remedial
    fraew.interim_measures_required,
    fraew.interim_measures_detail,
    fraew.has_remedial_actions,

    -- Wall types (full JSONB for drill-down)
    fraew.wall_types,

    -- Cladding material flags (key underwriting signals)
    fraew.has_combustible_cladding,
    fraew.eps_insulation_present,
    fraew.mineral_wool_insulation_present,
    fraew.pir_insulation_present,
    fraew.acrylic_render_present,
    fraew.cement_render_present,
    fraew.aluminium_composite_cladding,
    fraew.hpl_cladding_present,
    fraew.timber_cladding_present,

    -- Fire safety features
    fraew.cavity_barriers_present,
    fraew.cavity_barriers_windows,
    fraew.fire_breaks_floor_level,
    fraew.fire_breaks_party_walls,
    fraew.dry_riser_present,
    fraew.evacuation_strategy,

    -- Compliance flags (critical for insurers)
    fraew.bs8414_test_evidence,
    fraew.br135_criteria_met,
    fraew.adb_compliant,

    -- Recommended actions
    fraew.height_survey_recommended,
    fraew.fire_door_survey_recommended,
    fraew.intrusive_investigation_recommended,
    fraew.asbestos_suspected,

    fraew.extraction_confidence,
    b.updated_at                        AS block_updated_at

FROM silver.blocks b

LEFT JOIN LATERAL (
    SELECT ff.*
    FROM silver.fraew_features ff
    JOIN silver.document_features df
        ON df.feature_id = ff.feature_id
       AND df.block_id   = b.block_id
    ORDER BY df.assessment_date DESC NULLS LAST,
             ff.created_at DESC
    LIMIT 1
) fraew ON TRUE;

COMMENT ON VIEW gold.fraew_block_detail_v1 IS
    'Per-block FRAEW detail view. One row per block with latest FRAEW document fields. '
    'Covers PAS 9980:2022 compliance, cladding materials, wall types, '
    'cavity barriers, and BS 8414 test evidence.';


-- =============================================================
-- 6.  gold.fraew_compliance_summary_v1
--
-- Portfolio-level FRAEW compliance overview.
-- Powers the Safety & Compliance section of the dashboard.
-- =============================================================
CREATE OR REPLACE VIEW gold.fraew_compliance_summary_v1 AS
SELECT
    b.ha_id,
    b.portfolio_id,

    -- Coverage
    COUNT(DISTINCT b.block_id)                  AS total_blocks,
    COUNT(DISTINCT fraew.fraew_id)              AS blocks_with_fraew,
    COUNT(DISTINCT b.block_id)
        - COUNT(DISTINCT fraew.fraew_id)         AS blocks_missing_fraew,

    -- RAG distribution
    COUNT(DISTINCT b.block_id)
        FILTER (WHERE b.fraew_status = 'RED')    AS fraew_red_count,
    COUNT(DISTINCT b.block_id)
        FILTER (WHERE b.fraew_status = 'AMBER')  AS fraew_amber_count,
    COUNT(DISTINCT b.block_id)
        FILTER (WHERE b.fraew_status = 'GREEN')  AS fraew_green_count,

    -- In-date
    COUNT(DISTINCT fraew.fraew_id)
        FILTER (WHERE fraew.is_in_date = TRUE)   AS fraew_in_date_count,
    COUNT(DISTINCT fraew.fraew_id)
        FILTER (WHERE fraew.is_in_date = FALSE)  AS fraew_out_of_date_count,

    -- Combustible cladding (major risk signal)
    COUNT(DISTINCT fraew.fraew_id)
        FILTER (WHERE fraew.has_combustible_cladding = TRUE)
                                                 AS blocks_combustible_cladding,
    COUNT(DISTINCT fraew.fraew_id)
        FILTER (WHERE fraew.aluminium_composite_cladding = TRUE)
                                                 AS blocks_acm_cladding,
    COUNT(DISTINCT fraew.fraew_id)
        FILTER (WHERE fraew.eps_insulation_present = TRUE)
                                                 AS blocks_eps_insulation,

    -- BS 8414 compliance gaps
    COUNT(DISTINCT fraew.fraew_id)
        FILTER (WHERE fraew.bs8414_test_evidence = FALSE
                  AND fraew.has_combustible_cladding = TRUE)
                                                 AS blocks_no_bs8414_combustible,

    -- Clause 14 usage
    COUNT(DISTINCT fraew.fraew_id)
        FILTER (WHERE fraew.clause_14_applied = TRUE)
                                                 AS blocks_clause_14_used,

    -- Further action flags
    COUNT(DISTINCT fraew.fraew_id)
        FILTER (WHERE fraew.height_survey_recommended = TRUE)
                                                 AS blocks_height_survey_needed,
    COUNT(DISTINCT fraew.fraew_id)
        FILTER (WHERE fraew.intrusive_investigation_recommended = TRUE)
                                                 AS blocks_intrusive_needed,
    COUNT(DISTINCT fraew.fraew_id)
        FILTER (WHERE fraew.asbestos_suspected = TRUE)
                                                 AS blocks_asbestos_suspected

FROM silver.blocks b
LEFT JOIN LATERAL (
    SELECT ff.*
    FROM silver.fraew_features ff
    JOIN silver.document_features df
        ON df.feature_id = ff.feature_id
       AND df.block_id   = b.block_id
    ORDER BY df.assessment_date DESC NULLS LAST
    LIMIT 1
) fraew ON TRUE
GROUP BY b.ha_id, b.portfolio_id;

COMMENT ON VIEW gold.fraew_compliance_summary_v1 IS
    'Portfolio-level FRAEW compliance summary. '
    'Covers RAG distribution, combustible cladding exposure, '
    'BS 8414 gaps, and further investigation requirements.';


-- =============================================================
-- 7.  Rebuild gold.fra_block_detail_v1
--
-- The migration 014 version references fraew columns by name.
-- Now that fraew_features has been rebuilt with a new schema,
-- the view needs to reference the new column names.
-- DROP and recreate to apply changes cleanly.
-- =============================================================
DROP VIEW IF EXISTS gold.fra_block_detail_v1 CASCADE;

CREATE VIEW gold.fra_block_detail_v1 AS
SELECT
    b.block_id,
    b.ha_id,
    b.portfolio_id,
    b.name                              AS block_name,
    b.height_category,
    b.total_units,

    -- RAG status (from triggers)
    b.fra_status,
    b.fraew_status,

    -- FRA Risk score (from migration 014)
    rs.fra_risk_score,
    rs.risk_band,
    rs.score_breakdown,

    -- Latest FRA
    fra.fra_id,
    fra.fra_assessment_type,
    fra.risk_rating                     AS fra_raw_risk_rating,
    fra.rag_status                      AS fra_rag_status,
    fra.assessment_date                 AS fra_assessment_date,
    fra.assessment_valid_until,
    fra.is_in_date                      AS fra_is_in_date,
    fra.assessor_name,
    fra.assessor_company,
    fra.evacuation_strategy,
    fra.evacuation_strategy_changed,
    COALESCE(fra.total_action_count, 0)         AS total_action_count,
    COALESCE(fra.overdue_action_count, 0)        AS overdue_action_count,
    COALESCE(fra.no_date_action_count, 0)        AS no_date_action_count,
    COALESCE(fra.outstanding_action_count, 0)    AS outstanding_action_count,
    COALESCE(fra.high_priority_action_count, 0)  AS high_priority_action_count,
    fra.bsa_2022_applicable,
    fra.mandatory_occurrence_noted,
    fra.has_smoke_detection,
    fra.has_fire_doors,
    fra.has_compartmentation,
    fra.has_emergency_lighting,
    fra.extraction_confidence           AS fra_extraction_confidence,

    -- Latest FRAEW (from rebuilt table)
    fraew.fraew_id,
    fraew.building_risk_rating          AS fraew_raw_risk_rating,
    fraew.rag_status                    AS fraew_rag_status,
    fraew.pas_9980_compliant,
    fraew.has_remedial_actions,
    fraew.has_combustible_cladding,
    fraew.eps_insulation_present,
    fraew.aluminium_composite_cladding,
    fraew.bs8414_test_evidence,
    fraew.clause_14_applied,
    fraew.assessment_date               AS fraew_assessment_date,
    fraew.is_in_date                    AS fraew_is_in_date,
    fraew.extraction_confidence         AS fraew_extraction_confidence,

    b.updated_at                        AS block_updated_at

FROM silver.blocks b

LEFT JOIN LATERAL (
    SELECT fra2.*
    FROM silver.fra_features fra2
    JOIN silver.document_features df
        ON df.feature_id = fra2.feature_id
       AND df.block_id   = b.block_id
    ORDER BY df.assessment_date DESC NULLS LAST
    LIMIT 1
) fra ON TRUE

LEFT JOIN silver.fra_risk_scores rs
    ON rs.fra_id = fra.fra_id

LEFT JOIN LATERAL (
    SELECT ff.*
    FROM silver.fraew_features ff
    JOIN silver.document_features df
        ON df.feature_id = ff.feature_id
       AND df.block_id   = b.block_id
    ORDER BY df.assessment_date DESC NULLS LAST
    LIMIT 1
) fraew ON TRUE;

COMMENT ON VIEW gold.fra_block_detail_v1 IS
    'Per-block combined FRA + FRAEW view (migrations 013 + 014 + 015). '
    'Joins fra_features, fra_risk_scores, and fraew_features. '
    'Use for the Safety & Compliance block table.';


-- =============================================================
-- Self-test assertions
-- =============================================================
DO $$
BEGIN
    -- FRAEW normalize function tests
    -- PAS 9980 3-band
    ASSERT silver.normalize_fraew_risk_rating('Low')         = 'GREEN', 'Low → GREEN';
    ASSERT silver.normalize_fraew_risk_rating('Medium')      = 'AMBER', 'Medium → AMBER';
    ASSERT silver.normalize_fraew_risk_rating('High')        = 'RED',   'High → RED';

    -- Elizabeth Court scenarios
    ASSERT silver.normalize_fraew_risk_rating('Tolerable')   = 'GREEN', 'Tolerable → GREEN';
    ASSERT silver.normalize_fraew_risk_rating('tolerable')   = 'GREEN', 'tolerable (lower) → GREEN';
    ASSERT silver.normalize_fraew_risk_rating('Intolerable') = 'RED',   'Intolerable → RED';
    ASSERT silver.normalize_fraew_risk_rating('Tolerable but further action required') = 'AMBER',
        'Tolerable but → AMBER';

    -- In-sentence usage
    ASSERT silver.normalize_fraew_risk_rating('overall risk is Low') = 'GREEN',
        'in-sentence Low → GREEN';
    ASSERT silver.normalize_fraew_risk_rating('No further action required') = 'GREEN',
        'No further action → GREEN';
    ASSERT silver.normalize_fraew_risk_rating('Further assessment required') = 'AMBER',
        'Further assessment → AMBER';

    -- NULL cases
    ASSERT silver.normalize_fraew_risk_rating(NULL)          IS NULL, 'NULL → NULL';
    ASSERT silver.normalize_fraew_risk_rating('N/A')         IS NULL, 'N/A → NULL';
    ASSERT silver.normalize_fraew_risk_rating('Unknown')     IS NULL, 'Unknown → NULL';
    ASSERT silver.normalize_fraew_risk_rating('')            IS NULL, 'empty → NULL';

    RAISE NOTICE 'Migration 015: all normalize_fraew_risk_rating() assertions passed.';
END;
$$;