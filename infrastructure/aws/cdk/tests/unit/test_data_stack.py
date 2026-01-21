"""
Tests for DataStack.
"""
import aws_cdk as cdk
import pytest
from aws_cdk import aws_ec2 as ec2, aws_kms as kms
from aws_cdk.assertions import Match, Template

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
def stack(app, env, networking_stack, security_stack):
    """Create a DataStack instance."""
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
def template(stack):
    """Create a CloudFormation template from the stack."""
    return Template.from_stack(stack)


def test_stack_synthesizes(stack):
    """Test that the stack synthesizes without errors."""
    template = Template.from_stack(stack)
    assert template is not None


def test_s3_buckets_created(template):
    """Test that S3 buckets are created."""
    # Bronze bucket
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketName": Match.string_like_regexp("platform-bronze-.*"),
            "VersioningConfiguration": {
                "Status": "Enabled",
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
        },
    )
    
    # Processed bucket
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketName": Match.string_like_regexp("platform-processed-.*"),
            "VersioningConfiguration": {
                "Status": "Enabled",
            },
        },
    )


def test_s3_buckets_encrypted(template):
    """Test that S3 buckets use KMS encryption."""
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": Match.array_with([
                    Match.object_like({
                        "ServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                        },
                    }),
                ]),
            },
        },
    )


def test_s3_ssl_only_policy(template):
    """Test that S3 buckets have SSL-only bucket policies."""
    template.has_resource_properties(
        "AWS::S3::BucketPolicy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with([
                    Match.object_like({
                        "Sid": "DenyInsecureConnections",
                        "Effect": "Deny",
                        "Condition": {
                            "Bool": {
                                "aws:SecureTransport": "false",
                            },
                        },
                    }),
                ]),
            },
        },
    )


def test_rds_instance_created(template):
    """Test that RDS PostgreSQL instance is created."""
    template.has_resource_properties(
        "AWS::RDS::DBInstance",
        {
            "Engine": "postgres",
            "DBInstanceClass": Match.string_like_regexp("db\\.t3\\..*"),
            "AllocatedStorage": "20",
            "StorageEncrypted": True,
            "PubliclyAccessible": False,
            "MultiAZ": False,
            "DeletionProtection": False,
        },
    )


def test_rds_subnet_group_created(template):
    """Test that RDS subnet group is created."""
    template.has_resource_properties(
        "AWS::RDS::DBSubnetGroup",
        {
            "DBSubnetGroupDescription": "Subnet group for RDS database",
        },
    )


def test_database_secret_created(template):
    """Test that Secrets Manager secret is created."""
    template.has_resource_properties(
        "AWS::SecretsManager::Secret",
        {
            "Description": "RDS PostgreSQL database credentials",
            "GenerateSecretString": {
                "SecretStringTemplate": Match.string_like_regexp(".*username.*"),
                "GenerateStringKey": "password",
                "PasswordLength": 32,
            },
        },
    )


def test_secrets_manager_key_created(template):
    """Test that KMS key for Secrets Manager is created."""
    template.has_resource_properties(
        "AWS::KMS::Key",
        {
            "Description": "KMS key for Secrets Manager encryption",
            "EnableKeyRotation": True,
        },
    )


def test_s3_lifecycle_rules(template):
    """Test that S3 buckets have lifecycle rules."""
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "LifecycleConfiguration": {
                "Rules": Match.array_with([
                    Match.object_like({
                        "Id": "TransitionToIA",
                        "Status": "Enabled",
                    }),
                ]),
            },
        },
    )


def test_outputs_exist(template):
    """Test that stack outputs are created."""
    template.has_output(
        "*",
        {
            "Value": Match.any_value(),
        },
    )
