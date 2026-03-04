-- =============================================================
-- Seed: underwriter_demo_seed.sql
-- Demo data for the Underwriter Portfolio Overview dashboard.
-- Mirrors the Albyn Housing Society example from the UI design.
-- Run AFTER all migrations (001-012).
-- =============================================================

-- 1. Housing Association
INSERT INTO housing_associations (ha_id, name, metadata)
VALUES ('ha_albyn', 'Albyn Housing Society', '{"region": "Scotland"}'::jsonb)
ON CONFLICT (ha_id) DO NOTHING;

-- 2. Portfolio
INSERT INTO silver.portfolios (portfolio_id, ha_id, name, renewal_year)
VALUES ('aaaaaaaa-0000-0000-0000-000000000001', 'ha_albyn', 'Albyn 2025 Portfolio', 2025)
ON CONFLICT (portfolio_id) DO NOTHING;

-- 3. Blocks (10 blocks, mix of heights and FRA statuses)
INSERT INTO silver.blocks (
    block_id, ha_id, portfolio_id, name, jurisdiction,
    total_units, height_m, height_category, build_year,
    construction_type, ews_cladding_status, fra_status, fraew_status
) VALUES
('bbbbbbbb-0000-0000-0000-000000000001','ha_albyn','aaaaaaaa-0000-0000-0000-000000000001','Riverside Court','SCO',24,19.2,'16m+',1994,'concrete_frame','unsafe_acm','RED','assessed'),
('bbbbbbbb-0000-0000-0000-000000000002','ha_albyn','aaaaaaaa-0000-0000-0000-000000000001','Harbour View','SCO',18,16.5,'16m+',1989,'concrete_frame','under_review','RED','assessed'),
('bbbbbbbb-0000-0000-0000-000000000003','ha_albyn','aaaaaaaa-0000-0000-0000-000000000001','Castle Gardens','SCO',12,14.2,'11-16m',2001,'brick','compliant','AMBER','assessed'),
('bbbbbbbb-0000-0000-0000-000000000004','ha_albyn','aaaaaaaa-0000-0000-0000-000000000001','Elm Park','SCO',8,12.1,'11-16m',1998,'brick','compliant','AMBER','pending'),
('bbbbbbbb-0000-0000-0000-000000000005','ha_albyn','aaaaaaaa-0000-0000-0000-000000000001','Meadow Rise','SCO',6,11.8,'11-16m',2005,'timber_frame','compliant','AMBER','pending'),
('bbbbbbbb-0000-0000-0000-000000000006','ha_albyn','aaaaaaaa-0000-0000-0000-000000000001','Birch Lane','SCO',9,13.0,'11-16m',1995,'brick','compliant','AMBER','assessed'),
('bbbbbbbb-0000-0000-0000-000000000007','ha_albyn','aaaaaaaa-0000-0000-0000-000000000001','Oak Court','SCO',6,11.5,'11-16m',2003,'brick','compliant','AMBER','assessed'),
('bbbbbbbb-0000-0000-0000-000000000008','ha_albyn','aaaaaaaa-0000-0000-0000-000000000001','Thistle Close','SCO',4,8.5,'<11m',2010,'brick','none','GREEN',NULL),
('bbbbbbbb-0000-0000-0000-000000000009','ha_albyn','aaaaaaaa-0000-0000-0000-000000000001','Pine Court','SCO',4,7.2,'<11m',2015,'timber_frame','none','GREEN',NULL),
('bbbbbbbb-0000-0000-0000-000000000010','ha_albyn','aaaaaaaa-0000-0000-0000-000000000001','Rowan Place','SCO',4,9.0,'<11m',2012,'brick','none','GREEN',NULL)
ON CONFLICT (block_id) DO UPDATE SET fra_status = EXCLUDED.fra_status, fraew_status = EXCLUDED.fraew_status;

-- 4a. Houses (144 properties, rented, no block)
INSERT INTO silver.properties (
    property_id, ha_id, portfolio_id, block_id,
    uprn, address, postcode, latitude, longitude,
    units, build_year, construction_type,
    tenure, property_type, responsible_party, sum_insured
)
SELECT
    gen_random_uuid(), 'ha_albyn', 'aaaaaaaa-0000-0000-0000-000000000001', NULL,
    LPAD((100000001000 + s)::text, 12, '0'),
    s || ' Birch Avenue, Inverness',
    CASE (s % 4) WHEN 0 THEN 'IV1 1AA' WHEN 1 THEN 'IV2 3BB' WHEN 2 THEN 'IV3 5CC' ELSE 'AB10 1DD' END,
    57.4 + (s % 20) * 0.03, -4.2 + (s % 15) * 0.04,
    1, 1960 + (s % 55), CASE (s % 3) WHEN 0 THEN 'brick' WHEN 1 THEN 'stone' ELSE 'timber_frame' END,
    'rented', 'house', 'ha_controlled',
    65000 + (s % 30) * 2000
FROM generate_series(1, 144) AS s
ON CONFLICT DO NOTHING;

