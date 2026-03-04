"""
Database adapter interface for dependency injection.
Allows classes to accept a database pool for testability.
"""
from typing import Protocol, Optional, List, Any
import asyncpg


class IDatabaseAdapter(Protocol):
    """Protocol for database adapters (allows dependency injection and mocking)."""
    
    async def execute(self, query: str, *args) -> str:
        """Execute a query."""
        ...
    
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Fetch rows from a query."""
        ...
    
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row from a query."""
        ...
    
    async def fetchval(self, query: str, *args) -> Optional[Any]:
        """Fetch a single value from a query."""
        ...


class AsyncPGAdapter:
    """Database adapter implementation using asyncpg pool."""
    
    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize adapter with an asyncpg pool.
        
        Args:
            pool: asyncpg.Pool instance
        """
        self.pool = pool
    
    async def execute(self, query: str, *args) -> str:
        """Execute a query."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Fetch rows from a query."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row from a query."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args) -> Optional[Any]:
        """Fetch a single value from a query."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)


class GlobalDatabaseAdapter:
    """Adapter that uses the global DatabasePool (default behavior for production)."""
    
    async def execute(self, query: str, *args) -> str:
        """Execute a query using global pool."""
        from backend.core.database.db_pool import DatabasePool
        pool = DatabasePool.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Fetch rows using global pool."""
        from backend.core.database.db_pool import DatabasePool
        pool = DatabasePool.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row using global pool."""
        from backend.core.database.db_pool import DatabasePool
        pool = DatabasePool.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args) -> Optional[Any]:
        """Fetch a single value using global pool."""
        from backend.core.database.db_pool import DatabasePool
        pool = DatabasePool.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)
