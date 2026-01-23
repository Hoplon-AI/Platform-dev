# CI/CD Setup with GitHub Actions OIDC

This document describes the CI/CD pipeline setup using GitHub Actions with AWS OIDC authentication.

## Overview

- **Repository**: `Hoplon-AI/Platform-dev`
- **Branch**: `main` → deploys to **dev** environment
- **Region**: `eu-west-1`
- **Account**: `025215344919`
- **Authentication**: OIDC (no long-lived access keys)

## AWS Resources Created

### OIDC Provider
- **ARN**: `arn:aws:iam::025215344919:oidc-provider/token.actions.githubusercontent.com`
- **URL**: `https://token.actions.githubusercontent.com`
- **Thumbprint**: `6938fd4d98bab03faadb97b34396831e3780aea1`

### IAM Role
- **Role Name**: `github-actions-platform-dev`
- **ARN**: `arn:aws:iam::025215344919:role/github-actions-platform-dev`
- **Trust Policy**: Allows GitHub Actions from `Hoplon-AI/Platform-dev` repository, `main` branch only
- **Permissions**: `AdministratorAccess` (for dev environment)

### Trust Policy Details

The role can only be assumed by:
- **Repository**: `Hoplon-AI/Platform-dev`
- **Branch**: `refs/heads/main`
- **Audience**: `sts.amazonaws.com`

## GitHub Actions Workflow

### Workflow File
`.github/workflows/cdk-deploy-dev.yml`

### Workflow Jobs

1. **lint-and-test**: Runs linting and tests
2. **cdk-synth**: Synthesizes CDK templates
3. **cdk-diff**: Shows changes (PR only)
4. **cdk-deploy**: Deploys to dev (main branch only)

### Triggers

- **Push to main**: Runs all jobs, deploys to dev
- **Pull Request**: Runs lint, synth, and diff (no deploy)
- **Manual**: Can be triggered via `workflow_dispatch`

## Setup Verification

### Test OIDC Connection

1. Push a commit to `main` branch
2. Check GitHub Actions tab for workflow run
3. Verify `cdk-synth` job succeeds
4. Check AWS CloudTrail for `AssumeRoleWithWebIdentity` events

### Verify Role Assumption

```bash
# Check CloudTrail logs for successful role assumption
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity \
  --region eu-west-1 \
  --max-results 10
```

## Security Best Practices

### ✅ Implemented
- OIDC authentication (no access keys)
- Branch restriction (main only)
- Repository restriction (Hoplon-AI/Platform-dev only)
- Least privilege principle (can be tightened further)

### 🔒 Recommendations for Production

When adding production environment:

1. **Create separate role** for production:
   ```bash
   aws iam create-role --role-name github-actions-platform-prod \
     --assume-role-policy-document file://prod-trust-policy.json
   ```

2. **Add manual approval** for production deployments:
   ```yaml
   # In workflow
   environment:
     name: production
     protection_rules:
       - type: required_reviewers
         reviewers: ["admin1", "admin2"]
   ```

3. **Restrict permissions** for production role:
   - Remove `AdministratorAccess`
   - Create custom policy with only required permissions
   - Use separate KMS keys for production

4. **Add deployment notifications**:
   - Slack/email on deployment success/failure
   - CloudWatch alarms for failed deployments

## Troubleshooting

### "Access Denied" errors

**Issue**: GitHub Actions can't assume role
- **Check**: Role trust policy matches repository/branch
- **Verify**: OIDC provider exists and thumbprint is correct
- **Test**: Manual role assumption with AWS CLI

### CDK Bootstrap Required

If you see "Environment needs to be bootstrapped":
```bash
# Bootstrap CDK in dev account
export AWS_PROFILE=dev-deployer
cd infrastructure/aws/cdk
cdk bootstrap aws://025215344919/eu-west-1
```

### Workflow Fails on CDK Deploy

**Check**:
1. CDK app is properly configured in `infrastructure/aws/cdk/`
2. Stack name matches in `app.py`
3. Required AWS resources are available
4. IAM role has necessary permissions

## Adding New Environments

### Staging Environment

1. Create new OIDC role:
   ```bash
   aws iam create-role --role-name github-actions-platform-staging \
     --assume-role-policy-document file://staging-trust-policy.json
   ```

2. Update workflow to add staging job:
   ```yaml
   cdk-deploy-staging:
     if: github.ref == 'refs/heads/develop'
     environment:
       name: staging
   ```

3. Add staging configuration to CDK app

### Production Environment

1. Create production role with restricted permissions
2. Add manual approval gate in workflow
3. Use separate AWS account (recommended)
4. Enable deployment protection rules

## Monitoring

### CloudWatch Metrics
- Monitor deployment success/failure rates
- Track deployment duration
- Set up alarms for failed deployments

### GitHub Actions Insights
- View workflow run history
- Monitor job success rates
- Track deployment frequency

## Rollback Procedure

If a deployment fails or causes issues:

1. **Via CDK**:
   ```bash
   cdk destroy PlatformDevStack
   ```

2. **Via CloudFormation Console**:
   - Go to CloudFormation in AWS Console
   - Select stack
   - Delete stack

3. **Via GitHub Actions**:
   - Re-run previous successful workflow
   - Or manually trigger rollback workflow

## Next Steps

- [X] Add CDK stack tests
- [X] Add CloudWatch dashboards
- [ ] Set up staging environment (optional)
- [ ] Create production environment with approval gates
- [ ] Tighten IAM permissions (remove AdministratorAccess, use least privilege)

## References

- [GitHub Actions OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
