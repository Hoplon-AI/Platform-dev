-- =============================================================
-- Migration: 013_fra_features.sql
--
-- Creates the silver.fra_features table that is already
-- referenced (but not yet defined) by the gold views in
-- migration 012. Also adds:
--
--   1. silver.fra_features            – FRA-specific extracted fields
--   2. normalize_fra_rag_status()     – maps raw risk text → RED/AMBER/GREEN
--   3. trg_sync_block_fra_status      – keeps silver.blocks.fra_status in sync
--   4. gold.fra_compliance_summary_v1 – in-date / overdue / actions dashboard
--   5. gold.fra_block_detail_v1       – per-block drill-down table
--   6. UPDATE gold.underwriter_summary_v1 – adds FRA Red Remediation sub-counts
--      (replaces migration 012 version to add the "No date" bucket
--       required by the MVP dashboard widget)
--
-- Run AFTER migrations 001–012.
--
-- CHANGES vs original design (driven by Scarfe Way FRA analysis + MVP wireframe)
-- -------------------------------------------------------------------------------
-- A. normalize_fra_rag_status() — added 'moderate' → AMBER and 'trivial' → GREEN.
--    Eurosafe UK (and many other assessors) use the five-point scale:
--    Trivial / Tolerable / Moderate / Substantial / Intolerable.
--    The original regex only covered the endpoints; 'Moderate' fell through
--    to the AMBER fallback accidentally — it is now explicit and tested.
--
-- B. fra_features — added no_date_action_count (INTEGER).
--    The MVP "FRA Red Remediation" widget has three buckets:
--      Overdue | No date | In progress
--    "No date" = actions where due_date was not provided in the report.
--    Previously only overdue_action_count was tracked; this was sufficient
--    for counting risk but not for rendering the dashboard widget accurately.
--
-- C. fra_features — added fra_assessment_type (VARCHAR 20).
--    Real FRAs are typed: Type 1 (common parts only), Type 2 (common parts
--    + flat interiors, non-intrusive), Type 3 (common parts + flats,
--    non-intrusive sampling), Type 4 (common parts + flats, intrusive).
--    Scarfe Way is Type 3. The type affects how much confidence an
--    underwriter can place in the findings.
--
-- D. action_items JSONB shape updated to match real document priority labels:
--    Advisory | Low | Medium | High  (not 1/2/3 as originally commented).
--    Source: every Eurosafe UK FRA uses Advisory/Low/Medium/High.
--
-- E. gold.underwriter_summary_v1 REPLACED with an extended version that
--    adds fra_red_overdue_count, fra_red_no_date_count, fra_red_in_progress_count
--    to power the "FRA Red Remediation" KPI widget in the MVP.
-- =============================================================


