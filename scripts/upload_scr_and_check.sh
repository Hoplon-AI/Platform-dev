#!/bin/bash
set -e

# Upload SCR PDF and check results (works with existing infrastructure)

PDF_FILE="data/scr/10532-midland-heart-crocodile-works-report.pdf"
HA_ID="ha_demo"
FILE_TYPE="scr_document"

if [ ! -f "$PDF_FILE" ]; then
    echo "Error: PDF file not found: $PDF_FILE"
    exit 1
fi

echo "=========================================="
echo "Upload SCR PDF and Check Agentic Results"
echo "=========================================="

# Try to get bucket from existing stack or use default
BUCKET=$(aws cloudformation describe-stacks \
    --stack-name PlatformDataDev \
    --query 'Stacks[0].Outputs[?OutputKey==`BronzeBucketName`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -z "$BUCKET" ]; then
    # Try to find any platform-bronze bucket
    BUCKET=$(aws s3 ls | grep "platform-bronze" | awk '{print $3}' | head -1)
fi

if [ -z "$BUCKET" ]; then
    echo "Error: Could not find S3 bucket."
    echo ""
    echo "Options:"
    echo "  1. Deploy stacks first (but there's a circular dependency issue to resolve)"
    echo "  2. Create bucket manually:"
    echo "     aws s3 mb s3://platform-bronze-<account-id>-<region>"
    echo "  3. Test locally with LocalStack (see scripts/run_e2e_ingestion_local.py)"
    exit 1
fi

echo "Using bucket: $BUCKET"

# Generate submission ID and date
SUBMISSION_ID=$(uuidgen)
INGEST_DATE=$(date -u +%Y-%m-%d)
FILENAME=$(basename "$PDF_FILE")

# Build S3 key
S3_KEY="ha_id=${HA_ID}/bronze/dataset=${FILE_TYPE}/ingest_date=${INGEST_DATE}/submission_id=${SUBMISSION_ID}/file=${FILENAME}"

echo ""
echo "[1/3] Uploading PDF to S3..."
aws s3 cp "$PDF_FILE" "s3://${BUCKET}/${S3_KEY}" \
    --content-type "application/pdf"

echo "✓ Upload complete"
echo "  Key: $S3_KEY"
echo "  Submission ID: $SUBMISSION_ID"

echo ""
echo "[2/3] Waiting for Step Functions to process (30 seconds)..."
sleep 30

echo ""
echo "[3/3] Check results with:"
echo ""
echo "  # Check Lambda logs"
echo "  aws logs tail /aws/lambda/platform-dev-ingestion-worker --since 5m"
echo ""
echo "  # Check Step Functions execution"
echo "  aws stepfunctions list-executions \\"
echo "    --state-machine-arn \$(aws cloudformation describe-stacks \\"
echo "      --stack-name PlatformIngestionDev \\"
echo "      --query 'Stacks[0].Outputs[?OutputKey==\`PdfIngestionStateMachineArn\`].OutputValue' \\"
echo "      --output text 2>/dev/null || echo 'Stack not found') \\"
echo "    --max-results 1"
echo ""
echo "  # Check database results (requires DB access)"
echo "  python scripts/check_agentic_results.py $SUBMISSION_ID"
echo ""
echo "Upload ID (submission_id): $SUBMISSION_ID"
