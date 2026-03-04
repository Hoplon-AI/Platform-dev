"""
Compute stack: ECS Fargate cluster, ALB, and service definitions.
"""
import os
from pathlib import Path

from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_logs as logs,
    aws_ecr_assets as ecr_assets,
    Duration,
    Tags,
    RemovalPolicy,
)
from constructs import Construct

# Path to project root (where Dockerfile lives)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


class ComputeStack(Stack):
    """Compute infrastructure: ECS Fargate and ALB."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        private_subnets: list[ec2.ISubnet],
        public_subnets: list[ec2.ISubnet],
        bronze_bucket,
        db_secret,
        secrets_key,
        s3_key,
        database_security_group: ec2.ISecurityGroup,
        database_host: str = "",
        database_port: int = 5432,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # CloudWatch Log Group for ECS (kept in Compute stack with ECS roles)
        log_group = logs.LogGroup(
            self,
            "EcsLogGroup",
            log_group_name="/ecs/platform-dev",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ECS Task Execution Role (for pulling images, writing logs, etc.)
        ecs_execution_role = iam.Role(
            self,
            "EcsTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        # ECS Task Role (for application permissions)
        ecs_task_role = iam.Role(
            self,
            "EcsTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Grant Secrets Manager access to tasks WITHOUT adding resource policies on the secret/key
        # (cross-stack grant_* helpers can introduce cyclic references).
        ecs_execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
                resources=[db_secret.secret_arn],
            )
        )
        ecs_task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
                resources=[db_secret.secret_arn],
            )
        )
        # KMS decrypt for the Secrets Manager CMK
        ecs_execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt", "kms:DescribeKey"],
                resources=[secrets_key.key_arn],
            )
        )
        ecs_task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt", "kms:DescribeKey"],
                resources=[secrets_key.key_arn],
            )
        )

        # ECS Cluster
        cluster = ecs.Cluster(
            self,
            "PlatformCluster",
            vpc=vpc,
            cluster_name="platform-dev",
            # container_insights is deprecated; use v2 API.
            container_insights_v2=ecs.ContainerInsights.ENABLED,
        )

        # Application Load Balancer
        alb = elbv2.ApplicationLoadBalancer(
            self,
            "PlatformALB",
            vpc=vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(subnets=public_subnets),
        )

        # Security Group for ALB
        alb_security_group = ec2.SecurityGroup(
            self,
            "ALBSecurityGroup",
            vpc=vpc,
            description="Security group for Application Load Balancer",
            allow_all_outbound=True,
        )

        # Allow HTTP/HTTPS from internet
        alb_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(80),
            "Allow HTTP from internet",
        )
        alb_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(443),
            "Allow HTTPS from internet",
        )

        # Associate security group with ALB
        alb.node.add_dependency(alb_security_group)

        # HTTPS Listener (HTTP redirects to HTTPS)
        # Note: Certificate needs to be created separately or via ACM
        # For now, using HTTP listener
        http_listener = alb.add_listener(
            "HttpListener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
        )

        # Fargate Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "BackendTaskDefinition",
            memory_limit_mib=1024,  # 1 GB for FastAPI + dependencies
            cpu=512,  # 0.5 vCPU for dev
            execution_role=ecs_execution_role,
            task_role=ecs_task_role,
        )

        # Build Docker image from project root
        backend_image = ecr_assets.DockerImageAsset(
            self,
            "BackendImage",
            directory=str(PROJECT_ROOT),
            platform=ecr_assets.Platform.LINUX_AMD64,
        )

        # Container definition
        container = task_definition.add_container(
            "BackendContainer",
            image=ecs.ContainerImage.from_docker_image_asset(backend_image),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="platform-backend",
                log_group=log_group,
            ),
            environment={
                "ENVIRONMENT": "dev",
                "AWS_DEFAULT_REGION": self.region,
                "BRONZE_BUCKET": bronze_bucket.bucket_name,
                "S3_BUCKET_NAME": bronze_bucket.bucket_name,
                "DB_SECRET_ARN": db_secret.secret_arn,
                "DATABASE_HOST": database_host,
                "DATABASE_PORT": str(database_port),
                "DEV_MODE": "true",
            },
        )

        container.add_port_mappings(
            ecs.PortMapping(
                container_port=8000,  # FastAPI port
                protocol=ecs.Protocol.TCP,
            )
        )

        # ECS Service
        service = ecs.FargateService(
            self,
            "BackendService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,  # Single instance for dev
            vpc_subnets=ec2.SubnetSelection(subnets=private_subnets),
            assign_public_ip=False,  # Use NAT for outbound
            security_groups=[
                self._create_service_security_group(
                    vpc, database_security_group
                )
            ],
        )

        # Add target to ALB
        http_listener.add_targets(
            "BackendTargets",
            port=8000,  # FastAPI port
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[service],
            health_check=elbv2.HealthCheck(
                path="/health",  # FastAPI health endpoint
                interval=Duration.seconds(30),
                timeout=Duration.seconds(10),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
        )

        # Auto Scaling (minimal for dev)
        scaling = service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=2,  # Max 2 for dev
        )

        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
        )

        # Grant S3 access to task role (least privilege)
        bronze_bucket.grant_read_write(ecs_task_role)

        # Grant KMS permissions for S3 encryption
        s3_key.grant_encrypt_decrypt(ecs_task_role)

        # Also grant access to processed bucket if needed
        # processed_bucket.grant_read(ecs_task_role)  # Uncomment if needed

        # Tag resources
        Tags.of(cluster).add("app", "platform")
        Tags.of(cluster).add("env", "dev")
        Tags.of(alb).add("app", "platform")
        Tags.of(alb).add("env", "dev")

        # Store references
        self.cluster = cluster
        self.service = service
        self.alb = alb
        self.alb_security_group = alb_security_group
        self.ecs_execution_role = ecs_execution_role
        self.ecs_task_role = ecs_task_role

        # Outputs
        CfnOutput(
            self,
            "ClusterName",
            value=cluster.cluster_name,
            description="ECS cluster name",
            export_name=f"{self.stack_name}-ClusterName",
        )

        CfnOutput(
            self,
            "ALBDnsName",
            value=alb.load_balancer_dns_name,
            description="Application Load Balancer DNS name",
            export_name=f"{self.stack_name}-ALBDnsName",
        )

        CfnOutput(
            self,
            "ServiceName",
            value=service.service_name,
            description="ECS service name",
            export_name=f"{self.stack_name}-ServiceName",
        )

    def _create_service_security_group(
        self, vpc: ec2.IVpc, database_sg: ec2.ISecurityGroup
    ) -> ec2.SecurityGroup:
        """Create security group for ECS service with minimal rules."""
        sg = ec2.SecurityGroup(
            self,
            "ServiceSecurityGroup",
            vpc=vpc,
            description="Security group for ECS Fargate service",
            allow_all_outbound=True,  # Allow outbound for package installs, etc.
        )

        # Allow inbound from ALB only
        # This will be set by ALB target group automatically, but explicit for clarity

        # Allow outbound to database
        sg.connections.allow_to(
            database_sg,
            ec2.Port.tcp(5432),
            "Allow PostgreSQL access",
        )

        return sg
