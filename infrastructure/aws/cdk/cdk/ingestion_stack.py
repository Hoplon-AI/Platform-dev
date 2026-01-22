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
            code=worker_layer_code,
            description=(
                "Dependencies for ingestion worker (asyncpg, pdfplumber, etc.). "
                "Set CDK_USE_DOCKER_BUNDLING=true to build this layer."
            ),
        )

        # Lambda worker
        ingestion_lambda = lambda_.Function(
            self,
            "IngestionWorkerLambda",
            function_name="platform-dev-ingestion-worker",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="backend.workers.stepfn_ingestion_worker.handler",
            code=lambda_.Code.from_asset(
                project_root,
                exclude=[
                    ".git/**",
                    "**/__pycache__/**",
                    "frontend/node_modules/**",
                    "frontend/dist/**",
                    "venv/**",
                    "venv_local/**",
                    "infrastructure/aws/cdk/.venv/**",
                    "infrastructure/aws/cdk/cdk.out/**",
                    "*.sqlite",
                    "*.log",
                    ".DS_Store",
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
                "S3_BUCKET_NAME": bronze_bucket.bucket_name,
                # Keep max attempts consistent across infra and app logic
                "PDF_PROCESSING_MAX_ATTEMPTS": "5",
            },
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=list(private_subnets)),
            security_groups=[database_security_group],
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Permissions (avoid cross-stack resource policy mutations to prevent cycles)
        # S3: read/write objects + list bucket
        ingestion_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=[
                    bronze_bucket.bucket_arn,
                    f"{bronze_bucket.bucket_arn}/*",
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

        # KMS decrypt (S3 CMK + Secrets CMK). Assumes key policies allow IAM in-account usage.
        ingestion_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt", "kms:DescribeKey"],
                resources=[s3_key.key_arn, secrets_key.key_arn],
            )
        )

        # Silver processor Lambda (writes features to normalized PG tables)
        silver_processor_lambda = lambda_.Function(
            self,
            "SilverProcessorLambda",
            function_name="platform-dev-silver-processor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="backend.workers.silver_processor.handler",
            code=lambda_.Code.from_asset(
                project_root,
                exclude=[
                    ".git/**",
                    "**/__pycache__/**",
                    "frontend/node_modules/**",
                    "frontend/dist/**",
                    "venv/**",
                    "venv_local/**",
                    "infrastructure/aws/cdk/.venv/**",
                    "infrastructure/aws/cdk/cdk.out/**",
                    "*.sqlite",
                    "*.log",
                    ".DS_Store",
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
                "S3_BUCKET_NAME": bronze_bucket.bucket_name,
            },
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=list(private_subnets)),
            security_groups=[database_security_group],
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Silver processor permissions
        bronze_bucket.grant_read(silver_processor_lambda)
        db_secret.grant_read(silver_processor_lambda)
        s3_key.grant_decrypt(silver_processor_lambda)
        secrets_key.grant_decrypt(silver_processor_lambda)

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
        rule = events.Rule(
            self,
            "BronzeSourceObjectCreatedRule",
            description="Start PDF ingestion state machine on source file PUT (keys containing /file=).",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [bronze_bucket.bucket_name]},
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

        # Expose references
        self.ingestion_lambda = ingestion_lambda
        self.silver_processor_lambda = silver_processor_lambda
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
            "PdfIngestionStateMachineArn",
            value=state_machine.state_machine_arn,
            description="ARN of PDF ingestion Step Functions state machine",
            export_name=f"{self.stack_name}-PdfIngestionStateMachineArn",
        )

