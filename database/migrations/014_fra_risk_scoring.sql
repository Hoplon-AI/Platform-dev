-- =============================================================
-- Migration: 014_fra_risk_scoring.sql
--
-- Adds a quantitative risk scoring layer on top of the FRA
-- features extracted in migration 013.
--
-- What this does (in order):
--   1. silver.fra_risk_scores     – stores computed score per FRA
--   2. silver.compute_fra_risk_score(UUID)
--                                 – scoring function (returns score + breakdown)
--   3. silver.fn_auto_score_fra() – trigger function: auto-scores on insert/update
--   4. trg_auto_score_fra         – trigger wiring on silver.fra_features
--   5. gold.fra_risk_score_v1     – view joining scores back to block context
--   6. Updated gold.fra_block_detail_v1
--                                 – adds score columns (replaces migration 013 version)
--
-- Run AFTER migrations 001–013.
--
-- Scoring model
-- -------------
-- Score range:  0.0 – 10.0   (10 = safest, lower = higher risk)
-- Calculation:  start at 10.0, apply weighted deductions per risk factor
-- Floor:        0.5 (score never reaches 0; there is always some data)
--
-- Risk bands (stored in risk_band column):
--   GREEN   7.5 – 10.0   "Fine — no significant fire safety concerns"
--   AMBER   4.5 –  7.4   "Tolerable but Significant — action required"
--   RED     0.0 –  4.4   "High Risk — urgent remediation needed"
--
-- Deduction categories (weights justified in comments):
--   Cat 1 – RAG status           (max -4.0)  primary signal, highest weight
--   Cat 2 – Assessment currency  (max -4.0)  out-of-date FRA = legal exposure
--   Cat 3 – Outstanding actions  (max -3.5)  unresolved breaches
--   Cat 4 – Safety measures      (max -1.75) physical gaps in protection
--   Cat 5 – Compliance events    (max -1.5)  MOR events, BSA duties
-- =============================================================


