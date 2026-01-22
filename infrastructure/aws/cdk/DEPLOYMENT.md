# CDK Infrastructure Deployment Guide

This guide covers deploying the Platform infrastructure stacks to AWS.

## Stack Overview

The infrastructure is organized into 6 separate stacks:

1. **NetworkingStack** (`PlatformNetworkingDev`)
   - VPC with public/private/isolated subnets
   - VPC endpoints (S3, ECR, CloudWatch, Secrets Manager)
   - NAT Gateway

2. **SecurityStack** (`PlatformSecurityDev`)
   - KMS keys for S3, RDS, and Secrets Manager
   - IAM roles for ECS tasks
   - Secrets Manager secret for database credentials

3. **DataStack** (`PlatformDataDev`)
   - S3 buckets (Bronze layer, processed data)
   - RDS PostgreSQL 16.9 instance
   - Database subnet group and security group

4. **IngestionStack** (`PlatformIngestionDev`)
   - EventBridge rule (filters S3 Object Created for keys containing `/file=`)
   - Step Functions state machine
   - Worker Lambda (PDF extraction/validation/features)

5. **ComputeStack** (`PlatformComputeDev`)
   - ECS Fargate cluster
   - Application Load Balancer
   - ECS service with auto-scaling

6. **ObservabilityStack** (`PlatformObservabilityDev`)
   - CloudWatch alarms (ECS, ALB, RDS)
   - CloudWatch dashboard
   - SNS topic for notifications

## Prerequisites

1. **AWS CLI configured** with appropriate credentials
2. **CDK CLI installed**: `npm install -g aws-cdk`
3. **Python 3.13+** with virtual environment
4. **CDK bootstrapped** in target account/region:
   ```bash
   cdk bootstrap aws://025215344919/eu-west-1
   ```

## Setup

### 1. Install Dependencies

```bash
cd infrastructure/aws/cdk
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Set environment variables (or use AWS CLI profiles):

```bash
export CDK_DEFAULT_ACCOUNT=025215344919
export CDK_DEFAULT_REGION=eu-west-1
```

Or use AWS profile:

```bash
export AWS_PROFILE=dev-deployer
```

### 3. Synthesize Templates

```bash
cdk synth
```

This generates CloudFormation templates without deploying.

Note: the ingestion worker Lambda uses a dependency layer that can be Docker-bundled.
To enable bundling (recommended for deploy), set:

```bash
export CDK_USE_DOCKER_BUNDLING=true
```

### 4. Review Changes

```bash
cdk diff
```

Shows what will be created/modified.

### 5. Deploy Stacks

Deploy in order (dependencies are handled automatically):

```bash
# Deploy all stacks
cdk deploy --all

# Or deploy individually
cdk deploy PlatformNetworkingDev
cdk deploy PlatformSecurityDev
cdk deploy PlatformDataDev
cdk deploy PlatformIngestionDev
cdk deploy PlatformComputeDev
cdk deploy PlatformObservabilityDev
```

## Post-Deployment Steps

### Enable PostGIS Extension

After RDS is created, enable PostGIS:

```bash
# Get database endpoint from stack outputs
DB_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name PlatformDataDev \
  --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
  --output text)

# Get database password from Secrets Manager
DB_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id PlatformSecurityDev-DatabaseSecret \
  --query 'SecretString' \
  --output text | jq -r '.password')

# Connect and enable PostGIS
psql -h $DB_ENDPOINT -U postgres -d platform_dev -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

Or use AWS Systems Manager Session Manager if RDS is in private subnet.

### Update Container Image

The compute stack uses a placeholder nginx image. Update to your FastAPI image:

1. Build and push image to ECR
2. Update `compute_stack.py`:
   ```python
   image=ecs.ContainerImage.from_ecr_repository(
       repository=ecr_repository,
       tag="latest"
   )
   ```
3. Redeploy compute stack

## Stack Outputs

### Networking Stack
- `VpcId`: VPC ID
- `PrivateSubnetIds`: Comma-separated private subnet IDs
- `DatabaseSubnetIds`: Comma-separated database subnet IDs

### Security Stack
- `S3KmsKeyId`: KMS key for S3 encryption
- `RDSKmsKeyId`: KMS key for RDS encryption
- `DatabaseSecretArn`: ARN of database credentials secret
- `EcsExecutionRoleArn`: ECS task execution role ARN
- `EcsTaskRoleArn`: ECS task role ARN