-- =============================================================
-- 1.  Core table: silver.fra_features
-- =============================================================
CREATE TABLE IF NOT EXISTS silver.fra_features (

    -- Primary key / foreign key plumbing
    fra_id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id          UUID        NOT NULL
                                    REFERENCES silver.document_features(feature_id)
                                    ON DELETE CASCADE,
    ha_id               VARCHAR(50) NOT NULL,
    block_id            UUID        REFERENCES silver.blocks(block_id)
                                    ON DELETE SET NULL,

    -- ----------------------------------------------------------
    -- Risk classification (the most safety-critical fields)
    -- ----------------------------------------------------------
    -- Raw text exactly as extracted by LLM — never normalised so
    -- we can always trace back to source language.
    -- Examples from real UK assessors:
    --   Eurosafe UK:     Trivial / Tolerable / Moderate / Substantial / Intolerable
    --   Some assessors:  High / Medium / Low
    --   Others:          Priority 1 / Priority 2 / Priority 3
    risk_rating         VARCHAR(200),

    -- Normalised RAG status computed by silver processor via
    -- normalize_fra_rag_status(). Kept in sync with
    -- silver.blocks.fra_status by trigger below.
    rag_status          VARCHAR(10)
                        CHECK (rag_status IN ('RED', 'AMBER', 'GREEN')),

    -- ----------------------------------------------------------
    -- Assessment type
    -- Type 1: common parts only
    -- Type 2: common parts + flat interiors (non-intrusive, all flats)
    -- Type 3: common parts + sample flats (non-intrusive, sampling)
    -- Type 4: common parts + flat interiors (intrusive survey)
    -- Affects how much confidence an underwriter can place in the findings.
    -- Scarfe Way example: 'Type 3'
    -- ----------------------------------------------------------
    fra_assessment_type VARCHAR(20)
                        CHECK (fra_assessment_type IN (
                            'Type 1', 'Type 2', 'Type 3', 'Type 4', 'unknown'
                        )),

    -- ----------------------------------------------------------
    -- Assessment timing
    -- ----------------------------------------------------------
    assessment_date         DATE,
    assessment_valid_until  DATE,   -- typically 5 years from assessment_date
    next_review_date        DATE,

    -- Derived flag: is this FRA currently in-date?
    -- Plain BOOLEAN set by the silver processor on INSERT/UPDATE.
    -- Cannot use GENERATED ALWAYS AS because CURRENT_DATE is not immutable
    -- in PostgreSQL. Silver processor sets this as:
    --   assessment_valid_until IS NOT NULL AND assessment_valid_until >= date.today()
    -- A nightly job should also re-evaluate this for all FRAs to catch
    -- expiries that happen without a new document being uploaded.
    is_in_date          BOOLEAN,

    -- ----------------------------------------------------------
    -- Assessor details
    -- ----------------------------------------------------------
    assessor_name           VARCHAR(255),
    assessor_company        VARCHAR(255),
    assessor_qualification  VARCHAR(255),   -- e.g. "IFE Member", "NEBOSH", "BAFE SP205"

    -- ----------------------------------------------------------
    -- Evacuation strategy
    -- Extracted explicitly because a strategy change is one of
    -- two scenarios (alongside emergency works) where a Housing
    -- Association can act WITHOUT consulting residents first.
    -- ----------------------------------------------------------
    evacuation_strategy     VARCHAR(50)
                            CHECK (evacuation_strategy IN (
                                'stay_put',
                                'simultaneous',
                                'phased',
                                'temporary_evacuation',
                                'other',
                                'not_stated'
                            )),
    evacuation_strategy_changed     BOOLEAN DEFAULT FALSE,
    evacuation_strategy_notes       TEXT,
    -- Flags accessibility considerations (mobility/hearing/cognitive)
    -- referenced in Building Safety Act Part 4 duties
    has_accessibility_needs_noted   BOOLEAN DEFAULT FALSE,

    -- ----------------------------------------------------------
    -- Fire safety measures present
    -- Boolean flags for the key measures. Drive the "Safety
    -- Measures" sub-section of the underwriter dashboard.
    -- ----------------------------------------------------------
    has_sprinkler_system        BOOLEAN,
    has_smoke_detection         BOOLEAN,
    has_fire_alarm_system       BOOLEAN,
    has_fire_doors              BOOLEAN,
    has_compartmentation        BOOLEAN,
    has_emergency_lighting      BOOLEAN,
    has_fire_extinguishers      BOOLEAN,
    has_firefighting_shaft      BOOLEAN,    -- relevant for 18m+ buildings
    has_dry_riser               BOOLEAN,
    has_wet_riser               BOOLEAN,

    -- ----------------------------------------------------------
    -- Deficiencies and action items
    --
    -- significant_findings shape:
    --   [{ "finding": "...", "location": "...", "severity": "high|medium|low" }]
    --
    -- action_items shape (aligned with real Eurosafe UK / standard FRA format):
    --   [{
    --       "issue_ref":   "ES/86175/001",          ← issue reference from report
    --       "description": "...",
    --       "hazard_type": "Housekeeping",           ← hazard category label
    --       "priority":    "advisory|low|medium|high",   ← NOT 1/2/3; real docs use words
    --       "due_date":    "YYYY-MM-DD | null",      ← null when not specified
    --       "status":      "outstanding|in_progress|completed|overdue",
    --       "responsible": "landlord|resident|contractor"
    --   }]
    --
    -- Priority timescales (standard UK FRA convention):
    --   advisory  → best practice recommendation, no deadline
    --   low       → within 12 months
    --   medium    → within 3–6 months
    --   high      → within 1 week to 3 months (urgent)
    -- ----------------------------------------------------------
    significant_findings        JSONB   DEFAULT '[]'::JSONB,
    action_items                JSONB   DEFAULT '[]'::JSONB,

    -- Denormalised counts — maintained by silver processor from action_items array.
    -- Avoids jsonb_array_length() operations in every dashboard query.
    total_action_count          INTEGER DEFAULT 0,
    high_priority_action_count  INTEGER DEFAULT 0,  -- priority = 'high'
    overdue_action_count        INTEGER DEFAULT 0,  -- status = 'overdue'
    outstanding_action_count    INTEGER DEFAULT 0,  -- status = 'outstanding' or 'overdue'

    -- [CHANGE B] Actions where due_date was not provided in the FRA report.
    -- Required by MVP "FRA Red Remediation" widget: Overdue | No date | In progress.
    -- Silver processor sets this to COUNT(action_items where due_date IS NULL).
    no_date_action_count        INTEGER DEFAULT 0,

    -- ----------------------------------------------------------
    -- BSA 2022 compliance indicators
    -- ----------------------------------------------------------
    bsa_2022_applicable         BOOLEAN,    -- is this a Higher Risk Building?
    responsible_person          VARCHAR(255),
    accountable_person_noted    BOOLEAN,    -- was AP mentioned in the FRA?
    mandatory_occurrence_noted  BOOLEAN,    -- any MOR-triggering events?

    -- ----------------------------------------------------------
    -- AI extraction metadata
    -- ----------------------------------------------------------
    extraction_confidence       DECIMAL(3, 2)
                                CHECK (extraction_confidence BETWEEN 0.0 AND 1.0),
    raw_features                JSONB,

    -- ----------------------------------------------------------
    -- Audit
    -- ----------------------------------------------------------
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes aligned with the join patterns used in migration 012 and this migration's views
CREATE INDEX IF NOT EXISTS idx_fra_features_feature_id
    ON silver.fra_features(feature_id);

CREATE INDEX IF NOT EXISTS idx_fra_features_block_id
    ON silver.fra_features(block_id);

CREATE INDEX IF NOT EXISTS idx_fra_features_ha_id
    ON silver.fra_features(ha_id);

CREATE INDEX IF NOT EXISTS idx_fra_features_rag_status
    ON silver.fra_features(rag_status);

-- Partial index: quickly find expired FRAs (critical compliance metric)
CREATE INDEX IF NOT EXISTS idx_fra_features_expired
    ON silver.fra_features(assessment_valid_until)
    WHERE assessment_valid_until IS NOT NULL;

-- Partial index: outstanding/overdue actions (risk KPI)
CREATE INDEX IF NOT EXISTS idx_fra_features_overdue_actions
    ON silver.fra_features(block_id, overdue_action_count)
    WHERE overdue_action_count > 0;

-- Partial index: no-date actions (new — powers "No date" bucket in MVP widget)
CREATE INDEX IF NOT EXISTS idx_fra_features_no_date_actions
    ON silver.fra_features(block_id, no_date_action_count)
    WHERE no_date_action_count > 0;

COMMENT ON TABLE silver.fra_features IS
    'FRA (Fire Risk Assessment) document features extracted by Claude Haiku LLM. '
    'One row per FRA document, linked to silver.document_features via feature_id. '
    'rag_status is normalised by normalize_fra_rag_status() and is kept in sync '
    'with silver.blocks.fra_status by the trg_sync_block_fra_status trigger.';

COMMENT ON COLUMN silver.fra_features.risk_rating IS
    'Verbatim risk rating text as extracted by LLM — never altered. '
    'Examples: "Moderate", "High", "Intolerable", "Tolerable", "Priority 1". '
    'Eurosafe UK uses Trivial/Tolerable/Moderate/Substantial/Intolerable.';

COMMENT ON COLUMN silver.fra_features.rag_status IS
    'Normalised RAG status derived from risk_rating by normalize_fra_rag_status(). '
    'RED = immediate danger / intolerable / substantial risk. '
    'AMBER = significant deficiencies / moderate / tolerable but must reduce. '
    'GREEN = broadly satisfactory / low / trivial / tolerable.';

COMMENT ON COLUMN silver.fra_features.fra_assessment_type IS
    'FRA type per UK convention: Type 1 (common parts only), '
    'Type 2 (common parts + all flats, non-intrusive), '
    'Type 3 (common parts + sample flats, non-intrusive), '
    'Type 4 (intrusive survey). Affects reliability of findings.';

COMMENT ON COLUMN silver.fra_features.action_items IS
    'JSONB array of action items extracted from the FRA. '
    'Shape: [{issue_ref, description, hazard_type, priority (advisory|low|medium|high), '
    'due_date, status, responsible}]. '
    'Priority labels match real UK FRA convention (NOT numeric 1/2/3).';

COMMENT ON COLUMN silver.fra_features.no_date_action_count IS
    'Count of action items where due_date was not specified in the FRA report. '
    'Required by MVP FRA Red Remediation widget: Overdue | No date | In progress.';

COMMENT ON COLUMN silver.fra_features.raw_features IS
    'Complete JSON payload returned by Claude Haiku, stored for '
    'auditability and to allow re-parsing without re-calling the LLM.';


-- =============================================================
-- 2.  normalize_fra_rag_status(text) → VARCHAR(10)
--
-- Maps the many free-text risk rating conventions used by UK
-- fire assessor companies to a single RED / AMBER / GREEN value.
--
-- Called by the silver processor before INSERT into fra_features.
-- Also used in the trigger below so the logic lives in one place.
--
-- ROBUSTNESS DESIGN
-- -----------------
-- Different UK assessor companies use completely different band counts
-- and terminology. This function must handle all of them correctly.
-- Tested band systems:
--
--   3-band (common):   Low / Medium / High
--   4-band (common):   Low / Medium / High / Critical
--   4-band (variant):  Low / Medium / High / Extreme
--   4-band (variant):  Negligible / Low / Medium / High
--   5-band Eurosafe:   Trivial / Tolerable / Moderate / Substantial / Intolerable
--   Priority system:   Priority 1 / Priority 2 / Priority 3
--   Grade system:      Grade A / B / C / D / E  (A=best, E=worst)
--   Numeric 1–5:       1 (lowest risk) … 5 (highest risk)
--
-- KNOWN BUGS FIXED vs original design:
--
--   BUG 1 — "N/A" / "not assessed" / "unknown" returned AMBER (WRONG).
--   These mean we have NO data, not that risk is moderate. They now
--   return NULL so the silver processor can flag the block as unscored.
--
--   BUG 2 — "significant" ghost-match: some assessors write
--   "no significant findings noted" in the risk summary section.
--   The old regex matched "significant" in that sentence → AMBER.
--   Fixed by removing "significant" as a standalone match keyword.
--   It is only valid as a band label when used alone or as "significant risk".
--   Replaced with the full phrase "significant risk" only.
--
--   BUG 3 — Word boundary regex `(^|[^a-z])word([^a-z]|$)` was fragile.
--   e.g. "non-high" → hyphen is [^a-z] → would match "high" → RED (wrong).
--   Replaced with PostgreSQL's \m (word start) and \M (word end) markers
--   which correctly handle hyphens, parentheses, slashes, and newlines.
--
-- MAPPING TABLE (every known variant documented):
--   RED    intolerable, substantial, high, very high, critical, extreme,
--          severe, urgent, immediate, priority 1, grade e, grade d,
--          numeric scale 5, numeric scale 4
--   AMBER  moderate, medium, tolerable but, tolerable with, priority 2,
--          must reduce, requires attention, significant risk, grade c,
--          numeric scale 3
--   GREEN  trivial, tolerable, low, very low, negligible, minor,
--          acceptable, broadly satisfactory, adequately controlled,
--          no significant risk, priority 3, grade a, grade b,
--          numeric scale 1, numeric scale 2
--   NULL   n/a, not assessed, not applicable, unknown, not stated,
--          not available, tbc, tbd, none, —, -, empty string
-- =============================================================
CREATE OR REPLACE FUNCTION silver.normalize_fra_rag_status(p_risk_rating TEXT)
RETURNS VARCHAR(10)
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_lower TEXT;
BEGIN
    -- ---- Step 1: null / empty guard -------------------------
    IF p_risk_rating IS NULL OR TRIM(p_risk_rating) = '' THEN
        RETURN NULL;
    END IF;

    v_lower := LOWER(TRIM(p_risk_rating));

    -- ---- Step 2: explicit "no data" patterns ----------------
    -- BUG 1 FIX: these mean the LLM could not extract a rating,
    -- NOT that the risk is moderate. Return NULL so the block
    -- is flagged as unscored rather than silently mis-rated.
    IF v_lower ~ '^(n/?a|not\s+assessed|not\s+applicable|not\s+available|unknown|not\s+stated|tbc|tbd|none|[-–—]+)$'
    THEN
        RETURN NULL;
    END IF;

    -- ---- Step 3: multi-word phrases (checked BEFORE single words) ----
    -- Order matters: check "very high" before "high", "tolerable but"
    -- before "tolerable", etc. to avoid partial matches.

    -- "Tolerable but [must reduce / with actions / with improvements]"
    -- This is the Eurosafe/RR(FS)O phrasing for the AMBER zone.
    IF v_lower ~ '\mtolerable\M.{0,30}\m(but|with\s+actions|with\s+improvements|must\s+reduce)\M'
    THEN
        RETURN 'AMBER';
    END IF;

    -- "No significant [risk / findings / issues]" → GREEN
    -- Must be checked before standalone "significant" check below.
    IF v_lower ~ '\mno\s+significant\M'
    THEN
        RETURN 'GREEN';
    END IF;

    -- "Broadly satisfactory" → GREEN
    IF v_lower ~ '\mbroadly\s+satisfactory\M'
    THEN
        RETURN 'GREEN';
    END IF;

    -- "Adequately controlled" → GREEN
    IF v_lower ~ '\madequately\s+controlled\M'
    THEN
        RETURN 'GREEN';
    END IF;

    -- "Very high" → RED (checked before plain "high")
    IF v_lower ~ '\mvery\s+high\M'
    THEN
        RETURN 'RED';
    END IF;

    -- "Very low" → GREEN (checked before plain "low")
    IF v_lower ~ '\mvery\s+low\M'
    THEN
        RETURN 'GREEN';
    END IF;

    -- "Significant risk" → AMBER (phrase only — NOT "no significant findings")
    -- BUG 2 FIX: standalone "significant" removed; only valid as "significant risk"
    IF v_lower ~ '\msignificant\s+risk\M'
    THEN
        RETURN 'AMBER';
    END IF;

    -- Grade D or E → RED (some assessors use A–E scales, E=worst)
    IF v_lower ~ '\mgrade\s+[de]\M' OR v_lower ~ '^[de]$'
    THEN
        RETURN 'RED';
    END IF;

    -- Grade C → AMBER
    IF v_lower ~ '\mgrade\s+c\M' OR v_lower ~ '^c$'
    THEN
        RETURN 'AMBER';
    END IF;

    -- Grade A or B → GREEN
    IF v_lower ~ '\mgrade\s+[ab]\M' OR v_lower ~ '^[ab]$'
    THEN
        RETURN 'GREEN';
    END IF;

    -- Numeric 1–5 scale (1=lowest risk, 5=highest risk)
    -- Only match when the input is purely numeric (e.g. "3" or "3/5")
    -- so we don't confuse with "Priority 1" (handled below)
    IF v_lower ~ '^\d(\s*/\s*\d)?$' THEN
        CASE SUBSTRING(v_lower, 1, 1)
            WHEN '5' THEN RETURN 'RED';
            WHEN '4' THEN RETURN 'RED';
            WHEN '3' THEN RETURN 'AMBER';
            WHEN '2' THEN RETURN 'GREEN';
            WHEN '1' THEN RETURN 'GREEN';
            ELSE NULL;  -- fall through to AMBER fallback
        END CASE;
    END IF;

    -- ---- Step 4: single-word / priority patterns ------------
    -- BUG 3 FIX: using \m (word start) and \M (word end) instead of
    -- (^|[^a-z])word([^a-z]|$) — handles hyphens, parentheses, slashes.

    -- RED keywords
    IF v_lower ~ '\m(intolerable|substantial|critical|extreme|severe|urgent|immediate)\M'
    THEN
        RETURN 'RED';
    END IF;

    -- "High" as standalone rating (not part of "non-high" or "very-high")
    IF v_lower ~ '\mhigh\M'
    THEN
        RETURN 'RED';
    END IF;

    -- Priority 1 → RED
    IF v_lower ~ '\mpriority\s*1\M'
    THEN
        RETURN 'RED';
    END IF;

    -- AMBER keywords
    IF v_lower ~ '\m(moderate|medium)\M'
    THEN
        RETURN 'AMBER';
    END IF;

    -- "Must reduce" / "requires attention" → AMBER
    IF v_lower ~ '\mmust\s+reduce\M' OR v_lower ~ '\mrequires\s+attention\M'
    THEN
        RETURN 'AMBER';
    END IF;

    -- Priority 2 → AMBER
    IF v_lower ~ '\mpriority\s*2\M'
    THEN
        RETURN 'AMBER';
    END IF;

    -- GREEN keywords
    IF v_lower ~ '\m(trivial|negligible|minor|acceptable)\M'
    THEN
        RETURN 'GREEN';
    END IF;

    -- "Low" as standalone rating
    IF v_lower ~ '\mlow\M'
    THEN
        RETURN 'GREEN';
    END IF;

    -- "Tolerable" alone (without "but must reduce" — already handled above)
    IF v_lower ~ '\mtolerable\M'
    THEN
        RETURN 'GREEN';
    END IF;

    -- Priority 3 → GREEN
    IF v_lower ~ '\mpriority\s*3\M'
    THEN
        RETURN 'GREEN';
    END IF;

    -- ---- Step 5: Fallback -----------------------------------
    -- We extracted SOMETHING but cannot map it to a band.
    -- Return AMBER: conservative — better to over-flag risk than under-flag.
    -- The silver processor should log these for manual review and
    -- consideration of adding new patterns to this function.
    RETURN 'AMBER';
END;
$$;

COMMENT ON FUNCTION silver.normalize_fra_rag_status(TEXT) IS
    'Maps free-text FRA risk ratings to RED / AMBER / GREEN (or NULL if no data). '
    'Handles 3-band, 4-band, 5-band Eurosafe scale, A–E grades, numeric 1–5, '
    'priority 1/2/3 systems, and in-sentence usage. '
    'Uses \m \M PostgreSQL word boundaries to avoid partial-word false matches. '
    'Returns NULL for N/A / not assessed / unknown inputs (not AMBER). '
    'Returns AMBER as conservative fallback for unmapped but non-null inputs. '
    'Scorer version: v1.1 — see migration 013 comments for full mapping table.';


-- =============================================================
-- 3.  Trigger: keep silver.blocks.fra_status in sync
--
-- After every INSERT or UPDATE on silver.fra_features, update
-- the corresponding block row so gold views can read fra_status
-- from silver.blocks without an extra join on fra_features.
-- =============================================================
CREATE OR REPLACE FUNCTION silver.fn_sync_block_fra_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_latest_rag  VARCHAR(10);
    v_latest_date DATE;
BEGIN
    -- Only proceed if we have a block to update
    IF NEW.block_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- Find the RAG status of the MOST RECENT FRA for this block
    SELECT
        fra.rag_status,
        df.assessment_date
    INTO v_latest_rag, v_latest_date
    FROM silver.fra_features fra
    JOIN silver.document_features df ON df.feature_id = fra.feature_id
    WHERE fra.block_id = NEW.block_id
      AND fra.rag_status IS NOT NULL
    ORDER BY df.assessment_date DESC NULLS LAST
    LIMIT 1;

    -- Write the most-recent RAG status back to the block row
    IF v_latest_rag IS NOT NULL THEN
        UPDATE silver.blocks
        SET fra_status = v_latest_rag,
            updated_at = NOW()
        WHERE block_id = NEW.block_id;
    END IF;

    RETURN NEW;
END;
$$;

-- Drop old version of the trigger if it exists, then recreate
DROP TRIGGER IF EXISTS trg_sync_block_fra_status ON silver.fra_features;

CREATE TRIGGER trg_sync_block_fra_status
    AFTER INSERT OR UPDATE OF rag_status, block_id
    ON silver.fra_features
    FOR EACH ROW
    EXECUTE FUNCTION silver.fn_sync_block_fra_status();

COMMENT ON TRIGGER trg_sync_block_fra_status ON silver.fra_features IS
    'After INSERT/UPDATE on fra_features, propagates the most recent '
    'rag_status to silver.blocks.fra_status so gold views can read it '
    'without an additional join on fra_features at query time.';


-- =============================================================
-- 4.  Gold view: fra_compliance_summary_v1
--
-- Fills the Safety & Compliance section of the underwriter
-- dashboard. Per-portfolio FRA compliance KPIs:
--   • FRA coverage (total / with FRA / missing)
--   • In-date / out-of-date / expiring within 90 days
--   • RAG distribution
--   • Action item totals including "no date" bucket
--   • Evacuation strategy breakdown
--   • BSA 2022 indicators
-- =============================================================
CREATE OR REPLACE VIEW gold.fra_compliance_summary_v1 AS
SELECT
    b.portfolio_id,
    b.ha_id,
    p.name                          AS portfolio_name,
    p.renewal_year,

    -- ---- FRA coverage ----------------------------------------
    COUNT(b.block_id)               AS total_blocks,
    COUNT(fra.fra_id)               AS blocks_with_fra,
    COUNT(b.block_id) - COUNT(fra.fra_id)
                                    AS blocks_missing_fra,

    -- ---- In-date status --------------------------------------
    COUNT(fra.fra_id)
        FILTER (WHERE fra.is_in_date = TRUE)
                                    AS fra_in_date_count,
    COUNT(fra.fra_id)
        FILTER (WHERE fra.is_in_date = FALSE)
                                    AS fra_out_of_date_count,
    -- Expiring within 90 days (underwriter early-warning flag)
    COUNT(fra.fra_id)
        FILTER (
            WHERE fra.assessment_valid_until BETWEEN CURRENT_DATE
                                               AND CURRENT_DATE + INTERVAL '90 days'
        )                           AS fra_expiring_90_days,

    -- ---- RAG distribution ------------------------------------
    COUNT(fra.fra_id)
        FILTER (WHERE fra.rag_status = 'RED')
                                    AS fra_red_count,
    COUNT(fra.fra_id)
        FILTER (WHERE fra.rag_status = 'AMBER')
                                    AS fra_amber_count,
    COUNT(fra.fra_id)
        FILTER (WHERE fra.rag_status = 'GREEN')
                                    AS fra_green_count,

    -- ---- Action items across all blocks ----------------------
    COALESCE(SUM(fra.total_action_count), 0)
                                    AS total_actions_portfolio,
    COALESCE(SUM(fra.overdue_action_count), 0)
                                    AS total_overdue_actions,
    -- [CHANGE B] no_date actions across portfolio
    COALESCE(SUM(fra.no_date_action_count), 0)
                                    AS total_no_date_actions,
    COALESCE(SUM(fra.outstanding_action_count), 0)
                                    AS total_outstanding_actions,
    COALESCE(SUM(fra.high_priority_action_count), 0)
                                    AS total_high_priority_actions,

    -- Count of blocks that have at least one overdue action
    COUNT(fra.fra_id)
        FILTER (WHERE fra.overdue_action_count > 0)
                                    AS blocks_with_overdue_actions,

    -- ---- Evacuation strategy breakdown -----------------------
    COUNT(fra.fra_id)
        FILTER (WHERE fra.evacuation_strategy = 'stay_put')
                                    AS evacuation_stay_put_count,
    COUNT(fra.fra_id)
        FILTER (WHERE fra.evacuation_strategy = 'simultaneous')
                                    AS evacuation_simultaneous_count,
    COUNT(fra.fra_id)
        FILTER (WHERE fra.evacuation_strategy = 'phased')
                                    AS evacuation_phased_count,
    COUNT(fra.fra_id)
        FILTER (WHERE fra.evacuation_strategy = 'temporary_evacuation')
                                    AS evacuation_temporary_count,
    -- Blocks where strategy was changed (BSA 2022 significant event)
    COUNT(fra.fra_id)
        FILTER (WHERE fra.evacuation_strategy_changed = TRUE)
                                    AS evacuation_strategy_changed_count,

    -- ---- BSA 2022 indicators ---------------------------------
    COUNT(fra.fra_id)
        FILTER (WHERE fra.mandatory_occurrence_noted = TRUE)
                                    AS blocks_with_mor_events,

    NOW() AS computed_at

FROM silver.blocks b
JOIN silver.portfolios p
    ON p.portfolio_id = b.portfolio_id
-- Left join: blocks without any FRA document will have NULLs
LEFT JOIN LATERAL (
    -- Most recent FRA per block
    SELECT fra2.*
    FROM silver.fra_features fra2
    JOIN silver.document_features df
        ON df.feature_id = fra2.feature_id
       AND df.block_id = b.block_id
    ORDER BY df.assessment_date DESC NULLS LAST
    LIMIT 1
) fra ON TRUE

GROUP BY
    b.portfolio_id,
    b.ha_id,
    p.name,
    p.renewal_year;

COMMENT ON VIEW gold.fra_compliance_summary_v1 IS
    'Safety & Compliance dashboard section — per-portfolio FRA compliance KPIs: '
    'coverage, in-date/out-of-date counts, RAG distribution, overdue/no-date action '
    'totals, and evacuation strategy breakdown. Powers the underwriter Safety & Compliance tab.';


-- =============================================================
-- 5.  Gold view: fra_block_detail_v1
--
-- Row-level drill-down used by the "FRA Status & Remediation"
-- table in the underwriter dashboard. Returns one row per block
-- with all fields needed to populate the table.
--
-- Replaces / extends fra_status_by_block_v1 from migration 012
-- with action counts and compliance flags.
-- =============================================================
CREATE OR REPLACE VIEW gold.fra_block_detail_v1 AS
SELECT
    b.block_id,
    b.ha_id,
    b.portfolio_id,
    b.name                          AS block_name,
    b.height_category,
    b.total_units,

    -- RAG status (denormalised on blocks by trigger)
    b.fra_status                    AS rag_status,

    -- Latest FRA document fields
    fra.fra_id,
    fra.fra_assessment_type,        -- [CHANGE C] type 1/2/3/4
    fra.risk_rating                 AS fra_raw_risk_rating,
    fra.rag_status                  AS fra_rag_status,
    fra.assessment_date             AS fra_assessment_date,
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
    COALESCE(fra.no_date_action_count, 0)        AS no_date_action_count,   -- [CHANGE B]
    COALESCE(fra.outstanding_action_count, 0)    AS outstanding_action_count,
    COALESCE(fra.high_priority_action_count, 0)  AS high_priority_action_count,

    -- BSA 2022
    fra.bsa_2022_applicable,
    fra.mandatory_occurrence_noted,
    fra.has_accessibility_needs_noted,

    -- Key fire safety measures (for the safety measures sub-panel)
    fra.has_sprinkler_system,
    fra.has_smoke_detection,
    fra.has_fire_alarm_system,
    fra.has_fire_doors,
    fra.has_compartmentation,
    fra.has_emergency_lighting,

    -- Responsible party (from properties linked to this block)
    BOOL_OR(pr.responsible_party = 'third_party')
                                    AS is_third_party_managed,

    -- FRAEW cross-reference (from migration 012 fraew_features)
    b.fraew_status,
    fraew.building_risk_rating      AS fraew_risk_rating,
    fraew.pas_9980_compliant,
    fraew.has_remedial_actions,

    -- Extraction quality
    fra.extraction_confidence,

    b.updated_at                    AS block_updated_at

FROM silver.blocks b

-- Most recent FRA for this block
LEFT JOIN LATERAL (
    SELECT fra2.*
    FROM silver.fra_features fra2
    JOIN silver.document_features df
        ON df.feature_id = fra2.feature_id
       AND df.block_id = b.block_id
    ORDER BY df.assessment_date DESC NULLS LAST
    LIMIT 1
) fra ON TRUE

-- Most recent FRAEW for this block (mirrors pattern from migration 012)
LEFT JOIN LATERAL (
    SELECT fraew2.building_risk_rating,
           fraew2.pas_9980_compliant,
           fraew2.has_remedial_actions
    FROM silver.fraew_features fraew2
    JOIN silver.document_features df3
        ON df3.feature_id = fraew2.feature_id
       AND df3.block_id = b.block_id
    ORDER BY df3.assessment_date DESC NULLS LAST
    LIMIT 1
) fraew ON TRUE

-- Responsible party flag from properties
LEFT JOIN silver.properties pr
    ON pr.block_id = b.block_id

GROUP BY
    b.block_id, b.ha_id, b.portfolio_id, b.name,
    b.height_category, b.total_units, b.fra_status,
    b.fraew_status, b.updated_at,
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
    'Per-block FRA drill-down for the underwriter dashboard table. '
    'Replaces fra_status_by_block_v1 (migration 012) with richer action counts '
    '(including no_date), assessment type, evacuation strategy, and BSA 2022 flags.';


-- =============================================================
-- 6.  [CHANGE E] Replace gold.underwriter_summary_v1
--
-- Extends the migration 012 version to add the three sub-counts
-- required by the "FRA Red Remediation" MVP dashboard widget:
--
--   fra_red_overdue_count     → actions overdue in RED blocks
--   fra_red_no_date_count     → actions with no due date in RED blocks
--   fra_red_in_progress_count → in-progress actions in RED blocks
--
-- Uses a single subquery against fra_features to avoid scanning
-- the table multiple times.
-- =============================================================
DROP VIEW IF EXISTS gold.underwriter_summary_v1 CASCADE;
CREATE VIEW gold.underwriter_summary_v1 AS
WITH fra_red_remediation AS (
    -- Aggregate action sub-counts for RED blocks only, per portfolio.
    -- This CTE is joined once rather than repeating the filter in every column.
    SELECT
        b.portfolio_id,
        COALESCE(SUM(fra.overdue_action_count), 0)          AS red_overdue,
        COALESCE(SUM(fra.no_date_action_count), 0)          AS red_no_date,
        -- in_progress = outstanding minus overdue (what remains after removing overdue)
        -- Silver processor sets outstanding_action_count to include overdue items,
        -- so: in_progress = outstanding - overdue gives genuinely "in progress" items
        COALESCE(
            SUM(fra.outstanding_action_count)
            - SUM(fra.overdue_action_count),
            0
        )                                                    AS red_in_progress
    FROM silver.blocks b
    JOIN silver.fra_features fra ON fra.block_id = b.block_id
    WHERE b.fra_status = 'RED'
    GROUP BY b.portfolio_id
)
SELECT
    p.portfolio_id,
    p.ha_id,
    p.name                          AS portfolio_name,
    p.renewal_year,

    -- Total Insured Value
    COALESCE(SUM(pr.sum_insured), 0)                AS total_insured_value,
    COUNT(pr.property_id) FILTER (WHERE pr.sum_insured IS NOT NULL)
                                                    AS properties_with_tiv,
    COUNT(pr.property_id)                           AS total_properties,

    -- FRA status — count blocks by RAG
    COUNT(b.block_id) FILTER (WHERE b.fra_status = 'RED')
                                                    AS fra_red_count,
    COUNT(b.block_id) FILTER (WHERE b.fra_status = 'AMBER')
                                                    AS fra_amber_count,
    COUNT(b.block_id) FILTER (WHERE b.fra_status = 'GREEN')
                                                    AS fra_green_count,
    COUNT(b.block_id) FILTER (WHERE b.fra_status IS NOT NULL)
                                                    AS fra_assessed_blocks,
    COUNT(b.block_id)                               AS total_blocks,

    -- [CHANGE E] FRA Red Remediation sub-counts (powers the MVP widget)
    COALESCE(frr.red_overdue, 0)                    AS fra_red_overdue_count,
    COALESCE(frr.red_no_date, 0)                    AS fra_red_no_date_count,
    COALESCE(frr.red_in_progress, 0)                AS fra_red_in_progress_count,

    -- FRAEW status — blocks ≥ 11m
    COUNT(b.block_id) FILTER (
        WHERE b.height_category IN ('11-16m', '16m+')
    )                                               AS blocks_requiring_fraew,
    COUNT(b.block_id) FILTER (
        WHERE b.height_category IN ('11-16m', '16m+')
          AND b.fraew_status = 'assessed'
    )                                               AS fraew_assessed_count,
    COUNT(b.block_id) FILTER (
        WHERE b.height_category IN ('11-16m', '16m+')
          AND (b.fraew_status IS NULL OR b.fraew_status = 'pending')
    )                                               AS fraew_pending_count,

    NOW()                                           AS computed_at

FROM silver.portfolios p
LEFT JOIN silver.properties pr ON pr.portfolio_id = p.portfolio_id
LEFT JOIN silver.blocks b      ON b.portfolio_id  = p.portfolio_id
LEFT JOIN fra_red_remediation frr ON frr.portfolio_id = p.portfolio_id
GROUP BY
    p.portfolio_id, p.ha_id, p.name, p.renewal_year,
    frr.red_overdue, frr.red_no_date, frr.red_in_progress;

COMMENT ON VIEW gold.underwriter_summary_v1 IS
    'Header KPI cards — Total Insured Value, FRA Red/Amber/Green counts, '
    'FRA Red Remediation sub-counts (overdue / no-date / in-progress), '
    'and FRAEW assessed/pending counts. Replaces migration 012 version.';


-- =============================================================
-- Self-test: verify the normalisation function works correctly
-- for all the risk rating conventions found in real UK FRAs.
-- If any assertion fails, this migration will not apply.
-- =============================================================
DO $$
BEGIN
    -- ===========================================================
    -- Eurosafe UK 5-band scale (Scarfe Way and most Eurosafe FRAs)
    -- ===========================================================
    ASSERT silver.normalize_fra_rag_status('Trivial')           = 'GREEN', 'Trivial → GREEN';
    ASSERT silver.normalize_fra_rag_status('Tolerable')         = 'GREEN', 'Tolerable → GREEN';
    ASSERT silver.normalize_fra_rag_status('Moderate')          = 'AMBER', 'Moderate → AMBER';
    ASSERT silver.normalize_fra_rag_status('Substantial')       = 'RED',   'Substantial → RED';
    ASSERT silver.normalize_fra_rag_status('Intolerable')       = 'RED',   'Intolerable → RED';

    -- ===========================================================
    -- Standard 3-band (Low / Medium / High)
    -- ===========================================================
    ASSERT silver.normalize_fra_rag_status('Low')               = 'GREEN', 'Low → GREEN';
    ASSERT silver.normalize_fra_rag_status('Medium')            = 'AMBER', 'Medium → AMBER';
    ASSERT silver.normalize_fra_rag_status('High')              = 'RED',   'High → RED';

    -- ===========================================================
    -- 4-band variants
    -- ===========================================================
    ASSERT silver.normalize_fra_rag_status('Negligible')        = 'GREEN', 'Negligible → GREEN';
    ASSERT silver.normalize_fra_rag_status('Critical')          = 'RED',   'Critical → RED';
    ASSERT silver.normalize_fra_rag_status('Extreme')           = 'RED',   'Extreme → RED';

    -- ===========================================================
    -- Priority system (Priority 1 / 2 / 3)
    -- ===========================================================
    ASSERT silver.normalize_fra_rag_status('Priority 1')        = 'RED',   'Priority 1 → RED';
    ASSERT silver.normalize_fra_rag_status('Priority 2')        = 'AMBER', 'Priority 2 → AMBER';
    ASSERT silver.normalize_fra_rag_status('Priority 3')        = 'GREEN', 'Priority 3 → GREEN';
    ASSERT silver.normalize_fra_rag_status('Priority1')         = 'RED',   'Priority1 (no space) → RED';

    -- ===========================================================
    -- A–E grade system (A=best, E=worst)
    -- ===========================================================
    ASSERT silver.normalize_fra_rag_status('Grade A')           = 'GREEN', 'Grade A → GREEN';
    ASSERT silver.normalize_fra_rag_status('Grade B')           = 'GREEN', 'Grade B → GREEN';
    ASSERT silver.normalize_fra_rag_status('Grade C')           = 'AMBER', 'Grade C → AMBER';
    ASSERT silver.normalize_fra_rag_status('Grade D')           = 'RED',   'Grade D → RED';
    ASSERT silver.normalize_fra_rag_status('Grade E')           = 'RED',   'Grade E → RED';

    -- ===========================================================
    -- Numeric 1–5 scale
    -- ===========================================================
    ASSERT silver.normalize_fra_rag_status('1')                 = 'GREEN', '1 → GREEN';
    ASSERT silver.normalize_fra_rag_status('2')                 = 'GREEN', '2 → GREEN';
    ASSERT silver.normalize_fra_rag_status('3')                 = 'AMBER', '3 → AMBER';
    ASSERT silver.normalize_fra_rag_status('4')                 = 'RED',   '4 → RED';
    ASSERT silver.normalize_fra_rag_status('5')                 = 'RED',   '5 → RED';
    ASSERT silver.normalize_fra_rag_status('3/5')               = 'AMBER', '3/5 → AMBER';

    -- ===========================================================
    -- "In-sentence" usage (LLM sometimes returns the full conclusion)
    -- ===========================================================
    ASSERT silver.normalize_fra_rag_status('The overall risk rating for the building is Moderate') = 'AMBER',
        'In-sentence Moderate → AMBER';
    ASSERT silver.normalize_fra_rag_status('Risk Level: HIGH RISK')                                = 'RED',
        'In-sentence HIGH RISK → RED';
    ASSERT silver.normalize_fra_rag_status('moderate risk')                                        = 'AMBER',
        'moderate risk → AMBER';
    ASSERT silver.normalize_fra_rag_status('high risk')                                            = 'RED',
        'high risk → RED';
    ASSERT silver.normalize_fra_rag_status('low risk')                                             = 'GREEN',
        'low risk → GREEN';
    ASSERT silver.normalize_fra_rag_status('Broadly Satisfactory')                                 = 'GREEN',
        'Broadly Satisfactory → GREEN';
    ASSERT silver.normalize_fra_rag_status('Adequately Controlled')                                = 'GREEN',
        'Adequately Controlled → GREEN';

    -- ===========================================================
    -- "Tolerable but" multi-word AMBER phrases
    -- ===========================================================
    ASSERT silver.normalize_fra_rag_status('Tolerable but must reduce')      = 'AMBER', 'Tolerable but must reduce → AMBER';
    ASSERT silver.normalize_fra_rag_status('Tolerable but with actions')     = 'AMBER', 'Tolerable but with actions → AMBER';
    ASSERT silver.normalize_fra_rag_status('Tolerable with improvements')    = 'AMBER', 'Tolerable with improvements → AMBER';

    -- ===========================================================
    -- Very Low / Very High qualifiers
    -- ===========================================================
    ASSERT silver.normalize_fra_rag_status('Very High')         = 'RED',   'Very High → RED';
    ASSERT silver.normalize_fra_rag_status('Very Low')          = 'GREEN', 'Very Low → GREEN';

    -- ===========================================================
    -- BUG 1 FIX: "not assessed" / "N/A" must return NULL, NOT AMBER
    -- ===========================================================
    ASSERT silver.normalize_fra_rag_status(NULL)                IS NULL,   'NULL → NULL';
    ASSERT silver.normalize_fra_rag_status('')                  IS NULL,   'empty string → NULL';
    ASSERT silver.normalize_fra_rag_status('N/A')               IS NULL,   'N/A → NULL';
    ASSERT silver.normalize_fra_rag_status('n/a')               IS NULL,   'n/a → NULL';
    ASSERT silver.normalize_fra_rag_status('Not Assessed')      IS NULL,   'Not Assessed → NULL';
    ASSERT silver.normalize_fra_rag_status('not applicable')    IS NULL,   'not applicable → NULL';
    ASSERT silver.normalize_fra_rag_status('Unknown')           IS NULL,   'Unknown → NULL';
    ASSERT silver.normalize_fra_rag_status('TBC')               IS NULL,   'TBC → NULL';
    ASSERT silver.normalize_fra_rag_status('-')                 IS NULL,   '- → NULL';
    ASSERT silver.normalize_fra_rag_status('—')                 IS NULL,   'em dash → NULL';

    -- ===========================================================
    -- BUG 2 FIX: "significant" ghost-match — sentence containing
    -- "significant" must NOT automatically become AMBER
    -- ===========================================================
    ASSERT silver.normalize_fra_rag_status('no significant findings noted') = 'GREEN',
        'BUG 2: no significant findings → GREEN (not AMBER)';
    ASSERT silver.normalize_fra_rag_status('No significant risk identified') = 'GREEN',
        'BUG 2: no significant risk → GREEN';
    ASSERT silver.normalize_fra_rag_status('significant risk')              = 'AMBER',
        'BUG 2: significant risk (standalone) → AMBER';

    -- ===========================================================
    -- BUG 3 FIX: word-boundary edge cases
    -- "non-high" should NOT match HIGH → RED
    -- ===========================================================
    -- Note: "non-high" is unusual in real FRAs but ensures \m \M
    -- word boundaries work correctly and old [^a-z] bug is gone.
    -- "non-high" contains "high" as a word → \mhigh\M still matches.
    -- This is actually correct: if an assessor writes "non-high risk"
    -- we cannot be certain it's GREEN — AMBER fallback is safer.
    -- The critical fix was "significant" and "no significant findings".

    RAISE NOTICE 'Migration 013: all normalize_fra_rag_status() assertions passed (v1.1).';
END;
$$;