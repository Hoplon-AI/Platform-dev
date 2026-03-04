#!/usr/bin/env python3
import os

import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks, NagSuppressions

from cdk.networking_stack import NetworkingStack
from cdk.security_stack import SecurityStack
from cdk.data_stack import DataStack
from cdk.ingestion_stack import IngestionStack
from cdk.compute_stack import ComputeStack
from cdk.observability_stack import ObservabilityStack

app = cdk.App()

# Enable cdk-nag security checks
cdk.Aspects.of(app).add(AwsSolutionsChecks())

# Dev environment configuration
dev_account = os.getenv('CDK_DEFAULT_ACCOUNT', '025215344919')
dev_region = os.getenv('CDK_DEFAULT_REGION', 'eu-west-1')

env = cdk.Environment(account=dev_account, region=dev_region)

# Stack 1: Networking (VPC, subnets, VPC endpoints)
networking_stack = NetworkingStack(
    app,
    "PlatformNetworkingDev",
    env=env,
    description="Networking infrastructure: VPC, subnets, VPC endpoints",
)

# Stack 2: Security (KMS, IAM, Secrets Manager)
security_stack = SecurityStack(
    app,
    "PlatformSecurityDev",
    env=env,
    description="Security infrastructure: KMS keys, IAM roles, Secrets Manager",
)

# Stack 3: Data (S3, RDS with PostGIS)
data_stack = DataStack(
    app,
    "PlatformDataDev",
    vpc=networking_stack.vpc,
    database_subnets=networking_stack.database_subnets,
    private_subnets=networking_stack.private_subnets,  # For Lambda VPC access
    s3_key=security_stack.s3_key,
    rds_key=security_stack.rds_key,
    env=env,
    description="Data infrastructure: S3 buckets and RDS PostgreSQL with PostGIS",
)

# Stack 3b: Ingestion (EventBridge -> Step Functions -> worker Lambda)
# Note: CDK may report a false positive circular dependency during synthesis.
# The actual dependency is one-way: IngestionStack -> DataStack (for bronze_bucket).
# DataStack does NOT reference IngestionStack.
# Workaround: Deploy DataStack first, then IngestionStack (see CIRCULAR_DEPENDENCY_WORKAROUND.md)
ingestion_stack = IngestionStack(
    app,
    "PlatformIngestionDev",
    bronze_bucket=data_stack.bronze_bucket,
    vpc=networking_stack.vpc,
    private_subnets=networking_stack.private_subnets,
    database_security_group=data_stack.database_security_group,
    db_secret=data_stack.db_secret,
    database_host=data_stack.database.cluster_endpoint.hostname,
    database_port=data_stack.database.cluster_endpoint.port,
    s3_key=security_stack.s3_key,
    secrets_key=data_stack.secrets_key,
    env=env,
    description="Ingestion infrastructure: EventBridge rule, Step Functions, worker Lambda",
)

# Stack 4: Compute (ECS Fargate + ALB)
compute_stack = ComputeStack(
    app,
    "PlatformComputeDev",
    vpc=networking_stack.vpc,
    private_subnets=networking_stack.private_subnets,
    public_subnets=networking_stack.public_subnets,
    bronze_bucket=data_stack.bronze_bucket,
    db_secret=data_stack.db_secret,
    secrets_key=data_stack.secrets_key,
    s3_key=security_stack.s3_key,
    database_security_group=data_stack.database_security_group,
    database_host=data_stack.database.cluster_endpoint.hostname,
    database_port=data_stack.database.cluster_endpoint.port,
    env=env,
    description="Compute infrastructure: ECS Fargate cluster and ALB",
)

# Stack 5: Observability (CloudWatch alarms and dashboards)
observability_stack = ObservabilityStack(
    app,
    "PlatformObservabilityDev",
    cluster_name=compute_stack.cluster.cluster_name,
    service_name=compute_stack.service.service_name,
    alb_arn=compute_stack.alb.load_balancer_arn,
    database_endpoint=data_stack.database.cluster_endpoint.hostname,
    log_group_name="/ecs/platform-dev",
    lambda_function_name=ingestion_stack.ingestion_lambda.function_name,
    env=env,
    description="Observability infrastructure: CloudWatch alarms, dashboards, and logging",
)

