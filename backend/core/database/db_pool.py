"""
Database connection pool using asyncpg.
"""
import json
import os
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg


def _get_db_credentials_from_secret() -> dict:
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
        min_size: int = 1,
        max_size: int = 5,
    ):
        if cls._pool is not None:
            return

        database_url = os.getenv("DATABASE_URL")

        if database_url:
            print("[DB_POOL] Connecting using DATABASE_URL")
            try:
                cls._pool = await asyncpg.create_pool(
                    dsn=database_url,
                    min_size=min_size,
                    max_size=max_size,
                    command_timeout=30,
                )
                print("[DB_POOL] Connection pool created successfully")
                return
            except Exception as e:
                print(f"[DB_POOL] Failed to create DATABASE_URL pool: {e}")
                raise

        try:
            secret_creds = _get_db_credentials_from_secret()
            print(
                "[DB_POOL] Got credentials from Secrets Manager: "
                f"host={secret_creds.get('host')}, "
                f"user={secret_creds.get('username')}, "
                f"db={secret_creds.get('dbname')}"
            )
        except Exception as e:
            print(f"[DB_POOL] Failed to get credentials from Secrets Manager: {e}")
            secret_creds = {}

        db_host = (
            host
            or secret_creds.get("host")
            or os.getenv("DATABASE_HOST")
            or os.getenv("DB_HOST", "localhost")
        )
        db_port = port or int(
            secret_creds.get("port", 0)
            or os.getenv("DATABASE_PORT")
            or os.getenv("DB_PORT", 5432)
        )
        db_user = (
            user
            or secret_creds.get("username")
            or os.getenv("DATABASE_USER")
            or os.getenv("DB_USER", "postgres")
        )
        db_password = (
            password
            or secret_creds.get("password")
            or os.getenv("DATABASE_PASSWORD")
            or os.getenv("DB_PASSWORD", "postgres")
        )
        db_name = (
            database
            or secret_creds.get("dbname")
            or os.getenv("DATABASE_NAME")
            or os.getenv("DB_NAME", "platform_dev")
        )

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
            print("[DB_POOL] Connection pool created successfully")
        except Exception as e:
            print(f"[DB_POOL] Failed to create connection pool: {e}")
            raise

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

    @classmethod
    def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            raise RuntimeError("Database pool not initialized. Call DatabasePool.initialize() first.")
        return cls._pool

    @classmethod
    @asynccontextmanager
    async def acquire(cls):
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            yield conn

    @classmethod
    async def execute(cls, query: str, *args):
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)

    @classmethod
    async def fetch(cls, query: str, *args):
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    @classmethod
    async def fetchrow(cls, query: str, *args):
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    @classmethod
    async def fetchval(cls, query: str, *args):
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)