# Platform Infrastructure CDK

AWS CDK infrastructure for the Platform application, deployed to **dev** environment in **eu-west-1**.

## Architecture

The infrastructure is organized into 5 separate stacks following AWS Well-Architected Framework principles:

```
┌─────────────────────────────────────────────────────────┐
│                  Networking Stack                       │
│  VPC, Subnets, VPC Endpoints, NAT Gateway              │
└─────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
┌───────▼────────┐            ┌──────────▼──────────┐
│ Security Stack│            │     Data Stack      │
│ KMS, IAM,     │            │  S3, RDS Postgres   │
│ Secrets Mgr   │            │   with PostGIS      │
└───────┬────────┘            └──────────┬──────────┘
        │                               │
        └───────────────┬───────────────┘
                        │
              ┌─────────▼──────────┐
              │   Compute Stack    │
              │ ECS Fargate + ALB  │
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────────┐
              │ Observability Stack    │
              │ CloudWatch Alarms      │
              └────────────────────────┘
```

## Stack Details

### 1. Networking Stack (`PlatformNetworkingDev`)
- **VPC**: 10.0.0.0/16 with 2 AZs
- **Subnets**: 
  - Public (ALB, NAT)
  - Private with Egress (ECS tasks)
  - Isolated (RDS database)
- **VPC Endpoints**: S3, ECR, CloudWatch, Secrets Manager
- **NAT Gateway**: Single gateway for cost optimization (dev)

### 2. Security Stack (`PlatformSecurityDev`)
- **KMS Keys**: Separate keys for S3, RDS, Secrets Manager
- **IAM Roles**: 
  - ECS Task Execution Role
  - ECS Task Role (application permissions)
- **Secrets Manager**: Database credentials secret

### 3. Data Stack (`PlatformDataDev`)
- **S3 Buckets**:
  - `platform-bronze-{account}-{region}`: Raw data (Bronze layer)
  - `platform-processed-{account}-{region}`: Processed data
- **RDS PostgreSQL 16.9**:
  - Instance: db.t3.micro (dev)
  - Storage: 20GB (auto-scaling to 100GB)
  - Backups: 7-day retention
  - Encryption: KMS
  - **PostGIS**: Must be enabled manually after deployment

### 4. Compute Stack (`PlatformComputeDev`)
- **ECS Fargate Cluster**: `platform-dev`
- **Application Load Balancer**: Internet-facing, HTTP (port 80)
- **ECS Service**:
  - Task: 512MB memory, 0.25 vCPU
  - Desired count: 1 (auto-scales 1-2)
  - Container: Placeholder nginx (update with FastAPI image)
- **Auto Scaling**: CPU-based (70% threshold)

### 5. Observability Stack (`PlatformObservabilityDev`)
- **CloudWatch Alarms**:
  - ECS: CPU, Memory utilization
  - ALB: 5xx errors, response time
  - RDS: CPU, connections, storage
- **CloudWatch Dashboard**: Platform metrics overview
- **SNS Topic**: Alarm notifications (optional)

## Quick Start

```bash
# 1. Install dependencies
cd infrastructure/aws/cdk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure AWS
export AWS_PROFILE=dev-deployer
export CDK_DEFAULT_ACCOUNT=025215344919
export CDK_DEFAULT_REGION=eu-west-1

# 3. Bootstrap (if not done)
cdk bootstrap aws://025215344919/eu-west-1

# 4. Synthesize
cdk synth

# 5. Deploy
cdk deploy --all
```

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

## Security Features

✅ **Encryption at Rest**:
- S3: KMS encryption
- RDS: KMS encryption
- Secrets Manager: KMS encryption

✅ **Encryption in Transit**:
- ALB → ECS: Internal VPC traffic
- Database: TLS/SSL

✅ **Network Security**:
- Database in isolated subnets (no internet access)
- ECS tasks in private subnets
- Security groups with minimal rules
- VPC endpoints to avoid NAT costs

✅ **IAM Security**:
- Least privilege roles
- No long-lived access keys for CI/CD (OIDC)
- Separate execution and task roles

✅ **Secrets Management**:
- Database credentials in Secrets Manager
- Automatic rotation support
- Encrypted with KMS

## Cost Optimization (Dev)

- Single NAT Gateway
- Single AZ RDS
- Minimal ECS resources
- S3 lifecycle policies (IA/Glacier)
- Short log retention (7 days)

**Estimated Monthly Cost**: ~$85 (varies with usage)

## CI/CD Integration

GitHub Actions workflow (`.github/workflows/cdk-deploy-dev.yml`) uses OIDC to:
- Synthesize CDK templates
- Show diffs on PRs
- Deploy to dev on `main` branch (currently disabled)

See [docs/CI_CD_SETUP.md](../../docs/CI_CD_SETUP.md) for details.

## PostGIS Setup

After RDS deployment, enable PostGIS:

```bash
# Get endpoint
DB_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name PlatformDataDev \
  --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
  --output text)

# Get password from Secrets Manager
DB_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id PlatformSecurityDev-DatabaseSecret \
  --query 'SecretString' \
  --output text | jq -r '.password')

# Enable PostGIS
psql -h $DB_ENDPOINT -U postgres -d platform_dev \
  -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

## Next Steps

1. ✅ Infrastructure stacks created
2. ⬜ Deploy stacks to AWS
3. ⬜ Enable PostGIS extension
4. ⬜ Build and push FastAPI container image
5. ⬜ Update ECS service with actual image
6. ⬜ Configure HTTPS certificate for ALB
7. ⬜ Set up database migrations in CI/CD
8. ⬜ Configure WAF rules for ALB
9. ⬜ Set up staging environment
10. ⬜ Prepare production environment

## Files

- `app.py`: CDK app entry point, instantiates all stacks
- `cdk/networking_stack.py`: VPC and networking
- `cdk/security_stack.py`: KMS, IAM, Secrets Manager
- `cdk/data_stack.py`: S3 and RDS
- `cdk/compute_stack.py`: ECS Fargate and ALB
- `cdk/observability_stack.py`: CloudWatch alarms and dashboards
- `cdk/postgis_setup.py`: Helper for PostGIS setup (optional)
- `requirements.txt`: Python dependencies
- `cdk.json`: CDK configuration

## References

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Platform Architecture Rules](../.cursor/rules.md)
