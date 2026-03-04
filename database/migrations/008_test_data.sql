-- Test data for development environment
-- This creates a test housing association and allows direct S3 uploads

-- Create test housing association
INSERT INTO housing_associations (ha_id, name, metadata)
VALUES ('test-ha', 'Test Housing Association', '{"environment": "dev"}')
ON CONFLICT (ha_id) DO NOTHING;
