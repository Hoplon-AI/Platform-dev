"""
Tests for NetworkingStack.
"""
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from cdk.networking_stack import NetworkingStack


@pytest.fixture
def app():
    """Create a CDK app for testing."""
    return cdk.App()


@pytest.fixture
def env():
    """Create a test environment."""
    return cdk.Environment(account="123456789012", region="eu-west-1")


@pytest.fixture
def stack(app, env):
    """Create a NetworkingStack instance."""
    return NetworkingStack(
        app,
        "TestNetworkingStack",
        env=env,
        description="Test networking stack",
    )


@pytest.fixture
def template(stack):
    """Create a CloudFormation template from the stack."""
    return Template.from_stack(stack)


def test_stack_synthesizes(stack):
    """Test that the stack synthesizes without errors."""
    template = Template.from_stack(stack)
    assert template is not None


def test_vpc_created(template):
    """Test that a VPC is created."""
    template.has_resource_properties(
        "AWS::EC2::VPC",
        {
            "CidrBlock": "10.0.0.0/16",
            "EnableDnsHostnames": True,
            "EnableDnsSupport": True,
            "Tags": Match.array_with([
                Match.object_like({"Key": "app", "Value": "platform"}),
                Match.object_like({"Key": "env", "Value": "dev"}),
            ]),
        },
    )


def test_public_subnets_created(template):
    """Test that public subnets are created."""
    template.resource_count_is("AWS::EC2::Subnet", 6)  # 2 AZs * 3 subnet types


def test_nat_gateway_created(template):
    """Test that NAT Gateway is created."""
    template.has_resource_properties(
        "AWS::EC2::NatGateway",
        Match.any_value(),
    )


def test_vpc_endpoints_created(template):
    """Test that VPC endpoints are created."""
    # At least one VPC endpoint should exist
    count = template.find_resources("AWS::EC2::VPCEndpoint")
    assert len(count) >= 1, f"Expected at least 1 VPC endpoint, found {len(count)}"


def test_internet_gateway_created(template):
    """Test that Internet Gateway is created."""
    template.has_resource_properties(
        "AWS::EC2::InternetGateway",
        Match.any_value(),
    )


def test_route_tables_created(template):
    """Test that route tables are created."""
    # Route tables are created by VPC, at least one should exist
    count = template.find_resources("AWS::EC2::RouteTable")
    assert len(count) >= 1, f"Expected at least 1 route table, found {len(count)}"


def test_outputs_exist(template):
    """Test that stack outputs are created."""
    template.has_output(
        "*",
        {
            "Value": Match.any_value(),
        },
    )
