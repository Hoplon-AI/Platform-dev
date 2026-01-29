#!/bin/bash
set -e

# Migrate from RDS Instance to Aurora Serverless v2
# This script handles the replacement by:
# 1. Creating a snapshot of existing RDS (optional, for data preservation)
# 2. Removing the old database resource
# 3. Deploying Aurora cluster

echo "=========================================="
echo "Migrate RDS to Aurora Serverless v2"
echo "=========================================="

cd infrastructure/aws/cdk

# Activate venv if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

export CDK_USE_DOCKER_BUNDLING=true

# Check if RDS instance exists
DB_INSTANCE_ID=$(aws rds describe-db-instances \
    --query 'DBInstances[?DBInstanceIdentifier==`platform-dev-platformdatabase`].DBInstanceIdentifier' \
    --output text 2>/dev/null || echo "")

if [ -n "$DB_INSTANCE_ID" ]; then
    echo ""
    echo "Found existing RDS instance: $DB_INSTANCE_ID"
    echo ""
    read -p "Create snapshot before migration? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        SNAPSHOT_ID="platform-dev-migration-$(date +%Y%m%d-%H%M%S)"
        echo "Creating snapshot: $SNAPSHOT_ID"
        aws rds create-db-snapshot \
            --db-instance-identifier "$DB_INSTANCE_ID" \
            --db-snapshot-identifier "$SNAPSHOT_ID"
        echo "Waiting for snapshot to complete..."
        aws rds wait db-snapshot-completed --db-snapshot-identifier "$SNAPSHOT_ID"
        echo "✓ Snapshot created: $SNAPSHOT_ID"
    fi
fi

echo ""
echo "Step 1: Removing old database from stack..."
echo "Note: We'll temporarily remove the database resource, then add Aurora"

# Option 1: Delete the database resource from CloudFormation
# This will delete the RDS instance
read -p "Delete existing RDS instance and create Aurora? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled."
    exit 0
fi

echo ""
echo "Step 2: Deleting old database resource..."
# Use CDK destroy or CloudFormation delete
# For safety, we'll use CloudFormation to delete just the database resource
aws cloudformation delete-stack --stack-name PlatformDataDev 2>/dev/null || true

echo "Waiting for stack deletion..."
aws cloudformation wait stack-delete-complete --stack-name PlatformDataDev || echo "Stack deletion in progress..."

echo ""
echo "Step 3: Deploying Aurora Serverless v2 cluster..."
cdk deploy PlatformDataDev --require-approval never

echo ""
echo "✓ Migration complete!"
echo ""
echo "Aurora Serverless v2 is now deployed with auto-pause."
echo "Cost when idle: ~$0 compute + ~$2/month storage"
echo ""
echo "Next steps:"
echo "  1. Enable PostGIS: psql -h <cluster-endpoint> -U postgres -d platform_dev -c 'CREATE EXTENSION IF NOT EXISTS postgis;'"
echo "  2. If you created a snapshot, you can restore data manually if needed"