-- 4b. Flats HA-controlled (161 flats in blocks 3-10)
INSERT INTO silver.properties (
    property_id, ha_id, portfolio_id, block_id,
    uprn, address, postcode, latitude, longitude,
    units, build_year, construction_type,
    tenure, property_type, responsible_party, sum_insured
)
SELECT
    gen_random_uuid(), 'ha_albyn', 'aaaaaaaa-0000-0000-0000-000000000001',
    (ARRAY[
        'bbbbbbbb-0000-0000-0000-000000000003',
        'bbbbbbbb-0000-0000-0000-000000000004',
        'bbbbbbbb-0000-0000-0000-000000000005',
        'bbbbbbbb-0000-0000-0000-000000000006',
        'bbbbbbbb-0000-0000-0000-000000000007',
        'bbbbbbbb-0000-0000-0000-000000000008',
        'bbbbbbbb-0000-0000-0000-000000000009',
        'bbbbbbbb-0000-0000-0000-000000000010'
    ])[((s - 1) % 8) + 1]::uuid,
    LPAD((100000002000 + s)::text, 12, '0'),
    'Flat ' || s || ', Castle Gardens, Inverness', 'IV1 2AB',
    57.48 + (s % 10) * 0.01, -4.22 + (s % 8) * 0.01,
    1, 1990 + (s % 30), 'brick',
    'leasehold', 'flat', 'ha_controlled',
    85000 + (s % 25) * 2000
FROM generate_series(1, 161) AS s
ON CONFLICT DO NOTHING;

-- 4c. Flats third-party managed (24 flats in RED blocks 1-2)
INSERT INTO silver.properties (
    property_id, ha_id, portfolio_id, block_id,
    uprn, address, postcode, latitude, longitude,
    units, build_year, construction_type,
    tenure, property_type, responsible_party, sum_insured
)
SELECT
    gen_random_uuid(), 'ha_albyn', 'aaaaaaaa-0000-0000-0000-000000000001',
    CASE WHEN s <= 12 THEN 'bbbbbbbb-0000-0000-0000-000000000001'::uuid ELSE 'bbbbbbbb-0000-0000-0000-000000000002'::uuid END,
    LPAD((100000003000 + s)::text, 12, '0'),
    'Flat ' || s || ', Riverside Court, Inverness', 'IV1 3CD',
    57.49 + (s % 5) * 0.005, -4.24 + (s % 4) * 0.005,
    1, 1994, 'concrete_frame',
    'leasehold', 'flat', 'third_party',
    95000 + (s % 10) * 3000
FROM generate_series(1, 24) AS s
ON CONFLICT DO NOTHING;

-- 4d. Block common areas (83 rows across all 10 blocks)
INSERT INTO silver.properties (
    property_id, ha_id, portfolio_id, block_id,
    uprn, address, postcode, latitude, longitude,
    units, build_year, construction_type,
    tenure, property_type, responsible_party, sum_insured
)
SELECT
    gen_random_uuid(), 'ha_albyn', 'aaaaaaaa-0000-0000-0000-000000000001',
    (ARRAY[
        'bbbbbbbb-0000-0000-0000-000000000001',
        'bbbbbbbb-0000-0000-0000-000000000002',
        'bbbbbbbb-0000-0000-0000-000000000003',
        'bbbbbbbb-0000-0000-0000-000000000004',
        'bbbbbbbb-0000-0000-0000-000000000005',
        'bbbbbbbb-0000-0000-0000-000000000006',
        'bbbbbbbb-0000-0000-0000-000000000007',
        'bbbbbbbb-0000-0000-0000-000000000008',
        'bbbbbbbb-0000-0000-0000-000000000009',
        'bbbbbbbb-0000-0000-0000-000000000010'
    ])[((s - 1) % 10) + 1]::uuid,
    LPAD((100000004000 + s)::text, 12, '0'),
    'Common Area Block ' || s || ', Inverness', 'IV1 4EF',
    57.47 + (s % 10) * 0.01, -4.20 + (s % 8) * 0.01,
    CASE WHEN s % 3 = 0 THEN 10 WHEN s % 3 = 1 THEN 8 ELSE 6 END,
    1995 + (s % 20), 'brick', 'rented', 'block_common',
    CASE WHEN ((s - 1) % 10) + 1 IN (1, 2) THEN 'third_party' ELSE 'ha_controlled' END,
    120000 + (s % 20) * 5000
FROM generate_series(1, 83) AS s
ON CONFLICT DO NOTHING;

-- 5. Underwriter user
INSERT INTO underwriter_users (underwriter_id, email, full_name, organisation, role, is_active)
VALUES ('cccccccc-0000-0000-0000-000000000001','james.mitchell@aviva.com','James Mitchell','Aviva','senior_underwriter',TRUE)
ON CONFLICT (email) DO NOTHING;

-- 6. Access grant
INSERT INTO ha_underwriter_access (ha_id, underwriter_id, renewal_year, access_level, granted_by)
VALUES ('ha_albyn','cccccccc-0000-0000-0000-000000000001',2025,'read','system_seed')
ON CONFLICT (ha_id, underwriter_id, renewal_year) DO NOTHING;

