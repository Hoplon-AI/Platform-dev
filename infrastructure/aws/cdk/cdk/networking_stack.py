"""
Networking stack: VPC, subnets, routing, and VPC endpoints.
"""
from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
    Tags,
)
from constructs import Construct


class NetworkingStack(Stack):
    """VPC and networking infrastructure."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC Configuration
        vpc = ec2.Vpc(
            self,
            "PlatformVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,  # Use 2 AZs for dev, increase for prod
            nat_gateways=1,  # Single NAT for dev cost optimization
            subnet_configuration=[
                # Public subnets for ALB/NAT
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC,
                    name="Public",
                    cidr_mask=24,
                ),
                # Private subnets for application compute
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    name="PrivateApp",
                    cidr_mask=24,
                ),
                # Isolated subnets for databases
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    name="PrivateDB",
                    cidr_mask=24,
                ),
            ],
        )

        # VPC Endpoints to reduce NAT costs and improve security
        # S3 Gateway endpoint (no cost)
        ec2.GatewayVpcEndpoint(
            self,
            "S3Endpoint",
            vpc=vpc,
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        # ECR endpoints for container image pulls
        ec2.InterfaceVpcEndpoint(
            self,
            "ECREndpoint",
            vpc=vpc,
            service=ec2.InterfaceVpcEndpointAwsService.ECR,
        )

        ec2.InterfaceVpcEndpoint(
            self,
            "ECRDockerEndpoint",
            vpc=vpc,
            service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
        )

        # CloudWatch Logs endpoint
        ec2.InterfaceVpcEndpoint(
            self,
            "CloudWatchLogsEndpoint",
            vpc=vpc,
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
        )

        # Secrets Manager endpoint
        ec2.InterfaceVpcEndpoint(
            self,
            "SecretsManagerEndpoint",
            vpc=vpc,
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
        )

        # CloudWatch endpoint for metrics
        ec2.InterfaceVpcEndpoint(
            self,
            "CloudWatchEndpoint",
            vpc=vpc,
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH,
        )

        # Tag resources
        Tags.of(vpc).add("app", "platform")
        Tags.of(vpc).add("env", "dev")
        Tags.of(vpc).add("owner", "platform-dev")
        Tags.of(vpc).add("cost_center", "engineering")
        Tags.of(vpc).add("data_classification", "internal")

        # Export values for other stacks
        self.vpc = vpc
        self.public_subnets = vpc.public_subnets
        self.private_subnets = vpc.private_subnets
        self.database_subnets = vpc.isolated_subnets

        # Outputs
        CfnOutput(
            self,
            "VpcId",
            value=vpc.vpc_id,
            description="VPC ID",
            export_name=f"{self.stack_name}-VpcId",
        )

        CfnOutput(
            self,
            "PrivateSubnetIds",
            value=",".join([subnet.subnet_id for subnet in vpc.private_subnets]),
            description="Private subnet IDs",
            export_name=f"{self.stack_name}-PrivateSubnetIds",
        )

        CfnOutput(
            self,
            "DatabaseSubnetIds",
            value=",".join([subnet.subnet_id for subnet in vpc.isolated_subnets]),
            description="Database subnet IDs",
            export_name=f"{self.stack_name}-DatabaseSubnetIds",
        )
