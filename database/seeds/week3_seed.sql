-- Seed data for Week 3 dashboard development
-- Intended for local/dev only.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Tenant / HA
INSERT INTO housing_associations (ha_id, name, metadata)
VALUES ('ha_demo', 'Demo Housing Association', '{"seed":"week3"}'::jsonb)
ON CONFLICT (ha_id) DO NOTHING;

-- Portfolio
INSERT INTO portfolios (portfolio_id, ha_id, name, renewal_year, metadata)
VALUES (
  '11111111-1111-1111-1111-111111111111',
  'ha_demo',
  'Demo Portfolio',
  2026,
  '{"seed":"week3"}'::jsonb
)
ON CONFLICT (portfolio_id) DO NOTHING;

-- Blocks
INSERT INTO blocks (
  block_id, ha_id, portfolio_id, name, jurisdiction, total_units, height_m, height_category,
  build_year, construction_type, ews_cladding_status, risk_rating, metadata
)
VALUES
(
  '22222222-2222-2222-2222-222222222222',
  'ha_demo',
  '11111111-1111-1111-1111-111111111111',
  'Block A',
  'ENG',
  20,
  18.5,
  '16m+',
  1998,
  'concrete',
  'unknown',
  'C',
  '{"seed":"week3"}'::jsonb
),
(
  '33333333-3333-3333-3333-333333333333',
  'ha_demo',
  '11111111-1111-1111-1111-111111111111',
  'Block B',
  'SCO',
  10,
  9.2,
  '<11m',
  2008,
  'brick',
  'none',
  'D',
  '{"seed":"week3"}'::jsonb
)
ON CONFLICT (block_id) DO NOTHING;

-- Properties (property_id is PK; UPRN indexed for joins)
INSERT INTO properties (
  property_id, ha_id, portfolio_id, block_id,
  uprn, address, postcode, latitude, longitude,
  units, height_m, build_year, construction_type, tenure, risk_rating, metadata
)
VALUES
(
  '44444444-4444-4444-4444-444444444444',
  'ha_demo',
  '11111111-1111-1111-1111-111111111111',
  '22222222-2222-2222-2222-222222222222',
  '100000000001',
  '1 Test Street',
  'SW1A 1AA',
  51.5010,
  -0.1416,
  1,
  18.5,
  1998,
  'concrete',
  'rented',
  'C',
  '{"seed":"week3"}'::jsonb
),
(
  '55555555-5555-5555-5555-555555555555',
  'ha_demo',
  '11111111-1111-1111-1111-111111111111',
  '33333333-3333-3333-3333-333333333333',
  '100000000002',
  '2 Demo Road',
  'EH1 1AA',
  55.9533,
  -3.1883,
  1,
  9.2,
  2008,
  'brick',
  'leasehold',
  'D',
  '{"seed":"week3"}'::jsonb
)
ON CONFLICT (property_id) DO NOTHING;

-- Upload audit (powers gold.ha_recent_activity_v1)
INSERT INTO upload_audit (
  upload_id, ha_id, file_type, filename, s3_key, checksum, file_size, user_id, uploaded_at, status, metadata
)
VALUES
(
  gen_random_uuid(),
  'ha_demo',
  'property_schedule',
  'demo_property_schedule.csv',
  'ha_demo/bronze/demo-upload-1/demo_property_schedule.csv',
  'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
  12345,
  'demo_user',
  NOW() - INTERVAL '2 days',
  'completed',
  '{"seed":"week3"}'::jsonb
),
(
  gen_random_uuid(),
  'ha_demo',
  'epc_data',
  'demo_epc.csv',
  'ha_demo/bronze/demo-upload-2/demo_epc.csv',
  'feedfacefeedfacefeedfacefeedfacefeedfacefeedfacefeedfacefeedface',
  23456,
  'demo_user',
  NOW() - INTERVAL '1 days',
  'completed',
  '{"seed":"week3"}'::jsonb
);

