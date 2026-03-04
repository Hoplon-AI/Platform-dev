"""
Helper Lambda function to enable PostGIS extension in RDS.
This can be run as a one-time setup after database creation.
"""
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_rds as rds,
)
from constructs import Construct


class PostGisSetupFunction(Construct):
    """Lambda function to enable PostGIS extension."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        database: rds.DatabaseInstance,
        db_secret_arn: str,
        vpc: ec2.IVpc,
        security_group: ec2.ISecurityGroup,
    ) -> None:
        super().__init__(scope, construct_id)

        # Lambda function to enable PostGIS
        postgis_function = _lambda.Function(
            self,
            "EnablePostGisFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
import boto3
import psycopg2
import json
import os

def handler(event, context):
    secrets_client = boto3.client('secretsmanager')
    
    # Get database credentials from Secrets Manager
    secret = secrets_client.get_secret_value(SecretId='{secret_arn}')
    credentials = json.loads(secret['SecretString'])
    
    # Connect to database
    conn = psycopg2.connect(
        host='{db_endpoint}',
        port=5432,
        database='platform_dev',
        user=credentials['username'],
        password=credentials['password']
    )
    
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Enable PostGIS extension
    cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    cursor.execute("SELECT postgis_version();")
    version = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return {{
        'statusCode': 200,
        'body': json.dumps({{
            'message': 'PostGIS enabled successfully',
            'version': version[0] if version else 'unknown'
        }})
    }}
""".format(
                    secret_arn=db_secret_arn,
                    db_endpoint=database.cluster_endpoint.hostname,
                )
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[security_group],
            timeout=Duration.minutes(5),
            memory_size=256,
        )

        # Grant permissions
        postgis_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[db_secret_arn],
            )
        )

        self.function = postgis_function
