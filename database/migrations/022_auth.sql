-- =============================================================
-- Migration: 022_auth.sql
--
-- Adds authentication support for underwriter login.
--
-- What this does:
--   1. Adds password_hash column to underwriter_users
--   2. Adds status column to ha_underwriter_access
--   3. Seeds one test underwriter account (james@aviva.com / demo1234)
--   4. Seeds access grant for ha_demo portfolio
-- =============================================================


-- 1. Password hash on underwriter_users
ALTER TABLE public.underwriter_users
    ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);


-- 2. Status badge on access grants (ready | pending | new)
ALTER TABLE public.ha_underwriter_access
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ready';


-- 3. Seed underwriter account
--    Password: EquiRisk@123
--    Hash generated with: bcrypt.hashpw(b'EquiRisk@123', bcrypt.gensalt())
INSERT INTO public.underwriter_users (
    email,
    full_name,
    organisation,
    role,
    password_hash,
    is_active
)
VALUES (
    'saraswatgovind70@gmail.com',
    'Govind Saraswat',
    'EquiRisk',
    'underwriter',
    '$2b$12$8YQUPIBH7esaAI3uFolnoukNS6tTZM.KVJby38yekG3uPR/lrhFmy',
    true
)
ON CONFLICT (email) DO UPDATE
    SET password_hash = EXCLUDED.password_hash,
        full_name     = EXCLUDED.full_name,
        organisation  = EXCLUDED.organisation,
        is_active     = EXCLUDED.is_active;


-- 4. Seed access grant: saraswatgovind70@gmail.com → ha_demo
INSERT INTO public.ha_underwriter_access (
    ha_id,
    underwriter_id,
    renewal_year,
    access_level,
    granted_by,
    status
)
SELECT
    'ha_demo',
    u.underwriter_id,
    2025,
    'read',
    'Marsh Commercial',
    'ready'
FROM public.underwriter_users u
WHERE u.email = 'saraswatgovind70@gmail.com'
ON CONFLICT (ha_id, underwriter_id, renewal_year) DO UPDATE
    SET granted_by = EXCLUDED.granted_by,
        status     = EXCLUDED.status;