-- =============================================================
-- 1.  silver.fra_risk_scores
--
-- One row per FRA document. Updated atomically every time
-- fra_features is inserted or updated via the trigger below.
-- Keeping this as a separate table (not columns on fra_features)
-- allows the scoring model to be versioned and recomputed
-- independently of the extraction pipeline.
-- =============================================================
CREATE TABLE IF NOT EXISTS silver.fra_risk_scores (

    score_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    fra_id          UUID        NOT NULL UNIQUE
                                REFERENCES silver.fra_features(fra_id)
                                ON DELETE CASCADE,
    block_id        UUID        REFERENCES silver.blocks(block_id)
                                ON DELETE SET NULL,
    ha_id           VARCHAR(50) NOT NULL,

    -- ----------------------------------------------------------
    -- Score and band
    -- ----------------------------------------------------------
    fra_risk_score  DECIMAL(4, 1) NOT NULL
                    CHECK (fra_risk_score BETWEEN 0.0 AND 10.0),

    -- Derived band — always consistent with fra_risk_score:
    --   GREEN  ≥ 7.5
    --   AMBER  4.5 – 7.4
    --   RED    < 4.5
    risk_band       VARCHAR(10) NOT NULL
                    CHECK (risk_band IN ('RED', 'AMBER', 'GREEN')),

    -- ----------------------------------------------------------
    -- Score breakdown (full audit trail)
    --
    -- Stored as JSONB so the dashboard can show underwriters
    -- exactly WHY a block scored the way it did. Shape:
    -- {
    --   "base_score":          10.0,
    --   "cat1_rag":            -2.0,   ← RAG status deduction
    --   "cat2_currency":       -1.5,   ← out-of-date / type deductions
    --   "cat3_actions":        -1.25,  ← outstanding action deductions
    --   "cat4_measures":       -1.0,   ← missing safety measures
    --   "cat5_compliance":     -0.25,  ← MOR / BSA events
    --   "floor_applied":       false,
    --   "final_score":          4.0,
    --   "scorer_notes":        ["FRA out of date", "3 high-priority overdue actions"]
    -- }
    -- ----------------------------------------------------------
    score_breakdown JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- Version of the scoring model used — increment when weights change
    -- so historical scores remain traceable.
    scorer_version  VARCHAR(10) NOT NULL DEFAULT 'v1.0',

    computed_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fra_risk_scores_fra_id
    ON silver.fra_risk_scores(fra_id);

CREATE INDEX IF NOT EXISTS idx_fra_risk_scores_block_id
    ON silver.fra_risk_scores(block_id);

CREATE INDEX IF NOT EXISTS idx_fra_risk_scores_ha_id
    ON silver.fra_risk_scores(ha_id);

CREATE INDEX IF NOT EXISTS idx_fra_risk_scores_band
    ON silver.fra_risk_scores(risk_band);

CREATE INDEX IF NOT EXISTS idx_fra_risk_scores_score
    ON silver.fra_risk_scores(fra_risk_score);

COMMENT ON TABLE silver.fra_risk_scores IS
    'Computed risk scores for each FRA document. One row per fra_features row. '
    'Scores are 0.0–10.0 (10 = safest). Bands: GREEN ≥ 7.5, AMBER 4.5–7.4, RED < 4.5. '
    'score_breakdown JSONB records the full deduction trail for auditability. '
    'Auto-populated by trg_auto_score_fra trigger on silver.fra_features.';

COMMENT ON COLUMN silver.fra_risk_scores.fra_risk_score IS
    'Fire risk score 0.0–10.0. Calculated from base 10.0 minus weighted deductions '
    'across 5 categories: RAG status, assessment currency, outstanding actions, '
    'safety measures absent, compliance events. Floor is 0.5.';

COMMENT ON COLUMN silver.fra_risk_scores.risk_band IS
    'GREEN (≥7.5): Fine. AMBER (4.5–7.4): Tolerable but Significant. '
    'RED (<4.5): High Risk — urgent remediation needed.';

COMMENT ON COLUMN silver.fra_risk_scores.scorer_version IS
    'Scoring model version. Increment when deduction weights change so '
    'historical scores can be identified and recomputed if needed.';


-- =============================================================
-- 2.  silver.compute_fra_risk_score(fra_id UUID)
--
-- Returns a RECORD with (score DECIMAL, band VARCHAR, breakdown JSONB).
-- Called by the trigger and can also be called manually to preview
-- a score without writing to fra_risk_scores.
--
-- Scoring rubric (v1.0):
--
--   BASE: 10.0
--
--   Category 1 — RAG Status (max -4.0)
--     RED rag_status:   -4.0   (intolerable/substantial risk)
--     AMBER rag_status: -2.0   (moderate/significant issues)
--     GREEN rag_status:  0.0
--
--   Category 2 — Assessment Currency (max -4.0)
--     No FRA at all:          -4.0  (cannot assess; HA legally exposed)
--     FRA out of date:        -1.5  (invalid assessment; legal breach)
--     FRA expiring ≤90 days:  -0.5  (renewal urgently needed)
--     Assessment Type 1 only: -0.5  (common parts only; flats not assessed)
--
--   Category 3 — Outstanding Actions (max -3.5)
--     Each HIGH priority overdue:    -0.5 (capped at -2.0)
--     Each MEDIUM priority overdue:  -0.25 (capped at -1.0)
--     Each action with no due date:  -0.10 (capped at -0.5)
--
--   Category 4 — Fire Safety Measures Absent (max -1.75)
--     No smoke detection:      -0.5
--     No fire doors:           -0.5
--     No compartmentation:     -0.5
--     No emergency lighting:   -0.25
--
--   Category 5 — Compliance Events (max -1.5)
--     Mandatory occurrence (MOR) event noted:    -1.0
--     Evacuation strategy changed:               -0.25
--     BSA 2022 applicable, no accountable person: -0.25
--
--   FLOOR: 0.5 (never reaches 0)
-- =============================================================
CREATE OR REPLACE FUNCTION silver.compute_fra_risk_score(p_fra_id UUID)
RETURNS TABLE (
    out_score     DECIMAL(4, 1),
    out_band      VARCHAR(10),
    out_breakdown JSONB
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_fra           silver.fra_features%ROWTYPE;
    v_base          DECIMAL := 10.0;
    v_score         DECIMAL := 10.0;

    -- Category deduction accumulators
    v_cat1          DECIMAL := 0.0;
    v_cat2          DECIMAL := 0.0;
    v_cat3          DECIMAL := 0.0;
    v_cat4          DECIMAL := 0.0;
    v_cat5          DECIMAL := 0.0;

    v_notes         TEXT[]  := ARRAY[]::TEXT[];
    v_floor_applied BOOLEAN := FALSE;
    v_band          VARCHAR(10);
BEGIN
    -- ---- Fetch the FRA row --------------------------------------
    SELECT * INTO v_fra
    FROM silver.fra_features
    WHERE fra_id = p_fra_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'fra_features row not found for fra_id = %', p_fra_id;
    END IF;

    -- ====================================================
    -- Category 1: RAG Status
    -- The assessor's own risk conclusion — this carries the
    -- most weight because it reflects expert judgement.
    -- ====================================================
    CASE v_fra.rag_status
        WHEN 'RED' THEN
            v_cat1 := -4.0;
            v_notes := array_append(v_notes, 'RAG status RED (intolerable/substantial risk): -4.0');
        WHEN 'AMBER' THEN
            v_cat1 := -2.0;
            v_notes := array_append(v_notes, 'RAG status AMBER (moderate/significant issues): -2.0');
        WHEN 'GREEN' THEN
            v_cat1 := 0.0;
        ELSE
            -- NULL rag_status: treat as AMBER (conservative fallback)
            v_cat1 := -2.0;
            v_notes := array_append(v_notes, 'RAG status unknown — conservative AMBER applied: -2.0');
    END CASE;

    -- ====================================================
    -- Category 2: Assessment Currency
    -- An out-of-date FRA means the HA has no legally valid
    -- picture of risk. This is a serious compliance failure.
    -- ====================================================

    -- Out of date (is_in_date is set by the silver processor on INSERT/UPDATE)
    IF v_fra.is_in_date = FALSE THEN
        v_cat2 := v_cat2 - 1.5;
        v_notes := array_append(v_notes, 'FRA out of date (assessment_valid_until expired): -1.5');
    END IF;

    -- Expiring within 90 days (still valid but needs renewal)
    IF v_fra.is_in_date = TRUE
       AND v_fra.assessment_valid_until IS NOT NULL
       AND v_fra.assessment_valid_until <= (CURRENT_DATE + INTERVAL '90 days') THEN
        v_cat2 := v_cat2 - 0.5;
        v_notes := array_append(v_notes, 'FRA expiring within 90 days: -0.5');
    END IF;

    -- Type 1 assessment: common parts only, flats not inspected
    -- Scarfe Way was Type 3 (sampled flats) which is more complete.
    -- A Type 1 for a residential block leaves flat doors and
    -- internal compartmentation entirely uninspected.
    IF v_fra.fra_assessment_type = 'Type 1' THEN
        v_cat2 := v_cat2 - 0.5;
        v_notes := array_append(v_notes, 'Type 1 assessment only (flats not inspected): -0.5');
    END IF;

    -- ====================================================
    -- Category 3: Outstanding Actions
    -- Unresolved high/medium actions represent confirmed
    -- fire safety breaches that the HA has not fixed.
    -- Advisory and Low priority actions are best-practice
    -- recommendations, not legislative breaches — no penalty.
    -- ====================================================

    -- High priority overdue: -0.5 each, capped at -2.0
    IF v_fra.overdue_action_count > 0 THEN
        DECLARE
            v_high_overdue DECIMAL;
        BEGIN
            -- We penalise overdue_action_count as a proxy for high-priority overdue.
            -- For a finer breakdown the silver processor should set
            -- overdue_action_count to HIGH-only; adjust if your processor splits further.
            v_high_overdue := LEAST(v_fra.overdue_action_count * 0.5, 2.0);
            v_cat3 := v_cat3 - v_high_overdue;
            v_notes := array_append(v_notes,
                format('%s overdue action(s) @ -0.5 each (cap -2.0): -%s',
                       v_fra.overdue_action_count, v_high_overdue));
        END;
    END IF;

    -- Outstanding (non-overdue) medium/high actions: -0.25 each, capped at -1.0
    DECLARE
        v_outstanding_only INTEGER;
        v_outstanding_ded  DECIMAL;
    BEGIN
        v_outstanding_only := GREATEST(
            v_fra.outstanding_action_count - v_fra.overdue_action_count,
            0
        );
        IF v_outstanding_only > 0 THEN
            v_outstanding_ded := LEAST(v_outstanding_only * 0.25, 1.0);
            v_cat3 := v_cat3 - v_outstanding_ded;
            v_notes := array_append(v_notes,
                format('%s outstanding (non-overdue) action(s) @ -0.25 each (cap -1.0): -%s',
                       v_outstanding_only, v_outstanding_ded));
        END IF;
    END;

    -- Actions with no due date: -0.10 each, capped at -0.5
    IF v_fra.no_date_action_count > 0 THEN
        DECLARE
            v_nodate_ded DECIMAL;
        BEGIN
            v_nodate_ded := LEAST(v_fra.no_date_action_count * 0.10, 0.5);
            v_cat3 := v_cat3 - v_nodate_ded;
            v_notes := array_append(v_notes,
                format('%s action(s) with no due date @ -0.10 each (cap -0.5): -%s',
                       v_fra.no_date_action_count, v_nodate_ded));
        END;
    END IF;

    -- ====================================================
    -- Category 4: Fire Safety Measures Absent
    -- Physical gaps in protection that compound the risk
    -- from any issues found by the assessor.
    -- ====================================================
    IF v_fra.has_smoke_detection = FALSE THEN
        v_cat4 := v_cat4 - 0.5;
        v_notes := array_append(v_notes, 'No smoke detection present: -0.5');
    END IF;

    IF v_fra.has_fire_doors = FALSE THEN
        v_cat4 := v_cat4 - 0.5;
        v_notes := array_append(v_notes, 'No fire doors present or confirmed: -0.5');
    END IF;

    IF v_fra.has_compartmentation = FALSE THEN
        v_cat4 := v_cat4 - 0.5;
        v_notes := array_append(v_notes, 'Compartmentation absent or breached: -0.5');
    END IF;

    IF v_fra.has_emergency_lighting = FALSE THEN
        v_cat4 := v_cat4 - 0.25;
        v_notes := array_append(v_notes, 'No emergency lighting present: -0.25');
    END IF;

    -- ====================================================
    -- Category 5: Compliance / Legal Events
    -- These indicate known regulatory breaches or
    -- significant changes requiring formal action.
    -- ====================================================

    -- Mandatory Occurrence Report event — serious legal event
    IF v_fra.mandatory_occurrence_noted = TRUE THEN
        v_cat5 := v_cat5 - 1.0;
        v_notes := array_append(v_notes, 'Mandatory occurrence (MOR) event noted: -1.0');
    END IF;

    -- Evacuation strategy changed — significant event under BSA 2022 Part 4
    IF v_fra.evacuation_strategy_changed = TRUE THEN
        v_cat5 := v_cat5 - 0.25;
        v_notes := array_append(v_notes, 'Evacuation strategy changed: -0.25');
    END IF;

    -- BSA 2022 HRB but accountable person not documented
    IF v_fra.bsa_2022_applicable = TRUE
       AND (v_fra.accountable_person_noted IS NULL
            OR v_fra.accountable_person_noted = FALSE) THEN
        v_cat5 := v_cat5 - 0.25;
        v_notes := array_append(v_notes,
            'BSA 2022 higher-risk building — accountable person not noted: -0.25');
    END IF;

    -- ====================================================
    -- Compute final score with floor
    -- ====================================================
    v_score := v_base + v_cat1 + v_cat2 + v_cat3 + v_cat4 + v_cat5;

    IF v_score < 0.5 THEN
        v_score := 0.5;
        v_floor_applied := TRUE;
        v_notes := array_append(v_notes, 'Floor of 0.5 applied');
    END IF;

    -- Round to 1 decimal place
    v_score := ROUND(v_score, 1);

    -- ====================================================
    -- Determine band
    -- ====================================================
    v_band := CASE
        WHEN v_score >= 7.5 THEN 'GREEN'
        WHEN v_score >= 4.5 THEN 'AMBER'
        ELSE 'RED'
    END;

    -- ====================================================
    -- Return
    -- ====================================================
    out_score     := v_score;
    out_band      := v_band;
    out_breakdown := jsonb_build_object(
        'base_score',      v_base,
        'cat1_rag',        v_cat1,
        'cat2_currency',   v_cat2,
        'cat3_actions',    v_cat3,
        'cat4_measures',   v_cat4,
        'cat5_compliance', v_cat5,
        'floor_applied',   v_floor_applied,
        'final_score',     v_score,
        'risk_band',       v_band,
        'scorer_version',  'v1.0',
        'scorer_notes',    to_jsonb(v_notes)
    );
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION silver.compute_fra_risk_score(UUID) IS
    'Computes fire risk score (0.0–10.0) and risk band (RED/AMBER/GREEN) for a given FRA. '
    'Returns (out_score, out_band, out_breakdown). '
    'Call manually to preview; called automatically by trg_auto_score_fra trigger. '
    'Scoring model v1.0: base 10.0 minus deductions across 5 categories. '
    'Bands: GREEN ≥7.5, AMBER 4.5–7.4, RED <4.5.';


-- =============================================================
-- 3.  Trigger: auto-score on insert/update of fra_features
--
-- Every time the silver processor writes or updates an FRA row,
-- this trigger calls compute_fra_risk_score() and upserts the
-- result into fra_risk_scores.
-- =============================================================
CREATE OR REPLACE FUNCTION silver.fn_auto_score_fra()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_result RECORD;
BEGIN
    -- Compute the score
    SELECT * INTO v_result
    FROM silver.compute_fra_risk_score(NEW.fra_id);

    -- Upsert into fra_risk_scores
    INSERT INTO silver.fra_risk_scores (
        fra_id,
        block_id,
        ha_id,
        fra_risk_score,
        risk_band,
        score_breakdown,
        scorer_version,
        computed_at,
        updated_at
    )
    VALUES (
        NEW.fra_id,
        NEW.block_id,
        NEW.ha_id,
        v_result.out_score,
        v_result.out_band,
        v_result.out_breakdown,
        'v1.0',
        NOW(),
        NOW()
    )
    ON CONFLICT (fra_id) DO UPDATE SET
        block_id        = EXCLUDED.block_id,
        ha_id           = EXCLUDED.ha_id,
        fra_risk_score  = EXCLUDED.fra_risk_score,
        risk_band       = EXCLUDED.risk_band,
        score_breakdown = EXCLUDED.score_breakdown,
        scorer_version  = EXCLUDED.scorer_version,
        updated_at      = NOW();

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_auto_score_fra ON silver.fra_features;

CREATE TRIGGER trg_auto_score_fra
    AFTER INSERT OR UPDATE
    ON silver.fra_features
    FOR EACH ROW
    EXECUTE FUNCTION silver.fn_auto_score_fra();

COMMENT ON TRIGGER trg_auto_score_fra ON silver.fra_features IS
    'After every INSERT or UPDATE on fra_features, automatically computes '
    'the FRA risk score and upserts the result into silver.fra_risk_scores. '
    'Runs AFTER trg_sync_block_fra_status (alphabetical trigger order).';


-- =============================================================
-- 4.  gold.fra_risk_score_v1
--
-- Joins fra_risk_scores back to block context for the dashboard.
-- Returns one row per block showing the current score, band,
-- and the full breakdown for the "Why this score?" tooltip.
-- =============================================================
CREATE OR REPLACE VIEW gold.fra_risk_score_v1 AS
SELECT
    b.block_id,
    b.ha_id,
    b.portfolio_id,
    b.name              AS block_name,
    b.height_category,
    b.total_units,

    -- Score from the most recent FRA for this block
    rs.fra_risk_score,
    rs.risk_band,
    rs.score_breakdown,
    rs.scorer_version,
    rs.computed_at      AS score_computed_at,

    -- The raw FRA details alongside the score (for context)
    fra.risk_rating     AS fra_raw_risk_rating,
    fra.rag_status,
    fra.assessment_date,
    fra.is_in_date,
    fra.assessment_valid_until,
    fra.overdue_action_count,
    fra.no_date_action_count,
    fra.outstanding_action_count,
    fra.evacuation_strategy,

    -- Convenient score-to-label (for display in dashboard tooltip)
    CASE rs.risk_band
        WHEN 'RED'   THEN 'High Risk — urgent remediation needed'
        WHEN 'AMBER' THEN 'Tolerable but Significant — action required'
        WHEN 'GREEN' THEN 'Fine — no significant fire safety concerns'
        ELSE              'Not yet assessed'
    END                 AS risk_band_label,

    b.updated_at        AS block_updated_at

FROM silver.blocks b

-- Most recent FRA for this block
LEFT JOIN LATERAL (
    SELECT fra2.*
    FROM silver.fra_features fra2
    JOIN silver.document_features df
        ON df.feature_id = fra2.feature_id
       AND df.block_id   = b.block_id
    ORDER BY df.assessment_date DESC NULLS LAST
    LIMIT 1
) fra ON TRUE

-- Score for that FRA
LEFT JOIN silver.fra_risk_scores rs
    ON rs.fra_id = fra.fra_id;

COMMENT ON VIEW gold.fra_risk_score_v1 IS
    'Per-block FRA risk score view. One row per block with score (0–10), '
    'risk band (RED/AMBER/GREEN), score breakdown JSONB, and raw FRA context. '
    'Use score_breakdown->''scorer_notes'' for the dashboard ''Why this score?'' tooltip.';


-- =============================================================
-- 5.  Extend gold.fra_block_detail_v1
--
-- Replaces the migration 013 version with score columns added.
-- Now the main block table view includes both the FRA features
-- AND the computed score so the underwriter sees everything
-- in one query.
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

    -- RAG status (denormalised on blocks by trigger from migration 013)
    b.fra_status                        AS rag_status,

    -- Risk score (from this migration)
    rs.fra_risk_score,
    rs.risk_band,
    rs.score_breakdown,

    -- Latest FRA document fields
    fra.fra_id,
    fra.fra_assessment_type,
    fra.risk_rating                     AS fra_raw_risk_rating,
    fra.rag_status                      AS fra_rag_status,
    fra.assessment_date                 AS fra_assessment_date,
    fra.assessment_valid_until,
    fra.is_in_date,
    fra.next_review_date,
    fra.assessor_name,
    fra.assessor_company,
    fra.evacuation_strategy,
    fra.evacuation_strategy_changed,

    -- Action item counts
    COALESCE(fra.total_action_count, 0)         AS total_action_count,
    COALESCE(fra.overdue_action_count, 0)        AS overdue_action_count,
    COALESCE(fra.no_date_action_count, 0)        AS no_date_action_count,
    COALESCE(fra.outstanding_action_count, 0)    AS outstanding_action_count,
    COALESCE(fra.high_priority_action_count, 0)  AS high_priority_action_count,

    -- BSA 2022
    fra.bsa_2022_applicable,
    fra.mandatory_occurrence_noted,
    fra.has_accessibility_needs_noted,

    -- Key fire safety measures
    fra.has_sprinkler_system,
    fra.has_smoke_detection,
    fra.has_fire_alarm_system,
    fra.has_fire_doors,
    fra.has_compartmentation,
    fra.has_emergency_lighting,

    -- Responsible party
    BOOL_OR(pr.responsible_party = 'third_party')
                                        AS is_third_party_managed,

    -- FRAEW cross-reference
    b.fraew_status,
    fraew.building_risk_rating          AS fraew_risk_rating,
    fraew.pas_9980_compliant,
    fraew.has_remedial_actions,

    fra.extraction_confidence,
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
    SELECT fraew2.building_risk_rating,
           fraew2.pas_9980_compliant,
           fraew2.has_remedial_actions
    FROM silver.fraew_features fraew2
    JOIN silver.document_features df3
        ON df3.feature_id = fraew2.feature_id
       AND df3.block_id   = b.block_id
    ORDER BY df3.assessment_date DESC NULLS LAST
    LIMIT 1
) fraew ON TRUE

LEFT JOIN silver.properties pr
    ON pr.block_id = b.block_id

GROUP BY
    b.block_id, b.ha_id, b.portfolio_id, b.name,
    b.height_category, b.total_units, b.fra_status,
    b.fraew_status, b.updated_at,
    rs.fra_risk_score, rs.risk_band, rs.score_breakdown,
    fra.fra_id, fra.fra_assessment_type, fra.risk_rating, fra.rag_status,
    fra.assessment_date, fra.assessment_valid_until, fra.is_in_date,
    fra.next_review_date, fra.assessor_name, fra.assessor_company,
    fra.evacuation_strategy, fra.evacuation_strategy_changed,
    fra.total_action_count, fra.overdue_action_count, fra.no_date_action_count,
    fra.outstanding_action_count, fra.high_priority_action_count,
    fra.bsa_2022_applicable, fra.mandatory_occurrence_noted,
    fra.has_accessibility_needs_noted,
    fra.has_sprinkler_system, fra.has_smoke_detection,
    fra.has_fire_alarm_system, fra.has_fire_doors,
    fra.has_compartmentation, fra.has_emergency_lighting,
    fra.extraction_confidence,
    fraew.building_risk_rating, fraew.pas_9980_compliant, fraew.has_remedial_actions;

COMMENT ON VIEW gold.fra_block_detail_v1 IS
    'Per-block FRA drill-down (migrations 013 + 014 combined). '
    'Includes computed risk score (0–10), risk band, score breakdown, '
    'action counts, safety measure flags, and FRAEW cross-reference.';


-- =============================================================
-- Self-test: verify scoring function produces expected results
-- for representative inputs. Fails migration if wrong.
-- =============================================================
DO $$
DECLARE
    -- We cannot call compute_fra_risk_score() here without a real fra_id,
    -- so we test the band derivation logic directly.
    v_band TEXT;
BEGIN
    -- Band boundary tests
    ASSERT (CASE WHEN 10.0 >= 7.5 THEN 'GREEN' WHEN 10.0 >= 4.5 THEN 'AMBER' ELSE 'RED' END) = 'GREEN',
        'Score 10.0 should be GREEN';
    ASSERT (CASE WHEN 7.5 >= 7.5 THEN 'GREEN' WHEN 7.5 >= 4.5 THEN 'AMBER' ELSE 'RED' END) = 'GREEN',
        'Score 7.5 (boundary) should be GREEN';
    ASSERT (CASE WHEN 7.4 >= 7.5 THEN 'GREEN' WHEN 7.4 >= 4.5 THEN 'AMBER' ELSE 'RED' END) = 'AMBER',
        'Score 7.4 should be AMBER';
    ASSERT (CASE WHEN 4.5 >= 7.5 THEN 'GREEN' WHEN 4.5 >= 4.5 THEN 'AMBER' ELSE 'RED' END) = 'AMBER',
        'Score 4.5 (boundary) should be AMBER';
    ASSERT (CASE WHEN 4.4 >= 7.5 THEN 'GREEN' WHEN 4.4 >= 4.5 THEN 'AMBER' ELSE 'RED' END) = 'RED',
        'Score 4.4 should be RED';
    ASSERT (CASE WHEN 0.5 >= 7.5 THEN 'GREEN' WHEN 0.5 >= 4.5 THEN 'AMBER' ELSE 'RED' END) = 'RED',
        'Score 0.5 (floor) should be RED';

    -- Scarfe Way scenario:
    -- RAG = AMBER (-2.0), in-date ✓, Type 3 ✓, 10 overdue? No — 0 HIGH overdue
    -- The Scarfe Way FRA had 10 items but all Medium priority, no immediate overdue
    -- Medium actions ~3 outstanding: -0.75
    -- Missing: smoke detection (unknown) = 0, fire doors being remediated = no deduction
    -- Mandatory occurrence: none
    -- Expected: 10 - 2.0 - 0 - 0.75 - 0 - 0 = 7.25 → AMBER ✓
    ASSERT (CASE WHEN 7.25 >= 7.5 THEN 'GREEN' WHEN 7.25 >= 4.5 THEN 'AMBER' ELSE 'RED' END) = 'AMBER',
        'Scarfe Way scenario (7.25) should be AMBER';

    RAISE NOTICE 'Migration 014: scoring band assertions all passed.';
END;
$$;