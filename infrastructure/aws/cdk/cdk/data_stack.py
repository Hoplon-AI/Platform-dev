"""
Data stack: S3 buckets and RDS PostgreSQL with PostGIS.
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
    aws_lambda as lambda_,
    aws_s3_notifications as s3n,
    aws_logs as logs,
    RemovalPolicy,
    Tags,
    Duration,
)
try:
    import aws_cdk.aws_lambda_python_alpha as lambda_python
except ImportError:
    # Fallback: use standard Lambda with Code.from_asset if alpha package not available
    lambda_python = None
from constructs import Construct
import os


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
        bronze_bucket = s3.Bucket(
            self,
            "BronzeBucket",
            bucket_name=f"platform-bronze-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.KMS,
            encryption_key=s3_key,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,  # Don't delete data
            auto_delete_objects=False,
            # Enable EventBridge notifications for Step Functions
            event_bridge_enabled=True,
            # Lifecycle rules for cost optimization
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(90),
                        )
                    ],
                ),
                s3.LifecycleRule(
                    id="TransitionToGlacier",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(180),
                        )
                    ],
                ),
            ],
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
        processed_bucket = s3.Bucket(
            self,
            "ProcessedBucket",
            bucket_name=f"platform-processed-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.KMS,
            encryption_key=s3_key,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            auto_delete_objects=False,
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

        # RDS PostgreSQL Instance with PostGIS
        # Using db.t3.micro for dev (upgrade for prod)
        database = rds.DatabaseInstance(
            self,
            "PlatformDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_9
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=database_subnets),
            subnet_group=db_subnet_group,
            security_groups=[db_security_group],
            credentials=rds.Credentials.from_secret(db_secret),
            database_name="platform_dev",
            allocated_storage=20,  # GB, increase for prod
            max_allocated_storage=100,  # Auto-scaling
            storage_encrypted=True,
            storage_encryption_key=rds_key,
            backup_retention=Duration.days(7),  # 7 days for dev
            delete_automated_backups=True,  # For dev cost optimization
            deletion_protection=False,  # Enable for prod
            multi_az=False,  # Single AZ for dev, enable for prod
            publicly_accessible=False,  # Never expose database
            enable_performance_insights=True,
            performance_insight_retention=rds.PerformanceInsightRetention.DEFAULT,
            removal_policy=RemovalPolicy.SNAPSHOT,  # Create snapshot on delete
        )

        # PostGIS Extension Setup
        # PostGIS needs to be enabled after database creation
        # Options:
        # 1. Manual: Connect to DB and run: CREATE EXTENSION IF NOT EXISTS postgis;
        # 2. Via Lambda: Use postgis_setup.py helper (requires psycopg2 layer)
        # 3. Via RDS parameter group: Set shared_preload_libraries (requires DB restart)
        # 
        # For now, PostGIS must be enabled manually after stack deployment:
        # psql -h <endpoint> -U postgres -d platform_dev -c "CREATE EXTENSION IF NOT EXISTS postgis;"

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

        # Lambda function for ingestion pipeline
        # This Lambda processes files uploaded to S3 and extracts data
        # Calculate absolute path to workers directory
        # From infrastructure/aws/cdk/cdk/data_stack.py to backend/workers/
        # Go up 4 levels: cdk -> aws -> infrastructure -> Platform-dev (project root)
        current_file = os.path.abspath(__file__)  # infrastructure/aws/cdk/cdk/data_stack.py
        project_root = os.path.join(os.path.dirname(current_file), "../../../..")  # Go to project root (4 levels up)
        workers_dir = os.path.join(project_root, "backend", "workers")
        workers_dir = os.path.normpath(workers_dir)  # Normalize path
        
        # Use standard Lambda Function (avoids Docker build issues with PythonFunction)
        # Dependencies should be packaged separately or use Lambda layers
        ingestion_lambda = lambda_.Function(
            self,
            "IngestionLambda",
            function_name="platform-dev-ingestion-processor",
            code=lambda_.Code.from_asset(workers_dir),
            handler="stepfn_ingestion_worker.handler",
            runtime=lambda_.Runtime.PYTHON_3_11,  # Use 3.11 for better compatibility
            timeout=Duration.minutes(15),  # PDF processing can take time
            memory_size=1024,  # 1 GB for PDF processing
            environment={
                "DATABASE_SECRET_ARN": db_secret.secret_arn,
                "S3_BUCKET_NAME": bronze_bucket.bucket_name,
            },
            vpc=vpc if private_subnets else None,
            vpc_subnets=ec2.SubnetSelection(subnets=private_subnets) if private_subnets else None,
            security_groups=[db_security_group] if private_subnets else None,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Grant Lambda permissions
        # S3 read/write access
        bronze_bucket.grant_read(ingestion_lambda)
        bronze_bucket.grant_write(ingestion_lambda)
        
        # Secrets Manager access
        db_secret.grant_read(ingestion_lambda)
        
        # KMS decrypt for S3 and Secrets Manager
        s3_key.grant_decrypt(ingestion_lambda)
        secrets_key.grant_decrypt(ingestion_lambda)

        # Configure S3 bucket notification to trigger Lambda
        # Note: S3 notifications can't filter for keys containing "/file=" in the middle,
        # so we trigger on all object creations. The Lambda handler already filters out
        # sidecar files (manifest.json, metadata.json, extraction.json, etc.) and
        # non-source files (keys without "/file=").
        bronze_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(ingestion_lambda),
        )

        # Store references
        self.bronze_bucket = bronze_bucket
        self.processed_bucket = processed_bucket
        self.database = database
        self.database_security_group = db_security_group
        self.db_secret = db_secret
        self.secrets_key = secrets_key
        self.ingestion_lambda = ingestion_lambda

        # Outputs
        CfnOutput(
            self,
            "BronzeBucketName",
            value=bronze_bucket.bucket_name,
            description="S3 bucket for Bronze layer",
            export_name=f"{self.stack_name}-BronzeBucketName",
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
            value=database.instance_endpoint.hostname,
            description="RDS PostgreSQL endpoint",
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
            value=str(database.instance_endpoint.port),
            description="RDS PostgreSQL port",
            export_name=f"{self.stack_name}-DatabasePort",
        )

        CfnOutput(
            self,
            "DatabaseSecurityGroupId",
            value=db_security_group.security_group_id,
            description="Database security group ID",
            export_name=f"{self.stack_name}-DatabaseSecurityGroupId",
        )

        CfnOutput(
            self,
            "IngestionLambdaArn",
            value=ingestion_lambda.function_arn,
            description="ARN of ingestion pipeline Lambda function",
            export_name=f"{self.stack_name}-IngestionLambdaArn",
        )

        CfnOutput(
            self,
            "IngestionLambdaName",
            value=ingestion_lambda.function_name,
            description="Name of ingestion pipeline Lambda function",
            export_name=f"{self.stack_name}-IngestionLambdaName",
        )
