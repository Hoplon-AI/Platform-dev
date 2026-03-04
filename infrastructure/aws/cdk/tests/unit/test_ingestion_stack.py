"""
Tests for IngestionStack.
"""

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from cdk.ingestion_stack import IngestionStack
from cdk.networking_stack import NetworkingStack
from cdk.security_stack import SecurityStack
from cdk.data_stack import DataStack


@pytest.fixture
def app():
    return cdk.App()


@pytest.fixture
def env():
    return cdk.Environment(account="123456789012", region="eu-west-1")


@pytest.fixture
def networking_stack(app, env):
    return NetworkingStack(app, "TestNetworkingStack", env=env)


@pytest.fixture
def security_stack(app, env):
    return SecurityStack(app, "TestSecurityStack", env=env)


@pytest.fixture
def data_stack(app, env, networking_stack, security_stack):
    return DataStack(
        app,
        "TestDataStack",
        vpc=networking_stack.vpc,
        database_subnets=networking_stack.database_subnets,
        private_subnets=networking_stack.private_subnets,
        s3_key=security_stack.s3_key,
        rds_key=security_stack.rds_key,
        env=env,
    )


@pytest.fixture
def stack(app, env, data_stack, networking_stack, security_stack):
    return IngestionStack(
        app,
        "TestIngestionStack",
        bronze_bucket=data_stack.bronze_bucket,
        vpc=networking_stack.vpc,
        private_subnets=networking_stack.private_subnets,
        database_security_group=data_stack.database_security_group,
        db_secret=data_stack.db_secret,
        database_host=data_stack.database.cluster_endpoint.hostname,
        database_port=data_stack.database.cluster_endpoint.port,
        s3_key=security_stack.s3_key,
        secrets_key=data_stack.secrets_key,
        env=env,
    )


@pytest.fixture
def template(stack):
    return Template.from_stack(stack)


def test_stack_synthesizes(template):
    assert template is not None


def test_state_machine_created(template):
    template.resource_count_is("AWS::StepFunctions::StateMachine", 1)


def test_event_rule_created(template):
    template.resource_count_is("AWS::Events::Rule", 1)
    template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "EventPattern": Match.object_like(
                {
                    "source": ["aws.s3"],
                    "detail-type": ["Object Created"],
                }
            )
        },
    )


def test_worker_lambda_created(template):
    # Note: additional Lambda(s) may be synthesized (e.g., log retention custom resource).
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Handler": "backend.workers.stepfn_ingestion_worker.handler",
        },
    )

