# TDD + asyncpg Implementation Pattern with Dependency Injection

This document outlines the Test-Driven Development (TDD) pattern using asyncpg with dependency injection for implementing database operations in this project.

## Pattern Overview

1. **Write tests first** (TDD approach)
2. **Use dependency injection** - Accept `db_pool` parameter in `__init__`
3. **Use asyncpg** via database adapter interface
4. **Make methods async** when they interact with the database
5. **Handle RuntimeError** gracefully when database pool is not initialized

## Database Adapter Pattern

All database operations use a **database adapter** for dependency injection. This allows:
- **Testing**: Inject test database pools
- **Flexibility**: Use different pools in different contexts
- **Production**: Default to global pool when `db_pool=None`

### Adapter Interface

```python
from backend.core.database.db_adapter import (
    IDatabaseAdapter,
    AsyncPGAdapter,
    GlobalDatabaseAdapter,
)
```

### Class Implementation Pattern

```python
import asyncpg
from backend.core.database.db_adapter import (
    IDatabaseAdapter,
    AsyncPGAdapter,
    GlobalDatabaseAdapter,
)

class YourClass:
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        """
        Initialize your class.
        
        Args:
            db_pool: Optional asyncpg.Pool instance. If provided, uses this pool.
                     If None, uses the global DatabasePool (production default).
        """
        if db_pool is not None:
            self.db_adapter: IDatabaseAdapter = AsyncPGAdapter(db_pool)
        else:
            self.db_adapter: IDatabaseAdapter = GlobalDatabaseAdapter()
    
    async def your_method(self):
        """Use self.db_adapter for all database operations."""
        await self.db_adapter.execute("INSERT INTO ...", param1, param2)
        record = await self.db_adapter.fetchrow("SELECT * FROM ...", param1)
        records = await self.db_adapter.fetch("SELECT * FROM ...", param1)
        value = await self.db_adapter.fetchval("SELECT COUNT(*) FROM ...")
```

## Implementation Steps

### 1. Add asyncpg to requirements.txt
```txt
asyncpg==0.29.0
```

### 2. Write Tests First (TDD)

Create test file in `tests/` directory with **dependency injection**:

```python
import pytest
import asyncpg
from your_module import YourClass

@pytest.fixture
async def test_db_pool():
    """Create a test database pool."""
    pool = await asyncpg.create_pool(
        host='localhost',
        port=5432,
        user='postgres',
        password='postgres',
        database='platform_dev_test',
        min_size=2,
        max_size=5,
    )
    yield pool
    await pool.close()

@pytest.mark.asyncio
async def test_your_method_stores_data(test_db_pool):
    """Test that your method stores data correctly."""
    # Inject test database pool
    instance = YourClass(db_pool=test_db_pool)
    
    await instance.your_method(...)
    
    # Verify data was stored using the test pool
    async with test_db_pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT * FROM your_table WHERE id = $1",
            test_id
        )
    
    assert record is not None
    assert record['field'] == expected_value
```

### 3. Implement Methods Using Database Adapter

Make methods async and use `self.db_adapter`:

```python
import asyncpg
import json
import uuid
from typing import Optional
from backend.core.database.db_adapter import (
    IDatabaseAdapter,
    AsyncPGAdapter,
    GlobalDatabaseAdapter,
)

class YourClass:
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        """Initialize with optional database pool."""
        if db_pool is not None:
            self.db_adapter: IDatabaseAdapter = AsyncPGAdapter(db_pool)
        else:
            self.db_adapter: IDatabaseAdapter = GlobalDatabaseAdapter()
    
    async def your_method(self, param1: str, param2: int):
        """Your method description."""
        try:
            await self.db_adapter.execute(
                """
                INSERT INTO your_table (field1, field2, metadata)
                VALUES ($1, $2, $3)
                """,
                param1,
                param2,
                json.dumps({"key": "value"}) if metadata else None,
            )
        except (RuntimeError, AttributeError):
            # Database pool not initialized or adapter not available - skip operation
            pass
    
    async def get_data(self, id: str):
        """Retrieve data from database."""
        try:
            record = await self.db_adapter.fetchrow(
                """
                SELECT * FROM your_table WHERE id = $1
                """,
                uuid.UUID(id)
            )
            
            if record is None:
                return None
            
            # Convert record to your data structure
            return YourDataClass(
                id=str(record['id']),
                field1=record['field1'],
                # ...
            )
        except (RuntimeError, AttributeError):
            return None
```

## Key Patterns

### UUID Handling
```python
# When inserting
uuid.UUID(upload_id)

# When retrieving
str(record['upload_id'])
```

### JSONB Handling
```python
# When inserting
json.dumps(metadata) if metadata else None

# When retrieving
metadata = json.loads(record['metadata']) if record['metadata'] else {}
```

### Error Handling
Always wrap database operations in try/except to handle cases where the database pool is not initialized:

```python
try:
    await self.db_adapter.execute(...)
except (RuntimeError, AttributeError):
    # Database pool not initialized or adapter not available - skip operation
    pass
```

### Dependency Injection Benefits

1. **Testability**: Inject test database pools in tests
2. **Isolation**: Each test uses its own database connection
3. **Flexibility**: Can use different pools for different contexts
4. **Production Default**: When `db_pool=None`, uses global pool automatically

### Async Methods
All methods that interact with the database should be async:

```python
# Before (synchronous placeholder)
def get_data(self, id: str):
    pass

# After (async implementation with dependency injection)
async def get_data(self, id: str):
    record = await self.db_adapter.fetchrow(...)
    return record
```

## Examples

See implemented examples with dependency injection:
- `backend/core/database/db_adapter.py` - Database adapter interface and implementations
- `backend/core/audit/audit_logger.py` - AuditLogger with dependency injection
- `infrastructure/storage/version_manager.py` - VersionManager with dependency injection
- `tests/test_audit_logger.py` - TDD tests with injected test pools
- `tests/test_version_manager.py` - TDD tests with injected test pools

### Production Usage

```python
# Uses global DatabasePool automatically
manager = VersionManager()  # db_pool=None uses GlobalDatabaseAdapter
logger = AuditLogger()  # db_pool=None uses GlobalDatabaseAdapter
```

### Test Usage

```python
# Inject test database pool
test_pool = await asyncpg.create_pool(...)
manager = VersionManager(db_pool=test_pool)
logger = AuditLogger(db_pool=test_pool)
```

## Testing

Run tests with:
```bash
pytest tests/test_your_module.py -v
```

For async tests, ensure `pytest-asyncio` is installed and use `@pytest.mark.asyncio` decorator.

## Next Steps

Apply this pattern to other TODO implementations:
1. Write tests first
2. Implement using asyncpg via DatabasePool
3. Make methods async
4. Handle RuntimeError gracefully