# ---- cdk-nag suppressions (DEV ONLY) ----
# These suppressions are intentionally scoped to the current dev-only environment.
# Tighten/remove these as we harden for staging/prod.
NagSuppressions.add_stack_suppressions(
    networking_stack,
    [
        {"id": "AwsSolutions-VPC7", "reason": "Dev: VPC Flow Logs not enabled yet; will enable for staging/prod."},
        {"id": "CdkNagValidationFailure", "reason": "Dev: Interface endpoint SG rule validation hits intrinsics; review in staging/prod."},
        {"id": "AwsSolutions-EC23", "reason": "Dev: Endpoint security groups managed by CDK; intrinsics prevent static analysis."},
    ],
)

NagSuppressions.add_stack_suppressions(
    data_stack,
    [
        {"id": "AwsSolutions-SMG4", "reason": "Dev: Secret rotation deferred; enable rotation when workloads stabilize."},
        {"id": "AwsSolutions-S1", "reason": "Dev: Access logs bucket not configured yet; enable for staging/prod."},
        {"id": "AwsSolutions-S10", "reason": "Dev: SSL enforced via bucket policy; cdk-nag may not detect it."},
        {"id": "AwsSolutions-RDS3", "reason": "Dev: Single-AZ Aurora for cost; enable Multi-AZ in staging/prod."},
        {"id": "AwsSolutions-RDS6", "reason": "Dev: IAM database authentication disabled for simplicity; enable for prod."},
        {"id": "AwsSolutions-RDS10", "reason": "Dev: Deletion protection disabled for iteration; enable in prod."},
        {"id": "AwsSolutions-RDS11", "reason": "Dev: Using default Postgres port; will review for prod hardening."},
        {"id": "AwsSolutions-IAM4", "reason": "Dev: CDK-generated Lambda roles may use AWS managed policies; tighten later."},
        {"id": "AwsSolutions-IAM5", "reason": "Dev: Lambda needs S3/KMS wildcard permissions for ingestion pipeline; tighten later."},
        {"id": "AwsSolutions-L1", "reason": "Dev: Using Python 3.11 for compatibility; upgrade to latest when available."},
    ],
)

NagSuppressions.add_stack_suppressions(
    ingestion_stack,
    [
        {"id": "AwsSolutions-IAM4", "reason": "Dev: Lambda/StepFn roles use AWS managed policies; tighten for staging/prod."},
        {"id": "AwsSolutions-IAM5", "reason": "Dev: Ingestion worker needs broad S3 object access within bronze bucket prefix; tighten later."},
        {"id": "AwsSolutions-L1", "reason": "Dev: Using Python 3.12; revisit runtime pinning policy as AWS evolves."},
        {"id": "AwsSolutions-SF2", "reason": "Enabled tracing on state machine; remaining warnings may be false positives."},
    ],
)

NagSuppressions.add_stack_suppressions(
    compute_stack,
    [
        {"id": "AwsSolutions-ELB2", "reason": "Dev: ALB access logs not enabled yet; enable for staging/prod."},
        {"id": "AwsSolutions-EC23", "reason": "Dev: ALB must be publicly reachable in dev; restrict via WAF in prod."},
        {"id": "AwsSolutions-ECS2", "reason": "Dev: Env vars used for bootstrap; move sensitive values to Secrets Manager."},
        {"id": "AwsSolutions-IAM4", "reason": "Dev: Using AWS managed policy for ECS execution role; replace with least-privilege later."},
        {"id": "AwsSolutions-IAM5", "reason": "Dev: CDK grants wildcard actions for S3/KMS convenience; tighten later."},
    ],
)

NagSuppressions.add_stack_suppressions(
    observability_stack,
    [
        {"id": "AwsSolutions-SNS3", "reason": "Dev: SNS topic policy hardening deferred; enable TLS-only publishers for prod."},
    ],
)

# Stack dependencies are inferred from cross-stack references (preferred).
# Avoid manual dependencies here to prevent accidental cyclic references.

app.synth()
