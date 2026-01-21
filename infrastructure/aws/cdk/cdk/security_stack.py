"""
Security stack: KMS keys, IAM roles, and Secrets Manager.
"""
from aws_cdk import (
    Stack,
    CfnOutput,
    aws_kms as kms,
    Tags,
    RemovalPolicy,
)
from constructs import Construct


class SecurityStack(Stack):
    """Security infrastructure: KMS, IAM, Secrets Manager."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # KMS Key for S3 encryption
        s3_key = kms.Key(
            self,
            "S3EncryptionKey",
            description="KMS key for S3 bucket encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,  # Don't delete keys
        )

        # KMS Key for RDS encryption
        rds_key = kms.Key(
            self,
            "RDSEncryptionKey",
            description="KMS key for RDS database encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Tag KMS keys
        Tags.of(s3_key).add("app", "platform")
        Tags.of(s3_key).add("env", "dev")
        Tags.of(s3_key).add("purpose", "s3-encryption")
        Tags.of(rds_key).add("app", "platform")
        Tags.of(rds_key).add("env", "dev")
        Tags.of(rds_key).add("purpose", "rds-encryption")
        # Store references
        self.s3_key = s3_key
        self.rds_key = rds_key

        # Outputs
        CfnOutput(
            self,
            "S3KmsKeyId",
            value=s3_key.key_id,
            description="KMS key ID for S3 encryption",
            export_name=f"{self.stack_name}-S3KmsKeyId",
        )

        CfnOutput(
            self,
            "RDSKmsKeyId",
            value=rds_key.key_id,
            description="KMS key ID for RDS encryption",
            export_name=f"{self.stack_name}-RDSKmsKeyId",
        )

        # Note: Secrets Manager encryption key is created in DataStack to avoid cross-stack cycles.
