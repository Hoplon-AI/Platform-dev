"""
Database connection pool using asyncpg.
"""
import asyncpg
import json
from typing import Optional
import os
from contextlib import asynccontextmanager


def _get_db_credentials_from_secret() -> dict:
    """
    Fetch database credentials from AWS Secrets Manager.

    Returns:
        dict with host, port, username, password, dbname keys
    """
    secret_arn = os.getenv("DB_SECRET_ARN")
    if not secret_arn:
        return {}

    import boto3
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response["SecretString"])


class DatabasePool:
    """AsyncPG connection pool manager."""

    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def initialize(
        cls,
        host: str = None,
        port: int = None,
        user: str = None,
        password: str = None,
        database: str = None,
        min_size: int = 5,
        max_size: int = 20,
    ):
        """
        Initialize the database connection pool.

        Credential resolution order:
        1. Explicit function arguments
        2. DB_SECRET_ARN (AWS Secrets Manager)
        3. Individual env vars (DB_HOST, DB_USER, etc.)
        4. Defaults (localhost, postgres, etc.)

        Args:
            host: Database host
            port: Database port
            user: Database user
            password: Database password
            database: Database name
            min_size: Minimum pool size
            max_size: Maximum pool size
        """
        if cls._pool is None:
            # Try to get credentials from Secrets Manager
            try:
                secret_creds = _get_db_credentials_from_secret()
                print(f"[DB_POOL] Got credentials from Secrets Manager: host={secret_creds.get('host')}, user={secret_creds.get('username')}, db={secret_creds.get('dbname')}")
            except Exception as e:
                print(f"[DB_POOL] Failed to get credentials from Secrets Manager: {e}")
                secret_creds = {}

            db_host = host or secret_creds.get("host") or os.getenv('DATABASE_HOST') or os.getenv('DB_HOST', 'localhost')
            db_port = port or int(secret_creds.get("port", 0) or os.getenv('DATABASE_PORT') or os.getenv('DB_PORT', 5432))
            db_user = user or secret_creds.get("username") or os.getenv('DB_USER', 'postgres')
            db_password = password or secret_creds.get("password") or os.getenv('DB_PASSWORD', 'postgres')
            db_name = database or secret_creds.get("dbname") or os.getenv('DB_NAME', 'platform_dev')

            print(f"[DB_POOL] Connecting to {db_host}:{db_port}/{db_name} as {db_user}")

            try:
                cls._pool = await asyncpg.create_pool(
                    host=db_host,
                    port=db_port,
                    user=db_user,
                    password=db_password,
                    database=db_name,
                    min_size=min_size,
                    max_size=max_size,
                    command_timeout=30,
                )
                print(f"[DB_POOL] Connection pool created successfully")
            except Exception as e:
                print(f"[DB_POOL] Failed to create connection pool: {e}")
                raise
    
    @classmethod
    async def close(cls):
        """Close the database connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
    
    @classmethod
    def get_pool(cls) -> asyncpg.Pool:
        """
        Get the database connection pool.
        
        Raises:
            RuntimeError: If pool is not initialized
        """
        if cls._pool is None:
            raise RuntimeError("Database pool not initialized. Call DatabasePool.initialize() first.")
        return cls._pool
    
    @classmethod
    @asynccontextmanager
    async def acquire(cls):
        """
        Acquire a connection from the pool (context manager).
        
        Usage:
            async with DatabasePool.acquire() as conn:
                await conn.execute("SELECT ...")
        """
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            yield conn
    
    @classmethod
    async def execute(cls, query: str, *args):
        """
        Execute a query using a connection from the pool.
        
        Args:
            query: SQL query string
            *args: Query parameters
            
        Returns:
            Query result
        """
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    @classmethod
    async def fetch(cls, query: str, *args):
        """
        Fetch rows from a query.
        
        Args:
            query: SQL query string
            *args: Query parameters
            
        Returns:
            List of Record objects
        """
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    @classmethod
    async def fetchrow(cls, query: str, *args):
        """
        Fetch a single row from a query.
        
        Args:
            query: SQL query string
            *args: Query parameters
            
        Returns:
            Record object or None
        """
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    @classmethod
    async def fetchval(cls, query: str, *args):
        """
        Fetch a single value from a query.
        
        Args:
            query: SQL query string
            *args: Query parameters
            
        Returns:
            Single value or None
        """
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)
