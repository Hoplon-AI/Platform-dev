#!/bin/bash
set -e

# Deploy PlatformIngestionDev and test agentic extraction with a safety report

echo "=========================================="
echo "Deploy PlatformIngestionDev & Test Agentic"
echo "=========================================="

# Check prerequisites
if ! command -v cdk &> /dev/null; then
    echo "Error: CDK CLI not found. Install with: npm install -g aws-cdk"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI not found"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS credentials not configured"
    exit 1
fi

echo ""
echo "[1/4] Deploying PlatformIngestionDev stack..."
echo "Note: CDK may report a false positive circular dependency error."
echo "This is a known CDK issue - DataStack does NOT actually depend on IngestionStack."
echo "Deploying prerequisites first, then IngestionStack..."
echo ""

cd infrastructure/aws/cdk

# Activate venv if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set Docker bundling for Lambda layer
export CDK_USE_DOCKER_BUNDLING=true

# Check if prerequisite stacks exist
echo "Checking prerequisite stacks..."
for stack in PlatformNetworkingDev PlatformSecurityDev PlatformDataDev; do
    status=$(aws cloudformation describe-stacks --stack-name "$stack" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
    if [ "$status" = "NOT_FOUND" ] || [ "$status" = "CREATE_FAILED" ] || [ "$status" = "ROLLBACK_COMPLETE" ]; then
        echo "  $stack: Not found or failed. Deploying prerequisites first..."
        echo "  Run: cdk deploy PlatformNetworkingDev PlatformSecurityDev PlatformDataDev"
        echo "  Then: cdk deploy PlatformIngestionDev"
        exit 1
    else
        echo "  $stack: $status"
    fi
done

# Deploy IngestionStack (assumes prerequisites are deployed)
echo ""
echo "Deploying PlatformIngestionDev..."
cdk deploy PlatformIngestionDev --require-approval never

echo ""
echo "[2/4] Verifying agentic extraction is enabled..."
LAMBDA_NAME="platform-dev-ingestion-worker"
USE_AGENTIC=$(aws lambda get-function-configuration \
    --function-name "$LAMBDA_NAME" \
    --query 'Environment.Variables.USE_AGENTIC_EXTRACTION' \
    --output text)

if [ "$USE_AGENTIC" != "true" ]; then
    echo "WARNING: USE_AGENTIC_EXTRACTION is not 'true' (got: $USE_AGENTIC)"
    echo "The Lambda may not have been updated. Check CloudFormation events."
else
    echo "✓ Agentic extraction is enabled"
fi

# Get bucket name
BUCKET=$(aws cloudformation describe-stacks \
    --stack-name PlatformDataDev \
    --query 'Stacks[0].Outputs[?OutputKey==`BronzeBucketName`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -z "$BUCKET" ]; then
    echo "WARNING: Could not get bucket name from DataStack. You may need to deploy DataStack first."
    echo "Please provide the S3 bucket name manually:"
    read -p "S3 Bucket Name: " BUCKET
fi

echo ""
echo "[3/4] Ready to test ingestion"
echo "  Bucket: $BUCKET"
echo "  Lambda: $LAMBDA_NAME"
echo ""
echo "Next steps:"
echo "  1. Upload a PDF safety report (FRA, FRAEW, or SCR document)"
echo "  2. The Step Functions state machine will trigger automatically"
echo "  3. Check results with: python scripts/check_agentic_results.py <upload_id>"
echo ""
echo "To upload via API (if API is running):"
echo "  curl -X POST http://localhost:8000/api/v1/upload/fra-document \\"
echo "    -F 'file=@path/to/safety_report.pdf' \\"
echo "    -H 'Authorization: Bearer <token>'"
echo ""
echo "Or upload directly to S3 to trigger EventBridge:"
echo "  aws s3 cp path/to/safety_report.pdf \\"
echo "    s3://$BUCKET/ha_id=ha_demo/bronze/dataset=fra_document/ingest_date=\$(date +%Y-%m-%d)/submission_id=\$(uuidgen)/file=safety_report.pdf"
echo ""
