-- Migration 021: Add renewal_date to silver.portfolios
--
-- The UI shows "Renewal: 15 Mar 2025" — a full date, not just a year.
-- silver.portfolios currently only has renewal_year INTEGER.
-- This adds renewal_date DATE (nullable, can be backfilled from renewal_year).
-- renewal_year is kept for backwards compatibility.

ALTER TABLE silver.portfolios
    ADD COLUMN IF NOT EXISTS renewal_date DATE;

COMMENT ON COLUMN silver.portfolios.renewal_date
    IS 'Full renewal date (e.g. 2025-03-15). Shown in dashboard header as "Renewal: 15 Mar 2025". renewal_year INTEGER is retained for backwards compatibility.';

-- Backfill from renewal_year: default to 1st January of that year
UPDATE silver.portfolios
SET renewal_date = make_date(renewal_year, 1, 1)
WHERE renewal_date IS NULL
  AND renewal_year IS NOT NULL;
