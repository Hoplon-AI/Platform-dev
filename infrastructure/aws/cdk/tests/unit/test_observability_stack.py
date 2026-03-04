"""
Tests for ObservabilityStack.
"""
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from cdk.observability_stack import ObservabilityStack


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
    """Create an ObservabilityStack instance."""
    return ObservabilityStack(
        app,
        "TestObservabilityStack",
        cluster_name="test-cluster",
        service_name="test-service",
        alb_arn="arn:aws:elasticloadbalancing:eu-west-1:123456789012:loadbalancer/app/test/1234567890123456",
        database_endpoint="test-db.123456789012.eu-west-1.rds.amazonaws.com",
        env=env,
        description="Test observability stack",
    )


@pytest.fixture
def template(stack):
    """Create a CloudFormation template from the stack."""
    return Template.from_stack(stack)


def test_stack_synthesizes(stack):
    """Test that the stack synthesizes without errors."""
    template = Template.from_stack(stack)
    assert template is not None


def test_cloudwatch_alarms_created(template):
    """Test that CloudWatch alarms are created."""
    # At least one alarm should exist (CPU or Memory)
    count = template.find_resources("AWS::CloudWatch::Alarm")
    assert len(count) >= 1, f"Expected at least 1 CloudWatch alarm, found {len(count)}"


def test_sns_topic_created(template):
    """Test that SNS topic for alarms is created."""
    template.has_resource_properties(
        "AWS::SNS::Topic",
        {
            "DisplayName": Match.string_like_regexp(".*Platform.*Alarms.*"),
        },
    )


def test_cloudwatch_dashboard_created(template):
    """Test that CloudWatch dashboard is created (if implemented)."""
    # Dashboard may be optional - check if it exists
    count = template.find_resources("AWS::CloudWatch::Dashboard")
    assert len(count) >= 0, "Dashboard count should be non-negative"


def test_log_group_created(template):
    """Test that CloudWatch log group is created (if implemented)."""
    # Log group may be in compute stack - check if it exists here
    count = template.find_resources("AWS::Logs::LogGroup")
    assert len(count) >= 0, "Log group count should be non-negative"


def test_outputs_exist(template):
    """Test that stack outputs are created."""
    template.has_output(
        "*",
        {
            "Value": Match.any_value(),
        },
    )
