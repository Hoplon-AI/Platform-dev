"""
Shared pytest fixtures for all tests.
"""
import os
import pytest
import pytest_asyncio
import boto3
import asyncpg
from moto import mock_aws
from infrastructure.storage.s3_config import S3Config, set_s3_config


@pytest.fixture(autouse=True)
def mock_s3_service(monkeypatch):
    """
    Automatically mock S3 service for all tests using moto.
    This fixture is autouse=True so it applies to all tests.
    """
    with mock_aws():
        # Create a mock S3 bucket
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-platform-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        # Create a test S3Config and set it as the global config
        # Use moto's default endpoint (no endpoint_url needed)
        test_config = S3Config(
            bucket_name=bucket_name,
            region='us-east-1',
            access_key_id='test_key',
            secret_access_key='test_secret',
            endpoint_url=None,  # Moto intercepts boto3 calls automatically
        )
        set_s3_config(test_config)
        
        yield test_config


@pytest.fixture(autouse=True)
def set_dev_mode():
    """Set DEV_MODE environment variable for all tests."""
    os.environ["DEV_MODE"] = "true"
    yield
    # Cleanup: remove DEV_MODE after test
    os.environ.pop("DEV_MODE", None)


@pytest_asyncio.fixture
async def test_db_pool():
    """
    Create a test database pool.
    
    Note: This requires PostgreSQL to be running with a test database.
    The test database should be created manually or via a setup script.
    """
    # Try to connect to test database
    # If it doesn't exist, the test will fail with a clear error
    try:
        pool = await asyncpg.create_pool(
            host=os.getenv('TEST_DB_HOST', 'localhost'),
            port=int(os.getenv('TEST_DB_PORT', '5432')),
            user=os.getenv('TEST_DB_USER', 'postgres'),
            password=os.getenv('TEST_DB_PASSWORD', 'postgres'),
            database=os.getenv('TEST_DB_NAME', 'platform_dev_test'),
            min_size=2,
            max_size=5,
        )
        yield pool
        await pool.close()
    except asyncpg.InvalidCatalogNameError:
        pytest.skip("Test database 'platform_dev_test' does not exist. Create it with: CREATE DATABASE platform_dev_test;")
    except asyncpg.PostgresConnectionError as e:
        pytest.skip(f"Could not connect to test database: {e}")
