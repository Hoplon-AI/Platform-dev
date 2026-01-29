#!/bin/bash
set -e

# Wait for PlatformDataDev to complete, then deploy PlatformIngestionDev

echo "=========================================="
echo "Wait for DataStack, then Deploy IngestionStack"
echo "=========================================="

echo "Monitoring PlatformDataDev status..."
while true; do
    STATUS=$(aws cloudformation describe-stacks --stack-name PlatformDataDev --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
    echo "$(date +%H:%M:%S) - PlatformDataDev: $STATUS"
    
    if [ "$STATUS" = "CREATE_COMPLETE" ] || [ "$STATUS" = "UPDATE_COMPLETE" ]; then
        echo ""
        echo "✓ PlatformDataDev is ready!"
        break
    elif [ "$STATUS" = "CREATE_FAILED" ] || [ "$STATUS" = "ROLLBACK_COMPLETE" ]; then
        echo ""
        echo "✗ PlatformDataDev failed! Check CloudFormation console for details."
        exit 1
    fi
    
    sleep 30
done

echo ""
echo "Deploying PlatformIngestionDev..."
echo ""

cd infrastructure/aws/cdk

# Activate venv if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

export CDK_USE_DOCKER_BUNDLING=true

cdk deploy PlatformIngestionDev --require-approval never

echo ""
echo "✓ PlatformIngestionDev deployed!"
echo ""
echo "Next: Test ingestion with:"
echo "  ./scripts/upload_pdf_to_trigger_ingestion.sh data/scr/10532-midland-heart-crocodile-works-report.pdf ha_demo scr_document"
