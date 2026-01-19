"""
Database connection pool using asyncpg.
"""
import asyncpg
from typing import Optional
import os
from contextlib import asynccontextmanager


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
        
        Args:
            host: Database host (defaults to env var DB_HOST or 'localhost')
            port: Database port (defaults to env var DB_PORT or 5432)
            user: Database user (defaults to env var DB_USER or 'postgres')
            password: Database password (defaults to env var DB_PASSWORD or 'postgres')
            database: Database name (defaults to env var DB_NAME or 'platform_dev')
            min_size: Minimum pool size
            max_size: Maximum pool size
        """
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=host or os.getenv('DB_HOST', 'localhost'),
                port=port or int(os.getenv('DB_PORT', 5432)),
                user=user or os.getenv('DB_USER', 'postgres'),
                password=password or os.getenv('DB_PASSWORD', 'postgres'),
                database=database or os.getenv('DB_NAME', 'platform_dev'),
                min_size=min_size,
                max_size=max_size,
            )
    
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
