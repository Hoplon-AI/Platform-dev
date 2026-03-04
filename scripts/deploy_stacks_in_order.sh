#!/bin/bash
set -e

# Deploy CDK stacks in order to work around circular dependency false positive
# This script deploys stacks sequentially, temporarily commenting out IngestionStack

echo "=========================================="
echo "Deploy CDK Stacks in Order"
echo "=========================================="

cd infrastructure/aws/cdk

# Activate venv if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

export CDK_USE_DOCKER_BUNDLING=true

echo ""
echo "Step 1/3: Deploying prerequisite stacks (Networking, Security, Data)..."
echo "Note: IngestionStack is temporarily commented out in app.py"
echo ""

# Deploy prerequisites (IngestionStack is commented out in app.py)
cdk deploy PlatformNetworkingDev PlatformSecurityDev PlatformDataDev --require-approval never

echo ""
echo "Step 2/3: Restoring IngestionStack in app.py..."
echo ""

# Restore IngestionStack in app.py
sed -i.bak 's/^# ingestion_stack = IngestionStack(/ingestion_stack = IngestionStack(/g' app.py
sed -i.bak 's/^#     app,/    app,/g' app.py
sed -i.bak 's/^#     "PlatformIngestionDev",/"PlatformIngestionDev",/g' app.py
sed -i.bak 's/^#     bronze_bucket=data_stack.bronze_bucket,/    bronze_bucket=data_stack.bronze_bucket,/g' app.py
sed -i.bak 's/^#     vpc=networking_stack.vpc,/    vpc=networking_stack.vpc,/g' app.py
sed -i.bak 's/^#     private_subnets=networking_stack.private_subnets,/    private_subnets=networking_stack.private_subnets,/g' app.py
sed -i.bak 's/^#     database_security_group=data_stack.database_security_group,/    database_security_group=data_stack.database_security_group,/g' app.py
sed -i.bak 's/^#     db_secret=data_stack.db_secret,/    db_secret=data_stack.db_secret,/g' app.py
sed -i.bak 's/^#     database_host=data_stack.database.instance_endpoint.hostname,/    database_host=data_stack.database.instance_endpoint.hostname,/g' app.py
sed -i.bak 's/^#     database_port=data_stack.database.instance_endpoint.port,/    database_port=data_stack.database.instance_endpoint.port,/g' app.py
sed -i.bak 's/^#     s3_key=security_stack.s3_key,/    s3_key=security_stack.s3_key,/g' app.py
sed -i.bak 's/^#     secrets_key=data_stack.secrets_key,/    secrets_key=data_stack.secrets_key,/g' app.py
sed -i.bak 's/^#     env=env,/    env=env,/g' app.py
sed -i.bak 's/^#     description="Ingestion infrastructure: EventBridge rule, Step Functions, worker Lambda",/    description="Ingestion infrastructure: EventBridge rule, Step Functions, worker Lambda",/g' app.py
sed -i.bak 's/^# )/)/g' app.py

# Restore ObservabilityStack reference
sed -i.bak 's/lambda_function_name=None,  # Temporarily None/lambda_function_name=ingestion_stack.ingestion_lambda.function_name,/g' app.py
sed -i.bak 's/# lambda_function_name=ingestion_stack.ingestion_lambda.function_name,//g' app.py

# Restore NagSuppressions
sed -i.bak 's/^# NagSuppressions.add_stack_suppressions(/NagSuppressions.add_stack_suppressions(/g' app.py
sed -i.bak 's/^#     ingestion_stack,/    ingestion_stack,/g' app.py
sed -i.bak 's/^#     \[/    [/g' app.py
sed -i.bak 's/^#         {"id": "AwsSolutions-IAM4"/        {"id": "AwsSolutions-IAM4"/g' app.py
sed -i.bak 's/^#         {"id": "AwsSolutions-IAM5"/        {"id": "AwsSolutions-IAM5"/g' app.py
sed -i.bak 's/^#         {"id": "AwsSolutions-L1"/        {"id": "AwsSolutions-L1"/g' app.py
sed -i.bak 's/^#         {"id": "AwsSolutions-SF2"/        {"id": "AwsSolutions-SF2"/g' app.py
sed -i.bak 's/^#     \],/    ],/g' app.py
sed -i.bak 's/^# )/)/g' app.py

echo "Step 3/3: Deploying IngestionStack..."
echo ""

cdk deploy PlatformIngestionDev --require-approval never

echo ""
echo "✓ All stacks deployed successfully!"
echo ""
echo "Next: Test ingestion with:"
echo "  ./scripts/upload_pdf_to_trigger_ingestion.sh data/scr/10532-midland-heart-crocodile-works-report.pdf ha_demo scr_document"
