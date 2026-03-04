"""
Ingestion stack: EventBridge rule + Step Functions + Lambda worker.

AWS-first pattern:
S3 (EventBridge enabled) -> EventBridge rule (filter */file=*) -> Step Functions -> Lambda worker
"""

from __future__ import annotations

import os
from typing import Optional, Sequence

from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    BundlingOptions,
    Fn,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as lambda_,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_secretsmanager as secretsmanager,
    aws_kms as kms,
    aws_logs as logs,
    aws_iam as iam,
)
from constructs import Construct


class IngestionStack(Stack):
    """
    Ingestion infrastructure for async processing.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bronze_bucket: s3.IBucket,
        vpc: ec2.IVpc,
        private_subnets: Sequence[ec2.ISubnet],
        database_security_group: ec2.ISecurityGroup,
        db_secret: secretsmanager.ISecret,
        database_host: str,
        database_port: int,
        s3_key: kms.IKey,
        secrets_key: kms.IKey,
        state_machine_name: str = "platform-dev-pdf-ingestion",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Store bucket reference (needed for EventBridge rule target)
        self._bronze_bucket = bronze_bucket
        
        # Use CloudFormation import to break CDK dependency cycle
        # Import bucket name from DataStack export instead of direct reference
        data_stack_name = f"{scope.node.try_get_context('@aws-cdk/core:stackId') or 'PlatformDataDev'}"
        # For now, still use direct reference but extract name early
        # TODO: Refactor to use Fn.importValue when DataStack is deployed
        self._bucket_name = bronze_bucket.bucket_name

        # Resolve repo root to package Lambda code from project root
        current_file = os.path.abspath(__file__)  # infrastructure/aws/cdk/cdk/ingestion_stack.py
        project_root = os.path.normpath(os.path.join(os.path.dirname(current_file), "../../../.."))

        # Layer with runtime deps for the ingestion worker (asyncpg + pdfplumber)
        layer_dir = os.path.join(os.path.dirname(current_file), "..", "lambda_layers", "ingestion_worker")
        layer_dir = os.path.normpath(layer_dir)

        # Layer dependencies bundling requires Docker (to build manylinux wheels for Lambda).
        # For local/unit tests (no Docker), set CDK_USE_DOCKER_BUNDLING=false (default).
        use_docker_bundling = os.getenv("CDK_USE_DOCKER_BUNDLING", "false").lower() == "true"

        worker_layer_code = (
            lambda_.Code.from_asset(
                layer_dir,
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash",
                        "-lc",
                        "pip install -r requirements.txt -t /asset-output/python",
                    ],
                ),
            )
            if use_docker_bundling
            else lambda_.Code.from_asset(layer_dir)
        )

        worker_deps_layer = lambda_.LayerVersion(
            self,
            "IngestionWorkerDeps",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.ARM_64],
            code=worker_layer_code,
            description=(
                "Dependencies for ingestion worker (asyncpg, pdfplumber, etc.). "
                "Set CDK_USE_DOCKER_BUNDLING=true to build this layer."
            ),
        )

        # Lambda security group: allows outbound HTTPS (AWS services) and DB access
        lambda_security_group = ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=vpc,
            description="Security group for ingestion Lambda functions",
            allow_all_outbound=True,  # Allow outbound to AWS services (S3, Secrets Manager, Bedrock)
        )
        # Allow Lambda to connect to database
        lambda_security_group.connections.allow_to(
            database_security_group,
            ec2.Port.tcp(5432),
            "Allow PostgreSQL access from Lambda",
        )

        # Log group for ingestion worker Lambda
        ingestion_lambda_log_group = logs.LogGroup(
            self,
            "IngestionWorkerLambdaLogs",
            log_group_name="/aws/lambda/platform-dev-ingestion-worker",
            retention=logs.RetentionDays.ONE_WEEK,
        )

        # Lambda worker
        ingestion_lambda = lambda_.Function(
            self,
            "IngestionWorkerLambda",
            function_name="platform-dev-ingestion-worker",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="backend.workers.stepfn_ingestion_worker.handler",
            code=lambda_.Code.from_asset(
                project_root,
                exclude=[
                    ".git",
                    ".git/**",
                    "**/__pycache__",
                    "**/__pycache__/**",
                    "**/node_modules",
                    "**/node_modules/**",
                    "frontend",
                    "frontend/**",
                    "docs",
                    "docs/**",
                    "data",
                    "data/**",
                    "dbt",
                    "dbt/**",
                    "infrastructure/aws",
                    "infrastructure/aws/**",
                    "scripts",
                    "scripts/**",
                    "tests",
                    "tests/**",
                    "venv",
                    "venv/**",
                    "venv_local",
                    "venv_local/**",
                    "*.sqlite",
                    "*.log",
                    ".DS_Store",
                    ".env*",
                ],
            ),
            memory_size=1536,
            timeout=Duration.minutes(15),
            layers=[worker_deps_layer],
            environment={
                # RDS endpoint details (host/port are not in the secret)
                "DB_HOST": database_host,
                "DB_PORT": str(database_port),
                "DB_NAME": "platform_dev",
                # Worker will read Secrets Manager for user/password
                "DATABASE_SECRET_ARN": db_secret.secret_arn,
                # Optional: let worker know bucket, though it is passed in the event
                "S3_BUCKET_NAME": self._bucket_name,
                # Keep max attempts consistent across infra and app logic
                "PDF_PROCESSING_MAX_ATTEMPTS": "5",
                # Agentic extraction (Bedrock/Claude): enabled by default
                "USE_AGENTIC_EXTRACTION": "true",
                "BEDROCK_MODEL_ID": "mistral.mistral-large-2402-v1:0",
                # Path to schemas for agentic feature definitions
                "SCHEMAS_PATH": "/var/task/schemas",
            },
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=list(private_subnets)),
            security_groups=[lambda_security_group],
            log_group=ingestion_lambda_log_group,
        )

        # Bedrock: invoke models for agentic feature extraction
        region = self.region or "eu-west-1"
        ingestion_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{region}::foundation-model/anthropic.claude-*",
                    f"arn:aws:bedrock:{region}::foundation-model/amazon.nova-*",
                    f"arn:aws:bedrock:{region}::foundation-model/mistral.*",
                ],
            )
        )

        # Permissions (avoid cross-stack resource policy mutations to prevent cycles)
        # S3: read/write objects + list bucket
        # Use bucket name to construct ARN to avoid CDK cross-stack reference issues
        bucket_arn_ingestion = f"arn:aws:s3:::{self._bucket_name}"
        ingestion_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=[
                    bucket_arn_ingestion,
                    f"{bucket_arn_ingestion}/*",
                ],
            )
        )

        # Secrets Manager: read DB creds
        ingestion_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
                resources=[db_secret.secret_arn],
            )
        )

        # KMS (S3 CMK + Secrets CMK). Assumes key policies allow IAM in-account usage.
        # GenerateDataKey needed for writing to encrypted S3 bucket
        ingestion_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"],
                resources=[s3_key.key_arn, secrets_key.key_arn],
            )
        )

        # Log group for silver processor Lambda
        silver_processor_log_group = logs.LogGroup(
            self,
            "SilverProcessorLambdaLogs",
            log_group_name="/aws/lambda/platform-dev-silver-processor",
            retention=logs.RetentionDays.ONE_WEEK,
        )

        # Silver processor Lambda (writes features to normalized PG tables)
        silver_processor_lambda = lambda_.Function(
            self,
            "SilverProcessorLambda",
            function_name="platform-dev-silver-processor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="backend.workers.silver_processor.handler",
            code=lambda_.Code.from_asset(
                project_root,
                exclude=[
                    ".git",
                    ".git/**",
                    "**/__pycache__",
                    "**/__pycache__/**",
                    "**/node_modules",
                    "**/node_modules/**",
                    "frontend",
                    "frontend/**",
                    "docs",
                    "docs/**",
                    "data",
                    "data/**",
                    "dbt",
                    "dbt/**",
                    "infrastructure/aws",
                    "infrastructure/aws/**",
                    "scripts",
                    "scripts/**",
                    "tests",
                    "tests/**",
                    "venv",
                    "venv/**",
                    "venv_local",
                    "venv_local/**",
                    "*.sqlite",
                    "*.log",
                    ".DS_Store",
                    ".env*",
                ],
            ),
            memory_size=512,
            timeout=Duration.minutes(5),
            layers=[worker_deps_layer],  # Reuse same layer (asyncpg)
            environment={
                "DB_HOST": database_host,
                "DB_PORT": str(database_port),
                "DB_NAME": "platform_dev",
                "DATABASE_SECRET_ARN": db_secret.secret_arn,
                "S3_BUCKET_NAME": self._bucket_name,
            },
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=list(private_subnets)),
            security_groups=[lambda_security_group],
            log_group=silver_processor_log_group,
        )

        # Silver processor permissions
        # Use explicit IAM policies with bucket name to avoid cross-stack dependency cycles
        # Construct ARN from bucket name to avoid CDK cross-stack reference issues
        bucket_arn_silver = f"arn:aws:s3:::{self._bucket_name}"
        silver_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=[
                    bucket_arn_silver,
                    f"{bucket_arn_silver}/*",
                ],
            )
        )
        # Use explicit IAM policies instead of grant_* methods to avoid cross-stack
        # resource policy modifications that create circular dependencies
        silver_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
                resources=[db_secret.secret_arn],
            )
        )
        silver_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt", "kms:DescribeKey"],
                resources=[s3_key.key_arn, secrets_key.key_arn],
            )
        )

        # Step Functions: invoke extraction Lambda with retries
        invoke_worker = sfn_tasks.LambdaInvoke(
            self,
            "ProcessPdf",
            lambda_function=ingestion_lambda,
            payload=sfn.TaskInput.from_object(
                {
                    "bucket": sfn.JsonPath.string_at("$.bucket"),
                    "key": sfn.JsonPath.string_at("$.key"),
                    "execution_arn": sfn.JsonPath.string_at("$$.Execution.Id"),
                }
            ),
            result_path="$.worker",
            payload_response_only=True,  # Return Lambda response directly (no Payload wrapper)
        )

        invoke_worker.add_retry(
            errors=["States.ALL"],
            interval=Duration.seconds(5),
            backoff_rate=2.0,
            max_attempts=5,
        )

        # Step Functions: invoke Silver processor Lambda (after extraction completes)
        # Only process to Silver if extraction succeeded
        invoke_silver = sfn_tasks.LambdaInvoke(
            self,
            "ProcessToSilver",
            lambda_function=silver_processor_lambda,
            payload=sfn.TaskInput.from_object(
                {
                    "bucket": sfn.JsonPath.string_at("$.bucket"),
                    "key": sfn.JsonPath.string_at("$.worker.metadata.features_s3_key"),
                    "execution_arn": sfn.JsonPath.string_at("$$.Execution.Id"),
                }
            ),
            result_path="$.silver",
            payload_response_only=True,  # Return Lambda response directly (no Payload wrapper)
        )

        invoke_silver.add_retry(
            errors=["States.ALL"],
            interval=Duration.seconds(5),
            backoff_rate=2.0,
            max_attempts=3,
        )

        # Condition: only process to Silver if extraction completed successfully
        # Check if worker status is "completed" or "needs_review" (both mean extraction succeeded)
        silver_condition = sfn.Condition.or_(
            sfn.Condition.string_equals("$.worker.status", "completed"),
            sfn.Condition.string_equals("$.worker.status", "needs_review"),
        )

        # Chain: extraction -> (if success) silver processing
        definition = invoke_worker.next(
            sfn.Choice(self, "ExtractionSucceeded")
            .when(silver_condition, invoke_silver)
            .otherwise(sfn.Succeed(self, "ExtractionFailed"))
        )

        # Use a dedicated log group for the state machine (optional)
        state_machine_logs = logs.LogGroup(
            self,
            "PdfIngestionStateMachineLogs",
            log_group_name="/aws/vendedlogs/states/platform-dev-pdf-ingestion",
            retention=logs.RetentionDays.ONE_WEEK,
        )

        state_machine = sfn.StateMachine(
            self,
            "PdfIngestionStateMachine",
            state_machine_name=state_machine_name,
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(30),
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=state_machine_logs,
                level=sfn.LogLevel.ALL,
                include_execution_data=True,
            ),
        )

        # EventBridge rule: S3 object created events for source objects only (keys containing /file=)
        # Requires bucket event_bridge_enabled=True (set in DataStack).
        # Use bucket name string to avoid cross-stack reference issues
        rule = events.Rule(
            self,
            "BronzeSourceObjectCreatedRule",
            description="Start PDF ingestion state machine on source file PUT (keys containing /file=).",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [self._bucket_name]},
                    "object": {"key": [{"wildcard": "*/file=*"}]},
                },
            ),
        )

        rule.add_target(
            targets.SfnStateMachine(
                state_machine,
                input=events.RuleTargetInput.from_object(
                    {
                        "bucket": events.EventField.from_path("$.detail.bucket.name"),
                        "key": events.EventField.from_path("$.detail.object.key"),
                    }
                ),
            )
        )

        # Migration runner Lambda (for running database migrations)
        migration_runner_log_group = logs.LogGroup(
            self,
            "MigrationRunnerLambdaLogs",
            log_group_name="/aws/lambda/platform-dev-migration-runner",
            retention=logs.RetentionDays.ONE_WEEK,
        )

        migration_runner_lambda = lambda_.Function(
            self,
            "MigrationRunnerLambda",
            function_name="platform-dev-migration-runner",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="backend.workers.migration_runner.handler",
            code=lambda_.Code.from_asset(
                project_root,
                exclude=[
                    ".git",
                    ".git/**",
                    "**/__pycache__",
                    "**/__pycache__/**",
                    "**/node_modules",
                    "**/node_modules/**",
                    "frontend",
                    "frontend/**",
                    "docs",
                    "docs/**",
                    "data",
                    "data/**",
                    "dbt",
                    "dbt/**",
                    "infrastructure/aws",
                    "infrastructure/aws/**",
                    "scripts",
                    "scripts/**",
                    "tests",
                    "tests/**",
                    "venv",
                    "venv/**",
                    "venv_local",
                    "venv_local/**",
                    "*.sqlite",
                    "*.log",
                    ".DS_Store",
                    ".env*",
                ],
            ),
            memory_size=256,
            timeout=Duration.minutes(5),
            layers=[worker_deps_layer],
            environment={
                "DB_HOST": database_host,
                "DB_PORT": str(database_port),
                "DB_NAME": "platform_dev",
                "DATABASE_SECRET_ARN": db_secret.secret_arn,
                "MIGRATIONS_DIR": "/var/task/database/migrations",
            },
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=list(private_subnets)),
            security_groups=[lambda_security_group],
            log_group=migration_runner_log_group,
        )

        # Migration runner permissions
        migration_runner_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
                resources=[db_secret.secret_arn],
            )
        )
        migration_runner_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt", "kms:DescribeKey"],
                resources=[secrets_key.key_arn],
            )
        )

        # Expose references
        self.ingestion_lambda = ingestion_lambda
        self.silver_processor_lambda = silver_processor_lambda
        self.migration_runner_lambda = migration_runner_lambda
        self.state_machine = state_machine
        self.event_rule = rule

        # Outputs
        CfnOutput(
            self,
            "IngestionWorkerLambdaArn",
            value=ingestion_lambda.function_arn,
            description="ARN of ingestion worker Lambda",
            export_name=f"{self.stack_name}-IngestionWorkerLambdaArn",
        )
        CfnOutput(
            self,
            "MigrationRunnerLambdaArn",
            value=migration_runner_lambda.function_arn,
            description="ARN of migration runner Lambda",
            export_name=f"{self.stack_name}-MigrationRunnerLambdaArn",
        )
        CfnOutput(
            self,
            "PdfIngestionStateMachineArn",
            value=state_machine.state_machine_arn,
            description="ARN of PDF ingestion Step Functions state machine",
            export_name=f"{self.stack_name}-PdfIngestionStateMachineArn",
        )

