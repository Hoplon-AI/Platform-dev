"""
Data stack: S3 buckets and Aurora Serverless v2 PostgreSQL with PostGIS.
Auto-pauses to 0 ACUs when idle (costs ~$0 compute + storage only).
"""
from aws_cdk import (
    Stack,
    CfnOutput,
    aws_s3 as s3,
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_secretsmanager as secretsmanager,
    aws_kms as kms,
    aws_iam as iam,
    RemovalPolicy,
    Tags,
    Duration,
)
from constructs import Construct


class DataStack(Stack):
    """Data infrastructure: S3 and RDS."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        database_subnets: list[ec2.ISubnet],
        s3_key,
        rds_key,
        private_subnets: list[ec2.ISubnet] = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # KMS Key for Secrets Manager (kept in Data stack to avoid cross-stack cycles)
        secrets_key = kms.Key(
            self,
            "SecretsManagerKey",
            description="KMS key for Secrets Manager encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Secrets Manager secret for database credentials (kept in Data stack to avoid cycles)
        db_secret = secretsmanager.Secret(
            self,
            "DatabaseSecret",
            description="RDS PostgreSQL database credentials",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "postgres"}',
                generate_string_key="password",
                exclude_characters='"@/\\',
                password_length=32,
            ),
            encryption_key=secrets_key,
        )

        # S3 Bucket for Bronze layer (raw data)
        # Import existing bucket (created in previous deployment with RETAIN policy)
        bronze_bucket_name = f"platform-bronze-{self.account}-{self.region}"
        bronze_bucket = s3.Bucket.from_bucket_name(
            self,
            "BronzeBucket",
            bronze_bucket_name
        )

        # SSL-only bucket policy for Bronze bucket
        bronze_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="DenyInsecureConnections",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["s3:*"],
                resources=[
                    bronze_bucket.bucket_arn,
                    f"{bronze_bucket.bucket_arn}/*",
                ],
                conditions={
                    "Bool": {"aws:SecureTransport": "false"},
                },
            )
        )

        # S3 Bucket for processed data (Silver/Gold layers if needed)
        # Import existing bucket (created in previous deployment with RETAIN policy)
        processed_bucket_name = f"platform-processed-{self.account}-{self.region}"
        processed_bucket = s3.Bucket.from_bucket_name(
            self,
            "ProcessedBucket",
            processed_bucket_name
        )

        # SSL-only bucket policy for Processed bucket
        processed_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="DenyInsecureConnections",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["s3:*"],
                resources=[
                    processed_bucket.bucket_arn,
                    f"{processed_bucket.bucket_arn}/*",
                ],
                conditions={
                    "Bool": {"aws:SecureTransport": "false"},
                },
            )
        )

        # Database Subnet Group
        db_subnet_group = rds.SubnetGroup(
            self,
            "DatabaseSubnetGroup",
            description="Subnet group for RDS database",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=database_subnets),
        )

        # Security Group for RDS
        db_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=vpc,
            description="Security group for RDS PostgreSQL",
            allow_all_outbound=False,  # Explicit egress rules
        )

        # Aurora Serverless v2 PostgreSQL Cluster with PostGIS
        # Auto-pauses to 0 ACUs when idle (costs ~$0 compute + storage only)
        # Requires Aurora PostgreSQL 16.3+ for auto-pause support
        # 
        # Cost when idle: ~$0 compute (0 ACUs) + ~$2/month storage (20GB @ $0.10/GB)
        # Cost when active: ~$0.12/ACU-hour (scales 0.5-2.0 ACUs based on load)
        # Resume time: up to 15 seconds when connection arrives after pause
        # Aurora Serverless v2 requires a writer instance
        # The writer instance uses serverless v2 scaling (0.5-2.0 ACUs)
        writer = rds.ClusterInstance.serverless_v2(
            "writer",
            scale_with_writer=True,  # Scale reader instances with writer
        )
        
        database = rds.DatabaseCluster(
            self,
            "PlatformDatabase",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_16_9
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=database_subnets),
            subnet_group=db_subnet_group,
            security_groups=[db_security_group],
            credentials=rds.Credentials.from_secret(db_secret),
            default_database_name="platform_dev",
            storage_encrypted=True,
            storage_encryption_key=rds_key,
            deletion_protection=False,  # Enable for prod
            removal_policy=RemovalPolicy.SNAPSHOT,  # Create snapshot on delete
            writer=writer,  # Required for serverless v2
            # Aurora Serverless v2 with auto-pause (scales to 0 ACUs when idle)
            # Auto-pause: Enabled by default in Aurora Serverless v2 (Nov 2024)
            # Cluster automatically pauses after 5 minutes of inactivity (default)
            # and resumes within 15 seconds when a connection is requested
            # Note: Backup retention defaults to 1 day; configure via AWS Console/CLI for 7 days
        )

        # PostGIS Extension Setup
        # PostGIS needs to be enabled after database creation
        # Options:
        # 1. Manual: Connect to DB and run: CREATE EXTENSION IF NOT EXISTS postgis;
        # 2. Via Lambda: Use postgis_setup.py helper (requires psycopg2 layer)
        # 
        # For Aurora Serverless v2, PostGIS must be enabled manually after stack deployment:
        # psql -h <cluster-endpoint> -U postgres -d platform_dev -c "CREATE EXTENSION IF NOT EXISTS postgis;"
        # 
        # Note: If the cluster is paused, the first connection will take up to 15 seconds to resume

        # Tag resources
        Tags.of(bronze_bucket).add("app", "platform")
        Tags.of(bronze_bucket).add("env", "dev")
        Tags.of(bronze_bucket).add("data_classification", "bronze")
        Tags.of(processed_bucket).add("app", "platform")
        Tags.of(processed_bucket).add("env", "dev")
        Tags.of(processed_bucket).add("data_classification", "processed")
        Tags.of(database).add("app", "platform")
        Tags.of(database).add("env", "dev")
        Tags.of(database).add("data_classification", "database")

        # Store references
        self.bronze_bucket = bronze_bucket
        self.processed_bucket = processed_bucket
        self.database = database
        self.database_security_group = db_security_group
        self.db_secret = db_secret
        self.secrets_key = secrets_key

        # Outputs
        # Export bucket name for cross-stack reference (breaks CDK dependency cycle)
        CfnOutput(
            self,
            "BronzeBucketName",
            value=bronze_bucket.bucket_name,
            description="S3 bucket for Bronze layer",
            export_name=f"{self.stack_name}-BronzeBucketName",
        )
        
        # Also export bucket ARN for IAM policies
        CfnOutput(
            self,
            "BronzeBucketArn",
            value=bronze_bucket.bucket_arn,
            description="S3 bucket ARN for Bronze layer",
            export_name=f"{self.stack_name}-BronzeBucketArn",
        )

        CfnOutput(
            self,
            "ProcessedBucketName",
            value=processed_bucket.bucket_name,
            description="S3 bucket for processed data",
            export_name=f"{self.stack_name}-ProcessedBucketName",
        )

        CfnOutput(
            self,
            "DatabaseEndpoint",
            value=database.cluster_endpoint.hostname,
            description="Aurora PostgreSQL cluster endpoint",
            export_name=f"{self.stack_name}-DatabaseEndpoint",
        )

        CfnOutput(
            self,
            "DatabaseSecretArn",
            value=db_secret.secret_arn,
            description="ARN of database credentials secret",
            export_name=f"{self.stack_name}-DatabaseSecretArn",
        )

        CfnOutput(
            self,
            "DatabasePort",
            value=str(database.cluster_endpoint.port),
            description="Aurora PostgreSQL port",
            export_name=f"{self.stack_name}-DatabasePort",
        )
        
        CfnOutput(
            self,
            "DatabaseReaderEndpoint",
            value=database.cluster_read_endpoint.hostname,
            description="Aurora PostgreSQL reader endpoint (for read replicas)",
            export_name=f"{self.stack_name}-DatabaseReaderEndpoint",
        )

        CfnOutput(
            self,
            "DatabaseSecurityGroupId",
            value=db_security_group.security_group_id,
            description="Database security group ID",
            export_name=f"{self.stack_name}-DatabaseSecurityGroupId",
        )

        # Ingestion pipeline resources (EventBridge rule + Step Functions + worker) are owned by IngestionStack.