-- 7. Upload audit
INSERT INTO upload_audit (upload_id, ha_id, file_type, filename, s3_key, checksum, file_size, user_id, status)
VALUES
('dddddddd-0000-0000-0000-000000000001','ha_albyn','fra_document','riverside_court_fra.pdf','ha_id=ha_albyn/bronze/dataset=fra_document/submission_id=dddddddd-0000-0000-0000-000000000001/file=riverside_court_fra.pdf','aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111',204800,'ha_user','completed'),
('dddddddd-0000-0000-0000-000000000002','ha_albyn','fra_document','harbour_view_fra.pdf','ha_id=ha_albyn/bronze/dataset=fra_document/submission_id=dddddddd-0000-0000-0000-000000000002/file=harbour_view_fra.pdf','bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222',198656,'ha_user','completed'),
('dddddddd-0000-0000-0000-000000000003','ha_albyn','fraew_document','riverside_court_fraew.pdf','ha_id=ha_albyn/bronze/dataset=fraew_document/submission_id=dddddddd-0000-0000-0000-000000000003/file=riverside_court_fraew.pdf','cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333',512000,'ha_user','completed'),
('dddddddd-0000-0000-0000-000000000004','ha_albyn','property_schedule','albyn_sov_2025.csv','ha_id=ha_albyn/bronze/dataset=property_schedule/submission_id=dddddddd-0000-0000-0000-000000000004/file=albyn_sov_2025.csv','dddd4444dddd4444dddd4444dddd4444dddd4444dddd4444dddd4444dddd4444',98304,'ha_user','completed')
ON CONFLICT (upload_id) DO NOTHING;

-- 8. Document features
INSERT INTO silver.document_features (feature_id, ha_id, upload_id, document_type, building_name, address, postcode, assessment_date, assessor_company, block_id, features_json)
VALUES
('eeeeeeee-0000-0000-0000-000000000001','ha_albyn','dddddddd-0000-0000-0000-000000000001','fra_document','Riverside Court','Riverside Court, Inverness','IV1 3CD','2024-11-15','SafeGuard Fire Consultants','bbbbbbbb-0000-0000-0000-000000000001','{"source":"seed"}'::jsonb),
('eeeeeeee-0000-0000-0000-000000000002','ha_albyn','dddddddd-0000-0000-0000-000000000002','fra_document','Harbour View','Harbour View, Inverness','IV1 3CD','2024-10-20','FireSafe Scotland Ltd','bbbbbbbb-0000-0000-0000-000000000002','{"source":"seed"}'::jsonb),
('eeeeeeee-0000-0000-0000-000000000003','ha_albyn','dddddddd-0000-0000-0000-000000000003','fraew_document','Riverside Court','Riverside Court, Inverness','IV1 3CD','2024-12-01','Exova Warringtonfire','bbbbbbbb-0000-0000-0000-000000000001','{"source":"seed"}'::jsonb)
ON CONFLICT (feature_id) DO NOTHING;

-- 9. FRA features
INSERT INTO silver.fra_features (fra_id, feature_id, ha_id, upload_id, risk_rating, assessment_valid_until)
VALUES
('ffffffff-0000-0000-0000-000000000001','eeeeeeee-0000-0000-0000-000000000001','ha_albyn','dddddddd-0000-0000-0000-000000000001','RED','2025-11-15'),
('ffffffff-0000-0000-0000-000000000002','eeeeeeee-0000-0000-0000-000000000002','ha_albyn','dddddddd-0000-0000-0000-000000000002','RED','2025-10-20')
ON CONFLICT (fra_id) DO NOTHING;

-- 10. FRAEW features
INSERT INTO silver.fraew_features (fraew_id, feature_id, ha_id, upload_id, building_risk_rating, pas_9980_compliant, has_interim_measures, has_remedial_actions)
VALUES
('00000000-ffff-0000-0000-000000000001','eeeeeeee-0000-0000-0000-000000000003','ha_albyn','dddddddd-0000-0000-0000-000000000003','HIGH',FALSE,TRUE,TRUE)
ON CONFLICT (fraew_id) DO NOTHING;

-- Verification counts
SELECT 'housing_associations' AS tbl, COUNT(*) AS cnt FROM housing_associations WHERE ha_id = 'ha_albyn'
UNION ALL SELECT 'portfolios',    COUNT(*) FROM silver.portfolios  WHERE ha_id = 'ha_albyn'
UNION ALL SELECT 'blocks',        COUNT(*) FROM silver.blocks      WHERE ha_id = 'ha_albyn'
UNION ALL SELECT 'properties',    COUNT(*) FROM silver.properties  WHERE ha_id = 'ha_albyn'
UNION ALL SELECT 'uw_users',      COUNT(*) FROM underwriter_users
UNION ALL SELECT 'fra_features',  COUNT(*) FROM silver.fra_features  WHERE ha_id = 'ha_albyn'
UNION ALL SELECT 'fraew_features',COUNT(*) FROM silver.fraew_features WHERE ha_id = 'ha_albyn';