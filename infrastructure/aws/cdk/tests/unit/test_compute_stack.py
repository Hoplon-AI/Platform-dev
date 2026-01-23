"""
Tests for ComputeStack.
"""
import aws_cdk as cdk
import pytest
from aws_cdk import aws_s3 as s3
from aws_cdk.assertions import Match, Template

from cdk.compute_stack import ComputeStack
from cdk.data_stack import DataStack
from cdk.networking_stack import NetworkingStack
from cdk.security_stack import SecurityStack


@pytest.fixture
def app():
    """Create a CDK app for testing."""
    return cdk.App()


@pytest.fixture
def env():
    """Create a test environment."""
    return cdk.Environment(account="123456789012", region="eu-west-1")


@pytest.fixture
def networking_stack(app, env):
    """Create a NetworkingStack for dependencies."""
    return NetworkingStack(
        app,
        "TestNetworkingStack",
        env=env,
        description="Test networking stack",
    )


@pytest.fixture
def security_stack(app, env):
    """Create a SecurityStack for dependencies."""
    return SecurityStack(
        app,
        "TestSecurityStack",
        env=env,
        description="Test security stack",
    )


@pytest.fixture
def data_stack(app, env, networking_stack, security_stack):
    """Create a DataStack for dependencies."""
    return DataStack(
        app,
        "TestDataStack",
        vpc=networking_stack.vpc,
        database_subnets=networking_stack.database_subnets,
        s3_key=security_stack.s3_key,
        rds_key=security_stack.rds_key,
        env=env,
        description="Test data stack",
    )


@pytest.fixture
def stack(app, env, networking_stack, data_stack):
    """Create a ComputeStack instance."""
    return ComputeStack(
        app,
        "TestComputeStack",
        vpc=networking_stack.vpc,
        private_subnets=networking_stack.private_subnets,
        public_subnets=networking_stack.public_subnets,
        bronze_bucket=data_stack.bronze_bucket,
        db_secret=data_stack.db_secret,
        secrets_key=data_stack.secrets_key,
        database_security_group=data_stack.database_security_group,
        env=env,
        description="Test compute stack",
    )


@pytest.fixture
def template(stack):
    """Create a CloudFormation template from the stack."""
    return Template.from_stack(stack)


def test_stack_synthesizes(stack):
    """Test that the stack synthesizes without errors."""
    template = Template.from_stack(stack)
    assert template is not None


def test_ecs_cluster_created(template):
    """Test that ECS cluster is created."""
    template.has_resource_properties(
        "AWS::ECS::Cluster",
        Match.any_value(),
    )


def test_ecs_service_created(template):
    """Test that ECS service is created."""
    template.has_resource_properties(
        "AWS::ECS::Service",
        {
            "LaunchType": "FARGATE",
            "DesiredCount": 1,
        },
    )


def test_alb_created(template):
    """Test that Application Load Balancer is created."""
    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::LoadBalancer",
        {
            "Type": "application",
            "Scheme": "internet-facing",
        },
    )


def test_target_group_created(template):
    """Test that target group is created."""
    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::TargetGroup",
        {
            "TargetType": "ip",
            "Protocol": "HTTP",
            "Port": Match.any_value(),  # Port may vary (8000 in implementation)
        },
    )


def test_ecs_task_definition_created(template):
    """Test that ECS task definition is created."""
    template.has_resource_properties(
        "AWS::ECS::TaskDefinition",
        {
            "RequiresCompatibilities": ["FARGATE"],
            "NetworkMode": "awsvpc",
            "Cpu": Match.string_like_regexp("256|512|1024"),
            "Memory": Match.string_like_regexp("512|1024|2048"),
        },
    )


def test_ecs_log_group_created(template):
    """Test that CloudWatch log group is created."""
    template.has_resource_properties(
        "AWS::Logs::LogGroup",
        {
            "LogGroupName": Match.string_like_regexp("/ecs/.*"),
        },
    )


def test_iam_roles_created(template):
    """Test that IAM roles are created."""
    # ECS Task Execution Role
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": Match.array_with([
                    Match.object_like({
                        "Action": "sts:AssumeRole",
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "ecs-tasks.amazonaws.com",
                        },
                    }),
                ]),
            },
        },
    )


def test_security_groups_created(template):
    """Test that security groups are created."""
    # At least 2 security groups should exist (ALB + ECS service)
    count = template.find_resources("AWS::EC2::SecurityGroup")
    assert len(count) >= 2, f"Expected at least 2 security groups, found {len(count)}"


def test_outputs_exist(template):
    """Test that stack outputs are created."""
    template.has_output(
        "*",
        {
            "Value": Match.any_value(),
        },
    )