### Data Stack
- `BronzeBucketName`: S3 bucket for Bronze layer
- `ProcessedBucketName`: S3 bucket for processed data
- `DatabaseEndpoint`: RDS PostgreSQL endpoint
- `DatabasePort`: RDS PostgreSQL port
- `DatabaseSecurityGroupId`: Database security group ID

### Compute Stack
- `ClusterName`: ECS cluster name
- `ALBDnsName`: Application Load Balancer DNS name
- `ServiceName`: ECS service name

### Observability Stack
- `DashboardUrl`: CloudWatch Dashboard URL
- `AlarmTopicArn`: SNS topic ARN for alarms

## Viewing Outputs

```bash
# Get all outputs from a stack
aws cloudformation describe-stacks \
  --stack-name PlatformNetworkingDev \
  --query 'Stacks[0].Outputs' \
  --output table

# Get specific output
aws cloudformation describe-stacks \
  --stack-name PlatformComputeDev \
  --query 'Stacks[0].Outputs[?OutputKey==`ALBDnsName`].OutputValue' \
  --output text
```

## Security Considerations

### Current Configuration (Dev)
- Single NAT Gateway (cost optimization)
- Single AZ RDS (cost optimization)
- No deletion protection
- 7-day backup retention
- AdministratorAccess for ECS task role (for dev flexibility)

### Production Recommendations
- Multi-AZ RDS
- Multiple NAT Gateways
- Enable deletion protection
- Increase backup retention
- Restrict IAM permissions (least privilege)
- Enable WAF on ALB
- Use separate AWS account

## Cost Optimization

### Dev Environment
- Single NAT Gateway
- Single AZ RDS (db.t3.micro)
- Minimal ECS tasks (1-2)
- 7-day log retention
- Lifecycle policies on S3 (transition to IA/Glacier)

### Estimated Monthly Cost (Dev)
- VPC + NAT: ~$35
- RDS db.t3.micro: ~$15
- ECS Fargate (512MB, 0.25 vCPU): ~$10
- ALB: ~$20
- S3 (minimal usage): ~$5
- **Total: ~$85/month** (varies with usage)

## Troubleshooting

### Stack Deployment Fails

1. **Check CloudFormation events**:
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name PlatformNetworkingDev \
     --max-items 10
   ```

2. **Common issues**:
   - Insufficient IAM permissions
   - Service quotas exceeded
   - Invalid subnet configuration
   - KMS key permissions

### ECS Service Won't Start

1. **Check service events**:
   ```bash
   aws ecs describe-services \
     --cluster platform-dev \
     --services <service-name> \
     --query 'services[0].events'
   ```

2. **Check task logs**:
   ```bash
   aws logs tail /ecs/platform-dev --follow
   ```

3. **Common issues**:
   - Container image not found
   - Secrets Manager access denied
   - Security group rules too restrictive
   - Insufficient task resources

### Database Connection Issues

1. **Verify security group** allows traffic from ECS
2. **Check database endpoint** is correct
3. **Verify secrets** are accessible
4. **Test connection** from ECS task:
   ```bash
   aws ecs execute-command \
     --cluster platform-dev \
     --task <task-id> \
     --container BackendContainer \
     --command "psql -h <endpoint> -U postgres -d platform_dev"
   ```

## Cleanup

To destroy all stacks (⚠️ **WARNING**: This deletes all resources):

```bash
# Destroy in reverse order
cdk destroy PlatformObservabilityDev
cdk destroy PlatformComputeDev
cdk destroy PlatformDataDev  # Creates snapshot before deletion
cdk destroy PlatformSecurityDev
cdk destroy PlatformNetworkingDev
```

**Note**: 
- RDS creates a snapshot before deletion (RemovalPolicy.SNAPSHOT)
- S3 buckets are retained (RemovalPolicy.RETAIN)
- KMS keys are retained (RemovalPolicy.RETAIN)

## Next Steps

1. ✅ Deploy infrastructure stacks
2. ⬜ Enable PostGIS extension
3. ⬜ Build and push container image to ECR
4. ⬜ Update ECS service with actual image
5. ⬜ Configure database migrations in CI/CD
6. ⬜ Set up HTTPS certificate for ALB
7. ⬜ Configure WAF rules
8. ⬜ Set up deployment notifications
