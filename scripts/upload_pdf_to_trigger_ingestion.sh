#!/bin/bash
set -e

# Upload a PDF to S3 to trigger Step Functions ingestion with agentic extraction

if [ $# -lt 2 ]; then
    echo "Usage: $0 <pdf_file> <ha_id> [file_type]"
    echo ""
    echo "Example:"
    echo "  $0 safety_report.pdf ha_demo fra_document"
    echo ""
    echo "File types: fra_document, fraew_document, scr_document"
    exit 1
fi

PDF_FILE="$1"
HA_ID="$2"
FILE_TYPE="${3:-fra_document}"

if [ ! -f "$PDF_FILE" ]; then
    echo "Error: PDF file not found: $PDF_FILE"
    exit 1
fi

# Get bucket from DataStack
BUCKET=$(aws cloudformation describe-stacks \
    --stack-name PlatformDataDev \
    --query 'Stacks[0].Outputs[?OutputKey==`BronzeBucketName`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -z "$BUCKET" ]; then
    echo "Error: Could not get bucket name from PlatformDataDev stack"
    echo "Please provide bucket name:"
    read -p "S3 Bucket Name: " BUCKET
fi

# Generate submission ID and date
SUBMISSION_ID=$(uuidgen)
INGEST_DATE=$(date -u +%Y-%m-%d)
FILENAME=$(basename "$PDF_FILE")

# Build S3 key
S3_KEY="ha_id=${HA_ID}/bronze/dataset=${FILE_TYPE}/ingest_date=${INGEST_DATE}/submission_id=${SUBMISSION_ID}/file=${FILENAME}"

echo "Uploading PDF to trigger ingestion..."
echo "  File: $PDF_FILE"
echo "  Bucket: $BUCKET"
echo "  Key: $S3_KEY"
echo ""

# Upload to S3 (this triggers EventBridge -> Step Functions)
aws s3 cp "$PDF_FILE" "s3://${BUCKET}/${S3_KEY}" \
    --content-type "application/pdf"

echo ""
echo "✓ Upload complete"
echo ""
echo "The Step Functions state machine should trigger automatically."
echo "Check status with:"
echo ""
echo "  # Check Step Functions executions"
echo "  aws stepfunctions list-executions \\"
echo "    --state-machine-arn \$(aws cloudformation describe-stacks \\"
echo "      --stack-name PlatformIngestionDev \\"
echo "      --query 'Stacks[0].Outputs[?OutputKey==\`PdfIngestionStateMachineArn\`].OutputValue' \\"
echo "      --output text) \\"
echo "    --max-results 1"
echo ""
echo "  # Check Lambda logs"
echo "  aws logs tail /aws/lambda/platform-dev-ingestion-worker --follow"
echo ""
echo "  # Check results (after processing completes)"
echo "  python scripts/check_agentic_results.py $SUBMISSION_ID"
echo ""
echo "Upload ID (submission_id): $SUBMISSION_ID"
