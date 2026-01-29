# Circular Dependency Workaround

## Issue

CDK reports a false positive circular dependency error:
```
ValidationError: 'PlatformDataDev' depends on 'PlatformIngestionDev' 
(PlatformDataDev -> PlatformIngestionDev/SilverProcessorLambda/ServiceRole/Resource.Arn). 
Adding this dependency (PlatformIngestionDev -> PlatformDataDev/BronzeBucket/Resource.Ref) 
would create a cyclic reference.
```

## Root Cause

This is a known CDK synthesis-time false positive. DataStack does NOT actually reference IngestionStack. The actual dependency is one-way: IngestionStack → DataStack (for the bronze_bucket).

The error occurs because:
1. IngestionStack uses `bronze_bucket.bucket_name` (creates CloudFormation reference to DataStack)
2. CDK's dependency analyzer incorrectly detects a reverse dependency

## Workaround

Deploy stacks in order, ignoring the synthesis error:

```bash
# 1. Deploy prerequisites
cdk deploy PlatformNetworkingDev PlatformSecurityDev

# 2. Deploy DataStack (this will show the error but can be ignored if stacks don't exist)
cdk deploy PlatformDataDev

# 3. Deploy IngestionStack (after DataStack exists)
cdk deploy PlatformIngestionDev

# 4. Continue with other stacks
cdk deploy PlatformComputeDev PlatformObservabilityDev
```

## Alternative: Use CloudFormation Exports/Imports

If the error persists, we can refactor to use CloudFormation exports:
1. DataStack exports bucket name as a CloudFormation export
2. IngestionStack imports it using `Fn::ImportValue`
3. This breaks the CDK dependency chain

## Status

- Current: Error occurs during synthesis
- Impact: Cannot use `cdk deploy --all` or `cdk synth`
- Workaround: Deploy stacks individually in order
- Long-term: Consider refactoring to use exports/imports or pass bucket name as string
