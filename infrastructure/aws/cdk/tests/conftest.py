"""
Pytest configuration and fixtures for CDK stack tests.
"""
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template


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
    """Base stack fixture - override in specific test files."""
    return cdk.Stack(app, "TestStack", env=env)


@pytest.fixture
def template(stack):
    """Create a CloudFormation template from a stack."""
    return Template.from_stack(stack)
